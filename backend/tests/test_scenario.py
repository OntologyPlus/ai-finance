import pytest
from engines.scenario_engine import ScenarioEngine


class TestScenarioEngine:
    def test_init(self):
        engine = ScenarioEngine()
        assert engine is not None

    @pytest.mark.asyncio
    async def test_compare_no_db(self):
        engine = ScenarioEngine()
        result = await engine.compare_scenarios([1, 2], db=None)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_elastic_adjustment_no_db(self):
        engine = ScenarioEngine()
        result = await engine.apply_elastic_adjustment("B001", 100.0, db=None)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_stress_test_no_db(self):
        engine = ScenarioEngine()
        result = await engine.run_stress_test(1, db=None)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_emergency_allocation_no_db(self):
        engine = ScenarioEngine()
        result = await engine.emergency_allocation(1, "B001", 100000, "测试", db=None)
        assert "error" in result

    def test_identify_differences(self):
        engine = ScenarioEngine()
        scenarios = [
            {"name": "基准", "type": "基准", "assumptions": {"growth": 0.1}},
            {"name": "悲观", "type": "悲观", "assumptions": {"growth": -0.1}},
        ]
        diffs = engine._identify_differences(scenarios)
        assert len(diffs) > 0
