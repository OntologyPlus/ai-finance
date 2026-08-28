from __future__ import annotations

from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from models.cash_flow import CashFlowPlan, CashPool, PaymentSchedule, ReceiptForecast


async def seed_cash_flow(db: AsyncSession) -> None:
    """初始化现金流种子数据"""
    from sqlalchemy import select

    result = await db.execute(select(CashPool).limit(1))
    if result.scalar_one_or_none():
        logger.info("Cash flow seed data already exists, skipping")
        return

    # 资金池
    pool = CashPool(
        pool_name="集团主资金池",
        total_balance=50000000,
        min_balance=10000000,
        alert_threshold=15000000,
        aggregation_rule={"type": "daily", "threshold": 100000},
    )
    db.add(pool)

    # 现金流计划
    now = datetime.now()
    for i in range(3):
        period_date = datetime(now.year, now.month + i if now.month + i <= 12 else now.month + i - 12, 1)
        period = period_date.strftime("%Y-%m")
        for activity_type, inflow, outflow in [
            ("经营", 8000000, 6500000),
            ("投资", 0, 2000000),
            ("筹资", 0, 500000),
        ]:
            plan = CashFlowPlan(
                period=period,
                activity_type=activity_type,
                inflow_amount=inflow,
                outflow_amount=outflow,
                net_amount=inflow - outflow,
                status="执行中" if i == 0 else "草稿",
            )
            db.add(plan)

    # 付款排期
    for days_offset, amount, vendor in [
        (5, 500000, "供应商A"),
        (10, 300000, "CRO服务商B"),
        (15, 800000, "设备供应商C"),
        (20, 200000, "咨询服务D"),
    ]:
        schedule = PaymentSchedule(
            planned_date=now + timedelta(days=days_offset),
            planned_amount=amount,
            vendor_name=vendor,
            status="待付款",
        )
        db.add(schedule)

    # 收款预测
    for days_offset, amount, customer, confidence in [
        (3, 1200000, "客户甲", 0.9),
        (10, 800000, "客户乙", 0.7),
        (20, 500000, "客户丙", 0.5),
    ]:
        forecast = ReceiptForecast(
            forecast_date=now + timedelta(days=days_offset),
            forecast_amount=amount,
            customer_name=customer,
            confidence=confidence,
        )
        db.add(forecast)

    await db.flush()
    logger.info("Cash flow seed data created")
