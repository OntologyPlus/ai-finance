from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.schemas import APIResponse
from engines.zero_based_budget_engine import ZeroBasedBudgetEngine

router = APIRouter()

engine = ZeroBasedBudgetEngine()


@router.post("/zbb/reviews", response_model=APIResponse)
async def initiate_zbb_review(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        period = body.get("period")
        total_budget_constraint = body.get("total_budget_constraint")
        if not period or total_budget_constraint is None:
            raise HTTPException(status_code=400, detail="period and total_budget_constraint are required")

        result = await engine.initiate_zbb_review(period, total_budget_constraint, db)
        return APIResponse(success=True, message="ZBB review initiated", data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/zbb/decision-units", response_model=APIResponse)
async def create_decision_unit(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        review_id = body.get("review_id")
        name = body.get("name")
        owner = body.get("owner")
        scope = body.get("scope", "")
        if not all([review_id, name, owner]):
            raise HTTPException(status_code=400, detail="review_id, name, owner are required")

        result = await engine.create_decision_unit(review_id, name, owner, scope, db)
        return APIResponse(success=True, message="Decision unit created", data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/zbb/decision-packages", response_model=APIResponse)
async def create_decision_package(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        unit_id = body.get("unit_id")
        level = body.get("level")
        amount = body.get("amount")
        justification = body.get("justification", "")
        if not all([unit_id, level is not None, amount is not None]):
            raise HTTPException(status_code=400, detail="unit_id, level, amount are required")

        result = await engine.create_decision_package(unit_id, level, amount, justification, db)
        return APIResponse(success=True, message="Decision package created", data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/zbb/rank/{review_id}", response_model=APIResponse)
async def rank_packages(
    review_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await engine.rank_packages(review_id, db)
        return APIResponse(success=True, data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/zbb/synthesize/{review_id}", response_model=APIResponse)
async def synthesize_budget(
    review_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        total_budget = body.get("total_budget")
        if total_budget is None:
            raise HTTPException(status_code=400, detail="total_budget is required")

        result = await engine.synthesize_budget(review_id, total_budget, db)
        return APIResponse(success=True, message="Budget synthesized", data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
