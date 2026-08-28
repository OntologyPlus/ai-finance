from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.schemas import APIResponse
from engines.impact_assessment_engine import ImpactAssessmentEngine
from engines.decision_sandbox import DecisionSandboxEngine
from engines.pareto_optimizer import ParetoOptimizer
from services.impact_attribution import ImpactAttributionService

router = APIRouter()

engine = ImpactAssessmentEngine()
sandbox_engine = DecisionSandboxEngine()
attribution_service = ImpactAttributionService()
pareto_optimizer = ParetoOptimizer()


@router.post("/impact/budget-change", response_model=APIResponse)
async def assess_budget_change(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        budget_id = body.get("budget_id")
        change_type = body.get("change_type")
        amount = body.get("amount")
        if not all([budget_id, change_type, amount is not None]):
            raise HTTPException(status_code=400, detail="budget_id, change_type, amount are required")

        result = await engine.assess_budget_change(budget_id, change_type, amount, db)
        return APIResponse(success=True, data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/impact/expense-overrun", response_model=APIResponse)
async def assess_expense_overrun(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        expense_id = body.get("expense_id")
        overrun_amount = body.get("overrun_amount")
        if not all([expense_id, overrun_amount is not None]):
            raise HTTPException(status_code=400, detail="expense_id and overrun_amount are required")

        result = await engine.assess_expense_overrun(expense_id, overrun_amount, db)
        return APIResponse(success=True, data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/impact/strategic-shift", response_model=APIResponse)
async def assess_strategic_shift(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        initiative_id = body.get("initiative_id")
        new_direction = body.get("new_direction")
        if not all([initiative_id, new_direction]):
            raise HTTPException(status_code=400, detail="initiative_id and new_direction are required")

        result = await engine.assess_strategic_shift(initiative_id, new_direction, db)
        return APIResponse(success=True, data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/impact/trace/{chain_id}", response_model=APIResponse)
async def trace_impact(
    chain_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await engine.trace_impact(chain_id, db)
        return APIResponse(success=True, data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/impact/mitigation/{chain_id}", response_model=APIResponse)
async def suggest_mitigation(
    chain_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await engine.suggest_mitigation(chain_id, db)
        return APIResponse(success=True, data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═════════════════════════════════════════════════════════════
# v8.0 Module I：决策沙盘 + 影响归因 + Pareto 前沿
# ═════════════════════════════════════════════════════════════


@router.post("/impact/sandbox", response_model=APIResponse)
async def simulate_sandbox(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """v8.0 决策沙盘：执行前模拟 5 域影响"""
    try:
        scenario_name = body.get("scenario_name", "未命名场景")
        operation_type = body.get("operation_type")
        params = body.get("params", {})
        if not operation_type:
            raise HTTPException(
                status_code=400,
                detail="operation_type is required",
            )
        result = await sandbox_engine.simulate(
            scenario_name=scenario_name,
            operation_type=operation_type,
            operation_params=params,
            db=db,
        )
        return APIResponse(success=True, data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/impact/sandbox/compare", response_model=APIResponse)
async def compare_sandbox_scenarios(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """v8.0 多场景对比"""
    try:
        scenarios = body.get("scenarios", [])
        if not scenarios or not isinstance(scenarios, list):
            raise HTTPException(
                status_code=400,
                detail="scenarios must be a non-empty list",
            )
        result = await sandbox_engine.compare_scenarios(scenarios, db=db)
        return APIResponse(success=True, data=result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/impact/sandbox/list", response_model=APIResponse)
async def list_sandboxes(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """v8.0 列出历史沙盘场景"""
    try:
        result = await sandbox_engine.list_sandboxes(db, limit)
        return APIResponse(success=True, data={"items": result})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/impact/sandbox/{sandbox_id}", response_model=APIResponse)
async def get_sandbox(
    sandbox_id: int,
    db: AsyncSession = Depends(get_db),
):
    """v8.0 获取沙盘详情"""
    try:
        result = await sandbox_engine.get_sandbox(sandbox_id, db)
        if not result:
            raise HTTPException(status_code=404, detail="沙盘场景不存在")
        return APIResponse(success=True, data=result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/impact/attribute", response_model=APIResponse)
async def attribute_metric(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """v8.0 影响归因：指标变化 → 根操作"""
    try:
        target_metric = body.get("target_metric")
        target_period = body.get("target_period")
        observed_value = body.get("observed_value")
        if not all([target_metric, target_period, observed_value is not None]):
            raise HTTPException(
                status_code=400,
                detail="target_metric, target_period, observed_value are required",
            )
        result = await attribution_service.attribute(
            target_metric=target_metric,
            target_period=target_period,
            observed_value=float(observed_value),
            db=db,
        )
        return APIResponse(success=True, data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/impact/attribute/list", response_model=APIResponse)
async def list_attributions(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """v8.0 列出历史归因分析"""
    try:
        result = await attribution_service.list_attributions(db, limit)
        return APIResponse(success=True, data={"items": result})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/impact/pareto", response_model=APIResponse)
async def compute_pareto(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """v8.0 Pareto 前沿优化"""
    try:
        candidates = body.get("candidates", [])
        weights = body.get("weights")
        if not candidates or not isinstance(candidates, list):
            raise HTTPException(
                status_code=400,
                detail="candidates must be a non-empty list",
            )
        optimizer = ParetoOptimizer(weights=weights) if weights else pareto_optimizer
        result = await optimizer.optimize(candidates, db=db)
        return APIResponse(success=True, data=result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/impact/pareto/auto", response_model=APIResponse)
async def auto_pareto_candidates(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """v8.0 自动生成预算调整方案并优化"""
    try:
        budget_id = body.get("budget_id")
        original_amount = body.get("original_amount")
        if not all([budget_id, original_amount is not None]):
            raise HTTPException(
                status_code=400,
                detail="budget_id, original_amount are required",
            )
        candidates = await pareto_optimizer.auto_candidates_from_budget_change(
            budget_id=budget_id,
            original_amount=float(original_amount),
            db=db,
        )
        result = await pareto_optimizer.optimize(candidates, db=db)
        return APIResponse(success=True, data=result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/impact/pareto/history", response_model=APIResponse)
async def get_pareto_history(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """v8.0 Pareto 优化历史"""
    try:
        result = await pareto_optimizer.get_pareto_history(db, limit)
        return APIResponse(success=True, data={"items": result})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
