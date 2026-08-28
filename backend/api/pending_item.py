from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.schemas import APIResponse, APIPageResponse
from models.pending_item import PendingItem

router = APIRouter()


@router.get("/pending-items", response_model=APIPageResponse)
async def list_pending_items(
    source_year: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    try:
        conditions = []
        if source_year:
            conditions.append(PendingItem.source_year == source_year)
        if status:
            conditions.append(PendingItem.status == status)
        if priority:
            conditions.append(PendingItem.priority == priority)

        stmt = select(PendingItem).where(and_(*conditions)) if conditions else select(PendingItem)
        result = await db.execute(stmt)
        items = result.scalars().all()

        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        page_items = items[start:end]

        data = [{c: getattr(r, c) for c in r.__table__.columns.keys()} for r in page_items]
        return APIPageResponse(success=True, total=total, page=page, page_size=page_size, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pending-items/{item_id}", response_model=APIResponse)
async def get_pending_item(
    item_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await db.get(PendingItem, item_id)
        if item is None:
            raise HTTPException(status_code=404, detail=f"PendingItem {item_id} not found")
        data = {c: getattr(item, c) for c in item.__table__.columns.keys()}
        return APIResponse(success=True, data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pending-items", response_model=APIResponse)
async def create_pending_item(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        item_id = body.get("id")
        if not item_id:
            raise HTTPException(status_code=400, detail="id is required")

        existing = await db.get(PendingItem, item_id)
        if existing:
            raise HTTPException(status_code=409, detail=f"PendingItem {item_id} already exists")

        item = PendingItem(**body)
        db.add(item)
        await db.flush()

        data = {c: getattr(item, c) for c in item.__table__.columns.keys()}
        return APIResponse(success=True, message="Pending item created", data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/pending-items/{item_id}", response_model=APIResponse)
async def update_pending_item(
    item_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await db.get(PendingItem, item_id)
        if item is None:
            raise HTTPException(status_code=404, detail=f"PendingItem {item_id} not found")

        for key, value in body.items():
            if hasattr(item, key) and key != "id":
                setattr(item, key, value)

        await db.flush()

        data = {c: getattr(item, c) for c in item.__table__.columns.keys()}
        return APIResponse(success=True, message="Pending item updated", data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pending-items/{item_id}/resolve", response_model=APIResponse)
async def resolve_pending_item(
    item_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        item = await db.get(PendingItem, item_id)
        if item is None:
            raise HTTPException(status_code=404, detail=f"PendingItem {item_id} not found")

        from datetime import datetime
        item.status = "已解决"
        item.resolution = body.get("resolution", "")
        item.resolved_at = datetime.now()

        await db.flush()

        data = {c: getattr(item, c) for c in item.__table__.columns.keys()}
        return APIResponse(success=True, message="Pending item resolved", data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
