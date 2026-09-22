"""Budget version snapshots, freeze, and adjustment diffs."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.budget import BudgetItem
from models.budget_version import (
    BudgetAdjustmentRecord,
    BudgetReason,
    BudgetVersion,
    BudgetVersionItem,
)


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def _item_snapshot(item: BudgetItem) -> Dict[str, Any]:
    return {
        "budget_id": item.budget_id,
        "budget_name": item.budget_name,
        "budget_category": item.budget_category,
        "l1_code": item.l1_code,
        "l2_code": item.l2_code,
        "l3_code": item.l3_code,
        "quadrant": item.quadrant,
        "annual_amount": float(item.annual_amount or 0),
        "granted_amount": float(item.granted_amount or 0),
        "frozen_amount": float(item.frozen_amount or 0),
        "used_amount": float(item.used_amount or 0),
        "available_amount": float(item.available_amount or 0),
        "status": item.status,
        "center_id": item.center_id,
        "department_id": item.department_id,
        "product_variety": item.product_variety,
    }


class BudgetVersioningEngine:
    async def _next_version_no(self, budget_year: int, db: AsyncSession) -> str:
        rows = (
            await db.execute(
                select(BudgetVersion.version_no).where(BudgetVersion.budget_year == budget_year)
            )
        ).scalars().all()
        max_n = 0
        for no in rows:
            text = str(no or "")
            if not text.upper().startswith("V"):
                continue
            try:
                max_n = max(max_n, int(text[1:]))
            except ValueError:
                continue
        return f"V{max_n + 1}"

    async def current_version(self, db: AsyncSession, budget_year: Optional[int] = None) -> Optional[BudgetVersion]:
        stmt = select(BudgetVersion).where(BudgetVersion.is_current.is_(True))
        if budget_year:
            stmt = stmt.where(BudgetVersion.budget_year == budget_year)
        result = await db.execute(stmt)
        return result.scalars().first()

    async def snapshot(
        self,
        db: AsyncSession,
        *,
        budget_year: Optional[int] = None,
        change_summary: str = "",
        created_by: Optional[str] = None,
        status: str = "DRAFT",
        freeze: bool = False,
        parent_version_id: Optional[str] = None,
        budget_ids: Optional[List[str]] = None,
    ) -> BudgetVersion:
        year = budget_year or datetime.now().year
        # Frozen "current" versions are the SoT. A partial item list would
        # supersede a full freeze and look like other budgets vanished.
        if freeze:
            budget_ids = None
        parent = parent_version_id
        if parent is None:
            current = await self.current_version(db, year)
            parent = current.version_id if current else None
        version = BudgetVersion(
            version_id=_id("BV"),
            budget_year=year,
            version_no=await self._next_version_no(year, db),
            parent_version_id=parent,
            status="FROZEN" if freeze else status,
            is_current=bool(freeze),
            change_summary=change_summary or None,
            created_by=created_by,
        )
        if freeze:
            await self._supersede_current(db, year, except_id=None)
        db.add(version)
        await db.flush()

        stmt = select(BudgetItem)
        if budget_ids:
            stmt = stmt.where(BudgetItem.budget_id.in_(budget_ids))
        items = (await db.execute(stmt)).scalars().all()
        for item in items:
            db.add(
                BudgetVersionItem(
                    item_id=_id("BVI"),
                    version_id=version.version_id,
                    budget_id=item.budget_id,
                    annual_amount=Decimal(str(item.annual_amount or 0)),
                    granted_amount=Decimal(str(item.granted_amount or 0)),
                    frozen_amount=Decimal(str(item.frozen_amount or 0)),
                    used_amount=Decimal(str(item.used_amount or 0)),
                    available_amount=Decimal(str(item.available_amount or 0)),
                    snapshot_json=_item_snapshot(item),
                )
            )
        await db.flush()
        logger.info(f"Budget version {version.version_id} {version.version_no} status={version.status} items={len(items)}")
        return version

    async def _supersede_current(self, db: AsyncSession, budget_year: int, except_id: Optional[str]) -> None:
        stmt = select(BudgetVersion).where(
            BudgetVersion.budget_year == budget_year,
            BudgetVersion.is_current.is_(True),
        )
        for row in (await db.execute(stmt)).scalars().all():
            if except_id and row.version_id == except_id:
                continue
            row.is_current = False
            if row.status == "FROZEN":
                row.status = "SUPERSEDED"
        await db.flush()

    async def freeze(self, version_id: str, db: AsyncSession, created_by: Optional[str] = None) -> BudgetVersion:
        version = await db.get(BudgetVersion, version_id)
        if version is None:
            raise ValueError(f"Budget version {version_id} not found")
        await self._supersede_current(db, version.budget_year, except_id=version.version_id)
        version.status = "FROZEN"
        version.is_current = True
        if created_by:
            version.created_by = created_by
        await db.flush()
        return version

    async def record_adjustment(
        self,
        db: AsyncSession,
        *,
        target_id: str,
        before: Dict[str, Any],
        after: Dict[str, Any],
        reason: str,
        adjustment_type: str = "AMOUNT",
        amount_direction: Optional[str] = None,
        related_budget_id: Optional[str] = None,
        module_code: Optional[str] = None,
        formula_text: Optional[str] = None,
        created_by: Optional[str] = None,
        from_version_id: Optional[str] = None,
        status: str = "待审批",
        target_type: str = "BUDGET",
    ) -> BudgetAdjustmentRecord:
        if from_version_id is None:
            current = await self.current_version(db)
            from_version_id = current.version_id if current else None
        record = BudgetAdjustmentRecord(
            adjustment_id=_id("AD"),
            from_version_id=from_version_id,
            adjustment_type=adjustment_type,
            amount_direction=amount_direction,
            target_type=target_type,
            target_id=target_id,
            related_budget_id=related_budget_id or (target_id if target_type == "BUDGET" else None),
            module_code=module_code,
            before_json=before,
            after_json=after,
            reason=reason,
            formula_text=formula_text,
            status=status,
            created_by=created_by,
        )
        db.add(record)
        await db.flush()
        return record

    async def apply_amount_adjustment(
        self,
        adjustment_id: str,
        db: AsyncSession,
        applied_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        record = await db.get(BudgetAdjustmentRecord, adjustment_id)
        if record is None:
            raise ValueError(f"Adjustment {adjustment_id} not found")
        if record.status != "待审批":
            raise ValueError(f"Adjustment {adjustment_id} is {record.status}, expected 待审批")
        budget_id = record.related_budget_id or record.target_id
        item = await db.get(BudgetItem, budget_id)
        if item is None:
            raise ValueError(f"Budget item {budget_id} not found")

        before_version = await self.snapshot(
            db,
            change_summary=f"调整前快照 {adjustment_id}",
            created_by=applied_by,
            freeze=True,
        )
        after_amount = Decimal(str((record.after_json or {}).get("annual_amount", item.annual_amount)))
        delta = after_amount - Decimal(str(item.annual_amount or 0))
        item.annual_amount = after_amount
        item.available_amount = Decimal(str(item.available_amount or 0)) + delta
        await db.flush()
        after_version = await self.snapshot(
            db,
            change_summary=f"调整后冻结 {adjustment_id}: {record.reason}",
            created_by=applied_by,
            freeze=True,
            parent_version_id=before_version.version_id,
        )
        record.status = "已执行"
        record.from_version_id = before_version.version_id
        record.to_version_id = after_version.version_id
        await db.flush()
        return {
            "adjustment_id": record.adjustment_id,
            "from_version_id": before_version.version_id,
            "to_version_id": after_version.version_id,
            "budget_id": budget_id,
            "annual_amount": float(item.annual_amount),
        }

    async def add_reason(
        self,
        db: AsyncSession,
        *,
        target_id: str,
        reason_text: str,
        formula_text: Optional[str] = None,
        parameter_json: Optional[Dict[str, Any]] = None,
        source_json: Optional[Any] = None,
        module_code: str = "AMOUNT",
        risk_text: Optional[str] = None,
        version_id: Optional[str] = None,
        target_name: Optional[str] = None,
        created_by: Optional[str] = None,
        data_scope: str = "DRAFT",
        target_type: str = "BUDGET",
    ) -> BudgetReason:
        row = BudgetReason(
            reason_id=_id("BR"),
            version_id=version_id,
            data_scope=data_scope,
            target_type=target_type,
            target_id=target_id,
            target_name=target_name,
            module_code=module_code,
            formula_text=formula_text,
            parameter_json=parameter_json,
            source_json=source_json,
            reason_text=reason_text,
            risk_text=risk_text,
            created_by=created_by,
        )
        db.add(row)
        await db.flush()
        return row


budget_versioning_engine = BudgetVersioningEngine()
