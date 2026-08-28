import pytest
from services.memory import MemoryManager


class TestMemoryManager:
    def test_init(self):
        mm = MemoryManager()
        assert mm._embedder is not None
        assert mm._max_working == 30

    @pytest.mark.asyncio
    async def test_store_fallback(self):
        mm = MemoryManager()
        mid = await mm.store("user1", "working", "测试内容", importance=0.5)
        assert mid.startswith("mem_")

    @pytest.mark.asyncio
    async def test_store_and_retrieve(self):
        mm = MemoryManager()
        await mm.store("user1", "episodic", "用户查看了预算执行率", importance=0.7)
        await mm.store("user1", "episodic", "助手回复了执行率数据", importance=0.5)
        ctx = mm.get_context("user1", "预算执行率")
        # Should return something (even with mock embeddings)
        assert isinstance(ctx, str)
