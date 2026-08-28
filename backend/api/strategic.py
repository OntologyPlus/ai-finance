from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.schemas import APIResponse, APIPageResponse
from models.strategic import StrategicInitiative, QuarterlyAllocation, ManagementReport
from models.budget import BudgetItem, BudgetSubjectL1
from services.strategic_cognitive import (
    compute_risk_gauge,
    build_impact_chain,
    compute_gap_analysis,
)

router = APIRouter()


@router.get("/strategic/initiatives", response_model=APIResponse)
async def list_initiatives(
    strategic_intent_l1: Optional[str] = Query(None, description="战略意图L1"),
    owner_center: Optional[str] = Query(None, description="归属中心"),
    status: Optional[str] = Query(None, description="状态"),
    db: AsyncSession = Depends(get_db),
):
    try:
        conditions = []
        if strategic_intent_l1:
            conditions.append(StrategicInitiative.strategic_intent_l1 == strategic_intent_l1)
        if owner_center:
            conditions.append(StrategicInitiative.owner_center == owner_center)
        if status:
            conditions.append(StrategicInitiative.status == status)

        stmt = select(StrategicInitiative).where(*conditions) if conditions else select(StrategicInitiative)
        result = await db.execute(stmt)
        items = result.scalars().all()

        data = [{c: getattr(r, c) for c in r.__table__.columns.keys()} for r in items]
        return APIResponse(success=True, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/strategic/initiatives", response_model=APIResponse)
async def create_initiative(body: dict, db: AsyncSession = Depends(get_db)):
    try:
        initiative = StrategicInitiative(**body)
        db.add(initiative)
        await db.flush()
        data = {c: getattr(initiative, c) for c in initiative.__table__.columns.keys()}
        return APIResponse(success=True, message="Initiative created", data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategic/allocations", response_model=APIResponse)
async def list_allocations(
    budget_id: Optional[str] = Query(None, description="预算项目ID"),
    quarter: Optional[str] = Query(None, description="季度"),
    db: AsyncSession = Depends(get_db),
):
    try:
        conditions = []
        if budget_id:
            conditions.append(QuarterlyAllocation.budget_id == budget_id)
        if quarter:
            conditions.append(QuarterlyAllocation.quarter == quarter)

        stmt = select(QuarterlyAllocation).where(*conditions) if conditions else select(QuarterlyAllocation)
        result = await db.execute(stmt)
        items = result.scalars().all()

        data = [{c: getattr(r, c) for c in r.__table__.columns.keys()} for r in items]
        return APIResponse(success=True, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/strategic/allocations", response_model=APIResponse)
async def create_allocation(body: dict, db: AsyncSession = Depends(get_db)):
    try:
        allocation = QuarterlyAllocation(**body)
        db.add(allocation)
        await db.flush()
        data = {c: getattr(allocation, c) for c in allocation.__table__.columns.keys()}
        return APIResponse(success=True, message="Allocation created", data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/management", response_model=APIResponse)
async def list_management_reports(
    report_type: Optional[str] = Query(None, description="报告类型"),
    report_period: Optional[str] = Query(None, description="报告期"),
    status: Optional[str] = Query(None, description="状态"),
    db: AsyncSession = Depends(get_db),
):
    try:
        conditions = []
        if report_type:
            conditions.append(ManagementReport.report_type == report_type)
        if report_period:
            conditions.append(ManagementReport.report_period == report_period)
        if status:
            conditions.append(ManagementReport.status == status)

        stmt = select(ManagementReport).where(*conditions) if conditions else select(ManagementReport)
        result = await db.execute(stmt)
        items = result.scalars().all()

        data = [{c: getattr(r, c) for c in r.__table__.columns.keys()} for r in items]
        return APIResponse(success=True, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reports/management", response_model=APIResponse)
async def create_management_report(body: dict, db: AsyncSession = Depends(get_db)):
    try:
        report = ManagementReport(**body)
        db.add(report)
        await db.flush()
        data = {c: getattr(report, c) for c in report.__table__.columns.keys()}
        return APIResponse(success=True, message="Report created", data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategic/matrix", response_model=APIResponse)
async def get_strategic_matrix(db: AsyncSession = Depends(get_db)):
    """Build strategic-budget matrix: rows=strategic intent L1, columns=L1 subject codes.

    Each cell contains: total_amount, used_amount, execution_rate.
    Also returns strategic coverage metrics.
    """
    try:
        # 1. Query all strategic initiatives
        init_stmt = select(StrategicInitiative)
        init_result = await db.execute(init_stmt)
        initiatives = init_result.scalars().all()

        # 2. Query all L1 subjects
        l1_stmt = select(BudgetSubjectL1)
        l1_result = await db.execute(l1_stmt)
        l1_subjects = l1_result.scalars().all()

        # 3. Query all budget items
        budget_stmt = select(BudgetItem)
        budget_result = await db.execute(budget_stmt)
        budget_items = budget_result.scalars().all()

        # 4. Build L1 code list for columns
        l1_codes = [s.l1_code for s in l1_subjects]

        # 5. Build intent L1 list for rows
        intent_l1_list = list(dict.fromkeys(
            i.strategic_intent_l1 for i in initiatives if i.strategic_intent_l1
        ))
        # Also include intent values from budget items that may not have matching initiatives
        for bi in budget_items:
            if bi.strategic_intent_l1 and bi.strategic_intent_l1 not in intent_l1_list:
                intent_l1_list.append(bi.strategic_intent_l1)

        # 6. Build matrix: group budget items by (strategic_intent_l1, l1_code)
        from decimal import Decimal
        matrix_map: dict[tuple[str, str], dict] = {}
        for bi in budget_items:
            intent = bi.strategic_intent_l1 or "未分类"
            code = bi.l1_code or "00"
            key = (intent, code)
            if key not in matrix_map:
                matrix_map[key] = {"total_amount": Decimal("0"), "used_amount": Decimal("0")}
            matrix_map[key]["total_amount"] += bi.annual_amount or Decimal("0")
            matrix_map[key]["used_amount"] += bi.used_amount or Decimal("0")

        matrix = []
        for intent in intent_l1_list:
            row: dict[str, any] = {"intent": intent, "cells": {}}
            for code in l1_codes:
                key = (intent, code)
                cell_data = matrix_map.get(key, {"total_amount": Decimal("0"), "used_amount": Decimal("0")})
                total = float(cell_data["total_amount"])
                used = float(cell_data["used_amount"])
                rate = round(used / total * 100, 2) if total > 0 else 0.0
                row["cells"][code] = {
                    "total_amount": total,
                    "used_amount": used,
                    "execution_rate": rate,
                }
            matrix.append(row)

        # 7. Calculate strategic coverage
        total_items = len(budget_items)
        aligned_items = sum(
            1 for bi in budget_items
            if bi.strategy_initiative_id or bi.strategic_intent_l1
        )
        total_amount = sum(float(bi.annual_amount or 0) for bi in budget_items)
        aligned_amount = sum(
            float(bi.annual_amount or 0) for bi in budget_items
            if bi.strategy_initiative_id or bi.strategic_intent_l1
        )
        coverage = {
            "item_coverage": round(aligned_items / total_items, 4) if total_items > 0 else 0.0,
            "amount_coverage": round(aligned_amount / total_amount, 4) if total_amount > 0 else 0.0,
            "aligned_items": aligned_items,
            "total_items": total_items,
        }

        return APIResponse(success=True, data={
            "matrix": matrix,
            "l1_codes": l1_codes,
            "intent_l1_list": intent_l1_list,
            "coverage": coverage,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 战略认知 API（v9.0 Module E.1） ────────────────────────────


@router.get("/strategic/risk-gauge", response_model=APIResponse)
async def get_strategic_risk_gauge(db: AsyncSession = Depends(get_db)):
    """战略风险仪表：5 维加权评分（目标差距/执行率/优先级/预算覆盖/停滞风险）。"""
    try:
        initiatives = (await db.execute(select(StrategicInitiative))).scalars().all()
        allocations = (await db.execute(select(QuarterlyAllocation))).scalars().all()
        budget_items = (await db.execute(select(BudgetItem))).scalars().all()

        gauge = compute_risk_gauge(initiatives, allocations, budget_items)
        return APIResponse(success=True, data=gauge.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategic/impact-chain/{initiative_id}", response_model=APIResponse)
async def get_initiative_impact_chain(
    initiative_id: str,
    db: AsyncSession = Depends(get_db),
):
    """举措影响链：战略意图 → 举措 → 预算分期 → 实际执行（4 层传导）。"""
    try:
        ini = (
            await db.execute(
                select(StrategicInitiative).where(
                    StrategicInitiative.initiative_id == initiative_id
                )
            )
        ).scalars().first()
        if not ini:
            raise HTTPException(status_code=404, detail=f"战略举措 {initiative_id} 不存在")

        allocations = (await db.execute(select(QuarterlyAllocation))).scalars().all()
        budget_items = (await db.execute(select(BudgetItem))).scalars().all()

        chain = build_impact_chain(ini, allocations, budget_items)
        return APIResponse(success=True, data=chain.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategic/gap-analysis", response_model=APIResponse)
async def get_strategic_gap_analysis(db: AsyncSession = Depends(get_db)):
    """战略 GAP 分析：按战略意图分组，KPI 达成 + 预算执行 + 状态判定 + 改进建议。"""
    try:
        initiatives = (await db.execute(select(StrategicInitiative))).scalars().all()
        budget_items = (await db.execute(select(BudgetItem))).scalars().all()
        allocations = (await db.execute(select(QuarterlyAllocation))).scalars().all()

        gap = compute_gap_analysis(initiatives, budget_items, allocations)
        return APIResponse(success=True, data=gap)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
