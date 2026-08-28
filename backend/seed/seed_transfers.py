from datetime import datetime
from decimal import Decimal

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from models.transfer import BudgetTransferRequest


TRANSFERS = [
    BudgetTransferRequest(
        transfer_id="TF-DEMO001",
        from_budget_id="BG-2026-010",
        to_budget_id="BG-2026-011",
        from_quadrant="收缩",
        to_quadrant="发展",
        amount=Decimal("50000.00"),
        same_quadrant="否",
        approval_required="中心负责人审批",
        status="已执行",
        requested_by="admin",
        approved_by="center_mgr_li",
        executed_at=datetime(2026, 5, 15, 10, 0),
    ),
    BudgetTransferRequest(
        transfer_id="TF-DEMO002",
        from_budget_id="BG-2026-008",
        to_budget_id="BG-2026-002",
        from_quadrant="稳定",
        to_quadrant="发展",
        amount=Decimal("30000.00"),
        same_quadrant="否",
        approval_required="CFO审批",
        status="已审批",
        requested_by="dept_head_wang",
        approved_by="cfo_zhang",
    ),
    BudgetTransferRequest(
        transfer_id="TF-DEMO003",
        from_budget_id="BG-2026-004",
        to_budget_id="BG-2026-009",
        from_quadrant="稳定",
        to_quadrant="稳定",
        amount=Decimal("20000.00"),
        same_quadrant="是",
        approval_required="部门负责人审批",
        status="待审批",
        requested_by="finance_bp_chen",
    ),
]


async def seed_transfers(db: AsyncSession) -> None:
    logger.info("Seeding budget transfer requests...")
    for t in TRANSFERS:
        existing = await db.get(BudgetTransferRequest, t.transfer_id)
        if existing is None:
            db.add(t)
    await db.flush()
    logger.info(f"Transfer seed completed. {len(TRANSFERS)} transfers ready.")
