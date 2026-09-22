"""Persist expense lines, settlement, OCR stubs, merchant profile, three-flow."""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.expense import ExpenseReport, InvoiceRecord
from models.expense_ops import (
    ExpenseLine,
    ExpenseSettlement,
    InvoiceMerchantProfile,
    OcrImage,
    OcrRun,
    ThreeFlowMismatch,
    ThreeFlowWhitelist,
)
from models.hcp_compliance import HCPActivityGuest, HCPKnowBook, HCPSignEvidence


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def _money(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    return Decimal(str(value))


def normalize_party_name(name: Optional[str]) -> str:
    if not name:
        return ""
    text = str(name).strip().lower()
    for token in ("有限责任公司", "股份有限公司", "有限公司", "（", "）", "(", ")", " "):
        text = text.replace(token.lower() if token.isascii() else token, "")
    return text


class ExpenseOperationalEngine:
    """Companion writes for operational audit fields."""

    async def persist_pack(
        self,
        expense: ExpenseReport,
        expense_data: Dict[str, Any],
        db: AsyncSession,
        invoices: Optional[List[InvoiceRecord]] = None,
    ) -> Dict[str, Any]:
        existing = await db.get(ExpenseSettlement, expense.expense_id)
        if existing is not None:
            pack = await self.load_pack(expense.expense_id, db)
            mismatches = pack.get("three_flow") or []
            return {
                "lines": pack.get("lines") or [],
                "settlement": pack.get("settlement"),
                "ocr": pack.get("ocr_runs"),
                "merchants": pack.get("merchants") or [],
                "hcp_guests": pack.get("hcp_guests") or [],
                "three_flow": {
                    "mismatch_count": len(mismatches),
                    "pending_count": sum(1 for m in mismatches if getattr(m, "status", None) == "pending"),
                    "mismatches": mismatches,
                },
            }

        existing_lines = (
            await db.execute(select(ExpenseLine).where(ExpenseLine.expense_id == expense.expense_id))
        ).scalars().all()
        lines = list(existing_lines) if existing_lines else await self._persist_lines(expense, expense_data, db)
        settlement = await self._persist_settlement(expense, lines, expense_data, db)
        invoices = invoices or []
        ocr = None
        if not (
            await db.execute(select(OcrRun.run_id).where(OcrRun.expense_id == expense.expense_id).limit(1))
        ).scalars().first():
            ocr = await self._persist_ocr(expense, expense_data, invoices, db)
        merchants: List[InvoiceMerchantProfile] = []
        if not (
            await db.execute(
                select(InvoiceMerchantProfile.profile_id).where(
                    InvoiceMerchantProfile.expense_id == expense.expense_id
                ).limit(1)
            )
        ).scalars().first():
            merchants = await self._persist_merchants(expense, invoices, expense_data, db)
        guests: List[HCPActivityGuest] = []
        if not (
            await db.execute(
                select(HCPActivityGuest.guest_id).where(HCPActivityGuest.expense_id == expense.expense_id).limit(1)
            )
        ).scalars().first():
            guests = await self._persist_hcp_evidence(expense, expense_data, db)
        three_flow = await self.check_three_flow(expense, expense_data, invoices, db)
        return {
            "lines": lines,
            "settlement": settlement,
            "ocr": ocr,
            "merchants": merchants,
            "hcp_guests": guests,
            "three_flow": three_flow,
        }

    async def _persist_lines(
        self,
        expense: ExpenseReport,
        expense_data: Dict[str, Any],
        db: AsyncSession,
    ) -> List[ExpenseLine]:
        raw_lines = expense_data.get("lines") or expense_data.get("subject_lines") or []
        if not raw_lines:
            raw_lines = [
                {
                    "source_bill_type": expense_data.get("source_bill_type") or "NONE",
                    "source_id": expense_data.get("source_id"),
                    "source_code": expense_data.get("source_code"),
                    "source_name": expense_data.get("source_name"),
                    "budget_id": expense.budget_id,
                    "l1_code": expense.l1_code,
                    "l2_code": expense.l2_code,
                    "l3_code": expense.l3_code,
                    "duty_center_id": expense.center_id,
                    "apply_money": expense.amount,
                    "pre_pass_money": expense_data.get("pre_pass_money"),
                    "real_money": expense_data.get("real_money"),
                    "offset_money": expense_data.get("offset_money"),
                }
            ]
        created: List[ExpenseLine] = []
        for idx, raw in enumerate(raw_lines, start=1):
            line = ExpenseLine(
                line_id=_id("EL"),
                expense_id=expense.expense_id,
                seq_no=int(raw.get("seq_no") or idx),
                source_bill_type=raw.get("source_bill_type") or "NONE",
                source_id=raw.get("source_id"),
                source_code=raw.get("source_code"),
                source_name=raw.get("source_name"),
                budget_id=raw.get("budget_id") or expense.budget_id,
                l1_code=raw.get("l1_code") or expense.l1_code,
                l2_code=raw.get("l2_code") or expense.l2_code,
                l3_code=raw.get("l3_code") or expense.l3_code,
                duty_center_id=raw.get("duty_center_id") or expense.center_id,
                apply_money=_money(
                    raw["apply_money"]
                    if raw.get("apply_money") is not None
                    else raw["amount"]
                    if raw.get("amount") is not None
                    else expense.amount
                ),
                pre_pass_money=_money(raw["pre_pass_money"]) if raw.get("pre_pass_money") is not None else None,
                real_money=_money(raw["real_money"]) if raw.get("real_money") is not None else None,
                offset_money=_money(raw["offset_money"]) if raw.get("offset_money") is not None else None,
            )
            db.add(line)
            created.append(line)
        await db.flush()
        return created

    async def _persist_settlement(
        self,
        expense: ExpenseReport,
        lines: List[ExpenseLine],
        expense_data: Dict[str, Any],
        db: AsyncSession,
    ) -> ExpenseSettlement:
        apply_total = sum((line.apply_money or Decimal("0")) for line in lines) or _money(expense.amount)
        settlement = ExpenseSettlement(
            expense_id=expense.expense_id,
            apply_money=_money(expense_data.get("apply_money")) if expense_data.get("apply_money") is not None else apply_total,
            pre_pass_money=_money(expense_data["pre_pass_money"]) if expense_data.get("pre_pass_money") is not None else None,
            real_money=_money(expense_data["real_money"]) if expense_data.get("real_money") is not None else None,
            pay_money=_money(expense_data["pay_money"]) if expense_data.get("pay_money") is not None else None,
            offset_money=_money(expense_data["offset_money"]) if expense_data.get("offset_money") is not None else None,
            currency=expense_data.get("currency") or "CNY",
        )
        db.add(settlement)
        await db.flush()
        return settlement

    async def _persist_ocr(
        self,
        expense: ExpenseReport,
        expense_data: Dict[str, Any],
        invoices: List[InvoiceRecord],
        db: AsyncSession,
    ) -> Optional[OcrRun]:
        images = []
        seen: set[tuple[str, str]] = set()
        for inv in invoices:
            url = getattr(inv, "file_path", None)
            if url:
                key = (inv.invoice_id or "", url)
                if key not in seen:
                    seen.add(key)
                    images.append({"invoice_id": inv.invoice_id, "image_url": url})
        for raw in expense_data.get("ocr_images") or []:
            url = raw.get("image_url")
            if not url:
                continue
            key = (raw.get("invoice_id") or "", url)
            if key in seen:
                continue
            seen.add(key)
            images.append(raw)
        if not images:
            return None
        run = OcrRun(
            run_id=_id("OCR"),
            expense_id=expense.expense_id,
            provider=expense_data.get("ocr_provider") or "pending",
            status="pending",
            progress_total=len(images),
            progress_done=0,
        )
        db.add(run)
        await db.flush()
        for raw in images:
            db.add(
                OcrImage(
                    image_id=_id("OI"),
                    run_id=run.run_id,
                    invoice_id=raw.get("invoice_id"),
                    image_url=raw.get("image_url") or "",
                    status=raw.get("status") or "pending",
                    doc_type=raw.get("doc_type"),
                    confidence=raw.get("confidence"),
                    ocr_raw=raw.get("ocr_raw"),
                )
            )
        await db.flush()
        return run

    async def _persist_merchants(
        self,
        expense: ExpenseReport,
        invoices: List[InvoiceRecord],
        expense_data: Dict[str, Any],
        db: AsyncSession,
    ) -> List[InvoiceMerchantProfile]:
        created: List[InvoiceMerchantProfile] = []
        extras = {m.get("invoice_id"): m for m in (expense_data.get("merchants") or []) if m.get("invoice_id")}
        for inv in invoices:
            extra = extras.get(inv.invoice_id) or {}
            name = extra.get("seller_name") or inv.seller_name
            if not name:
                continue
            profile = InvoiceMerchantProfile(
                profile_id=_id("MP"),
                invoice_id=inv.invoice_id,
                expense_id=expense.expense_id,
                seller_name=name,
                credit_code=extra.get("credit_code"),
                legal_person_name=extra.get("legal_person_name"),
                industry=extra.get("industry"),
                reg_status=extra.get("reg_status"),
                risk_summaries_json=extra.get("risk_summaries_json"),
            )
            db.add(profile)
            created.append(profile)
        await db.flush()
        return created

    async def _persist_hcp_evidence(
        self,
        expense: ExpenseReport,
        expense_data: Dict[str, Any],
        db: AsyncSession,
    ) -> List[HCPActivityGuest]:
        guests_raw = expense_data.get("hcp_guests") or expense_data.get("activity_guests") or []
        created: List[HCPActivityGuest] = []
        for raw in guests_raw:
            guest = HCPActivityGuest(
                guest_id=_id("HG"),
                expense_id=expense.expense_id,
                activity_id=raw.get("activity_id") or expense_data.get("source_id"),
                hcp_id=raw.get("hcp_id"),
                doctor_name=raw.get("doctor_name") or raw.get("name") or "",
                hospital_name=raw.get("hospital_name") or raw.get("institution"),
                is_hcp=1 if raw.get("is_hcp", True) else 0,
                is_sign="YES" if str(raw.get("is_sign") or "").upper() in ("YES", "1", "TRUE") else "NO",
                sign_time=raw.get("sign_time"),
                sign_addr=raw.get("sign_addr") or raw.get("address"),
                sign_longitude=str(raw.get("longitude")) if raw.get("longitude") is not None else None,
                sign_latitude=str(raw.get("latitude")) if raw.get("latitude") is not None else None,
                meet_role=raw.get("meet_role"),
                know_book_count=int(raw.get("know_book_count") or len(raw.get("know_books") or [])),
            )
            db.add(guest)
            created.append(guest)
            await db.flush()
            if guest.is_sign == "YES":
                db.add(
                    HCPSignEvidence(
                        sign_id=_id("HS"),
                        expense_id=expense.expense_id,
                        hcp_id=guest.hcp_id,
                        guest_id=guest.guest_id,
                        sign_time=guest.sign_time,
                        address=guest.sign_addr,
                        longitude=guest.sign_longitude,
                        latitude=guest.sign_latitude,
                        valid=1,
                    )
                )
            for seq, book in enumerate(raw.get("know_books") or [], start=1):
                url = book if isinstance(book, str) else book.get("url")
                if not url:
                    continue
                db.add(
                    HCPKnowBook(
                        book_id=_id("HK"),
                        expense_id=expense.expense_id,
                        hcp_id=guest.hcp_id,
                        guest_id=guest.guest_id,
                        file_url=url,
                        seq_no=seq,
                    )
                )
        await db.flush()
        return created

    async def check_three_flow(
        self,
        expense: ExpenseReport,
        expense_data: Dict[str, Any],
        invoices: List[InvoiceRecord],
        db: AsyncSession,
    ) -> Dict[str, Any]:
        payee = expense_data.get("payee_name")
        mismatches: List[ThreeFlowMismatch] = []
        for inv in invoices:
            extra = {}
            for raw in expense_data.get("invoices") or []:
                if raw.get("invoice_number") == inv.invoice_number:
                    extra = raw
                    break
            seller = extra.get("seller_name") or inv.seller_name
            tax_no = extra.get("seller_tax_no") or extra.get("credit_code")
            merchant = extra.get("merchant_name")
            row_payee = extra.get("payee_name") or payee
            parties = [seller, row_payee, merchant]
            present = [p for p in parties if p]
            if len(present) < 2:
                continue
            names = [normalize_party_name(p) for p in present]
            if len(set(names)) <= 1:
                continue
            existing_mismatch = (
                await db.execute(
                    select(ThreeFlowMismatch).where(
                        ThreeFlowMismatch.expense_id == expense.expense_id,
                        ThreeFlowMismatch.invoice_id == inv.invoice_id,
                    )
                )
            ).scalars().first()
            if existing_mismatch:
                mismatches.append(existing_mismatch)
                continue
            wl = await self._match_whitelist(db, tax_no, row_payee, merchant)
            mismatch = ThreeFlowMismatch(
                mismatch_id=_id("TFM"),
                expense_id=expense.expense_id,
                invoice_id=inv.invoice_id,
                seller_name=seller,
                seller_tax_no=tax_no,
                payee_name=row_payee,
                merchant_name=merchant,
                status="whitelisted" if wl else "pending",
                whitelist_id=wl.whitelist_id if wl else None,
            )
            db.add(mismatch)
            mismatches.append(mismatch)
        await db.flush()
        return {
            "mismatch_count": len(mismatches),
            "pending_count": sum(1 for m in mismatches if m.status == "pending"),
            "mismatches": mismatches,
        }

    async def _match_whitelist(
        self,
        db: AsyncSession,
        tax_no: Optional[str],
        payee: Optional[str],
        merchant: Optional[str],
    ) -> Optional[ThreeFlowWhitelist]:
        stmt = select(ThreeFlowWhitelist).where(ThreeFlowWhitelist.is_active.is_(True))
        result = await db.execute(stmt)
        for row in result.scalars().all():
            if not any([row.seller_tax_no, row.payee_name, row.merchant_name]):
                continue
            tax_ok = not row.seller_tax_no or row.seller_tax_no == tax_no
            payee_ok = not row.payee_name or normalize_party_name(row.payee_name) == normalize_party_name(payee)
            merchant_ok = not row.merchant_name or normalize_party_name(row.merchant_name) == normalize_party_name(merchant)
            if tax_ok and payee_ok and merchant_ok:
                return row
        return None

    async def load_pack(self, expense_id: str, db: AsyncSession) -> Dict[str, Any]:
        lines = (await db.execute(select(ExpenseLine).where(ExpenseLine.expense_id == expense_id))).scalars().all()
        settlement = await db.get(ExpenseSettlement, expense_id)
        ocr_runs = (await db.execute(select(OcrRun).where(OcrRun.expense_id == expense_id))).scalars().all()
        mismatches = (await db.execute(select(ThreeFlowMismatch).where(ThreeFlowMismatch.expense_id == expense_id))).scalars().all()
        merchants = (await db.execute(select(InvoiceMerchantProfile).where(InvoiceMerchantProfile.expense_id == expense_id))).scalars().all()
        guests = (await db.execute(select(HCPActivityGuest).where(HCPActivityGuest.expense_id == expense_id))).scalars().all()
        signs = (await db.execute(select(HCPSignEvidence).where(HCPSignEvidence.expense_id == expense_id))).scalars().all()
        books = (await db.execute(select(HCPKnowBook).where(HCPKnowBook.expense_id == expense_id))).scalars().all()
        images = []
        for run in ocr_runs:
            images.extend((await db.execute(select(OcrImage).where(OcrImage.run_id == run.run_id))).scalars().all())
        return {
            "lines": lines,
            "settlement": settlement,
            "ocr_runs": ocr_runs,
            "ocr_images": images,
            "three_flow": mismatches,
            "merchants": merchants,
            "hcp_guests": guests,
            "hcp_signs": signs,
            "hcp_know_books": books,
        }


expense_ops_engine = ExpenseOperationalEngine()
