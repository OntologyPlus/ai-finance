from __future__ import annotations

import asyncio
from typing import Any, Callable, Coroutine, Dict, List, Optional

from loguru import logger


class EventBus:
    def __init__(self) -> None:
        self._handlers: Dict[str, List[Callable]] = {}
        self._event_log: List[Dict[str, Any]] = []

    def subscribe(self, event_type: str, handler: Callable) -> None:
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug(f"EventBus: subscribed handler to '{event_type}'")

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
            except ValueError:
                pass

    async def publish(self, event_type: str, data: Any = None) -> None:
        entry = {
            "event_type": event_type,
            "data": data,
        }
        self._event_log.append(entry)

        handlers = self._handlers.get(event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error(f"EventBus handler error for '{event_type}': {e}")

    def get_event_log(self, event_type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        if event_type:
            filtered = [e for e in self._event_log if e["event_type"] == event_type]
        else:
            filtered = self._event_log
        return filtered[-limit:]


EVENT_TYPES = [
    "budget.created",
    "budget.granted",
    "budget.adjusted",
    "budget.b2a_converted",
    "budget.released",
    "expense.submitted",
    "expense.approved",
    "expense.rejected",
    "expense.written_off",
    "alert.triggered",
    "alert.responded",
    "alert.closed",
    "alert.escalated",
    "approval.started",
    "approval.completed",
    "approval.overdue",
    "analysis.completed",
    "report.generated",
]


_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
