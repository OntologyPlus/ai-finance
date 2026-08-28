"""
SemanticCache 单元测试 — v8.0 模块 G
测试缓存命中率、归一化、相似度匹配、TTL、LRU、统计
"""
from __future__ import annotations

import time

import pytest

from services.semantic_cache import CacheEntry, CacheHit, SemanticCache


@pytest.fixture
def fresh_cache() -> SemanticCache:
    """生成一个独立的缓存实例（与全局隔离）"""
    return SemanticCache(
        similarity_threshold=0.85,
        default_ttl=60,
        max_size=100,
    )


class TestSemanticCacheBasic:
    """基础读写测试"""

    def test_set_and_get_exact_match(self, fresh_cache: SemanticCache):
        """精确匹配：写入后再读应命中"""
        fresh_cache.set("查询本月预算执行率", "执行率 67%")
        hit = fresh_cache.get("查询本月预算执行率")
        assert hit.hit is True
        assert hit.response == "执行率 67%"
        assert hit.similarity == 1.0

    def test_normalization_lets_punct_pass(self, fresh_cache: SemanticCache):
        """归一化：标点和大小写不影响匹配"""
        fresh_cache.set("本月预算执行率", "执行率 67%")
        hit = fresh_cache.get("本月预算执行率！")
        assert hit.hit is True

    def test_miss_on_unrelated_query(self, fresh_cache: SemanticCache):
        """不相关查询不命中"""
        fresh_cache.set("查询本月预算", "预算 1000 万")
        hit = fresh_cache.get("今天天气怎么样")
        assert hit.hit is False

    def test_get_on_empty_cache(self, fresh_cache: SemanticCache):
        """空缓存查询"""
        hit = fresh_cache.get("随便问问")
        assert hit.hit is False


class TestSemanticCacheTTL:
    """TTL 过期测试"""

    def test_ttl_expiration(self):
        cache = SemanticCache(default_ttl=1, max_size=100)
        cache.set("短 TTL 查询", "result", ttl=1)
        # 立即读：应命中
        hit = cache.get("短 TTL 查询")
        assert hit.hit is True
        # 等待过期
        time.sleep(1.5)
        hit2 = cache.get("短 TTL 查询")
        assert hit2.hit is False


class TestSemanticCacheLRU:
    """LRU 容量淘汰测试"""

    def test_lru_eviction(self):
        cache = SemanticCache(default_ttl=3600, max_size=3)
        cache.set("q1", "r1")
        cache.set("q2", "r2")
        cache.set("q3", "r3")
        # 访问 q1 增加 hit_count，避免被淘汰（淘汰按 hit_count+timestamp 排序）
        cache.get("q1")
        # 加第 4 个：触发 LRU 淘汰
        cache.set("q4", "r4")
        # q2 或 q3 应被淘汰（最冷），q1/q4 保留
        assert cache.get("q4").hit is True


class TestSemanticCacheStats:
    """统计测试"""

    def test_hit_rate(self, fresh_cache: SemanticCache):
        """命中率统计"""
        fresh_cache.set("Q1", "R1")
        # 1 hit
        fresh_cache.get("Q1")
        # 1 miss
        fresh_cache.get("no-such-q")
        stats = fresh_cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["total_queries"] == 2
        assert stats["hit_rate"] == 0.5
        assert stats["size"] == 1

    def test_invalidate(self, fresh_cache: SemanticCache):
        """失效指定条目"""
        fresh_cache.set("to_remove", "x")
        assert fresh_cache.invalidate("to_remove") is True
        assert fresh_cache.get("to_remove").hit is False
        # 重复失效返回 False
        assert fresh_cache.invalidate("to_remove") is False

    def test_clear(self, fresh_cache: SemanticCache):
        """清空缓存"""
        fresh_cache.set("a", "1")
        fresh_cache.set("b", "2")
        fresh_cache.clear()
        stats = fresh_cache.get_stats()
        assert stats["size"] == 0
        assert stats["hits"] == 0
        assert stats["misses"] == 0

    def test_top_queries(self, fresh_cache: SemanticCache):
        """热门查询"""
        fresh_cache.set("q1", "r1")
        fresh_cache.set("q2", "r2")
        # 多次访问 q1
        for _ in range(3):
            fresh_cache.get("q1")
        top = fresh_cache.get_top_queries(2)
        assert len(top) == 2
        assert top[0]["query"] == "q1"
        assert top[0]["hit_count"] == 3


class TestSemanticCacheCosine:
    """余弦相似度计算"""

    def test_cosine_self(self):
        v = [0.1, 0.2, 0.3, 0.4]
        sim = SemanticCache._cosine_similarity(v, v)
        assert sim == pytest.approx(1.0, abs=1e-6)

    def test_cosine_zero_vector(self):
        v1 = [0.0, 0.0, 0.0]
        v2 = [1.0, 2.0, 3.0]
        sim = SemanticCache._cosine_similarity(v1, v2)
        assert sim == 0.0

    def test_cosine_orthogonal(self):
        v1 = [1.0, 0.0]
        v2 = [0.0, 1.0]
        sim = SemanticCache._cosine_similarity(v1, v2)
        assert sim == pytest.approx(0.0, abs=1e-6)

    def test_cosine_different_length(self):
        v1 = [1.0, 0.0]
        v2 = [1.0, 0.0, 0.5]
        sim = SemanticCache._cosine_similarity(v1, v2)
        assert sim == 0.0


class TestSemanticCacheIntegration:
    """集成测试：模拟真实使用场景"""

    def test_budget_query_scenario(self, fresh_cache: SemanticCache):
        """预算查询场景"""
        fresh_cache.set("本月研发费用预算执行率", "65.5%")
        # 重复问应命中
        h1 = fresh_cache.get("本月研发费用预算执行率")
        assert h1.hit is True
        assert h1.response == "65.5%"

    def test_token_savings(self, fresh_cache: SemanticCache):
        """token 节省统计"""
        long_response = "详细的预算分析报告" + "详情" * 200
        fresh_cache.set("复杂查询", long_response)
        # 命中一次
        fresh_cache.get("复杂查询")
        stats = fresh_cache.get_stats()
        assert stats["total_tokens_saved"] > 0
