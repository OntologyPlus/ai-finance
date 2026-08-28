from datetime import datetime

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.cost_center import CostCenter, StandardCost


COST_CENTERS = [
    {
        "center_code": "CC-STRATEGY",
        "center_name": "战略规划中心",
        "center_type": "投资",
        "manager": "张明",
        "parent_center_id": None,
        "status": "活跃",
    },
    {
        "center_code": "CC-RD",
        "center_name": "研发中心",
        "center_type": "成本",
        "manager": "李华",
        "parent_center_id": None,
        "status": "活跃",
    },
    {
        "center_code": "CC-MARKETING",
        "center_name": "营销中心",
        "center_type": "利润",
        "manager": "王芳",
        "parent_center_id": None,
        "status": "活跃",
    },
    {
        "center_code": "CC-ADMIN",
        "center_name": "管理中心",
        "center_type": "成本",
        "manager": "赵刚",
        "parent_center_id": None,
        "status": "活跃",
    },
]

STANDARD_COSTS = [
    # 战略规划中心标准成本
    {
        "cost_center_id": 1,
        "cost_item": "战略咨询费",
        "standard_quantity": 12,
        "standard_price": 50000,
        "standard_total": 600000,
        "effective_from": datetime(2026, 1, 1),
    },
    {
        "cost_center_id": 1,
        "cost_item": "行业研究费",
        "standard_quantity": 4,
        "standard_price": 80000,
        "standard_total": 320000,
        "effective_from": datetime(2026, 1, 1),
    },
    # 研发中心标准成本
    {
        "cost_center_id": 2,
        "cost_item": "CRO服务费",
        "standard_quantity": 3,
        "standard_price": 1200000,
        "standard_total": 3600000,
        "effective_from": datetime(2026, 1, 1),
    },
    {
        "cost_center_id": 2,
        "cost_item": "实验材料费",
        "standard_quantity": 100,
        "standard_price": 5000,
        "standard_total": 500000,
        "effective_from": datetime(2026, 1, 1),
    },
    {
        "cost_center_id": 2,
        "cost_item": "设备维护费",
        "standard_quantity": 12,
        "standard_price": 30000,
        "standard_total": 360000,
        "effective_from": datetime(2026, 1, 1),
    },
    # 营销中心标准成本
    {
        "cost_center_id": 3,
        "cost_item": "学术推广费",
        "standard_quantity": 20,
        "standard_price": 50000,
        "standard_total": 1000000,
        "effective_from": datetime(2026, 1, 1),
    },
    {
        "cost_center_id": 3,
        "cost_item": "市场调研费",
        "standard_quantity": 6,
        "standard_price": 60000,
        "standard_total": 360000,
        "effective_from": datetime(2026, 1, 1),
    },
    # 管理中心标准成本
    {
        "cost_center_id": 4,
        "cost_item": "办公租赁费",
        "standard_quantity": 12,
        "standard_price": 150000,
        "standard_total": 1800000,
        "effective_from": datetime(2026, 1, 1),
    },
    {
        "cost_center_id": 4,
        "cost_item": "IT运维费",
        "standard_quantity": 12,
        "standard_price": 80000,
        "standard_total": 960000,
        "effective_from": datetime(2026, 1, 1),
    },
]


async def seed_cost_center(db: AsyncSession) -> None:
    logger.info("Seeding cost centers...")
    for data in COST_CENTERS:
        stmt = select(CostCenter).where(
            CostCenter.center_code == data["center_code"]
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is None:
            db.add(CostCenter(**data))
    await db.flush()

    logger.info("Seeding standard costs...")
    for data in STANDARD_COSTS:
        # 按center_id + cost_item去重
        stmt = select(StandardCost).where(
            StandardCost.cost_center_id == data["cost_center_id"],
            StandardCost.cost_item == data["cost_item"],
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is None:
            db.add(StandardCost(**data))
    await db.flush()

    logger.info("Cost center seed completed.")
