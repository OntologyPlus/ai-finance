from typing import List, Optional

from pydantic import BaseModel, Field


class RelationDefinition(BaseModel):
    relation_id: str
    name: str
    source_object: str
    target_object: str
    scene_condition: str = Field(description="该关系生效的场景条件")
    semantic_description: str
    cardinality: str = Field(default="N:1", description="基数约束(N:1/1:N/1:1/N:N)")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="关系置信度(1.0=确定,0.6-0.9=推断)")
    provenance: str = Field(default="人工录入", description="数据来源(人工录入/系统推断/外部导入)")
    is_bidirectional: bool = Field(default=False, description="是否双向关系")
    reverse_relation_id: Optional[str] = Field(default=None, description="反向关系ID")


_RELATIONS: dict[str, RelationDefinition] = {}

_SCENE_RELATION_MAP: dict[str, list[str]] = {
    "fin.budget_planning": ["驱动", "对标", "归属"],
    "fin.budget_grant": ["冻结", "释放", "B→A转换"],
    "fin.expense_reimbursement": ["挂载", "审批组织线", "审批法人线"],
    "fin.business_analysis": ["驱动", "对标"],
    "fin.alert_monitoring": ["触发"],
    "fin.alert_response": ["响应", "确认", "升级"],
    "fin.b_class_management": ["B→A转换", "冻结", "释放"],
    "fin.pdca_review": ["对标", "驱动"],
    "fin.report_issuance": [],
    "fin.next_cycle": ["驱动", "对标", "归属"],
    "fin.budget_adjustment": ["冻结", "释放", "裁决"],
    "fin.cash_flow_monitoring": ["对应", "归集", "驱动(收入)", "匹配"],
    "fin.scenario_planning": ["情景包含", "弹性驱动", "储备调拨"],
    "fin.impact_assessment": [],
    "fin.zero_based_budget": [],
    "fin.cost_center_accounting": ["分摊", "结算"],
    "fin.hcp_compliance": ["互动", "付款"],
    "fin.pipeline_management": ["管线推进"],
    "fin.business_review": [],
}


def _init_relations() -> None:
    global _RELATIONS
    if _RELATIONS:
        return

    definitions = [
        RelationDefinition(
            relation_id="rel_mount",
            name="挂载",
            source_object="obj_expense_report",
            target_object="obj_budget_item",
            scene_condition="报销单提交时必须选择一个有效的预算项目进行挂载",
            semantic_description="报销单挂载到预算项目，建立支出与预算的对应关系，确保每笔支出都有预算来源",
            cardinality="N:1",
            confidence=1.0,
            provenance="人工录入",
            is_bidirectional=False,
            reverse_relation_id=None,
        ),
        RelationDefinition(
            relation_id="rel_benchmark",
            name="对标",
            source_object="obj_budget_item",
            target_object="obj_strategic_initiative",
            scene_condition="预算编制阶段，每个预算项目须对标至少一个战略举措",
            semantic_description="预算项目与战略举措的对标关系，确保预算配置与战略方向一致，实现战略到预算的纵向贯通",
            cardinality="N:1",
            confidence=1.0,
            provenance="人工录入",
            is_bidirectional=False,
            reverse_relation_id="rel_drive",
        ),
        RelationDefinition(
            relation_id="rel_belong",
            name="归属",
            source_object="obj_budget_item",
            target_object="obj_budget_quadrant",
            scene_condition="预算编制阶段，每个预算项目须归属于一个象限",
            semantic_description="预算项目归属象限，象限决定管控力度和资源配置优先级，发展象限优先保障，收缩象限从严管控",
            cardinality="N:1",
            confidence=1.0,
            provenance="人工录入",
            is_bidirectional=False,
            reverse_relation_id=None,
        ),
        RelationDefinition(
            relation_id="rel_control",
            name="管控",
            source_object="obj_budget_subject_l3",
            target_object="obj_expense_report",
            scene_condition="报销单提交时，L3科目的管控级别决定审批流程和超预算处理方式",
            semantic_description="L3科目对报销单的管控关系，根据管控级别标签(强管控/中心弱管控/组合管控/不管控)决定审批路径和约束力度",
            cardinality="1:N",
            confidence=1.0,
            provenance="系统推断",
            is_bidirectional=False,
            reverse_relation_id=None,
        ),
        RelationDefinition(
            relation_id="rel_trigger",
            name="触发",
            source_object="obj_budget_item",
            target_object="obj_alert_record",
            scene_condition="预算执行率超过阈值或里程碑延期时自动触发预警",
            semantic_description="支出数据变更或执行偏差触发预警记录，建立从数据异常到预警生成的因果链",
            cardinality="1:N",
            confidence=0.9,
            provenance="系统推断",
            is_bidirectional=False,
            reverse_relation_id=None,
        ),
        RelationDefinition(
            relation_id="rel_respond",
            name="响应",
            source_object="obj_role_center_bp",
            target_object="obj_alert_record",
            scene_condition="预警记录生成后，对应角色的财经BP须在规定时限内响应",
            semantic_description="角色对预警的响应关系，明确每个预警类型的责任角色和响应时限，确保预警不被遗漏",
            cardinality="N:1",
            confidence=1.0,
            provenance="系统推断",
            is_bidirectional=False,
            reverse_relation_id=None,
        ),
        RelationDefinition(
            relation_id="rel_confirm",
            name="确认",
            source_object="obj_role_budget_dept",
            target_object="obj_alert_record",
            scene_condition="财经BP响应预警后，财经中心预算管理部须确认响应方案",
            semantic_description="财经中心预算管理部对预警响应的确认关系，实现双签闭环(业务+财经BP)，确保预警处理方案合理合规",
            cardinality="N:1",
            confidence=1.0,
            provenance="系统推断",
            is_bidirectional=False,
            reverse_relation_id=None,
        ),
        RelationDefinition(
            relation_id="rel_escalate",
            name="升级",
            source_object="obj_alert_record",
            target_object="obj_role_committee",
            scene_condition="红色预警或超时未响应的预警须升级至上级角色直至管委会",
            semantic_description="预警记录向更高层级角色的升级关系，确保严重偏差或未处理预警能够得到更高层级的关注和决策",
            cardinality="N:1",
            confidence=0.85,
            provenance="系统推断",
            is_bidirectional=False,
            reverse_relation_id=None,
        ),
        RelationDefinition(
            relation_id="rel_freeze",
            name="冻结",
            source_object="obj_budget_item",
            target_object="obj_budget_item",
            scene_condition="A类预算授予时冻结对应额度，或预警触发后冻结超额部分",
            semantic_description="预算项目对预算额度的冻结操作，冻结后额度不可使用，需释放或核销后方可恢复",
            cardinality="1:1",
            confidence=1.0,
            provenance="系统推断",
            is_bidirectional=False,
            reverse_relation_id="rel_release",
        ),
        RelationDefinition(
            relation_id="rel_release",
            name="释放",
            source_object="obj_budget_item",
            target_object="obj_budget_item",
            scene_condition="预算项目取消或B类预算未使用额度可释放回预算池",
            semantic_description="预算项目对预算额度的释放操作，释放后额度回归可用状态或回收到预算池供重新分配",
            cardinality="1:1",
            confidence=1.0,
            provenance="系统推断",
            is_bidirectional=False,
            reverse_relation_id="rel_freeze",
        ),
        RelationDefinition(
            relation_id="rel_b2a_convert",
            name="B→A转换",
            source_object="obj_budget_item",
            target_object="obj_budget_item",
            scene_condition="B类预算项目里程碑达标后，经审批可转换为A类预算",
            semantic_description="B类预算向A类预算的转换关系，转换后预算从弹性授予变为确定性冻结，需提供里程碑达标证据并经审批",
            cardinality="1:1",
            confidence=1.0,
            provenance="人工录入",
            is_bidirectional=False,
            reverse_relation_id=None,
        ),
        RelationDefinition(
            relation_id="rel_approval_org",
            name="审批组织线",
            source_object="obj_expense_report",
            target_object="obj_role_center_bp",
            scene_condition="报销单提交后须沿组织架构逐级审批",
            semantic_description="报销单沿组织架构的审批路径，从直属上级到部门负责人到中心总经理，根据金额和科目确定审批层级",
            cardinality="N:1",
            confidence=1.0,
            provenance="系统推断",
            is_bidirectional=False,
            reverse_relation_id=None,
        ),
        RelationDefinition(
            relation_id="rel_approval_legal",
            name="审批法人线",
            source_object="obj_expense_report",
            target_object="obj_role_budget_dept",
            scene_condition="报销单须同时经过财经中心预算管理部的法人线审批",
            semantic_description="报销单沿法人治理的审批路径，由财经中心预算管理部审核预算合规性和财务合规性，与组织线并行形成双线审批",
            cardinality="N:1",
            confidence=1.0,
            provenance="系统推断",
            is_bidirectional=False,
            reverse_relation_id=None,
        ),
        RelationDefinition(
            relation_id="rel_adjudicate",
            name="裁决",
            source_object="obj_role_committee",
            target_object="obj_budget_item",
            scene_condition="跨象限调拨、重大预算分歧等事项须由管委会裁决",
            semantic_description="管委会对分歧事项的裁决关系，管委会作为最高决策机构对预算编制和执行中的重大分歧进行最终裁决",
            cardinality="1:N",
            confidence=1.0,
            provenance="人工录入",
            is_bidirectional=False,
            reverse_relation_id=None,
        ),
        RelationDefinition(
            relation_id="rel_drive",
            name="驱动",
            source_object="obj_strategic_initiative",
            target_object="obj_budget_item",
            scene_condition="战略目标驱动预算编制，每个战略举措须有对应的预算项目支撑",
            semantic_description="战略目标对预算项目的驱动关系，确保预算配置服务于战略目标，实现从战略到资源的正向传导",
            cardinality="1:N",
            confidence=1.0,
            provenance="人工录入",
            is_bidirectional=False,
            reverse_relation_id="rel_benchmark",
        ),
        # === 现金流监控域 ===
        RelationDefinition(
            relation_id="rel_correspond",
            name="对应",
            source_object="obj_expense_report",
            target_object="obj_payment_schedule",
            scene_condition="报销单审批完成后生成付款排期",
            semantic_description="报销单对应付款排期，建立支出审批到实际付款的对应关系",
            cardinality="1:1",
            confidence=1.0,
            provenance="系统推断",
        ),
        RelationDefinition(
            relation_id="rel_aggregate",
            name="归集",
            source_object="obj_cash_pool",
            target_object="obj_cash_flow_plan",
            scene_condition="资金池归集各单位的现金流计划",
            semantic_description="资金池对各单位现金流的归集关系，实现集团资金的统一管理和调配",
            cardinality="1:N",
            confidence=1.0,
            provenance="系统推断",
        ),
        RelationDefinition(
            relation_id="rel_drive_revenue",
            name="驱动(收入)",
            source_object="obj_receipt_forecast",
            target_object="obj_cash_flow_plan",
            scene_condition="收入预算驱动收款预测，进而影响现金流计划",
            semantic_description="收入端对现金流的驱动关系，确保现金流预测包含收入端数据",
            cardinality="N:1",
            confidence=0.9,
            provenance="系统推断",
        ),
        RelationDefinition(
            relation_id="rel_match_receipt_payment",
            name="匹配",
            source_object="obj_payment_schedule",
            target_object="obj_receipt_forecast",
            scene_condition="收支匹配分析时建立付款与收款的对应关系",
            semantic_description="付款排期与收款预测的匹配关系，用于分析收支时间差和流动性风险",
            cardinality="N:N",
            confidence=0.8,
            provenance="系统推断",
        ),
        # === 情景规划域 ===
        RelationDefinition(
            relation_id="rel_scenario_contains",
            name="情景包含",
            source_object="obj_scenario",
            target_object="obj_scenario_assumption",
            scene_condition="情景由一组假设条件定义",
            semantic_description="情景对假设条件的包含关系，每个情景至少包含一个假设条件",
            cardinality="1:N",
            confidence=1.0,
            provenance="人工录入",
        ),
        RelationDefinition(
            relation_id="rel_elastic_drive",
            name="弹性驱动",
            source_object="obj_elastic_budget",
            target_object="obj_budget_item",
            scene_condition="弹性预算基于业务量变动调整预算项目额度",
            semantic_description="业务量指标对弹性预算的驱动关系，当业务量偏离基准时自动调整预算",
            cardinality="N:1",
            confidence=0.9,
            provenance="系统推断",
        ),
        RelationDefinition(
            relation_id="rel_reserve_allocate",
            name="储备调拨",
            source_object="obj_budget_reserve",
            target_object="obj_budget_item",
            scene_condition="紧急调拨时从预算储备金调拨到预算项目",
            semantic_description="预算储备对预算项目的调拨关系，紧急调拨须经管委会批准",
            cardinality="1:N",
            confidence=1.0,
            provenance="人工录入",
        ),
        # === 成本中心域 ===
        RelationDefinition(
            relation_id="rel_allocate",
            name="分摊",
            source_object="obj_cost_center",
            target_object="obj_cost_allocation",
            scene_condition="共享成本按规则分摊到各成本中心",
            semantic_description="成本中心间的分摊关系，按人数/面积/收入比例等基准分摊共享成本",
            cardinality="1:N",
            confidence=1.0,
            provenance="系统推断",
        ),
        RelationDefinition(
            relation_id="rel_settle",
            name="结算",
            source_object="obj_cost_center",
            target_object="obj_internal_settlement",
            scene_condition="成本中心间的内部交易结算",
            semantic_description="成本中心间的结算关系，按内部转移价格计算服务费用",
            cardinality="1:N",
            confidence=1.0,
            provenance="系统推断",
        ),
        # === HCP合规域 ===
        RelationDefinition(
            relation_id="rel_interact",
            name="互动",
            source_object="obj_hcp",
            target_object="obj_hcp_interaction",
            scene_condition="HCP与企业发生的每次互动",
            semantic_description="HCP与互动记录的关系，记录每次互动的详细信息和合规状态",
            cardinality="1:N",
            confidence=1.0,
            provenance="人工录入",
        ),
        RelationDefinition(
            relation_id="rel_pay",
            name="付款",
            source_object="obj_hcp",
            target_object="obj_hcp_payment",
            scene_condition="向HCP支付讲课费/咨询费/差旅费",
            semantic_description="HCP与付款记录的关系，跟踪每个HCP的付款历史和年度总额",
            cardinality="1:N",
            confidence=1.0,
            provenance="人工录入",
        ),
        # === 研发管线域 ===
        RelationDefinition(
            relation_id="rel_pipeline_advance",
            name="管线推进",
            source_object="obj_pipeline",
            target_object="obj_rnd_project",
            scene_condition="管线阶段推进时建立管线与研发项目的关联",
            semantic_description="研发管线与研发项目的推进关系，记录阶段转换和Go/No-Go决策",
            cardinality="1:N",
            confidence=0.9,
            provenance="系统推断",
        ),
    ]

    _RELATIONS = {rel.relation_id: rel for rel in definitions}


def get_all_relations() -> dict[str, RelationDefinition]:
    _init_relations()
    return _RELATIONS.copy()


def get_relations_for_scene(scene_id: str) -> list[RelationDefinition]:
    _init_relations()
    relation_names = _SCENE_RELATION_MAP.get(scene_id, [])
    return [rel for rel in _RELATIONS.values() if rel.name in relation_names]


def get_relation(relation_id: str) -> Optional[RelationDefinition]:
    _init_relations()
    return _RELATIONS.get(relation_id)
