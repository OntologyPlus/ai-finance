import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models.ontology import OntologyEventRecord

logger = logging.getLogger(__name__)


class OntologyEventType(str, Enum):
    OBJECT_CREATED = "object.created"
    OBJECT_UPDATED = "object.updated"
    OBJECT_DELETED = "object.deleted"
    RELATION_CREATED = "relation.created"
    RELATION_DELETED = "relation.deleted"
    RULE_VIOLATED = "rule.violated"
    ALERT_TRIGGERED = "alert.triggered"
    ALERT_ESCALATED = "alert.escalated"
    ALERT_CLOSED = "alert.closed"
    BUDGET_WRITTEN_OFF = "budget.written_off"
    BUDGET_FROZEN = "budget.frozen"
    BUDGET_RELEASED = "budget.released"
    BUDGET_GRANTED = "budget.granted"
    BUDGET_ADJUSTED = "budget.adjusted"
    SCENE_ACTIVATED = "scene.activated"
    CONSISTENCY_ISSUE = "consistency.issue"


class OntologyEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: f"EVT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{id(object):x}")
    event_type: OntologyEventType
    source: str
    payload: Dict[str, Any] = {}
    timestamp: datetime = Field(default_factory=datetime.now)
    correlation_id: Optional[str] = None


EventHandler = Callable[[OntologyEvent], None]
AsyncEventHandler = Callable[[OntologyEvent], Any]


class OntologyEventBus:
    MAX_HISTORY = 1000

    def __init__(self, db: Optional[AsyncSession] = None):
        self._handlers: Dict[OntologyEventType, List[EventHandler]] = {}
        self._global_handlers: List[EventHandler] = []
        self._event_history: List[OntologyEvent] = []
        self._db = db

    def set_db(self, db: AsyncSession):
        self._db = db

    def subscribe(self, event_type: OntologyEventType, handler: EventHandler) -> None:
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def subscribe_global(self, handler: EventHandler) -> None:
        self._global_handlers.append(handler)

    def unsubscribe(self, event_type: OntologyEventType, handler: EventHandler) -> None:
        if event_type in self._handlers:
            self._handlers[event_type] = [h for h in self._handlers[event_type] if h is not handler]

    async def publish(
        self,
        event_type: OntologyEventType,
        source: str,
        payload: Dict[str, Any],
        correlation_id: Optional[str] = None,
    ) -> OntologyEvent:
        event = OntologyEvent(
            event_type=event_type,
            source=source,
            payload=payload,
            correlation_id=correlation_id,
        )

        self._event_history.append(event)
        if len(self._event_history) > self.MAX_HISTORY:
            self._event_history = self._event_history[-self.MAX_HISTORY:]

        type_handlers = self._handlers.get(event_type, [])
        for handler in type_handlers:
            try:
                handler(event)
            except Exception:
                logger.exception("Handler %s failed for event %s", handler.__name__, event.event_id)

        for handler in self._global_handlers:
            try:
                handler(event)
            except Exception:
                logger.exception("Global handler %s failed for event %s", handler.__name__, event.event_id)

        # Persist to database
        if self._db:
            try:
                record = OntologyEventRecord(
                    event_id=event.event_id,
                    event_type=event.event_type.value if isinstance(event.event_type, OntologyEventType) else str(event.event_type),
                    source=event.source,
                    payload=event.payload,
                    correlation_id=event.correlation_id,
                )
                self._db.add(record)
                await self._db.flush()
            except Exception as e:
                logger.warning(f"事件持久化失败: {e}")

        return event

    async def get_event_history(
        self,
        event_type: Optional[OntologyEventType] = None,
        limit: int = 100,
    ) -> List[OntologyEvent]:
        # Try DB first for comprehensive history
        if self._db:
            try:
                stmt = select(OntologyEventRecord).order_by(OntologyEventRecord.created_at.desc()).limit(limit)
                if event_type:
                    stmt = stmt.where(OntologyEventRecord.event_type == event_type.value)
                rows = (await self._db.execute(stmt)).scalars().all()
                return [
                    OntologyEvent(
                        event_id=row.event_id,
                        event_type=OntologyEventType(row.event_type),
                        source=row.source or "",
                        payload=row.payload or {},
                        timestamp=row.created_at,
                        correlation_id=row.correlation_id,
                    )
                    for row in rows
                ]
            except Exception as e:
                logger.warning(f"事件历史DB查询失败: {e}")

        # Fallback to in-memory history
        if event_type:
            return [e for e in reversed(self._event_history) if e.event_type == event_type][:limit]
        return list(reversed(self._event_history))[:limit]


_event_bus: Optional[OntologyEventBus] = None


def get_event_bus() -> OntologyEventBus:
    global _event_bus
    if _event_bus is None:
        _event_bus = OntologyEventBus()
    return _event_bus


# ---------------------------------------------------------------------------
# Built-in subscribers
# ---------------------------------------------------------------------------

def _audit_logger(event: OntologyEvent) -> None:
    payload_summary = str(event.payload)[:200] if event.payload else "{}"
    logger.info(
        "[Audit] type=%s source=%s event_id=%s payload=%s",
        event.event_type.value,
        event.source,
        event.event_id,
        payload_summary,
    )


_WRITE_BACK_TRIGGER_TYPES = {
    OntologyEventType.BUDGET_WRITTEN_OFF,
    OntologyEventType.BUDGET_FROZEN,
    OntologyEventType.BUDGET_RELEASED,
    OntologyEventType.BUDGET_GRANTED,
    OntologyEventType.ALERT_TRIGGERED,
}


def _write_back_trigger(event: OntologyEvent) -> None:
    if event.event_type not in _WRITE_BACK_TRIGGER_TYPES:
        return
    logger.info(
        "[WriteBack] Publishing write-back request for event_type=%s source=%s correlation_id=%s",
        event.event_type.value,
        event.source,
        event.correlation_id,
    )
    try:
        from ontology.write_back import get_write_back_engine, WriteBackConsistency
        engine = get_write_back_engine()
        action_map = {
            OntologyEventType.BUDGET_WRITTEN_OFF: ("budget_system", "write_off", WriteBackConsistency.STRONG),
            OntologyEventType.BUDGET_FROZEN: ("budget_system", "freeze", WriteBackConsistency.STRONG),
            OntologyEventType.BUDGET_RELEASED: ("budget_system", "release", WriteBackConsistency.STRONG),
            OntologyEventType.BUDGET_GRANTED: ("budget_system", "grant", WriteBackConsistency.STRONG),
            OntologyEventType.ALERT_TRIGGERED: ("message_system", "alert", WriteBackConsistency.EVENTUAL),
        }
        mapping = action_map.get(event.event_type)
        if mapping:
            target_system, action, consistency = mapping
            payload = {**event.payload, "action": action}
            import asyncio
            asyncio.ensure_future(engine.execute(
                source_action=event.event_type.value,
                target_system=target_system,
                payload=payload,
                consistency=consistency,
            ))
    except Exception as e:
        logger.error(f"[WriteBack] Failed to trigger write-back: {e}")


def _consistency_alert(event: OntologyEvent) -> None:
    if event.event_type != OntologyEventType.CONSISTENCY_ISSUE:
        return
    severity = event.payload.get("severity", "unknown")
    description = event.payload.get("description", "")
    logger.warning(
        "[ConsistencyAlert] severity=%s description=%s source=%s",
        severity,
        description,
        event.source,
    )


_ALERT_TRIGGER_TYPES = {
    OntologyEventType.BUDGET_WRITTEN_OFF,
    OntologyEventType.BUDGET_FROZEN,
    OntologyEventType.BUDGET_RELEASED,
    OntologyEventType.BUDGET_GRANTED,
}


def _alert_on_event(event: OntologyEvent) -> None:
    """Event-driven real-time alert subscriber.

    Subscribes to budget events and triggers alert checking immediately.
    Uses asyncio.create_task with done callback and timeout protection.
    """
    if event.event_type not in _ALERT_TRIGGER_TYPES:
        return
    try:
        from engines.alert_monitor import AlertMonitorEngine
        import asyncio

        engine = AlertMonitorEngine()

        def _on_alert_done(task: asyncio.Task):
            try:
                task.result()
                logger.info("[EventBus] Alert check completed successfully")
            except Exception as e:
                logger.error(f"[EventBus] Alert check failed: {e}")

        async def _run_with_timeout():
            try:
                return await asyncio.wait_for(
                    engine.check_on_event(event.event_type.value, event.payload, None),
                    timeout=30,
                )
            except asyncio.TimeoutError:
                logger.error("[EventBus] Alert check timed out after 30s")
                return None

        task = asyncio.create_task(_run_with_timeout())
        task.add_done_callback(_on_alert_done)
    except Exception as e:
        logger.error(f"[Alert] Real-time check failed: {e}")


def setup_default_subscribers() -> None:
    bus = get_event_bus()
    bus.subscribe_global(_audit_logger)
    for et in _WRITE_BACK_TRIGGER_TYPES:
        bus.subscribe(et, _write_back_trigger)
    bus.subscribe(OntologyEventType.CONSISTENCY_ISSUE, _consistency_alert)
    for et in _ALERT_TRIGGER_TYPES:
        bus.subscribe(et, _alert_on_event)
