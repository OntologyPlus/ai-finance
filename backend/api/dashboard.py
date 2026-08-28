from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.schemas import APIResponse
from models.budget import BudgetItem
from models.alert import AlertRecord
from models.approval import ApprovalRecord
from models.analysis import ExecutionRate
from engines.role_dashboard import RoleDashboardEngine, SUPPORTED_ROLES

router = APIRouter()
role_engine = RoleDashboardEngine()


@router.get("/dashboard/role/{role}", response_model=APIResponse)
async def get_role_dashboard(
    role: str,
    center_id: Optional[str] = Query(None, description="中心 ID（center_lead 必填）"),
    l1_code: Optional[str] = Query(None, description="L1 科目（product_manager 必填）"),
    period: Optional[str] = Query(None, description="期间 YYYY-MM"),
    db: AsyncSession = Depends(get_db),
):
    """v8.0 角色化 Dashboard：CFO / center_lead / product_manager"""
    if role not in SUPPORTED_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported role '{role}'. Supported: {list(SUPPORTED_ROLES)}",
        )
    try:
        data = await role_engine.build(
            role=role,
            db=db,
            center_id=center_id,
            l1_code=l1_code,
            period=period,
        )
        return APIResponse(success=True, data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/role-supported", response_model=APIResponse)
async def list_supported_roles():
    """v8.0 列出支持的角色"""
    return APIResponse(
        success=True,
        data={"supported_roles": list(SUPPORTED_ROLES)},
    )


@router.get("/dashboard/overview", response_model=APIResponse)
async def get_dashboard_overview(
    db: AsyncSession = Depends(get_db),
):
    try:
        stmt_budget = select(BudgetItem).where(
            BudgetItem.status.in_(["已授予", "执行中"])
        )
        result_budget = await db.execute(stmt_budget)
        budget_items = result_budget.scalars().all()

        total_budget = sum(float(i.annual_amount or 0) for i in budget_items)
        total_used = sum(float(i.used_amount or 0) for i in budget_items)
        total_available = sum(float(i.available_amount or 0) for i in budget_items)
        execution_rate = round(total_used / total_budget * 100, 2) if total_budget > 0 else 0

        stmt_alert = select(AlertRecord).where(
            AlertRecord.alert_status.in_(["开放", "响应中", "待闭环确认"])
        )
        result_alert = await db.execute(stmt_alert)
        open_alerts = result_alert.scalars().all()

        alert_count = len(open_alerts)
        high_priority_alerts = sum(1 for a in open_alerts if a.alert_level in ("红色", "橙色"))

        stmt_approval = select(ApprovalRecord).where(
            ApprovalRecord.approval_action == "待审批"
        )
        result_approval = await db.execute(stmt_approval)
        pending_approvals = result_approval.scalars().all()

        overview = {
            "budget_summary": {
                "total_items": len(budget_items),
                "total_budget": total_budget,
                "total_used": total_used,
                "total_available": total_available,
                "execution_rate": execution_rate,
            },
            "alert_count": alert_count,
            "high_priority_alerts": high_priority_alerts,
            "pending_approvals": len(pending_approvals),
        }

        return APIResponse(success=True, data=overview)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/budget-by-quadrant", response_model=APIResponse)
async def get_budget_by_quadrant(
    db: AsyncSession = Depends(get_db),
):
    try:
        stmt = select(BudgetItem).where(BudgetItem.status.in_(["已授予", "执行中"]))
        result = await db.execute(stmt)
        items = result.scalars().all()

        quadrant_data = {"发展": [], "收缩": [], "稳定": [], "探索": []}
        for item in items:
            quadrant_data[item.quadrant].append(item)

        result_data = {}
        for quadrant, q_items in quadrant_data.items():
            total_annual = sum(float(i.annual_amount or 0) for i in q_items)
            total_used = sum(float(i.used_amount or 0) for i in q_items)
            total_available = sum(float(i.available_amount or 0) for i in q_items)
            result_data[quadrant] = {
                "item_count": len(q_items),
                "total_annual": total_annual,
                "total_used": total_used,
                "total_available": total_available,
                "execution_rate": round(total_used / total_annual * 100, 2) if total_annual > 0 else 0,
            }

        return APIResponse(success=True, data=result_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/budget-by-l1", response_model=APIResponse)
async def get_budget_by_l1(
    db: AsyncSession = Depends(get_db),
):
    try:
        stmt = select(BudgetItem).where(BudgetItem.status.in_(["已授予", "执行中"]))
        result = await db.execute(stmt)
        items = result.scalars().all()

        l1_data = {}
        for item in items:
            l1 = item.l1_code
            if l1 not in l1_data:
                l1_data[l1] = {"total_annual": 0, "total_used": 0, "total_available": 0, "item_count": 0}
            l1_data[l1]["total_annual"] += float(item.annual_amount or 0)
            l1_data[l1]["total_used"] += float(item.used_amount or 0)
            l1_data[l1]["total_available"] += float(item.available_amount or 0)
            l1_data[l1]["item_count"] += 1

        for l1_code, data in l1_data.items():
            data["execution_rate"] = round(data["total_used"] / data["total_annual"] * 100, 2) if data["total_annual"] > 0 else 0

        return APIResponse(success=True, data=l1_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/alert-trend", response_model=APIResponse)
async def get_alert_trend(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    try:
        stmt = select(AlertRecord).order_by(AlertRecord.created_at.desc())
        result = await db.execute(stmt)
        alerts = result.scalars().all()

        trend = {}
        for alert in alerts:
            if alert.created_at:
                date_key = alert.created_at.strftime("%Y-%m-%d")
                if date_key not in trend:
                    trend[date_key] = {"蓝色": 0, "黄色": 0, "橙色": 0, "红色": 0, "total": 0}
                trend[date_key][alert.alert_level] = trend[date_key].get(alert.alert_level, 0) + 1
                trend[date_key]["total"] += 1

        sorted_trend = dict(sorted(trend.items(), reverse=True)[:days])

        return APIResponse(success=True, data=sorted_trend)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/execution-trend", response_model=APIResponse)
async def get_execution_trend(
    center_id: Optional[str] = Query(None),
    limit: int = Query(12, ge=1, le=60),
    db: AsyncSession = Depends(get_db),
):
    try:
        conditions = []
        if center_id:
            conditions.append(ExecutionRate.center_id == center_id)

        stmt = select(ExecutionRate).where(*conditions).order_by(ExecutionRate.period.desc()).limit(limit) if conditions else select(ExecutionRate).order_by(ExecutionRate.period.desc()).limit(limit)
        result = await db.execute(stmt)
        rates = result.scalars().all()

        trend = {}
        for r in rates:
            period = r.period
            if period not in trend:
                trend[period] = {"monthly_rate": [], "cumulative_rate": [], "annual_rate": []}
            trend[period]["monthly_rate"].append(float(r.monthly_rate or 0))
            trend[period]["cumulative_rate"].append(float(r.cumulative_rate or 0))
            trend[period]["annual_rate"].append(float(r.annual_rate or 0))

        avg_trend = {}
        for period, values in trend.items():
            count = len(values["monthly_rate"])
            avg_trend[period] = {
                "avg_monthly_rate": round(sum(values["monthly_rate"]) / count, 2) if count else 0,
                "avg_cumulative_rate": round(sum(values["cumulative_rate"]) / count, 2) if count else 0,
                "avg_annual_rate": round(sum(values["annual_rate"]) / count, 2) if count else 0,
                "item_count": count,
            }

        return APIResponse(success=True, data=avg_trend)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
