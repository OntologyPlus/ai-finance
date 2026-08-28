import json
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from models.ontology import OntologyObjectInstance, OntologyRelationInstance
from models.budget import BudgetItem, BudgetSubjectL1
from models.expense import ExpenseReport
from models.alert import AlertRecord


async def seed_ontology_instances(db: AsyncSession) -> None:
    """从业务数据（预算项目、报销单、预警记录）生成本体实例的种子数据，使用 upsert 模式。"""

    # ── a) 从预算项目创建对象实例 ──────────────────────────────────
    result = await db.execute(select(BudgetItem))
    budget_items = result.scalars().all()

    budget_obj_count = 0
    for item in budget_items:
        instance_id = f"OI-{item.budget_id}"
        existing = await db.get(OntologyObjectInstance, instance_id)
        if existing:
            continue

        attributes = {
            "budget_id": item.budget_id,
            "budget_name": item.budget_name,
            "budget_category": item.budget_category,
            "annual_amount": float(item.annual_amount) if item.annual_amount else 0,
            "strategic_intent_l1": item.strategic_intent_l1 if hasattr(item, "strategic_intent_l1") else None,
            "strategic_intent_l2": item.strategic_intent_l2 if hasattr(item, "strategic_intent_l2") else None,
            "center": item.center_id if hasattr(item, "center_id") else None,
            "product_variety": item.product_variety if hasattr(item, "product_variety") else None,
            "channel": item.channel if hasattr(item, "channel") else None,
        }

        db.add(OntologyObjectInstance(
            instance_id=instance_id,
            type_id="obj_budget_item",
            attributes=attributes,
            status=item.status or "active",
        ))
        budget_obj_count += 1

    logger.info(f"ontology_object_instance (budget_item): seeded {budget_obj_count} new records (total budget items: {len(budget_items)})")

    # ── b) 从报销单创建对象实例 ──────────────────────────────────
    result = await db.execute(select(ExpenseReport))
    expense_reports = result.scalars().all()

    expense_obj_count = 0
    for exp in expense_reports:
        instance_id = f"OI-{exp.expense_id}"
        existing = await db.get(OntologyObjectInstance, instance_id)
        if existing:
            continue

        attributes = {
            "expense_id": exp.expense_id,
            "budget_id": exp.budget_id,
            "amount": float(exp.amount) if exp.amount else 0,
            "expense_type": exp.control_tag if hasattr(exp, "control_tag") else None,
            "status": exp.status,
        }

        db.add(OntologyObjectInstance(
            instance_id=instance_id,
            type_id="obj_expense_report",
            attributes=attributes,
            status=exp.status or "active",
        ))
        expense_obj_count += 1

    logger.info(f"ontology_object_instance (expense_report): seeded {expense_obj_count} new records (total expense reports: {len(expense_reports)})")

    # ── c) 从预警记录创建对象实例 ──────────────────────────────────
    result = await db.execute(select(AlertRecord))
    alert_records = result.scalars().all()

    alert_obj_count = 0
    for alert in alert_records:
        instance_id = f"OI-{alert.alert_id}"
        existing = await db.get(OntologyObjectInstance, instance_id)
        if existing:
            continue

        attributes = {
            "alert_id": alert.alert_id,
            "alert_type": alert.alert_type if hasattr(alert, "alert_type") else None,
            "alert_level": alert.alert_level if hasattr(alert, "alert_level") else None,
            "budget_id": alert.budget_id if hasattr(alert, "budget_id") else None,
            "status": alert.alert_status if hasattr(alert, "alert_status") else None,
        }

        db.add(OntologyObjectInstance(
            instance_id=instance_id,
            type_id="obj_alert_record",
            attributes=attributes,
            status=alert.alert_status if hasattr(alert, "alert_status") else "active",
        ))
        alert_obj_count += 1

    logger.info(f"ontology_object_instance (alert_record): seeded {alert_obj_count} new records (total alert records: {len(alert_records)})")

    # ── d) 创建 mount 关系实例（报销单→预算项目） ──────────────────
    mount_rel_count = 0
    for exp in expense_reports:
        if not exp.budget_id:
            continue

        instance_id = f"RI-mount-{exp.expense_id}"
        existing = await db.get(OntologyRelationInstance, instance_id)
        if existing:
            continue

        db.add(OntologyRelationInstance(
            instance_id=instance_id,
            type_id="rel_mount",
            source_instance_id=f"OI-{exp.expense_id}",
            target_instance_id=f"OI-{exp.budget_id}",
            attributes={"mount_type": "核销挂载"},
        ))
        mount_rel_count += 1

    logger.info(f"ontology_relation_instance (mount): seeded {mount_rel_count} new records")

    # ── e) 创建象限对象实例（如果不存在） ──────────────────────────
    quadrants = ["发展", "收缩", "稳定", "探索"]
    for q in quadrants:
        instance_id = f"OI-Q-{q}"
        existing = await db.get(OntologyObjectInstance, instance_id)
        if not existing:
            db.add(OntologyObjectInstance(
                instance_id=instance_id,
                type_id="obj_budget_item",
                attributes={"name": f"{q}象限", "quadrant": q},
                status="active",
            ))

    # ── f) 创建 belong 关系实例（预算项目→象限） ──────────────────
    belong_rel_count = 0
    for item in budget_items:
        if not hasattr(item, "quadrant") or not item.quadrant:
            continue

        target_instance_id = f"OI-Q-{item.quadrant}"
        instance_id = f"RI-belong-{item.budget_id}"

        existing = await db.get(OntologyRelationInstance, instance_id)
        if existing:
            continue

        db.add(OntologyRelationInstance(
            instance_id=instance_id,
            type_id="rel_belong",
            source_instance_id=f"OI-{item.budget_id}",
            target_instance_id=target_instance_id,
        ))
        belong_rel_count += 1

    logger.info(f"ontology_relation_instance (belong): seeded {belong_rel_count} new records")
