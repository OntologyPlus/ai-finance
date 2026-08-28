from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.schemas import APIResponse
from engines.cost_center_engine import CostCenterEngine

router = APIRouter()

engine = CostCenterEngine()


@router.post("/cost-centers/standard-costs", response_model=APIResponse)
async def set_standard_cost(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        center_id = body.get("center_id")
        cost_item = body.get("cost_item")
        quantity = body.get("quantity")
        price = body.get("price")
        if not all([center_id, cost_item, quantity is not None, price is not None]):
            raise HTTPException(status_code=400, detail="center_id, cost_item, quantity, price are required")

        result = await engine.set_standard_cost(center_id, cost_item, quantity, price, db)
        return APIResponse(success=True, message="Standard cost set", data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cost-centers/{center_id}/variance", response_model=APIResponse)
async def variance_analysis(
    center_id: str,
    period: str = Query(..., description="期间, 如 2024-06"),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await engine.variance_analysis(center_id, period, db)
        return APIResponse(success=True, data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cost-centers/allocate/{allocation_id}", response_model=APIResponse)
async def allocate_cost(
    allocation_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await engine.allocate_cost(allocation_id, db)
        return APIResponse(success=True, message="Cost allocated", data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cost-centers/settle", response_model=APIResponse)
async def settle_internal(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        provider_id = body.get("provider_id")
        consumer_id = body.get("consumer_id")
        volume = body.get("volume")
        price = body.get("price")
        if not all([provider_id, consumer_id, volume is not None, price is not None]):
            raise HTTPException(status_code=400, detail="provider_id, consumer_id, volume, price are required")

        result = await engine.settle_internal(provider_id, consumer_id, volume, price, db)
        return APIResponse(success=True, message="Internal settlement completed", data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
