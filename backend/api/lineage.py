"""
v12.0: 八阶段血缘追踪 API

GET /api/lineage/expense/{id} — 报销→预算→象限→战略举措→SP
GET /api/lineage/alert/{id}   — 预警→预算→象限→战略举措
GET /api/lineage/budget/{id}  — 预算→象限→战略举措→SP
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.schemas import APIResponse
from services.lineage_tracker import get_lineage_tracker


router = APIRouter()


@router.get("/lineage/expense/{expense_id}", response_model=APIResponse)
async def get_expense_lineage(
    expense_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取报销单的血缘链路（SP→BP→战略举措→象限→预算→L3→报销）"""
    try:
        tracker = get_lineage_tracker()
        result = await tracker.trace_expense(expense_id, db)
        return APIResponse(success=True, data=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/lineage/alert/{alert_id}", response_model=APIResponse)
async def get_alert_lineage(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取预警的血缘链路（预警→预算→象限→战略举措）"""
    try:
        tracker = get_lineage_tracker()
        result = await tracker.trace_alert(alert_id, db)
        return APIResponse(success=True, data=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/lineage/budget/{budget_id}", response_model=APIResponse)
async def get_budget_lineage(
    budget_id: str,
    db: AsyncSession = Depends(get_db),
):
    """获取预算的血缘链路（预算→象限→战略举措→SP）"""
    try:
        tracker = get_lineage_tracker()
        result = await tracker.trace_budget(budget_id, db)
        return APIResponse(success=True, data=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
