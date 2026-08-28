import pytest
from services.intent_classifier import IntentClassifier


class TestIntentClassifier:
    def test_init(self):
        ic = IntentClassifier()
        assert ic._trained is True

    @pytest.mark.asyncio
    async def test_classify_budget(self):
        ic = IntentClassifier()
        intent, conf = await ic.classify("查看预算执行率")
        assert intent in ("budget_query", "analysis_query")

    @pytest.mark.asyncio
    async def test_classify_expense(self):
        ic = IntentClassifier()
        intent, conf = await ic.classify("提交报销单")
        assert intent == "expense_query"

    @pytest.mark.asyncio
    async def test_classify_alert(self):
        ic = IntentClassifier()
        intent, conf = await ic.classify("当前有哪些预警")
        assert intent == "alert_query"

    @pytest.mark.asyncio
    async def test_classify_general(self):
        ic = IntentClassifier()
        intent, conf = await ic.classify("你好")
        assert intent == "general"

    def test_resolve_conflict_weighted(self):
        ic = IntentClassifier()
        # LLM has higher weight (0.6 vs 0.4)
        result = ic._resolve_conflict(("budget_query", 0.5), ("expense_query", 0.5))
        assert result[0] == "expense_query"  # LLM wins at equal confidence

        # Rule wins when high enough
        result = ic._resolve_conflict(("budget_query", 0.9), ("expense_query", 0.5))
        assert result[0] == "budget_query"  # 0.9*0.4=0.36 > 0.5*0.6=0.3
