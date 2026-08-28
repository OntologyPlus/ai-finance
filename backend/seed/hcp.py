from datetime import datetime

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.hcp_compliance import HCP, ComplianceRule


HCP_DATA = [
    {
        "hcp_id": "HCP-001",
        "name": "陈建国",
        "institution": "北京协和医院",
        "department": "肿瘤内科",
        "specialty": "肿瘤免疫治疗",
        "verification_status": "已验证",
        "annual_interaction_count": 5,
        "annual_payment_total": 35000,
        "payment_limit": 50000,
    },
    {
        "hcp_id": "HCP-002",
        "name": "刘美华",
        "institution": "上海瑞金医院",
        "department": "内分泌科",
        "specialty": "糖尿病与代谢疾病",
        "verification_status": "待验证",
        "annual_interaction_count": 2,
        "annual_payment_total": 15000,
        "payment_limit": 50000,
    },
    {
        "hcp_id": "HCP-003",
        "name": "王志远",
        "institution": "广州中山医院",
        "department": "心血管内科",
        "specialty": "心血管疾病",
        "verification_status": "已验证",
        "annual_interaction_count": 8,
        "annual_payment_total": 48000,
        "payment_limit": 50000,
    },
]

COMPLIANCE_RULES = [
    {
        "rule_id": "HR-026",
        "rule_name": "HCP付款前验证",
        "legal_basis": "《医药行业合规管理指引》第12条",
        "check_logic": "付款前必须验证HCP身份和资质，未验证的HCP不得进行付款",
        "violation_action": "阻止付款，要求先完成HCP验证",
        "is_active": 1,
    },
    {
        "rule_id": "HR-027",
        "rule_name": "HCP年度付款限额",
        "legal_basis": "《医药行业合规管理指引》第15条",
        "check_logic": "HCP年度付款总额不得超过年度限额（默认50000元），超限额付款须特别审批",
        "violation_action": "阻止超限额付款，须合规总监审批后方可执行",
        "is_active": 1,
    },
]


async def seed_hcp(db: AsyncSession) -> None:
    logger.info("Seeding HCPs...")
    for data in HCP_DATA:
        stmt = select(HCP).where(HCP.hcp_id == data["hcp_id"])
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is None:
            db.add(HCP(**data))
    await db.flush()

    logger.info("Seeding compliance rules...")
    for data in COMPLIANCE_RULES:
        stmt = select(ComplianceRule).where(ComplianceRule.rule_id == data["rule_id"])
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is None:
            db.add(ComplianceRule(**data))
    await db.flush()

    logger.info("HCP seed completed.")
