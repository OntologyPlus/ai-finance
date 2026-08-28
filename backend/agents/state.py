from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from langgraph.graph.message import add_messages
from typing import Annotated


class AgentState(dict):
    """LangGraph状态定义，驱动多Agent协作流程"""

    messages: Annotated[list, add_messages]
    intent: str
    intent_confidence: float
    agent_name: str
    tool_results: List[Dict[str, Any]]
    reflection_count: int
    reflection_passed: bool
    context: Dict[str, Any]
    scene: Optional[Any]
    reasoning_trace: Optional[Any]
    response: str
    hallucination_safe: bool
    safe: bool
    violations: List[str]

    def __init__(self, **kwargs):
        super().__init__()
        self.update({
            "messages": kwargs.get("messages", []),
            "intent": kwargs.get("intent", "general"),
            "intent_confidence": kwargs.get("intent_confidence", 0.0),
            "agent_name": kwargs.get("agent_name", ""),
            "tool_results": kwargs.get("tool_results", []),
            "reflection_count": kwargs.get("reflection_count", 0),
            "reflection_passed": kwargs.get("reflection_passed", True),
            "context": kwargs.get("context", {}),
            "scene": kwargs.get("scene", None),
            "reasoning_trace": kwargs.get("reasoning_trace", None),
            "response": kwargs.get("response", ""),
            "hallucination_safe": kwargs.get("hallucination_safe", True),
            "safe": kwargs.get("safe", True),
            "violations": kwargs.get("violations", []),
        })

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        self.update({key: value})


@dataclass
class ReflectionResult:
    """Self-Reflection结果"""
    should_continue: bool
    next_action: Optional[str] = None
    reasoning: str = ""
