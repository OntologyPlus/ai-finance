from __future__ import annotations

import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.budget import BudgetItem, BudgetSubjectL1, BudgetSubjectL2, BudgetSubjectL3
from models.ontology import OntologyRule, OntologyScene, ReasoningTrace
from models.analysis import ExecutionRate, BudgetHealthScore
from models.transfer import BudgetTransferRequest
from models.strategic import StrategicInitiative


class BudgetPlanningEngine:
    """Budget Planning Engine (阶段一): Converts SP/BP strategic plans into annual budget item lists.

    Follows the perceive→reason→plan→execute→reflect cognitive pattern.
    Uses the ontology rule engine for quadrant assignment, A/B classification,
    and strategic alignment verification.
    """

    def __init__(self):
        self.engine_name = "budget_planning"

    async def _perceive(self, sp_data: Dict, bp_data: Dict, db: AsyncSession) -> Dict:
        stmt = select(OntologyScene).where(
            OntologyScene.corresponding_stage == "阶段一",
            OntologyScene.is_active.is_(True),
        )
        result = await db.execute(stmt)
        scene = result.scalars().first()

        stmt_rules = select(OntologyRule).where(
            OntologyRule.is_active.is_(True),
            OntologyRule.scene_tags.contains("预算编制"),
        )
        rules_result = await db.execute(stmt_rules)
        rules = rules_result.scalars().all()

        strategic_initiatives = sp_data.get("strategic_initiatives", [])
        bp_initiatives = bp_data.get("initiatives", [])

        return {
            "scene": scene,
            "rules": rules,
            "strategic_initiatives": strategic_initiatives,
            "bp_initiatives": bp_initiatives,
        }

    async def _reason(
        self,
        perception: Dict,
        budget_proposals: List[Dict],
        db: AsyncSession,
    ) -> Dict:
        reasoning_steps = []
        rule_ids = []

        for rule in perception["rules"]:
            rule_ids.append(rule.rule_id)
            try:
                condition = json.loads(rule.condition) if isinstance(rule.condition, str) else rule.condition
            except (json.JSONDecodeError, TypeError):
                condition = {}
            reasoning_steps.append({
                "rule_id": rule.rule_id,
                "rule_name": rule.rule_name,
                "condition": condition,
                "applied": True,
            })

        quadrant_recommendations = {}
        for initiative in perception["strategic_initiatives"]:
            init_id = initiative.get("id", "")
            quadrant_result = await self.recommend_quadrant(initiative, db)
            quadrant_recommendations[init_id] = quadrant_result

        ab_classifications = {}
        for proposal in budget_proposals:
            proposal_id = proposal.get("budget_id", str(uuid.uuid4())[:8])
            category = await self._classify_ab_internal(proposal, db)
            ab_classifications[proposal_id] = category

        alignment_results = {}
        for proposal in budget_proposals:
            proposal_id = proposal.get("budget_id", str(uuid.uuid4())[:8])
            aligned_result = await self.check_strategic_alignment(
                proposal, perception["strategic_initiatives"], db
            )
            alignment_results[proposal_id] = aligned_result

        return {
            "reasoning_steps": reasoning_steps,
            "rule_ids": rule_ids,
            "quadrant_recommendations": quadrant_recommendations,
            "ab_classifications": ab_classifications,
            "alignment_results": alignment_results,
        }

    async def _plan(self, reasoning: Dict, budget_proposals: List[Dict], db: AsyncSession = None) -> List[Dict]:
        plan_steps = []

        for proposal in budget_proposals:
            proposal_id = proposal.get("budget_id", str(uuid.uuid4())[:8])
            init_id = proposal.get("strategy_initiative_id", "")
            quadrant_result = reasoning["quadrant_recommendations"].get(init_id, {"quadrant": "稳定"})
            if isinstance(quadrant_result, dict):
                quadrant = quadrant_result.get("quadrant", "稳定")
            else:
                quadrant = quadrant_result
            category = reasoning["ab_classifications"].get(proposal_id, "B")
            aligned_result = reasoning["alignment_results"].get(proposal_id, {"aligned": False})
            aligned = aligned_result.get("aligned", False) if isinstance(aligned_result, dict) else aligned_result

            # Calculate suggested amount
            suggested_amount = await self._calculate_suggested_amount(proposal, db)

            plan_steps.append({
                "budget_id": proposal_id,
                "quadrant": quadrant,
                "category": category,
                "aligned": aligned,
                "action": "create" if aligned else "flag_for_review",
                "suggested_amount": suggested_amount,
            })

        return plan_steps

    async def _calculate_suggested_amount(
        self, budget_item: Dict[str, Any], db: AsyncSession = None
    ) -> Optional[float]:
        """Calculate suggested budget amount based on historical execution rate and strategic priority.

        Args:
            budget_item: Budget item data dictionary.
            db: Optional AsyncSession for querying historical data.

        Returns:
            Suggested amount or None if cannot determine.
        """
        try:
            annual_amount = float(budget_item.get("annual_amount", 0) or 0)
            if annual_amount <= 0:
                return None

            suggested = annual_amount
            strategic_priority = budget_item.get("strategic_priority", "medium")

            # Check historical execution rate from previous year's data
            historical_execution_rate = None
            if db:
                budget_id = budget_item.get("budget_id")
                if budget_id:
                    stmt = select(BudgetItem).where(
                        BudgetItem.budget_id == budget_id,
                    )
                    result = await db.execute(stmt)
                    existing = result.scalars().first()
                    if existing and existing.annual_amount and float(existing.annual_amount) > 0:
                        used = float(existing.used_amount or 0)
                        granted = float(existing.granted_amount or 0)
                        if granted > 0:
                            historical_execution_rate = used / granted

            # Adjust based on historical execution rate
            if historical_execution_rate is not None:
                if historical_execution_rate < 0.8:
                    # Under-execution: suggest reducing
                    suggested = annual_amount * (0.9 + 0.1 * historical_execution_rate)
                elif historical_execution_rate > 1.0:
                    # Over-execution: suggest increasing
                    suggested = annual_amount * min(historical_execution_rate, 1.2)

            # Adjust based on strategic priority
            if strategic_priority == "high":
                suggested *= 1.2  # +20% for high priority
            elif strategic_priority == "low":
                suggested *= 0.9  # -10% for low priority

            return round(suggested, 2)
        except Exception as e:
            logger.error(f"Suggested amount calculation failed: {e}")
            return None

    async def _execute(
        self,
        plan_steps: List[Dict],
        budget_proposals: List[Dict],
        db: AsyncSession,
    ) -> List[BudgetItem]:
        created_items = []

        for step in plan_steps:
            proposal = next(
                (p for p in budget_proposals if p.get("budget_id") == step["budget_id"]),
                None,
            )
            if proposal is None:
                continue

            if step["action"] == "flag_for_review":
                logger.warning(
                    f"Budget proposal {step['budget_id']} flagged for review - "
                    f"no strategic alignment found"
                )

            budget_id = proposal.get("budget_id", f"BG-{uuid.uuid4().hex[:8].upper()}")
            existing = await db.get(BudgetItem, budget_id)
            if existing:
                created_items.append(existing)
                continue

            l3_code = proposal.get("l3_code")
            l2_code = proposal.get("l2_code")
            l1_code = proposal.get("l1_code")

            if l3_code and not l1_code:
                l3 = await db.get(BudgetSubjectL3, l3_code)
                if l3:
                    l1_code = l3.l1_code
                    l2_code = l3.l2_code

            if l2_code and not l1_code:
                l2 = await db.get(BudgetSubjectL2, l2_code)
                if l2:
                    l1_code = l2.l1_code

            budget_item = BudgetItem(
                budget_id=budget_id,
                budget_name=proposal.get("budget_name", ""),
                budget_category=step["category"],
                l1_code=l1_code or "00",
                l2_code=l2_code,
                l3_code=l3_code,
                quadrant=step["quadrant"],
                strategy_initiative_id=proposal.get("strategy_initiative_id"),
                annual_amount=proposal.get("annual_amount", 0),
                granted_amount=0,
                frozen_amount=0,
                used_amount=0,
                available_amount=0,
                grant_percentage=0,
                status="编制中",
                center_id=proposal.get("center_id"),
                department_id=proposal.get("department_id"),
                project_id=proposal.get("project_id"),
            )
            db.add(budget_item)
            created_items.append(budget_item)

        await db.flush()
        return created_items

    async def _reflect(
        self,
        created_items: List[BudgetItem],
        reasoning: Dict,
        db: AsyncSession,
    ) -> None:
        trace_id = f"RT-BP-{uuid.uuid4().hex[:8].upper()}"
        steps_json = json.dumps(reasoning["reasoning_steps"], ensure_ascii=False, default=str)
        rule_ids_json = json.dumps(reasoning["rule_ids"], ensure_ascii=False)

        unaligned_count = sum(
            1 for v in reasoning["alignment_results"].values()
            if (v.get("aligned", False) if isinstance(v, dict) else not v)
        )
        conclusion = (
            f"Created {len(created_items)} budget items, "
            f"{unaligned_count} unaligned proposals flagged"
        )

        trace = ReasoningTrace(
            trace_id=trace_id,
            scene_id=reasoning.get("scene_id"),
            scene_name="预算编制",
            input_data=json.dumps(
                {"item_count": len(created_items)}, ensure_ascii=False, default=str
            ),
            steps=steps_json,
            conclusion=conclusion,
            confidence=95.00 if unaligned_count == 0 else 75.00,
            rule_ids=rule_ids_json,
        )
        db.add(trace)
        await db.flush()

    async def create_budget_from_strategy(
        self,
        sp_data: Dict[str, Any],
        bp_data: Dict[str, Any],
        db: AsyncSession,
    ) -> List[BudgetItem]:
        """Parse SP/BP data to extract strategic initiatives and generate budget item list.

        Args:
            sp_data: Strategic Plan data containing strategic initiatives.
            bp_data: Business Plan data containing business initiatives.
            db: AsyncSession for database operations.

        Returns:
            List of created BudgetItem objects.
        """
        try:
            budget_proposals = bp_data.get("budget_proposals", [])

            perception = await self._perceive(sp_data, bp_data, db)
            reasoning = await self._reason(perception, budget_proposals, db)
            plan_steps = await self._plan(reasoning, budget_proposals, db)
            created_items = await self._execute(plan_steps, budget_proposals, db)
            await self._reflect(created_items, reasoning, db)

            logger.info(
                f"Budget planning complete: {len(created_items)} items created"
            )
            return created_items
        except Exception as e:
            logger.error(f"Budget planning failed: {e}")
            raise

    async def classify_ab_category(
        self, budget_item: Dict[str, Any], db: AsyncSession
    ) -> str:
        """Classify a budget item as A (high certainty) or B (progress-dependent).

        A: High certainty, approved projects with clear deliverables.
        B: Progress-dependent, milestone-verified items.

        Args:
            budget_item: Budget item data dictionary.
            db: AsyncSession for database operations.

        Returns:
            "A" or "B" classification string.
        """
        try:
            return await self._classify_ab_internal(budget_item, db)
        except Exception as e:
            logger.error(f"A/B classification failed: {e}")
            return "B"

    async def _classify_ab_internal(
        self, budget_item: Dict[str, Any], db: AsyncSession
    ) -> str:
        stmt = select(OntologyRule).where(
            OntologyRule.rule_id == "HR-AB-001",
            OntologyRule.is_active.is_(True),
        )
        result = await db.execute(stmt)
        rule = result.scalars().first()

        certainty = budget_item.get("certainty", "low")
        approval_status = budget_item.get("approval_status", "pending")
        has_milestone = budget_item.get("has_milestone", False)
        is_approved_project = budget_item.get("is_approved_project", False)

        # Enhanced dimensions
        has_project = budget_item.get("project_id") is not None
        annual_amount = float(budget_item.get("annual_amount", 0) or 0)
        strategic_priority = budget_item.get("strategic_priority", "medium")

        # Score-based classification: higher score → more likely A
        score = 0

        if rule:
            try:
                condition = json.loads(rule.condition) if isinstance(rule.condition, str) else rule.condition
                if condition.get("default_category") == "A":
                    if certainty == "high" or is_approved_project:
                        return "A"
            except (json.JSONDecodeError, TypeError):
                pass

        # Original dimensions
        if is_approved_project and approval_status in ("approved", "已批准"):
            score += 3
        if certainty == "high" and not has_milestone:
            score += 2
        if has_milestone:
            score -= 1
        if certainty in ("low", "medium"):
            score -= 1

        # Enhanced dimensions
        if has_project:
            score += 2  # Linked project → more likely A
        if annual_amount > 5_000_000:  # >500万 → more likely A
            score += 2
        if strategic_priority == "high":
            score += 2
        elif strategic_priority == "low":
            score -= 1

        return "A" if score >= 3 else "B"

    async def recommend_quadrant(
        self,
        strategic_initiative: Dict[str, Any],
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Recommend a quadrant assignment for a strategic initiative.

        Quadrants: 发展 (Develop), 收缩 (Shrink), 稳定 (Stable), 探索 (Explore).
        Uses rule engine conditions when available, and applies strategic intent weight.

        Args:
            strategic_initiative: Strategic initiative data.
            db: AsyncSession for database operations.

        Returns:
            Dict with quadrant name, flag_for_review, and strategic_intent_adjustment.
        """
        try:
            stmt = select(OntologyRule).where(
                OntologyRule.rule_id == "HR-QD-001",
                OntologyRule.is_active.is_(True),
            )
            result = await db.execute(stmt)
            rule = result.scalars().first()

            growth_rate = strategic_initiative.get("growth_rate", 0)
            market_share = strategic_initiative.get("market_share", 0)
            strategic_priority = strategic_initiative.get("priority", "medium")
            strategic_intent_l1 = strategic_initiative.get("strategic_intent_l1")

            quadrant = "稳定"
            rule_engine_adjusted = False

            if rule:
                try:
                    condition = json.loads(rule.condition) if isinstance(rule.condition, str) else rule.condition
                    if condition.get("use_rule_engine", False):
                        # Execute rule engine conditions
                        rule_conditions = condition.get("conditions", [])
                        for rc in rule_conditions:
                            if rc.get("type") == "growth_threshold":
                                threshold = rc.get("value", 0.2)
                                if growth_rate > threshold:
                                    quadrant = rc.get("quadrant", "发展")
                                    rule_engine_adjusted = True
                            elif rc.get("type") == "market_share_threshold":
                                threshold = rc.get("value", 0.1)
                                if market_share < threshold:
                                    quadrant = rc.get("quadrant", "探索")
                                    rule_engine_adjusted = True
                            elif rc.get("type") == "priority_mapping":
                                mapping = rc.get("mapping", {})
                                if strategic_priority in mapping:
                                    quadrant = mapping[strategic_priority]
                                    rule_engine_adjusted = True
                except (json.JSONDecodeError, TypeError):
                    pass

            # Fallback to default logic if rule engine didn't adjust
            if not rule_engine_adjusted:
                if strategic_priority == "high" and growth_rate > 0.2:
                    quadrant = "发展"
                elif strategic_priority == "low" and growth_rate < -0.1:
                    quadrant = "收缩"
                elif strategic_priority == "high" and market_share < 0.1:
                    quadrant = "探索"
                else:
                    quadrant = "稳定"

            # Strategic intent weight: boost toward 发展 for high priority items
            flag_for_review = False
            strategic_intent_adjustment = None
            if strategic_intent_l1:
                if strategic_priority == "high" and quadrant != "发展":
                    strategic_intent_adjustment = f"战略意图 {strategic_intent_l1} 为高优先级，建议从 '{quadrant}' 调整为 '发展'"
                    if strategic_priority == "high":
                        quadrant = "发展"
                # Flag for review if in 收缩 but has high strategic priority
                if quadrant == "收缩" and strategic_priority == "high":
                    flag_for_review = True

            return {
                "quadrant": quadrant,
                "flag_for_review": flag_for_review,
                "strategic_intent_adjustment": strategic_intent_adjustment,
            }
        except Exception as e:
            logger.error(f"Quadrant recommendation failed: {e}")
            return {"quadrant": "稳定", "flag_for_review": False, "strategic_intent_adjustment": None}

    async def check_strategic_alignment(
        self,
        budget_item: Dict[str, Any],
        strategic_initiatives: List[Dict[str, Any]],
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Check if a budget item aligns with any strategic initiative.

        Args:
            budget_item: Budget item data.
            strategic_initiatives: List of strategic initiatives from SP.
            db: AsyncSession for database operations.

        Returns:
            Dict with aligned (bool), alignment_type (str), matched_initiative (str|None).
        """
        try:
            if not strategic_initiatives:
                return {"aligned": False, "alignment_type": "none", "matched_initiative": None}

            initiative_id = budget_item.get("strategy_initiative_id")
            if initiative_id:
                for init in strategic_initiatives:
                    if init.get("id") == initiative_id:
                        return {
                            "aligned": True,
                            "alignment_type": "initiative_id",
                            "matched_initiative": initiative_id,
                        }

            l1_code = budget_item.get("l1_code")
            budget_name = budget_item.get("budget_name", "").lower()

            for init in strategic_initiatives:
                init_l1 = init.get("l1_code")
                init_keywords = init.get("keywords", [])
                if init_l1 and l1_code and init_l1 == l1_code:
                    return {
                        "aligned": True,
                        "alignment_type": "l1_code",
                        "matched_initiative": init.get("id"),
                    }
                if init_keywords and any(kw in budget_name for kw in init_keywords):
                    return {
                        "aligned": True,
                        "alignment_type": "keyword",
                        "matched_initiative": init.get("id"),
                    }

            return {"aligned": False, "alignment_type": "none", "matched_initiative": None}
        except Exception as e:
            logger.error(f"Strategic alignment check failed: {e}")
            return {"aligned": False, "alignment_type": "none", "matched_initiative": None}

    async def calculate_strategic_coverage(self, db: AsyncSession) -> Dict[str, Any]:
        """Calculate strategic coverage: ratio of budget items/amounts with strategic alignment.

        Args:
            db: AsyncSession for database operations.

        Returns:
            Dict with item_coverage, amount_coverage, aligned_items, total_items.
        """
        try:
            stmt = select(BudgetItem)
            result = await db.execute(stmt)
            items = result.scalars().all()

            total_items = len(items)
            if total_items == 0:
                return {"item_coverage": 0.0, "amount_coverage": 0.0, "aligned_items": 0, "total_items": 0}

            aligned_items = 0
            aligned_amount = Decimal("0")
            total_amount = Decimal("0")

            for item in items:
                annual = item.annual_amount or Decimal("0")
                total_amount += annual
                # A budget item is considered strategically aligned if it has
                # a strategy_initiative_id or a strategic_intent_l1 value
                if item.strategy_initiative_id or item.strategic_intent_l1:
                    aligned_items += 1
                    aligned_amount += annual

            item_coverage = round(aligned_items / total_items, 4) if total_items > 0 else 0.0
            amount_coverage = round(float(aligned_amount) / float(total_amount), 4) if float(total_amount) > 0 else 0.0

            return {
                "item_coverage": item_coverage,
                "amount_coverage": amount_coverage,
                "aligned_items": aligned_items,
                "total_items": total_items,
            }
        except Exception as e:
            logger.error(f"Strategic coverage calculation failed: {e}")
            return {"item_coverage": 0.0, "amount_coverage": 0.0, "aligned_items": 0, "total_items": 0}

    async def calculate_strategic_budget_ratio(self, db: AsyncSession) -> List[Dict[str, Any]]:
        """Calculate budget ratio per strategic intent L1.

        Args:
            db: AsyncSession for database operations.

        Returns:
            List of dicts with intent, total_amount, ratio.
        """
        try:
            stmt = select(BudgetItem)
            result = await db.execute(stmt)
            items = result.scalars().all()

            intent_totals: Dict[str, Decimal] = {}
            grand_total = Decimal("0")

            for item in items:
                annual = item.annual_amount or Decimal("0")
                grand_total += annual
                intent = item.strategic_intent_l1 or "未分类"
                intent_totals[intent] = intent_totals.get(intent, Decimal("0")) + annual

            ratios = []
            for intent, total in intent_totals.items():
                ratio = round(float(total) / float(grand_total), 4) if float(grand_total) > 0 else 0.0
                ratios.append({
                    "intent": intent,
                    "total_amount": float(total),
                    "ratio": ratio,
                })

            ratios.sort(key=lambda x: x["total_amount"], reverse=True)
            return ratios
        except Exception as e:
            logger.error(f"Strategic budget ratio calculation failed: {e}")
            return []

    # === v4.1 新增：预算健康度评分 + 调拨影响模拟 ===

    async def calculate_budget_health_score(
        self, period: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """预算健康度评分（0-100，5 维度加权）

        - execution (25%)：各 L1 执行率偏离时间进度的程度
        - alignment (25%)：A 类执行率 + B→A 转换进度
        - risk (20%)：超支项数 + 红色预警数 + 敞口金额
        - transfer (15%)：调拨频次 + 调拨方向合理性
        - data (15%)：必填字段完整率 + 口径一致率
        """
        try:
            execution = await self._execution_health(period, db)
            alignment = await self._strategic_alignment_score(period, db)
            risk = await self._risk_exposure_score(period, db)
            transfer = await self._transfer_reasonability(period, db)
            data = await self._data_completeness(period, db)

            overall = (
                execution * 0.25 + alignment * 0.25 + risk * 0.20
                + transfer * 0.15 + data * 0.15
            )
            overall = round(max(0.0, min(100.0, overall)), 2)

            grade = (
                "A" if overall >= 85
                else "B" if overall >= 70
                else "C" if overall >= 55
                else "D"
            )

            dim_scores = {
                "execution": execution,
                "alignment": alignment,
                "risk": risk,
                "transfer": transfer,
                "data": data,
            }
            risk_factors = await self._collect_risk_factors(period, db, dim_scores)
            recommendations = self._generate_recommendations(overall, dim_scores, risk_factors)

            return {
                "overall_score": overall,
                "grade": grade,
                "dimension_scores": dim_scores,
                "period": period,
                "risk_factors": risk_factors,
                "recommendations": recommendations,
                "generated_at": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"[budget_health] 计算失败: {e}")
            return {
                "overall_score": 50.0,
                "grade": "C",
                "dimension_scores": {
                    "execution": 50, "alignment": 50, "risk": 50,
                    "transfer": 50, "data": 50,
                },
                "period": period,
                "risk_factors": [],
                "recommendations": ["健康度计算异常，请稍后重试"],
                "error": str(e),
            }

    async def _execution_health(self, period: str, db: AsyncSession) -> float:
        """执行健康度：所有 L1 在 period 的累计执行率与时间进度的偏离度评分

        返回 0-100。数据缺失时返回 50（中性）。
        """
        try:
            stmt = select(ExecutionRate).where(ExecutionRate.period == period)
            result = await db.execute(stmt)
            rates = result.scalars().all()
            if not rates:
                return 50.0

            year = int(period.split("-")[0]) if "-" in period else datetime.now().year
            month = int(period.split("-")[1]) if "-" in period else datetime.now().month
            time_progress = month / 12.0 * 100.0  # 时间进度百分比

            deviations: List[float] = []
            for r in rates:
                cum = float(r.cumulative_rate or 0)
                # 偏差 = |累计执行率 - 时间进度|
                deviation = abs(cum - time_progress)
                deviations.append(deviation)

            if not deviations:
                return 50.0
            avg_dev = sum(deviations) / len(deviations)
            # 偏离 0 → 100, ≤5pp → 90, ≤10pp → 75, ≤20pp → 55, >20pp → 30
            if avg_dev <= 1:
                score = 100.0
            elif avg_dev <= 5:
                score = 90.0
            elif avg_dev <= 10:
                score = 75.0
            elif avg_dev <= 20:
                score = 55.0
            else:
                score = 30.0
            return round(score, 2)
        except Exception as e:
            logger.warning(f"[budget_health] execution_health 失败: {e}")
            return 50.0

    async def _strategic_alignment_score(self, period: str, db: AsyncSession) -> float:
        """战略对齐度：A 类执行率 + 战略举措覆盖度"""
        try:
            # A 类预算项执行率均值
            stmt_a = (
                select(func.avg(ExecutionRate.cumulative_rate))
                .where(ExecutionRate.period == period)
                .join(BudgetItem, BudgetItem.l1_code == ExecutionRate.l1_code)
                .where(BudgetItem.budget_category == "A")
            )
            result_a = await db.execute(stmt_a)
            a_avg = result_a.scalar() or 0.0

            # 战略举措覆盖度
            coverage = await self.calculate_strategic_coverage(db)
            amount_coverage = float(coverage.get("amount_coverage", 0)) * 100.0

            score = (float(a_avg) * 0.6 + amount_coverage * 0.4)
            return round(max(0.0, min(100.0, score)), 2)
        except Exception as e:
            logger.warning(f"[budget_health] alignment_score 失败: {e}")
            return 50.0

    async def _risk_exposure_score(self, period: str, db: AsyncSession) -> float:
        """风险敞口：超支项数 + 敞口金额 → 评分（高分=低风险）"""
        try:
            stmt = select(ExecutionRate).where(ExecutionRate.period == period)
            result = await db.execute(stmt)
            rates = result.scalars().all()

            if not rates:
                return 60.0

            overrun_count = 0
            exposure_amount = Decimal("0")
            total_annual = Decimal("0")
            for r in rates:
                if r.cumulative_rate and float(r.cumulative_rate) > 100:
                    overrun_count += 1
                if r.annual_budget and r.cumulative_actual:
                    delta = Decimal(str(r.cumulative_actual)) - Decimal(str(r.annual_budget))
                    if delta > 0:
                        exposure_amount += delta
                if r.annual_budget:
                    total_annual += Decimal(str(r.annual_budget))

            exposure_ratio = float(exposure_amount / total_annual) if total_annual > 0 else 0.0

            # 超支项 > 5 → 40, ≤5 → 60, 0 → 80
            if overrun_count == 0 and exposure_ratio < 0.05:
                score = 90.0
            elif overrun_count <= 2 and exposure_ratio < 0.1:
                score = 75.0
            elif overrun_count <= 5 and exposure_ratio < 0.2:
                score = 55.0
            else:
                score = 30.0
            return round(score, 2)
        except Exception as e:
            logger.warning(f"[budget_health] risk_score 失败: {e}")
            return 50.0

    async def _transfer_reasonability(self, period: str, db: AsyncSession) -> float:
        """调拨合理性：调拨频次 + 调拨方向"""
        try:
            year = int(period.split("-")[0]) if "-" in period else datetime.now().year
            stmt = select(BudgetTransferRequest).where(
                func.extract("year", BudgetTransferRequest.created_at) == year
            )
            result = await db.execute(stmt)
            transfers = result.scalars().all()

            if not transfers:
                return 70.0  # 无调拨视为正常

            # 调拨频次：> 10 → 低分
            cnt = len(transfers)
            if cnt > 15:
                freq_score = 40.0
            elif cnt > 10:
                freq_score = 60.0
            elif cnt > 5:
                freq_score = 80.0
            else:
                freq_score = 90.0

            # 调拨方向合理性：稳定→发展 / 稳定→探索 视为合理
            reasonable_dir = 0
            for t in transfers:
                if t.from_quadrant in ("稳定", "收缩") and t.to_quadrant in ("发展", "探索"):
                    reasonable_dir += 1
                elif t.from_quadrant == t.to_quadrant:
                    reasonable_dir += 1
            dir_score = round(reasonable_dir / cnt * 100.0, 2) if cnt > 0 else 70.0

            return round(freq_score * 0.4 + dir_score * 0.6, 2)
        except Exception as e:
            logger.warning(f"[budget_health] transfer_score 失败: {e}")
            return 50.0

    async def _data_completeness(self, period: str, db: AsyncSession) -> float:
        """数据完整度：必填字段完整率 + 口径一致率"""
        try:
            stmt = select(BudgetItem)
            result = await db.execute(stmt)
            items = result.scalars().all()
            if not items:
                return 50.0

            required_fields = ["l1_code", "l2_code", "annual_amount", "quadrant", "budget_category", "center_id"]
            total = len(items)
            complete = 0
            for it in items:
                ok = all(getattr(it, f, None) not in (None, "", 0) for f in required_fields)
                if ok:
                    complete += 1
            return round(complete / total * 100.0, 2)
        except Exception as e:
            logger.warning(f"[budget_health] data_score 失败: {e}")
            return 50.0

    async def _collect_risk_factors(
        self, period: str, db: AsyncSession, dim_scores: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """收集风险因素"""
        factors: List[Dict[str, Any]] = []
        if dim_scores.get("execution", 100) < 60:
            factors.append({
                "factor": "执行率偏离时间进度较大",
                "severity": "high" if dim_scores["execution"] < 40 else "medium",
                "dimension": "execution",
            })
        if dim_scores.get("alignment", 100) < 60:
            factors.append({
                "factor": "战略对齐度不足（A 类执行率或战略覆盖度偏低）",
                "severity": "high" if dim_scores["alignment"] < 40 else "medium",
                "dimension": "alignment",
            })
        if dim_scores.get("risk", 100) < 60:
            factors.append({
                "factor": "存在超支项或敞口金额过大",
                "severity": "high" if dim_scores["risk"] < 40 else "medium",
                "dimension": "risk",
            })
        if dim_scores.get("transfer", 100) < 60:
            factors.append({
                "factor": "调拨频次过高或方向异常",
                "severity": "medium",
                "dimension": "transfer",
            })
        if dim_scores.get("data", 100) < 60:
            factors.append({
                "factor": "必填字段缺失率较高",
                "severity": "medium",
                "dimension": "data",
            })
        return factors

    def _generate_recommendations(
        self, overall: float, dim_scores: Dict[str, float], risk_factors: List[Dict]
    ) -> List[str]:
        """生成改进建议"""
        recs: List[str] = []
        if dim_scores.get("execution", 100) < 70:
            recs.append("建议召开月度执行率复盘会，对执行率 < 80% 的 L1 科目制定追赶计划")
        if dim_scores.get("alignment", 100) < 70:
            recs.append("建议提升 A 类预算执行优先级，并对 B→A 转换的里程碑进行季度跟踪")
        if dim_scores.get("risk", 100) < 70:
            recs.append("建议对超支项立即启动根因分析，并冻结非必要新增支出")
        if dim_scores.get("transfer", 100) < 70:
            recs.append("建议审视调拨合理性，避免同周期内频繁调拨")
        if dim_scores.get("data", 100) < 70:
            recs.append("建议补齐预算项必填字段，确保口径一致性")
        if overall >= 85:
            recs.append("整体健康度优秀，建议持续保持")
        elif not recs:
            recs.append("整体健康度良好，可适度优化执行节奏")
        return recs

    async def simulate_transfer_impact(
        self, from_id: str, to_id: str, amount: float, db: AsyncSession
    ) -> Dict[str, Any]:
        """模拟预算调拨的连锁影响

        返回：源/目标执行率变化 + 触发预警预测
        """
        try:
            from_item = await self._get_budget_item(from_id, db)
            to_item = await self._get_budget_item(to_id, db)
            if not from_item or not to_item:
                return {"error": "预算项不存在", "from_id": from_id, "to_id": to_id}

            from_before = await self._calc_current_rate(from_item, db)
            to_before = await self._calc_current_rate(to_item, db)

            from_after_budget = float(from_item.get("annual_amount", 0)) - amount
            to_after_budget = float(to_item.get("annual_amount", 0)) + amount
            from_after_rate = await self._calc_rate_after(from_item, from_after_budget, db)
            to_after_rate = await self._calc_rate_after(to_item, to_after_budget, db)

            predicted_alerts: List[Dict[str, Any]] = []
            if from_after_rate > 100:
                predicted_alerts.append({
                    "level": "red",
                    "item": from_id,
                    "item_name": from_item.get("budget_name", ""),
                    "reason": f"调拨后执行率 {from_after_rate:.1f}%，触发红色预警",
                })
            elif from_after_rate > 90:
                predicted_alerts.append({
                    "level": "yellow",
                    "item": from_id,
                    "item_name": from_item.get("budget_name", ""),
                    "reason": f"调拨后执行率 {from_after_rate:.1f}%，建议关注",
                })
            if to_after_rate < 30 and to_before >= 30:
                predicted_alerts.append({
                    "level": "yellow",
                    "item": to_id,
                    "item_name": to_item.get("budget_name", ""),
                    "reason": f"调拨后执行率 {to_after_rate:.1f}%，执行过慢",
                })

            # 调拨方向合理性
            from_quadrant = from_item.get("quadrant", "")
            to_quadrant = to_item.get("quadrant", "")
            direction_ok = (
                (from_quadrant in ("稳定", "收缩") and to_quadrant in ("发展", "探索"))
                or from_quadrant == to_quadrant
            )

            return {
                "from_item": {"id": from_id, "name": from_item.get("budget_name", ""), "quadrant": from_quadrant},
                "to_item": {"id": to_id, "name": to_item.get("budget_name", ""), "quadrant": to_quadrant},
                "amount": amount,
                "from_rate_change": {
                    "before": round(from_before, 2),
                    "after": round(from_after_rate, 2),
                    "delta_pp": round(from_after_rate - from_before, 2),
                },
                "to_rate_change": {
                    "before": round(to_before, 2),
                    "after": round(to_after_rate, 2),
                    "delta_pp": round(to_after_rate - to_before, 2),
                },
                "predicted_alerts": predicted_alerts,
                "direction_reasonable": direction_ok,
                "direction_note": "稳定/收缩 → 发展/探索，方向合理" if direction_ok else "调拨方向需审视",
            }
        except Exception as e:
            logger.error(f"[simulate_transfer_impact] 失败: {e}")
            return {"error": str(e), "from_id": from_id, "to_id": to_id, "amount": amount}

    async def _get_budget_item(self, item_id: str, db: AsyncSession) -> Optional[Dict[str, Any]]:
        """获取预算项（含累计执行率）"""
        try:
            stmt = select(BudgetItem).where(BudgetItem.budget_id == item_id)
            result = await db.execute(stmt)
            item = result.scalar_one_or_none()
            if not item:
                return None
            return {
                "budget_id": item.budget_id,
                "budget_name": item.budget_name,
                "l1_code": item.l1_code,
                "l2_code": item.l2_code,
                "quadrant": item.quadrant,
                "annual_amount": float(item.annual_amount or 0),
                "granted_amount": float(item.granted_amount or 0),
                "used_amount": float(item.used_amount or 0),
                "available_amount": float(item.available_amount or 0),
            }
        except Exception as e:
            logger.warning(f"[_get_budget_item] 失败: {e}")
            return None

    async def _calc_current_rate(self, item: Dict[str, Any], db: AsyncSession) -> float:
        """计算当前累计执行率（%），基于 used / annual"""
        annual = item.get("annual_amount", 0)
        used = item.get("used_amount", 0)
        if annual <= 0:
            return 0.0
        return round(used / annual * 100.0, 2)

    async def _calc_rate_after(
        self, item: Dict[str, Any], new_annual: float, db: AsyncSession
    ) -> float:
        """计算调拨后执行率（%）。假设 used 不变，annual 变化。"""
        if new_annual <= 0:
            return 999.0  # 异常高
        used = item.get("used_amount", 0)
        return round(used / new_annual * 100.0, 2)

    # ══════════════════════════════════════════════════════════════════════════
    # v12.1: 阶段 1 战略分解（战略主题 → 战略举措 → 预算项 自动拆分）
    # ══════════════════════════════════════════════════════════════════════════

    async def auto_decompose_strategy(
        self,
        theme: str,
        year: int,
        total_budget: float,
        strategic_intent_l1: Optional[str] = None,
        db: AsyncSession = None,
    ) -> Dict[str, Any]:
        """v12.1: 战略主题自动分解

        流程：
        1) 语义理解：解析 theme 中的战略意图关键词，推断 intent_l1
        2) 举措拆分：将主题拆解为 3-6 个战略举措，每个举措分配金额权重
        3) 预算生成：每个举措下生成 1-3 个预算项（L1 分类）
        4) 象限判定：根据 theme 关键词判定发展/稳定/收缩/探索
        5) A/B 分类：高确定性举措→A / 里程碑验证→B
        6) 关联追溯：记录 initiative_id → budget_item_id 映射（血缘）

        Returns:
            {
              "theme": "...",
              "year": 2026,
              "intent_l1": "...",
              "quadrant": "...",
              "total_budget": 10000000,
              "initiatives": [
                {
                  "initiative_id": "INI-XXX",
                  "name": "举措名称",
                  "description": "...",
                  "budget_weight_pct": 30.0,   # 占总预算比例
                  "allocated_amount": 3000000,   # 分配金额
                  "priority": "high",
                  "category": "A",
                  "milestones": ["Q1 启动", "Q3 完成验证"],  # 仅 B 类有
                  "kpi_target": "...",
                  "budget_items": [
                    {
                      "budget_id": "BG-XXX",
                      "budget_name": "...",
                      "l1_code": "01",
                      "amount": 1500000,
                      "quadrant": "...",
                      "category": "...",
                      "rationale": "..."
                    }
                  ]
                }
              ],
              "summary": {
                "total_initiatives": 4,
                "total_budget_items": 8,
                "category_a_count": 2,
                "category_b_count": 2,
                "quadrant_distribution": {"发展": 2, "稳定": 2},
                "confidence": 92.5,
              },
              "next_steps": ["提交管委会审批", "审批后自动生成 BudgetItem 记录"],
            }
        """
        try:
            # ── 1) 语义理解：关键词 → intent_l1 ──────────────────────
            keyword_map = {
                "全渠道商业化": ["商业化", "渠道", "销售", "市场", "推广", "品牌", "营销"],
                "创新研发": ["研发", "创新", "临床", "管线", "试验", "产品", "生物"],
                "国际化": ["国际", "出海", "海外", "BD", "License", "全球", "跨境"],
            }
            detected_intent = strategic_intent_l1
            if not detected_intent:
                for intent, keywords in keyword_map.items():
                    if any(kw in theme for kw in keywords):
                        detected_intent = intent
                        break
            if not detected_intent:
                detected_intent = "全渠道商业化"  # 默认

            # ── 2) 象限判定 ────────────────────────────────────────────
            growth_keywords = ["增长", "扩张", "发展", "加速", "突破", "高增长", "提速"]
            shrink_keywords = ["收缩", "削减", "优化", "精简", "控制成本", "降本"]
            explore_keywords = ["探索", "试点", "创新", "孵化", "新业务", "前沿", "早期"]

            quadrant = "稳定"
            if any(kw in theme for kw in growth_keywords):
                quadrant = "发展"
            elif any(kw in theme for kw in shrink_keywords):
                quadrant = "收缩"
            elif any(kw in theme for kw in explore_keywords):
                quadrant = "探索"

            # ── 3) 举措拆分 ─────────────────────────────────────────────
            # 基于 theme 语义 + intent 推断举措数量和命名
            initiative_configs = self._infer_initiatives(theme, detected_intent, quadrant)

            # ── 4) 金额分配 ────────────────────────────────────────────
            total = float(total_budget)
            # 按优先级分配权重
            weight_map = {"high": 0.35, "medium": 0.25, "low": 0.15}
            base_weights = [weight_map.get(ic["priority"], 0.25) for ic in initiative_configs]
            total_weight = sum(base_weights) or 1.0
            normalized_weights = [w / total_weight for w in base_weights]

            # ── 5) 预算项生成 + 血缘关联 ────────────────────────────────
            L1_CODE_MAP = {
                "全渠道商业化": ["01", "02", "03"],
                "创新研发": ["04", "05", "06"],
                "国际化": ["07", "08", "09"],
            }
            l1_codes = L1_CODE_MAP.get(detected_intent, ["01", "02", "03"])
            L1_NAME_MAP = {
                "01": "市场与渠道费用", "02": "销售管理费用", "03": "品牌推广费用",
                "04": "研发项目费用", "05": "临床试验费用", "06": "技术平台费用",
                "07": "国际市场费用", "08": "海外注册费用", "09": "BD与并购费用",
            }

            initiative_id_prefix = f"INI-{year}-"
            budget_id_prefix = f"BG-{year}-"

            initiatives = []
            total_allocated = Decimal("0")

            for i, config in enumerate(initiative_configs):
                ini_id = f"{initiative_id_prefix}{uuid.uuid4().hex[:6].upper()}"
                alloc_pct = float(normalized_weights[i] * 100)
                alloc_amount = round(total * normalized_weights[i], 0)
                total_allocated += Decimal(str(alloc_amount))

                # 每个举措生成 1-2 个预算项
                n_items = 2 if alloc_amount > total * 0.3 else 1
                budget_items = []
                for j in range(n_items):
                    bg_id = f"{budget_id_prefix}{uuid.uuid4().hex[:6].upper()}"
                    item_amount = round(alloc_amount / n_items, 0)
                    l1 = l1_codes[j % len(l1_codes)]
                    item_category = self._classify_ab_internal(
                        {"certainty": config["certainty"], "priority": config["priority"],
                         "annual_amount": item_amount}, db or object()
                    )
                    budget_items.append({
                        "budget_id": bg_id,
                        "budget_name": f"{config['name']}-{L1_NAME_MAP.get(l1, l1)}",
                        "l1_code": l1,
                        "l1_name": L1_NAME_MAP.get(l1, l1),
                        "amount": item_amount,
                        "quadrant": quadrant,
                        "category": item_category,
                        "rationale": (
                            f"从战略主题「{theme}」拆解而来，"
                            f"支撑举措「{config['name']}」，"
                            f"象限{quadrant}，优先级{config['priority']}"
                        ),
                        "strategy_initiative_id": ini_id,
                    })

                # B 类举措生成里程碑
                milestones = []
                if config["category"] == "B":
                    for q in ["Q1", "Q2", "Q3", "Q4"]:
                        milestones.append({
                            "quarter": q,
                            "description": f"{config['name']} {q} 里程碑",
                            "status": "未达成",
                        })

                initiatives.append({
                    "initiative_id": ini_id,
                    "name": config["name"],
                    "description": config["description"],
                    "budget_weight_pct": round(alloc_pct, 1),
                    "allocated_amount": alloc_amount,
                    "priority": config["priority"],
                    "category": config["category"],
                    "kpi_target": config.get("kpi_target", ""),
                    "milestones": milestones,
                    "budget_items": budget_items,
                })

            # ── 6) 汇总统计 ─────────────────────────────────────────────
            total_items = sum(len(ini["budget_items"]) for ini in initiatives)
            category_a = sum(1 for ini in initiatives if ini["category"] == "A")
            quad_dist: Dict[str, int] = {}
            for ini in initiatives:
                quad_dist[quadrant] = quad_dist.get(quadrant, 0) + 1

            # 计算置信度（基于输入完整度）
            confidence = 95.0
            if not strategic_intent_l1:
                confidence -= 5  # 未指定 intent_l1
            if total_budget < 100000:
                confidence -= 10  # 金额过小

            steps = [
                {"step": "perceive", "detail": f"感知战略主题「{theme}」，意图识别为{detected_intent}，象限{quadrant}"},
                {"step": "reason", "detail": f"拆解为{len(initiatives)}个举措，{total_items}个预算项，按优先级分配权重"},
                {"step": "plan", "detail": f"A类{category_a}个（高确定性）/ B类{len(initiatives)-category_a}个（里程碑验证）/ 总金额¥{total:,.0f}"},
                {"step": "execute", "detail": "生成预算项预填数据，待管委会审批后写入数据库"},
            ]

            conclusion = (
                f"战略主题「{theme}」分解完成："
                f"{len(initiatives)}个举措 → {total_items}个预算项，"
                f"总预算¥{total:,.0f}，置信度{confidence}%"
            )

            return {
                "theme": theme,
                "year": year,
                "intent_l1": detected_intent,
                "quadrant": quadrant,
                "total_budget": total,
                "initiatives": initiatives,
                "summary": {
                    "total_initiatives": len(initiatives),
                    "total_budget_items": total_items,
                    "category_a_count": category_a,
                    "category_b_count": len(initiatives) - category_a,
                    "quadrant_distribution": quad_dist,
                    "confidence": confidence,
                },
                "decomposition_rationale": {
                    "intent_based_on": "theme keyword analysis" if not strategic_intent_l1 else "user specified",
                    "quadrant_based_on": "theme keyword analysis",
                    "weights_based_on": "priority levels (high=35%/medium=25%/low=15%)",
                },
                "next_steps": [
                    "① 人工确认分解结果（如需调整举措或金额，点击编辑）",
                    "② 提交管委会审批",
                    "③ 审批通过后，点击「一键生成预算」写入数据库",
                ],
                "_trace": {
                    "scene_name": f"战略分解-{theme[:10]}",
                    "steps": steps,
                    "conclusion": conclusion,
                    "confidence": confidence,
                    "rule_ids": ["HR-AB-001", "HR-QD-001"],
                },
            }
        except Exception as e:
            logger.error(f"auto_decompose_strategy 失败: {e}")
            raise

    def _infer_initiatives(
        self, theme: str, intent_l1: str, quadrant: str
    ) -> List[Dict[str, Any]]:
        """基于 theme/intent/quadrant 语义推断举措配置列表（数量+命名+优先级+类别）"""
        configs: List[Dict[str, Any]] = []

        # 商业化类举措模板
        if intent_l1 == "全渠道商业化":
            configs = [
                {"name": f"{theme}-核心市场深耕", "description": "聚焦核心城市医院覆盖与准入，提升终端覆盖率", "priority": "high", "certainty": "high", "category": "A", "kpi_target": "覆盖医院数 +20%"},
                {"name": f"{theme}-数字化营销", "description": "搭建数字化患者触达与随访体系", "priority": "high", "certainty": "medium", "category": "B", "kpi_target": "数字渠道患者触达 +50%"},
                {"name": f"{theme}-品牌影响力建设", "description": "医学教育活动与 KOL 合作网络", "priority": "medium", "certainty": "high", "category": "A", "kpi_target": "医学会议参与 +30%"},
                {"name": f"{theme}-渠道下沉拓展", "description": "拓展下沉市场第三终端覆盖", "priority": "medium", "certainty": "low", "category": "B", "kpi_target": "下沉市场销售 +25%"},
            ]
        elif intent_l1 == "创新研发":
            configs = [
                {"name": f"{theme}-核心管线推进", "description": "重点临床项目入组与数据锁库", "priority": "high", "certainty": "high", "category": "A", "kpi_target": "III期入组完成率 100%"},
                {"name": f"{theme}-早期项目探索", "description": "新技术平台与靶点探索研究", "priority": "medium", "certainty": "low", "category": "B", "kpi_target": "2个新靶点验证"},
                {"name": f"{theme}-临床运营效率提升", "description": "临床运营数字化与流程优化", "priority": "medium", "certainty": "medium", "category": "B", "kpi_target": "入组速度 +15%"},
            ]
        elif intent_l1 == "国际化":
            configs = [
                {"name": f"{theme}-重点市场准入", "description": "目标市场 NDA 申报与商业化准备", "priority": "high", "certainty": "high", "category": "A", "kpi_target": "1个市场获批"},
                {"name": f"{theme}-国际合作网络", "description": "BD 合作与 license-out 推进", "priority": "medium", "certainty": "medium", "category": "B", "kpi_target": "签署1项BD协议"},
                {"name": f"{theme}-海外商业化布局", "description": "海外子公司设立与团队搭建", "priority": "low", "certainty": "low", "category": "B", "kpi_target": "建立1个海外子公司"},
            ]

        # 调整：收缩象限减少举措数量，降低高优先级比例
        if quadrant == "收缩":
            configs = [
                {"name": f"{theme}-核心业务维持", "description": "保住核心市场与关键客户", "priority": "high", "certainty": "high", "category": "A", "kpi_target": "核心销售不下降"},
                {"name": f"{theme}-成本优化行动", "description": "降本增效，结构性费用压缩", "priority": "high", "certainty": "high", "category": "A", "kpi_target": "费用率 -5pp"},
            ]
        elif quadrant == "探索":
            # 探索增加一个创新试点
            configs.append({
                "name": f"{theme}-创新试点", "description": "探索新商业模式或技术方向", "priority": "low", "certainty": "low", "category": "B", "kpi_target": "完成1个试点项目",
            })

        return configs[:6]  # 最多 6 个举措

    async def create_budget_from_decomposition(
        self,
        decomposition: Dict[str, Any],
        db: AsyncSession,
        year: Optional[int] = None,
    ) -> Dict[str, Any]:
        """v12.1: 将战略分解结果批量写入 BudgetItem 表

        遍历 decomposition['initiatives'][*]['budget_items']，
        跳过已存在的 budget_id（如已有则跳过），
        写入数据库并返回创建结果。
        """
        try:
            created_items: List[Dict[str, Any]] = []
            skipped_items: List[Dict[str, Any]] = []
            created_initiatives: List[Dict[str, Any]] = []

            for ini in decomposition.get("initiatives", []):
                ini_id = ini.get("initiative_id", f"INI-{uuid.uuid4().hex[:6].upper()}")
                ini_obj = await db.execute(
                    select(StrategicInitiative).where(
                        StrategicInitiative.initiative_id == ini_id
                    )
                )
                existing_ini = ini_obj.scalars().first()

                if not existing_ini:
                    new_ini = StrategicInitiative(
                        initiative_id=ini_id,
                        initiative_name=ini["name"],
                        strategic_intent_l1=decomposition.get("intent_l1"),
                        owner_center=ini.get("center", "待定"),
                        owner_manager=ini.get("owner", "待定"),
                        kpi_target=Decimal(str(ini.get("kpi_target", "0"))),
                        budget_allocated=Decimal(str(ini.get("allocated_amount", 0))),
                        status="规划中",
                    )
                    db.add(new_ini)
                    created_initiatives.append({"initiative_id": ini_id, "name": ini["name"]})

                for bi in ini.get("budget_items", []):
                    bg_id = bi.get("budget_id", f"BG-{uuid.uuid4().hex[:6].upper()}")
                    existing_budget = await db.get(BudgetItem, bg_id)
                    if existing_budget:
                        skipped_items.append({"budget_id": bg_id, "name": bi.get("budget_name")})
                        continue

                    budget_item = BudgetItem(
                        budget_id=bg_id,
                        budget_name=bi.get("budget_name", ""),
                        budget_category=bi.get("category", "B"),
                        l1_code=bi.get("l1_code", "00"),
                        quadrant=bi.get("quadrant", decomposition.get("quadrant", "稳定")),
                        strategy_initiative_id=ini_id,
                        annual_amount=Decimal(str(bi.get("amount", 0))),
                        granted_amount=Decimal("0"),
                        frozen_amount=Decimal("0"),
                        used_amount=Decimal("0"),
                        available_amount=Decimal("0"),
                        grant_percentage=Decimal("0"),
                        status="编制中",
                        center_id=bi.get("center_id"),
                    )
                    db.add(budget_item)
                    created_items.append({"budget_id": bg_id, "name": bi.get("budget_name")})

            # 记录 trace
            trace_id = f"RT-DEC-{uuid.uuid4().hex[:8].upper()}"
            trace = ReasoningTrace(
                trace_id=trace_id,
                scene_name=f"战略分解-{decomposition.get('theme', '')[:10]}",
                input_data=json.dumps({
                    "theme": decomposition.get("theme"),
                    "year": decomposition.get("year"),
                    "total_budget": decomposition.get("total_budget"),
                    "initiative_count": len(created_initiatives),
                }, ensure_ascii=False),
                steps=json.dumps(decomposition.get("_trace", {}).get("steps", []), ensure_ascii=False, default=str),
                conclusion=decomposition.get("_trace", {}).get("conclusion", ""),
                confidence=Decimal(str(decomposition.get("summary", {}).get("confidence", 85))),
                rule_ids=json.dumps(["HR-AB-001", "HR-QD-001"], ensure_ascii=False),
            )
            db.add(trace)
            await db.flush()

            return {
                "success": True,
                "created_initiatives": len(created_initiatives),
                "created_budget_items": len(created_items),
                "skipped_budget_items": len(skipped_items),
                "initiative_ids": [i["initiative_id"] for i in created_initiatives],
                "budget_ids": [i["budget_id"] for i in created_items],
                "skipped": skipped_items,
            }
        except Exception as e:
            logger.error(f"create_budget_from_decomposition 失败: {e}")
            raise

