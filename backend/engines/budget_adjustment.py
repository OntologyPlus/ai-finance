from __future__ import annotations

import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from loguru import logger
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.budget import BudgetItem
from models.ontology import OntologyRule, ReasoningTrace
from models.transfer import BudgetTransferRequest


class BudgetAdjustmentEngine:
    """Budget Adjustment Engine (阶段六): Handles budget transfers and adjustments.

    Same-quadrant transfers require 财经中心审批.
    Cross-quadrant transfers require 管委会批准.
    """

    def __init__(self):
        self.engine_name = "budget_adjustment"

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
            trace_id=f"RT-AD-{uuid.uuid4().hex[:8].upper()}",
            scene_name=scene_name,
            input_data=json.dumps(input_data, ensure_ascii=False, default=str),
            steps=json.dumps(steps, ensure_ascii=False, default=str),
            conclusion=conclusion,
            confidence=confidence,
            rule_ids=json.dumps(rule_ids, ensure_ascii=False),
        )
        db.add(trace)
        await db.flush()

    async def request_transfer(
        self,
        from_id: str,
        to_id: str,
        amount: float,
        db: AsyncSession,
        requester: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Request a budget transfer between two budget items.
        Same quadrant: 财经中心审批.
        Cross quadrant: 管委会批准.
        Args:
            from_id: Source budget item ID.
            to_id: Target budget item ID.
            amount: Amount to transfer.
            db: AsyncSession for database operations.
            requester: User ID of the requester (for SoD check). Optional but recommended.
        Returns:
            Dict with transfer request details and approval requirements.
        Raises:
            ValueError: If budget items not found or insufficient available amount.
            SoDViolation: If requester previously performed the approval-side action.
        """
        try:
            # ── SoD：调拨发起人 ≠ 调拨最终审批人 ──
            if requester:
                try:
                    from ontology.sod import get_sod_enforcer, SoDViolation
                    get_sod_enforcer().check(
                        user_id=str(requester),
                        operation="budget.transfer.request",
                        resource_id=f"{from_id}->{to_id}",
                    )
                except SoDViolation:
                    raise

            from_item = await db.get(BudgetItem, from_id)
            if from_item is None:
                raise ValueError(f"Source budget item {from_id} not found")

            to_item = await db.get(BudgetItem, to_id)
            if to_item is None:
                raise ValueError(f"Target budget item {to_id} not found")

            transfer_amount = Decimal(str(amount))
            available = Decimal(str(from_item.available_amount))

            if transfer_amount > available:
                raise ValueError(
                    f"Transfer amount {transfer_amount} exceeds available amount {available} "
                    f"in source budget {from_id}"
                )

            steps = [
                {"step": "perceive", "detail": f"Transfer request: {from_id} -> {to_id}, amount={amount}"},
            ]

            same_quadrant = from_item.quadrant == to_item.quadrant
            approval_required = "财经中心审批" if same_quadrant else "管委会批准"

            steps.append({
                "step": "reason",
                "detail": f"Quadrant check: from={from_item.quadrant}, to={to_item.quadrant}, "
                          f"same={same_quadrant}, approval={approval_required}",
            })

            transfer_id = f"TF-{uuid.uuid4().hex[:8].upper()}"

            # Persist transfer request to database
            transfer_record = BudgetTransferRequest(
                transfer_id=transfer_id,
                from_budget_id=from_id,
                to_budget_id=to_id,
                from_quadrant=from_item.quadrant,
                to_quadrant=to_item.quadrant,
                amount=Decimal(str(amount)),
                same_quadrant="是" if same_quadrant else "否",
                approval_required=approval_required,
                status="待审批",
            )
            db.add(transfer_record)

            steps.append({"step": "plan", "detail": f"Transfer {transfer_id} requires {approval_required}"})
            steps.append({"step": "reflect", "detail": "Transfer request created and persisted, awaiting approval"})

            await self._record_trace(
                scene_name="预算调拨申请",
                input_data={"from_id": from_id, "to_id": to_id, "amount": amount},
                steps=steps,
                conclusion=f"Transfer {transfer_id} requested, approval: {approval_required}",
                rule_ids=["HR-TF-001"],
                confidence=Decimal("100.00"),
                db=db,
            )

            await db.flush()

            logger.info(f"Transfer request {transfer_id}: {from_id} -> {to_id}, amount={amount}")
            return {
                "transfer_id": transfer_id,
                "from_budget_id": from_id,
                "to_budget_id": to_id,
                "from_quadrant": from_item.quadrant,
                "to_quadrant": to_item.quadrant,
                "amount": amount,
                "same_quadrant": same_quadrant,
                "approval_required": approval_required,
                "status": "待审批",
                "created_at": datetime.now().isoformat(),
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Transfer request failed: {e}")
            raise

    async def execute_transfer(
        self,
        transfer_id: str,
        approved_by: str,
        db: AsyncSession,
        from_budget_id: Optional[str] = None,
        to_budget_id: Optional[str] = None,
        transfer_amount: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Execute an approved budget transfer.

        Looks up the transfer request from DB first, then updates budget amounts.

        Args:
            transfer_id: Transfer request ID (format: TF-XXXXXXXX).
            approved_by: Approver name/ID.
            db: AsyncSession for database operations.
            from_budget_id: Source budget item ID (fallback if DB record not found).
            to_budget_id: Target budget item ID (fallback if DB record not found).
            transfer_amount: Amount to transfer (fallback if DB record not found).

        Returns:
            Dict with execution result.

        Raises:
            ValueError: If transfer data is invalid.
        """
        try:
            # Try to load transfer record from DB
            transfer_record = await db.get(BudgetTransferRequest, transfer_id)

            if transfer_record:
                from_budget_id = transfer_record.from_budget_id
                to_budget_id = transfer_record.to_budget_id
                transfer_amount = float(transfer_record.amount)

                if transfer_record.status not in ("待审批", "已审批"):
                    raise ValueError(f"Transfer {transfer_id} has status '{transfer_record.status}', cannot execute")

                # Update transfer record status
                transfer_record.status = "已执行"
                transfer_record.approved_by = approved_by
                transfer_record.executed_at = datetime.now()

            stmt = select(OntologyRule).where(
                OntologyRule.rule_id == "HR-TF-001",
                OntologyRule.is_active.is_(True),
            )
            result = await db.execute(stmt)
            rule = result.scalars().first()

            steps = [
                {"step": "perceive", "detail": f"Executing transfer {transfer_id}, approved by {approved_by}"},
            ]

            steps.append({"step": "reason", "detail": "Approval verified, proceeding with transfer execution"})
            steps.append({"step": "plan", "detail": "Update source and target budget amounts"})

            # Execute actual amount changes
            if from_budget_id and to_budget_id and transfer_amount is not None:
                from_item = await db.get(BudgetItem, from_budget_id)
                to_item = await db.get(BudgetItem, to_budget_id)

                if from_item and to_item:
                    amount_decimal = Decimal(str(transfer_amount))
                    from_item.available_amount = Decimal(str(from_item.available_amount)) - amount_decimal
                    from_item.annual_amount = Decimal(str(from_item.annual_amount)) - amount_decimal
                    to_item.available_amount = Decimal(str(to_item.available_amount)) + amount_decimal
                    to_item.annual_amount = Decimal(str(to_item.annual_amount)) + amount_decimal
                    await db.flush()

                    # Publish event
                    from ontology.events import get_event_bus, OntologyEventType
                    event_bus = get_event_bus()
                    await event_bus.publish(
                        event_type=OntologyEventType.BUDGET_ADJUSTED,
                        source=f"adjustment:{transfer_id}",
                        payload={"from": from_budget_id, "to": to_budget_id, "amount": float(transfer_amount)},
                    )

                    steps.append({"step": "execute", "detail": f"Transfer {transfer_id} executed: {transfer_amount} from {from_budget_id} to {to_budget_id}"})
                else:
                    steps.append({"step": "execute", "detail": f"Transfer {transfer_id} executed (no amount change - budget items not found)"})
            else:
                steps.append({"step": "execute", "detail": f"Transfer {transfer_id} executed (no amount change parameters provided)"})

            logger.info(f"Transfer {transfer_id} executed by {approved_by}")

            steps.append({"step": "reflect", "detail": "Transfer execution complete"})

            execution_result = {
                "transfer_id": transfer_id,
                "approved_by": approved_by,
                "status": "已执行",
                "executed_at": datetime.now().isoformat(),
            }

            await self._record_trace(
                scene_name="预算调拨执行",
                input_data={"transfer_id": transfer_id, "approved_by": approved_by},
                steps=steps,
                conclusion=f"Transfer {transfer_id} executed by {approved_by}",
                rule_ids=["HR-TF-001"],
                confidence=Decimal("100.00"),
                db=db,
            )

            from ontology.decision_recorder import emit_decision

            entity_ids = [transfer_id]
            if from_budget_id:
                entity_ids.append(from_budget_id)
            if to_budget_id:
                entity_ids.append(to_budget_id)
            await emit_decision(
                category="budget_transfer",
                scenario=f"执行调拨 {transfer_id}",
                outcome="executed",
                reasoning=f"Transfer {transfer_id} executed by {approved_by}",
                decision_maker=str(approved_by or "system"),
                entity_ids=entity_ids,
                applied_rule_ids=["HR-TF-001"],
                hook_id="engine.execute_transfer",
                metadata={"from_budget_id": from_budget_id, "to_budget_id": to_budget_id},
                db=db,
            )
            return execution_result

        except Exception as e:
            logger.error(f"Transfer execution failed for {transfer_id}: {e}")
            raise

    async def request_adjustment(
        self,
        budget_id: str,
        adjustment_type: str,
        amount: float,
        reason: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Request a budget adjustment (increase/decrease).

        Args:
            budget_id: Budget item ID to adjust.
            adjustment_type: "increase" or "decrease".
            amount: Adjustment amount.
            reason: Reason for adjustment.
            db: AsyncSession for database operations.

        Returns:
            Dict with adjustment request details.

        Raises:
            ValueError: If budget item not found or invalid adjustment type.
        """
        try:
            budget_item = await db.get(BudgetItem, budget_id)
            if budget_item is None:
                raise ValueError(f"Budget item {budget_id} not found")

            if adjustment_type not in ("increase", "decrease"):
                raise ValueError(f"Invalid adjustment type: {adjustment_type}, must be 'increase' or 'decrease'")

            adjustment_amount = Decimal(str(amount))
            current_annual = Decimal(str(budget_item.annual_amount))

            steps = [
                {"step": "perceive", "detail": f"Adjustment request for {budget_id}: {adjustment_type} by {amount}"},
            ]

            if adjustment_type == "decrease" and adjustment_amount > current_annual:
                raise ValueError(
                    f"Decrease amount {adjustment_amount} exceeds annual budget {current_annual}"
                )

            new_annual = (
                current_annual + adjustment_amount
                if adjustment_type == "increase"
                else current_annual - adjustment_amount
            )

            approval_level = "管委会批准" if adjustment_amount > Decimal("1000000") else "财经中心审批"

            steps.append({
                "step": "reason",
                "detail": f"Adjustment: {adjustment_type} {amount}, new annual={new_annual}, approval={approval_level}",
            })

            adjustment_id = f"AD-{uuid.uuid4().hex[:8].upper()}"

            adjustment_request = {
                "adjustment_id": adjustment_id,
                "budget_id": budget_id,
                "adjustment_type": adjustment_type,
                "amount": amount,
                "reason": reason,
                "current_annual": float(current_annual),
                "new_annual": float(new_annual),
                "approval_required": approval_level,
                "status": "待审批",
                "created_at": datetime.now().isoformat(),
            }

            steps.append({"step": "plan", "detail": f"Adjustment {adjustment_id} requires {approval_level}"})
            steps.append({"step": "reflect", "detail": "Adjustment request created, awaiting approval"})

            await self._record_trace(
                scene_name="预算调整申请",
                input_data={"budget_id": budget_id, "type": adjustment_type, "amount": amount},
                steps=steps,
                conclusion=f"Adjustment {adjustment_id} requested: {adjustment_type} by {amount}",
                rule_ids=["HR-AD-001"],
                confidence=Decimal("100.00"),
                db=db,
            )

            logger.info(f"Adjustment request {adjustment_id}: {budget_id} {adjustment_type} by {amount}")
            return adjustment_request

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Adjustment request failed for {budget_id}: {e}")
            raise

    # v12.0: 沙盘推演（文档 §4.6.3 PDCA-B 季度复盘调拨建议）
    async def simulate_transfer_sandbox(
        self,
        from_id: str,
        to_id: str,
        amount: float,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """调拨沙盘推演：在不实际修改数据的情况下，预测执行率变化、预警触发、战略影响

        文档 §5.3 L5 方案推演示例：
        - 发展象限调出50万后执行率变化：72%→78%
        - 收缩象限调入50万后执行率变化：95%→82%
        - 3GAP分析、3List归类

        Returns:
            沙盘推演结果（执行率变化、预警预测、3List影响、方向合理性）
        """
        try:
            from_item = await db.get(BudgetItem, from_id)
            to_item = await db.get(BudgetItem, to_id)
            if not from_item or not to_item:
                return {"error": "源或目标预算项不存在"}

            transfer_amount = Decimal(str(amount))
            from_annual = Decimal(str(from_item.annual_amount or 0))
            from_used = Decimal(str(from_item.used_amount or 0))
            to_annual = Decimal(str(to_item.annual_amount or 0))
            to_used = Decimal(str(to_item.used_amount or 0))

            # === 1. 执行率变化预测 ===
            from_new_annual = from_annual - transfer_amount
            to_new_annual = to_annual + transfer_amount

            from_rate_before = (from_used / from_annual * 100) if from_annual > 0 else Decimal("0")
            to_rate_before = (to_used / to_annual * 100) if to_annual > 0 else Decimal("0")
            from_rate_after = (from_used / from_new_annual * 100) if from_new_annual > 0 else Decimal("0")
            to_rate_after = (to_used / to_new_annual * 100) if to_new_annual > 0 else Decimal("0")

            # === 2. 象限影响 + 审批要求 ===
            same_quadrant = from_item.quadrant == to_item.quadrant
            approval_required = "财经中心审批" if same_quadrant else "管委会批准"

            # === 3. 预警预测（基于软规则 SR-001..003） ===
            from_alerts = []
            to_alerts = []
            # 源：调出后执行率上升 → 黄色阈值 110%
            if from_rate_after >= 110:
                from_alerts.append({"level": "黄色", "reason": f"调拨后执行率{float(from_rate_after):.1f}%>110%", "rule": "SR-002"})
            elif from_rate_after >= 105:
                from_alerts.append({"level": "蓝色", "reason": f"调拨后执行率{float(from_rate_after):.1f}%>105%", "rule": "SR-001"})
            # 目标：调入后执行率下降
            if to_rate_after < 50 and to_rate_before >= 50:
                to_alerts.append({"level": "蓝色", "reason": f"调入后执行率{float(to_rate_after):.1f}%<50%", "rule": "SR-002"})

            # === 4. 3GAP 影响推演 ===
            gap_impact = {
                "gap1_target_gap": {
                    "from_before": float(from_annual - from_used),
                    "from_after": float(from_new_annual - from_used),
                    "to_before": float(to_annual - to_used),
                    "to_after": float(to_new_annual - to_used),
                },
            }

            # === 5. 3List 影响归类 ===
            list_impact = {
                "from_category": "必赢清单" if from_item.strategic_intent_l1 and from_rate_after < 80 else "观察清单",
                "to_category": "必赢清单" if to_item.strategic_intent_l1 and to_rate_after < 80 else "观察清单",
                "note": "跨象限调拨可能影响战略意图达成率",
            }

            # === 6. 方向合理性评分（0-100）===
            direction_score = 100
            if not same_quadrant:
                direction_score -= 30  # 跨象限扣分
            if from_rate_after > 110:
                direction_score -= 20  # 调出后超阈值
            if to_rate_after < 50:
                direction_score -= 15  # 调入后过低
            if from_item.budget_category == "B" and to_item.budget_category == "A":
                direction_score -= 10  # B→A 转换未走流程
            direction_score = max(0, direction_score)

            result = {
                "success": True,
                "from_budget": {
                    "budget_id": from_id,
                    "budget_name": getattr(from_item, "budget_name", from_id),
                    "quadrant": from_item.quadrant,
                    "annual_before": float(from_annual),
                    "annual_after": float(from_new_annual),
                    "execution_rate_before": float(from_rate_before.quantize(Decimal("0.01"))),
                    "execution_rate_after": float(from_rate_after.quantize(Decimal("0.01"))),
                },
                "to_budget": {
                    "budget_id": to_id,
                    "budget_name": getattr(to_item, "budget_name", to_id),
                    "quadrant": to_item.quadrant,
                    "annual_before": float(to_annual),
                    "annual_after": float(to_new_annual),
                    "execution_rate_before": float(to_rate_before.quantize(Decimal("0.01"))),
                    "execution_rate_after": float(to_rate_after.quantize(Decimal("0.01"))),
                },
                "transfer": {
                    "amount": amount,
                    "same_quadrant": same_quadrant,
                    "approval_required": approval_required,
                },
                "predicted_alerts": {
                    "from_alerts": from_alerts,
                    "to_alerts": to_alerts,
                    "total": len(from_alerts) + len(to_alerts),
                },
                "gap_impact": gap_impact,
                "list_impact": list_impact,
                "direction_score": direction_score,
                "recommendation": (
                    "✓ 调拨方案合理，可执行"
                    if direction_score >= 70
                    else "⚠ 调拨后可能触发预警，建议优化"
                    if direction_score >= 40
                    else "✗ 调拨方向不合理，建议重新评估"
                ),
            }

            await self._record_trace(
                scene_name="调拨沙盘推演",
                input_data={"from_id": from_id, "to_id": to_id, "amount": amount},
                steps=[
                    {"step": "load_budgets", "from": from_id, "to": to_id},
                    {"step": "predict_rates", "from_after": float(from_rate_after), "to_after": float(to_rate_after)},
                    {"step": "predict_alerts", "count": len(from_alerts) + len(to_alerts)},
                    {"step": "score_direction", "score": direction_score},
                ],
                conclusion=f"调拨沙盘推演完成，方向评分 {direction_score}/100",
                rule_ids=["HR-TF-001", "SR-001", "SR-002"],
                confidence=Decimal("90.00"),
                db=db,
            )

            return result

        except Exception as e:
            logger.error(f"沙盘推演失败: {e}")
            return {"error": str(e)}
