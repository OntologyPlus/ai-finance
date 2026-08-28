from __future__ import annotations

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from models.scenario import Scenario, ElasticBudget, BudgetReserve


async def seed_scenario(db: AsyncSession) -> None:
    """初始化情景规划种子数据"""
    from sqlalchemy import select
    from models.scenario import ElasticBudget
    result = await db.execute(select(Scenario).limit(1))
    if result.scalar_one_or_none():
        logger.info("Scenario seed data already exists, skipping scenarios, but ensuring elastic_budgets...")
    else:
        # 基准情景
        db.add(Scenario(
            name="2024年度基准情景",
            scenario_type="基准",
            period="2024",
            assumptions={"revenue_growth": 0.1, "cost_growth": 0.05, "exchange_rate": 1.0, "base_revenue": 100000000, "base_cost": 80000000},
            budget_summary={"total_budget": 80000000, "budget_items": 22},
            status="已审批",
        ))

        # 悲观情景
        db.add(Scenario(
            name="2024年度悲观情景",
            scenario_type="悲观",
            period="2024",
            assumptions={"revenue_growth": -0.1, "cost_growth": 0.15, "exchange_rate": 0.95, "revenue_decline": 0.3, "cost_increase": 0.2, "base_revenue": 100000000, "base_cost": 80000000},
            budget_summary={"total_budget": 72000000, "budget_items": 22},
            status="草稿",
        ))

        # 乐观情景
        db.add(Scenario(
            name="2024年度乐观情景",
            scenario_type="乐观",
            period="2024",
            assumptions={"revenue_growth": 0.25, "cost_growth": 0.03, "exchange_rate": 1.05, "base_revenue": 100000000, "base_cost": 80000000},
            budget_summary={"total_budget": 92000000, "budget_items": 22},
            status="草稿",
        ))

        # 预算储备
        db.add(BudgetReserve(
            reserve_name="集团预算储备金",
            total_amount=10000000,
            used_amount=0,
            available_amount=10000000,
            approval_required=1,
        ))

    # v12.2: 弹性预算（按业务量联动调节，3 条不同驱动指标）
    eb_check = await db.execute(select(ElasticBudget).limit(1))
    if not eb_check.scalar_one_or_none():
        for budget_id, driver, base_vol, base_amt, coeff, cur_vol, ratio in [
            ("BG-2026-001", "门诊量", 100000, 5000000, 1.2, 110000, 0.3),
            ("BG-2026-002", "手术台次", 8000, 8000000, 0.9, 7200, 0.25),
            ("BG-2026-003", "住院床日", 50000, 12000000, 1.0, 55000, 0.35),
        ]:
            db.add(ElasticBudget(
                budget_id=budget_id,
                driver_metric=driver,
                base_volume=base_vol,
                base_amount=base_amt,
                elasticity_coefficient=coeff,
                current_volume=cur_vol,
                adjusted_amount=round(base_amt * (cur_vol / base_vol) * coeff, 2),
                max_adjustment_ratio=ratio,
            ))

    await db.flush()
    logger.info("Scenario seed data created")
