from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional

from loguru import logger


@dataclass
class CollaborationRule:
    rule_id: str
    source_agent: str
    target_agent: str
    trigger_event: str
    condition: str
    action: str
    is_active: bool = True


@dataclass
class Message:
    message_id: str
    sender: str
    channel: str
    data: Any
    timestamp: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class ContextBus:
    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable]] = {}
        self._messages: List[Message] = []
        self._collaboration_rules: Dict[str, CollaborationRule] = {}
        self._agent_contexts: Dict[str, Dict[str, Any]] = {}

    def subscribe(self, channel: str, handler: Callable) -> None:
        if channel not in self._subscribers:
            self._subscribers[channel] = []
        self._subscribers[channel].append(handler)
        logger.debug(f"ContextBus: {handler.__name__ if hasattr(handler, '__name__') else 'handler'} subscribed to '{channel}'")

    def unsubscribe(self, channel: str, handler: Callable) -> None:
        if channel in self._subscribers:
            try:
                self._subscribers[channel].remove(handler)
            except ValueError:
                pass

    async def publish(self, channel: str, sender: str, data: Any, metadata: Optional[dict] = None) -> str:
        from datetime import datetime

        msg_id = f"MSG-{len(self._messages) + 1:04d}"
        message = Message(
            message_id=msg_id,
            sender=sender,
            channel=channel,
            data=data,
            timestamp=datetime.now().isoformat(),
            metadata=metadata or {},
        )
        self._messages.append(message)

        handlers = self._subscribers.get(channel, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                logger.error(f"ContextBus: handler error on '{channel}': {e}")

        await self._apply_collaboration_rules(channel, sender, data)

        return msg_id

    def set_agent_context(self, agent_name: str, context: Dict[str, Any]) -> None:
        self._agent_contexts[agent_name] = context

    def get_agent_context(self, agent_name: str) -> Dict[str, Any]:
        return self._agent_contexts.get(agent_name, {})

    def update_agent_context(self, agent_name: str, updates: Dict[str, Any]) -> None:
        if agent_name not in self._agent_contexts:
            self._agent_contexts[agent_name] = {}
        self._agent_contexts[agent_name].update(updates)

    def add_collaboration_rule(self, rule: CollaborationRule) -> None:
        self._collaboration_rules[rule.rule_id] = rule
        logger.info(f"ContextBus: added collaboration rule '{rule.rule_id}' ({rule.source_agent} -> {rule.target_agent})")

    def remove_collaboration_rule(self, rule_id: str) -> None:
        if rule_id in self._collaboration_rules:
            del self._collaboration_rules[rule_id]

    def load_collaboration_rules(self, rules: List[Dict[str, Any]]) -> None:
        for rule_data in rules:
            rule = CollaborationRule(
                rule_id=rule_data.get("rule_id", ""),
                source_agent=rule_data.get("source_agent", ""),
                target_agent=rule_data.get("target_agent", ""),
                trigger_event=rule_data.get("trigger_event", ""),
                condition=rule_data.get("condition", ""),
                action=rule_data.get("action", "notify"),
                is_active=rule_data.get("is_active", True),
            )
            self.add_collaboration_rule(rule)
        logger.info(f"ContextBus: loaded {len(rules)} collaboration rules")

    def get_messages(self, channel: Optional[str] = None, sender: Optional[str] = None, limit: int = 100) -> List[Message]:
        filtered = self._messages
        if channel:
            filtered = [m for m in filtered if m.channel == channel]
        if sender:
            filtered = [m for m in filtered if m.sender == sender]
        return filtered[-limit:]

    def get_collaboration_rules(self, source_agent: Optional[str] = None) -> List[CollaborationRule]:
        rules = list(self._collaboration_rules.values())
        if source_agent:
            rules = [r for r in rules if r.source_agent == source_agent]
        return rules

    async def _apply_collaboration_rules(self, channel: str, sender: str, data: Any) -> None:
        for rule in self._collaboration_rules.values():
            if not rule.is_active:
                continue
            if rule.source_agent != sender:
                continue
            if rule.trigger_event != channel:
                continue

            target_channel = f"agent.{rule.target_agent}"
            handlers = self._subscribers.get(target_channel, [])
            for handler in handlers:
                try:
                    collab_data = {
                        "rule_id": rule.rule_id,
                        "source_agent": sender,
                        "action": rule.action,
                        "original_data": data,
                    }
                    if asyncio.iscoroutinefunction(handler):
                        await handler(collab_data)
                    else:
                        handler(collab_data)
                except Exception as e:
                    logger.error(f"ContextBus: collaboration rule '{rule.rule_id}' handler error: {e}")


DEFAULT_COLLABORATION_RULES = [
    {"rule_id": "CR-001", "source_agent": "expense", "target_agent": "budget", "trigger_event": "expense.submitted", "condition": "", "action": "check_budget_availability"},
    {"rule_id": "CR-002", "source_agent": "alert", "target_agent": "expense", "trigger_event": "alert.triggered", "condition": "", "action": "restrict_expense"},
    {"rule_id": "CR-003", "source_agent": "budget", "target_agent": "alert", "trigger_event": "budget.exceeded", "condition": "", "action": "trigger_alert"},
    {"rule_id": "CR-004", "source_agent": "analysis", "target_agent": "budget", "trigger_event": "analysis.completed", "condition": "", "action": "suggest_adjustment"},
    {"rule_id": "CR-005", "source_agent": "alert", "target_agent": "analysis", "trigger_event": "alert.escalated", "condition": "", "action": "deep_analysis"},
]


_context_bus: Optional[ContextBus] = None


def get_context_bus() -> ContextBus:
    global _context_bus
    if _context_bus is None:
        _context_bus = ContextBus()
        _context_bus.load_collaboration_rules(DEFAULT_COLLABORATION_RULES)
    return _context_bus
