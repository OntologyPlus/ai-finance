import pytest
from services.rag import RAGPipeline, RAGResult


class TestRAGPipeline:
    def test_init(self):
        rag = RAGPipeline()
        assert rag._embedder is not None
        assert rag._kb is not None

    def test_rag_result(self):
        result = RAGResult(content="测试", source="kb", score=0.9)
        d = result.to_dict()
        assert d["content"] == "测试"
        assert d["score"] == 0.9

    def test_rrf_fuse(self):
        rag = RAGPipeline()
        bm25 = [RAGResult("内容1", "es_bm25", 10.0), RAGResult("内容2", "es_bm25", 8.0)]
        vector = [RAGResult("内容1", "es_vector", 0.95), RAGResult("内容3", "es_vector", 0.8)]
        fused = rag._rrf_fuse(bm25, vector)
        assert len(fused) >= 2
        # "内容1" appears in both, should rank higher
        assert fused[0].content == "内容1"

    def test_assess_relevance_empty(self):
        rag = RAGPipeline()
        assert rag._assess_relevance([], "query") == 0.0
