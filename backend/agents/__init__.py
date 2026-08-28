from agents.base import BaseAgent, ToolCapableBaseAgent, register, get_all, get
from agents.finance_agent import FinanceAgent

# Deprecated: 以下Agent已废弃，所有请求统一由FinanceAgent处理
# from agents.budget_agent import BudgetAgent      # DEPRECATED: use FinanceAgent
# from agents.expense_agent import ExpenseAgent    # DEPRECATED: use FinanceAgent
# from agents.alert_agent import AlertAgent        # DEPRECATED: use FinanceAgent
# from agents.analysis_agent import AnalysisAgent  # DEPRECATED: use FinanceAgent
# from agents.report_agent import ReportAgent      # DEPRECATED: use FinanceAgent
# from agents.general_agent import GeneralAgent    # DEPRECATED: use FinanceAgent

AgentRegistry = type("AgentRegistry", (), {"register": register, "get_all": get_all, "get": get})

__all__ = [
    "BaseAgent",
    "ToolCapableBaseAgent",
    "AgentRegistry",
    "register",
    "get_all",
    "get",
    "FinanceAgent"
]
