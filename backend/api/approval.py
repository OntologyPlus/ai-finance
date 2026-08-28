from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.schemas import APIResponse
from models.approval import ApprovalRecord
from models.approval_config import ApprovalThresholdConfig, ApproverProfile
from models.expense import ExpenseReport
from engines.approval_engine import ApprovalEngine
from engines.approval_bottleneck import ApprovalBottleneckEngine
from engines.approval_router import ApprovalRouter

router = APIRouter()

approval_engine = ApprovalEngine()
router_engine = ApprovalRouter()
bottleneck_engine = ApprovalBottleneckEngine()


# v11.0: 审批角色 → 本体规则 ID 映射
APPROVAL_ROLE_RULE_MAP = {
    "部门经理": ["HR-AP-001"],
    "部门负责人": ["HR-AP-001", "HR-009"],
    "财务BP": ["HR-AP-002"],
    "分管领导": ["HR-AP-003"],
    "中心总经理": ["HR-AP-002", "HR-010"],
    "财务总监": ["HR-AP-003"],
    "法人代表": ["HR-AP-003"],
    "CFO": ["HR-AP-003"],
    "总经理": ["HR-AP-003"],
}


def _attach_approval_rule_ids(rows: list[dict]) -> list[dict]:
    """v11.0: 给 approval 响应附加 rule_ids 字段"""
    for row in rows:
        role = row.get("approver_role") or ""
        # 优先按角色匹配
        matched = APPROVAL_ROLE_RULE_MAP.get(role)
        if matched:
            row["rule_ids"] = matched
        else:
            row["rule_ids"] = ["HR-AP-001"]
    return rows


@router.get("/approvals/stats", response_model=APIResponse)
async def get_approval_stats(
    approver_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    try:
        conditions = []
        if approver_id:
            conditions.append(ApprovalRecord.approver_id == approver_id)

        stmt = select(ApprovalRecord).where(and_(*conditions)) if conditions else select(ApprovalRecord)
        result = await db.execute(stmt)
        records = result.scalars().all()

        by_action = {}
        by_role = {}
        overdue_count = 0

        for r in records:
            action = r.approval_action or "unknown"
            by_action[action] = by_action.get(action, 0) + 1

            role = r.approver_role or "unknown"
            by_role[role] = by_role.get(role, 0) + 1

            if r.is_overdue:
                overdue_count += 1

        stats = {
            "total": len(records),
            "by_action": by_action,
            "by_role": by_role,
            "overdue_count": overdue_count,
            "pending_count": by_action.get("待审批", 0),
            "approved_count": by_action.get("通过", 0),
            "rejected_count": by_action.get("驳回", 0),
        }

        return APIResponse(success=True, data=stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/approvals/pending", response_model=APIResponse)
async def get_pending_approvals(
    approver_id: Optional[str] = Query(None, description="当前审批人ID"),
    db: AsyncSession = Depends(get_db),
):
    try:
        if approver_id:
            records = await approval_engine.get_pending_approvals(approver_id, db)
        else:
            stmt = select(ApprovalRecord).where(ApprovalRecord.approval_action == "待审批")
            result = await db.execute(stmt)
            records = result.scalars().all()
        data = [{c: getattr(r, c) for c in r.__table__.columns.keys()} for r in records]
        _attach_approval_rule_ids(data)
        return APIResponse(success=True, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/approvals/{expense_id}", response_model=APIResponse)
async def get_approval_chain(
    expense_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        expense = await db.get(ExpenseReport, expense_id)
        if expense is None:
            raise HTTPException(status_code=404, detail=f"Expense report {expense_id} not found")

        status = await approval_engine.get_approval_status(expense_id, db)
        # v11.0: 给每条 approval chain 记录加 rule_ids
        if isinstance(status, dict):
            for line_key in ("org_line", "legal_line"):
                line_records = status.get(line_key)
                if isinstance(line_records, list):
                    for rec in line_records:
                        if isinstance(rec, dict):
                            role = rec.get("approver_role") or rec.get("required_role") or ""
                            matched = APPROVAL_ROLE_RULE_MAP.get(role) or ["HR-AP-001"]
                            rec["rule_ids"] = matched
        return APIResponse(success=True, data=status)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/approvals/{approval_id}/approve", response_model=APIResponse)
async def approve_step(
    approval_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        comment = body.get("comment")
        record = await approval_engine.approve_step(approval_id, "通过", comment, db)
        data = {c: getattr(record, c) for c in record.__table__.columns.keys()}
        return APIResponse(success=True, message="Approved", data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/approvals/{approval_id}/reject", response_model=APIResponse)
async def reject_step(
    approval_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        comment = body.get("comment")
        record = await approval_engine.approve_step(approval_id, "驳回", comment, db)
        data = {c: getattr(record, c) for c in record.__table__.columns.keys()}
        return APIResponse(success=True, message="Rejected", data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/approvals/{approval_id}/delegate", response_model=APIResponse)
async def delegate_approval(
    approval_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        from_user_id = body.get("from_user_id")
        to_user_id = body.get("to_user_id")
        reason = body.get("reason", "")
        if not from_user_id or not to_user_id:
            raise HTTPException(status_code=400, detail="from_user_id and to_user_id are required")

        record = await approval_engine.delegate_approval(
            approval_id, from_user_id, to_user_id, reason, db
        )
        data = {c: getattr(record, c) for c in record.__table__.columns.keys()}
        return APIResponse(success=True, message="Approval delegated", data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ────── v7.0 新增：动态阈值配置 / 智能审批人推荐 / 瓶颈识别 ──────


@router.get("/approvals/config", response_model=APIResponse)
async def get_threshold_config(
    center_id: Optional[str] = Query(None, description="中心ID（None=全局）"),
    db: AsyncSession = Depends(get_db),
):
    """获取审批动态阈值配置"""
    try:
        stmt = select(ApprovalThresholdConfig).where(ApprovalThresholdConfig.is_active == 1)
        if center_id:
            stmt = stmt.where(
                (ApprovalThresholdConfig.center_id == center_id) | (ApprovalThresholdConfig.center_id.is_(None))
            )
        result = await db.execute(stmt)
        configs = result.scalars().all()
        data = [
            {
                "id": c.id,
                "config_name": c.config_name,
                "center_id": c.center_id,
                "l1_code": c.l1_code,
                "legal_entity": c.legal_entity,
                "tiers": [
                    {"tier": 1, "amount": c.tier1_amount, "role": c.tier1_role},
                    {"tier": 2, "amount": c.tier2_amount, "role": c.tier2_role},
                    {"tier": 3, "amount": c.tier3_amount, "role": c.tier3_role},
                    {"tier": 4, "amount": c.tier4_amount, "role": c.tier4_role},
                    {"tier": 5, "amount": c.tier5_amount, "role": c.tier5_role},
                ],
            }
            for c in configs
        ]
        return APIResponse(success=True, message=f"返回 {len(data)} 条配置", data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/approvals/route-recommend", response_model=APIResponse)
async def recommend_approvers(
    body: dict = Body(default_factory=dict),
    db: AsyncSession = Depends(get_db),
):
    """智能审批人推荐"""
    try:
        target_role = body.get("target_role", "部门负责人")
        center_id = body.get("center_id")
        l1_code = body.get("l1_code")
        amount = float(body.get("amount", 0))
        top_n = int(body.get("top_n", 3))
        result = await router_engine.recommend_approvers(
            db, target_role=target_role, center_id=center_id,
            l1_code=l1_code, amount=amount, top_n=top_n,
        )
        return APIResponse(success=True, data=result.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/approvals/bottleneck", response_model=APIResponse)
async def analyze_bottleneck(
    period: Optional[str] = Query(None, description="统计期 YYYY-MM"),
    top_n: int = Query(3, ge=1, le=10),
    db: AsyncSession = Depends(get_db),
):
    """审批瓶颈智能识别"""
    try:
        analysis = await bottleneck_engine.analyze_bottlenecks(db, period=period, top_n=top_n)
        return APIResponse(success=True, data=analysis.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
