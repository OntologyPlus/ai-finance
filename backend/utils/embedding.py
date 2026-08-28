from __future__ import annotations

import hashlib
import random
from typing import List, Optional

_EMBEDDING_DIM = 1536
_mock_cache: dict[str, List[float]] = {}


class EmbeddingUtil:
    def __init__(self, dim: int = _EMBEDDING_DIM):
        self.dim = dim
        self._real_mode = False
        self._client = None
        self._init_real_embedding()

    def _init_real_embedding(self):
        """尝试初始化真实Embedding，失败则降级为Mock"""
        try:
            from models.config import settings
            if settings.LLM_API_KEY and settings.LLM_API_KEY != "your-api-key-here" and settings.LLM_API_KEY != "your-llm-api-key":
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=settings.LLM_API_KEY,
                    base_url=settings.LLM_API_URL,
                )
                self._real_mode = True
        except Exception:
            self._real_mode = False

    def embed(self, text: str) -> List[float]:
        if not text:
            return [0.0] * self.dim
        if self._real_mode:
            return self._real_embed(text)
        return self._mock_embed(text)

    def _real_embed(self, text: str) -> List[float]:
        """使用OpenAI Embeddings API"""
        try:
            response = self._client.embeddings.create(
                model="text-embedding-3-small",
                input=text[:8000],  # 截断过长文本
                dimensions=min(self.dim, 1536),
            )
            return response.data[0].embedding
        except Exception:
            return self._mock_embed(text)

    def _mock_embed(self, text: str) -> List[float]:
        """降级为确定性随机向量"""
        cache_key = hashlib.md5(text.encode()).hexdigest()
        if cache_key in _mock_cache:
            return _mock_cache[cache_key]
        random.seed(hashlib.sha256(text.encode()).hexdigest())
        vec = [random.gauss(0, 1) for _ in range(self.dim)]
        norm = sum(x * x for x in vec) ** 0.5
        if norm > 0:
            vec = [x / norm for x in vec]
        _mock_cache[cache_key] = vec
        return vec

    @staticmethod
    def cosine_similarity(a: List[float], b: List[float]) -> float:
        if len(a) != len(b) or not a:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
