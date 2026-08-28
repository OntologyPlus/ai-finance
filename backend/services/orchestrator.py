from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from agents.base import BaseAgent, ToolCapableBaseAgent, get
from agents.supervisor import Supervisor
from agents.state import AgentState
from services.intent_classifier import IntentClassifier
from services.memory import MemoryManager
from services.guardrails import Guardrails
from services.audit_log import AuditLogger
from ontology.events import get_event_bus, OntologyEventType
from skills.skill_loader import SkillLoader


class AgentOrchestrator:
    def __init__(self) -> None:
        self._classifier = IntentClassifier()
        self._memory = MemoryManager()
        self._guardrails = Guardrails()
        self._audit = AuditLogger()
        self._skill_loader = SkillLoader()
        self._skill_loader.load_skills(os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills"))
        ToolCapableBaseAgent._skill_loader = self._skill_loader
        self._supervisor = Supervisor()
        self._agents: Dict[str, BaseAgent] = {}

    def _get_agent(self, name: str = "general_query") -> Optional[BaseAgent]:
        """获取Agent实例"""
        if name in self._agents:
            return self._agents[name]

        agent_cls = get(name)
        if agent_cls is None:
            # Fallback到FinanceAgent（兼容层）
            agent_cls = get("finance")
        if agent_cls is None:
            return None
        agent = agent_cls()
        self._agents[name] = agent
        return agent

    async def route(
        self,
        messages: List[Dict[str, str]],
        context: Dict[str, Any],
        db: AsyncSession,
    ) -> Dict[str, Any]:
        user_input = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_input = m.get("content", "")
                break

        intent, confidence = await self._classifier.classify(user_input)
        context["classified_intent"] = intent
        context["intent_confidence"] = confidence

        # 通过Supervisor路由到专业Agent
        from agents.supervisor import _INTENT_AGENT_MAP
        agent_name = _INTENT_AGENT_MAP.get(intent, "general_query")
        agent = self._get_agent(agent_name)

        return {
            "intent": intent,
            "confidence": confidence,
            "agent_name": agent_name,
            "agent": agent,
            "user_input": user_input,
        }

    async def execute(
        self,
        messages: List[Dict[str, str]],
        context: Dict[str, Any],
        db: AsyncSession,
    ) -> Dict[str, Any]:
        user_input = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_input = m.get("content", "")
                break

        safe, masked_text, violations = self._guardrails.check(user_input)
        if not safe:
            self._audit.log(
                action="guardrails_blocked",
                actor=context.get("user_id", "unknown"),
                resource="chat",
                details={"violations": violations},
                severity="warning",
            )
            return {
                "response": "您的输入包含不安全内容，请修改后重试。",
                "intent": "blocked",
                "confidence": 1.0,
                "agent_name": "guardrails",
                "suggestions": [],
                "trace_id": "",
                "violations": violations,
            }

        if violations:
            for m in messages:
                if m.get("role") == "user":
                    m["content"] = masked_text
                    break

        # 使用Supervisor执行多Agent协作
        state = AgentState(
            messages=messages,
            context={**context, "db": db},
        )

        try:
            result_state = await self._supervisor.run(state)
            response = result_state.get("response", "")
            intent = result_state.get("intent", "general")
            confidence = result_state.get("intent_confidence", 0.0)
            agent_name = result_state.get("agent_name", "general_query")
        except Exception as e:
            logger.error(f"Supervisor execution error: {e}")
            # Fallback到原有FinanceAgent
            routing = await self.route(messages, context, db)
            intent = routing["intent"]
            confidence = routing["confidence"]
            agent = routing["agent"]
            agent_name = routing["agent_name"]

            if agent is None:
                return {
                    "response": "系统暂不可用，请稍后重试。",
                    "intent": intent,
                    "confidence": confidence,
                    "agent_name": "none",
                    "suggestions": [],
                    "trace_id": "",
                }

            user_id = context.get("user_id", "anonymous")
            memory_context = self._memory.get_context(user_id, user_input)
            enhanced_messages = messages.copy()
            if memory_context:
                enhanced_messages.insert(0, {
                    "role": "system",
                    "content": f"[用户上下文记忆]\n{memory_context}",
                })

            try:
                response = await agent.execute(enhanced_messages, context, db)
            except Exception as ex:
                logger.error(f"Agent execution error [{agent_name}]: {ex}")
                response = "处理您的请求时遇到错误，请稍后重试。"

        # 记忆存储
        user_id = context.get("user_id", "anonymous")
        self._memory.store(
            user_id=user_id,
            memory_type="episodic",
            content=f"用户: {user_input[:200]}",
            importance=0.5,
        )
        self._memory.store(
            user_id=user_id,
            memory_type="episodic",
            content=f"助手: {response[:200]}",
            importance=0.3,
        )

        trace_id = self._audit.log(
            action="agent_execute",
            actor=user_id,
            resource=agent_name,
            details={
                "intent": intent,
                "confidence": confidence,
                "input_length": len(user_input),
                "output_length": len(response),
            },
            severity="info",
        )

        agent = self._agents.get(agent_name)
        suggestions = agent.get_suggestions() if agent and hasattr(agent, 'get_suggestions') else []

        event_bus = get_event_bus()
        _INTENT_EVENT_MAP = {
            "budget_planning": OntologyEventType.BUDGET_GRANTED,
            "budget_grant": OntologyEventType.BUDGET_GRANTED,
            "b2a_conversion": OntologyEventType.BUDGET_ADJUSTED,
            "expense_submit": OntologyEventType.BUDGET_WRITTEN_OFF,
            "alert_response": OntologyEventType.ALERT_TRIGGERED,
            "alert_closure": OntologyEventType.ALERT_CLOSED,
            "alert_escalation": OntologyEventType.ALERT_ESCALATED,
        }
        event_type = _INTENT_EVENT_MAP.get(intent, OntologyEventType.OBJECT_UPDATED)
        await event_bus.publish(
            event_type=event_type,
            source=f"agent:{agent_name}",
            payload={
                "agent": agent_name,
                "intent": intent,
                "user_id": user_id,
            },
        )

        should_continue = self._self_reflect(response, messages)

        return {
            "response": response,
            "intent": intent,
            "confidence": confidence,
            "agent_name": agent_name,
            "suggestions": suggestions,
            "trace_id": trace_id,
            "should_continue": should_continue,
        }

    async def _classify_intent(self, messages: List[Dict[str, str]]) -> Tuple[str, float]:
        user_input = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_input = m.get("content", "")
                break
        return await self._classifier.classify(user_input)

    def _build_memory_enhanced_prompt(self, messages: List[Dict[str, str]], context: Dict[str, Any]) -> str:
        user_id = context.get("user_id", "anonymous")
        user_input = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_input = m.get("content", "")
                break
        return self._memory.get_context(user_id, user_input)

    def _self_reflect(self, result: str, messages: List[Dict[str, str]]) -> bool:
        if not result or len(result.strip()) < 10:
            return True
        if result.startswith("[LLM调用失败]") or result.startswith("[流式调用失败]"):
            return True
        if "请提供更多" in result or "需要更多信息" in result:
            return True
        return False
