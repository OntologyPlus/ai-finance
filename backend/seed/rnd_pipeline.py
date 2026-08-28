from datetime import datetime

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.rnd_pipeline import Pipeline, RnDProject, RnDMilestone, ClinicalTrial


PIPELINE_DATA = [
    {
        "pipeline_id": "PL-ONCO-001",
        "name": "肿瘤免疫管线",
        "indication": "非小细胞肺癌/黑色素瘤",
        "current_stage": "II期临床",
        "go_nogo_status": "Go",
        "estimated_launch_date": datetime(2028, 6, 30),
        "total_budget": 85000000,
        "consumed_budget": 32000000,
        "status": "活跃",
    },
    {
        "pipeline_id": "PL-META-001",
        "name": "代谢疾病管线",
        "indication": "2型糖尿病/肥胖",
        "current_stage": "I期临床",
        "go_nogo_status": "Go",
        "estimated_launch_date": datetime(2029, 12, 31),
        "total_budget": 52000000,
        "consumed_budget": 12000000,
        "status": "活跃",
    },
]

PROJECT_DATA = [
    {
        "project_id": "PRJ-ONCO-001",
        "name": "PD-1联合用药II期临床",
        "pipeline_id": "PL-ONCO-001",
        "project_type": "临床试验",
        "manager": "周明",
        "finance_budget": 25000000,
        "management_budget": 30000000,
        "consumed_finance": 10000000,
        "consumed_management": 12000000,
        "status": "进行中",
    },
    {
        "project_id": "PRJ-META-001",
        "name": "GLP-1受体激动剂I期临床",
        "pipeline_id": "PL-META-001",
        "project_type": "临床试验",
        "manager": "孙丽",
        "finance_budget": 15000000,
        "management_budget": 18000000,
        "consumed_finance": 5000000,
        "consumed_management": 6000000,
        "status": "进行中",
    },
]

MILESTONE_DATA = [
    # PD-1项目里程碑
    {
        "project_id": "PRJ-ONCO-001",
        "name": "II期临床启动",
        "planned_date": datetime(2025, 9, 1),
        "actual_date": datetime(2025, 9, 15),
        "status": "已完成",
        "cro_payment_id": None,
    },
    {
        "project_id": "PRJ-ONCO-001",
        "name": "首例入组",
        "planned_date": datetime(2025, 11, 1),
        "actual_date": datetime(2025, 11, 20),
        "status": "已完成",
        "cro_payment_id": "CRO-PAY-0001",
    },
    {
        "project_id": "PRJ-ONCO-001",
        "name": "中期分析",
        "planned_date": datetime(2026, 6, 1),
        "actual_date": None,
        "status": "待完成",
        "cro_payment_id": None,
    },
    {
        "project_id": "PRJ-ONCO-001",
        "name": "末例入组",
        "planned_date": datetime(2026, 9, 1),
        "actual_date": None,
        "status": "待完成",
        "cro_payment_id": None,
    },
    # GLP-1项目里程碑
    {
        "project_id": "PRJ-META-001",
        "name": "I期临床启动",
        "planned_date": datetime(2025, 12, 1),
        "actual_date": datetime(2025, 12, 10),
        "status": "已完成",
        "cro_payment_id": None,
    },
    {
        "project_id": "PRJ-META-001",
        "name": "SAD给药完成",
        "planned_date": datetime(2026, 3, 1),
        "actual_date": datetime(2026, 3, 15),
        "status": "已完成",
        "cro_payment_id": "CRO-PAY-0002",
    },
    {
        "project_id": "PRJ-META-001",
        "name": "MAD给药完成",
        "planned_date": datetime(2026, 7, 1),
        "actual_date": None,
        "status": "已延期",
        "cro_payment_id": None,
    },
]

TRIAL_DATA = [
    {
        "trial_id": "CT-ONCO-001",
        "name": "PD-1+CTLA-4联合治疗NSCLC II期试验",
        "phase": "II期",
        "cro_vendor": "药明康德",
        "center_count": 15,
        "total_cost": 22000000,
        "allocation_ratios": {
            "北京协和医院": 0.15,
            "上海瑞金医院": 0.12,
            "广州中山医院": 0.10,
            "华西医院": 0.10,
            "其他11家中心": 0.53,
        },
        "pipeline_id": "PL-ONCO-001",
        "status": "进行中",
    },
]


async def seed_rnd_pipeline(db: AsyncSession) -> None:
    logger.info("Seeding pipelines...")
    for data in PIPELINE_DATA:
        stmt = select(Pipeline).where(Pipeline.pipeline_id == data["pipeline_id"])
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is None:
            db.add(Pipeline(**data))
    await db.flush()

    logger.info("Seeding R&D projects...")
    for data in PROJECT_DATA:
        stmt = select(RnDProject).where(RnDProject.project_id == data["project_id"])
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is None:
            db.add(RnDProject(**data))
    await db.flush()

    logger.info("Seeding R&D milestones...")
    for data in MILESTONE_DATA:
        # 按project_id + name去重
        stmt = select(RnDMilestone).where(
            RnDMilestone.project_id == data["project_id"],
            RnDMilestone.name == data["name"],
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is None:
            db.add(RnDMilestone(**data))
    await db.flush()

    logger.info("Seeding clinical trials...")
    for data in TRIAL_DATA:
        stmt = select(ClinicalTrial).where(ClinicalTrial.trial_id == data["trial_id"])
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is None:
            db.add(ClinicalTrial(**data))
    await db.flush()

    logger.info("R&D pipeline seed completed.")
