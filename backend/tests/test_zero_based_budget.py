import pytest
from engines.zero_based_budget_engine import ZeroBasedBudgetEngine

class TestZeroBasedBudgetEngine:
    def test_init(self):
        engine = ZeroBasedBudgetEngine()
        assert engine is not None

    @pytest.mark.asyncio
    async def test_initiate_zbb_review_no_db(self):
        engine = ZeroBasedBudgetEngine()
        result = await engine.initiate_zbb_review("2024", 1000000, db=None)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_create_decision_unit_no_db(self):
        engine = ZeroBasedBudgetEngine()
        result = await engine.create_decision_unit(1, "测试单元", "张三", "测试范围", db=None)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_create_decision_package_no_db(self):
        engine = ZeroBasedBudgetEngine()
        result = await engine.create_decision_package(1, "最低", 100000, "测试说明", db=None)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_create_decision_package_invalid_level(self):
        engine = ZeroBasedBudgetEngine()
        result = await engine.create_decision_package(1, "无效级别", 100000, "测试说明", db=None)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_rank_packages_no_db(self):
        engine = ZeroBasedBudgetEngine()
        result = await engine.rank_packages(1, db=None)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_synthesize_budget_no_db(self):
        engine = ZeroBasedBudgetEngine()
        result = await engine.synthesize_budget(1, 1000000, db=None)
        assert "error" in result

    def test_calculate_strategic_alignment(self):
        engine = ZeroBasedBudgetEngine()
        # 最低包: score * 0.8
        assert engine._calculate_strategic_alignment("最低", 10) == 8.0
        # 当前包: score * 1.0
        assert engine._calculate_strategic_alignment("当前", 10) == 10.0
        # 增强包: score * 0.6
        assert engine._calculate_strategic_alignment("增强", 10) == 6.0
