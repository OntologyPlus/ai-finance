from __future__ import annotations

import hashlib
import uuid
from typing import Any, Dict, List, Optional

from loguru import logger

from utils.embedding import EmbeddingUtil


class KnowledgeBase:
    def __init__(self) -> None:
        self._documents: Dict[str, Dict[str, Any]] = {}
        self._embedder = EmbeddingUtil(dim=128)

    def ingest(self, text: str, source: str = "", metadata: Optional[Dict[str, Any]] = None) -> str:
        doc_id = f"doc_{uuid.uuid4().hex[:8]}"

        chunk_size = 500
        chunks = []
        for i in range(0, len(text), chunk_size):
            chunk = text[i:i + chunk_size]
            chunks.append({
                "chunk_id": f"{doc_id}_c{len(chunks)}",
                "text": chunk,
                "embedding": self._embedder.embed(chunk),
            })

        self._documents[doc_id] = {
            "doc_id": doc_id,
            "source": source,
            "metadata": metadata or {},
            "full_text": text,
            "chunks": chunks,
            "hash": hashlib.sha256(text.encode()).hexdigest(),
        }

        logger.info(f"KnowledgeBase: ingested doc {doc_id}, {len(chunks)} chunks, source={source}")
        return doc_id

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        query_embedding = self._embedder.embed(query)

        scored = []
        for doc_id, doc in self._documents.items():
            for chunk in doc.get("chunks", []):
                sim = EmbeddingUtil.cosine_similarity(query_embedding, chunk.get("embedding", []))
                scored.append({
                    "doc_id": doc_id,
                    "source": doc["source"],
                    "metadata": doc["metadata"],
                    "chunk_text": chunk["text"],
                    "relevance": sim,
                })

        scored.sort(key=lambda x: x["relevance"], reverse=True)
        return scored[:top_k]

    def delete(self, doc_id: str) -> bool:
        if doc_id in self._documents:
            del self._documents[doc_id]
            logger.info(f"KnowledgeBase: deleted doc {doc_id}")
            return True
        return False

    def list_documents(self) -> List[Dict[str, Any]]:
        return [
            {
                "doc_id": doc["doc_id"],
                "source": doc["source"],
                "metadata": doc["metadata"],
                "chunk_count": len(doc.get("chunks", [])),
                "hash": doc["hash"],
            }
            for doc in self._documents.values()
        ]
