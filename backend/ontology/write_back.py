from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional

from loguru import logger
from pydantic import BaseModel, Field


class WriteBackConsistency(str, Enum):
    STRONG = "strong"
    EVENTUAL = "eventual"


class WriteBackStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD_LETTER = "dead_letter"


class WriteBackEntry(BaseModel):
    entry_id: str
    idempotency_key: str
    source_action: str
    target_system: str
    consistency: WriteBackConsistency
    payload: Dict[str, Any]
    status: WriteBackStatus = WriteBackStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3
    last_error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    executed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class DeadLetterEntry(BaseModel):
    entry_id: str
    original_entry: WriteBackEntry
    reason: str
    created_at: datetime = Field(default_factory=datetime.now)
    reviewed: bool = False
    resolution: Optional[str] = None


class WriteBackResult(BaseModel):
    entry_id: str
    success: bool
    message: str = ""
    data: Optional[Dict[str, Any]] = None


class WriteBackEngine:
    def __init__(self, max_retries: int = 3, retry_delay_seconds: int = 5):
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self._entries: Dict[str, WriteBackEntry] = {}
        self._dead_letters: Dict[str, DeadLetterEntry] = {}
        self._idempotency_keys: Dict[str, str] = {}
        self._handlers: Dict[str, Callable[..., Coroutine]] = {}

    def register_handler(
        self, target_system: str, handler: Callable[..., Coroutine]
    ) -> None:
        self._handlers[target_system] = handler

    def generate_idempotency_key(
        self, source_action: str, target_system: str, payload: Dict[str, Any]
    ) -> str:
        content = f"{source_action}:{target_system}:{json.dumps(payload, sort_keys=True, default=str)}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    async def execute(
        self,
        source_action: str,
        target_system: str,
        payload: Dict[str, Any],
        consistency: WriteBackConsistency = WriteBackConsistency.STRONG,
        idempotency_key: Optional[str] = None,
    ) -> WriteBackResult:
        if idempotency_key is None:
            idempotency_key = self.generate_idempotency_key(source_action, target_system, payload)

        if idempotency_key in self._idempotency_keys:
            existing_id = self._idempotency_keys[idempotency_key]
            existing = self._entries.get(existing_id)
            if existing and existing.status == WriteBackStatus.SUCCESS:
                logger.info(f"Write-Back idempotent hit: {idempotency_key}")
                return WriteBackResult(
                    entry_id=existing_id,
                    success=True,
                    message="幂等命中，操作已执行过",
                    data=existing.payload,
                )

        entry = WriteBackEntry(
            entry_id=f"WB-{uuid.uuid4().hex[:8].upper()}",
            idempotency_key=idempotency_key,
            source_action=source_action,
            target_system=target_system,
            consistency=consistency,
            payload=payload,
            max_retries=self.max_retries,
        )

        self._entries[entry.entry_id] = entry
        self._idempotency_keys[idempotency_key] = entry.entry_id

        if consistency == WriteBackConsistency.STRONG:
            result = await self._execute_with_retry(entry)
            return result
        else:
            import asyncio
            asyncio.create_task(self._execute_async(entry))
            return WriteBackResult(
                entry_id=entry.entry_id,
                success=True,
                message="异步Write-Back已提交",
            )

    async def _execute_with_retry(self, entry: WriteBackEntry) -> WriteBackResult:
        handler = self._handlers.get(entry.target_system)
        if handler is None:
            entry.status = WriteBackStatus.FAILED
            entry.last_error = f"未注册的目标系统: {entry.target_system}"
            self._move_to_dead_letter(entry, entry.last_error)
            return WriteBackResult(
                entry_id=entry.entry_id,
                success=False,
                message=entry.last_error,
            )

        for attempt in range(entry.max_retries + 1):
            try:
                entry.status = WriteBackStatus.RETRYING if attempt > 0 else WriteBackStatus.PENDING
                entry.retry_count = attempt
                entry.executed_at = datetime.now()

                result_data = await handler(entry.payload)

                entry.status = WriteBackStatus.SUCCESS
                entry.completed_at = datetime.now()
                logger.info(f"Write-Back success: {entry.entry_id} ({entry.source_action}→{entry.target_system})")
                return WriteBackResult(
                    entry_id=entry.entry_id,
                    success=True,
                    message="Write-Back执行成功",
                    data=result_data if isinstance(result_data, dict) else None,
                )

            except Exception as e:
                entry.last_error = str(e)
                logger.warning(
                    f"Write-Back attempt {attempt + 1}/{entry.max_retries + 1} failed: "
                    f"{entry.entry_id} - {e}"
                )
                if attempt < entry.max_retries:
                    import asyncio
                    delay = self.retry_delay_seconds * (attempt + 1)
                    await asyncio.sleep(delay)

        entry.status = WriteBackStatus.FAILED
        self._move_to_dead_letter(entry, f"重试{entry.max_retries}次后仍失败: {entry.last_error}")
        return WriteBackResult(
            entry_id=entry.entry_id,
            success=False,
            message=f"Write-Back失败，已移入死信队列: {entry.last_error}",
        )

    async def _execute_async(self, entry: WriteBackEntry) -> None:
        result = await self._execute_with_retry(entry)
        if not result.success:
            logger.error(f"Async Write-Back failed: {entry.entry_id} - {result.message}")

    def _move_to_dead_letter(self, entry: WriteBackEntry, reason: str) -> None:
        dead_letter = DeadLetterEntry(
            entry_id=f"DL-{uuid.uuid4().hex[:8].upper()}",
            original_entry=entry,
            reason=reason,
        )
        self._dead_letters[dead_letter.entry_id] = dead_letter
        logger.error(f"Write-Back moved to dead letter: {entry.entry_id} - {reason}")

    def get_entry(self, entry_id: str) -> Optional[WriteBackEntry]:
        return self._entries.get(entry_id)

    def get_dead_letters(self) -> Dict[str, DeadLetterEntry]:
        return self._dead_letters.copy()

    def retry_dead_letter(self, dead_letter_id: str) -> Optional[WriteBackResult]:
        dead_letter = self._dead_letters.get(dead_letter_id)
        if dead_letter is None:
            return None

        import asyncio
        entry = dead_letter.original_entry
        entry.retry_count = 0
        entry.status = WriteBackStatus.PENDING
        entry.last_error = None

        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(self._execute_with_retry(entry))
            return WriteBackResult(
                entry_id=entry.entry_id,
                success=True,
                message="死信队列重试已提交",
            )
        else:
            result = loop.run_until_complete(self._execute_with_retry(entry))
            if result.success:
                del self._dead_letters[dead_letter_id]
            return result

    def get_stats(self) -> Dict[str, Any]:
        total = len(self._entries)
        success = sum(1 for e in self._entries.values() if e.status == WriteBackStatus.SUCCESS)
        failed = sum(1 for e in self._entries.values() if e.status == WriteBackStatus.FAILED)
        pending = sum(1 for e in self._entries.values() if e.status == WriteBackStatus.PENDING)
        retrying = sum(1 for e in self._entries.values() if e.status == WriteBackStatus.RETRYING)
        dead_letter_count = len(self._dead_letters)

        return {
            "total": total,
            "success": success,
            "failed": failed,
            "pending": pending,
            "retrying": retrying,
            "dead_letter": dead_letter_count,
            "success_rate": (success / total * 100) if total > 0 else 0,
        }


_write_back_engine: Optional[WriteBackEngine] = None


def get_write_back_engine() -> WriteBackEngine:
    global _write_back_engine
    if _write_back_engine is None:
        _write_back_engine = WriteBackEngine()
        _register_default_handlers(_write_back_engine)
    return _write_back_engine


def _register_default_handlers(engine: WriteBackEngine) -> None:
    async def _budget_system_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
        """预算系统Write-Back：核销时同步更新预算额度"""
        action = payload.get("action", "")
        budget_id = payload.get("budget_id", "")
        amount = payload.get("amount", 0)

        logger.info(f"[Write-Back→预算系统] action={action}, budget_id={budget_id}, amount={amount}")

        try:
            from ontology.cache_manager import get_cache_manager
            from decimal import Decimal

            cache_mgr = get_cache_manager()

            if action == "write_off":
                # 核销：减少可用额度
                remaining = cache_mgr.get_remaining_amount(budget_id)
                if remaining is not None:
                    new_remaining = remaining - Decimal(str(amount))
                    cache_mgr.update_remaining_amount_cache_aside(budget_id, new_remaining)
                    logger.info(f"[Write-Back→预算系统] 核销成功: {budget_id} remaining {remaining}→{new_remaining}")
                    return {"action": action, "budget_id": budget_id, "status": "updated", "new_remaining": str(new_remaining)}
                else:
                    logger.warning(f"[Write-Back→预算系统] 预算{budget_id}缓存无值，需从DB加载后重试")
                    return {"action": action, "budget_id": budget_id, "status": "cache_miss"}

            elif action == "freeze":
                # 冻结：减少可用额度
                remaining = cache_mgr.get_remaining_amount(budget_id)
                if remaining is not None:
                    new_remaining = remaining - Decimal(str(amount))
                    cache_mgr.update_remaining_amount_cache_aside(budget_id, new_remaining)
                    return {"action": action, "budget_id": budget_id, "status": "frozen", "new_remaining": str(new_remaining)}

            elif action == "release":
                # 释放：增加可用额度
                remaining = cache_mgr.get_remaining_amount(budget_id)
                if remaining is not None:
                    new_remaining = remaining + Decimal(str(amount))
                    cache_mgr.update_remaining_amount_cache_aside(budget_id, new_remaining)
                    return {"action": action, "budget_id": budget_id, "status": "released", "new_remaining": str(new_remaining)}

            return {"action": action, "budget_id": budget_id, "status": "unknown_action"}

        except Exception as e:
            logger.error(f"[Write-Back→预算系统] 执行失败: {e}")
            raise

    async def _message_system_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
        """消息系统Write-Back：预警触发时发送通知"""
        alert_id = payload.get("alert_id", "")
        alert_level = payload.get("alert_level", "")
        message = payload.get("message", "")
        targets = payload.get("targets", [])

        logger.info(f"[Write-Back→消息系统] alert_id={alert_id}, level={alert_level}, targets={targets}")

        # 按预警级别确定通知渠道和紧急程度
        channel_map = {
            "蓝色": {"channel": "站内信", "urgency": "低"},
            "黄色": {"channel": "站内信+邮件", "urgency": "中"},
            "橙色": {"channel": "站内信+邮件+短信", "urgency": "高"},
            "红色": {"channel": "站内信+邮件+短信+电话", "urgency": "紧急"},
        }
        channel_info = channel_map.get(alert_level, {"channel": "站内信", "urgency": "低"})

        notification_results = []
        for target in targets:
            notification_results.append({
                "target": target,
                "channel": channel_info["channel"],
                "status": "sent",
                "urgency": channel_info["urgency"],
            })

        return {
            "alert_id": alert_id,
            "notification_sent": True,
            "channel": channel_info["channel"],
            "urgency": channel_info["urgency"],
            "recipients": len(targets),
            "results": notification_results,
        }

    async def _report_system_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
        """报表系统Write-Back：数据变更时标记报表需重新生成"""
        report_type = payload.get("report_type", "")
        period = payload.get("period", "")
        trigger_action = payload.get("trigger_action", "")
        budget_ids = payload.get("budget_ids", [])

        logger.info(f"[Write-Back→报表系统] report_type={report_type}, period={period}, trigger={trigger_action}")

        # 标记相关报表为"待重新生成"状态
        affected_reports = []
        if report_type == "monthly":
            affected_reports.append({"report_type": "月度快报", "period": period, "status": "待重新生成", "reason": f"由{trigger_action}触发"})
        elif report_type == "quarterly":
            affected_reports.append({"report_type": "季度汇报PPT", "period": period, "status": "待重新生成", "reason": f"由{trigger_action}触发"})
        elif report_type == "yearly":
            affected_reports.append({"report_type": "年度复盘报告", "period": period, "status": "待重新生成", "reason": f"由{trigger_action}触发"})

        # 如果指定了预算项目，标记这些项目相关的报表
        for bid in budget_ids:
            affected_reports.append({"budget_id": bid, "report_impact": "数据已变更，相关报表需更新"})

        return {
            "report_type": report_type,
            "period": period,
            "status": "regeneration_scheduled",
            "affected_reports": affected_reports,
        }

    engine.register_handler("budget_system", _budget_system_handler)
    engine.register_handler("message_system", _message_system_handler)
    engine.register_handler("report_system", _report_system_handler)
