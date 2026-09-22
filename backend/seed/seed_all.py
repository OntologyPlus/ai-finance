import asyncio
import sys
from pathlib import Path

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import db_manager, get_db, init_db
from models.budget import BudgetSubjectL1, BudgetSubjectL2, BudgetSubjectL3, BudgetItem, B2AConversion, ControlMode
from models.expense import ExpenseReport, InvoiceRecord, BudgetWriteOff
from models.approval import ApprovalRecord
from models.alert import AlertRecord, AlertClosure, AlertEscalation
from models.organization import Department, Role, Employee
from models.analysis import ExecutionRate, GapAnalysis, ListAnalysis, MonthlyReport
from models.ontology import OntologyObject, OntologyRelation, OntologyBehavior, OntologyRule, OntologyScene, ReasoningTrace
from models.caliber import CaliberMapping, CaliberDifference
from models.transfer import BudgetTransferRequest
from models.cash_flow import CashFlowPlan, CashPool, PaymentSchedule, ReceiptForecast
from models.cost_center import CostCenter, StandardCost
from models.hcp_compliance import HCP, ComplianceRule, HCPActivityGuest, HCPSignEvidence, HCPKnowBook
from models.rnd_pipeline import Pipeline, RnDProject, RnDMilestone, ClinicalTrial
from models.scenario import Scenario, ElasticBudget, BudgetReserve
from models.expense_ops import (
    ExpenseLine,
    ExpenseSettlement,
    InvoiceMerchantProfile,
    OcrRun,
    OcrImage,
    ThreeFlowMismatch,
    ThreeFlowWhitelist,
)
from models.budget_version import BudgetVersion, BudgetVersionItem, BudgetAdjustmentRecord, BudgetReason
from models.rule_catalog import RuleCatalogVersion, DecisionRulePin

from seed.seed_budget import seed_budget
from seed.seed_organization import seed_organization
from seed.seed_demo_data import seed_demo_data
from seed.seed_alert_rules import seed_alert_rules
from seed.seed_ontology_definitions import seed_ontology_definitions
from seed.seed_ontology_instances import seed_ontology_instances
from seed.seed_forms import seed_forms
from seed.seed_users import seed_users
from seed.seed_caliber import seed_caliber_mappings
from seed.seed_transfers import seed_transfers
from seed.cash_flow import seed_cash_flow
from seed.cost_center import seed_cost_center
from seed.hcp import seed_hcp
from seed.rnd_pipeline import seed_rnd_pipeline
from seed.scenario import seed_scenario
from seed.seed_operational import seed_operational
from models.ontology import OntologyObjectInstance, OntologyRelationInstance, OntologyEventRecord, OntologyVersionSnapshot, OntologyConsistencyIssue
from models.user import User


CLEAR_ORDER = [
    ReasoningTrace,
    OntologyConsistencyIssue,
    OntologyVersionSnapshot,
    OntologyEventRecord,
    OntologyRelationInstance,
    OntologyObjectInstance,
    OntologyScene,
    OntologyBehavior,
    OntologyRelation,
    OntologyObject,
    OntologyRule,
    DecisionRulePin,
    RuleCatalogVersion,
    OcrImage,
    OcrRun,
    ThreeFlowMismatch,
    ThreeFlowWhitelist,
    InvoiceMerchantProfile,
    ExpenseLine,
    ExpenseSettlement,
    HCPKnowBook,
    HCPSignEvidence,
    HCPActivityGuest,
    BudgetReason,
    BudgetAdjustmentRecord,
    BudgetVersionItem,
    BudgetVersion,
    ReceiptForecast,
    PaymentSchedule,
    CashPool,
    CashFlowPlan,
    ClinicalTrial,
    RnDMilestone,
    RnDProject,
    Pipeline,
    ComplianceRule,
    HCP,
    StandardCost,
    CostCenter,
    BudgetReserve,
    ElasticBudget,
    Scenario,
    BudgetTransferRequest,
    CaliberDifference,
    CaliberMapping,
    AlertEscalation,
    AlertClosure,
    AlertRecord,
    ApprovalRecord,
    BudgetWriteOff,
    InvoiceRecord,
    ExpenseReport,
    ExecutionRate,
    GapAnalysis,
    ListAnalysis,
    MonthlyReport,
    B2AConversion,
    BudgetItem,
    BudgetSubjectL3,
    BudgetSubjectL2,
    BudgetSubjectL1,
    ControlMode,
    Employee,
    Role,
    Department,
    User,
]


async def _clear_all_data(db: AsyncSession) -> None:
    logger.info("Clearing existing data...")
    # Disable foreign key checks to avoid self-referential and cross-table constraint errors
    await db.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
    for model in CLEAR_ORDER:
        await db.execute(text(f"DELETE FROM {model.__tablename__}"))
    await db.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    await db.flush()
    logger.info("All existing data cleared.")


async def seed_all(force_reload: bool = False) -> None:
    """v12.2: 一键填充全部演示数据

    Args:
        force_reload: True 时先清空所有表再 seed（重建）；False 时仅增量（已有数据保留）

    包含 15 步：
        1.  组织数据（4 中心 + 12 部门 + 20 员工）
        2.  预算科目（9 L1 / 12 L2 / 70 L3 / 4 控制模式）
        3.  预算项 + B2A 转换
        4.  预警规则
        5.  本体定义
        6.  演示数据（费用 / 审批 / 预警 / 执行率 / 月报）
        7.  本体实例
        8.  表单模板
        9.  用户
        10. 口径映射
        11. 预算调拨
        12. 现金流（v12.2 接入）
        13. 成本中心（v12.2 接入）
        14. HCP 合规（v12.2 接入）
        15. 研发管线（v12.2 接入）
        16. 情景规划（v12.2 接入）
    """
    logger.info("=" * 60)
    logger.info("Starting full database seed...")
    logger.info("=" * 60)

    await init_db()

    async with db_manager.async_session_factory() as session:
        try:
            if force_reload:
                await _clear_all_data(session)
                await session.commit()
            logger.info("Step 1/16: Seeding organization data...")
            await seed_organization(session)
            await session.commit()
            logger.info("Step 2/16: Seeding budget data...")
            await seed_budget(session)
            await session.commit()
            logger.info("Step 3/16: Seeding alert rules...")
            await seed_alert_rules(session)
            await session.commit()
            logger.info("Step 4/16: Seeding ontology definitions...")
            await seed_ontology_definitions(session)
            await session.commit()
            logger.info("Step 5/16: Seeding demo data...")
            await seed_demo_data(session)
            await session.commit()
            logger.info("Step 6/16: Seeding ontology instances...")
            await seed_ontology_instances(session)
            await session.commit()
            logger.info("Step 7/16: Seeding form templates...")
            await seed_forms(session)
            await session.commit()
            logger.info("Step 8/16: Seeding users...")
            await seed_users(session)
            await session.commit()
            logger.info("Step 9/16: Seeding caliber mappings...")
            await seed_caliber_mappings(session)
            await session.commit()
            logger.info("Step 10/16: Seeding budget transfers...")
            await seed_transfers(session)
            await session.commit()
            logger.info("Step 11/16: Seeding cash flow...")
            await seed_cash_flow(session)
            await session.commit()
            logger.info("Step 12/16: Seeding cost center...")
            await seed_cost_center(session)
            await session.commit()
            logger.info("Step 13/16: Seeding HCP compliance...")
            await seed_hcp(session)
            await session.commit()
            logger.info("Step 14/16: Seeding R&D pipeline...")
            await seed_rnd_pipeline(session)
            await session.commit()
            logger.info("Step 15/16: Seeding scenario planning...")
            await seed_scenario(session)
            await session.commit()
            logger.info("Step 16/17: Seeding operational audit/budget version layer...")
            await seed_operational(session)
            await session.commit()
            logger.info("=" * 60)
            logger.info("Full database seed completed successfully! (17 steps)")
            logger.info("=" * 60)
        except Exception as e:
            await session.rollback()
            logger.error(f"Seed failed: {e}")
            raise


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Seed the AI finance database")
    parser.add_argument("--force", action="store_true", help="Clear all data and re-seed from scratch")
    args = parser.parse_args()
    asyncio.run(seed_all(force_reload=args.force))
