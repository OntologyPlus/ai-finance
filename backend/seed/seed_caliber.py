from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from models.caliber import CaliberMapping


MAPPINGS = [
    CaliberMapping(mapping_id="CM-B1", financial_code="B1", financial_name="研发费用", management_code="B1", management_name="研发投入", conversion_rule="1:1", adjustment_formula="financial * 1.15", difference_note="管理口径含资本化研发支出", sort_order=1),
    CaliberMapping(mapping_id="CM-B2", financial_code="B2", financial_name="市场费用", management_code="B2", management_name="市场投入", conversion_rule="1:1", adjustment_formula="financial * 1.15", difference_note="管理口径含品牌建设投入", sort_order=2),
    CaliberMapping(mapping_id="CM-B3", financial_code="B3", financial_name="管理费用", management_code="B3", management_name="管理运营", conversion_rule="1:1", adjustment_formula="financial", difference_note="口径一致", sort_order=3),
    CaliberMapping(mapping_id="CM-B4", financial_code="B4", financial_name="制造费用", management_code="B4", management_name="生产运营", conversion_rule="1:1", adjustment_formula="financial", difference_note="口径一致", sort_order=4),
    CaliberMapping(mapping_id="CM-B5", financial_code="B5", financial_name="采购费用", management_code="B5", management_name="供应链成本", conversion_rule="1:1", adjustment_formula="financial", difference_note="口径一致", sort_order=5),
    CaliberMapping(mapping_id="CM-B6", financial_code="B6", financial_name="人力成本", management_code="B6", management_name="人才投入", conversion_rule="1:1", adjustment_formula="financial * 1.10", difference_note="管理口径含培训发展费用", sort_order=6),
    CaliberMapping(mapping_id="CM-B7", financial_code="B7", financial_name="财务费用", management_code="B7", management_name="资金成本", conversion_rule="1:1", adjustment_formula="financial", difference_note="口径一致", sort_order=7),
    CaliberMapping(mapping_id="CM-B8", financial_code="B8", financial_name="税费", management_code="B8", management_name="税务成本", conversion_rule="1:1", adjustment_formula="financial * 0.92", difference_note="管理口径剔除不可抵扣税项", sort_order=8),
    CaliberMapping(mapping_id="CM-B9", financial_code="B9", financial_name="其他费用", management_code="B9", management_name="战略储备", conversion_rule="1:1", adjustment_formula="financial * 0.70", difference_note="管理口径剔除非战略支出", sort_order=9),
]


async def seed_caliber_mappings(db: AsyncSession) -> None:
    logger.info("Seeding caliber mappings...")
    for m in MAPPINGS:
        existing = await db.get(CaliberMapping, m.mapping_id)
        if existing is None:
            db.add(m)
    await db.flush()
    logger.info(f"Caliber mapping seed completed. {len(MAPPINGS)} mappings ready.")
