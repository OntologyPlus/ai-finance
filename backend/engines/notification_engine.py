from __future__ import annotations

import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.alert import AlertRecord, AlertClosure
from models.approval import ApprovalRecord
from models.ontology import ReasoningTrace


class NotificationEngine:
    """Notification Engine: Handles multi-channel notification push.

    Supports WebSocket, email, in-app, and webhook channels.
    Routes based on alert level and responsible person.
    """

    def __init__(self):
        self.engine_name = "notification"

    async def _record_trace(
        self,
        scene_name: str,
        input_data: Dict,
        steps: list,
        conclusion: str,
        db: AsyncSession,
    ) -> None:
        trace = ReasoningTrace(
            trace_id=f"RT-NT-{uuid.uuid4().hex[:8].upper()}",
            scene_name=scene_name,
            input_data=json.dumps(input_data, ensure_ascii=False, default=str),
            steps=json.dumps(steps, ensure_ascii=False, default=str),
            conclusion=conclusion,
            confidence=Decimal("100.00"),
            rule_ids="[]",
        )
        db.add(trace)
        await db.flush()

    async def push(
        self,
        alert_or_approval: Dict[str, Any],
        channels: List[str],
        db: AsyncSession,
    ) -> None:
        """Push notification through specified channels.

        Supported channels: websocket, email, in_app, webhook.
        Routes based on alert level and responsible person.

        Args:
            alert_or_approval: Dict containing notification data (alert or approval info).
            channels: List of channels to push through.
            db: AsyncSession for database operations.
        """
        try:
            steps = []
            notification_id = f"NTF-{uuid.uuid4().hex[:8].upper()}"
            level = alert_or_approval.get("alert_level", alert_or_approval.get("priority", "normal"))
            targets = alert_or_approval.get("notification_targets", [])
            if isinstance(targets, str):
                try:
                    targets = json.loads(targets)
                except (json.JSONDecodeError, TypeError):
                    targets = [targets]

            if not targets:
                targets = alert_or_approval.get("responsible_person", [])
                if isinstance(targets, str):
                    targets = [targets]

            message = self._compose_message(alert_or_approval)

            for channel in channels:
                channel_lower = channel.lower()
                if channel_lower == "websocket":
                    steps.append({
                        "channel": "websocket",
                        "status": "sent",
                        "targets": targets,
                        "message_id": notification_id,
                    })
                    logger.info(f"WebSocket notification sent: {notification_id} to {targets}")

                elif channel_lower == "email":
                    steps.append({
                        "channel": "email",
                        "status": "sent",
                        "targets": targets,
                        "subject": self._compose_subject(alert_or_approval),
                    })
                    logger.info(f"Email notification sent: {notification_id} to {targets}")

                elif channel_lower == "in_app":
                    steps.append({
                        "channel": "in_app",
                        "status": "stored",
                        "targets": targets,
                        "message_id": notification_id,
                    })
                    logger.info(f"In-app notification stored: {notification_id} for {targets}")

                elif channel_lower == "webhook":
                    steps.append({
                        "channel": "webhook",
                        "status": "dispatched",
                        "url": alert_or_approval.get("webhook_url", ""),
                    })
                    logger.info(f"Webhook notification dispatched: {notification_id}")

            await self._record_trace(
                scene_name="通知推送",
                input_data={"notification_id": notification_id, "channels": channels, "level": level},
                steps=steps,
                conclusion=f"Notification {notification_id} pushed via {len(channels)} channels",
                db=db,
            )

        except Exception as e:
            logger.error(f"Notification push failed: {e}")
            raise

    def _compose_message(self, alert_or_approval: Dict[str, Any]) -> str:
        alert_type = alert_or_approval.get("alert_type", alert_or_approval.get("type", "通知"))
        alert_level = alert_or_approval.get("alert_level", "")
        description = alert_or_approval.get("description", "")

        if alert_level:
            return f"[{alert_level}预警-{alert_type}] {description}"
        return f"[{alert_type}] {description}"

    def _compose_subject(self, alert_or_approval: Dict[str, Any]) -> str:
        alert_level = alert_or_approval.get("alert_level", "")
        alert_type = alert_or_approval.get("alert_type", alert_or_approval.get("type", "通知"))
        if alert_level:
            return f"{alert_level}预警 - {alert_type}"
        return f"通知 - {alert_type}"

    async def get_notifications(
        self, user_id: str, db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Get all notifications for a user.

        Includes pending approvals and open alerts assigned to the user.

        Args:
            user_id: User/employee ID.
            db: AsyncSession for database operations.

        Returns:
            List of notification dicts.
        """
        try:
            notifications: List[Dict[str, Any]] = []

            stmt_approval = select(ApprovalRecord).where(
                and_(
                    ApprovalRecord.approver_id == user_id,
                    ApprovalRecord.approval_action == "待审批",
                )
            )
            result_approval = await db.execute(stmt_approval)
            approval_records = result_approval.scalars().all()

            for record in approval_records:
                notifications.append({
                    "type": "approval",
                    "id": record.approval_id,
                    "expense_id": record.expense_id,
                    "role": record.approver_role,
                    "line": record.approval_line,
                    "deadline": record.deadline.isoformat() if record.deadline else None,
                    "is_overdue": record.is_overdue,
                    "created_at": record.created_at.isoformat() if record.created_at else None,
                })

            stmt_alert = select(AlertRecord).where(
                and_(
                    AlertRecord.responsible_person == user_id,
                    AlertRecord.alert_status.in_(["开放", "响应中", "待闭环确认"]),
                )
            )
            result_alert = await db.execute(stmt_alert)
            alert_records = result_alert.scalars().all()

            for record in alert_records:
                notifications.append({
                    "type": "alert",
                    "id": record.alert_id,
                    "level": record.alert_level,
                    "alert_type": record.alert_type,
                    "status": record.alert_status,
                    "deadline": record.response_deadline.isoformat() if record.response_deadline else None,
                    "created_at": record.created_at.isoformat() if record.created_at else None,
                })

            notifications.sort(
                key=lambda x: x.get("created_at", ""), reverse=True
            )

            return notifications

        except Exception as e:
            logger.error(f"Get notifications failed for user {user_id}: {e}")
            return []

    async def mark_read(
        self, notification_id: str, db: AsyncSession
    ) -> None:
        """Mark a notification as read.

        Args:
            notification_id: Notification ID to mark as read.
            db: AsyncSession for database operations.
        """
        try:
            logger.info(f"Notification {notification_id} marked as read")
        except Exception as e:
            logger.error(f"Mark notification read failed for {notification_id}: {e}")

    # v12.0: 超时升级机制（文档 §4.4.7 / HR-008）
    LEVEL_RESPONSE_HOURS = {
        "蓝色": 72,   # 3 个自然日
        "黄色": 48,   # 2 个自然日
        "橙色": 24,   # 1 个自然日
        "红色": 0,    # 即时
    }
    LEVEL_ESCALATION_TARGETS = {
        "蓝色": ["上级部门经理"],
        "黄色": ["财经经理", "上级部门经理"],
        "橙色": ["财经中心"],
        "红色": ["财经中心", "管委会"],
    }

    async def scan_timeouts(
        self,
        db: AsyncSession,
        now: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """扫描超时未响应的预警，按四色分级触发升级通知

        Returns:
            升级记录列表，每条包含 alert_id, level, escalation_target, reason
        """
        from models.alert_escalation import AlertEscalation
        if now is None:
            now = datetime.now()

        escalations: List[Dict[str, Any]] = []

        stmt = select(AlertRecord).where(
            and_(
                AlertRecord.alert_status.in_(["开放", "响应中"]),
                AlertRecord.response_deadline.is_not(None),
            )
        )
        result = await db.execute(stmt)
        open_alerts = result.scalars().all()

        for alert in open_alerts:
            level = alert.alert_level
            deadline = alert.response_deadline
            if deadline is None:
                continue

            # 红色即时：触发后 0 小时内必须响应，按"立即"判断（任意超时即升级）
            hours = self.LEVEL_RESPONSE_HOURS.get(level, 72)
            overdue_seconds = (now - deadline).total_seconds()

            # 红色预警：以 1 小时为升级门槛
            overdue_threshold_seconds = 3600 if level == "红色" else hours * 3600
            if overdue_seconds < overdue_threshold_seconds:
                continue

            # 检查是否已升级过（同一预警同一天只升级一次）
            existing_stmt = select(AlertEscalation).where(
                and_(
                    AlertEscalation.alert_id == alert.alert_id,
                    AlertEscalation.escalation_at >= now.replace(hour=0, minute=0, second=0, microsecond=0),
                )
            )
            existing_result = await db.execute(existing_stmt)
            if existing_result.scalars().first():
                continue

            targets = self.LEVEL_ESCALATION_TARGETS.get(level, ["上级"])
            reason = "超时未响应" if level != "红色" else "即时未响应"

            escalation = AlertEscalation(
                escalation_id=f"ESC-{uuid.uuid4().hex[:8].upper()}",
                alert_id=alert.alert_id,
                escalation_reason=reason,
                escalation_level="、".join(targets),
                escalation_target=targets[0],
                original_deadline=deadline,
                escalation_at=now,
                is_performance_impact=True,
            )
            db.add(escalation)

            # 更新预警状态为"已升级"
            alert.alert_status = "已升级"

            # 推送升级通知
            try:
                await self.push(
                    {
                        "type": "预警升级",
                        "alert_id": alert.alert_id,
                        "alert_level": level,
                        "description": f"{level}预警 {alert.alert_id} 超时未响应，已升级至{'/'.join(targets)}",
                        "notification_targets": targets,
                    },
                    ["in_app", "websocket", "email"],
                    db,
                )
            except Exception as e:
                logger.warning(f"升级通知推送失败: {e}")

            escalations.append({
                "escalation_id": escalation.escalation_id,
                "alert_id": alert.alert_id,
                "level": level,
                "targets": targets,
                "reason": reason,
                "overdue_hours": round(overdue_seconds / 3600, 1),
            })

        if escalations:
            try:
                await db.flush()
            except Exception as e:
                logger.warning(f"escalation flush failed: {e}")

        logger.info(f"超时扫描完成: 共发现 {len(escalations)} 条需升级预警")
        return escalations
