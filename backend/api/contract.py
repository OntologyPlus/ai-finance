from typing import Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import get_db
from models.schemas import APIResponse, APIPageResponse
from models.contract import Contract

router = APIRouter()


@router.get("/contracts", response_model=APIPageResponse)
async def list_contracts(
    status: Optional[str] = Query(None),
    department_id: Optional[str] = Query(None),
    vendor_name: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    try:
        conditions = []
        if status:
            conditions.append(Contract.status == status)
        if department_id:
            conditions.append(Contract.department_id == department_id)
        if vendor_name:
            conditions.append(Contract.vendor_name.like(f"%{vendor_name}%"))

        stmt = select(Contract).where(and_(*conditions)) if conditions else select(Contract)
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


@router.get("/contracts/expiring", response_model=APIResponse)
async def get_expiring_contracts(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    try:
        now = datetime.now()
        threshold = now + timedelta(days=days)
        stmt = select(Contract).where(
            and_(
                Contract.end_date != None,
                Contract.end_date >= now,
                Contract.end_date <= threshold,
            )
        )
        result = await db.execute(stmt)
        items = result.scalars().all()
        data = [{c: getattr(r, c) for c in r.__table__.columns.keys()} for r in items]
        return APIResponse(success=True, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/contracts/{contract_id}", response_model=APIResponse)
async def get_contract(
    contract_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        contract = await db.get(Contract, contract_id)
        if contract is None:
            raise HTTPException(status_code=404, detail=f"Contract {contract_id} not found")

        data = {c: getattr(contract, c) for c in contract.__table__.columns.keys()}
        return APIResponse(success=True, data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/contracts", response_model=APIResponse)
async def create_contract(
    contract_data: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        contract = Contract(**contract_data)
        db.add(contract)
        await db.flush()
        data = {c: getattr(contract, c) for c in contract.__table__.columns.keys()}
        return APIResponse(success=True, message="Contract created", data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/contracts/{contract_id}", response_model=APIResponse)
async def update_contract(
    contract_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        contract = await db.get(Contract, contract_id)
        if contract is None:
            raise HTTPException(status_code=404, detail=f"Contract {contract_id} not found")

        for key, value in body.items():
            if hasattr(contract, key):
                setattr(contract, key, value)
        await db.flush()

        data = {c: getattr(contract, c) for c in contract.__table__.columns.keys()}
        return APIResponse(success=True, message="Contract updated", data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/contracts/{contract_id}/payment", response_model=APIResponse)
async def record_payment(
    contract_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    try:
        contract = await db.get(Contract, contract_id)
        if contract is None:
            raise HTTPException(status_code=404, detail=f"Contract {contract_id} not found")

        payment_amount = body.get("amount", 0)
        if payment_amount <= 0:
            raise HTTPException(status_code=400, detail="Payment amount must be positive")

        contract.paid_amount = (contract.paid_amount or 0) + payment_amount
        contract.updated_at = datetime.now()
        await db.flush()

        data = {c: getattr(contract, c) for c in contract.__table__.columns.keys()}
        return APIResponse(success=True, message="Payment recorded", data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
