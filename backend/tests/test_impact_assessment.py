import pytest
from engines.impact_assessment_engine import ImpactAssessmentEngine


class TestImpactAssessmentEngine:
    def test_init(self):
        engine = ImpactAssessmentEngine()
        assert engine is not None

    @pytest.mark.asyncio
    async def test_assess_budget_change_no_db(self):
        engine = ImpactAssessmentEngine()
        result = await engine.assess_budget_change("B001", "decrease", 100000, db=None)
        assert "impacts" in result
        assert len(result["impacts"]) == 5

    @pytest.mark.asyncio
    async def test_assess_strategic_shift(self):
        engine = ImpactAssessmentEngine()
        result = await engine.assess_strategic_shift("SI001", "国际化", db=None)
        assert result["overall_risk"] == "高"

    @pytest.mark.asyncio
    async def test_trace_impact_no_db(self):
        engine = ImpactAssessmentEngine()
        result = await engine.trace_impact(1, db=None)
        assert "error" in result

    def test_auto_suggest(self):
        engine = ImpactAssessmentEngine()
        assert "预算" in engine._auto_suggest("budget", "高")
        assert "战略" in engine._auto_suggest("strategic", "高")
