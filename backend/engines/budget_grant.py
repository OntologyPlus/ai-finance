from __future__ import annotations

import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from loguru import logger
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.budget import BudgetItem, B2AConversion
from models.ontology import OntologyRule, ReasoningTrace
from models.alert import AlertRecord


class BudgetGrantEngine:
    """Budget Grant Engine (阶段二): Handles differentiated granting and locking for A/B budget categories.

    A-class budgets receive 100% grant immediately.
    B-class budgets receive 0% grant until milestone verification.
    B→A conversion is supported upon milestone achievement.
    """

    def __init__(self):
        self.engine_name = "budget_grant"

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
            trace_id=f"RT-BG-{uuid.uuid4().hex[:8].upper()}",
            scene_name=scene_name,
            input_data=json.dumps(input_data, ensure_ascii=False, default=str),
            steps=json.dumps(steps, ensure_ascii=False, default=str),
            conclusion=conclusion,
            confidence=confidence,
            rule_ids=json.dumps(rule_ids, ensure_ascii=False),
        )
        db.add(trace)
        await db.flush()

    async def grant_a_class(
        self, budget_id: str, db: AsyncSession
    ) -> BudgetItem:
        """Grant A-class budget: 100% grant, full freeze, notify business department.

        Args:
            budget_id: The budget item ID to grant.
            db: AsyncSession for database operations.

        Returns:
            Updated BudgetItem with granted status.

        Raises:
            ValueError: If budget item not found or not A-class.
        """
        try:
            budget_item = await db.get(BudgetItem, budget_id)
            if budget_item is None:
                raise ValueError(f"Budget item {budget_id} not found")
            if budget_item.budget_category != "A":
                raise ValueError(
                    f"Budget item {budget_id} is {budget_item.budget_category}-class, not A-class"
                )

            steps = [
                {"step": "perceive", "detail": f"Found A-class budget {budget_id}, annual_amount={budget_item.annual_amount}"},
                {"step": "reason", "detail": "A-class: apply 100% grant, full freeze"},
                {"step": "plan", "detail": "Set grant_percentage=100%, granted_amount=annual_amount, frozen_amount=annual_amount"},
            ]

            annual = Decimal(str(budget_item.annual_amount))
            budget_item.grant_percentage = Decimal("100.00")
            budget_item.granted_amount = annual
            budget_item.frozen_amount = annual
            budget_item.available_amount = annual
            budget_item.used_amount = Decimal("0")
            budget_item.status = "已授予"

            steps.append({"step": "execute", "detail": f"Budget {budget_id} granted: {annual}"})
            steps.append({"step": "reflect", "detail": "A-class grant complete, notification pending"})

            await db.flush()

            await self._record_trace(
                scene_name="A类预算授予",
                input_data={"budget_id": budget_id, "category": "A"},
                steps=steps,
                conclusion=f"A-class budget {budget_id} granted at 100%",
                rule_ids=["HR-GRANT-A"],
                confidence=Decimal("100.00"),
                db=db,
            )

            logger.info(f"A-class budget {budget_id} granted successfully")
            from ontology.decision_recorder import emit_decision

            await emit_decision(
                category="budget_grant",
                scenario=f"A类预算授予 {budget_id}",
                outcome="executed",
                reasoning=f"A-class budget {budget_id} granted at 100%",
                decision_maker="system",
                entity_ids=[budget_id],
                applied_rule_ids=["HR-GRANT-A"],
                hook_id="engine.grant_a_class",
                metadata={"budget_id": budget_id},
                db=db,
            )
            return budget_item

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"A-class grant failed for {budget_id}: {e}")
            raise

    async def grant_b_class(
        self, budget_id: str, db: AsyncSession
    ) -> BudgetItem:
        """Grant B-class budget: 0% grant, create milestone tracking.

        B-class budgets are not granted until milestone verification.
        A pending project budget ID is stored for tracking.

        Args:
            budget_id: The budget item ID to process.
            db: AsyncSession for database operations.

        Returns:
            Updated BudgetItem with pending milestone status.

        Raises:
            ValueError: If budget item not found or not B-class.
        """
        try:
            budget_item = await db.get(BudgetItem, budget_id)
            if budget_item is None:
                raise ValueError(f"Budget item {budget_id} not found")
            if budget_item.budget_category != "B":
                raise ValueError(
                    f"Budget item {budget_id} is {budget_item.budget_category}-class, not B-class"
                )

            steps = [
                {"step": "perceive", "detail": f"Found B-class budget {budget_id}"},
                {"step": "reason", "detail": "B-class: 0% grant, create milestone tracking"},
                {"step": "plan", "detail": "Set grant_percentage=0%, granted_amount=0, frozen_amount=0"},
            ]

            budget_item.grant_percentage = Decimal("0.00")
            budget_item.granted_amount = Decimal("0")
            budget_item.frozen_amount = Decimal("0")
            budget_item.available_amount = Decimal("0")
            budget_item.used_amount = Decimal("0")
            budget_item.pending_project_budget_id = f"PPB-{uuid.uuid4().hex[:8].upper()}"
            budget_item.status = "待审批"

            steps.append({"step": "execute", "detail": f"B-class budget {budget_id} set to 0% grant, milestone tracking created"})
            steps.append({"step": "reflect", "detail": "Awaiting milestone verification for B→A conversion"})

            await db.flush()

            # Auto-create quarterly milestones
            from models.milestone import Milestone
            annual = Decimal(str(budget_item.annual_amount))
            fiscal_year = datetime.now().year
            quarter_end_map = {
                1: datetime(fiscal_year, 3, 31),
                2: datetime(fiscal_year, 6, 30),
                3: datetime(fiscal_year, 9, 30),
                4: datetime(fiscal_year, 12, 31),
            }
            for q in range(1, 5):
                milestone = Milestone(
                    milestone_id=f"MS-{budget_id}-Q{q}",
                    budget_id=budget_id,
                    name=f"Q{q}里程碑",
                    planned_date=quarter_end_map[q],
                    quarter=q,
                    amount_release=annual / 4,
                    status="pending",
                )
                db.add(milestone)
            await db.flush()

            await self._record_trace(
                scene_name="B类预算授予",
                input_data={"budget_id": budget_id, "category": "B"},
                steps=steps,
                conclusion=f"B-class budget {budget_id} set to 0% grant, pending milestone",
                rule_ids=["HR-GRANT-B"],
                confidence=Decimal("100.00"),
                db=db,
            )

            logger.info(f"B-class budget {budget_id} processed, milestone tracking created")
            from ontology.decision_recorder import emit_decision

            await emit_decision(
                category="budget_grant",
                scenario=f"B类预算授予 {budget_id}",
                outcome="executed",
                reasoning=f"B-class budget {budget_id} set to 0% grant, pending milestone",
                decision_maker="system",
                entity_ids=[budget_id],
                applied_rule_ids=["HR-GRANT-B"],
                hook_id="engine.grant_b_class",
                metadata={"budget_id": budget_id},
                db=db,
            )
            return budget_item

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"B-class grant failed for {budget_id}: {e}")
            raise

    async def b2a_convert(
        self,
        budget_id: str,
        milestone_evidence: str,
        db: AsyncSession,
    ) -> BudgetItem:
        """Convert B-class budget to A-class upon milestone achievement.

        Verifies milestone evidence, updates category from B to A,
        sets grant_percentage to 100%, creates B2A conversion record,
        and checks B-class inflation alert.

        Args:
            budget_id: The budget item ID to convert.
            milestone_evidence: Evidence of milestone achievement.
            db: AsyncSession for database operations.

        Returns:
            Updated BudgetItem with A-class status.

        Raises:
            ValueError: If budget item not found, not B-class, or evidence insufficient.
        """
        try:
            budget_item = await db.get(BudgetItem, budget_id)
            if budget_item is None:
                raise ValueError(f"Budget item {budget_id} not found")
            if budget_item.budget_category != "B":
                raise ValueError(
                    f"Budget item {budget_id} is {budget_item.budget_category}-class, cannot convert"
                )
            if not milestone_evidence or len(milestone_evidence.strip()) < 10:
                raise ValueError("Milestone evidence is insufficient (minimum 10 characters)")

            # Check milestone completion requirement
            from models.milestone import Milestone
            stmt_ms = select(Milestone).where(Milestone.budget_id == budget_id)
            result_ms = await db.execute(stmt_ms)
            milestones = result_ms.scalars().all()
            completed_count = sum(1 for ms in milestones if ms.status == "completed")
            if completed_count < 2:
                raise ValueError("B类转A类需要至少完成2个季度里程碑")

            # v12.0: 三维度综合验证（时间/费用/累计），与文档 §4.4.3 里程碑预警规则对齐
            # 取已完成的里程碑中"最高级别"作为整体验证结论（蓝色/黄色/红色）
            from datetime import timedelta
            LEVEL_PRIORITY = {"蓝色": 1, "黄色": 2, "橙色": 3, "红色": 4}
            max_level = "蓝色"
            max_reasons = []

            completed_milestones = [ms for ms in milestones if ms.status == "completed"]
            for ms in completed_milestones:
                # 维度1：证据材料完整性
                if not ms.evidence or not ms.evidence.strip():
                    raise ValueError(f"里程碑 {ms.milestone_id} 缺少证据材料，无法完成B→A转换")

                # 维度2：时间偏差
                if ms.actual_date and ms.planned_date:
                    deviation_days = (ms.actual_date - ms.planned_date).days
                    if deviation_days > 60:
                        ms_level = "红色"
                        ms_reason = f"时间偏差{deviation_days}天>60天"
                    elif deviation_days > 30:
                        ms_level = "黄色"
                        ms_reason = f"时间偏差{deviation_days}天(31-60天)"
                    elif deviation_days > 20:
                        ms_level = "蓝色"
                        ms_reason = f"时间偏差{deviation_days}天(21-30天)"
                    else:
                        ms_level = None
                        ms_reason = None
                    if ms_level and LEVEL_PRIORITY.get(ms_level, 0) > LEVEL_PRIORITY.get(max_level, 0):
                        max_level = ms_level
                        max_reasons.append(f"[{ms.milestone_id}] {ms_reason}")

                # 维度3：费用偏差（amount_release vs 实际发生额）
                # 此处用 amount_release 作为计划值，evidence 中的数字无结构化字段，
                # 但若 evidence 文本中含"超支"/"超额"则视为黄色信号
                if ms.evidence:
                    text_lower = ms.evidence.lower()
                    if "严重超支" in ms.evidence or "重大超支" in ms.evidence:
                        ms_cost_level = "红色"
                        ms_cost_reason = "里程碑证据标注严重超支"
                    elif "超支" in ms.evidence or "超额" in ms.evidence:
                        ms_cost_level = "黄色"
                        ms_cost_reason = "里程碑证据标注超支"
                    else:
                        ms_cost_level = None
                        ms_cost_reason = None
                    if ms_cost_level and LEVEL_PRIORITY.get(ms_cost_level, 0) > LEVEL_PRIORITY.get(max_level, 0):
                        max_level = ms_cost_level
                        max_reasons.append(f"[{ms.milestone_id}] {ms_cost_reason}")

            # v12.0: 最高级别为红色时强制拒绝B→A转换
            if max_level == "红色":
                reasons_str = "; ".join(max_reasons) if max_reasons else "三维度中有红色信号"
                raise ValueError(
                    f"B→A转换被拒：里程碑验证存在红色级别风险（{reasons_str}）。"
                    f"需重新完成里程碑或将风险降至黄色及以下"
                )
            if max_level == "黄色":
                # 黄色时仍允许转换，但记录风险信号
                steps_extra = {
                    "warning": f"里程碑验证黄色风险: {'; '.join(max_reasons) if max_reasons else '维度偏离'}",
                }
            else:
                steps_extra = None

            steps = [
                {"step": "perceive", "detail": f"Found B-class budget {budget_id}, evidence provided"},
                {"step": "reason", "detail": "Milestone evidence verified, proceeding B→A conversion"},
                {"step": "plan", "detail": "Update category to A, set 100% grant, create conversion record"},
            ]
            if steps_extra:
                steps.append(steps_extra)

            annual = Decimal(str(budget_item.annual_amount))
            budget_item.budget_category = "A"
            budget_item.grant_percentage = Decimal("100.00")
            budget_item.granted_amount = annual
            budget_item.frozen_amount = annual
            budget_item.available_amount = annual
            budget_item.status = "已授予"

            now = datetime.now()
            quarter = f"Q{(now.month - 1) // 3 + 1}"

            # v12.0: 把黄色风险信号持久化到转换记录 evidence 字段
            combined_evidence = milestone_evidence
            if max_level == "黄色" and max_reasons:
                combined_evidence = (
                    f"{milestone_evidence}\n\n"
                    f"[里程碑验证黄色风险] {'; '.join(max_reasons)}"
                )

            conversion = B2AConversion(
                conversion_id=f"B2A-{uuid.uuid4().hex[:8].upper()}",
                budget_id=budget_id,
                conversion_date=now,
                milestone_evidence=combined_evidence,
                milestone_period=quarter,
                approval_status="已通过",
                pre_category="B",
                post_category="A",
                frozen_amount=annual,
                report_to_committee=(max_level == "黄色"),  # 黄色风险须上报管委会
            )
            db.add(conversion)

            steps.append({"step": "execute", "detail": f"B→A conversion complete for {budget_id}"})

            await self._check_b_class_inflation(budget_item, db, steps)

            steps.append({"step": "reflect", "detail": "B→A conversion complete, inflation check done"})

            await db.flush()

            await self._record_trace(
                scene_name="B转A转换",
                input_data={
                    "budget_id": budget_id,
                    "evidence_length": len(milestone_evidence),
                    "max_level": max_level,
                },
                steps=steps,
                conclusion=f"Budget {budget_id} converted from B to A (risk level: {max_level})",
                rule_ids=["HR-B2A-001"],
                confidence=Decimal("95.00") if max_level == "蓝色" else Decimal("85.00"),
                db=db,
            )

            logger.info(f"B→A conversion complete for budget {budget_id}")
            from ontology.decision_recorder import emit_decision

            await emit_decision(
                category="budget_b2a",
                scenario=f"B转A {budget_id}",
                outcome="executed",
                reasoning=f"Budget {budget_id} converted from B to A (risk level: {max_level})",
                decision_maker="system",
                entity_ids=[budget_id],
                applied_rule_ids=["HR-B2A-001"],
                hook_id="engine.b2a_convert",
                metadata={"budget_id": budget_id, "risk_level": max_level},
                db=db,
            )
            return budget_item

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"B→A conversion failed for {budget_id}: {e}")
            raise

    async def generate_b2a_report(self, db: AsyncSession, period: str = None) -> Dict[str, Any]:
        from models.budget import B2AConversion, BudgetItem
        from sqlalchemy import select
        from datetime import datetime

        stmt = select(B2AConversion).order_by(B2AConversion.created_at.desc())
        result = await db.execute(stmt)
        conversions = result.scalars().all()

        total_b_class = await db.execute(select(BudgetItem).where(BudgetItem.budget_category == "B"))
        b_items = total_b_class.scalars().all()

        total_b_budget = sum(float(item.annual_amount or 0) for item in b_items)
        converted_amount = sum(float(c.frozen_amount or 0) for c in conversions)
        conversion_rate = round(converted_amount / total_b_budget * 100, 2) if total_b_budget > 0 else 0

        by_quarter = {}
        for c in conversions:
            q = f"Q{(c.created_at.month - 1) // 3 + 1}" if c.created_at else "Q1"
            by_quarter[q] = by_quarter.get(q, 0) + float(c.frozen_amount or 0)

        by_l1 = {}
        for c in conversions:
            budget_item = await db.execute(select(BudgetItem).where(BudgetItem.budget_id == c.budget_id))
            item = budget_item.scalar_one_or_none()
            l1 = item.l1_code if item else "未知"
            by_l1[l1] = by_l1.get(l1, 0) + float(c.frozen_amount or 0)

        return {
            "report_type": "B→A转换专项报告",
            "period": period or datetime.now().strftime("%Y-%m"),
            "summary": {
                "total_b_budget": total_b_budget,
                "converted_amount": converted_amount,
                "conversion_rate": conversion_rate,
                "conversion_count": len(conversions),
            },
            "by_quarter": by_quarter,
            "by_l1": by_l1,
            "conversions": [{"id": c.conversion_id, "budget_id": c.budget_id, "amount": float(c.frozen_amount or 0), "evidence": c.milestone_evidence, "status": c.approval_status, "date": c.created_at.isoformat() if c.created_at else None} for c in conversions],
        }

    async def _check_b_class_inflation(
        self,
        converted_item: BudgetItem,
        db: AsyncSession,
        steps: list,
    ) -> None:
        """Check if B-class frozen amount exceeds 30% of A-class executed amount (orange alert)."""
        stmt = select(BudgetItem).where(
            and_(
                BudgetItem.budget_category == "B",
                BudgetItem.center_id == converted_item.center_id,
                BudgetItem.status != "已取消",
            )
        )
        result = await db.execute(stmt)
        b_items = result.scalars().all()

        total_b_frozen = sum(Decimal(str(item.frozen_amount)) for item in b_items)

        stmt_a = select(BudgetItem).where(
            and_(
                BudgetItem.budget_category == "A",
                BudgetItem.center_id == converted_item.center_id,
                BudgetItem.status != "已取消",
            )
        )
        result_a = await db.execute(stmt_a)
        a_items = result_a.scalars().all()

        total_a_executed = sum(Decimal(str(item.used_amount)) for item in a_items)

        if total_a_executed > 0 and total_b_frozen > total_a_executed * Decimal("0.3"):
            steps.append({
                "step": "alert",
                "detail": (
                    f"B-class inflation alert: B frozen={total_b_frozen}, "
                    f"A executed={total_a_executed}, ratio={total_b_frozen / total_a_executed:.2%}"
                ),
            })
            logger.warning(
                f"B-class inflation orange alert for center {converted_item.center_id}: "
                f"B frozen={total_b_frozen} > A executed * 30% = {total_a_executed * Decimal('0.3')}"
            )
            # 创建真实的 AlertRecord
            alert = AlertRecord(
                alert_id=f"ALT-BINF-{uuid.uuid4().hex[:8].upper()}",
                budget_id=converted_item.budget_id,
                alert_type="B类膨胀预警",
                alert_level="橙色",
                alert_status="开放",
                description=f"B类冻结金额({total_b_frozen})超过A类执行金额({total_a_executed})的30%",
            )
            db.add(alert)

    # ══════════════════════════════════════════════════════════════════
    # v12.1: 阶段 2 — B→A 智能预判（AI 增强）
    # ══════════════════════════════════════════════════════════════════
    async def predict_b2a_conversion(
        self,
        budget_id: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """v12.1: 单个 B 类预算的 B→A 转换预判

        算法：基于 5 维加权评分，给出 0-100 的「转换就绪度」分数，
        并诊断风险因子、给出修复建议。

        Returns:
            {
                "budget_id": "...",
                "ready_score": 0-100,
                "predicted_outcome": "可转换/黄色风险/红色拦截",
                "risk_level": "蓝色/黄色/红色",
                "risk_factors": [{type, severity, detail}],
                "recommendations": ["..."],
                "milestone_summary": {total, completed, pending, overdue},
                "dimension_scores": {evidence, time, cost, completion, consistency}
            }
        """
        from models.milestone import Milestone
        from datetime import datetime, timedelta

        item = await db.get(BudgetItem, budget_id)
        if item is None:
            raise ValueError(f"Budget item {budget_id} not found")
        if item.budget_category != "B":
            return {
                "budget_id": budget_id,
                "ready_score": 100,
                "predicted_outcome": "无需转换（非 B 类）",
                "risk_level": "蓝色",
                "risk_factors": [],
                "recommendations": [f"该预算为{item.budget_category}类，无需 B→A 转换"],
                "milestone_summary": {"total": 0, "completed": 0, "pending": 0, "overdue": 0},
                "dimension_scores": {},
            }

        # 加载里程碑
        stmt = select(Milestone).where(Milestone.budget_id == budget_id).order_by(Milestone.quarter)
        result = await db.execute(stmt)
        milestones = result.scalars().all()
        total_ms = len(milestones)
        completed_ms = [m for m in milestones if m.status == "completed"]
        pending_ms = [m for m in milestones if m.status == "pending"]
        now = datetime.now()
        overdue_ms = [m for m in pending_ms if m.planned_date and m.planned_date < now]

        # ── 维度 1：里程碑完成度（权重 35%）──
        completion_rate = len(completed_ms) / max(total_ms, 1)
        completion_score = completion_rate * 100
        if len(completed_ms) < 2:
            completion_score *= 0.5  # 至少需要 2 个才能转 A，直接打折

        # ── 维度 2：时间偏差（权重 25%）──
        time_penalties = []
        time_score = 100.0
        for ms in completed_ms:
            if ms.actual_date and ms.planned_date:
                dev = (ms.actual_date - ms.planned_date).days
                if dev > 60:
                    time_score = 0
                    time_penalties.append({"milestone_id": ms.milestone_id, "days": dev, "level": "红色"})
                elif dev > 30:
                    time_score = min(time_score, 40)
                    time_penalties.append({"milestone_id": ms.milestone_id, "days": dev, "level": "黄色"})
                elif dev > 20:
                    time_score = min(time_score, 70)
                    time_penalties.append({"milestone_id": ms.milestone_id, "days": dev, "level": "蓝色"})

        # ── 维度 3：费用偏差（权重 15%）──
        cost_score = 100.0
        cost_penalties = []
        for ms in completed_ms:
            if ms.evidence:
                if "严重超支" in ms.evidence or "重大超支" in ms.evidence:
                    cost_score = 0
                    cost_penalties.append({"milestone_id": ms.milestone_id, "level": "红色", "reason": "严重超支"})
                elif "超支" in ms.evidence or "超额" in ms.evidence:
                    cost_score = min(cost_score, 50)
                    cost_penalties.append({"milestone_id": ms.milestone_id, "level": "黄色", "reason": "超支"})

        # ── 维度 4：证据完整度（权重 15%）──
        evidence_score = 100.0
        for ms in completed_ms:
            if not ms.evidence or len(ms.evidence.strip()) < 10:
                evidence_score = min(evidence_score, 30)
        if not completed_ms:
            evidence_score = 0

        # ── 维度 5：逾期风险（权重 10%）──
        overdue_score = 100.0
        if total_ms > 0:
            overdue_rate = len(overdue_ms) / total_ms
            overdue_score = max(0, 100 - overdue_rate * 100)

        # 加权汇总
        ready_score = round(
            completion_score * 0.35
            + time_score * 0.25
            + cost_score * 0.15
            + evidence_score * 0.15
            + overdue_score * 0.10,
            1,
        )

        # 风险等级判定
        if ready_score >= 80:
            predicted_outcome = "可转换（建议立即提交）"
            risk_level = "蓝色"
        elif ready_score >= 60:
            predicted_outcome = "黄色风险（可转换但需管委会审批）"
            risk_level = "黄色"
        elif ready_score >= 30:
            predicted_outcome = "需补强（建议先完成更多里程碑）"
            risk_level = "黄色"
        else:
            predicted_outcome = "红色拦截（转换将被拒）"
            risk_level = "红色"

        # 风险因子聚合
        risk_factors = []
        for p in time_penalties:
            risk_factors.append({
                "type": "时间偏差",
                "severity": p["level"],
                "detail": f"里程碑 {p['milestone_id']} 偏差 {p['days']} 天",
            })
        for p in cost_penalties:
            risk_factors.append({
                "type": "费用偏差",
                "severity": p["level"],
                "detail": f"里程碑 {p['milestone_id']}：{p['reason']}",
            })
        if len(completed_ms) < 2:
            risk_factors.append({
                "type": "里程碑不足",
                "severity": "黄色",
                "detail": f"仅完成 {len(completed_ms)}/4 季度里程碑，B→A 转换至少需要 2 个",
            })
        if overdue_ms:
            risk_factors.append({
                "type": "逾期里程碑",
                "severity": "黄色" if len(overdue_ms) == 1 else "红色",
                "detail": f"{len(overdue_ms)} 个里程碑已逾期：{', '.join(m.milestone_id for m in overdue_ms[:3])}",
            })
        if evidence_score < 100:
            risk_factors.append({
                "type": "证据缺失",
                "severity": "黄色" if evidence_score > 50 else "红色",
                "detail": "部分已完成里程碑缺少证据材料（< 10 字符）",
            })

        # 修复建议
        recommendations = []
        if len(completed_ms) < 2:
            recommendations.append(f"先完成至少 2 个季度里程碑（当前 {len(completed_ms)} 个）")
        if overdue_ms:
            recommendations.append(f"优先处理 {len(overdue_ms)} 个逾期里程碑")
        for p in time_penalties:
            if p["level"] == "红色":
                recommendations.append(f"里程碑 {p['milestone_id']} 时间偏差 {p['days']} 天 > 60 天，需重新完成")
        for p in cost_penalties:
            if p["level"] == "红色":
                recommendations.append(f"里程碑 {p['milestone_id']} 严重超支，需补充成本优化证据")
        if evidence_score < 100:
            recommendations.append("补全所有已完成里程碑的证据材料（≥ 10 字符）")
        if not recommendations:
            recommendations.append("各项指标良好，可直接提交 B→A 转换申请")

        return {
            "budget_id": budget_id,
            "budget_name": item.budget_name,
            "annual_amount": float(item.annual_amount or 0),
            "ready_score": ready_score,
            "predicted_outcome": predicted_outcome,
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "recommendations": recommendations,
            "milestone_summary": {
                "total": total_ms,
                "completed": len(completed_ms),
                "pending": len(pending_ms),
                "overdue": len(overdue_ms),
            },
            "dimension_scores": {
                "completion": round(completion_score, 1),
                "time": round(time_score, 1),
                "cost": round(cost_score, 1),
                "evidence": round(evidence_score, 1),
                "overdue": round(overdue_score, 1),
            },
        }

    async def batch_scan_b2a_risk(
        self,
        db: AsyncSession,
        top_n: int = 10,
    ) -> Dict[str, Any]:
        """v12.1: 批量扫描所有 B 类预算的 B→A 转换风险

        Returns:
            {
                "summary": {total_b_items, ready_count, yellow_risk_count, red_blocked_count},
                "ready_to_convert": [...top N 高分项],
                "at_risk": [...top N 低分项],
                "by_center": {center_id: {count, avg_score, total_amount}},
                "by_l1": {l1_code: {count, avg_score, total_amount}},
            }
        """
        from sqlalchemy import and_

        # 拉取所有 B 类且未取消的预算
        stmt = select(BudgetItem).where(
            and_(
                BudgetItem.budget_category == "B",
                BudgetItem.status != "已取消",
            )
        )
        result = await db.execute(stmt)
        b_items = result.scalars().all()

        if not b_items:
            return {
                "summary": {
                    "total_b_items": 0,
                    "ready_count": 0,
                    "yellow_risk_count": 0,
                    "red_blocked_count": 0,
                    "total_b_amount": 0,
                },
                "ready_to_convert": [],
                "at_risk": [],
                "by_center": {},
                "by_l1": {},
                "scanned_at": datetime.now().isoformat(),
            }

        # 逐项预判
        predictions = []
        for item in b_items:
            try:
                pred = await self.predict_b2a_conversion(item.budget_id, db)
                pred["center_id"] = item.center_id
                pred["l1_code"] = item.l1_code
                predictions.append(pred)
            except Exception as e:
                logger.error(f"预测 {item.budget_id} 失败: {e}")

        # 分类汇总
        ready_list = [p for p in predictions if p["risk_level"] == "蓝色"]
        yellow_list = [p for p in predictions if p["risk_level"] == "黄色"]
        red_list = [p for p in predictions if p["risk_level"] == "红色"]

        # 按分数排序
        ready_sorted = sorted(ready_list, key=lambda x: -x["ready_score"])[:top_n]
        risk_sorted = sorted(red_list + yellow_list, key=lambda x: x["ready_score"])[:top_n]

        # 按中心聚合
        by_center: Dict[str, Dict] = {}
        for p in predictions:
            cid = p.get("center_id") or "未分配"
            if cid not in by_center:
                by_center[cid] = {"count": 0, "total_amount": 0, "scores": []}
            by_center[cid]["count"] += 1
            by_center[cid]["total_amount"] += p.get("annual_amount", 0)
            by_center[cid]["scores"].append(p["ready_score"])
        for cid, v in by_center.items():
            v["avg_score"] = round(sum(v["scores"]) / len(v["scores"]), 1)
            v["total_amount"] = round(v["total_amount"], 2)
            del v["scores"]

        # 按 L1 聚合
        by_l1: Dict[str, Dict] = {}
        for p in predictions:
            l1 = p.get("l1_code") or "未分类"
            if l1 not in by_l1:
                by_l1[l1] = {"count": 0, "total_amount": 0, "scores": []}
            by_l1[l1]["count"] += 1
            by_l1[l1]["total_amount"] += p.get("annual_amount", 0)
            by_l1[l1]["scores"].append(p["ready_score"])
        for l1, v in by_l1.items():
            v["avg_score"] = round(sum(v["scores"]) / len(v["scores"]), 1)
            v["total_amount"] = round(v["total_amount"], 2)
            del v["scores"]

        total_b_amount = sum(float(item.annual_amount or 0) for item in b_items)

        return {
            "summary": {
                "total_b_items": len(b_items),
                "ready_count": len(ready_list),
                "yellow_risk_count": len(yellow_list),
                "red_blocked_count": len(red_list),
                "total_b_amount": round(total_b_amount, 2),
            },
            "ready_to_convert": ready_sorted,
            "at_risk": risk_sorted,
            "by_center": by_center,
            "by_l1": by_l1,
            "scanned_at": datetime.now().isoformat(),
        }

    async def release_budget(
        self,
        budget_id: str,
        amount: float,
        reason: str,
        db: AsyncSession,
    ) -> BudgetItem:
        """Release frozen budget amount back to available.

        Reduces frozen_amount and increases available_amount.

        Args:
            budget_id: The budget item ID.
            amount: Amount to release.
            reason: Reason for release.
            db: AsyncSession for database operations.

        Returns:
            Updated BudgetItem.

        Raises:
            ValueError: If budget not found or insufficient frozen amount.
        """
        try:
            budget_item = await db.get(BudgetItem, budget_id)
            if budget_item is None:
                raise ValueError(f"Budget item {budget_id} not found")

            release_amount = Decimal(str(amount))
            frozen = Decimal(str(budget_item.frozen_amount))

            if release_amount > frozen:
                raise ValueError(
                    f"Release amount {release_amount} exceeds frozen amount {frozen}"
                )

            steps = [
                {"step": "perceive", "detail": f"Budget {budget_id}, frozen={frozen}, release={release_amount}"},
                {"step": "reason", "detail": f"Release reason: {reason}"},
                {"step": "plan", "detail": "Reduce frozen_amount, increase available_amount"},
            ]

            budget_item.frozen_amount = frozen - release_amount
            budget_item.available_amount = Decimal(str(budget_item.available_amount)) + release_amount

            steps.append({"step": "execute", "detail": f"Released {release_amount} from budget {budget_id}"})
            steps.append({"step": "reflect", "detail": "Budget release complete"})

            await db.flush()

            await self._record_trace(
                scene_name="预算释放",
                input_data={"budget_id": budget_id, "amount": amount, "reason": reason},
                steps=steps,
                conclusion=f"Released {amount} from budget {budget_id}",
                rule_ids=["HR-RELEASE-001"],
                confidence=Decimal("100.00"),
                db=db,
            )

            logger.info(f"Released {amount} from budget {budget_id}")
            return budget_item

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Budget release failed for {budget_id}: {e}")
            raise
