from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from engines.budget_versioning import budget_versioning_engine
from engines.expense_ops import expense_ops_engine
from engines.hcp_compliance_engine import HCPComplianceEngine
from models.budget_version import BudgetAdjustmentRecord, BudgetReason, BudgetVersion, BudgetVersionItem
from models.database import get_db
from models.expense import ExpenseReport, InvoiceRecord
from models.expense_ops import ThreeFlowMismatch, ThreeFlowWhitelist
from models.hcp_compliance import HCPActivityGuest, HCPKnowBook, HCPSignEvidence
from models.rule_catalog import DecisionRulePin, RuleCatalogVersion
from models.schemas import APIResponse

router = APIRouter()
hcp_engine = HCPComplianceEngine()


def _row(obj):
    if obj is None:
        return None
    return jsonable_encoder({c: getattr(obj, c) for c in obj.__table__.columns.keys()})


def _rows(items):
    return [_row(i) for i in items]


@router.get("/expenses/three-flow", response_model=APIResponse)
async def list_three_flow(
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(ThreeFlowMismatch)
    if status:
        stmt = stmt.where(ThreeFlowMismatch.status == status)
    rows = (await db.execute(stmt)).scalars().all()
    return APIResponse(success=True, data=_rows(rows))


@router.post("/expenses/three-flow/whitelist", response_model=APIResponse)
async def add_three_flow_whitelist(body: dict, db: AsyncSession = Depends(get_db)):
    import uuid

    if not any([body.get("seller_tax_no"), body.get("payee_name"), body.get("merchant_name")]):
        raise HTTPException(status_code=400, detail="seller_tax_no、payee_name、merchant_name 至少填一项")
    row = ThreeFlowWhitelist(
        whitelist_id=f"WL-{uuid.uuid4().hex[:8].upper()}",
        seller_name=body.get("seller_name"),
        seller_tax_no=body.get("seller_tax_no"),
        payee_name=body.get("payee_name"),
        merchant_name=body.get("merchant_name"),
        reason=body.get("reason"),
        is_active=True,
    )
    db.add(row)
    await db.flush()
    return APIResponse(success=True, message="白名单已写入", data=_row(row))


@router.get("/expenses/{expense_id}/operational", response_model=APIResponse)
async def get_expense_operational(expense_id: str, db: AsyncSession = Depends(get_db)):
    expense = await db.get(ExpenseReport, expense_id)
    if expense is None:
        raise HTTPException(status_code=404, detail=f"Expense {expense_id} not found")
    pack = await expense_ops_engine.load_pack(expense_id, db)
    return APIResponse(
        success=True,
        data={
            "expense": _row(expense),
            "settlement": _row(pack["settlement"]),
            "lines": _rows(pack["lines"]),
            "ocr_runs": _rows(pack["ocr_runs"]),
            "ocr_images": _rows(pack["ocr_images"]),
            "three_flow": _rows(pack["three_flow"]),
            "merchants": _rows(pack["merchants"]),
            "hcp_guests": _rows(pack["hcp_guests"]),
            "hcp_signs": _rows(pack["hcp_signs"]),
            "hcp_know_books": _rows(pack["hcp_know_books"]),
        },
    )


@router.post("/expenses/{expense_id}/three-flow/check", response_model=APIResponse)
async def check_expense_three_flow(expense_id: str, body: dict, db: AsyncSession = Depends(get_db)):
    expense = await db.get(ExpenseReport, expense_id)
    if expense is None:
        raise HTTPException(status_code=404, detail=f"Expense {expense_id} not found")
    invoices = (
        await db.execute(select(InvoiceRecord).where(InvoiceRecord.expense_id == expense_id))
    ).scalars().all()
    result = await expense_ops_engine.check_three_flow(expense, body or {}, list(invoices), db)
    return APIResponse(
        success=True,
        message=f"三流检查完成，待确认 {result['pending_count']} 组",
        data={
            "mismatch_count": result["mismatch_count"],
            "pending_count": result["pending_count"],
            "mismatches": _rows(result["mismatches"]),
        },
    )


@router.get("/budgets/versions", response_model=APIResponse)
async def list_budget_versions(
    budget_year: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(BudgetVersion)
    if budget_year:
        stmt = stmt.where(BudgetVersion.budget_year == budget_year)
    stmt = stmt.order_by(BudgetVersion.created_at.desc())
    versions = (await db.execute(stmt)).scalars().all()
    return APIResponse(success=True, data=_rows(versions))


@router.post("/budgets/versions/snapshot", response_model=APIResponse)
async def snapshot_budget_version(body: dict, db: AsyncSession = Depends(get_db)):
    version = await budget_versioning_engine.snapshot(
        db,
        budget_year=body.get("budget_year"),
        change_summary=body.get("change_summary") or "",
        created_by=body.get("created_by"),
        freeze=bool(body.get("freeze")),
    )
    return APIResponse(success=True, message=f"已生成 {version.version_no}", data=_row(version))


@router.get("/budgets/versions/{version_id}", response_model=APIResponse)
async def get_budget_version(version_id: str, db: AsyncSession = Depends(get_db)):
    version = await db.get(BudgetVersion, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail=f"Version {version_id} not found")
    items = (
        await db.execute(select(BudgetVersionItem).where(BudgetVersionItem.version_id == version_id))
    ).scalars().all()
    reasons = (
        await db.execute(select(BudgetReason).where(BudgetReason.version_id == version_id))
    ).scalars().all()
    return APIResponse(
        success=True,
        data={"version": _row(version), "items": _rows(items), "reasons": _rows(reasons)},
    )


@router.post("/budgets/versions/{version_id}/freeze", response_model=APIResponse)
async def freeze_budget_version(version_id: str, body: dict = None, db: AsyncSession = Depends(get_db)):
    try:
        version = await budget_versioning_engine.freeze(
            version_id, db, created_by=(body or {}).get("created_by")
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return APIResponse(success=True, message="版本已冻结", data=_row(version))


@router.get("/budgets/adjustments", response_model=APIResponse)
async def list_budget_adjustments(db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(select(BudgetAdjustmentRecord).order_by(BudgetAdjustmentRecord.created_at.desc()))
    ).scalars().all()
    return APIResponse(success=True, data=_rows(rows))


@router.post("/budgets/adjustments/{adjustment_id}/apply", response_model=APIResponse)
async def apply_budget_adjustment(adjustment_id: str, body: dict = None, db: AsyncSession = Depends(get_db)):
    try:
        result = await budget_versioning_engine.apply_amount_adjustment(
            adjustment_id, db, applied_by=(body or {}).get("applied_by")
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return APIResponse(success=True, message="调整已执行并冻结新版本", data=result)


@router.get("/budgets/reasons", response_model=APIResponse)
async def list_budget_reasons(
    target_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(BudgetReason)
    if target_id:
        stmt = stmt.where(BudgetReason.target_id == target_id)
    rows = (await db.execute(stmt)).scalars().all()
    return APIResponse(success=True, data=_rows(rows))


@router.post("/budgets/reasons", response_model=APIResponse)
async def create_budget_reason(body: dict, db: AsyncSession = Depends(get_db)):
    if not body.get("target_id") or not body.get("reason_text"):
        raise HTTPException(status_code=400, detail="target_id and reason_text are required")
    row = await budget_versioning_engine.add_reason(
        db,
        target_id=body["target_id"],
        reason_text=body["reason_text"],
        formula_text=body.get("formula_text"),
        parameter_json=body.get("parameter_json"),
        source_json=body.get("source_json"),
        module_code=body.get("module_code") or "AMOUNT",
        risk_text=body.get("risk_text"),
        version_id=body.get("version_id"),
        target_name=body.get("target_name"),
        created_by=body.get("created_by"),
        data_scope=body.get("data_scope") or "DRAFT",
    )
    return APIResponse(success=True, data=_row(row))


@router.get("/hcp/{hcp_id}/evidence", response_model=APIResponse)
async def get_hcp_evidence(hcp_id: str, db: AsyncSession = Depends(get_db)):
    guests = (await db.execute(select(HCPActivityGuest).where(HCPActivityGuest.hcp_id == hcp_id))).scalars().all()
    signs = (await db.execute(select(HCPSignEvidence).where(HCPSignEvidence.hcp_id == hcp_id))).scalars().all()
    books = (await db.execute(select(HCPKnowBook).where(HCPKnowBook.hcp_id == hcp_id))).scalars().all()
    summary = await hcp_engine.collect_activity_evidence(hcp_id, db)
    return APIResponse(
        success=True,
        data={
            "summary": summary,
            "guests": _rows(guests),
            "signs": _rows(signs),
            "know_books": _rows(books),
        },
    )


@router.get("/decisions/rule-catalog", response_model=APIResponse)
async def get_rule_catalog(db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(select(RuleCatalogVersion).order_by(RuleCatalogVersion.version_no.desc()))
    ).scalars().all()
    return APIResponse(success=True, data=_rows(rows))


@router.get("/decisions/{decision_id}/rule-pin", response_model=APIResponse)
async def get_decision_rule_pin(decision_id: str, db: AsyncSession = Depends(get_db)):
    pin = (
        await db.execute(select(DecisionRulePin).where(DecisionRulePin.decision_id == decision_id))
    ).scalars().first()
    if pin is None:
        raise HTTPException(status_code=404, detail="No rule pin for this decision")
    return APIResponse(success=True, data=_row(pin))
