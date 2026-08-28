import pytest
from engines.cost_center_engine import CostCenterEngine

class TestCostCenterEngine:
    def test_init(self):
        engine = CostCenterEngine()
        assert engine is not None

    @pytest.mark.asyncio
    async def test_set_standard_cost_no_db(self):
        engine = CostCenterEngine()
        result = await engine.set_standard_cost(1, "测试项目", 100, 50, db=None)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_variance_analysis_no_db(self):
        engine = CostCenterEngine()
        result = await engine.variance_analysis(1, "2024-06", db=None)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_allocate_cost_no_db(self):
        engine = CostCenterEngine()
        result = await engine.allocate_cost(1, db=None)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_settle_internal_no_db(self):
        engine = CostCenterEngine()
        result = await engine.settle_internal(1, 2, 100, 50, db=None)
        assert "error" in result

    def test_assess_variance(self):
        engine = CostCenterEngine()
        assert engine._assess_variance(0, 100) == "无标准"
        assert engine._assess_variance(3, 100) == "正常"
        assert engine._assess_variance(8, 100) == "轻微偏差"
        assert engine._assess_variance(15, 100) == "显著偏差"
        assert engine._assess_variance(25, 100) == "严重偏差"

    def test_generate_variance_recommendation(self):
        engine = CostCenterEngine()
        assert engine._generate_variance_recommendation(0, 0) == "无标准成本数据"
        rec1 = engine._generate_variance_recommendation(15, 100)
        assert "显著超出" in rec1
        rec2 = engine._generate_variance_recommendation(8, 100)
        assert "略高于" in rec2
        rec3 = engine._generate_variance_recommendation(3, 100)
        assert "基本一致" in rec3
        rec4 = engine._generate_variance_recommendation(-10, 100)
        assert "低于标准" in rec4
