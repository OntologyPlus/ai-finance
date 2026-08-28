"""
语义缓存服务 — 基于 embedding cosine similarity 的查询缓存
按 v8.0 计划 §3.2 模块 G 实施：高频问题答案缓存，降低 LLM 成本 50%+
"""
from __future__ import annotations

import math
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from utils.embedding import EmbeddingUtil


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    query: str
    response: str
    embedding: List[float]
    timestamp: float
    ttl: int
    hit_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CacheHit:
    """缓存命中结果"""
    hit: bool
    response: Optional[str] = None
    similarity: float = 0.0
    matched_query: Optional[str] = None
    hit_count: int = 0


class SemanticCache:
    """语义缓存：用 embedding cosine similarity 匹配相似查询"""

    def __init__(
        self,
        similarity_threshold: float = 0.88,
        default_ttl: int = 3600,  # 1 小时
        max_size: int = 1000,
    ):
        self.similarity_threshold = similarity_threshold
        self.default_ttl = default_ttl
        self.max_size = max_size
        self._store: Dict[str, CacheEntry] = {}
        self._embedding = EmbeddingUtil()
        # 统计
        self._stats = {
            "hits": 0,
            "misses": 0,
            "total_queries": 0,
            "total_tokens_saved": 0,
        }

    @staticmethod
    def _cosine_similarity(v1: List[float], v2: List[float]) -> float:
        """计算两个向量的余弦相似度"""
        if not v1 or not v2 or len(v1) != len(v2):
            return 0.0
        dot = sum(a * b for a, b in zip(v1, v2))
        n1 = math.sqrt(sum(a * a for a in v1))
        n2 = math.sqrt(sum(b * b for b in v2))
        if n1 == 0 or n2 == 0:
            return 0.0
        return dot / (n1 * n2)

    @staticmethod
    def _normalize_query(query: str) -> str:
        """查询标准化：小写、去标点、合并空白"""
        q = query.lower().strip()
        q = re.sub(r"[\s\u3000]+", " ", q)
        q = re.sub(r"[^\w\s\u4e00-\u9fff]", "", q)
        return q

    def _generate_key(self, query: str) -> str:
        """生成缓存 key（归一化后的 hash）"""
        normalized = self._normalize_query(query)
        # 简化：直接用归一化文本（短查询足够）
        return normalized[:200] if len(normalized) > 200 else normalized

    def _evict_expired(self) -> int:
        """清理过期缓存"""
        now = time.time()
        expired = [k for k, v in self._store.items() if now - v.timestamp > v.ttl]
        for k in expired:
            del self._store[k]
        return len(expired)

    def _evict_lru(self) -> int:
        """LRU 清理（按 hit_count + timestamp）"""
        if len(self._store) <= self.max_size:
            return 0
        # 按（hit_count, timestamp）排序，淘汰最冷的数据
        sorted_items = sorted(
            self._store.items(),
            key=lambda x: (x[1].hit_count, x[1].timestamp),
        )
        to_remove = len(self._store) - self.max_size
        for k, _ in sorted_items[:to_remove]:
            del self._store[k]
        return to_remove

    def get(self, query: str) -> CacheHit:
        """查询缓存
        - 先做归一化精确匹配
        - 失败则用 embedding 找最相似的
        - 相似度 >= threshold 视为命中
        """
        self._stats["total_queries"] += 1
        self._evict_expired()

        if not self._store:
            self._stats["misses"] += 1
            return CacheHit(hit=False)

        # 1. 精确匹配（归一化后）
        key = self._generate_key(query)
        if key in self._store:
            entry = self._store[key]
            if time.time() - entry.timestamp <= entry.ttl:
                entry.hit_count += 1
                self._stats["hits"] += 1
                self._stats["total_tokens_saved"] += len(entry.response) // 4
                return CacheHit(
                    hit=True,
                    response=entry.response,
                    similarity=1.0,
                    matched_query=entry.query,
                    hit_count=entry.hit_count,
                )

        # 2. 语义匹配（embedding cosine）
        query_emb = self._embedding.embed(query)
        best_match: Optional[CacheEntry] = None
        best_sim = 0.0

        for entry in self._store.values():
            sim = self._cosine_similarity(query_emb, entry.embedding)
            if sim > best_sim:
                best_sim = sim
                best_match = entry

        if best_match and best_sim >= self.similarity_threshold:
            best_match.hit_count += 1
            self._stats["hits"] += 1
            self._stats["total_tokens_saved"] += len(best_match.response) // 4
            return CacheHit(
                hit=True,
                response=best_match.response,
                similarity=best_sim,
                matched_query=best_match.query,
                hit_count=best_match.hit_count,
            )

        self._stats["misses"] += 1
        return CacheHit(hit=False, similarity=best_sim if best_match else 0.0)

    def set(
        self,
        query: str,
        response: str,
        ttl: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """写入缓存"""
        key = self._generate_key(query)
        embedding = self._embedding.embed(query)

        # 容量管理
        self._evict_lru()

        self._store[key] = CacheEntry(
            key=key,
            query=query,
            response=response,
            embedding=embedding,
            timestamp=time.time(),
            ttl=ttl or self.default_ttl,
            metadata=metadata or {},
        )

    def invalidate(self, query: str) -> bool:
        """失效指定缓存"""
        key = self._generate_key(query)
        if key in self._store:
            del self._store[key]
            return True
        return False

    def clear(self) -> None:
        """清空缓存"""
        self._store.clear()
        self._stats = {"hits": 0, "misses": 0, "total_queries": 0, "total_tokens_saved": 0}

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total = self._stats["total_queries"]
        hit_rate = self._stats["hits"] / total if total > 0 else 0.0
        return {
            **self._stats,
            "hit_rate": round(hit_rate, 4),
            "size": len(self._store),
            "similarity_threshold": self.similarity_threshold,
        }

    def get_top_queries(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """获取热门查询（按 hit_count）"""
        sorted_items = sorted(
            self._store.values(),
            key=lambda x: -x.hit_count,
        )[:top_n]
        return [
            {
                "query": e.query,
                "hit_count": e.hit_count,
                "age_seconds": int(time.time() - e.timestamp),
                "response_length": len(e.response),
            }
            for e in sorted_items
        ]


# ─── 全局实例 ─────────────────────────────────────

_global_cache: Optional[SemanticCache] = None


def get_semantic_cache() -> SemanticCache:
    """获取全局语义缓存实例（单例）"""
    global _global_cache
    if _global_cache is None:
        _global_cache = SemanticCache()
    return _global_cache
