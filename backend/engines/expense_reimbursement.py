from __future__ import annotations

import json
import uuid
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.budget import BudgetItem, BudgetSubjectL3, ControlMode
from models.expense import ExpenseReport, InvoiceRecord, BudgetWriteOff
from models.ontology import OntologyRule, ReasoningTrace
from models.budget_occupation import BudgetOccupation


class ExpenseReimbursementEngine:
    """Expense Reimbursement Engine (阶段三): Handles the complete 9-step reimbursement flow.

    Steps:
    1. Budget ID validation (HR-001: no budget ID -> reject)
    2. L3 control tag identification
    3. Four-level control routing
    4. Budget sufficiency check (HR-002)
    5. Invoice dedup check
    6. Create expense report with approval routing
    7-9. Approval, write-off, alert check (handled by other engines)
    """

    def __init__(self):
        self.engine_name = "expense_reimbursement"

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
            trace_id=f"RT-ER-{uuid.uuid4().hex[:8].upper()}",
            scene_name=scene_name,
            input_data=json.dumps(input_data, ensure_ascii=False, default=str),
            steps=json.dumps(steps, ensure_ascii=False, default=str),
            conclusion=conclusion,
            confidence=confidence,
            rule_ids=json.dumps(rule_ids, ensure_ascii=False),
        )
        db.add(trace)
        await db.flush()

    async def submit_expense(
        self, expense_data: Dict[str, Any], db: AsyncSession
    ) -> ExpenseReport:
        """Submit an expense report through the 6-step validation flow.

        Steps 1-6 are handled here; steps 7-9 are delegated to other engines.

        Args:
            expense_data: Expense submission data including budget_id, amount, etc.
            db: AsyncSession for database operations.

        Returns:
            Created ExpenseReport with approval routing.

        Raises:
            ValueError: If any validation step fails.
        """
        try:
            steps = []

            # ── SoD：报销发起人 ≠ 报销最终审批人 ──
            # 阻断同一人对同一报销单（resource_id）既发起又审批的自批自核风险。
            try:
                from ontology.sod import get_sod_enforcer
                submitter = (
                    expense_data.get("submitter")
                    or expense_data.get("user_id")
                    or expense_data.get("employee_id")
                )
                if submitter:
                    get_sod_enforcer().check(
                        user_id=str(submitter),
                        operation="expense.submit",
                        resource_id=str(expense_data.get("expense_id") or expense_data.get("report_id") or ""),
                    )
            except Exception as _sod_err:
                # SoDViolation 重新抛；其它异常（如 import 失败）只 warn 不阻断
                from ontology.sod import SoDViolation
                if isinstance(_sod_err, SoDViolation):
                    raise

            budget_id = expense_data.get("budget_id")
            budget_item = await db.get(BudgetItem, budget_id) if budget_id else None
            from ontology.rules.hard_rules import HardRuleEngine
            from ontology.decision_recorder import emit_decision

            hr001 = HardRuleEngine().execute(
                "HR-001",
                {"budget_id": budget_id, "has_budget": budget_item is not None},
            )
            if hr001.output == "BLOCK":
                steps.append({"step": 1, "result": "rejected", "rule": "HR-001", "detail": hr001.reasoning})
                await self._record_trace(
                    scene_name="费用报销提交",
                    input_data=expense_data,
                    steps=steps,
                    conclusion="Rejected: no budget ID (HR-001)",
                    rule_ids=["HR-001"],
                    confidence=Decimal("100.00"),
                    db=db,
                )
                msg = (
                    "HR-001: 报销必须关联预算项目，未提供预算ID"
                    if not budget_id
                    else f"HR-001: 预算项目不存在: {budget_id}"
                )
                await emit_decision(
                    category="expense_submit",
                    scenario="提交报销：无有效预算ID",
                    outcome="blocked",
                    reasoning=hr001.reasoning,
                    decision_maker=str(expense_data.get("applicant_id") or "system"),
                    entity_ids=[eid for eid in (expense_data.get("expense_id"),) if eid],
                    applied_rule_ids=["HR-001"],
                    hook_id="engine.submit_expense",
                    metadata={"budget_id": budget_id},
                    db=db,
                )
                raise ValueError(msg)

            steps.append({"step": 1, "result": "passed", "detail": f"Budget ID validated: {budget_id}"})

            expense_date_val = expense_data.get("expense_date")
            if expense_date_val is not None:
                if isinstance(expense_date_val, str):
                    expense_date_parsed = datetime.strptime(expense_date_val, "%Y-%m-%d").date()
                elif isinstance(expense_date_val, datetime):
                    expense_date_parsed = expense_date_val.date()
                elif isinstance(expense_date_val, date):
                    expense_date_parsed = expense_date_val
                else:
                    expense_date_parsed = None

                if expense_date_parsed is not None:
                    today = date.today()
                    expense_year = expense_date_parsed.year
                    submit_year = today.year
                    time_limit_exceeded = False
                    time_limit_reason = ""

                    if expense_year < submit_year:
                        deadline = date(submit_year, 3, 31)
                        if today > deadline:
                            time_limit_exceeded = True
                            time_limit_reason = f"跨年度费用须在次年3月31日前报销，费用发生日期{expense_date_parsed}，截止日期{deadline}"
                    else:
                        max_allowed = expense_date_parsed + timedelta(days=90)
                        if today > max_allowed:
                            time_limit_exceeded = True
                            time_limit_reason = f"费用发生日期距今超过3个月，费用发生日期{expense_date_parsed}，最迟报销日期{max_allowed}"

                    if time_limit_exceeded:
                        steps.append({
                            "step": 1.5,
                            "result": "rejected",
                            "rule": "HR-015",
                            "detail": time_limit_reason,
                        })
                        await self._record_trace(
                            scene_name="费用报销提交",
                            input_data=expense_data,
                            steps=steps,
                            conclusion=f"Rejected: expense time limit exceeded (HR-015)",
                            rule_ids=["HR-001", "HR-015"],
                            confidence=Decimal("100.00"),
                            db=db,
                        )
                        await emit_decision(
                            category="expense_submit",
                            scenario="提交报销：超过报销时效",
                            outcome="blocked",
                            reasoning=time_limit_reason,
                            decision_maker=str(expense_data.get("applicant_id") or "system"),
                            entity_ids=[eid for eid in (expense_data.get("expense_id"), budget_id) if eid],
                            applied_rule_ids=["HR-001", "HR-015"],
                            hook_id="engine.submit_expense",
                            metadata={"budget_id": budget_id},
                            db=db,
                        )
                        raise ValueError(f"HR-015: {time_limit_reason}")
                    steps.append({"step": 1.5, "result": "passed", "detail": "Expense time limit check passed"})

            if budget_item is None:
                raise ValueError(f"Budget item {budget_id} not found")

            l3_code = expense_data.get("l3_code") or budget_item.l3_code
            control_info = await self.route_control_level(l3_code, db)
            steps.append({"step": 2, "result": "passed", "detail": f"L3 control tag: {l3_code}"})
            steps.append({
                "step": 3,
                "result": "passed",
                "detail": f"Control level: {control_info['control_tag']}",
                "routing": control_info,
            })

            amount = Decimal(str(expense_data.get("amount", 0)))
            budget_available = await self.check_budget_availability(budget_id, float(amount), db)
            if not budget_available:
                steps.append({
                    "step": 4,
                    "result": "rejected",
                    "rule": "HR-002",
                    "detail": f"Insufficient budget: requested={amount}, available={budget_item.available_amount}",
                })
                await self._record_trace(
                    scene_name="费用报销提交",
                    input_data=expense_data,
                    steps=steps,
                    conclusion="Rejected: insufficient budget (HR-002)",
                    rule_ids=["HR-001", "HR-002"],
                    confidence=Decimal("100.00"),
                    db=db,
                )
                await emit_decision(
                    category="expense_submit",
                    scenario="提交报销：预算额度不足",
                    outcome="blocked",
                    reasoning="HR-002: 预算额度不足，报销金额超出可用预算",
                    decision_maker=str(expense_data.get("applicant_id") or "system"),
                    entity_ids=[eid for eid in (expense_data.get("expense_id"), budget_id) if eid],
                    applied_rule_ids=["HR-001", "HR-002"],
                    hook_id="engine.submit_expense",
                    metadata={"budget_id": budget_id},
                    db=db,
                )
                raise ValueError("HR-002: 预算额度不足，报销金额超出可用预算")
            steps.append({"step": 4, "result": "passed", "detail": "Budget sufficiency check passed"})

            invoices = expense_data.get("invoices", [])
            for inv in invoices:
                invoice_number = inv.get("invoice_number", "")
                if invoice_number:
                    is_dup = await self.check_invoice_duplicate(invoice_number, db)
                    if is_dup:
                        steps.append({
                            "step": 5,
                            "result": "rejected",
                            "detail": f"Duplicate invoice: {invoice_number}",
                        })
                        await self._record_trace(
                            scene_name="费用报销提交",
                            input_data=expense_data,
                            steps=steps,
                            conclusion=f"Rejected: duplicate invoice {invoice_number}",
                            rule_ids=["HR-001", "HR-002"],
                            confidence=Decimal("100.00"),
                            db=db,
                        )
                        raise ValueError(f"发票重复: {invoice_number}")
            steps.append({"step": 5, "result": "passed", "detail": "Invoice dedup check passed"})

            expense_id = expense_data.get("expense_id", f"EX-{uuid.uuid4().hex[:8].upper()}")
            l1_code = expense_data.get("l1_code", budget_item.l1_code)

            expense_report = ExpenseReport(
                expense_id=expense_id,
                applicant_id=expense_data.get("applicant_id", ""),
                budget_id=budget_id,
                l1_code=l1_code,
                l2_code=expense_data.get("l2_code", budget_item.l2_code),
                l3_code=l3_code,
                amount=amount,
                description=expense_data.get("description", ""),
                control_tag=control_info.get("control_tag"),
                status="待审批" if control_info.get("control_tag") != "不管控" else "已审批",
                center_id=expense_data.get("center_id", budget_item.center_id),
                department_id=expense_data.get("department_id", budget_item.department_id),
                legal_entity_id=expense_data.get("legal_entity_id"),
            )
            db.add(expense_report)

            invoice_records = []
            for inv in invoices:
                invoice_record = InvoiceRecord(
                    invoice_id=f"INV-{uuid.uuid4().hex[:8].upper()}",
                    expense_id=expense_id,
                    invoice_number=inv.get("invoice_number", ""),
                    invoice_code=inv.get("invoice_code"),
                    invoice_date=inv.get("invoice_date"),
                    invoice_amount=inv.get("invoice_amount"),
                    invoice_type=inv.get("invoice_type"),
                    seller_name=inv.get("seller_name"),
                    file_path=inv.get("file_path"),
                    is_duplicate=False,
                )
                db.add(invoice_record)
                invoice_records.append(invoice_record)
            await db.flush()

            ops_pack = {}
            try:
                from engines.expense_ops import expense_ops_engine

                ops_pack = await expense_ops_engine.persist_pack(
                    expense_report, expense_data, db, invoices=invoice_records
                )
            except Exception as ops_err:
                logger.warning(f"Operational expense pack failed (non-blocking): {ops_err}")

            steps.append({
                "step": 6,
                "result": "passed",
                "detail": f"Expense report created: {expense_id}, status={expense_report.status}",
                "lines": len(ops_pack.get("lines") or []),
                "three_flow_pending": (ops_pack.get("three_flow") or {}).get("pending_count", 0),
            })

            # Step 7: Strategic alignment evaluation
            strategic_score = await self._evaluate_strategic_alignment(budget_item, expense_data, db)
            steps.append({
                "step": 7,
                "result": "evaluated",
                "strategic_alignment_score": strategic_score["strategic_alignment_score"],
                "resource_rationality_score": strategic_score["resource_rationality_score"],
            })

            await db.flush()

            # Auto-create expense effect tracking record
            try:
                from models.expense_effect import ExpenseEffectTracking

                effect = ExpenseEffectTracking(
                    tracking_id=f"EFT-{uuid.uuid4().hex[:8].upper()}",
                    expense_id=expense_id,
                    budget_id=budget_id,
                    expected_outcome=expense_data.get("expected_outcome", "待填写"),
                    evaluation_deadline=date.today() + timedelta(days=90),
                    status="待评估",
                )
                db.add(effect)
                await db.flush()
            except Exception as effect_err:
                logger.warning(f"Auto-create effect tracking failed (non-blocking): {effect_err}")

            # Calculate write-off metrics for Write-Back and cache
            write_off_amount = amount
            new_used = Decimal(str(budget_item.used_amount)) + write_off_amount
            execution_rate = (new_used / Decimal(str(budget_item.annual_amount))) * Decimal("100") if Decimal(str(budget_item.annual_amount)) > 0 else Decimal("0")

            try:
                from ontology.write_back import get_write_back_engine, WriteBackConsistency
                wb_engine = get_write_back_engine()
                await wb_engine.execute(
                    source_action="budget_writeoff",
                    target_system="budget_system",
                    payload={
                        "action": "update_used_amount",
                        "budget_id": expense_report.budget_id,
                        "amount": float(write_off_amount),
                        "new_used_amount": float(new_used),
                        "execution_rate": float(execution_rate),
                    },
                    consistency=WriteBackConsistency.STRONG,
                    idempotency_key=f"writeoff-{expense_id}",
                )
            except Exception as wb_err:
                logger.warning(f"Write-Back for writeoff failed (non-blocking): {wb_err}")

            try:
                from ontology.cache_manager import get_cache_manager
                cache_mgr = get_cache_manager()
                db_remaining = Decimal(str(budget_item.annual_amount)) - Decimal(str(budget_item.used_amount))
                cache_mgr.update_remaining_amount_cache_aside(expense_report.budget_id, db_remaining)
                cache_mgr.set_execution_rate(
                    budget_item.l1_code,
                    execution_rate.quantize(Decimal("0.01")),
                )
            except Exception as cache_err:
                logger.warning(f"Cache update for writeoff failed (non-blocking): {cache_err}")

            await self._record_trace(
                scene_name="费用报销提交",
                input_data={"expense_id": expense_id, "budget_id": budget_id, "amount": float(amount)},
                steps=steps,
                conclusion=f"Expense {expense_id} submitted, status={expense_report.status}",
                rule_ids=["HR-001", "HR-002"],
                confidence=Decimal("95.00"),
                db=db,
            )

            await emit_decision(
                category="expense_submit",
                scenario=f"提交报销 {expense_id}",
                outcome="executed",
                reasoning=f"Expense {expense_id} submitted, status={expense_report.status}",
                decision_maker=str(expense_report.applicant_id or "system"),
                entity_ids=[expense_id, budget_id],
                applied_rule_ids=["HR-001", "HR-002"],
                hook_id="engine.submit_expense",
                metadata={
                    "budget_id": budget_id,
                    "status": expense_report.status,
                    "line_count": len(ops_pack.get("lines") or []),
                    "three_flow_pending": (ops_pack.get("three_flow") or {}).get("pending_count", 0),
                },
                db=db,
            )
            logger.info(f"Expense report {expense_id} submitted successfully")
            return expense_report

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Expense submission failed: {e}")
            raise

    async def route_control_level(
        self, l3_code: Optional[str], db: AsyncSession
    ) -> Dict[str, Any]:
        """Determine the control routing based on L3 control tag.

        强管控: cross_dept=False, cross_category=False, standard dual approval.
        中心弱管控: cross_dept=True (within center), need BP+GM approval.
        组合管控: cross_dept=True, cross_category=True (within center), need BP+GM.
        不管控: auto-approve.

        Args:
            l3_code: L3 subject code for control tag lookup.
            db: AsyncSession for database operations.

        Returns:
            Dict with control_tag, cross_dept, cross_category, approval_requirements.
        """
        try:
            if not l3_code:
                return {
                    "control_tag": "强管控",
                    "cross_dept": False,
                    "cross_category": False,
                    "approval_requirements": ["部门负责人", "中心总经理", "法人财务负责人", "法人或授权人"],
                }

            l3 = await db.get(BudgetSubjectL3, l3_code)
            if l3 is None:
                return {
                    "control_tag": "强管控",
                    "cross_dept": False,
                    "cross_category": False,
                    "approval_requirements": ["部门负责人", "中心总经理", "法人财务负责人", "法人或授权人"],
                }

            control_tag = l3.control_tag

            routing_map = {
                "强管控": {
                    "control_tag": "强管控",
                    "cross_dept": False,
                    "cross_category": False,
                    "approval_requirements": ["部门负责人", "中心总经理", "法人财务负责人", "法人或授权人"],
                },
                "中心弱管控": {
                    "control_tag": "中心弱管控",
                    "cross_dept": True,
                    "cross_category": False,
                    "approval_requirements": ["BP", "中心总经理"],
                },
                "组合管控": {
                    "control_tag": "组合管控",
                    "cross_dept": True,
                    "cross_category": True,
                    "approval_requirements": ["BP", "中心总经理"],
                },
                "不管控": {
                    "control_tag": "不管控",
                    "cross_dept": True,
                    "cross_category": True,
                    "approval_requirements": [],
                },
            }

            return routing_map.get(control_tag, routing_map["强管控"])

        except Exception as e:
            logger.error(f"Control level routing failed: {e}")
            return {
                "control_tag": "强管控",
                "cross_dept": False,
                "cross_category": False,
                "approval_requirements": ["部门负责人", "中心总经理", "法人财务负责人", "法人或授权人"],
            }

    async def check_budget_availability(
        self, budget_id: str, amount: float, db: AsyncSession
    ) -> bool:
        """Check if the budget has sufficient available amount.

        Args:
            budget_id: Budget item ID.
            amount: Requested amount.
            db: AsyncSession for database operations.

        Returns:
            True if budget is sufficient.
        """
        try:
            budget_item = await db.get(BudgetItem, budget_id)
            if budget_item is None:
                return False

            available = Decimal(str(budget_item.available_amount))
            frozen = Decimal(str(budget_item.frozen_amount))
            used = Decimal(str(budget_item.used_amount))
            requested = Decimal(str(amount))

            remaining = frozen - used
            return requested <= available and requested <= remaining

        except Exception as e:
            logger.error(f"Budget availability check failed: {e}")
            return False

    async def check_invoice_duplicate(
        self, invoice_number: str, db: AsyncSession
    ) -> bool:
        """Check if an invoice number has already been submitted.

        Args:
            invoice_number: Invoice number to check.
            db: AsyncSession for database operations.

        Returns:
            True if invoice is a duplicate.
        """
        try:
            stmt = select(InvoiceRecord).where(
                and_(
                    InvoiceRecord.invoice_number == invoice_number,
                    InvoiceRecord.is_duplicate.is_(False),
                )
            )
            result = await db.execute(stmt)
            existing = result.scalars().first()
            return existing is not None

        except Exception as e:
            logger.error(f"Invoice dedup check failed: {e}")
            return False

    async def _evaluate_strategic_alignment(
        self, budget_item: BudgetItem, expense_data: Dict[str, Any], db: AsyncSession
    ) -> Dict[str, Any]:
        """评估报销的战略对齐度和资源合理性

        检查预算项的战略意图、象限归属、同类费用趋势等，
        返回战略对齐分和资源合理性分。

        Args:
            budget_item: 关联的预算项
            expense_data: 报销数据
            db: AsyncSession

        Returns:
            Dict with strategic_alignment_score (0-100), resource_rationality_score (0-100),
            and details
        """
        strategic_alignment_score = 70  # 默认基准分
        resource_rationality_score = 70  # 默认基准分
        details = []

        # 1. 检查战略意图L1对齐
        strategic_intent = getattr(budget_item, 'strategic_intent_l1', None)
        l3_code = expense_data.get("l3_code") or budget_item.l3_code or ""

        # 战略意图与L3科目对齐映射 — 先从DB加载，否则回退到硬编码默认值
        DEFAULT_ALIGNMENT_MAP = {
            "创新研发": ["B2"],  # 创新研发对齐研发费用
            "全渠道商业化": ["B5", "B3"],  # 全渠道商业化对齐市场费用和业务费用
            "国际化": ["B5", "B3", "B9"],  # 国际化对齐市场、业务和财务费用
        }

        ALIGNMENT_MAP = DEFAULT_ALIGNMENT_MAP
        try:
            stmt = select(OntologyRule).where(
                and_(
                    OntologyRule.rule_type == "strategic_alignment_map",
                    OntologyRule.is_active.is_(True),
                )
            )
            result = await db.execute(stmt)
            db_rule = result.scalars().first()
            if db_rule and db_rule.result:
                db_map = json.loads(db_rule.result)
                if isinstance(db_map, dict):
                    ALIGNMENT_MAP = db_map
        except Exception as e:
            logger.warning(f"Failed to load alignment map from DB, using default: {e}")

        if strategic_intent and l3_code:
            l1_code = budget_item.l1_code
            aligned_l1_codes = ALIGNMENT_MAP.get(strategic_intent, [])
            if aligned_l1_codes and l1_code in aligned_l1_codes:
                strategic_alignment_score += 20
                details.append(f"费用科目{l1_code}与战略意图「{strategic_intent}」对齐")
            else:
                strategic_alignment_score -= 15
                details.append(f"费用科目{l1_code}与战略意图「{strategic_intent}」不对齐")

        # 2. 检查象限归属 - 收缩象限需要额外审查
        quadrant = getattr(budget_item, 'quadrant', None)
        if quadrant == "收缩":
            strategic_alignment_score -= 20
            resource_rationality_score -= 15
            details.append("收缩象限费用需额外审查，扣减对齐分和合理性分")
        elif quadrant == "发展":
            strategic_alignment_score += 5
            details.append("发展象限费用，战略对齐度加分")
        elif quadrant == "探索":
            resource_rationality_score -= 10
            details.append("探索象限费用，资源合理性需关注")

        # 3. 检查同类费用趋势 - 近3个月是否增长超30%
        try:
            from datetime import datetime, timedelta
            three_months_ago = datetime.now() - timedelta(days=90)
            stmt = select(ExpenseReport).where(
                and_(
                    ExpenseReport.l3_code == l3_code,
                    ExpenseReport.created_at >= three_months_ago,
                    ExpenseReport.status.in_(["已审批", "已核销"]),
                )
            )
            result = await db.execute(stmt)
            recent_expenses = result.scalars().all()

            if len(recent_expenses) >= 3:
                # 按月分组计算趋势
                monthly_totals: Dict[str, float] = {}
                for exp in recent_expenses:
                    month_key = exp.created_at.strftime("%Y-%m") if exp.created_at else "unknown"
                    monthly_totals[month_key] = monthly_totals.get(month_key, 0) + float(exp.amount or 0)

                months = sorted(monthly_totals.keys())
                if len(months) >= 2:
                    first_month = monthly_totals[months[0]]
                    last_month = monthly_totals[months[-1]]
                    if first_month > 0:
                        increase_rate = (last_month - first_month) / first_month
                        if increase_rate > 0.30:
                            resource_rationality_score -= 20
                            details.append(
                                f"同类L3费用近3月增长{increase_rate*100:.0f}%，超过30%阈值，资源合理性存疑"
                            )
                        elif increase_rate < -0.10:
                            resource_rationality_score += 5
                            details.append("同类L3费用呈下降趋势，资源使用合理")
        except Exception as e:
            logger.warning(f"Strategic alignment trend check failed (non-blocking): {e}")

        # 4. 检查报销金额与预算比例
        amount = Decimal(str(expense_data.get("amount", 0)))
        annual_amount = Decimal(str(budget_item.annual_amount or 0))
        if annual_amount > 0:
            expense_ratio = float(amount / annual_amount * 100)
            if expense_ratio > 20:
                resource_rationality_score -= 10
                details.append(f"单笔报销占年度预算{expense_ratio:.1f}%，比例偏高")
            elif expense_ratio < 5:
                resource_rationality_score += 5
                details.append("单笔报销占预算比例合理")

        # 确保分数在0-100范围内
        strategic_alignment_score = max(0, min(100, strategic_alignment_score))
        resource_rationality_score = max(0, min(100, resource_rationality_score))

        return {
            "strategic_alignment_score": strategic_alignment_score,
            "resource_rationality_score": resource_rationality_score,
            "needs_strategic_review": strategic_alignment_score < 40,
            "details": details,
        }

    async def write_off_budget(
        self, expense_id: str, db: AsyncSession
    ) -> BudgetWriteOff:
        """Write off budget after dual-line approval is completed.

        Verifies approval completion, deducts used_amount from budget,
        updates execution rate, and checks alert rules.

        Args:
            expense_id: Expense report ID to write off.
            db: AsyncSession for database operations.

        Returns:
            Created BudgetWriteOff record.

        Raises:
            ValueError: If expense not found or approval not complete.
        """
        try:
            expense = await db.get(ExpenseReport, expense_id)
            if expense is None:
                raise ValueError(f"Expense report {expense_id} not found")

            if expense.status not in ("已审批", "已核销"):
                raise ValueError(
                    f"Expense {expense_id} status is {expense.status}, "
                    f"cannot write off (requires 已审批)"
                )

            steps = [
                {"step": "perceive", "detail": f"Expense {expense_id} approved, proceeding write-off"},
                {"step": "reason", "detail": "Dual-line approval verified, deduct budget"},
            ]

            budget_item = await db.get(BudgetItem, expense.budget_id)
            if budget_item is None:
                raise ValueError(f"Budget item {expense.budget_id} not found")

            write_off_amount = Decimal(str(expense.amount))
            budget_item.used_amount = Decimal(str(budget_item.used_amount)) + write_off_amount
            budget_item.available_amount = Decimal(str(budget_item.frozen_amount)) - Decimal(str(budget_item.used_amount))

            annual = Decimal(str(budget_item.annual_amount))
            execution_rate = (
                (Decimal(str(budget_item.used_amount)) / annual * 100)
                if annual > 0
                else Decimal("0")
            )

            expense.status = "已核销"
            if budget_item.status == "已授予":
                budget_item.status = "执行中"

            write_off = BudgetWriteOff(
                write_off_id=f"WO-{uuid.uuid4().hex[:8].upper()}",
                expense_id=expense_id,
                budget_id=expense.budget_id,
                write_off_amount=write_off_amount,
                write_off_date=datetime.now(),
                execution_rate=execution_rate.quantize(Decimal("0.01")),
            )
            db.add(write_off)

            steps.append({"step": "execute", "detail": f"Write-off {write_off.write_off_id} created, amount={write_off_amount}"})
            steps.append({
                "step": "reflect",
                "detail": f"Execution rate: {execution_rate:.2f}%, budget status: {budget_item.status}",
            })

            await db.flush()

            await self._record_trace(
                scene_name="预算核销",
                input_data={"expense_id": expense_id, "budget_id": expense.budget_id, "amount": float(write_off_amount)},
                steps=steps,
                conclusion=f"Write-off complete, execution rate={execution_rate:.2f}%",
                rule_ids=["HR-WO-001"],
                confidence=Decimal("100.00"),
                db=db,
            )

            from ontology.decision_recorder import emit_decision

            await emit_decision(
                category="budget_write_off",
                scenario=f"核销报销 {expense_id}",
                outcome="executed",
                reasoning=f"Write-off complete, execution rate={execution_rate:.2f}%",
                decision_maker="system",
                entity_ids=[expense_id, expense.budget_id, write_off.write_off_id],
                applied_rule_ids=["HR-WO-001"],
                hook_id="engine.write_off",
                metadata={"budget_id": expense.budget_id, "amount": float(write_off_amount)},
                db=db,
            )
            logger.info(f"Budget write-off complete for expense {expense_id}")
            return write_off

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Budget write-off failed for {expense_id}: {e}")
            raise

    async def occupy_budget(
        self,
        budget_id: str,
        expense_id: str,
        amount: float,
        db: AsyncSession,
    ) -> BudgetOccupation:
        """Occupy budget when expense is submitted.

        Creates a BudgetOccupation record and reduces available budget.

        Args:
            budget_id: Budget item ID.
            expense_id: Expense report ID.
            amount: Amount to occupy.
            db: AsyncSession for database operations.

        Returns:
            Created BudgetOccupation record.

        Raises:
            ValueError: If budget not found or insufficient.
        """
        try:
            budget_item = await db.get(BudgetItem, budget_id)
            if budget_item is None:
                raise ValueError(f"Budget item {budget_id} not found")

            available = Decimal(str(budget_item.available_amount))
            requested = Decimal(str(amount))

            if requested > available:
                raise ValueError(
                    f"HR-002: 预算额度不足，可用{available}，申请占用{requested}"
                )

            occupation = BudgetOccupation(
                budget_id=budget_id,
                expense_id=expense_id,
                occupied_amount=amount,
                status="占用中",
            )
            db.add(occupation)

            # Reduce available amount
            budget_item.available_amount = available - requested
            await db.flush()

            await self._record_trace(
                scene_name="预算占用",
                input_data={"budget_id": budget_id, "expense_id": expense_id, "amount": amount},
                steps=[{"step": "occupy", "occupation_id": occupation.id}],
                conclusion=f"Budget {budget_id} occupied {amount} for expense {expense_id}",
                rule_ids=["HR-BO-OCCUPY"],
                confidence=Decimal("100.00"),
                db=db,
            )

            logger.info(f"Budget {budget_id} occupied {amount} for expense {expense_id}")
            return occupation

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Budget occupation failed: {e}")
            raise

    async def release_occupation(
        self, expense_id: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """Release occupation when expense is rejected.

        Finds the active occupation for the expense and releases it,
        restoring the available budget.

        Args:
            expense_id: Expense report ID.
            db: AsyncSession for database operations.

        Returns:
            Dict with release result.

        Raises:
            ValueError: If no active occupation found.
        """
        try:
            stmt = select(BudgetOccupation).where(
                and_(
                    BudgetOccupation.expense_id == expense_id,
                    BudgetOccupation.status == "占用中",
                )
            )
            result = await db.execute(stmt)
            occupation = result.scalars().first()

            if occupation is None:
                raise ValueError(f"No active occupation found for expense {expense_id}")

            occupation.status = "已释放"
            occupation.released_at = datetime.now()

            # Restore available amount
            budget_item = await db.get(BudgetItem, occupation.budget_id)
            if budget_item is not None:
                budget_item.available_amount = Decimal(str(budget_item.available_amount)) + Decimal(str(occupation.occupied_amount))

            await db.flush()

            await self._record_trace(
                scene_name="预算占用释放",
                input_data={"expense_id": expense_id, "occupation_id": occupation.id},
                steps=[{"step": "release", "occupation_id": occupation.id}],
                conclusion=f"Occupation released for expense {expense_id}, amount {occupation.occupied_amount}",
                rule_ids=["HR-BO-RELEASE"],
                confidence=Decimal("100.00"),
                db=db,
            )

            logger.info(f"Budget occupation released for expense {expense_id}")
            return {
                "occupation_id": occupation.id,
                "expense_id": expense_id,
                "budget_id": occupation.budget_id,
                "released_amount": occupation.occupied_amount,
                "status": "已释放",
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Budget occupation release failed: {e}")
            raise

    async def confirm_occupation(
        self, expense_id: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """Convert occupation to actual write-off.

        Finds the active occupation for the expense and marks it as 核销,
        indicating the occupied budget has been formally consumed.

        Args:
            expense_id: Expense report ID.
            db: AsyncSession for database operations.

        Returns:
            Dict with confirmation result.

        Raises:
            ValueError: If no active occupation found.
        """
        try:
            stmt = select(BudgetOccupation).where(
                and_(
                    BudgetOccupation.expense_id == expense_id,
                    BudgetOccupation.status == "占用中",
                )
            )
            result = await db.execute(stmt)
            occupation = result.scalars().first()

            if occupation is None:
                raise ValueError(f"No active occupation found for expense {expense_id}")

            occupation.status = "已核销"

            # Update budget used_amount
            budget_item = await db.get(BudgetItem, occupation.budget_id)
            if budget_item is not None:
                budget_item.used_amount = Decimal(str(budget_item.used_amount)) + Decimal(str(occupation.occupied_amount))

            await db.flush()

            await self._record_trace(
                scene_name="预算占用核销",
                input_data={"expense_id": expense_id, "occupation_id": occupation.id},
                steps=[{"step": "confirm", "occupation_id": occupation.id}],
                conclusion=f"Occupation confirmed for expense {expense_id}, amount {occupation.occupied_amount}",
                rule_ids=["HR-BO-CONFIRM"],
                confidence=Decimal("100.00"),
                db=db,
            )

            logger.info(f"Budget occupation confirmed for expense {expense_id}")
            return {
                "occupation_id": occupation.id,
                "expense_id": expense_id,
                "budget_id": occupation.budget_id,
                "confirmed_amount": occupation.occupied_amount,
                "status": "已核销",
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Budget occupation confirmation failed: {e}")
            raise
