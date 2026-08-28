from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.schemas import APIResponse
from engines.scenario_engine import ScenarioEngine

router = APIRouter()

engine = ScenarioEngine()


@router.get("/scenarios", response_model=APIResponse)
async def list_scenarios(
    scenario_type: Optional[str] = Query(None),
    period: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    try:
        from sqlalchemy import select
        from models.scenario import Scenario
        conditions = []
        if scenario_type:
            conditions.append(Scenario.scenario_type == scenario_type)
        if period:
            conditions.append(Scenario.period == period)
        stmt = select(Scenario).where(*conditions) if conditions else select(Scenario)
        result = await db.execute(stmt)
        scenarios = result.scalars().all()
        data = [{c: getattr(s, c) for c in s.__table__.columns.keys()} for s in scenarios]
        return APIResponse(success=True, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenarios", response_model=APIResponse)
async def create_scenario(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        name = body.get("name")
        scenario_type = body.get("scenario_type")
        assumptions = body.get("assumptions", {})
        period = body.get("period")
        if not name or not scenario_type or not period:
            raise HTTPException(status_code=400, detail="name, scenario_type, period are required")

        result = await engine.create_scenario(name, scenario_type, assumptions, period, db)
        return APIResponse(success=True, message="Scenario created", data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenarios/compare", response_model=APIResponse)
async def compare_scenarios(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        scenario_ids = body.get("scenario_ids")
        if not scenario_ids or not isinstance(scenario_ids, list):
            raise HTTPException(status_code=400, detail="scenario_ids (list[int]) is required")

        result = await engine.compare_scenarios(scenario_ids, db)
        return APIResponse(success=True, data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenarios/elastic-adjustment", response_model=APIResponse)
async def apply_elastic_adjustment(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        budget_id = body.get("budget_id")
        actual_volume = body.get("actual_volume")
        if budget_id is None or actual_volume is None:
            raise HTTPException(status_code=400, detail="budget_id and actual_volume are required")

        result = await engine.apply_elastic_adjustment(budget_id, actual_volume, db)
        return APIResponse(success=True, message="Elastic adjustment applied", data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenarios/stress-test", response_model=APIResponse)
async def run_stress_test(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        scenario_id = body.get("scenario_id")
        if scenario_id is None:
            raise HTTPException(status_code=400, detail="scenario_id is required")

        result = await engine.run_stress_test(scenario_id, db)
        return APIResponse(success=True, data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenarios/emergency-allocation", response_model=APIResponse)
async def emergency_allocation(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        reserve_id = body.get("reserve_id")
        budget_id = body.get("budget_id")
        amount = body.get("amount")
        reason = body.get("reason", "")
        if not all([reserve_id, budget_id, amount]):
            raise HTTPException(status_code=400, detail="reserve_id, budget_id, amount are required")

        result = await engine.emergency_allocation(reserve_id, budget_id, amount, reason, db)
        return APIResponse(success=True, message="Emergency allocation executed", data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
