from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from utils.embedding import EmbeddingUtil
from services.knowledge_base import KnowledgeBase
from services.semantic_chunker import SemanticChunker
from services.query_rewriter import QueryRewriter


class RAGResult:
    """RAG检索结果"""
    def __init__(self, content: str, source: str, score: float, metadata: Optional[Dict] = None):
        self.content = content
        self.source = source
        self.score = score
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {"content": self.content, "source": self.source, "score": self.score, "metadata": self.metadata}


class RAGPipeline:
    """混合检索：ES全文 + ES向量 + RRF融合 + CRAG纠错"""

    def __init__(self):
        self._chunker = SemanticChunker()
        self._rewriter = QueryRewriter()
        self._embedder = EmbeddingUtil(dim=768)
        self._kb = KnowledgeBase()
        self._es_client = None

    def _es_available(self) -> bool:
        try:
            from models.database import db_manager
            return db_manager.es_client is not None
        except Exception:
            return False

    async def retrieve(self, query: str, top_k: int = 5) -> List[RAGResult]:
        """主检索入口"""
        # 1. 查询重写
        try:
            rewritten = await self._rewrite_query(query)
        except Exception:
            rewritten = query

        # 2. 检索
        if self._es_available():
            try:
                bm25_results = await self._es_search(rewritten, top_k * 2)
                vector_results = await self._vector_search(rewritten, top_k * 2)
                fused = self._rrf_fuse(bm25_results, vector_results)
            except Exception as e:
                logger.warning(f"ES search failed, falling back to KB: {e}")
                fused = self._kb_search(rewritten, top_k * 2)
        else:
            fused = self._kb_search(rewritten, top_k * 2)

        # 3. CRAG纠错
        if self._assess_relevance(fused, query) < 0.5 and len(fused) > 0:
            try:
                rewritten_v2 = await self._rewrite_with_context(query, fused)
                if self._es_available():
                    fused_v2 = await self._es_search(rewritten_v2, top_k)
                else:
                    fused_v2 = self._kb_search(rewritten_v2, top_k)
                if fused_v2:
                    fused = fused_v2
            except Exception as e:
                logger.debug(f"CRAG correction failed: {e}")

        return fused[:top_k]

    async def _rewrite_query(self, query: str) -> str:
        """查询重写"""
        try:
            result = self._rewriter.rewrite(query)
            if isinstance(result, str):
                return result
            return result.get("rewritten", query) if isinstance(result, dict) else query
        except Exception:
            return query

    async def _es_search(self, query: str, top_k: int) -> List[RAGResult]:
        """ES全文检索 (BM25)"""
        from models.database import db_manager
        es = db_manager.es_client
        if es is None:
            return []
        try:
            result = await es.search(
                index="ontology",
                body={
                    "query": {"match": {"content": {"query": query}}},
                    "size": top_k,
                },
            )
            hits = result.get("hits", {}).get("hits", [])
            return [RAGResult(
                content=h["_source"].get("content", ""),
                source=h["_source"].get("source", "es_bm25"),
                score=h["_score"],
                metadata=h["_source"],
            ) for h in hits]
        except Exception as e:
            logger.debug(f"ES BM25 search failed: {e}")
            return []

    async def _vector_search(self, query: str, top_k: int) -> List[RAGResult]:
        """ES向量检索 (kNN)"""
        from models.database import db_manager
        es = db_manager.es_client
        if es is None:
            return []
        try:
            query_emb = self._embedder.embed(query)
            result = await es.search(
                index="ontology",
                body={
                    "query": {
                        "script_score": {
                            "query": {"match_all": {}},
                            "script": {
                                "source": "cosineSimilarity(params.query_vector, 'embedding') + 1.0",
                                "params": {"query_vector": query_emb},
                            },
                        }
                    },
                    "size": top_k,
                },
            )
            hits = result.get("hits", {}).get("hits", [])
            return [RAGResult(
                content=h["_source"].get("content", ""),
                source=h["_source"].get("source", "es_vector"),
                score=h["_score"],
                metadata=h["_source"],
            ) for h in hits]
        except Exception as e:
            logger.debug(f"ES vector search failed: {e}")
            return []

    def _kb_search(self, query: str, top_k: int) -> List[RAGResult]:
        """内存KnowledgeBase后备检索"""
        try:
            results = self._kb.search(query, top_k=top_k)
            return [RAGResult(
                content=r.get("chunk_text", ""),
                source=r.get("source", "kb"),
                score=r.get("relevance", 0),
            ) for r in results]
        except Exception:
            return []

    def _rrf_fuse(
        self,
        bm25_results: List[RAGResult],
        vector_results: List[RAGResult],
        bm25_weight: float = 0.3,
        vector_weight: float = 0.7,
        k: int = 60,
    ) -> List[RAGResult]:
        """RRF (Reciprocal Rank Fusion) 融合"""
        scores: Dict[str, float] = {}
        content_map: Dict[str, RAGResult] = {}

        for rank, r in enumerate(bm25_results):
            key = f"{r.source}:{r.content[:100]}"
            scores[key] = scores.get(key, 0) + bm25_weight / (k + rank + 1)
            if key not in content_map:
                content_map[key] = r

        for rank, r in enumerate(vector_results):
            key = f"{r.source}:{r.content[:100]}"
            scores[key] = scores.get(key, 0) + vector_weight / (k + rank + 1)
            if key not in content_map:
                content_map[key] = r

        sorted_keys = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
        return [content_map[k] for k in sorted_keys]

    def _assess_relevance(self, results: List[RAGResult], query: str) -> float:
        """评估检索结果相关性"""
        if not results:
            return 0.0
        avg_score = sum(r.score for r in results) / len(results)
        return min(avg_score / 10.0, 1.0) if avg_score > 0 else 0.3

    async def _rewrite_with_context(self, query: str, results: List[RAGResult]) -> str:
        """基于检索结果重写查询（CRAG纠错）"""
        try:
            from utils.llm_client import get_llm_client
            llm = get_llm_client()
            context = "\n".join(r.content[:200] for r in results[:3])
            prompt = (
                f"原始查询：{query}\n"
                f"检索到的上下文：\n{context}\n\n"
                f"基于以上上下文，请重写查询以获得更精确的检索结果。只输出重写后的查询。"
            )
            response = await llm.invoke([{"role": "user", "content": prompt}], temperature=0)
            return response.content.strip()
        except Exception:
            return query

    async def ingest_ontology(self, db: AsyncSession):
        """将本体定义索引进RAG"""
        try:
            from ontology.objects import get_all_objects
            from ontology.relations import get_all_relations
            from ontology.behaviors import get_all_behaviors
            from ontology.rules import get_all_rules

            for obj in get_all_objects().values():
                content = f"对象: {obj.name} - {getattr(obj, 'natural_language_definition', '')}"
                self._kb.ingest(content, metadata={"type": "object", "id": obj.object_id})

            for rel in get_all_relations().values():
                content = f"关系: {rel.name} - {getattr(rel, 'semantic_description', '')}"
                self._kb.ingest(content, metadata={"type": "relation", "id": rel.relation_id})

            for beh in get_all_behaviors().values():
                content = f"行为: {beh.name} - {getattr(beh, 'natural_language_definition', '')}"
                self._kb.ingest(content, metadata={"type": "behavior", "id": beh.behavior_id})

            for rule in get_all_rules().values():
                content = f"规则: {rule.name} - {getattr(rule, 'natural_language_definition', '')}"
                self._kb.ingest(content, metadata={"type": "rule", "id": rule.rule_id})

            logger.info("Ontology ingested into RAG pipeline")
        except Exception as e:
            logger.error(f"Failed to ingest ontology: {e}")
