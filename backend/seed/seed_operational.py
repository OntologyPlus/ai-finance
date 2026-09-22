from datetime import datetime
from decimal import Decimal

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from engines.budget_versioning import budget_versioning_engine
from engines.expense_ops import expense_ops_engine
from engines.rule_pinning import ensure_active_catalog
from models.budget import BudgetItem
from models.budget_version import BudgetVersion
from models.expense import ExpenseReport, InvoiceRecord
from models.expense_ops import ExpenseSettlement, ThreeFlowWhitelist


async def seed_operational(db: AsyncSession) -> None:
    """Attach operational evidence onto existing demo expenses/budgets."""
    catalog = await ensure_active_catalog(db)
    logger.info(f"Active rule catalog {catalog.version_id} sha={catalog.content_sha256[:12]}")

    expense = await db.get(ExpenseReport, "EXP-001")
    if expense is None:
        logger.warning("EXP-001 missing, skip operational expense seed")
    elif await db.get(ExpenseSettlement, "EXP-001") is None:
        existing_inv = (
            await db.execute(select(InvoiceRecord).where(InvoiceRecord.expense_id == "EXP-001"))
        ).scalars().first()
        if existing_inv is None:
            existing_inv = InvoiceRecord(
                invoice_id="INV-SEED01",
                expense_id="EXP-001",
                invoice_number="1101234560",
                invoice_code="044002500111",
                invoice_amount=Decimal("3500.00"),
                invoice_type="增值税电子普通发票",
                seller_name="北京差旅行有限公司",
                file_path="/demo/invoices/exp-001.png",
                is_duplicate=False,
            )
            db.add(existing_inv)
            await db.flush()

        pack = await expense_ops_engine.persist_pack(
            expense,
            {
                "source_bill_type": "TRAVEL",
                "source_id": "TA-2026-001",
                "source_code": "TA-2026-001",
                "source_name": "北京出差申请",
                "apply_money": 3500,
                "pre_pass_money": 3500,
                "real_money": 3380,
                "payee_name": "张三",
                "currency": "CNY",
                "invoices": [
                    {
                        "invoice_number": existing_inv.invoice_number,
                        "seller_name": "北京差旅行有限公司",
                        "seller_tax_no": "91110108MA01DEMO1",
                        "payee_name": "张三",
                        "merchant_name": "北京差旅行酒店",
                    }
                ],
                "ocr_images": [{"invoice_id": existing_inv.invoice_id, "image_url": existing_inv.file_path}],
            },
            db,
            invoices=[existing_inv],
        )
        logger.info(f"Seeded EXP-001 lines={len(pack.get('lines') or [])}")

        db.add(
            ThreeFlowWhitelist(
                whitelist_id="WL-SEED01",
                seller_name="北京华北医院劳务服务中心",
                seller_tax_no="91110000MAHCP001",
                payee_name="华建国",
                merchant_name="北京华北医院",
                reason="讲课费个人收款已备案",
                is_active=True,
            )
        )

        market = await db.get(ExpenseReport, "EXP-003")
        if market is not None:
            await expense_ops_engine.persist_pack(
                market,
                {
                    "source_bill_type": "ACTIVITY",
                    "source_id": "ACT-2026-088",
                    "source_code": "ACT-2026-088",
                    "source_name": "数字营销推广会",
                    "apply_money": 45000,
                    "hcp_guests": [
                        {
                            "activity_id": "ACT-2026-088",
                            "hcp_id": "HCP-001",
                            "doctor_name": "华建国",
                            "hospital_name": "北京华北医院",
                            "is_hcp": True,
                            "is_sign": "YES",
                            "sign_time": datetime(2026, 5, 18, 9, 30),
                            "sign_addr": "北京市东城区帅府园1号",
                            "longitude": "116.417",
                            "latitude": "39.911",
                            "meet_role": "讲者",
                            "know_books": [{"url": "/demo/know-books/hcp-001.pdf"}],
                        }
                    ],
                },
                db,
                invoices=[],
            )
    else:
        logger.info("Operational expense pack already present")

    existing_version = (await db.execute(select(BudgetVersion))).scalars().first()
    item = await db.get(BudgetItem, "BG-2026-001")
    if item is not None and existing_version is None:
        version = await budget_versioning_engine.snapshot(
            db,
            budget_year=2026,
            change_summary="2026 初始冻结版本",
            created_by="seed",
            freeze=True,
        )
        await budget_versioning_engine.add_reason(
            db,
            target_id="BG-2026-001",
            target_name=item.budget_name,
            reason_text="差旅预算承接 2026 年中心编制数，按上年执行率 92% 核定。",
            formula_text="2026差旅 = 2025实际 × 1.08",
            parameter_json={"baseline_2025": 120000, "growth_rate": 0.08, "amount": float(item.annual_amount or 0)},
            source_json=[
                {
                    "sourceType": "FILE",
                    "fileName": "2026年度预算编制底稿.xlsx",
                    "locator": "差旅!C12",
                    "usage": "上年实际与增长假设",
                }
            ],
            module_code="MAINTENANCE",
            version_id=version.version_id,
            data_scope="VERSION",
            created_by="seed",
        )
        await budget_versioning_engine.record_adjustment(
            db,
            target_id="BG-2026-001",
            before={"annual_amount": float(item.annual_amount or 0)},
            after={"annual_amount": float(item.annual_amount or 0) + 10000},
            reason="Q2 差旅追加（演示 diff，未执行）",
            amount_direction="increase",
            related_budget_id="BG-2026-001",
            formula_text="追加 = 10000",
            from_version_id=version.version_id,
            status="待审批",
            created_by="seed",
        )
    await db.flush()
    logger.info("Operational seed completed")
