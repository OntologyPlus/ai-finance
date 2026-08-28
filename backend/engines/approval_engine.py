from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.approval import ApprovalRecord
from models.expense import ExpenseReport, BudgetWriteOff
from models.ontology import OntologyRule, ReasoningTrace
from models.organization import Employee
from models.user import User


class ApprovalEngine:
    """Approval Engine: Handles dual-line approval workflow.

    Organization line (强管控): 申请人直属主管→部门负责人→财经BP→中心总经理→分管副总裁
    Legal line (强管控): 法人财务负责人→法人或授权人→院外专项审批→矩阵授权审批

    Organization line (中心弱管控/组合管控): 财经BP→中心总经理
    Legal line (中心弱管控/组合管控): 法人财务负责人→法人或授权人→矩阵授权审批

    After both lines complete, triggers budget write-off.
    """

    def __init__(self):
        self.engine_name = "approval"

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
            trace_id=f"RT-AP-{uuid.uuid4().hex[:8].upper()}",
            scene_name=scene_name,
            input_data=json.dumps(input_data, ensure_ascii=False, default=str),
            steps=json.dumps(steps, ensure_ascii=False, default=str),
            conclusion=conclusion,
            confidence=confidence,
            rule_ids=json.dumps(rule_ids, ensure_ascii=False),
        )
        db.add(trace)
        await db.flush()

    async def create_approval_chain(
        self,
        expense_id: str,
        control_level: Dict[str, Any],
        db: AsyncSession,
        strategic_alignment_score: int = 100,
    ) -> List[ApprovalRecord]:
        """Generate approval records based on control level.

        For 强管控: full dual-line approval (up to 9 steps).
            Organization line (5 steps):
                1. 申请人直属主管 2. 部门负责人 3. 财经BP 4. 中心总经理 5. 分管副总裁(金额>100万)
            Legal line (4 steps):
                6. 法人财务负责人 7. 法人或授权人 8. 院外专项审批(涉及院外机构) 9. 矩阵授权审批(跨部门/跨法人)
        For 中心弱管控/组合管控: BP + GM + legal approval (3-5 steps).
            1. 财经BP 2. 中心总经理 3. 法人财务负责人 4. 法人或授权人(金额>50万) 5. 矩阵授权审批(跨部门)
        For 不管控: no approval needed.

        Args:
            expense_id: Expense report ID.
            control_level: Control routing info from ExpenseReimbursementEngine.
            db: AsyncSession for database operations.

        Returns:
            List of created ApprovalRecord objects.
        """
        try:
            expense = await db.get(ExpenseReport, expense_id)
            if expense is None:
                raise ValueError(f"Expense report {expense_id} not found")

            control_tag = control_level.get("control_tag", "强管控")
            records: List[ApprovalRecord] = []

            if control_tag == "不管控":
                expense.status = "已审批"
                await db.flush()
                return records

            now = datetime.now()
            deadline = now + timedelta(hours=48)

            if control_tag == "强管控":
                org_steps = [
                    ("申请人直属主管", 1),
                    ("部门负责人", 2),
                    ("财经BP", 3),
                    ("中心总经理", 4),
                ]
                if expense.amount and expense.amount > Decimal("1000000"):
                    org_steps.append(("分管副总裁", 5))

                # Insert strategic review step if strategic_alignment_score < 40
                if strategic_alignment_score < 30:
                    # Low score: mandatory strategic review, must be approved by 战略负责人
                    org_steps.insert(3, ("战略审核", 3, True, "战略负责人"))
                    org_steps = [(role, idx + 1) + rest[2:] for idx, (role, *rest) in enumerate(org_steps)]
                elif strategic_alignment_score < 40:
                    # Medium-low score: optional strategic review
                    org_steps.insert(3, ("战略审核", 3, False, None))
                    org_steps = [(role, idx + 1) + rest[2:] for idx, (role, *rest) in enumerate(org_steps)]

                legal_steps = [
                    ("法人财务负责人", 6),
                    ("法人或授权人", 7),
                ]
                if expense.legal_entity_id and expense.legal_entity_id.startswith("EXT"):
                    legal_steps.append(("院外专项审批", 8))
                if control_level.get("cross_dept") or control_level.get("cross_entity"):
                    legal_steps.append(("矩阵授权审批", 9))

                for step_info in org_steps:
                    role = step_info[0]
                    step_num = step_info[1]
                    is_mandatory = step_info[2] if len(step_info) > 2 else False
                    required_role = step_info[3] if len(step_info) > 3 else None
                    # Store is_mandatory and required_role in approval_comment as JSON metadata
                    metadata_str = ""
                    if is_mandatory or required_role:
                        metadata_str = json.dumps({"is_mandatory": is_mandatory, "required_role": required_role}, ensure_ascii=False)
                    record = ApprovalRecord(
                        approval_id=f"AP-{uuid.uuid4().hex[:8].upper()}",
                        expense_id=expense_id,
                        approval_line="组织管理线",
                        approval_step=step_num,
                        approver_id=await _resolve_approver_id(role, expense, db),
                        approver_role=role,
                        approval_action="待审批",
                        deadline=deadline,
                        is_overdue=False,
                        approval_comment=metadata_str or None,
                    )
                    db.add(record)
                    records.append(record)

                for role, step_num in legal_steps:
                    record = ApprovalRecord(
                        approval_id=f"AP-{uuid.uuid4().hex[:8].upper()}",
                        expense_id=expense_id,
                        approval_line="法人架构线",
                        approval_step=step_num,
                        approver_id=await _resolve_approver_id(role, expense, db),
                        approver_role=role,
                        approval_action="待审批",
                        deadline=deadline,
                        is_overdue=False,
                    )
                    db.add(record)
                    records.append(record)

                expense.status = "组织线审批中"

            elif control_tag in ("中心弱管控", "组合管控"):
                bp_gm_steps = [
                    ("财经BP", 1),
                    ("中心总经理", 2),
                ]

                # Insert strategic review step if strategic_alignment_score < 40
                if strategic_alignment_score < 30:
                    bp_gm_steps.insert(1, ("战略审核", 1, True, "战略负责人"))
                    bp_gm_steps = [(role, idx + 1) + rest[2:] for idx, (role, *rest) in enumerate(bp_gm_steps)]
                elif strategic_alignment_score < 40:
                    bp_gm_steps.insert(1, ("战略审核", 1, False, None))
                    bp_gm_steps = [(role, idx + 1) + rest[2:] for idx, (role, *rest) in enumerate(bp_gm_steps)]

                legal_steps = [
                    ("法人财务负责人", 3),
                ]
                if expense.amount and expense.amount > Decimal("500000"):
                    legal_steps.append(("法人或授权人", 4))
                if control_level.get("cross_dept") or control_level.get("cross_entity"):
                    legal_steps.append(("矩阵授权审批", 5))

                for step_info in bp_gm_steps:
                    role = step_info[0]
                    step_num = step_info[1]
                    is_mandatory = step_info[2] if len(step_info) > 2 else False
                    required_role = step_info[3] if len(step_info) > 3 else None
                    metadata_str = ""
                    if is_mandatory or required_role:
                        metadata_str = json.dumps({"is_mandatory": is_mandatory, "required_role": required_role}, ensure_ascii=False)
                    record = ApprovalRecord(
                        approval_id=f"AP-{uuid.uuid4().hex[:8].upper()}",
                        expense_id=expense_id,
                        approval_line="组织管理线",
                        approval_step=step_num,
                        approver_id=await _resolve_approver_id(role, expense, db),
                        approver_role=role,
                        approval_action="待审批",
                        deadline=deadline,
                        is_overdue=False,
                        approval_comment=metadata_str or None,
                    )
                    db.add(record)
                    records.append(record)

                for role, step_num in legal_steps:
                    record = ApprovalRecord(
                        approval_id=f"AP-{uuid.uuid4().hex[:8].upper()}",
                        expense_id=expense_id,
                        approval_line="法人架构线",
                        approval_step=step_num,
                        approver_id=await _resolve_approver_id(role, expense, db),
                        approver_role=role,
                        approval_action="待审批",
                        deadline=deadline,
                        is_overdue=False,
                    )
                    db.add(record)
                    records.append(record)

                expense.status = "组织线审批中"

            await db.flush()

            await self._record_trace(
                scene_name="审批链创建",
                input_data={"expense_id": expense_id, "control_tag": control_tag},
                steps=[{"step": "create_chain", "control_tag": control_tag, "record_count": len(records)}],
                conclusion=f"Created {len(records)} approval records for {control_tag}",
                rule_ids=["HR-AP-001"],
                confidence=Decimal("100.00"),
                db=db,
            )

            logger.info(f"Approval chain created for expense {expense_id}: {len(records)} records")
            return records

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Approval chain creation failed for {expense_id}: {e}")
            raise

    async def approve_step(
        self,
        approval_id: str,
        action: str,
        comment: Optional[str],
        db: AsyncSession,
        strategic_alignment_rating: Optional[int] = None,
        resource_efficiency_rating: Optional[int] = None,
    ) -> ApprovalRecord:
        """Process an approval step (通过/驳回).

        Checks if all steps in the current line are completed.
        If org line complete, starts legal line.
        If legal line complete, triggers budget write-off.

        Args:
            approval_id: Approval record ID.
            action: "通过" or "驳回".
            comment: Optional approval comment.
            db: AsyncSession for database operations.

        Returns:
            Updated ApprovalRecord.

        Raises:
            ValueError: If approval record not found or action invalid.
        """
        try:
            record = await db.get(ApprovalRecord, approval_id)
            if record is None:
                raise ValueError(f"Approval record {approval_id} not found")
            if record.approval_action != "待审批":
                raise ValueError(f"Approval {approval_id} already processed: {record.approval_action}")
            if action not in ("通过", "驳回"):
                raise ValueError(f"Invalid action: {action}, must be 通过 or 驳回")

            record.approval_action = action
            record.approved_at = datetime.now()
            record.is_overdue = record.deadline and datetime.now() > record.deadline

            # Parse metadata from approval_comment (is_mandatory, required_role)
            step_metadata = {}
            if record.approval_comment:
                try:
                    step_metadata = json.loads(record.approval_comment)
                except (json.JSONDecodeError, TypeError):
                    step_metadata = {}
            is_mandatory_step = step_metadata.get("is_mandatory", False)
            required_role = step_metadata.get("required_role")

            # Handle mandatory strategic review step: cannot be skipped
            if record.approver_role == "战略审核" and is_mandatory_step:
                if action == "驳回":
                    # Mandatory strategic review rejected -> reject entire expense
                    expense = await db.get(ExpenseReport, record.expense_id)
                    if expense is not None:
                        expense.status = "已驳回"
                    # Preserve metadata in comment, append rejection info
                    original_comment = comment or ""
                    record.approval_comment = json.dumps({
                        **step_metadata,
                        "rejection_result": "mandatory_rejected",
                    }, ensure_ascii=False) + (" | " + original_comment if original_comment else "")
                    await db.flush()

                    await self._record_trace(
                        scene_name="审批处理",
                        input_data={"approval_id": approval_id, "action": action, "mandatory": True},
                        steps=[{"step": "mandatory_reject", "detail": f"Mandatory strategic review rejected for expense {record.expense_id}"}],
                        conclusion=f"Expense {record.expense_id} rejected by mandatory strategic review",
                        rule_ids=["HR-AP-002"],
                        confidence=Decimal("100.00"),
                        db=db,
                    )

                    logger.info(f"Mandatory strategic review {approval_id} rejected, expense {record.expense_id} auto-rejected")
                    from ontology.decision_record import DecisionActorType
                    from ontology.decision_recorder import emit_decision

                    await emit_decision(
                        category="approval_final",
                        scenario=f"战略审核驳回 {record.expense_id}",
                        outcome="rejected",
                        reasoning="Mandatory strategic review rejected",
                        decision_maker=str(record.approver_id or "system"),
                        actor_type=DecisionActorType.PERSON,
                        entity_ids=[record.expense_id, approval_id],
                        applied_rule_ids=["HR-AP-002"],
                        hook_id="engine.approve_step",
                        db=db,
                    )
                    return record

            # Handle strategic review step additional fields
            if record.approver_role == "战略审核" and action == "通过":
                extra_parts = []
                if strategic_alignment_rating is not None:
                    extra_parts.append(f"战略对齐评分: {strategic_alignment_rating}/5")
                if resource_efficiency_rating is not None:
                    extra_parts.append(f"资源效率评分: {resource_efficiency_rating}/5")
                if extra_parts:
                    # Preserve metadata prefix, append rating info
                    metadata_prefix = json.dumps(step_metadata, ensure_ascii=False) if step_metadata else ""
                    rating_str = " | ".join(extra_parts)
                    record.approval_comment = (metadata_prefix + " | " + rating_str) if metadata_prefix else rating_str

            expense = await db.get(ExpenseReport, record.expense_id)
            if expense is None:
                raise ValueError(f"Expense report {record.expense_id} not found")

            if action == "驳回":
                expense.status = "已驳回"
                await db.flush()

                await self._record_trace(
                    scene_name="审批处理",
                    input_data={"approval_id": approval_id, "action": action},
                    steps=[{"step": "reject", "detail": f"Expense {record.expense_id} rejected by {record.approver_role}"}],
                    conclusion=f"Expense {record.expense_id} rejected",
                    rule_ids=["HR-AP-002"],
                    confidence=Decimal("100.00"),
                    db=db,
                )

                logger.info(f"Approval {approval_id} rejected for expense {record.expense_id}")
                from ontology.decision_record import DecisionActorType
                from ontology.decision_recorder import emit_decision

                await emit_decision(
                    category="expense_reject",
                    scenario=f"审批驳回 {record.expense_id}",
                    outcome="rejected",
                    reasoning=comment or f"Rejected by {record.approver_role}",
                    decision_maker=str(record.approver_id or "system"),
                    actor_type=DecisionActorType.PERSON,
                    entity_ids=[record.expense_id, approval_id],
                    applied_rule_ids=["HR-AP-002"],
                    hook_id="engine.approve_step",
                    db=db,
                )
                return record

            line_complete = await self._check_line_complete(
                record.expense_id, record.approval_line, db
            )

            if record.approval_line == "组织管理线" and line_complete:
                legal_pending = await self._has_pending_legal_line(record.expense_id, db)
                if legal_pending:
                    expense.status = "法人线审批中"
                else:
                    expense.status = "已审批"

            elif record.approval_line == "法人架构线" and line_complete:
                expense.status = "已审批"

            await db.flush()

            all_complete = await self.check_approval_complete(record.expense_id, db)
            if all_complete and expense.status == "已审批":
                from engines.expense_reimbursement import ExpenseReimbursementEngine
                er_engine = ExpenseReimbursementEngine()
                await er_engine.write_off_budget(record.expense_id, db)

            await self._record_trace(
                scene_name="审批处理",
                input_data={"approval_id": approval_id, "action": action},
                steps=[{
                    "step": "approve",
                    "detail": f"Approved by {record.approver_role}, line_complete={line_complete}, all_complete={all_complete}",
                }],
                conclusion=f"Approval step {approval_id} processed, expense status={expense.status}",
                rule_ids=["HR-AP-002"],
                confidence=Decimal("100.00"),
                db=db,
            )

            logger.info(f"Approval {approval_id} processed: {action}")
            from ontology.decision_record import DecisionActorType
            from ontology.decision_recorder import emit_decision

            await emit_decision(
                category="approval_final" if expense.status == "已审批" else "expense_approve",
                scenario=f"审批通过 {record.expense_id}",
                outcome="approved",
                reasoning=comment or f"Approved by {record.approver_role}",
                decision_maker=str(record.approver_id or "system"),
                actor_type=DecisionActorType.PERSON,
                entity_ids=[record.expense_id, approval_id],
                applied_rule_ids=["HR-AP-002"],
                hook_id="engine.approve_step",
                metadata={"expense_status": expense.status},
                db=db,
            )
            return record

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Approval step processing failed for {approval_id}: {e}")
            raise

    async def _check_line_complete(
        self, expense_id: str, approval_line: str, db: AsyncSession
    ) -> bool:
        stmt = select(ApprovalRecord).where(
            and_(
                ApprovalRecord.expense_id == expense_id,
                ApprovalRecord.approval_line == approval_line,
            )
        )
        result = await db.execute(stmt)
        records = result.scalars().all()

        if not records:
            return False

        return all(r.approval_action == "通过" for r in records)

    async def _has_pending_legal_line(
        self, expense_id: str, db: AsyncSession
    ) -> bool:
        stmt = select(ApprovalRecord).where(
            and_(
                ApprovalRecord.expense_id == expense_id,
                ApprovalRecord.approval_line == "法人架构线",
                ApprovalRecord.approval_action == "待审批",
            )
        )
        result = await db.execute(stmt)
        return result.scalars().first() is not None

    async def get_pending_approvals(
        self, approver_id: str, db: AsyncSession
    ) -> List[ApprovalRecord]:
        """Get all pending approval records for a given approver.

        Args:
            approver_id: The approver's employee ID.
            db: AsyncSession for database operations.

        Returns:
            List of pending ApprovalRecord objects.
        """
        try:
            stmt = select(ApprovalRecord).where(
                and_(
                    ApprovalRecord.approver_id == approver_id,
                    ApprovalRecord.approval_action == "待审批",
                )
            ).order_by(ApprovalRecord.deadline)
            result = await db.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Get pending approvals failed for {approver_id}: {e}")
            return []

    async def check_approval_complete(
        self, expense_id: str, db: AsyncSession
    ) -> bool:
        """Check if all approval steps for an expense are completed.

        Args:
            expense_id: Expense report ID.
            db: AsyncSession for database operations.

        Returns:
            True if all approvals are completed (all 通过).
        """
        try:
            stmt = select(ApprovalRecord).where(
                ApprovalRecord.expense_id == expense_id,
            )
            result = await db.execute(stmt)
            records = result.scalars().all()

            if not records:
                return True

            return all(r.approval_action == "通过" for r in records)
        except Exception as e:
            logger.error(f"Approval completion check failed for {expense_id}: {e}")
            return False

    async def get_approval_status(
        self, expense_id: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """Get the full approval status for an expense report.

        Args:
            expense_id: Expense report ID.
            db: AsyncSession for database operations.

        Returns:
            Dict with approval status details per line.
        """
        try:
            stmt = select(ApprovalRecord).where(
                ApprovalRecord.expense_id == expense_id,
            ).order_by(ApprovalRecord.approval_step)
            result = await db.execute(stmt)
            records = result.scalars().all()

            org_line = [r for r in records if r.approval_line == "组织管理线"]
            legal_line = [r for r in records if r.approval_line == "法人架构线"]

            def _parse_step_metadata(r: ApprovalRecord) -> dict:
                """Extract is_mandatory and required_role from approval_comment metadata."""
                meta = {}
                if r.approval_comment:
                    try:
                        parsed = json.loads(r.approval_comment)
                        if isinstance(parsed, dict):
                            meta = parsed
                    except (json.JSONDecodeError, TypeError):
                        pass
                return meta

            return {
                "expense_id": expense_id,
                "org_line": [
                    {
                        "step": r.approval_step,
                        "role": r.approver_role,
                        "action": r.approval_action,
                        "comment": r.approval_comment,
                        "approved_at": r.approved_at.isoformat() if r.approved_at else None,
                        "is_mandatory": _parse_step_metadata(r).get("is_mandatory", False),
                        "required_role": _parse_step_metadata(r).get("required_role"),
                    }
                    for r in org_line
                ],
                "legal_line": [
                    {
                        "step": r.approval_step,
                        "role": r.approver_role,
                        "action": r.approval_action,
                        "comment": r.approval_comment,
                        "approved_at": r.approved_at.isoformat() if r.approved_at else None,
                        "is_mandatory": _parse_step_metadata(r).get("is_mandatory", False),
                        "required_role": _parse_step_metadata(r).get("required_role"),
                    }
                    for r in legal_line
                ],
                "all_complete": all(r.approval_action == "通过" for r in records) if records else True,
            }
        except Exception as e:
            logger.error(f"Get approval status failed for {expense_id}: {e}")
            return {"expense_id": expense_id, "error": str(e)}

    async def check_approval_overdue(
        self, db: AsyncSession
    ) -> List[ApprovalRecord]:
        try:
            now = datetime.now()
            stmt = select(ApprovalRecord).where(
                and_(
                    ApprovalRecord.approval_action == "待审批",
                    ApprovalRecord.deadline < now,
                )
            )
            result = await db.execute(stmt)
            overdue_records = result.scalars().all()

            for record in overdue_records:
                record.is_overdue = True

            await db.flush()

            logger.info(f"Found {len(overdue_records)} overdue approval records")
            return list(overdue_records)
        except Exception as e:
            logger.error(f"Check approval overdue failed: {e}")
            return []

    async def delegate_approval(
        self,
        approval_id: str,
        from_user_id: str,
        to_user_id: str,
        reason: str,
        db: AsyncSession,
    ) -> ApprovalRecord:
        """Delegate an approval step to another person.

        Args:
            approval_id: The approval record ID.
            from_user_id: The current approver's user ID.
            to_user_id: The delegate's user ID.
            reason: Reason for delegation.
            db: AsyncSession for database operations.

        Returns:
            Updated ApprovalRecord.

        Raises:
            ValueError: If approval record not found or not owned by from_user_id.
        """
        try:
            record = await db.get(ApprovalRecord, approval_id)
            if record is None:
                raise ValueError(f"Approval record {approval_id} not found")
            if record.approver_id != from_user_id:
                raise ValueError(f"Approval {approval_id} is not owned by {from_user_id}")
            if record.approval_action != "待审批":
                raise ValueError(f"Approval {approval_id} already processed: {record.approval_action}")

            # Check if this is a mandatory strategic review step (cannot be delegated/skipped)
            step_metadata = {}
            if record.approval_comment:
                try:
                    step_metadata = json.loads(record.approval_comment)
                except (json.JSONDecodeError, TypeError):
                    step_metadata = {}
            if record.approver_role == "战略审核" and step_metadata.get("is_mandatory", False):
                raise ValueError(f"Approval {approval_id} is a mandatory strategic review step and cannot be delegated")

            original_approver = record.approver_id
            record.approver_id = to_user_id
            record.approval_comment = f"[委派] 原审批人: {original_approver}, 原因: {reason}"

            await db.flush()

            await self._record_trace(
                scene_name="审批委派",
                input_data={"approval_id": approval_id, "from": from_user_id, "to": to_user_id},
                steps=[{"step": "delegate", "from": from_user_id, "to": to_user_id, "reason": reason}],
                conclusion=f"Approval {approval_id} delegated from {from_user_id} to {to_user_id}",
                rule_ids=["HR-AP-003"],
                confidence=Decimal("100.00"),
                db=db,
            )

            logger.info(f"Approval {approval_id} delegated from {from_user_id} to {to_user_id}")
            return record

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Delegate approval failed for {approval_id}: {e}")
            raise

    async def get_approval_time_stats(
        self, db: AsyncSession
    ) -> Dict[str, Any]:
        try:
            stmt = select(ApprovalRecord).where(
                ApprovalRecord.approval_action.in_(["通过", "驳回"])
            )
            result = await db.execute(stmt)
            completed_records = result.scalars().all()

            stmt_all = select(ApprovalRecord)
            result_all = await db.execute(stmt_all)
            all_records = result_all.scalars().all()

            total_completed = len(completed_records)
            total_all = len(all_records)

            durations = []
            by_role: Dict[str, list] = {}

            for record in completed_records:
                if record.approved_at and record.deadline:
                    created_at = record.deadline - timedelta(hours=48)
                    duration_hours = (record.approved_at - created_at).total_seconds() / 3600
                    durations.append(duration_hours)
                    role = record.approver_role
                    if role not in by_role:
                        by_role[role] = []
                    by_role[role].append(duration_hours)

            avg_duration_hours = sum(durations) / len(durations) if durations else 0

            overdue_count = sum(1 for r in all_records if r.is_overdue)
            overdue_rate = overdue_count / total_all if total_all > 0 else 0

            by_role_stats = {}
            for role, role_durations in by_role.items():
                by_role_stats[role] = {
                    "avg_duration_hours": round(sum(role_durations) / len(role_durations), 2) if role_durations else 0,
                    "count": len(role_durations),
                }

            overdue_by_role: Dict[str, int] = {}
            for r in all_records:
                if r.is_overdue:
                    overdue_by_role[r.approver_role] = overdue_by_role.get(r.approver_role, 0) + 1
            for role in by_role_stats:
                by_role_stats[role]["overdue_count"] = overdue_by_role.get(role, 0)

            return {
                "avg_duration_hours": round(avg_duration_hours, 2),
                "overdue_rate": round(overdue_rate, 4),
                "by_role": by_role_stats,
            }
        except Exception as e:
            logger.error(f"Get approval time stats failed: {e}")
            return {"avg_duration_hours": 0, "overdue_rate": 0, "by_role": {}}


async def _resolve_approver_id(
    role: str, expense: ExpenseReport, db: AsyncSession
) -> str:
    """Resolve real approver ID from organization structure.

    Queries the Employee/User table to find the person matching the role and department/center.
    Falls back to placeholder format if no matching person is found.
    """
    # Map Chinese approval role names to system role values
    ROLE_MAP = {
        "直属主管": "dept_head",
        "部门负责人": "dept_head",
        "财经BP": "finance_bp",
        "中心总经理": "center_manager",
        "分管副总裁": "cfo",
        "法人财务负责人": "finance_bp",
        "法人或授权人": "cfo",
        "战略审核": "cfo",
    }

    system_role = ROLE_MAP.get(role)
    if not system_role:
        return f"APPROVER-{role}-{expense.department_id or 'UNKNOWN'}"

    try:
        if role in ("直属主管", "部门负责人"):
            # Find dept_head in the same department
            stmt = select(Employee).where(
                and_(
                    Employee.is_active.is_(True),
                    Employee.dept_id == expense.department_id,
                )
            )
            result = await db.execute(stmt)
            employees = result.scalars().all()
            # Check role_id or join with User table
            for emp in employees:
                if emp.role_id and system_role in emp.role_id.lower():
                    return emp.employee_id
            # Fallback: check User table
            user_stmt = select(User).where(
                and_(
                    User.is_active.is_(True),
                    User.role == system_role,
                    User.department_id == expense.department_id,
                )
            )
            user_result = await db.execute(user_stmt)
            user = user_result.scalars().first()
            if user:
                return user.user_id

        elif role == "财经BP":
            # Find finance_bp in the same center
            stmt = select(Employee).where(
                and_(
                    Employee.is_active.is_(True),
                    Employee.center_id == expense.center_id,
                )
            )
            result = await db.execute(stmt)
            employees = result.scalars().all()
            for emp in employees:
                if emp.role_id and "finance_bp" in emp.role_id.lower():
                    return emp.employee_id
            # Fallback: check User table
            user_stmt = select(User).where(
                and_(
                    User.is_active.is_(True),
                    User.role == "finance_bp",
                    User.center_id == expense.center_id,
                )
            )
            user_result = await db.execute(user_stmt)
            user = user_result.scalars().first()
            if user:
                return user.user_id

        elif role == "中心总经理":
            # Find center_manager in the same center
            stmt = select(Employee).where(
                and_(
                    Employee.is_active.is_(True),
                    Employee.center_id == expense.center_id,
                )
            )
            result = await db.execute(stmt)
            employees = result.scalars().all()
            for emp in employees:
                if emp.role_id and "center_manager" in emp.role_id.lower():
                    return emp.employee_id
            user_stmt = select(User).where(
                and_(
                    User.is_active.is_(True),
                    User.role == "center_manager",
                    User.center_id == expense.center_id,
                )
            )
            user_result = await db.execute(user_stmt)
            user = user_result.scalars().first()
            if user:
                return user.user_id

        elif role == "分管副总裁":
            # Find cfo or admin
            for target_role in ("cfo", "admin"):
                user_stmt = select(User).where(
                    and_(
                        User.is_active.is_(True),
                        User.role == target_role,
                    )
                )
                user_result = await db.execute(user_stmt)
                user = user_result.scalars().first()
                if user:
                    return user.user_id

        elif role == "法人财务负责人":
            # Find finance_bp in any center
            stmt = select(Employee).where(
                and_(
                    Employee.is_active.is_(True),
                )
            )
            result = await db.execute(stmt)
            employees = result.scalars().all()
            for emp in employees:
                if emp.role_id and "finance_bp" in emp.role_id.lower():
                    return emp.employee_id
            user_stmt = select(User).where(
                and_(
                    User.is_active.is_(True),
                    User.role == "finance_bp",
                )
            )
            user_result = await db.execute(user_stmt)
            user = user_result.scalars().first()
            if user:
                return user.user_id

        elif role == "法人或授权人":
            # Find cfo
            user_stmt = select(User).where(
                and_(
                    User.is_active.is_(True),
                    User.role == "cfo",
                )
            )
            user_result = await db.execute(user_stmt)
            user = user_result.scalars().first()
            if user:
                return user.user_id

    except Exception as e:
        logger.warning(f"Failed to resolve approver for role '{role}': {e}")

    # Fallback: placeholder format
    return f"APPROVER-{role}-{expense.department_id or 'UNKNOWN'}"
