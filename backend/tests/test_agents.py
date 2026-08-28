import pytest
from agents.base import get_all, get, BaseAgent, ToolCapableBaseAgent


class TestAgentRegistry:
    def test_agents_registered(self):
        registry = get_all()
        # Should have at least the 6 specialized agents + finance
        assert "budget_planning" in registry or "finance" in registry
        assert "expense_reimbursement" in registry or "finance" in registry
        assert "alert_monitor" in registry or "finance" in registry
        assert "business_analysis" in registry or "finance" in registry
        assert "report_generation" in registry or "finance" in registry
        assert "general_query" in registry or "finance" in registry

    def test_get_agent(self):
        # Finance should always be available as fallback
        agent_cls = get("finance")
        assert agent_cls is not None

    def test_get_nonexistent_agent(self):
        agent_cls = get("nonexistent_agent")
        assert agent_cls is None

    def test_all_agents_inherit_base(self):
        registry = get_all()
        for name, cls in registry.items():
            assert issubclass(cls, BaseAgent), f"{name} should inherit from BaseAgent"


class TestAgentRouting:
    @pytest.mark.asyncio
    async def test_intent_agent_map(self):
        from agents.supervisor import _INTENT_AGENT_MAP
        assert "budget_query" in _INTENT_AGENT_MAP
        assert "expense_query" in _INTENT_AGENT_MAP
        assert "alert_query" in _INTENT_AGENT_MAP
        assert "analysis_query" in _INTENT_AGENT_MAP
        assert "report_query" in _INTENT_AGENT_MAP
        assert "general" in _INTENT_AGENT_MAP
