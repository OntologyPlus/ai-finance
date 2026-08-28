from __future__ import annotations

import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.business_review import BusinessReviewMeeting, MeetingResolution, ResolutionTracking
from models.alert import AlertRecord
from models.analysis import ExecutionRate, GapAnalysis
from models.budget import BudgetItem
from models.ontology import ReasoningTrace


class BusinessReviewEngine:
    """Business Review Engine (阶段九): 经营分析会与决议闭环.

    Handles meeting agenda generation, resolution recording,
    resolution tracking, and cross-center comparison.
    """

    def __init__(self):
        self.engine_name = "business_review"

    async def _record_trace(
        self,
        scene_name: str,
        input_data: Dict,
        steps: list,
        conclusion: str,
        rule_ids: list,
        confidence: Decimal,
        db: AsyncSession,
    ) -> None:
        trace = ReasoningTrace(
            trace_id=f"RT-BR-{uuid.uuid4().hex[:8].upper()}",
            scene_name=scene_name,
            input_data=json.dumps(input_data, ensure_ascii=False, default=str),
            steps=json.dumps(steps, ensure_ascii=False, default=str),
            conclusion=conclusion,
            confidence=confidence,
            rule_ids=json.dumps(rule_ids, ensure_ascii=False),
        )
        db.add(trace)
        await db.flush()

    async def generate_agenda(
        self, meeting_type: str, period: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """Auto-generate meeting agenda based on alerts/3GAP/execution rates.

        Args:
            meeting_type: Meeting type (月度/季度).
            period: Analysis period.
            db: AsyncSession for database operations.

        Returns:
            Dict with generated agenda and meeting record.
        """
        try:
            steps = []
            agenda_items = []

            # 1. Collect alert data
            stmt_alert = select(AlertRecord).where(
                AlertRecord.alert_status.in_(["开放", "响应中", "已升级"]),
            )
            result_alert = await db.execute(stmt_alert)
            open_alerts = result_alert.scalars().all()
            steps.append({"step": "alert_data", "count": len(open_alerts)})

            red_alerts = [a for a in open_alerts if a.alert_level == "红色"]
            orange_alerts = [a for a in open_alerts if a.alert_level == "橙色"]

            if red_alerts:
                agenda_items.append({
                    "item": "红色预警处理",
                    "priority": "紧急",
                    "duration": "15min",
                    "detail": f"共{len(red_alerts)}条红色预警需处理",
                })
            if orange_alerts:
                agenda_items.append({
                    "item": "橙色预警跟进",
                    "priority": "重要",
                    "duration": "10min",
                    "detail": f"共{len(orange_alerts)}条橙色预警需跟进",
                })

            # 2. Execution rate review
            stmt_exec = select(ExecutionRate).where(ExecutionRate.period == period)
            result_exec = await db.execute(stmt_exec)
            rates = result_exec.scalars().all()
            steps.append({"step": "execution_data", "count": len(rates)})

            avg_rate = 0
            if rates:
                avg_rate = sum(float(r.annual_rate or 0) for r in rates) / len(rates)

            agenda_items.append({
                "item": "预算执行率回顾",
                "priority": "重要",
                "duration": "20min",
                "detail": f"平均执行率{avg_rate:.1f}%",
            })

            # 3. 3GAP analysis (for quarterly meetings)
            if meeting_type == "季度":
                stmt_gap = select(GapAnalysis).where(GapAnalysis.period == period)
                result_gap = await db.execute(stmt_gap)
                gaps = result_gap.scalars().all()
                steps.append({"step": "gap_data", "count": len(gaps)})

                agenda_items.append({
                    "item": "3GAP差距分析",
                    "priority": "重要",
                    "duration": "30min",
                    "detail": "目标差距/执行差距/能力差距分析",
                })

            # 4. Resolution tracking
            agenda_items.append({
                "item": "上次决议执行情况",
                "priority": "常规",
                "duration": "10min",
            })

            # 5. Next period priorities
            agenda_items.append({
                "item": "下阶段工作重点",
                "priority": "常规",
                "duration": "15min",
            })

            # Create meeting record
            meeting = BusinessReviewMeeting(
                meeting_type=meeting_type,
                period=period,
                agenda=agenda_items,
                status="计划中",
            )
            db.add(meeting)
            await db.flush()
            steps.append({"step": "create_meeting", "meeting_id": meeting.id})

            await self._record_trace(
                scene_name="经营分析会议程生成",
                input_data={"meeting_type": meeting_type, "period": period},
                steps=steps,
                conclusion=f"Meeting agenda generated, meeting_id={meeting.id}",
                rule_ids=["HR-BR-AGENDA"],
                confidence=Decimal("90.00"),
                db=db,
            )

            logger.info(f"Meeting agenda generated for {meeting_type} period {period}")
            return {
                "meeting_id": meeting.id,
                "meeting_type": meeting_type,
                "period": period,
                "agenda": agenda_items,
                "status": "计划中",
            }

        except Exception as e:
            logger.error(f"Meeting agenda generation failed: {e}")
            raise

    async def record_resolution(
        self,
        meeting_id: int,
        content: str,
        owner: str,
        deadline: datetime,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Record a meeting resolution.

        Args:
            meeting_id: Meeting ID.
            content: Resolution content.
            owner: Responsible person.
            deadline: Deadline for the resolution.
            db: AsyncSession for database operations.

        Returns:
            Dict with resolution record.
        """
        try:
            meeting = await db.get(BusinessReviewMeeting, meeting_id)
            if meeting is None:
                raise ValueError(f"Meeting {meeting_id} not found")

            resolution = MeetingResolution(
                meeting_id=meeting_id,
                content=content,
                owner=owner,
                deadline=deadline,
                completion_status="待执行",
                progress=0,
            )
            db.add(resolution)

            meeting.resolution_count = (meeting.resolution_count or 0) + 1
            await db.flush()

            # Create initial tracking record
            tracking = ResolutionTracking(
                resolution_id=resolution.id,
                progress_percent=0,
                risk_flag="无",
            )
            db.add(tracking)
            await db.flush()

            await self._record_trace(
                scene_name="会议决议记录",
                input_data={"meeting_id": meeting_id, "content": content, "owner": owner},
                steps=[{"step": "record_resolution", "resolution_id": resolution.id}],
                conclusion=f"Resolution {resolution.id} recorded for meeting {meeting_id}",
                rule_ids=["HR-BR-RES"],
                confidence=Decimal("100.00"),
                db=db,
            )

            logger.info(f"Resolution {resolution.id} recorded for meeting {meeting_id}")
            return {
                "resolution_id": resolution.id,
                "meeting_id": meeting_id,
                "content": content,
                "owner": owner,
                "deadline": deadline.isoformat() if deadline else None,
                "status": "待执行",
                "progress": 0,
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Resolution recording failed: {e}")
            raise

    async def track_resolution(
        self,
        resolution_id: int,
        progress: float,
        risk_flag: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Track resolution progress.

        Args:
            resolution_id: Resolution ID.
            progress: Progress percentage (0-100).
            risk_flag: Risk flag (无/低/中/高).
            db: AsyncSession for database operations.

        Returns:
            Dict with updated tracking info.
        """
        try:
            resolution = await db.get(MeetingResolution, resolution_id)
            if resolution is None:
                raise ValueError(f"Resolution {resolution_id} not found")

            resolution.progress = progress

            # Update completion status based on progress
            if progress >= 100:
                resolution.completion_status = "已完成"
            elif progress > 0:
                resolution.completion_status = "执行中"
                # Check if overdue
                if resolution.deadline and datetime.now() > resolution.deadline:
                    resolution.completion_status = "已逾期"

            # Create new tracking record
            tracking = ResolutionTracking(
                resolution_id=resolution_id,
                progress_percent=progress,
                risk_flag=risk_flag,
            )
            db.add(tracking)
            await db.flush()

            await self._record_trace(
                scene_name="决议进度追踪",
                input_data={"resolution_id": resolution_id, "progress": progress, "risk_flag": risk_flag},
                steps=[{"step": "track", "tracking_id": tracking.id}],
                conclusion=f"Resolution {resolution_id} progress updated to {progress}%",
                rule_ids=["HR-BR-TRACK"],
                confidence=Decimal("100.00"),
                db=db,
            )

            logger.info(f"Resolution {resolution_id} progress updated to {progress}%")
            return {
                "resolution_id": resolution_id,
                "progress": progress,
                "completion_status": resolution.completion_status,
                "risk_flag": risk_flag,
                "tracking_id": tracking.id,
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Resolution tracking failed: {e}")
            raise

    async def cross_center_compare(
        self, period: str, center_ids: List[str], db: AsyncSession
    ) -> Dict[str, Any]:
        """Cross-center comparison of business metrics.

        Args:
            period: Analysis period.
            center_ids: List of center IDs to compare.
            db: AsyncSession for database operations.

        Returns:
            Dict with cross-center comparison data.
        """
        try:
            steps = []
            comparison_data = []

            for center_id in center_ids:
                # Budget execution for this center
                stmt = select(BudgetItem).where(
                    and_(
                        BudgetItem.center_id == center_id,
                        BudgetItem.status.in_(["已授予", "执行中", "已核销"]),
                    )
                )
                result = await db.execute(stmt)
                items = result.scalars().all()

                total_budget = sum(float(i.annual_amount or 0) for i in items)
                total_used = sum(float(i.used_amount or 0) for i in items)
                execution_rate = round(total_used / total_budget * 100, 2) if total_budget > 0 else 0

                # Alert count for this center
                budget_ids = [i.budget_id for i in items]
                alert_count = 0
                red_count = 0
                if budget_ids:
                    stmt_alert = select(AlertRecord).where(
                        and_(
                            AlertRecord.budget_id.in_(budget_ids),
                            AlertRecord.alert_status != "已闭环",
                        )
                    )
                    result_alert = await db.execute(stmt_alert)
                    alerts = result_alert.scalars().all()
                    alert_count = len(alerts)
                    red_count = sum(1 for a in alerts if a.alert_level == "红色")

                # Execution rate detail by L1
                l1_rates = {}
                for item in items:
                    l1 = item.l1_code or "未分类"
                    if l1 not in l1_rates:
                        l1_rates[l1] = {"budget": 0, "used": 0}
                    l1_rates[l1]["budget"] += float(item.annual_amount or 0)
                    l1_rates[l1]["used"] += float(item.used_amount or 0)

                l1_execution = {}
                for l1, vals in l1_rates.items():
                    l1_execution[l1] = round(vals["used"] / vals["budget"] * 100, 2) if vals["budget"] > 0 else 0

                comparison_data.append({
                    "center_id": center_id,
                    "total_budget": total_budget,
                    "total_used": total_used,
                    "execution_rate": execution_rate,
                    "item_count": len(items),
                    "open_alerts": alert_count,
                    "red_alerts": red_count,
                    "l1_execution_rates": l1_execution,
                })

            steps.append({"step": "cross_center_compare", "center_count": len(center_ids)})

            # Rank by execution rate
            ranked = sorted(comparison_data, key=lambda x: x["execution_rate"], reverse=True)

            await self._record_trace(
                scene_name="跨中心对比分析",
                input_data={"period": period, "center_ids": center_ids},
                steps=steps,
                conclusion=f"Cross-center comparison completed for {len(center_ids)} centers",
                rule_ids=["HR-BR-COMPARE"],
                confidence=Decimal("90.00"),
                db=db,
            )

            logger.info(f"Cross-center comparison completed for {len(center_ids)} centers")
            return {
                "period": period,
                "comparison": ranked,
                "center_count": len(center_ids),
            }

        except Exception as e:
            logger.error(f"Cross-center comparison failed: {e}")
            raise
