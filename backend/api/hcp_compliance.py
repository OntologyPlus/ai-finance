from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.schemas import APIResponse
from engines.hcp_compliance_engine import HCPComplianceEngine

router = APIRouter()

engine = HCPComplianceEngine()


@router.post("/hcp/verify", response_model=APIResponse)
async def verify_hcp(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        hcp_id = body.get("hcp_id")
        if not hcp_id:
            raise HTTPException(status_code=400, detail="hcp_id is required")

        result = await engine.verify_hcp(hcp_id, db)
        return APIResponse(success=True, data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hcp/interaction-check", response_model=APIResponse)
async def check_interaction_compliance(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        interaction_id = body.get("interaction_id")
        if not interaction_id:
            raise HTTPException(status_code=400, detail="interaction_id is required")

        result = await engine.check_interaction_compliance(interaction_id, db)
        return APIResponse(success=True, data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hcp/payment-limit-check", response_model=APIResponse)
async def check_payment_limit(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        hcp_id = body.get("hcp_id")
        payment_amount = body.get("payment_amount")
        if not hcp_id or payment_amount is None:
            raise HTTPException(status_code=400, detail="hcp_id and payment_amount are required")

        result = await engine.check_payment_limit(hcp_id, payment_amount, db)
        return APIResponse(success=True, data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hcp/{hcp_id}/risk", response_model=APIResponse)
async def analyze_aggregate_risk(
    hcp_id: str,
    period: str = Query(..., description="年度, 如 2024"),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await engine.analyze_aggregate_risk(hcp_id, period, db)
        return APIResponse(success=True, data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
