from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from models.ontology import OntologyRule


SOFT_RULE_PARAMS = [
    {"rule_id": "SR-001", "rule_name": "月度执行进度蓝色阈值", "rule_type": "软规则", "condition": "月度执行进度 > 105%", "result": "触发蓝色预警", "scene_tags": '["fin.alert_monitoring"]', "referenced_objects": '["obj_alert_record","obj_budget_item"]', "example": "月度执行进度106%时触发蓝色预警"},
    {"rule_id": "SR-002", "rule_name": "月度执行进度黄色阈值", "rule_type": "软规则", "condition": "月度执行进度 > 110%", "result": "触发黄色预警", "scene_tags": '["fin.alert_monitoring"]', "referenced_objects": '["obj_alert_record","obj_budget_item"]', "example": "月度执行进度112%时触发黄色预警"},
    {"rule_id": "SR-003", "rule_name": "月度执行进度红色阈值", "rule_type": "软规则", "condition": "月度执行进度超过年度预算", "result": "触发红色预警", "scene_tags": '["fin.alert_monitoring"]', "referenced_objects": '["obj_alert_record","obj_budget_item"]', "example": "累计支出超过年度预算时触发红色预警"},
    {"rule_id": "SR-004", "rule_name": "季度滚动预测蓝色阈值", "rule_type": "软规则", "condition": "季度滚动预测 > 105%", "result": "触发蓝色预警", "scene_tags": '["fin.alert_monitoring"]', "referenced_objects": '["obj_alert_record","obj_budget_item"]', "example": "季度滚动预测106%时触发蓝色预警"},
    {"rule_id": "SR-005", "rule_name": "季度滚动预测黄色阈值", "rule_type": "软规则", "condition": "季度滚动预测 > 110%", "result": "触发黄色预警", "scene_tags": '["fin.alert_monitoring"]', "referenced_objects": '["obj_alert_record","obj_budget_item"]', "example": "季度滚动预测112%时触发黄色预警"},
    {"rule_id": "SR-006", "rule_name": "季度滚动预测红色阈值", "rule_type": "软规则", "condition": "季度滚动预测 > 115%", "result": "触发红色预警", "scene_tags": '["fin.alert_monitoring"]', "referenced_objects": '["obj_alert_record","obj_budget_item"]', "example": "季度滚动预测116%时触发红色预警"},
    {"rule_id": "SR-007", "rule_name": "B类膨胀比例上限", "rule_type": "软规则", "condition": "B类授予总额/年度总额 > 30%", "result": "触发膨胀预警", "scene_tags": '["fin.b_class_management","fin.budget_planning"]', "referenced_objects": '["obj_budget_item"]', "example": "B类预算膨胀比例35%时触发预警"},
    {"rule_id": "SR-008", "rule_name": "单项目/单供应商偏差红色阈值", "rule_type": "软规则", "condition": "偏差金额 > 50万", "result": "触发红色预警", "scene_tags": '["fin.alert_monitoring"]', "referenced_objects": '["obj_alert_record","obj_budget_item"]', "example": "单项目偏差60万时触发红色预警"},
    {"rule_id": "SR-009", "rule_name": "部门负责人审批金额门槛", "rule_type": "软规则", "condition": "报销金额 > 5万", "result": "须部门负责人审批", "scene_tags": '["fin.expense_reimbursement"]', "referenced_objects": '["obj_expense_report","obj_role_budget_dept"]', "example": "报销6万元须部门负责人审批"},
    {"rule_id": "SR-010", "rule_name": "中心总经理审批金额门槛", "rule_type": "软规则", "condition": "报销金额 > 20万", "result": "须中心总经理审批", "scene_tags": '["fin.expense_reimbursement"]', "referenced_objects": '["obj_expense_report","obj_role_center_bp"]', "example": "报销25万元须中心总经理审批"},
    {"rule_id": "SR-011", "rule_name": "项目化管理门槛", "rule_type": "软规则", "condition": "年度预算>50万 或 新增项目单笔>20万", "result": "纳入项目化管理", "scene_tags": '["fin.budget_planning","fin.b_class_management"]', "referenced_objects": '["obj_budget_item"]', "example": "年度预算60万的项目须纳入项目化管理"},
]

HARD_RULE_DEFS = [
    {"rule_id": "HR-001", "rule_name": "支出必须有对应预算", "rule_type": "硬规则", "condition": "报销单未挂载到任何预算项目", "result": "硬性拦截(BLOCK)", "scene_tags": '["fin.expense_reimbursement","fin.budget_planning"]', "referenced_objects": '["obj_expense_report","obj_budget_item"]', "example": "无预算的报销单被系统自动拦截"},
    {"rule_id": "HR-002", "rule_name": "预算核销不可超额", "rule_type": "硬规则", "condition": "核销金额 > 可用额度", "result": "硬性拦截(BLOCK)", "scene_tags": '["fin.expense_reimbursement"]', "referenced_objects": '["obj_budget_item"]', "example": "核销金额超过可用额度时被拦截"},
    {"rule_id": "HR-003", "rule_name": "预警触发≠超支许可", "rule_type": "硬规则", "condition": "预警触发后支出仍被批准", "result": "硬性拦截(BLOCK)", "scene_tags": '["fin.alert_response"]', "referenced_objects": '["obj_alert_record","obj_expense_report"]', "example": "预警触发后放行支出被系统拦截"},
    {"rule_id": "HR-004", "rule_name": "先批后用(A类预算)", "rule_type": "硬规则", "condition": "A类预算未审批即执行支出", "result": "硬性拦截(BLOCK)", "scene_tags": '["fin.budget_grant","fin.expense_reimbursement"]', "referenced_objects": '["obj_budget_item"]', "example": "A类预算未审批即支出被拦截"},
    {"rule_id": "HR-005", "rule_name": "双签闭环(业务+财经BP)", "rule_type": "硬规则", "condition": "闭环缺少业务BP或财经BP签认", "result": "硬性拦截(BLOCK)", "scene_tags": '["fin.alert_response"]', "referenced_objects": '["obj_alert_record","obj_role_center_bp","obj_role_budget_dept"]', "example": "仅业务BP签认无财经BP确认时闭环被拦截"},
    {"rule_id": "HR-006", "rule_name": "税务申报数据必须完整准确", "rule_type": "硬规则", "condition": "税务申报数据不完整或不准确", "result": "硬性拦截(BLOCK)", "scene_tags": '["fin.report_issuance"]', "referenced_objects": '["obj_report_monthly"]', "example": "税务申报数据遗漏时被拦截"},
    {"rule_id": "HR-007", "rule_name": "战略预算组合比例由管委会决定", "rule_type": "硬规则", "condition": "战略预算组合比例未经管委会决定", "result": "硬性拦截(BLOCK)", "scene_tags": '["fin.budget_planning","fin.next_cycle"]', "referenced_objects": '["obj_role_committee","obj_budget_item"]', "example": "非管委会角色调整战略预算比例被拦截"},
    {"rule_id": "HR-008", "rule_name": "跨象限调拨须管委会批准", "rule_type": "硬规则", "condition": "跨象限调拨未经管委会批准", "result": "硬性拦截(BLOCK)", "scene_tags": '["fin.budget_adjustment"]', "referenced_objects": '["obj_budget_item","obj_budget_quadrant","obj_role_committee"]', "example": "从发展象限调拨到收缩象限未经管委会批准被拦截"},
    {"rule_id": "HR-009", "rule_name": "里程碑延期未完成报备不得自行推进下一里程碑", "rule_type": "硬规则", "condition": "里程碑延期未报备即推进下一里程碑", "result": "硬性拦截(BLOCK)", "scene_tags": '["fin.b_class_management"]', "referenced_objects": '["obj_budget_item"]', "example": "里程碑延期未报备即推进被拦截"},
    {"rule_id": "HR-010", "rule_name": "实际支出不得超出里程碑计划金额", "rule_type": "硬规则", "condition": "实际支出 > 里程碑计划金额", "result": "硬性拦截(BLOCK)", "scene_tags": '["fin.b_class_management"]', "referenced_objects": '["obj_budget_item"]', "example": "实际支出超出里程碑计划金额被拦截"},
    {"rule_id": "HR-011", "rule_name": "里程碑预警触发后新增支出须经对应级别审批", "rule_type": "硬规则", "condition": "预警触发后新增支出未经审批", "result": "硬性拦截(BLOCK)", "scene_tags": '["fin.alert_response","fin.b_class_management"]', "referenced_objects": '["obj_alert_record","obj_expense_report"]', "example": "预警触发后新增支出未经审批被拦截"},
    {"rule_id": "HR-012", "rule_name": "未闭环预警须在经营分析会中专项汇报", "rule_type": "硬规则", "condition": "存在未闭环预警但未在经营分析会汇报", "result": "硬性拦截(BLOCK)", "scene_tags": '["fin.business_analysis","fin.pdca_review"]', "referenced_objects": '["obj_alert_record","obj_role_ops_dept"]', "example": "经营分析会中未汇报未闭环预警被标记"},
]

REASONING_RULE_DEFS = [
    {"rule_id": "RR-001", "rule_name": "差旅费与项目数量正相关", "rule_type": "推理规则", "condition": "差旅费与项目数量偏差超过30%", "result": "建议关注差旅费合理性", "scene_tags": '["fin.alert_monitoring"]', "referenced_objects": '["obj_budget_item"]', "example": "项目数减少但差旅费增加时触发关注"},
    {"rule_id": "RR-002", "rule_name": "招待费与渠道拓展阶段关联", "rule_type": "推理规则", "condition": "招待费占比超过渠道拓展阶段阈值", "result": "建议关注招待费合理性", "scene_tags": '["fin.alert_monitoring"]', "referenced_objects": '["obj_budget_item"]', "example": "成熟期招待费占比超过6%时触发关注"},
    {"rule_id": "RR-003", "rule_name": "培训费季节性波动模式", "rule_type": "推理规则", "condition": "培训费偏差超出季节模式50%", "result": "建议关注培训费合理性", "scene_tags": '["fin.alert_monitoring"]', "referenced_objects": '["obj_budget_item"]', "example": "Q2培训费异常偏高时触发关注"},
    {"rule_id": "RR-004", "rule_name": "预算执行率与剩余时间非线性关系", "rule_type": "推理规则", "condition": "前期执行过快或后期突击花钱", "result": "预警执行节奏异常", "scene_tags": '["fin.business_analysis"]', "referenced_objects": '["obj_budget_item"]', "example": "时间进度30%时执行率70%触发关注"},
    {"rule_id": "RR-005", "rule_name": "研发里程碑延期对后续节点传导效应", "rule_type": "推理规则", "condition": "里程碑延期产生传导放大效应", "result": "建议调整后续里程碑计划", "scene_tags": '["fin.b_class_management"]', "referenced_objects": '["obj_budget_item"]', "example": "当前延期10天，后续3个里程碑预计累计延期65天"},
]


async def seed_alert_rules(db: AsyncSession) -> None:
    logger.info("Seeding soft rule parameters...")
    for data in SOFT_RULE_PARAMS:
        existing = await db.get(OntologyRule, data["rule_id"])
        if existing is None:
            db.add(OntologyRule(**data))
    await db.flush()

    logger.info("Seeding hard rule definitions...")
    for data in HARD_RULE_DEFS:
        existing = await db.get(OntologyRule, data["rule_id"])
        if existing is None:
            db.add(OntologyRule(**data))
    await db.flush()

    logger.info("Seeding reasoning rule definitions...")
    for data in REASONING_RULE_DEFS:
        existing = await db.get(OntologyRule, data["rule_id"])
        if existing is None:
            db.add(OntologyRule(**data))
    await db.flush()

    logger.info("Alert rules seed completed.")
