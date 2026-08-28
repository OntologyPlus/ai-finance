from typing import List, Optional

from pydantic import BaseModel, Field


class LifecycleTransition(BaseModel):
    from_state: str
    to_state: str
    trigger: str = ""  # what triggers this transition
    guard_condition: str = ""  # condition that must be true


class LifecycleDef(BaseModel):
    states: List[str]
    initial_state: str
    transitions: List[LifecycleTransition] = Field(default_factory=list)


class ObjectDefinition(BaseModel):
    object_id: str
    name: str
    category: str = Field(description="strategic/budget/expense/alert/role/report/tool")
    natural_language_definition: str
    key_attributes: List[str] = Field(default_factory=list)
    participating_relations: List[str] = Field(default_factory=list)
    parent_type: Optional[str] = Field(default=None, description="父类型ID，支持类型继承")
    sub_types: List[str] = Field(default_factory=list, description="子类型ID列表")
    lifecycle: Optional[LifecycleDef] = Field(default=None, description="生命周期状态机定义")


_OBJECTS: dict[str, ObjectDefinition] = {}


def _init_objects() -> None:
    global _OBJECTS
    if _OBJECTS:
        return

    definitions = [
        ObjectDefinition(
            object_id="obj_strategic_sp",
            name="SP战略规划",
            category="strategic",
            natural_language_definition="集团3-5年战略规划，定义长期发展方向、核心战略目标和资源配置原则，是所有预算编制的顶层依据",
            key_attributes=["规划周期", "战略目标列表", "资源配置原则", "审批状态"],
            participating_relations=["驱动"],
        ),
        ObjectDefinition(
            object_id="obj_strategic_bp",
            name="BP年度业务计划",
            category="strategic",
            natural_language_definition="基于SP制定的年度业务计划，将战略目标分解为年度可执行的业务目标和关键举措，直接指导年度预算编制",
            key_attributes=["年度", "业务目标", "关键举措", "SP关联编号"],
            participating_relations=["驱动"],
        ),
        ObjectDefinition(
            object_id="obj_strategic_initiative",
            name="战略举措",
            category="strategic",
            natural_language_definition="SP/BP中定义的具体战略行动项，每个战略举措可对标一个或多个预算项目，确保预算与战略对齐",
            key_attributes=["举措编号", "举措名称", "所属SP/BP", "对标预算项目列表", "完成状态"],
            participating_relations=["对标", "驱动"],
        ),
        ObjectDefinition(
            object_id="obj_budget_item",
            name="预算项目",
            category="budget",
            natural_language_definition="年度预算编制的基本单元，包含A类(确定性支出)和B类(弹性支出)两种类别，归属于特定象限和预算科目，必须标注战略意图维度",
            key_attributes=["预算ID", "项目名称", "A/B类别", "年度金额", "已授予额度", "已冻结额度", "已使用额度", "状态", "战略意图L1", "战略意图L2", "产品线", "区域"],
            participating_relations=["挂载", "对标", "归属", "冻结", "释放", "B→A转换", "驱动", "管控"],
            lifecycle=LifecycleDef(
                states=["未审批", "审批中", "已审批", "执行中", "已核销", "已驳回"],
                initial_state="未审批",
                transitions=[
                    LifecycleTransition(from_state="未审批", to_state="审批中", trigger="提交审批"),
                    LifecycleTransition(from_state="审批中", to_state="已审批", trigger="审批通过"),
                    LifecycleTransition(from_state="审批中", to_state="已驳回", trigger="审批驳回"),
                    LifecycleTransition(from_state="已审批", to_state="执行中", trigger="首次核销"),
                    LifecycleTransition(from_state="执行中", to_state="已核销", trigger="核销完成"),
                ],
            ),
        ),
        ObjectDefinition(
            object_id="obj_budget_quadrant",
            name="象限",
            category="budget",
            natural_language_definition="基于战略定位划分的预算象限(发展/收缩/稳定/探索)，决定预算项目的管控力度和资源配置优先级",
            key_attributes=["象限名称", "战略定位", "管控力度", "资源配置优先级"],
            participating_relations=["归属"],
        ),
        ObjectDefinition(
            object_id="obj_budget_subject_l1",
            name="预算科目L1",
            category="budget",
            natural_language_definition="预算科目体系的第一层级，定义费用大类(如人力成本、运营费用、资本性支出等)，确定管控模式和预警规则类型",
            key_attributes=["L1编码", "L1名称", "管控模式", "预警规则类型", "是否含L2子类"],
            participating_relations=["管控"],
            sub_types=["obj_budget_subject_l2"],
        ),
        ObjectDefinition(
            object_id="obj_budget_subject_l2",
            name="预算科目L2",
            category="budget",
            natural_language_definition="预算科目体系的第二层级，在L1基础上进一步细分费用类别，可包含特殊规则和ROI预警阈值",
            key_attributes=["L2编码", "L2名称", "归属L1编码", "特殊规则", "ROI预警阈值"],
            participating_relations=["管控"],
            parent_type="obj_budget_subject_l1",
            sub_types=["obj_budget_subject_l3"],
        ),
        ObjectDefinition(
            object_id="obj_budget_subject_l3",
            name="预算科目L3",
            category="budget",
            natural_language_definition="预算科目体系的最细粒度层级，定义具体费用项目并标注管控级别(强管控/中心弱管控/组合管控/不管控)，直接关联报销单管控",
            key_attributes=["L3编码", "L3名称", "归属L2编码", "归属L1编码", "管控级别标签", "品种组编码", "是否项目化管理"],
            participating_relations=["管控"],
            parent_type="obj_budget_subject_l2",
        ),
        ObjectDefinition(
            object_id="obj_expense_report",
            name="报销单",
            category="expense",
            natural_language_definition="员工提交的费用报销申请，必须挂载到对应预算项目并经过审批流程(组织线+法人线)后方可执行",
            key_attributes=["报销单号", "申请人", "报销金额", "挂载预算项目ID", "审批状态", "提交日期"],
            participating_relations=["挂载", "审批组织线", "审批法人线"],
            lifecycle=LifecycleDef(
                states=["草稿", "审批中", "已审批", "已支付", "已作废"],
                initial_state="草稿",
                transitions=[
                    LifecycleTransition(from_state="草稿", to_state="审批中", trigger="提交报销"),
                    LifecycleTransition(from_state="审批中", to_state="已审批", trigger="双线审批通过"),
                    LifecycleTransition(from_state="审批中", to_state="草稿", trigger="审批退回"),
                    LifecycleTransition(from_state="已审批", to_state="已支付", trigger="支付完成"),
                    LifecycleTransition(from_state="草稿", to_state="已作废", trigger="作废"),
                ],
            ),
        ),
        ObjectDefinition(
            object_id="obj_budget_usage_request",
            name="预算使用申请",
            category="expense",
            natural_language_definition="A类预算使用前的申请单据，需经审批后方可执行支出，体现'先批后用'原则",
            key_attributes=["申请编号", "申请金额", "关联预算项目ID", "申请人", "审批状态"],
            participating_relations=["挂载", "审批组织线"],
        ),
        ObjectDefinition(
            object_id="obj_alert_record",
            name="预警记录",
            category="alert",
            natural_language_definition="系统自动或人工触发的预警信息，记录预算执行偏差、里程碑延期等异常情况，须有对应的响应和闭环处理",
            key_attributes=["预警编号", "预警类型", "预警级别(蓝/黄/橙/红)", "触发条件", "关联预算项目", "响应状态", "闭环状态"],
            participating_relations=["触发", "响应", "确认", "升级"],
            lifecycle=LifecycleDef(
                states=["待响应", "响应中", "已闭环", "已升级", "超时未闭环"],
                initial_state="待响应",
                transitions=[
                    LifecycleTransition(from_state="待响应", to_state="响应中", trigger="开始响应"),
                    LifecycleTransition(from_state="响应中", to_state="已闭环", trigger="双签闭环"),
                    LifecycleTransition(from_state="响应中", to_state="已升级", trigger="升级处理"),
                    LifecycleTransition(from_state="待响应", to_state="超时未闭环", trigger="响应超时"),
                    LifecycleTransition(from_state="超时未闭环", to_state="已升级", trigger="自动升级"),
                ],
            ),
        ),
        ObjectDefinition(
            object_id="obj_role_committee",
            name="管委会",
            category="role",
            natural_language_definition="集团最高决策机构，负责战略预算组合比例决定、跨象限调拨批准、分歧事项裁决等关键决策",
            key_attributes=["委员名单", "决策权限范围", "例会周期"],
            participating_relations=["裁决", "审批组织线"],
        ),
        ObjectDefinition(
            object_id="obj_role_budget_dept",
            name="财经中心预算管理部",
            category="role",
            natural_language_definition="预算管理的归口部门，负责预算编制组织、预算授予执行、预警监控和预算调整审核",
            key_attributes=["部门编码", "职责范围", "审批权限"],
            participating_relations=["响应", "确认", "审批法人线"],
        ),
        ObjectDefinition(
            object_id="obj_role_center_bp",
            name="各中心财经BP",
            category="role",
            natural_language_definition="各业务中心的财经业务伙伴，负责本中心预算执行监控、预警响应确认和双签闭环中的财经BP签认",
            key_attributes=["所属中心", "BP姓名", "签认权限"],
            participating_relations=["响应", "确认", "审批组织线", "审批法人线"],
        ),
        ObjectDefinition(
            object_id="obj_role_ops_dept",
            name="运营中心经营管理部",
            category="role",
            natural_language_definition="负责经营分析会组织、3GAP+3List分析工具执行和PDCA复盘推进的运营管理部门",
            key_attributes=["部门编码", "职责范围"],
            participating_relations=["响应"],
        ),
        ObjectDefinition(
            object_id="obj_role_hr_center",
            name="人力中心",
            category="role",
            natural_language_definition="负责人力成本相关预算的编制审核和执行监控，参与人力成本预警的响应处理",
            key_attributes=["中心编码", "职责范围"],
            participating_relations=["响应", "确认"],
        ),
        ObjectDefinition(
            object_id="obj_report_monthly",
            name="月度快报",
            category="report",
            natural_language_definition="每月出具的预算执行情况快报，包含执行率、偏差分析和预警汇总，服务于经营分析会",
            key_attributes=["报告期", "执行率", "偏差分析", "预警汇总"],
            participating_relations=[],
        ),
        ObjectDefinition(
            object_id="obj_report_quarterly",
            name="季度汇报PPT",
            category="report",
            natural_language_definition="季度经营分析汇报材料，包含3GAP+3List分析结果、滚动预测和战略执行评估",
            key_attributes=["季度", "3GAP分析", "3List分析", "滚动预测", "战略执行评估"],
            participating_relations=[],
        ),
        ObjectDefinition(
            object_id="obj_report_yearly",
            name="年度复盘报告",
            category="report",
            natural_language_definition="年度PDCA复盘报告，总结全年预算执行情况、战略目标达成度和下年度改进计划",
            key_attributes=["年度", "执行总结", "战略达成度", "改进计划"],
            participating_relations=[],
        ),
        ObjectDefinition(
            object_id="obj_tool_3gap_3list",
            name="3GAP+3List",
            category="tool",
            natural_language_definition="经营分析核心工具：3GAP(目标差距、执行差距、能力差距)定位问题根因，3List(必赢清单、改善清单、资源清单)制定行动方案",
            key_attributes=["分析周期", "3GAP结果", "3List结果", "关联预警"],
            participating_relations=[],
        ),
        # === 现金流监控域 (模块1) ===
        ObjectDefinition(
            object_id="obj_cash_flow_plan",
            name="现金流计划",
            category="cash_flow",
            natural_language_definition="按月度/季度的资金收支计划，区分经营/投资/筹资三类活动，实现利润线+现金流线双轮驱动监控",
            key_attributes=["计划期", "活动类型(经营/投资/筹资)", "流入金额", "流出金额", "净额", "实际流入", "实际流出", "状态"],
            participating_relations=["对应", "归集", "匹配"],
            lifecycle=LifecycleDef(
                states=["草稿", "已审批", "执行中", "已结算"],
                initial_state="草稿",
                transitions=[
                    LifecycleTransition(from_state="草稿", to_state="已审批", trigger="审批通过"),
                    LifecycleTransition(from_state="已审批", to_state="执行中", trigger="开始执行"),
                    LifecycleTransition(from_state="执行中", to_state="已结算", trigger="结算完成"),
                ],
            ),
        ),
        ObjectDefinition(
            object_id="obj_cash_pool",
            name="资金池",
            category="cash_flow",
            natural_language_definition="集团资金池，统一管理各下属单位的资金归集和下拨，确保集团整体流动性安全",
            key_attributes=["资金池名称", "总余额", "最低余额", "预警阈值", "归集规则"],
            participating_relations=["归集"],
        ),
        ObjectDefinition(
            object_id="obj_payment_schedule",
            name="付款排期",
            category="cash_flow",
            natural_language_definition="应付账款的付款时间安排，关联报销单和合同，确保付款不早于审批完成日、不晚于合同约定日",
            key_attributes=["排期ID", "关联报销单", "关联合同", "计划付款日", "计划金额", "实际付款日", "实际金额", "状态"],
            participating_relations=["对应"],
            lifecycle=LifecycleDef(
                states=["待付款", "已付款", "已逾期", "已取消"],
                initial_state="待付款",
                transitions=[
                    LifecycleTransition(from_state="待付款", to_state="已付款", trigger="付款完成"),
                    LifecycleTransition(from_state="待付款", to_state="已逾期", trigger="超过计划付款日"),
                    LifecycleTransition(from_state="待付款", to_state="已取消", trigger="取消付款"),
                ],
            ),
        ),
        ObjectDefinition(
            object_id="obj_receipt_forecast",
            name="收款预测",
            category="cash_flow",
            natural_language_definition="应收账款的收款时间预测，关联收入预算，为现金流预测提供收入端数据支撑",
            key_attributes=["预测ID", "关联收入预算", "预测收款日", "预测金额", "实际收款日", "实际金额", "置信度"],
            participating_relations=["驱动(收入)", "匹配"],
        ),
        # === 情景规划域 (模块2) ===
        ObjectDefinition(
            object_id="obj_scenario",
            name="情景",
            category="scenario",
            natural_language_definition="预算情景(乐观/基准/悲观/压力测试)，每个情景包含一组假设条件，用于多情景预算编制和对比分析",
            key_attributes=["情景名称", "情景类型", "假设条件", "状态"],
            participating_relations=["情景包含"],
            lifecycle=LifecycleDef(
                states=["草稿", "已审批", "已执行", "已归档"],
                initial_state="草稿",
                transitions=[
                    LifecycleTransition(from_state="草稿", to_state="已审批", trigger="审批通过"),
                    LifecycleTransition(from_state="已审批", to_state="已执行", trigger="开始执行"),
                    LifecycleTransition(from_state="已执行", to_state="已归档", trigger="归档"),
                ],
            ),
        ),
        ObjectDefinition(
            object_id="obj_scenario_assumption",
            name="情景假设",
            category="scenario",
            natural_language_definition="情景的关键假设条件（增长率/汇率/政策变动/市场变化等），是情景差异的核心驱动因素",
            key_attributes=["假设名称", "假设类型", "基准值", "乐观值", "悲观值", "影响权重"],
            participating_relations=["情景包含"],
        ),
        ObjectDefinition(
            object_id="obj_elastic_budget",
            name="弹性预算",
            category="scenario",
            natural_language_definition="基于业务量变动的预算调整规则，当实际业务量偏离基准时自动调整预算额度，调整幅度不超过基准±30%",
            key_attributes=["预算项目ID", "驱动指标", "基准业务量", "基准金额", "弹性系数", "当前业务量", "调整后金额"],
            participating_relations=["弹性驱动"],
        ),
        ObjectDefinition(
            object_id="obj_budget_reserve",
            name="预算储备",
            category="scenario",
            natural_language_definition="集团级预算储备金，用于紧急调拨和不可预见支出，紧急调拨须经管委会批准",
            key_attributes=["储备名称", "总额", "已用金额", "可用金额", "是否需审批"],
            participating_relations=["储备调拨"],
        ),
        # === 影响评估域 (模块3) ===
        ObjectDefinition(
            object_id="obj_impact_chain",
            name="影响链",
            category="impact",
            natural_language_definition="一个操作触发的跨域影响路径，记录从源头操作到各域影响的完整传导链路",
            key_attributes=["影响链ID", "源头操作", "操作类型", "影响域列表", "总体风险等级"],
            participating_relations=[],
        ),
        ObjectDefinition(
            object_id="obj_impact_node",
            name="影响节点",
            category="impact",
            natural_language_definition="影响链中的单个影响点，记录对特定域(预算/费用/预警/现金流/战略)的具体影响",
            key_attributes=["节点ID", "所属影响链", "影响域", "影响描述", "影响程度(低/中/高)", "缓解方案"],
            participating_relations=[],
        ),
        # === 零基预算域 (模块4) ===
        ObjectDefinition(
            object_id="obj_zbb_review",
            name="零基审视",
            category="budget",
            natural_language_definition="对预算项目从零开始的必要性审视，年度预算编制前强制进行，打破历史惯性",
            key_attributes=["审视期", "审视状态", "决策单元数量", "总预算约束"],
            participating_relations=[],
            lifecycle=LifecycleDef(
                states=["启动", "编制中", "排序中", "已审批", "已执行"],
                initial_state="启动",
                transitions=[
                    LifecycleTransition(from_state="启动", to_state="编制中", trigger="开始编制决策包"),
                    LifecycleTransition(from_state="编制中", to_state="排序中", trigger="提交排序"),
                    LifecycleTransition(from_state="排序中", to_state="已审批", trigger="管委会审批"),
                    LifecycleTransition(from_state="已审批", to_state="已执行", trigger="执行零基预算"),
                ],
            ),
        ),
        ObjectDefinition(
            object_id="obj_zbb_decision_unit",
            name="决策单元",
            category="budget",
            natural_language_definition="零基审视的最小单元，可独立决策的预算包，每个决策单元编制最低/当前/增强三个层级方案",
            key_attributes=["单元名称", "负责人", "范围", "排序", "战略价值评分"],
            participating_relations=[],
        ),
        ObjectDefinition(
            object_id="obj_zbb_package",
            name="决策包",
            category="budget",
            natural_language_definition="决策单元的预算方案，含最低(维持运营最低需求)/当前(维持现有水平)/增强(战略提升)三个层级",
            key_attributes=["决策单元ID", "层级(最低/当前/增强)", "金额", "必要性说明", "战略对齐度"],
            participating_relations=[],
        ),
        # === 成本中心域 (模块5) ===
        ObjectDefinition(
            object_id="obj_cost_center",
            name="成本中心",
            category="cost_center",
            natural_language_definition="独立核算成本的组织单元，设定标准成本并进行差异分析，支持成本分摊和内部结算",
            key_attributes=["成本中心编码", "中心名称", "中心类型(成本/利润/投资/收入)", "负责人", "标准成本"],
            participating_relations=["分摊", "结算"],
        ),
        ObjectDefinition(
            object_id="obj_standard_cost",
            name="标准成本",
            category="cost_center",
            natural_language_definition="成本中心的单位标准成本，作为差异分析的基准，标准成本=标准用量×标准单价",
            key_attributes=["成本中心ID", "成本项目", "标准用量", "标准单价", "标准成本总额", "有效期"],
            participating_relations=[],
        ),
        ObjectDefinition(
            object_id="obj_cost_allocation",
            name="成本分摊",
            category="cost_center",
            natural_language_definition="共享成本按规则分摊到各成本中心，支持按人数/面积/收入比例等多种分摊基准",
            key_attributes=["分摊规则ID", "分摊基准", "分摊比例", "源成本中心", "目标成本中心列表"],
            participating_relations=["分摊"],
        ),
        ObjectDefinition(
            object_id="obj_internal_settlement",
            name="内部结算",
            category="cost_center",
            natural_language_definition="成本中心间的内部交易结算，按内部转移价格计算服务费用",
            key_attributes=["结算ID", "提供方", "使用方", "服务量", "内部转移价格", "结算金额", "结算状态"],
            participating_relations=["结算"],
        ),
        # === HCP合规域 (模块6) ===
        ObjectDefinition(
            object_id="obj_hcp",
            name="HCP(医疗卫生专业人士)",
            category="compliance",
            natural_language_definition="与企业有互动的医疗卫生专业人士(医生/专家)，须进行身份验证和合规管理",
            key_attributes=["HCP编号", "姓名", "机构", "科室", "资质状态", "年度互动次数", "年度付款总额"],
            participating_relations=["互动", "付款"],
        ),
        ObjectDefinition(
            object_id="obj_hcp_interaction",
            name="HCP互动记录",
            category="compliance",
            natural_language_definition="与HCP的每次互动记录，须包含互动目的、内容摘要和参与人员，月度超3次触发合规审查",
            key_attributes=["互动ID", "HCP编号", "互动类型(学术会议/咨询/培训)", "互动日期", "互动目的", "内容摘要", "参与人员"],
            participating_relations=["互动"],
        ),
        ObjectDefinition(
            object_id="obj_hcp_payment",
            name="HCP付款",
            category="compliance",
            natural_language_definition="向HCP支付的讲课费/咨询费/差旅费，须先完成身份验证，年度总额不得超过合规限额",
            key_attributes=["付款ID", "HCP编号", "付款类型", "付款金额", "关联互动ID", "审批状态"],
            participating_relations=["付款"],
        ),
        ObjectDefinition(
            object_id="obj_compliance_rule",
            name="合规规则",
            category="compliance",
            natural_language_definition="HCP互动的合规规则，包括阳光法案、反腐败法等法规要求和企业内部政策",
            key_attributes=["规则ID", "规则名称", "法规依据", "检查逻辑", "违规处理"],
            participating_relations=[],
        ),
        # === 研发管线域 (模块7) ===
        ObjectDefinition(
            object_id="obj_pipeline",
            name="研发管线",
            category="rnd",
            natural_language_definition="创新药研发管线，覆盖发现→临床前→IND→I/II/III期→NDA→上市全生命周期，阶段推进须通过Go/No-Go决策",
            key_attributes=["管线编号", "管线名称", "适应症", "当前阶段", "Go/No-Go状态", "预计上市时间"],
            participating_relations=["管线推进"],
            lifecycle=LifecycleDef(
                states=["发现", "临床前", "IND申报", "I期临床", "II期临床", "III期临床", "NDA申报", "已上市", "已终止", "已暂停"],
                initial_state="发现",
                transitions=[
                    LifecycleTransition(from_state="发现", to_state="临床前", trigger="Go决策"),
                    LifecycleTransition(from_state="临床前", to_state="IND申报", trigger="Go决策"),
                    LifecycleTransition(from_state="IND申报", to_state="I期临床", trigger="IND获批"),
                    LifecycleTransition(from_state="I期临床", to_state="II期临床", trigger="Go决策"),
                    LifecycleTransition(from_state="II期临床", to_state="III期临床", trigger="Go决策"),
                    LifecycleTransition(from_state="III期临床", to_state="NDA申报", trigger="Go决策"),
                    LifecycleTransition(from_state="NDA申报", to_state="已上市", trigger="NDA获批"),
                    LifecycleTransition(from_state="*", to_state="已终止", trigger="No-Go决策"),
                    LifecycleTransition(from_state="*", to_state="已暂停", trigger="暂停决策"),
                ],
            ),
        ),
        ObjectDefinition(
            object_id="obj_rnd_project",
            name="研发项目",
            category="rnd",
            natural_language_definition="管线下的具体研发项目，拥有独立的项目制预算和里程碑管理",
            key_attributes=["项目编号", "项目名称", "所属管线", "项目类型", "项目经理", "预算总额", "已消耗金额"],
            participating_relations=[],
        ),
        ObjectDefinition(
            object_id="obj_rnd_milestone",
            name="研发里程碑",
            category="rnd",
            natural_language_definition="研发项目的关键里程碑，与CRO付款挂钩，里程碑完成方可触发付款",
            key_attributes=["里程碑ID", "所属项目", "里程碑名称", "计划完成日", "实际完成日", "状态", "关联CRO付款"],
            participating_relations=[],
        ),
        ObjectDefinition(
            object_id="obj_clinical_trial",
            name="临床试验",
            category="rnd",
            natural_language_definition="临床试验项目，含CRO合同和多中心分摊，费用按协议比例分摊到各中心",
            key_attributes=["试验编号", "试验名称", "试验阶段", "CRO供应商", "中心数量", "总费用", "分摊协议"],
            participating_relations=[],
        ),
        ObjectDefinition(
            object_id="obj_rnd_budget",
            name="研发预算",
            category="rnd",
            natural_language_definition="研发项目的双口径预算(财务口径+管理口径)，独立于常规预算体系管理",
            key_attributes=["研发项目ID", "财务口径金额", "管理口径金额", "已消耗财务口径", "已消耗管理口径", "口径差异说明"],
            participating_relations=[],
        ),
        # === 经营分析会域 (模块8-9) ===
        ObjectDefinition(
            object_id="obj_report_signoff",
            name="报告签发",
            category="report",
            natural_language_definition="报告的签发流程(编制→审核→签发→发布)，确保报告经过适当审核后方可发布",
            key_attributes=["签发ID", "报告ID", "编制人", "审核人", "签发人", "签发状态"],
            participating_relations=[],
            lifecycle=LifecycleDef(
                states=["编制中", "待审核", "待签发", "已签发", "已发布", "已驳回"],
                initial_state="编制中",
                transitions=[
                    LifecycleTransition(from_state="编制中", to_state="待审核", trigger="提交审核"),
                    LifecycleTransition(from_state="待审核", to_state="待签发", trigger="审核通过"),
                    LifecycleTransition(from_state="待审核", to_state="已驳回", trigger="审核驳回"),
                    LifecycleTransition(from_state="待签发", to_state="已签发", trigger="签发通过"),
                    LifecycleTransition(from_state="已签发", to_state="已发布", trigger="发布"),
                ],
            ),
        ),
        ObjectDefinition(
            object_id="obj_executive_brief",
            name="高管简报",
            category="report",
            natural_language_definition="面向高管的结构化简报，遵循三聚焦范式(聚焦问题/聚焦原因/聚焦行动)，一页纸呈现关键信息",
            key_attributes=["简报ID", "报告期", "聚焦问题", "聚焦原因", "聚焦行动", "关键指标"],
            participating_relations=[],
        ),
        ObjectDefinition(
            object_id="obj_business_review_meeting",
            name="经营分析会",
            category="meeting",
            natural_language_definition="月度/季度经营分析会，遵循一报一会制度，自动生成议程并追踪决议闭环",
            key_attributes=["会议ID", "会议类型(月度/季度)", "会议日期", "议程", "参会人员", "决议数量"],
            participating_relations=[],
        ),
        ObjectDefinition(
            object_id="obj_meeting_resolution",
            name="会议决议",
            category="meeting",
            natural_language_definition="经营分析会的决议事项，含责任人/截止日/预期成果，超时未完成自动预警",
            key_attributes=["决议ID", "所属会议", "决议内容", "责任人", "截止日期", "完成状态"],
            participating_relations=[],
            lifecycle=LifecycleDef(
                states=["待执行", "执行中", "已完成", "已逾期", "已取消"],
                initial_state="待执行",
                transitions=[
                    LifecycleTransition(from_state="待执行", to_state="执行中", trigger="开始执行"),
                    LifecycleTransition(from_state="执行中", to_state="已完成", trigger="执行完成"),
                    LifecycleTransition(from_state="待执行", to_state="已逾期", trigger="超过截止日"),
                    LifecycleTransition(from_state="执行中", to_state="已逾期", trigger="超过截止日"),
                ],
            ),
        ),
        ObjectDefinition(
            object_id="obj_resolution_tracking",
            name="决议追踪",
            category="meeting",
            natural_language_definition="决议执行进度追踪，与PDCA行动项关联，实现从会议决议到行动闭环的完整追踪",
            key_attributes=["追踪ID", "决议ID", "进度百分比", "最新进展", "风险标记", "下次汇报日期"],
            participating_relations=[],
        ),
        # === 人效指标域 (模块10) ===
        ObjectDefinition(
            object_id="obj_headcount_budget",
            name="人头预算",
            category="budget",
            natural_language_definition="按部门/中心的人头预算，与人力成本预算(B1科目)联动，实现人效管控",
            key_attributes=["部门ID", "年度", "编制人数", "实际人数", "人均成本", "人均产出"],
            participating_relations=[],
        ),
        ObjectDefinition(
            object_id="obj_efficiency_metric",
            name="人效指标",
            category="budget",
            natural_language_definition="人效指标体系，含人均产出/人均成本/人均利润/人力成本占收入比等关键指标",
            key_attributes=["指标ID", "指标名称", "计算公式", "基准值", "实际值", "趋势"],
            participating_relations=[],
        ),
        ObjectDefinition(
            object_id="obj_contract",
            name="合同",
            category="contract",
            natural_language_definition="企业与外部供应商或合作方签订的具有法律约束力的协议，是费用支付和三单匹配的核心依据",
            key_attributes=["contract_id", "contract_name", "contract_type", "vendor_id", "total_amount", "signed_date", "expiry_date", "status", "budget_id", "department_id"],
            participating_relations=["匹配"],
            lifecycle=LifecycleDef(
                states=["草拟", "审批中", "已签署", "执行中", "已到期", "已终止"],
                initial_state="草拟",
                transitions=[
                    LifecycleTransition(from_state="草拟", to_state="审批中", trigger="提交审批"),
                    LifecycleTransition(from_state="审批中", to_state="已签署", trigger="审批通过"),
                    LifecycleTransition(from_state="审批中", to_state="草拟", trigger="审批退回"),
                    LifecycleTransition(from_state="已签署", to_state="执行中", trigger="开始执行"),
                    LifecycleTransition(from_state="执行中", to_state="已到期", trigger="到期"),
                    LifecycleTransition(from_state="执行中", to_state="已终止", trigger="终止"),
                ],
            ),
        ),
    ]

    _OBJECTS = {obj.object_id: obj for obj in definitions}


def get_all_objects() -> dict[str, ObjectDefinition]:
    _init_objects()
    return _OBJECTS.copy()


def get_objects_by_category(category: str) -> list[ObjectDefinition]:
    _init_objects()
    return [obj for obj in _OBJECTS.values() if obj.category == category]


def get_object(object_id: str) -> Optional[ObjectDefinition]:
    _init_objects()
    return _OBJECTS.get(object_id)
