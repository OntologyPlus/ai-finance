from typing import Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.schemas import APIResponse, APIPageResponse
from models.archive import ArchiveRecord

router = APIRouter()


@router.get("/archives", response_model=APIPageResponse)
async def list_archives(
    archive_type: Optional[str] = Query(None),
    related_entity_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    try:
        conditions = []
        if archive_type:
            conditions.append(ArchiveRecord.archive_type == archive_type)
        if related_entity_type:
            conditions.append(ArchiveRecord.related_entity_type == related_entity_type)
        if status:
            conditions.append(ArchiveRecord.status == status)

        stmt = select(ArchiveRecord).where(and_(*conditions)) if conditions else select(ArchiveRecord)
        result = await db.execute(stmt)
        items = result.scalars().all()

        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        page_items = items[start:end]

        data = [{c: getattr(r, c) for c in r.__table__.columns.keys()} for r in page_items]

        return APIPageResponse(
            success=True,
            total=total,
            page=page,
            page_size=page_size,
            data=data,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/archives/retention/expiring", response_model=APIResponse)
async def get_retention_expiring_archives(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    try:
        now = datetime.now()
        threshold = now + timedelta(days=days)
        stmt = select(ArchiveRecord)
        result = await db.execute(stmt)
        items = result.scalars().all()

        expiring = []
        for item in items:
            if item.archived_at and item.retention_years:
                expiry_date = item.archived_at + timedelta(days=item.retention_years * 365)
                if now <= expiry_date <= threshold:
                    expiring.append({c: getattr(item, c) for c in item.__table__.columns.keys()})

        return APIResponse(success=True, data=expiring)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/archives/{archive_id}", response_model=APIResponse)
async def get_archive(
    archive_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        archive = await db.get(ArchiveRecord, archive_id)
        if archive is None:
            raise HTTPException(status_code=404, detail=f"Archive {archive_id} not found")

        data = {c: getattr(archive, c) for c in archive.__table__.columns.keys()}
        return APIResponse(success=True, data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/archives", response_model=APIResponse)
async def create_archive(
    archive_data: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        archive = ArchiveRecord(**archive_data)
        db.add(archive)
        await db.flush()
        data = {c: getattr(archive, c) for c in archive.__table__.columns.keys()}
        return APIResponse(success=True, message="Archive record created", data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/archives/{archive_id}", response_model=APIResponse)
async def update_archive(
    archive_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        archive = await db.get(ArchiveRecord, archive_id)
        if archive is None:
            raise HTTPException(status_code=404, detail=f"Archive {archive_id} not found")

        for key, value in body.items():
            if hasattr(archive, key):
                setattr(archive, key, value)
        await db.flush()

        data = {c: getattr(archive, c) for c in archive.__table__.columns.keys()}
        return APIResponse(success=True, message="Archive record updated", data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
