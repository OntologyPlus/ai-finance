from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select, and_, func, extract
from sqlalchemy.ext.asyncio import AsyncSession

from models.alert import AlertRecord, AlertClosure, AlertEscalation
from models.budget import BudgetItem, BudgetSubjectL1, B2AConversion
from models.ontology import OntologyRule, ReasoningTrace
from models.organization import Employee


ALERT_RESPONSE_HOURS = {
    "蓝色": 72,
    "黄色": 48,
    "橙色": 24,
    "红色": 4,
}

ESCALATION_TIMEOUT_DAYS = {
    "蓝色": 3,
    "黄色": 2,
    "橙色": 1,
    "红色": 0,
}


class AlertMonitorEngine:
    """Alert Monitor Engine (阶段五): Handles alert scanning, triggering, classification, push, closure, and escalation.

    Executes monthly execution progress rules (SR-001/002/003),
    quarterly rolling forecast rules (SR-004/005/006),
    milestone alert rules, and L1-specific rules.
    Four-color classification: 蓝色/黄色/橙色/红色.
    """

    def __init__(self):
        self.engine_name = "alert_monitor"

    async def _get_threshold(
        self, rule_id: str, default_value: int, db: AsyncSession
    ) -> int:
        """从OntologyRule表读取阈值配置，若不存在则返回默认值。

        Args:
            rule_id: 规则ID，如 "ALERT-STRATEGIC-LOW-THRESHOLD"
            default_value: 默认阈值
            db: AsyncSession
        """
        try:
            stmt = select(OntologyRule).where(
                and_(
                    OntologyRule.rule_id == rule_id,
                    OntologyRule.is_active.is_(True),
                )
            )
            result = await db.execute(stmt)
            rule = result.scalars().first()
            if rule and rule.result:
                try:
                    return int(float(rule.result))
                except (ValueError, TypeError):
                    pass
        except Exception as e:
            logger.debug(f"[AlertMonitor] Failed to read threshold {rule_id}: {e}")
        return default_value

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
            trace_id=f"RT-AM-{uuid.uuid4().hex[:8].upper()}",
            scene_name=scene_name,
            input_data=json.dumps(input_data, ensure_ascii=False, default=str),
            steps=json.dumps(steps, ensure_ascii=False, default=str),
            conclusion=conclusion,
            confidence=confidence,
            rule_ids=json.dumps(rule_ids, ensure_ascii=False),
        )
        db.add(trace)
        await db.flush()

    async def _create_alert_record(
        self,
        alert_level: str,
        alert_type: str,
        l1_code: Optional[str],
        trigger_value: Decimal,
        threshold_value: Decimal,
        deviation_rate: Decimal,
        budget_id: Optional[str],
        project_id: Optional[str],
        responsible_person: Optional[str],
        db: AsyncSession,
    ) -> AlertRecord:
        response_hours = ALERT_RESPONSE_HOURS.get(alert_level, 72)
        deadline = datetime.now() + timedelta(hours=response_hours)

        alert = AlertRecord(
            alert_id=f"AL-{uuid.uuid4().hex[:8].upper()}",
            alert_level=alert_level,
            alert_type=alert_type,
            alert_status="开放",
            l1_code=l1_code,
            budget_id=budget_id,
            project_id=project_id,
            trigger_value=trigger_value,
            threshold_value=threshold_value,
            deviation_rate=deviation_rate,
            responsible_person=responsible_person,
            response_deadline=deadline,
            response_hours=response_hours,
        )
        db.add(alert)
        await db.flush()

        try:
            from ontology.write_back import get_write_back_engine, WriteBackConsistency
            wb_engine = get_write_back_engine()
            await wb_engine.execute(
                source_action="alert_triggered",
                target_system="message_system",
                payload={
                    "alert_id": alert.alert_id,
                    "alert_level": alert_level,
                    "alert_type": alert_type,
                    "l1_code": l1_code,
                    "message": f"{alert_level}预警: {alert_type}, L1科目{l1_code}, 偏差率{deviation_rate}%",
                },
                consistency=WriteBackConsistency.EVENTUAL,
                idempotency_key=f"alert-{alert.alert_id}",
            )
        except Exception as wb_err:
            logger.warning(f"Write-Back for alert notification failed (non-blocking): {wb_err}")

        return alert

    async def check_on_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        db: Optional[AsyncSession],
    ) -> Optional[AlertRecord]:
        """Event-driven real-time alert checking.

        Responds to budget events immediately rather than waiting for daily scan.

        Supported event types:
        - BUDGET_WRITTEN_OFF: check execution rate thresholds
        - BUDGET_FROZEN: check if frozen amount leaves insufficient available budget
        - BUDGET_RELEASED: check if released amount is significant
        - BUDGET_GRANTED: check if grant pushes execution rate to concerning level

        Only creates alert if one doesn't already exist for same budget_id + type in last 24h.

        Args:
            event_type: Event type string (e.g. "budget.written_off").
            payload: Event payload dict.
            db: Optional AsyncSession; if None, a new session will be created.

        Returns:
            AlertRecord if alert triggered, None otherwise.
        """
        if db is None:
            from models.database import db_manager
            logger.debug("[Alert] check_on_event: creating own session")
            async with db_manager.async_session_factory() as session:
                try:
                    result = await self._check_on_event_internal(event_type, payload, session)
                    await session.commit()
                    logger.debug("[Alert] check_on_event: own session committed")
                    return result
                except Exception:
                    await session.rollback()
                    logger.warning("[Alert] check_on_event: own session rolled back")
                    raise
        else:
            return await self._check_on_event_internal(event_type, payload, db)

    async def _check_on_event_internal(
        self,
        event_type: str,
        payload: Dict[str, Any],
        db: AsyncSession,
    ) -> Optional[AlertRecord]:
        """Core logic for event-driven alert checking (extracted from check_on_event)."""
        try:
            budget_id = payload.get("budget_id")
            if not budget_id:
                logger.warning(f"[Alert] check_on_event: no budget_id in payload for {event_type}")
                return None

            # Dedup: check if alert already exists for same budget_id + type in last 24h
            alert_type_map = {
                "budget.written_off": "实时核销预警",
                "budget.frozen": "实时冻结预警",
                "budget.released": "实时释放预警",
                "budget.granted": "实时授予预警",
            }
            alert_type = alert_type_map.get(event_type, "实时事件预警")

            cutoff = datetime.now() - timedelta(hours=24)
            stmt_dedup = select(AlertRecord).where(
                and_(
                    AlertRecord.budget_id == budget_id,
                    AlertRecord.alert_type == alert_type,
                    AlertRecord.created_at >= cutoff,
                )
            )
            result_dedup = await db.execute(stmt_dedup)
            existing = result_dedup.scalars().first()
            if existing:
                logger.debug(f"[Alert] Dedup: alert already exists for {budget_id} + {alert_type} in last 24h")
                return None

            # Fetch budget item
            budget_item = await db.get(BudgetItem, budget_id)
            if budget_item is None:
                logger.warning(f"[Alert] check_on_event: budget {budget_id} not found")
                return None

            annual = Decimal(str(budget_item.annual_amount))
            used = Decimal(str(budget_item.used_amount))
            frozen = Decimal(str(budget_item.frozen_amount))
            available = Decimal(str(budget_item.available_amount))

            alert_level = None
            trigger_value = Decimal("0")
            threshold_value = Decimal("0")
            deviation_rate = Decimal("0")

            if event_type == "budget.written_off":
                # Check execution rate thresholds
                if annual > 0:
                    rate = used / annual * 100
                    if rate > 100:
                        alert_level = "红色"
                    elif rate > 95:
                        alert_level = "橙色"
                    elif rate > 80:
                        alert_level = "黄色"
                    trigger_value = used
                    threshold_value = annual
                    deviation_rate = (rate - Decimal("80")).quantize(Decimal("0.01")) if rate > 80 else Decimal("0")

            elif event_type == "budget.frozen":
                # Check if frozen amount leaves insufficient available budget
                if annual > 0:
                    available_rate = available / annual * 100
                    if available_rate < 5:
                        alert_level = "红色"
                    elif available_rate < 15:
                        alert_level = "橙色"
                    elif available_rate < 25:
                        alert_level = "黄色"
                    trigger_value = frozen
                    threshold_value = annual
                    deviation_rate = (Decimal("100") - available_rate).quantize(Decimal("0.01"))

            elif event_type == "budget.released":
                # Check if released amount is significant (>20% of annual)
                release_amount = Decimal(str(payload.get("amount", 0)))
                if annual > 0 and release_amount > annual * Decimal("0.2"):
                    alert_level = "蓝色"
                    trigger_value = release_amount
                    threshold_value = annual * Decimal("0.2")
                    deviation_rate = ((release_amount - annual * Decimal("0.2")) / (annual * Decimal("0.2")) * 100).quantize(Decimal("0.01"))

            elif event_type == "budget.granted":
                # Check if grant pushes execution rate to concerning level
                if annual > 0:
                    rate = used / annual * 100
                    if rate > 95:
                        alert_level = "橙色"
                    elif rate > 80:
                        alert_level = "黄色"
                    trigger_value = used
                    threshold_value = annual
                    deviation_rate = (rate - Decimal("80")).quantize(Decimal("0.01")) if rate > 80 else Decimal("0")

            if not alert_level:
                return None

            alert = await self._create_alert_record(
                alert_level=alert_level,
                alert_type=alert_type,
                l1_code=budget_item.l1_code,
                trigger_value=trigger_value,
                threshold_value=threshold_value,
                deviation_rate=deviation_rate,
                budget_id=budget_id,
                project_id=budget_item.project_id,
                responsible_person=None,
                db=db,
            )

            logger.info(f"[Alert] Real-time alert triggered: {alert_type}, level={alert_level}, budget={budget_id}")
            return alert

        except Exception as e:
            logger.error(f"[Alert] check_on_event failed for {event_type}: {e}")
            return None

    async def daily_scan(self, db: AsyncSession) -> List[AlertRecord]:
        """Execute daily alert scanning across all rule categories.

        Runs monthly execution progress, quarterly rolling forecast,
        milestone, and L1-specific alert rules.

        Args:
            db: AsyncSession for database operations.

        Returns:
            List of newly created AlertRecord objects.
        """
        try:
            all_alerts: List[AlertRecord] = []

            stmt = select(BudgetSubjectL1).where(BudgetSubjectL1.is_active == True if hasattr(BudgetSubjectL1, 'is_active') else True)
            result = await db.execute(stmt)
            l1_subjects = result.scalars().all()

            for l1 in l1_subjects:
                monthly_alert = await self.check_monthly_execution(l1.l1_code, db)
                if monthly_alert:
                    all_alerts.append(monthly_alert)

                quarterly_alert = await self.check_quarterly_rolling(l1.l1_code, db)
                if quarterly_alert:
                    all_alerts.append(quarterly_alert)

                l1_alerts = await self.check_l1_specific(l1.l1_code, db)
                all_alerts.extend(l1_alerts)

            stmt_budget = select(BudgetItem).where(
                and_(
                    BudgetItem.project_id.isnot(None),
                    BudgetItem.status.in_(["已授予", "执行中"]),
                )
            )
            result_budget = await db.execute(stmt_budget)
            project_budgets = result_budget.scalars().all()

            for budget in project_budgets:
                milestone_alert = await self.check_milestone(budget.project_id, db)
                if milestone_alert:
                    all_alerts.append(milestone_alert)

            # Strategic dimension scan
            stmt_all_budget = select(BudgetItem).where(
                BudgetItem.status.in_(["已授予", "执行中"])
            )
            result_all_budget = await db.execute(stmt_all_budget)
            budget_items = result_all_budget.scalars().all()

            now = datetime.now()
            months_elapsed = now.month

            # 从OntologyRule读取战略维度阈值
            strategic_low_threshold = await self._get_threshold(
                "ALERT-STRATEGIC-LOW-THRESHOLD", 40, db
            )
            strategic_high_threshold = await self._get_threshold(
                "ALERT-STRATEGIC-HIGH-THRESHOLD", 100, db
            )
            low_rate = Decimal(str(strategic_low_threshold)) / Decimal("100")
            high_rate = Decimal(str(strategic_high_threshold)) / Decimal("100")

            strategic_groups: Dict[str, Dict] = {}
            for item in budget_items:
                si = item.strategic_intent_l1 or "未关联"
                if si not in strategic_groups:
                    strategic_groups[si] = {"total": Decimal("0"), "used": Decimal("0"), "count": 0}
                strategic_groups[si]["total"] += Decimal(str(item.annual_amount))
                strategic_groups[si]["used"] += Decimal(str(item.used_amount))
                strategic_groups[si]["count"] += 1

            for strategy, data in strategic_groups.items():
                if data["total"] <= 0:
                    continue
                rate = data["used"] / data["total"]

                # Low execution rate for strategic group
                if rate < low_rate and months_elapsed >= 6:
                    deviation = ((low_rate - rate) / low_rate * 100).quantize(Decimal("0.01"))
                    alert = await self._create_alert_record(
                        alert_level="黄色",
                        alert_type="战略维度",
                        l1_code=None,
                        trigger_value=data["used"].quantize(Decimal("0.01")),
                        threshold_value=(data["total"] * low_rate).quantize(Decimal("0.01")),
                        deviation_rate=deviation,
                        budget_id=None,
                        project_id=None,
                        responsible_person=None,
                        db=db,
                    )
                    all_alerts.append(alert)

                # Check 收缩 quadrant over-execution
                shrink_items = [i for i in budget_items if i.quadrant == "收缩" and (i.strategic_intent_l1 or "未关联") == strategy]
                if shrink_items:
                    shrink_total = sum(Decimal(str(i.annual_amount)) for i in shrink_items)
                    shrink_used = sum(Decimal(str(i.used_amount)) for i in shrink_items)
                    if shrink_total > 0 and shrink_used / shrink_total > high_rate:
                        deviation = ((shrink_used / shrink_total - high_rate) * 100).quantize(Decimal("0.01"))
                        alert = await self._create_alert_record(
                            alert_level="红色",
                            alert_type="战略维度",
                            l1_code=None,
                            trigger_value=shrink_used.quantize(Decimal("0.01")),
                            threshold_value=(shrink_total * high_rate).quantize(Decimal("0.01")),
                            deviation_rate=deviation,
                            budget_id=None,
                            project_id=None,
                            responsible_person=None,
                            db=db,
                        )
                        all_alerts.append(alert)

            for alert in all_alerts:
                await self.push_alert(alert.alert_id, db)

            await self._record_trace(
                scene_name="预警日扫描",
                input_data={"l1_count": len(l1_subjects), "project_count": len(project_budgets)},
                steps=[{"step": "scan_complete", "alert_count": len(all_alerts)}],
                conclusion=f"Daily scan complete: {len(all_alerts)} alerts generated",
                rule_ids=["SR-001", "SR-002", "SR-003", "SR-004", "SR-005", "SR-006"],
                confidence=Decimal("90.00"),
                db=db,
            )

            logger.info(f"Daily alert scan complete: {len(all_alerts)} alerts")
            return all_alerts

        except Exception as e:
            logger.error(f"Daily alert scan failed: {e}")
            raise

    async def check_monthly_execution(
        self, l1_code: str, db: AsyncSession
    ) -> Optional[AlertRecord]:
        """Check monthly execution progress against plan for an L1 subject.

        Uses execution rate deviation logic per Palantir Ontology FDE methodology:
        - Target execution rate = (current_month / 12) * 100 (time-based plan)
        - Blue: actual_rate < target_rate * 80%
        - Yellow: actual_rate < target_rate * 60%
        - Red: actual_rate < target_rate * 40%
        - Over-budget: actual > annual budget (hard violation, separate from soft rules)

        Args:
            l1_code: L1 subject code.
            db: AsyncSession for database operations.

        Returns:
            AlertRecord if threshold exceeded, None otherwise.
        """
        try:
            stmt = select(BudgetItem).where(
                and_(
                    BudgetItem.l1_code == l1_code,
                    BudgetItem.status.in_(["已授予", "执行中"]),
                )
            )
            result = await db.execute(stmt)
            items = result.scalars().all()

            if not items:
                return None

            total_annual = sum(Decimal(str(i.annual_amount)) for i in items)
            total_used = sum(Decimal(str(i.used_amount)) for i in items)

            if total_annual <= 0:
                return None

            now = datetime.now()
            target_rate = Decimal(str(now.month)) / Decimal("12") * 100
            actual_rate = total_used / total_annual * 100

            alert_level = None
            threshold = Decimal("0")

            if total_used > total_annual:
                alert_level = "红色"
                threshold = total_annual
            elif actual_rate < target_rate * Decimal("0.4"):
                alert_level = "红色"
                threshold = total_annual * target_rate * Decimal("0.4") / 100
            elif actual_rate < target_rate * Decimal("0.6"):
                alert_level = "黄色"
                threshold = total_annual * target_rate * Decimal("0.6") / 100
            elif actual_rate < target_rate * Decimal("0.8"):
                alert_level = "蓝色"
                threshold = total_annual * target_rate * Decimal("0.8") / 100

            for item in items:
                item_deviation = Decimal(str(item.used_amount)) - Decimal(str(item.annual_amount))
                if item_deviation > Decimal("500000"):
                    alert_level = "红色"
                    threshold = Decimal(str(item.annual_amount))
                    break

            if not alert_level:
                return None

            deviation_rate = ((total_used - threshold) / threshold * 100) if threshold > 0 else Decimal("0")

            alert = await self._create_alert_record(
                alert_level=alert_level,
                alert_type="月度执行进度",
                l1_code=l1_code,
                trigger_value=total_used,
                threshold_value=threshold,
                deviation_rate=deviation_rate.quantize(Decimal("0.01")),
                budget_id=None,
                project_id=None,
                responsible_person=None,
                db=db,
            )

            logger.info(f"Monthly execution alert: L1={l1_code}, level={alert_level}, actual_rate={actual_rate:.1f}%, target_rate={target_rate:.1f}%")
            return alert

        except Exception as e:
            logger.error(f"Monthly execution check failed for L1 {l1_code}: {e}")
            return None

    async def check_quarterly_rolling(
        self, l1_code: str, db: AsyncSession
    ) -> Optional[AlertRecord]:
        """Check quarterly rolling forecast against plan for an L1 subject.

        Uses execution rate deviation logic per Palantir Ontology FDE methodology:
        - Target execution rate = (current_month / 12) * 100
        - Blue: forecast_rate < target_rate * 80%
        - Yellow: forecast_rate < target_rate * 60%
        - Red: forecast_rate < target_rate * 40%

        Args:
            l1_code: L1 subject code.
            db: AsyncSession for database operations.

        Returns:
            AlertRecord if threshold exceeded, None otherwise.
        """
        try:
            stmt = select(BudgetItem).where(
                and_(
                    BudgetItem.l1_code == l1_code,
                    BudgetItem.status.in_(["已授予", "执行中"]),
                )
            )
            result = await db.execute(stmt)
            items = result.scalars().all()

            if not items:
                return None

            total_annual = sum(Decimal(str(i.annual_amount)) for i in items)
            total_used = sum(Decimal(str(i.used_amount)) for i in items)
            total_frozen = sum(Decimal(str(i.frozen_amount)) for i in items)

            if total_annual <= 0:
                return None

            now = datetime.now()
            target_rate = Decimal(str(now.month)) / Decimal("12") * 100

            forecast = total_used + (total_frozen - total_used) * Decimal("0.8")
            forecast_rate = forecast / total_annual * 100

            alert_level = None
            if forecast_rate < target_rate * Decimal("0.4"):
                alert_level = "红色"
            elif forecast_rate < target_rate * Decimal("0.6"):
                alert_level = "黄色"
            elif forecast_rate < target_rate * Decimal("0.8"):
                alert_level = "蓝色"

            if not alert_level:
                return None

            deviation_rate = abs(forecast_rate - target_rate).quantize(Decimal("0.01"))

            alert = await self._create_alert_record(
                alert_level=alert_level,
                alert_type="季度滚动预测",
                l1_code=l1_code,
                trigger_value=forecast.quantize(Decimal("0.01")),
                threshold_value=total_annual,
                deviation_rate=deviation_rate,
                budget_id=None,
                project_id=None,
                responsible_person=None,
                db=db,
            )

            logger.info(f"Quarterly rolling alert: L1={l1_code}, level={alert_level}, forecast_rate={forecast_rate:.1f}%, target_rate={target_rate:.1f}%")
            return alert

        except Exception as e:
            logger.error(f"Quarterly rolling check failed for L1 {l1_code}: {e}")
            return None

    async def check_milestone(
        self, project_id: str, db: AsyncSession
    ) -> Optional[AlertRecord]:
        """Check milestone progress for a project across three dimensions.

        Three dimensions: time, cost, cumulative progress.
        Take highest level; all three triggered -> red + budget increase.

        Args:
            project_id: Project ID to check.
            db: AsyncSession for database operations.

        Returns:
            AlertRecord if milestone deviation detected, None otherwise.
        """
        try:
            stmt = select(BudgetItem).where(
                and_(
                    BudgetItem.project_id == project_id,
                    BudgetItem.status.in_(["已授予", "执行中"]),
                )
            )
            result = await db.execute(stmt)
            items = result.scalars().all()

            if not items:
                return None

            total_annual = sum(Decimal(str(i.annual_amount)) for i in items)
            total_used = sum(Decimal(str(i.used_amount)) for i in items)

            time_alert = None
            cost_alert = None
            progress_alert = None

            now = datetime.now()
            year_progress = Decimal(str((now.month * 100) // 12))

            # Time dimension: check if any milestone with a planned date has passed but not completed
            quarter_deadline_map = {
                "Q1": datetime(now.year, 3, 31),
                "Q2": datetime(now.year, 6, 30),
                "Q3": datetime(now.year, 9, 30),
                "Q4": datetime(now.year, 12, 31),
            }
            for item in items:
                stmt_b2a = select(B2AConversion).where(
                    and_(
                        B2AConversion.budget_id == item.budget_id,
                        B2AConversion.approval_status != "已通过",
                    )
                )
                result_b2a = await db.execute(stmt_b2a)
                pending_conversions = result_b2a.scalars().all()
                for conv in pending_conversions:
                    deadline = quarter_deadline_map.get(conv.milestone_period)
                    if deadline and now > deadline:
                        delay_days = (now - deadline).days
                        if delay_days > 30:
                            time_alert = "黄色"
                        elif delay_days > 0:
                            time_alert = "蓝色"
                        break
                if time_alert:
                    break

            if total_annual > 0:
                cost_progress = total_used / total_annual * 100
                if cost_progress > year_progress + Decimal("20"):
                    cost_alert = "黄色"
                elif cost_progress > year_progress + Decimal("10"):
                    cost_alert = "蓝色"

            if total_annual > 0:
                execution_rate = total_used / total_annual * 100
                if execution_rate < year_progress - Decimal("20"):
                    progress_alert = "黄色"
                elif execution_rate < year_progress - Decimal("10"):
                    progress_alert = "蓝色"

            all_alerts = [a for a in [time_alert, cost_alert, progress_alert] if a]
            if not all_alerts:
                return None

            level_priority = {"蓝色": 1, "黄色": 2, "橙色": 3, "红色": 4}
            alert_level = max(all_alerts, key=lambda x: level_priority.get(x, 0))

            if len(all_alerts) == 3:
                alert_level = "红色"

            deviation_rate = Decimal("0")
            if total_annual > 0:
                deviation_rate = abs(total_used / total_annual * 100 - year_progress).quantize(Decimal("0.01"))

            # Look up responsible person from organization structure
            responsible_person = None
            first_item = items[0] if items else None
            if first_item:
                stmt_emp = select(Employee).where(
                    and_(
                        Employee.center_id == first_item.center_id,
                        Employee.dept_id == first_item.department_id,
                        Employee.role_id == "R001",
                        Employee.is_active == True,
                    )
                )
                result_emp = await db.execute(stmt_emp)
                resp_employee = result_emp.scalar_one_or_none()
                if resp_employee:
                    responsible_person = resp_employee.employee_name

            alert = await self._create_alert_record(
                alert_level=alert_level,
                alert_type="里程碑",
                l1_code=items[0].l1_code if items else None,
                trigger_value=total_used,
                threshold_value=total_annual,
                deviation_rate=deviation_rate,
                budget_id=items[0].budget_id if items else None,
                project_id=project_id,
                responsible_person=responsible_person,
                db=db,
            )

            logger.info(f"Milestone alert: project={project_id}, level={alert_level}")
            return alert

        except Exception as e:
            logger.error(f"Milestone check failed for project {project_id}: {e}")
            return None

    async def check_l1_specific(
        self, l1_code: str, db: AsyncSession
    ) -> List[AlertRecord]:
        """Check L1-specific alert rules.

        B1: Intangible/engineering/fixed asset specific rules.
        B2: R&D stage specific rules (IND/NDA/III期).
        B4: Tax compliance rules.
        B5: ROI rules by L2.
        B6: Headcount linkage rules.
        B8: Investment stage rules (single > 5M -> red).

        Args:
            l1_code: L1 subject code.
            db: AsyncSession for database operations.

        Returns:
            List of AlertRecord objects for L1-specific violations.
        """
        try:
            alerts: List[AlertRecord] = []

            stmt = select(BudgetItem).where(
                and_(
                    BudgetItem.l1_code == l1_code,
                    BudgetItem.status.in_(["已授予", "执行中"]),
                )
            )
            result = await db.execute(stmt)
            items = result.scalars().all()

            if not items:
                return alerts

            l1_specific_rules = {
                "B1": self._check_b1_rules,
                "B2": self._check_b2_rules,
                "B3": self._check_b3_rules,
                "B4": self._check_b4_rules,
                "B5": self._check_b5_rules,
                "B6": self._check_b6_rules,
                "B7": self._check_b7_rules,
                "B8": self._check_b8_rules,
                "B9": self._check_b9_rules,
            }

            checker = l1_specific_rules.get(l1_code)
            if checker:
                l1_alerts = await checker(items, db)
                alerts.extend(l1_alerts)

            return alerts

        except Exception as e:
            logger.error(f"L1-specific check failed for {l1_code}: {e}")
            return []

    async def _check_b1_rules(
        self, items: List[BudgetItem], db: AsyncSession
    ) -> List[AlertRecord]:
        alerts = []
        b1_thresholds = {
            "无形资产": {
                "keywords": ["无形资产", "专利", "商标", "版权", "知识产权"],
                "yellow": Decimal("1.1"),
                "red": Decimal("1.3"),
            },
            "工程支出": {
                "keywords": ["工程", "建设", "施工", "基建"],
                "yellow": Decimal("1.2"),
                "red": Decimal("1.5"),
            },
            "固定资产": {
                "keywords": ["设备", "固定资产", "采购设备", "机器"],
                "yellow": Decimal("1.2"),
                "red": Decimal("1.5"),
            },
        }
        default_thresholds = {"yellow": Decimal("1.1"), "red": Decimal("1.3")}

        for item in items:
            used = Decimal(str(item.used_amount))
            annual = Decimal(str(item.annual_amount))
            if annual <= 0:
                continue
            name = item.budget_name or ""
            thresholds = default_thresholds
            for sub_name, config in b1_thresholds.items():
                if any(kw in name for kw in config["keywords"]):
                    thresholds = config
                    break

            yellow_threshold = annual * thresholds["yellow"]
            red_threshold = annual * thresholds["red"]

            if used > red_threshold:
                alert = await self._create_alert_record(
                    alert_level="红色",
                    alert_type="L1专项",
                    l1_code="B1",
                    trigger_value=used,
                    threshold_value=red_threshold,
                    deviation_rate=((used - red_threshold) / red_threshold * 100).quantize(Decimal("0.01")),
                    budget_id=item.budget_id,
                    project_id=item.project_id,
                    responsible_person=None,
                    db=db,
                )
                alerts.append(alert)
            elif used > yellow_threshold:
                alert = await self._create_alert_record(
                    alert_level="黄色",
                    alert_type="L1专项",
                    l1_code="B1",
                    trigger_value=used,
                    threshold_value=yellow_threshold,
                    deviation_rate=((used - yellow_threshold) / yellow_threshold * 100).quantize(Decimal("0.01")),
                    budget_id=item.budget_id,
                    project_id=item.project_id,
                    responsible_person=None,
                    db=db,
                )
                alerts.append(alert)
        return alerts

    async def _check_b2_rules(
        self, items: List[BudgetItem], db: AsyncSession
    ) -> List[AlertRecord]:
        alerts = []
        rd_stages = {"IND": Decimal("0.3"), "NDA": Decimal("0.6"), "III期": Decimal("0.8")}
        for item in items:
            used = Decimal(str(item.used_amount))
            annual = Decimal(str(item.annual_amount))
            if annual <= 0:
                continue
            execution_rate = used / annual
            for stage, threshold_ratio in rd_stages.items():
                if execution_rate > threshold_ratio and item.project_id:
                    alert = await self._create_alert_record(
                        alert_level="黄色",
                        alert_type="L1专项",
                        l1_code="B2",
                        trigger_value=used,
                        threshold_value=annual * threshold_ratio,
                        deviation_rate=((execution_rate - threshold_ratio) / threshold_ratio * 100).quantize(Decimal("0.01")),
                        budget_id=item.budget_id,
                        project_id=item.project_id,
                        responsible_person=None,
                        db=db,
                    )
                    alerts.append(alert)
                    break
        return alerts

    async def _check_b3_rules(
        self, items: List[BudgetItem], db: AsyncSession
    ) -> List[AlertRecord]:
        alerts = []
        travel_keywords = ["差旅", "招待", "交通", "住宿", "餐饮"]
        consulting_keywords = ["咨询", "软件服务", "信息技术服务", "外包服务"]
        travel_threshold = Decimal("50000")

        for item in items:
            used = Decimal(str(item.used_amount))
            annual = Decimal(str(item.annual_amount))
            name = item.budget_name or ""

            if any(kw in name for kw in travel_keywords):
                if used > travel_threshold:
                    alert = await self._create_alert_record(
                        alert_level="黄色",
                        alert_type="L1专项",
                        l1_code="B3",
                        trigger_value=used,
                        threshold_value=travel_threshold,
                        deviation_rate=((used - travel_threshold) / travel_threshold * 100).quantize(Decimal("0.01")),
                        budget_id=item.budget_id,
                        project_id=item.project_id,
                        responsible_person=None,
                        db=db,
                    )
                    alerts.append(alert)
            elif any(kw in name for kw in consulting_keywords):
                if annual > 0 and used > annual * Decimal("1.1"):
                    threshold = annual * Decimal("1.1")
                    alert = await self._create_alert_record(
                        alert_level="黄色",
                        alert_type="L1专项",
                        l1_code="B3",
                        trigger_value=used,
                        threshold_value=threshold,
                        deviation_rate=((used - threshold) / threshold * 100).quantize(Decimal("0.01")),
                        budget_id=item.budget_id,
                        project_id=item.project_id,
                        responsible_person=None,
                        db=db,
                    )
                    alerts.append(alert)

        total_annual = sum(Decimal(str(i.annual_amount)) for i in items)
        total_used = sum(Decimal(str(i.used_amount)) for i in items)
        if total_annual > 0 and total_used > total_annual * Decimal("1.1"):
            threshold = total_annual * Decimal("1.1")
            alert = await self._create_alert_record(
                alert_level="黄色",
                alert_type="L1专项",
                l1_code="B3",
                trigger_value=total_used,
                threshold_value=threshold,
                deviation_rate=((total_used - threshold) / threshold * 100).quantize(Decimal("0.01")),
                budget_id=None,
                project_id=None,
                responsible_person=None,
                db=db,
            )
            alerts.append(alert)

        return alerts

    async def _check_b4_rules(
        self, items: List[BudgetItem], db: AsyncSession
    ) -> List[AlertRecord]:
        alerts = []
        for item in items:
            used = Decimal(str(item.used_amount))
            annual = Decimal(str(item.annual_amount))
            if annual <= 0:
                continue
            ratio = used / annual
            if ratio > Decimal("1.1"):
                threshold = annual * Decimal("1.1")
                alert = await self._create_alert_record(
                    alert_level="黄色",
                    alert_type="L1专项",
                    l1_code="B4",
                    trigger_value=used,
                    threshold_value=threshold,
                    deviation_rate=((used - threshold) / threshold * 100).quantize(Decimal("0.01")),
                    budget_id=item.budget_id,
                    project_id=item.project_id,
                    responsible_person=None,
                    db=db,
                )
                alerts.append(alert)
            elif ratio > Decimal("1.05"):
                threshold = annual * Decimal("1.05")
                alert = await self._create_alert_record(
                    alert_level="蓝色",
                    alert_type="L1专项",
                    l1_code="B4",
                    trigger_value=used,
                    threshold_value=threshold,
                    deviation_rate=((used - threshold) / threshold * 100).quantize(Decimal("0.01")),
                    budget_id=item.budget_id,
                    project_id=item.project_id,
                    responsible_person=None,
                    db=db,
                )
                alerts.append(alert)
        return alerts

    async def _check_b5_rules(
        self, items: List[BudgetItem], db: AsyncSession
    ) -> List[AlertRecord]:
        alerts = []
        b5_subcategories = {
            "销售驱动": {
                "keywords": ["销售"],
                "yellow": Decimal("1.2"),
                "red": Decimal("1.5"),
            },
            "市场驱动": {
                "keywords": ["市场"],
                "blue": Decimal("1.0"),
            },
            "医学驱动": {
                "keywords": ["医学", "KOL"],
                "yellow": Decimal("1.15"),
                "red": Decimal("1.5"),
            },
            "患者驱动": {
                "keywords": ["患者"],
                "yellow": Decimal("1.1"),
                "red": Decimal("1.3"),
            },
            "政策驱动": {
                "keywords": ["政策"],
                "yellow": Decimal("1.2"),
            },
            "开发驱动": {
                "keywords": ["开发"],
                "yellow": Decimal("1.3"),
                "red": Decimal("1.6"),
            },
        }

        for item in items:
            used = Decimal(str(item.used_amount))
            annual = Decimal(str(item.annual_amount))
            if annual <= 0:
                continue
            name = item.budget_name or ""

            for sub_name, config in b5_subcategories.items():
                if not any(kw in name for kw in config["keywords"]):
                    continue

                if "red" in config and used > annual * config["red"]:
                    threshold = annual * config["red"]
                    alert = await self._create_alert_record(
                        alert_level="红色",
                        alert_type="L1专项",
                        l1_code="B5",
                        trigger_value=used,
                        threshold_value=threshold,
                        deviation_rate=((used - threshold) / threshold * 100).quantize(Decimal("0.01")),
                        budget_id=item.budget_id,
                        project_id=item.project_id,
                        responsible_person=None,
                        db=db,
                    )
                    alerts.append(alert)
                elif "yellow" in config and used > annual * config["yellow"]:
                    threshold = annual * config["yellow"]
                    alert = await self._create_alert_record(
                        alert_level="黄色",
                        alert_type="L1专项",
                        l1_code="B5",
                        trigger_value=used,
                        threshold_value=threshold,
                        deviation_rate=((used - threshold) / threshold * 100).quantize(Decimal("0.01")),
                        budget_id=item.budget_id,
                        project_id=item.project_id,
                        responsible_person=None,
                        db=db,
                    )
                    alerts.append(alert)
                elif "blue" in config and used > annual * config["blue"]:
                    threshold = annual * config["blue"]
                    alert = await self._create_alert_record(
                        alert_level="蓝色",
                        alert_type="L1专项",
                        l1_code="B5",
                        trigger_value=used,
                        threshold_value=threshold,
                        deviation_rate=((used - threshold) / threshold * 100).quantize(Decimal("0.01")),
                        budget_id=item.budget_id,
                        project_id=item.project_id,
                        responsible_person=None,
                        db=db,
                    )
                    alerts.append(alert)
                break

        return alerts

    async def _check_b6_rules(
        self, items: List[BudgetItem], db: AsyncSession
    ) -> List[AlertRecord]:
        alerts = []
        salary_keywords = ["工资", "薪酬", "薪资", "奖金"]
        social_security_keywords = ["社保", "公积金", "五险一金"]
        headcount_keywords = ["编制", "人员", "招聘"]

        for item in items:
            used = Decimal(str(item.used_amount))
            annual = Decimal(str(item.annual_amount))
            if annual <= 0:
                continue
            name = item.budget_name or ""
            ratio = used / annual

            if any(kw in name for kw in salary_keywords):
                if ratio > Decimal("1.05"):
                    threshold = annual * Decimal("1.05")
                    alert = await self._create_alert_record(
                        alert_level="黄色",
                        alert_type="L1专项",
                        l1_code="B6",
                        trigger_value=used,
                        threshold_value=threshold,
                        deviation_rate=((used - threshold) / threshold * 100).quantize(Decimal("0.01")),
                        budget_id=item.budget_id,
                        project_id=item.project_id,
                        responsible_person=None,
                        db=db,
                    )
                    alerts.append(alert)
            elif any(kw in name for kw in social_security_keywords):
                if ratio > Decimal("1.05"):
                    threshold = annual * Decimal("1.05")
                    alert = await self._create_alert_record(
                        alert_level="蓝色",
                        alert_type="L1专项",
                        l1_code="B6",
                        trigger_value=used,
                        threshold_value=threshold,
                        deviation_rate=((used - threshold) / threshold * 100).quantize(Decimal("0.01")),
                        budget_id=item.budget_id,
                        project_id=item.project_id,
                        responsible_person=None,
                        db=db,
                    )
                    alerts.append(alert)
            elif any(kw in name for kw in headcount_keywords):
                if ratio > Decimal("1.2"):
                    threshold = annual * Decimal("1.2")
                    alert = await self._create_alert_record(
                        alert_level="红色",
                        alert_type="L1专项",
                        l1_code="B6",
                        trigger_value=used,
                        threshold_value=threshold,
                        deviation_rate=((used - threshold) / threshold * 100).quantize(Decimal("0.01")),
                        budget_id=item.budget_id,
                        project_id=item.project_id,
                        responsible_person=None,
                        db=db,
                    )
                    alerts.append(alert)
                elif ratio > Decimal("1.1"):
                    threshold = annual * Decimal("1.1")
                    alert = await self._create_alert_record(
                        alert_level="黄色",
                        alert_type="L1专项",
                        l1_code="B6",
                        trigger_value=used,
                        threshold_value=threshold,
                        deviation_rate=((used - threshold) / threshold * 100).quantize(Decimal("0.01")),
                        budget_id=item.budget_id,
                        project_id=item.project_id,
                        responsible_person=None,
                        db=db,
                    )
                    alerts.append(alert)
                elif ratio > Decimal("1.05"):
                    threshold = annual * Decimal("1.05")
                    alert = await self._create_alert_record(
                        alert_level="蓝色",
                        alert_type="L1专项",
                        l1_code="B6",
                        trigger_value=used,
                        threshold_value=threshold,
                        deviation_rate=((used - threshold) / threshold * 100).quantize(Decimal("0.01")),
                        budget_id=item.budget_id,
                        project_id=item.project_id,
                        responsible_person=None,
                        db=db,
                    )
                    alerts.append(alert)
            else:
                if ratio > Decimal("1.1"):
                    threshold = annual * Decimal("1.1")
                    alert = await self._create_alert_record(
                        alert_level="黄色",
                        alert_type="L1专项",
                        l1_code="B6",
                        trigger_value=used,
                        threshold_value=threshold,
                        deviation_rate=((used - threshold) / threshold * 100).quantize(Decimal("0.01")),
                        budget_id=item.budget_id,
                        project_id=item.project_id,
                        responsible_person=None,
                        db=db,
                    )
                    alerts.append(alert)
        return alerts

    async def _check_b7_rules(
        self, items: List[BudgetItem], db: AsyncSession
    ) -> List[AlertRecord]:
        alerts = []
        b7_subcategories = {
            "成品采购": {
                "keywords": ["成品", "采购", "进货"],
                "blue": Decimal("0.8"),
            },
            "委托加工": {
                "keywords": ["委托", "加工", "外协"],
                "yellow": Decimal("1.1"),
                "red": Decimal("1.3"),
            },
            "自主生产": {
                "keywords": ["原材料", "自主生产", "生产用料", "原料"],
                "yellow": Decimal("1.1"),
                "red": Decimal("1.3"),
            },
        }

        for item in items:
            used = Decimal(str(item.used_amount))
            annual = Decimal(str(item.annual_amount))
            if annual <= 0:
                continue
            name = item.budget_name or ""

            for sub_name, config in b7_subcategories.items():
                if not any(kw in name for kw in config["keywords"]):
                    continue

                if "red" in config and used > annual * config["red"]:
                    threshold = annual * config["red"]
                    alert = await self._create_alert_record(
                        alert_level="红色",
                        alert_type="L1专项",
                        l1_code="B7",
                        trigger_value=used,
                        threshold_value=threshold,
                        deviation_rate=((used - threshold) / threshold * 100).quantize(Decimal("0.01")),
                        budget_id=item.budget_id,
                        project_id=item.project_id,
                        responsible_person=None,
                        db=db,
                    )
                    alerts.append(alert)
                elif "yellow" in config and used > annual * config["yellow"]:
                    threshold = annual * config["yellow"]
                    alert = await self._create_alert_record(
                        alert_level="黄色",
                        alert_type="L1专项",
                        l1_code="B7",
                        trigger_value=used,
                        threshold_value=threshold,
                        deviation_rate=((used - threshold) / threshold * 100).quantize(Decimal("0.01")),
                        budget_id=item.budget_id,
                        project_id=item.project_id,
                        responsible_person=None,
                        db=db,
                    )
                    alerts.append(alert)
                elif "blue" in config and used > annual * config["blue"]:
                    threshold = annual * config["blue"]
                    alert = await self._create_alert_record(
                        alert_level="蓝色",
                        alert_type="L1专项",
                        l1_code="B7",
                        trigger_value=used,
                        threshold_value=threshold,
                        deviation_rate=((used - threshold) / threshold * 100).quantize(Decimal("0.01")),
                        budget_id=item.budget_id,
                        project_id=item.project_id,
                        responsible_person=None,
                        db=db,
                    )
                    alerts.append(alert)
                break

        return alerts

    async def _check_b8_rules(
        self, items: List[BudgetItem], db: AsyncSession
    ) -> List[AlertRecord]:
        alerts = []
        for item in items:
            if Decimal(str(item.annual_amount)) > Decimal("5000000"):
                used = Decimal(str(item.used_amount))
                annual = Decimal(str(item.annual_amount))
                if annual > 0 and used > annual:
                    alert = await self._create_alert_record(
                        alert_level="红色",
                        alert_type="L1专项",
                        l1_code="B8",
                        trigger_value=used,
                        threshold_value=annual,
                        deviation_rate=((used - annual) / annual * 100).quantize(Decimal("0.01")),
                        budget_id=item.budget_id,
                        project_id=item.project_id,
                        responsible_person=None,
                        db=db,
                    )
                    alerts.append(alert)
        return alerts

    async def _check_b9_rules(
        self, items: List[BudgetItem], db: AsyncSession
    ) -> List[AlertRecord]:
        alerts = []
        interest_keywords = ["利息", "融资", "贷款"]
        fee_keywords = ["手续费", "银行手续费", "账户管理费"]

        for item in items:
            used = Decimal(str(item.used_amount))
            annual = Decimal(str(item.annual_amount))
            name = item.budget_name or ""

            if any(kw in name for kw in interest_keywords):
                if annual > 0 and used > annual * Decimal("1.05"):
                    threshold = annual * Decimal("1.05")
                    alert = await self._create_alert_record(
                        alert_level="蓝色",
                        alert_type="L1专项",
                        l1_code="B9",
                        trigger_value=used,
                        threshold_value=threshold,
                        deviation_rate=((used - threshold) / threshold * 100).quantize(Decimal("0.01")),
                        budget_id=item.budget_id,
                        project_id=item.project_id,
                        responsible_person=None,
                        db=db,
                    )
                    alerts.append(alert)
            elif any(kw in name for kw in fee_keywords):
                fee_threshold = Decimal("10000")
                if used > fee_threshold:
                    alert = await self._create_alert_record(
                        alert_level="黄色",
                        alert_type="L1专项",
                        l1_code="B9",
                        trigger_value=used,
                        threshold_value=fee_threshold,
                        deviation_rate=((used - fee_threshold) / fee_threshold * 100).quantize(Decimal("0.01")),
                        budget_id=item.budget_id,
                        project_id=item.project_id,
                        responsible_person=None,
                        db=db,
                    )
                    alerts.append(alert)

        return alerts

    def classify_alert_level(self, deviation_data: Dict[str, Any]) -> str:
        """Classify alert level based on deviation data.

        Args:
            deviation_data: Dict containing deviation metrics.

        Returns:
            Alert level string (蓝色/黄色/橙色/红色).
        """
        deviation_rate = Decimal(str(deviation_data.get("deviation_rate", 0)))
        is_over_budget = deviation_data.get("is_over_budget", False)
        is_single_large = deviation_data.get("is_single_large_deviation", False)

        if is_over_budget or is_single_large:
            return "红色"
        if deviation_rate > Decimal("30"):
            return "红色"
        if deviation_rate > Decimal("20"):
            return "橙色"
        if deviation_rate > Decimal("10"):
            return "黄色"
        return "蓝色"

    async def push_alert(self, alert_id: str, db: AsyncSession) -> None:
        """Push an alert to responsible person and start response timer.

        Routes based on alert level and starts the response countdown.

        Args:
            alert_id: Alert record ID.
            db: AsyncSession for database operations.
        """
        try:
            alert = await db.get(AlertRecord, alert_id)
            if alert is None:
                logger.warning(f"Alert {alert_id} not found for push")
                return

            alert.alert_status = "开放"
            alert.response_deadline = datetime.now() + timedelta(
                hours=ALERT_RESPONSE_HOURS.get(alert.alert_level, 72)
            )

            notification_targets = []
            if alert.alert_level in ("红色", "橙色"):
                notification_targets.append("center_gm")
                notification_targets.append("finance_bp")
            elif alert.alert_level == "黄色":
                notification_targets.append("finance_bp")
                notification_targets.append("dept_head")
            else:
                notification_targets.append("dept_head")

            alert.notification_targets = json.dumps(notification_targets, ensure_ascii=False)

            await db.flush()
            logger.info(f"Alert {alert_id} pushed, level={alert.alert_level}, targets={notification_targets}")

        except Exception as e:
            logger.error(f"Alert push failed for {alert_id}: {e}")

    async def respond_alert(
        self,
        alert_id: str,
        response: str,
        responder: str,
        db: AsyncSession,
    ) -> AlertClosure:
        """Business unit submits remediation plan for an alert.

        Creates a closure record with status "待BP确认".

        Args:
            alert_id: Alert record ID.
            response: Remediation plan text.
            responder: Name/ID of the responder.
            db: AsyncSession for database operations.

        Returns:
            Created AlertClosure record.

        Raises:
            ValueError: If alert not found or not in open/responding status.
        """
        try:
            # ── SoD：预警响应人 ≠ 预警闭环确认人（HR-013 双签底线） ──
            try:
                from ontology.sod import get_sod_enforcer, SoDViolation
                get_sod_enforcer().check(
                    user_id=str(responder),
                    operation="alert.respond",
                    resource_id=str(alert_id),
                )
            except SoDViolation:
                raise

            alert = await db.get(AlertRecord, alert_id)
            if alert is None:
                raise ValueError(f"Alert {alert_id} not found")
            if alert.alert_status not in ("开放", "响应中"):
                raise ValueError(f"Alert {alert_id} is in status {alert.alert_status}, cannot respond")

            alert.alert_status = "待闭环确认"

            closure = AlertClosure(
                closure_id=f"CL-{uuid.uuid4().hex[:8].upper()}",
                alert_id=alert_id,
                business_response=response,
                business_responder=responder,
                business_response_at=datetime.now(),
                closure_status="待BP确认",
                retention_period=3,
            )
            db.add(closure)
            await db.flush()

            logger.info(f"Alert {alert_id} responded by {responder}")
            from ontology.decision_record import DecisionActorType
            from ontology.decision_recorder import emit_decision

            await emit_decision(
                category="alert_respond",
                scenario=f"预警响应 {alert_id}",
                outcome="executed",
                reasoning="预警响应已提交，待财经BP确认",
                decision_maker=str(responder or "system"),
                actor_type=DecisionActorType.PERSON,
                entity_ids=[alert_id, closure.closure_id],
                applied_rule_ids=["HR-013"],
                hook_id="engine.respond_alert",
                metadata={"alert_id": alert_id},
                db=db,
            )
            return closure

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Alert response failed for {alert_id}: {e}")
            raise

    async def confirm_closure(
        self,
        closure_id: str,
        bp_confirmation: str,
        bp_confirmer: str,
        db: AsyncSession,
    ) -> AlertClosure:
        """Finance BP confirms remediation plan and closes the alert.

        Updates closure status to "已闭环" and archives for >= 3 years.

        Args:
            closure_id: Closure record ID.
            bp_confirmation: BP's confirmation opinion.
            bp_confirmer: Name/ID of the BP confirmer.
            db: AsyncSession for database operations.

        Returns:
            Updated AlertClosure record.

        Raises:
            ValueError: If closure not found or not in pending BP status.
        """
        try:
            # ── SoD：闭环确认人 ≠ 预警响应人（HR-013 双签底线） ──
            try:
                from ontology.sod import get_sod_enforcer, SoDViolation
                get_sod_enforcer().check(
                    user_id=str(bp_confirmer),
                    operation="alert.confirm_closure",
                    resource_id=str(closure_id),
                )
            except SoDViolation:
                raise

            closure = await db.get(AlertClosure, closure_id)
            if closure is None:
                raise ValueError(f"Closure {closure_id} not found")
            if closure.closure_status != "待BP确认":
                raise ValueError(
                    f"Closure {closure_id} is in status {closure.closure_status}, "
                    f"cannot confirm (requires 待BP确认)"
                )

            closure.bp_confirmation = bp_confirmation
            closure.bp_confirmer = bp_confirmer
            closure.bp_confirmation_at = datetime.now()
            closure.closure_status = "已闭环"
            closure.retention_period = max(closure.retention_period, 3)

            alert = await db.get(AlertRecord, closure.alert_id)
            if alert:
                alert.alert_status = "已闭环"

            await db.flush()

            logger.info(f"Alert closure {closure_id} confirmed by {bp_confirmer}")
            from ontology.decision_record import DecisionActorType
            from ontology.decision_recorder import emit_decision

            await emit_decision(
                category="alert_closure",
                scenario=f"预警闭环 {closure.alert_id}",
                outcome="executed",
                reasoning="财经BP确认整改方案，预警已闭环",
                decision_maker=str(bp_confirmer or "system"),
                actor_type=DecisionActorType.PERSON,
                entity_ids=[closure.alert_id, closure_id],
                applied_rule_ids=["HR-013"],
                hook_id="engine.confirm_closure",
                metadata={"alert_id": closure.alert_id},
                db=db,
            )
            return closure

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Closure confirmation failed for {closure_id}: {e}")
            raise

    async def escalate_alert(
        self, alert_id: str, db: AsyncSession
    ) -> AlertEscalation:
        """Escalate an alert due to timeout.

        Checks timeout thresholds: blue 3 days, yellow 2 days, orange 1 day, red immediate.
        Creates escalation record and notifies superior.

        Args:
            alert_id: Alert record ID.
            db: AsyncSession for database operations.

        Returns:
            Created AlertEscalation record.

        Raises:
            ValueError: If alert not found or not eligible for escalation.
        """
        try:
            alert = await db.get(AlertRecord, alert_id)
            if alert is None:
                raise ValueError(f"Alert {alert_id} not found")

            now = datetime.now()
            timeout_days = ESCALATION_TIMEOUT_DAYS.get(alert.alert_level, 3)

            if alert.response_deadline and now < alert.response_deadline:
                elapsed_hours = (now - (alert.response_deadline - timedelta(hours=ALERT_RESPONSE_HOURS.get(alert.alert_level, 72)))).total_seconds() / 3600
                if elapsed_hours < timeout_days * 24 and alert.alert_level != "红色":
                    raise ValueError(
                        f"Alert {alert_id} not yet eligible for escalation "
                        f"(timeout: {timeout_days} days for {alert.alert_level})"
                    )

            escalation = AlertEscalation(
                escalation_id=f"ES-{uuid.uuid4().hex[:8].upper()}",
                alert_id=alert_id,
                escalation_reason="超时未响应" if alert.alert_status == "开放" else "超时未闭环",
                escalation_level="上级管理层",
                escalation_target="center_gm" if alert.alert_level in ("红色", "橙色") else "dept_head",
                original_deadline=alert.response_deadline,
                escalation_at=now,
                is_performance_impact=alert.alert_level in ("红色", "橙色"),
            )
            db.add(escalation)

            alert.alert_status = "已升级"

            await db.flush()

            logger.warning(f"Alert {alert_id} escalated: level={alert.alert_level}")
            from ontology.decision_recorder import emit_decision

            await emit_decision(
                category="alert_escalate",
                scenario=f"预警升级 {alert_id}",
                outcome="executed",
                reasoning=escalation.escalation_reason,
                decision_maker="system",
                entity_ids=[alert_id, escalation.escalation_id],
                applied_rule_ids=["HR-012"],
                hook_id="engine.escalate_alert",
                metadata={"alert_id": alert_id, "level": alert.alert_level},
                db=db,
            )
            return escalation

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Alert escalation failed for {alert_id}: {e}")
            raise

    async def auto_escalate_timeout_alerts(self, db: AsyncSession) -> List[AlertEscalation]:
        """Auto-escalate alerts that have exceeded their response deadline.

        Scans all open/responding alerts and escalates those past deadline.
        This should be called by a scheduled task (e.g., hourly).

        Args:
            db: AsyncSession for database operations.

        Returns:
            List of created AlertEscalation records.
        """
        try:
            now = datetime.now()
            escalated: List[AlertEscalation] = []

            stmt = select(AlertRecord).where(
                AlertRecord.alert_status.in_(["开放", "响应中", "待闭环确认"])
            )
            result = await db.execute(stmt)
            open_alerts = result.scalars().all()

            for alert in open_alerts:
                if alert.response_deadline and now > alert.response_deadline:
                    try:
                        escalation = await self.escalate_alert(alert.alert_id, db)
                        escalated.append(escalation)
                    except ValueError:
                        pass

            if escalated:
                logger.info(f"Auto-escalated {len(escalated)} timeout alerts")

            return escalated

        except Exception as e:
            logger.error(f"Auto-escalation scan failed: {e}")
            raise

    async def predictive_scan(self, db: AsyncSession) -> List[AlertRecord]:
        """Predictive alert scan using linear regression on usage trends.

        For each budget item with at least 3 months of usage data:
        - Query ExpenseReport table for monthly usage amounts
        - Calculate 3-month moving average
        - Perform linear regression (least squares) on last 3 months
        - Apply seasonal adjustment (quarterly factors)
        - Project end-of-year usage with trend + seasonality
        - If projected > annual_amount: generate orange "预测超支" alert
        - If projected < annual_amount * 0.5: generate blue "资源闲置" alert

        Args:
            db: AsyncSession for database operations.

        Returns:
            List of generated AlertRecord objects.
        """
        try:
            all_alerts: List[AlertRecord] = []

            stmt = select(BudgetItem).where(
                BudgetItem.status.in_(["已授予", "执行中"])
            )
            result = await db.execute(stmt)
            budget_items = result.scalars().all()

            now = datetime.now()
            current_month = now.month
            remaining_months = 12 - current_month

            if remaining_months <= 0:
                return all_alerts

            # 季度因子：Q1=0.9, Q2=1.0, Q3=1.0, Q4=1.1
            quarter_factors = {1: 0.9, 2: 1.0, 3: 1.0, 4: 1.1}

            for item in budget_items:
                annual = Decimal(str(item.annual_amount))
                used = Decimal(str(item.used_amount))

                if annual <= 0:
                    continue

                months_elapsed = current_month
                if months_elapsed < 3:
                    continue

                # 从ExpenseReport表按月分组查询核销金额
                monthly_usages: List[float] = []
                try:
                    from models.expense import ExpenseReport
                    for m_offset in range(min(3, months_elapsed)):
                        target_month = current_month - m_offset
                        target_year = now.year
                        if target_month <= 0:
                            target_month += 12
                            target_year -= 1
                        stmt_exp = select(func.coalesce(func.sum(ExpenseReport.amount), 0)).where(
                            and_(
                                ExpenseReport.budget_id == item.budget_id,
                                ExpenseReport.status == "已核销",
                                extract("year", ExpenseReport.created_at) == target_year,
                                extract("month", ExpenseReport.created_at) == target_month,
                            )
                        )
                        res_exp = await db.execute(stmt_exp)
                        month_total = float(res_exp.scalar() or 0)
                        monthly_usages.append(month_total)

                    # 月份从旧到新排列
                    monthly_usages.reverse()
                except Exception as e:
                    logger.debug(f"[PredictiveScan] ExpenseReport query failed for {item.budget_id}: {e}")
                    monthly_usages = []

                # 计算月度平均使用量
                if len(monthly_usages) >= 3:
                    # 3个月移动平均
                    moving_avg = sum(monthly_usages) / len(monthly_usages)
                else:
                    # 回退到简单除法
                    moving_avg = float(used) / months_elapsed

                # 线性回归（最小二乘法）计算趋势
                slope = 0.0
                if len(monthly_usages) >= 3:
                    n = len(monthly_usages)
                    x_vals = list(range(n))
                    y_vals = monthly_usages
                    x_mean = sum(x_vals) / n
                    y_mean = sum(y_vals) / n
                    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, y_vals))
                    denominator = sum((x - x_mean) ** 2 for x in x_vals)
                    if denominator != 0:
                        slope = numerator / denominator

                # 用趋势预测年末使用量
                trend_projected = float(used) + (moving_avg + slope) * remaining_months

                # 季节性调整
                current_quarter = (current_month - 1) // 3 + 1
                seasonal_factor = quarter_factors.get(current_quarter, 1.0)
                projected = trend_projected * seasonal_factor

                # 预测结果元数据
                prediction_meta = {
                    "budget_id": item.budget_id,
                    "l1_code": item.l1_code,
                    "annual_amount": float(annual),
                    "current_used": float(used),
                    "monthly_usages": monthly_usages,
                    "moving_avg": round(moving_avg, 2),
                    "slope": round(slope, 2),
                    "trend_projected": round(trend_projected, 2),
                    "seasonal_factor": seasonal_factor,
                    "final_projected": round(projected, 2),
                    "remaining_months": remaining_months,
                }

                projected_decimal = Decimal(str(round(projected, 2)))

                if projected_decimal > annual:
                    # 预测超支
                    deviation = ((projected_decimal - annual) / annual * 100).quantize(Decimal("0.01"))
                    alert = await self._create_alert_record(
                        alert_level="橙色",
                        alert_type="预测超支",
                        l1_code=item.l1_code,
                        trigger_value=projected_decimal.quantize(Decimal("0.01")),
                        threshold_value=annual,
                        deviation_rate=deviation,
                        budget_id=item.budget_id,
                        project_id=item.project_id,
                        responsible_person=None,
                        db=db,
                    )
                    # 写入预测元数据
                    if alert and hasattr(alert, 'notification_targets'):
                        try:
                            existing_meta = {}
                            if alert.notification_targets:
                                existing_meta = json.loads(alert.notification_targets)
                            existing_meta["prediction"] = prediction_meta
                            alert.notification_targets = json.dumps(existing_meta, ensure_ascii=False)
                            await db.flush()
                        except Exception:
                            pass
                    all_alerts.append(alert)

                elif projected_decimal < annual * Decimal("0.5"):
                    # 资源闲置
                    deviation = ((annual * Decimal("0.5") - projected_decimal) / (annual * Decimal("0.5")) * 100).quantize(Decimal("0.01"))
                    alert = await self._create_alert_record(
                        alert_level="蓝色",
                        alert_type="资源闲置",
                        l1_code=item.l1_code,
                        trigger_value=projected_decimal.quantize(Decimal("0.01")),
                        threshold_value=(annual * Decimal("0.5")).quantize(Decimal("0.01")),
                        deviation_rate=deviation,
                        budget_id=item.budget_id,
                        project_id=item.project_id,
                        responsible_person=None,
                        db=db,
                    )
                    if alert and hasattr(alert, 'notification_targets'):
                        try:
                            existing_meta = {}
                            if alert.notification_targets:
                                existing_meta = json.loads(alert.notification_targets)
                            existing_meta["prediction"] = prediction_meta
                            alert.notification_targets = json.dumps(existing_meta, ensure_ascii=False)
                            await db.flush()
                        except Exception:
                            pass
                    all_alerts.append(alert)

            if all_alerts:
                logger.info(f"Predictive scan complete: {len(all_alerts)} alerts generated")

            return all_alerts

        except Exception as e:
            logger.error(f"Predictive scan failed: {e}")
            raise

    async def cascade_risk_assess(
        self,
        l1_code: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Cascade risk assessment: when an L1 subject triggers a red alert,
        evaluate连锁风险 on related L2 subjects and strategic intent directions.

        Args:
            l1_code: L1 subject code that triggered the alert.
            db: AsyncSession for database operations.

        Returns:
            Dict with cascade risk assessment results.
        """
        try:
            # 1. Get all budget items under this L1
            stmt = select(BudgetItem).where(
                and_(
                    BudgetItem.l1_code == l1_code,
                    BudgetItem.status.in_(["已授予", "执行中"]),
                )
            )
            result = await db.execute(stmt)
            items = result.scalars().all()

            if not items:
                return {"l1_code": l1_code, "error": "未找到相关预算项目", "cascade_risks": []}

            total_annual = sum(Decimal(str(i.annual_amount)) for i in items)
            total_used = sum(Decimal(str(i.used_amount)) for i in items)
            overall_rate = (total_used / total_annual * 100) if total_annual > 0 else Decimal("0")

            # 2. Assess L2 cascade risks
            l2_risks = []
            by_l2: Dict[str, List] = {}
            for item in items:
                l2 = item.l2_code or "未分类"
                by_l2.setdefault(l2, []).append(item)

            for l2, l2_items in by_l2.items():
                l2_annual = sum(Decimal(str(i.annual_amount)) for i in l2_items)
                l2_used = sum(Decimal(str(i.used_amount)) for i in l2_items)
                l2_rate = (l2_used / l2_annual * 100) if l2_annual > 0 else Decimal("0")

                risk_level = "低"
                if l2_rate > Decimal("100"):
                    risk_level = "高"
                elif l2_rate > Decimal("90"):
                    risk_level = "中"

                l2_risks.append({
                    "l2_code": l2,
                    "item_count": len(l2_items),
                    "annual_amount": float(l2_annual),
                    "used_amount": float(l2_used),
                    "execution_rate": float(l2_rate.quantize(Decimal("0.01"))),
                    "risk_level": risk_level,
                    "recommendation": (
                        f"L2科目{l2}执行率{l2_rate:.1f}%，"
                        + ("已超预算，需立即管控" if l2_rate > 100
                           else "接近预算上限，需加强监控" if l2_rate > 90
                           else "执行正常")
                    ),
                })

            # 3. Assess strategic intent cascade risks
            strategic_risks = []
            by_intent: Dict[str, List] = {}
            for item in items:
                intent = item.strategic_intent_l1 or "未关联"
                by_intent.setdefault(intent, []).append(item)

            for intent, intent_items in by_intent.items():
                intent_annual = sum(Decimal(str(i.annual_amount)) for i in intent_items)
                intent_used = sum(Decimal(str(i.used_amount)) for i in intent_items)
                intent_rate = (intent_used / intent_annual * 100) if intent_annual > 0 else Decimal("0")

                # Check quadrant distribution
                quadrant_dist = {}
                for item in intent_items:
                    q = item.quadrant
                    quadrant_dist[q] = quadrant_dist.get(q, 0) + 1

                risk_level = "低"
                if intent_rate > Decimal("100"):
                    risk_level = "高"
                elif intent_rate > Decimal("90") or (intent_rate < Decimal("30") and intent == "未关联"):
                    risk_level = "中"

                strategic_risks.append({
                    "strategic_intent": intent,
                    "item_count": len(intent_items),
                    "annual_amount": float(intent_annual),
                    "used_amount": float(intent_used),
                    "execution_rate": float(intent_rate.quantize(Decimal("0.01"))),
                    "quadrant_distribution": quadrant_dist,
                    "risk_level": risk_level,
                    "recommendation": (
                        f"战略方向「{intent}」执行率{intent_rate:.1f}%，"
                        + ("已超预算，需评估是否调整战略" if intent_rate > 100
                           else "接近预算上限" if intent_rate > 90
                           else "执行率偏低，需加速推进" if intent_rate < 50
                           else "执行正常")
                    ),
                })

            # 4. Assess quadrant cascade risks
            quadrant_risks = []
            by_quadrant: Dict[str, List] = {}
            for item in items:
                q = item.quadrant
                by_quadrant.setdefault(q, []).append(item)

            expected_rates = {"发展": 80, "收缩": 40, "稳定": 60, "探索": 50}
            for quadrant, q_items in by_quadrant.items():
                q_annual = sum(Decimal(str(i.annual_amount)) for i in q_items)
                q_used = sum(Decimal(str(i.used_amount)) for i in q_items)
                q_rate = (q_used / q_annual * 100) if q_annual > 0 else Decimal("0")
                expected = expected_rates.get(quadrant, 60)
                deviation = float(q_rate) - expected

                risk_level = "低"
                if abs(deviation) > 30:
                    risk_level = "高"
                elif abs(deviation) > 15:
                    risk_level = "中"

                quadrant_risks.append({
                    "quadrant": quadrant,
                    "item_count": len(q_items),
                    "annual_amount": float(q_annual),
                    "used_amount": float(q_used),
                    "execution_rate": float(q_rate.quantize(Decimal("0.01"))),
                    "expected_rate": expected,
                    "deviation": round(deviation, 2),
                    "risk_level": risk_level,
                    "recommendation": (
                        f"{quadrant}象限执行率{q_rate:.1f}%（预期{expected}%），"
                        + ("偏离过大，需评估战略调整" if abs(deviation) > 30
                           else "存在偏差，需关注" if abs(deviation) > 15
                           else "符合预期")
                    ),
                })

            # 5. Overall cascade risk summary
            high_risk_count = (
                sum(1 for r in l2_risks if r["risk_level"] == "高")
                + sum(1 for r in strategic_risks if r["risk_level"] == "高")
                + sum(1 for r in quadrant_risks if r["risk_level"] == "高")
            )
            medium_risk_count = (
                sum(1 for r in l2_risks if r["risk_level"] == "中")
                + sum(1 for r in strategic_risks if r["risk_level"] == "中")
                + sum(1 for r in quadrant_risks if r["risk_level"] == "中")
            )

            overall_cascade_risk = "低"
            if high_risk_count >= 2:
                overall_cascade_risk = "高"
            elif high_risk_count >= 1 or medium_risk_count >= 3:
                overall_cascade_risk = "中"

            await self._record_trace(
                scene_name="级联风险评估",
                input_data={"l1_code": l1_code},
                steps=[
                    {"step": "assess_l2", "count": len(l2_risks)},
                    {"step": "assess_strategic", "count": len(strategic_risks)},
                    {"step": "assess_quadrant", "count": len(quadrant_risks)},
                ],
                conclusion=f"Cascade risk for L1 {l1_code}: {overall_cascade_risk} ({high_risk_count} high, {medium_risk_count} medium)",
                rule_ids=["SR-CASCADE"],
                confidence=Decimal("80.00"),
                db=db,
            )

            logger.info(f"Cascade risk assessment complete for L1 {l1_code}: {overall_cascade_risk}")

            return {
                "l1_code": l1_code,
                "overall_rate": float(overall_rate.quantize(Decimal("0.01"))),
                "overall_cascade_risk": overall_cascade_risk,
                "high_risk_count": high_risk_count,
                "medium_risk_count": medium_risk_count,
                "l2_risks": l2_risks,
                "strategic_risks": strategic_risks,
                "quadrant_risks": quadrant_risks,
            }

        except Exception as e:
            logger.error(f"Cascade risk assessment failed for L1 {l1_code}: {e}")
            raise

    async def alert_pattern_analysis(
        self,
        l1_code: Optional[str],
        db: AsyncSession,
        lookback_months: int = 6,
    ) -> Dict[str, Any]:
        """Analyze historical alert patterns to identify systemic vs sporadic issues.

        Args:
            l1_code: Optional L1 code to filter (if None, analyze all).
            db: AsyncSession for database operations.
            lookback_months: Number of months to look back (default 6).

        Returns:
            Dict with pattern analysis results.
        """
        try:
            cutoff = datetime.now() - timedelta(days=lookback_months * 30)
            stmt = select(AlertRecord).where(AlertRecord.created_at >= cutoff)
            if l1_code:
                stmt = stmt.where(AlertRecord.l1_code == l1_code)
            result = await db.execute(stmt)
            alerts = result.scalars().all()

            if not alerts:
                return {
                    "l1_code": l1_code,
                    "lookback_months": lookback_months,
                    "error": "无历史预警数据",
                    "patterns": [],
                }

            # 1. Group by alert_type
            by_type: Dict[str, List] = {}
            for alert in alerts:
                atype = alert.alert_type or "未知"
                by_type.setdefault(atype, []).append(alert)

            # 2. Group by l1_code
            by_l1: Dict[str, List] = {}
            for alert in alerts:
                l1 = alert.l1_code or "未分类"
                by_l1.setdefault(l1, []).append(alert)

            # 3. Identify patterns
            patterns = []

            # Pattern: recurring type (same type appears >= 3 times)
            for atype, type_alerts in by_type.items():
                if len(type_alerts) >= 3:
                    # Check if it's systemic (spans multiple L1 codes)
                    affected_l1s = set(a.l1_code for a in type_alerts if a.l1_code)
                    is_systemic = len(affected_l1s) >= 2

                    # Average response time
                    response_times = []
                    for a in type_alerts:
                        if a.created_at and a.response_deadline:
                            hours = ALERT_RESPONSE_HOURS.get(a.alert_level, 72)
                            response_times.append(hours)

                    avg_response_hours = sum(response_times) / len(response_times) if response_times else 0

                    # Closure rate
                    closed = sum(1 for a in type_alerts if a.alert_status == "已闭环")
                    closure_rate = (closed / len(type_alerts) * 100) if type_alerts else 0

                    patterns.append({
                        "pattern_type": "反复出现",
                        "alert_type": atype,
                        "occurrence_count": len(type_alerts),
                        "is_systemic": is_systemic,
                        "affected_l1_codes": list(affected_l1s),
                        "avg_response_hours": round(avg_response_hours, 1),
                        "closure_rate": round(closure_rate, 1),
                        "severity": "系统性问题" if is_systemic else "局部反复",
                        "recommendation": (
                            f"「{atype}」类预警反复出现{len(type_alerts)}次，"
                            + ("属于系统性问题，建议从流程层面改进" if is_systemic
                               else "集中在特定科目，建议针对性管控")
                        ),
                    })

            # Pattern: escalation-prone (high escalation rate)
            for l1, l1_alerts in by_l1.items():
                escalated = sum(1 for a in l1_alerts if a.alert_status == "已升级")
                escalation_rate = (escalated / len(l1_alerts) * 100) if l1_alerts else 0
                if escalation_rate > 30:
                    patterns.append({
                        "pattern_type": "易升级",
                        "l1_code": l1,
                        "total_alerts": len(l1_alerts),
                        "escalated_count": escalated,
                        "escalation_rate": round(escalation_rate, 1),
                        "severity": "响应效率问题",
                        "recommendation": f"L1科目{l1}的预警升级率达{escalation_rate:.1f}%，响应效率需改善",
                    })

            # Pattern: level distribution
            level_dist = {"蓝色": 0, "黄色": 0, "橙色": 0, "红色": 0}
            for alert in alerts:
                level = alert.alert_level
                if level in level_dist:
                    level_dist[level] += 1

            total_alerts = len(alerts)
            high_level_ratio = (level_dist["红色"] + level_dist["橙色"]) / total_alerts * 100 if total_alerts > 0 else 0

            if high_level_ratio > 50:
                patterns.append({
                    "pattern_type": "高级别占比过高",
                    "level_distribution": level_dist,
                    "high_level_ratio": round(high_level_ratio, 1),
                    "severity": "风险集中",
                    "recommendation": f"高级别预警(橙+红)占比{high_level_ratio:.1f}%，整体风险集中度偏高",
                })

            # Summary statistics
            closed_count = sum(1 for a in alerts if a.alert_status == "已闭环")
            open_count = sum(1 for a in alerts if a.alert_status in ("开放", "响应中"))

            await self._record_trace(
                scene_name="预警模式分析",
                input_data={"l1_code": l1_code, "lookback_months": lookback_months},
                steps=[
                    {"step": "load_alerts", "count": len(alerts)},
                    {"step": "group_by_type", "types": len(by_type)},
                    {"step": "identify_patterns", "patterns": len(patterns)},
                ],
                conclusion=f"Alert pattern analysis: {len(patterns)} patterns identified from {len(alerts)} alerts",
                rule_ids=["SR-PATTERN"],
                confidence=Decimal("75.00"),
                db=db,
            )

            logger.info(f"Alert pattern analysis complete: {len(patterns)} patterns from {len(alerts)} alerts")

            return {
                "l1_code": l1_code,
                "lookback_months": lookback_months,
                "total_alerts": total_alerts,
                "closed_count": closed_count,
                "open_count": open_count,
                "overall_closure_rate": round(closed_count / total_alerts * 100, 1) if total_alerts > 0 else 0,
                "level_distribution": level_dist,
                "type_distribution": {k: len(v) for k, v in by_type.items()},
                "patterns": patterns,
            }

        except Exception as e:
            logger.error(f"Alert pattern analysis failed: {e}")
            raise

    # === v4.1 新增：5 层根因下钻 + 疲劳度分析 ===

    async def drill_down_alert(
        self, alert_id: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """预警 5 层根因下钻

        L1: 哪个 L1 科目
        L2: 哪个 L2 子科目
        Center: 哪个中心
        Trend: 本季 vs 上季趋势
        Peer: 同象限其他科目表现
        """
        try:
            alert = await self._get_alert(alert_id, db)
            if not alert:
                return {"error": "预警不存在", "alert_id": alert_id}

            l1_node = await self._drill_l1(alert, db)
            l2_node = await self._drill_l2(alert, db)
            center_node = await self._drill_center(alert, db)
            trend_node = await self._drill_trend(alert, db)
            peer_node = await self._drill_peer(alert, db)

            ai_root_cause = self._build_root_cause_summary({
                "alert": alert, "l1": l1_node, "l2": l2_node,
                "center": center_node, "trend": trend_node, "peer": peer_node,
            })

            return {
                "alert_id": alert_id,
                "period": alert.get("period"),
                "alert_level": alert.get("alert_level"),
                "alert_type": alert.get("alert_type"),
                "l1_node": l1_node,
                "l2_node": l2_node,
                "center_node": center_node,
                "trend_node": trend_node,
                "peer_node": peer_node,
                "ai_root_cause": ai_root_cause,
                "generated_at": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"[drill_down_alert] 失败: {e}")
            return {"error": str(e), "alert_id": alert_id}

    async def _get_alert(self, alert_id: str, db: AsyncSession) -> Optional[Dict[str, Any]]:
        """获取预警详情"""
        try:
            stmt = select(AlertRecord).where(AlertRecord.alert_id == alert_id)
            result = await db.execute(stmt)
            a = result.scalar_one_or_none()
            if not a:
                return None
            return {
                "alert_id": a.alert_id,
                "alert_level": a.alert_level,
                "alert_type": a.alert_type,
                "alert_status": a.alert_status,
                "l1_code": a.l1_code,
                "l2_code": a.l2_code,
                "l3_code": a.l3_code,
                "budget_id": a.budget_id,
                "project_id": a.project_id,
                "trigger_value": float(a.trigger_value or 0),
                "threshold_value": float(a.threshold_value or 0),
                "deviation_rate": float(a.deviation_rate or 0),
                "responsible_person": a.responsible_person,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                # 用于季度对比
                "period": a.created_at.strftime("%Y-%m") if a.created_at else None,
            }
        except Exception as e:
            logger.warning(f"[_get_alert] 失败: {e}")
            return None

    async def _drill_l1(self, alert: Dict[str, Any], db: AsyncSession) -> Dict[str, Any]:
        """L1 层级：返回 alert 所在 L1 科目 + 历史告警频次"""
        l1 = alert.get("l1_code")
        result: Dict[str, Any] = {"l1_code": l1, "subject_name": None, "alert_count_30d": 0, "current_rate": None}
        if not l1:
            return result
        try:
            # 历史 30 天告警频次
            cutoff = datetime.now() - timedelta(days=30)
            stmt = select(func.count(AlertRecord.alert_id)).where(
                and_(
                    AlertRecord.l1_code == l1,
                    AlertRecord.created_at >= cutoff,
                )
            )
            r = await db.execute(stmt)
            cnt = r.scalar() or 0
            result["alert_count_30d"] = int(cnt)

            # 关联预算项
            stmt2 = select(BudgetItem).where(BudgetItem.l1_code == l1).limit(1)
            r2 = await db.execute(stmt2)
            item = r2.scalar_one_or_none()
            if item:
                result["subject_name"] = item.budget_name
                annual = float(item.annual_amount or 0)
                used = float(item.used_amount or 0)
                if annual > 0:
                    result["current_rate"] = round(used / annual * 100.0, 2)
        except Exception as e:
            logger.warning(f"[_drill_l1] 失败: {e}")
        return result

    async def _drill_l2(self, alert: Dict[str, Any], db: AsyncSession) -> Dict[str, Any]:
        """L2 层级：返回该 L1 下各 L2 的执行率 + 偏差排名"""
        l1 = alert.get("l1_code")
        result: Dict[str, Any] = {"items": [], "ranking": []}
        if not l1:
            return result
        try:
            stmt = select(BudgetItem).where(BudgetItem.l1_code == l1)
            r = await db.execute(stmt)
            items = r.scalars().all()
            enriched = []
            for it in items:
                annual = float(it.annual_amount or 0)
                used = float(it.used_amount or 0)
                rate = round(used / annual * 100.0, 2) if annual > 0 else 0.0
                enriched.append({
                    "budget_id": it.budget_id,
                    "name": it.budget_name,
                    "l2_code": it.l2_code,
                    "annual_amount": annual,
                    "used_amount": used,
                    "rate": rate,
                })
            enriched.sort(key=lambda x: abs(x["rate"] - 50.0), reverse=True)
            result["items"] = enriched[:5]  # Top 5 偏差最大
            result["ranking"] = [
                {"budget_id": x["budget_id"], "name": x["name"], "rate": x["rate"]}
                for x in enriched[:5]
            ]
        except Exception as e:
            logger.warning(f"[_drill_l2] 失败: {e}")
        return result

    async def _drill_center(self, alert: Dict[str, Any], db: AsyncSession) -> Dict[str, Any]:
        """中心维度：各中心的执行率 + 偏差排名"""
        result: Dict[str, Any] = {"centers": [], "ranking": []}
        try:
            l1 = alert.get("l1_code")
            stmt = select(
                BudgetItem.center_id,
                func.sum(BudgetItem.annual_amount).label("total_annual"),
                func.sum(BudgetItem.used_amount).label("total_used"),
                func.count(BudgetItem.budget_id).label("cnt"),
            ).group_by(BudgetItem.center_id)
            if l1:
                stmt = stmt.where(BudgetItem.l1_code == l1)
            r = await db.execute(stmt)
            rows = r.all()
            centers = []
            for row in rows:
                annual = float(row.total_annual or 0)
                used = float(row.total_used or 0)
                rate = round(used / annual * 100.0, 2) if annual > 0 else 0.0
                centers.append({
                    "center_id": row.center_id or "未分配",
                    "total_annual": annual,
                    "total_used": used,
                    "item_count": int(row.cnt or 0),
                    "rate": rate,
                })
            centers.sort(key=lambda x: x["rate"], reverse=True)
            result["centers"] = centers
            result["ranking"] = [{"center_id": c["center_id"], "rate": c["rate"]} for c in centers[:5]]
        except Exception as e:
            logger.warning(f"[_drill_center] 失败: {e}")
        return result

    async def _drill_trend(self, alert: Dict[str, Any], db: AsyncSession) -> Dict[str, Any]:
        """趋势维度：本季 vs 上季，3 维度（执行率/超支/进度）"""
        result: Dict[str, Any] = {
            "this_quarter": {"period": alert.get("period"), "metrics": {}},
            "last_quarter": {"period": None, "metrics": {}},
            "delta": {},
        }
        try:
            current_period = alert.get("period", datetime.now().strftime("%Y-%m"))
            # 简单取上季：月份减 3
            try:
                dt = datetime.strptime(current_period, "%Y-%m")
                prev_dt = dt - timedelta(days=90)
                prev_period = prev_dt.strftime("%Y-%m")
            except Exception:
                prev_period = current_period

            for label, period in [("this_quarter", current_period), ("last_quarter", prev_period)]:
                stmt = select(
                    func.count(AlertRecord.alert_id).label("alert_count"),
                    func.avg(AlertRecord.deviation_rate).label("avg_deviation"),
                )
                stmt = stmt.where(AlertRecord.created_at.like(f"{period}%"))
                r = await db.execute(stmt)
                row = r.one()
                result[label]["period"] = period
                result[label]["metrics"] = {
                    "alert_count": int(row.alert_count or 0),
                    "avg_deviation": round(float(row.avg_deviation or 0), 2),
                }

            this_m = result["this_quarter"]["metrics"]
            last_m = result["last_quarter"]["metrics"]
            result["delta"] = {
                "alert_count_delta": this_m.get("alert_count", 0) - last_m.get("alert_count", 0),
                "avg_deviation_delta": round(
                    this_m.get("avg_deviation", 0) - last_m.get("avg_deviation", 0), 2
                ),
            }
        except Exception as e:
            logger.warning(f"[_drill_trend] 失败: {e}")
        return result

    async def _drill_peer(self, alert: Dict[str, Any], db: AsyncSession) -> Dict[str, Any]:
        """同类对标：同象限其他科目的平均执行率 + 偏差"""
        result: Dict[str, Any] = {"quadrant": None, "peer_avg": None, "deviation": None, "peers": []}
        try:
            l1 = alert.get("l1_code")
            if not l1:
                return result
            # 获取本 L1 的象限
            stmt = select(BudgetItem).where(BudgetItem.l1_code == l1).limit(1)
            r = await db.execute(stmt)
            ref = r.scalar_one_or_none()
            if not ref:
                return result
            quadrant = ref.quadrant
            result["quadrant"] = quadrant

            # 同象限其他 L1
            stmt2 = select(
                BudgetItem.l1_code,
                func.sum(BudgetItem.annual_amount).label("annual"),
                func.sum(BudgetItem.used_amount).label("used"),
            ).where(
                and_(BudgetItem.quadrant == quadrant, BudgetItem.l1_code != l1)
            ).group_by(BudgetItem.l1_code)
            r2 = await db.execute(stmt2)
            peers = r2.all()
            peer_rates = []
            for p in peers:
                annual = float(p.annual or 0)
                used = float(p.used or 0)
                rate = round(used / annual * 100.0, 2) if annual > 0 else 0.0
                peer_rates.append({"l1_code": p.l1_code, "rate": rate})
                result["peers"].append({"l1_code": p.l1_code, "rate": rate})

            if peer_rates:
                peer_avg = sum(p["rate"] for p in peer_rates) / len(peer_rates)
                result["peer_avg"] = round(peer_avg, 2)
                # 当前 alert 所在 L1 的 rate
                cur_stmt = select(
                    func.sum(BudgetItem.annual_amount).label("annual"),
                    func.sum(BudgetItem.used_amount).label("used"),
                ).where(BudgetItem.l1_code == l1)
                cur_r = await db.execute(cur_stmt)
                cur_row = cur_r.one()
                cur_annual = float(cur_row.annual or 0)
                cur_used = float(cur_row.used or 0)
                cur_rate = round(cur_used / cur_annual * 100.0, 2) if cur_annual > 0 else 0.0
                result["deviation"] = round(cur_rate - peer_avg, 2)
                result["current_rate"] = cur_rate
        except Exception as e:
            logger.warning(f"[_drill_peer] 失败: {e}")
        return result

    def _build_root_cause_summary(self, nodes: Dict[str, Any]) -> str:
        """AI 根因总结（模板回退）"""
        try:
            alert = nodes.get("alert", {})
            l1 = nodes.get("l1", {})
            trend = nodes.get("trend", {})
            peer = nodes.get("peer", {})

            parts = []
            l1_name = l1.get("subject_name") or l1.get("l1_code") or "未知科目"
            level = alert.get("alert_level", "蓝色")
            atype = alert.get("alert_type", "")
            deviation = alert.get("deviation_rate", 0)

            parts.append(f"【{level}级{atype}】触发于 {l1_name}，偏离率 {deviation}%")

            # L1 频次
            if l1.get("alert_count_30d", 0) > 3:
                parts.append(f"近 30 天该 L1 已触发 {l1['alert_count_30d']} 次预警，属高频预警科目")
            elif l1.get("alert_count_30d", 0) > 0:
                parts.append(f"近 30 天该 L1 累计触发 {l1['alert_count_30d']} 次预警")

            # 趋势
            delta = trend.get("delta", {})
            if delta.get("alert_count_delta", 0) > 0:
                parts.append(
                    f"较上季预警数增加 {delta['alert_count_delta']} 次，平均偏离率上升 {delta.get('avg_deviation_delta', 0)}pp"
                )
            elif delta.get("alert_count_delta", 0) < 0:
                parts.append(f"较上季预警数减少 {abs(delta['alert_count_delta'])} 次，趋势改善")

            # 同类对标
            if peer.get("deviation") is not None:
                if peer["deviation"] > 5:
                    parts.append(
                        f"同象限其他 L1 平均执行率 {peer['peer_avg']}%，本 L1 偏离 +{peer['deviation']}pp，需优先治理"
                    )
                elif peer["deviation"] < -5:
                    parts.append(
                        f"同象限其他 L1 平均执行率 {peer['peer_avg']}%，本 L1 执行偏慢 {abs(peer['deviation'])}pp"
                    )
                else:
                    parts.append(f"同象限其他 L1 平均执行率 {peer['peer_avg']}%，本 L1 处于正常区间")

            parts.append(f"建议：① 召开 {l1_name} 专项复盘会；② 检视同象限调拨合理性；③ 强化 {l1.get('l1_code', '')} 责任人的执行跟进。")
            return "；".join(parts)
        except Exception as e:
            logger.warning(f"[_build_root_cause_summary] 失败: {e}")
            return "AI 根因总结生成失败"

    async def analyze_alert_fatigue(
        self, db: AsyncSession, months: int = 3
    ) -> Dict[str, Any]:
        """预警疲劳度分析（近 N 月）

        - 同类预警频次
        - 同类预警未闭环率
        - 用户响应时长 P50/P75/P90
        - 预警有效性（触发后是否真发生问题）
        - 建议：合并/降级/取消
        """
        try:
            metrics = await self._calc_fatigue_metrics(db, months)
            suggestions = self._generate_fatigue_suggestions(metrics)
            return {
                "months": months,
                "metrics": metrics,
                "suggestions": suggestions,
                "generated_at": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"[analyze_alert_fatigue] 失败: {e}")
            return {
                "months": months,
                "metrics": {},
                "suggestions": [],
                "error": str(e),
            }

    async def _calc_fatigue_metrics(
        self, db: AsyncSession, months: int
    ) -> Dict[str, Any]:
        """计算疲劳度指标"""
        try:
            cutoff = datetime.now() - timedelta(days=months * 30)

            # 1. 频次 + 未闭环率
            stmt = select(AlertRecord)
            r = await db.execute(stmt)
            all_alerts = r.scalars().all()
            recent = [a for a in all_alerts if a.created_at and a.created_at >= cutoff]
            if not recent:
                return {
                    "total_alerts": 0,
                    "open_alerts": 0,
                    "open_rate": 0.0,
                    "frequency_by_type": {},
                    "open_rate_by_type": {},
                    "response_hours": {"p50": 0, "p75": 0, "p90": 0},
                    "effectiveness": 0.0,
                }
            open_alerts = [a for a in recent if a.alert_status in ("开放", "响应中")]
            type_freq: Dict[str, int] = {}
            type_open: Dict[str, int] = {}
            for a in recent:
                t = a.alert_type
                type_freq[t] = type_freq.get(t, 0) + 1
                if a.alert_status in ("开放", "响应中"):
                    type_open[t] = type_open.get(t, 0) + 1

            frequency_by_type = dict(sorted(type_freq.items(), key=lambda x: x[1], reverse=True))
            open_rate_by_type = {
                t: round(type_open.get(t, 0) / freq * 100.0, 1)
                for t, freq in type_freq.items()
            }

            # 2. 响应时长分位数
            response_durations = []
            for a in recent:
                if a.created_at and a.response_deadline:
                    delta = (a.response_deadline - a.created_at).total_seconds() / 3600.0
                    if delta > 0:
                        response_durations.append(delta)
            response_durations.sort()
            p50 = response_durations[len(response_durations) // 2] if response_durations else 0
            p75_idx = int(len(response_durations) * 0.75)
            p90_idx = int(len(response_durations) * 0.90)
            p75 = response_durations[p75_idx] if p75_idx < len(response_durations) else 0
            p90 = response_durations[p90_idx] if p90_idx < len(response_durations) else 0

            # 3. 预警有效性：已闭环中，trigger_value > threshold_value 的比例（粗略）
            closed = [a for a in recent if a.alert_status in ("已闭环", "待闭环确认")]
            effective = sum(
                1 for a in closed
                if a.trigger_value is not None and a.threshold_value is not None
                and float(a.trigger_value) > float(a.threshold_value)
            )
            effectiveness = round(effective / len(closed) * 100.0, 1) if closed else 0.0

            return {
                "total_alerts": len(recent),
                "open_alerts": len(open_alerts),
                "open_rate": round(len(open_alerts) / len(recent) * 100.0, 1),
                "frequency_by_type": frequency_by_type,
                "open_rate_by_type": open_rate_by_type,
                "response_hours": {
                    "p50": round(p50, 1),
                    "p75": round(p75, 1),
                    "p90": round(p90, 1),
                },
                "effectiveness": effectiveness,
            }
        except Exception as e:
            logger.warning(f"[_calc_fatigue_metrics] 失败: {e}")
            return {}

    def _generate_fatigue_suggestions(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成疲劳度建议（合并/降级/取消）"""
        suggestions: List[Dict[str, Any]] = []
        freq = metrics.get("frequency_by_type", {})
        open_rate = metrics.get("open_rate_by_type", {})
        eff = metrics.get("effectiveness", 100.0)

        # 频次高 + 未闭环率高 → 合并/降级
        for alert_type, count in freq.items():
            if count >= 5:
                rate = open_rate.get(alert_type, 0)
                if rate >= 50:
                    suggestions.append({
                        "action": "合并",
                        "alert_type": alert_type,
                        "reason": f"近 N 月触发 {count} 次，未闭环率 {rate}%，建议合并同类规则",
                        "severity": "high" if rate >= 70 else "medium",
                    })
                elif rate >= 30:
                    suggestions.append({
                        "action": "降级",
                        "alert_type": alert_type,
                        "reason": f"近 N 月触发 {count} 次，未闭环率 {rate}%，建议降级为周报提示",
                        "severity": "medium",
                    })

        # 有效性低 → 取消
        if eff < 50:
            suggestions.append({
                "action": "取消",
                "alert_type": "整体规则集",
                "reason": f"近 N 月预警有效性仅 {eff}%，多数预警未真实触发问题，建议审视规则阈值",
                "severity": "high",
            })

        return suggestions
