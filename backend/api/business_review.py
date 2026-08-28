from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.schemas import APIResponse
from engines.business_review_engine import BusinessReviewEngine

router = APIRouter()

engine = BusinessReviewEngine()


@router.post("/business-review/agenda", response_model=APIResponse)
async def generate_agenda(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        meeting_type = body.get("meeting_type")
        period = body.get("period")
        if not all([meeting_type, period]):
            raise HTTPException(status_code=400, detail="meeting_type and period are required")

        result = await engine.generate_agenda(meeting_type, period, db)
        return APIResponse(success=True, data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/business-review/resolutions", response_model=APIResponse)
async def record_resolution(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        meeting_id = body.get("meeting_id")
        content = body.get("content")
        owner = body.get("owner")
        deadline = body.get("deadline")
        if not all([meeting_id, content, owner, deadline]):
            raise HTTPException(status_code=400, detail="meeting_id, content, owner, deadline are required")

        result = await engine.record_resolution(meeting_id, content, owner, deadline, db)
        return APIResponse(success=True, message="Resolution recorded", data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/business-review/resolutions/{resolution_id}/track", response_model=APIResponse)
async def track_resolution(
    resolution_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        progress = body.get("progress")
        risk_flag = body.get("risk_flag", "")
        if progress is None:
            raise HTTPException(status_code=400, detail="progress is required")

        result = await engine.track_resolution(resolution_id, progress, risk_flag, db)
        return APIResponse(success=True, message="Resolution tracked", data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/business-review/cross-center-compare", response_model=APIResponse)
async def cross_center_compare(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        period = body.get("period")
        center_ids = body.get("center_ids", [])
        if not period:
            raise HTTPException(status_code=400, detail="period is required")

        result = await engine.cross_center_compare(period, center_ids, db)
        return APIResponse(success=True, data=result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
