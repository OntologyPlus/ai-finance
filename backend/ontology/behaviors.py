from typing import List, Optional

from pydantic import BaseModel, Field


class SideEffect(BaseModel):
    target_type: str          # e.g. "obj_budget_item"
    field: str                # e.g. "frozen_amount"
    operation: str            # increment/decrement/set/compute
    value_source: str         # e.g. "param.annual_amount" or "context.current_amount * 0.3"
    description: str = ""     # human-readable description

class Precondition(BaseModel):
    type: str                 # field_check/relation_exists/status_in/rule_passed
    target: str               # object/relation/rule ID
    condition: str            # e.g. "status == 'approved'"
    error_message: str        # message when precondition not met


class BehaviorDefinition(BaseModel):
    behavior_id: str
    name: str
    preconditions: str
    effects: str
    parameters: List[str] = Field(default_factory=list)
    stage: str = Field(description="阶段一~八")
    preconditions_struct: List[Precondition] = Field(default_factory=list, description="结构化前置条件")
    effects_struct: List[SideEffect] = Field(default_factory=list, description="结构化副作用")


_BEHAVIORS: dict[str, BehaviorDefinition] = {}

_SCENE_BEHAVIOR_MAP: dict[str, list[str]] = {
    "fin.budget_planning": [
        "fin.budget.a_class_freeze",
        "fin.budget.b_class_grant",
    ],
    "fin.budget_grant": [
        "fin.budget.a_class_freeze",
        "fin.budget.b_class_grant",
        "fin.budget.b2a_convert",
        "fin.budget.release",
    ],
    "fin.expense_reimbursement": [
        "fin.expense.submit",
        "fin.approval.org_line",
        "fin.approval.legal_line",
        "fin.budget.write_off",
        "fin.control.route",
    ],
    "fin.business_analysis": [
        "fin.analysis.3gap",
        "fin.analysis.3list",
    ],
    "fin.alert_monitoring": [
        "fin.alert.create_monthly",
        "fin.alert.create_quarterly",
        "fin.alert.create_milestone",
    ],
    "fin.alert_response": [
        "fin.alert.escalate",
        "fin.alert.close",
    ],
    "fin.b_class_management": [
        "fin.budget.b_class_grant",
        "fin.budget.b2a_convert",
        "fin.budget.release",
    ],
    "fin.pdca_review": [
        "fin.pdca.monthly",
        "fin.pdca.quarterly",
        "fin.pdca.yearly",
    ],
    "fin.report_issuance": [
        "fin.report.monthly",
        "fin.report.quarterly",
    ],
    "fin.next_cycle": [
        "fin.pdca.yearly",
    ],
    "fin.budget_adjustment": [
        "fin.adjustment.transfer",
        "fin.budget.release",
    ],
    "fin.cash_flow_monitoring": [
        "fin.cashflow.forecast",
        "fin.cashflow.liquidity_alert",
        "fin.cashflow.profit_cash_gap",
        "fin.cashflow.receipt_payment_match",
    ],
    "fin.scenario_planning": [
        "fin.scenario.create",
        "fin.scenario.compare",
        "fin.scenario.elastic_adjust",
        "fin.scenario.stress_test",
        "fin.scenario.emergency_allocate",
    ],
    "fin.impact_assessment": [
        "fin.impact.assess",
        "fin.impact.trace",
        "fin.impact.mitigate",
    ],
    "fin.zero_based_budget": [
        "fin.zbb.initiate",
        "fin.zbb.create_package",
        "fin.zbb.rank",
        "fin.zbb.synthesize",
    ],
    "fin.cost_center_accounting": [
        "fin.costcenter.set_standard",
        "fin.costcenter.variance_analysis",
        "fin.costcenter.allocate",
        "fin.costcenter.settle",
    ],
    "fin.hcp_compliance": [
        "fin.hcp.verify",
        "fin.hcp.compliance_check",
        "fin.hcp.payment_limit_check",
        "fin.hcp.aggregate_risk",
    ],
    "fin.pipeline_management": [
        "fin.pipeline.advance",
        "fin.pipeline.terminate",
        "fin.rnd.dual_budget",
        "fin.rnd.cro_payment",
        "fin.rnd.multi_center_allocate",
        "fin.rnd.efficiency_analysis",
    ],
    "fin.business_review": [
        "fin.report.signoff",
        "fin.report.executive_brief",
        "fin.meeting.generate_agenda",
        "fin.meeting.record_resolution",
        "fin.meeting.track_resolution",
        "fin.meeting.cross_center_compare",
    ],
}


def _init_behaviors() -> None:
    global _BEHAVIORS
    if _BEHAVIORS:
        return

    definitions = [
        BehaviorDefinition(
            behavior_id="fin.budget.a_class_freeze",
            name="A类预算冻结",
            preconditions="预算项目已审批通过且类别为A；年度预算金额已确认",
            effects="对应预算项目的额度被冻结，冻结额度等于年度预算金额，可用额度相应减少",
            parameters=["budget_id", "annual_amount", "approver"],
            stage="阶段二",
            preconditions_struct=[
                Precondition(type="status_in", target="obj_budget_item", condition="status == '已审批'", error_message="预算项目未审批"),
                Precondition(type="field_check", target="obj_budget_item", condition="budget_category == 'A'", error_message="非A类预算不可冻结"),
            ],
            effects_struct=[
                SideEffect(target_type="obj_budget_item", field="frozen_amount", operation="set", value_source="param.annual_amount", description="冻结额度等于年度预算金额"),
                SideEffect(target_type="obj_budget_item", field="available_amount", operation="decrement", value_source="param.annual_amount", description="可用额度减少"),
            ],
        ),
        BehaviorDefinition(
            behavior_id="fin.budget.b_class_grant",
            name="B类预算授予",
            preconditions="预算项目已审批通过且类别为B；象限归属已确定",
            effects="B类预算按授予比例(初始比例由管委会决定)授予额度，授予额度=年度预算×授予比例",
            parameters=["budget_id", "annual_amount", "grant_percentage", "approver"],
            stage="阶段二",
            preconditions_struct=[
                Precondition(type="status_in", target="obj_budget_item", condition="status == '已审批'", error_message="预算项目未审批"),
                Precondition(type="field_check", target="obj_budget_item", condition="budget_category == 'B'", error_message="非B类预算不可授予"),
            ],
            effects_struct=[
                SideEffect(target_type="obj_budget_item", field="granted_amount", operation="compute", value_source="param.annual_amount * param.grant_percentage", description="授予额度=年度预算×授予比例"),
            ],
        ),
        BehaviorDefinition(
            behavior_id="fin.budget.b2a_convert",
            name="B→A转换",
            preconditions="B类预算项目里程碑已达标；有里程碑达标证据；已向管委会提交专项报告",
            effects="预算类别从B转为A，转换后额度按A类规则冻结；转换记录记入B2A转换表",
            parameters=["budget_id", "milestone_evidence", "milestone_period", "approver", "report_to_committee"],
            stage="阶段二/五",
        ),
        BehaviorDefinition(
            behavior_id="fin.budget.release",
            name="预算释放",
            preconditions="预算项目已取消或B类预算未使用额度需释放；经审批同意",
            effects="释放的额度回归可用状态或回收到预算池；更新预算项目的已冻结/已授予额度",
            parameters=["budget_id", "release_amount", "release_reason", "approver"],
            stage="阶段二/六",
        ),
        BehaviorDefinition(
            behavior_id="fin.control.route",
            name="管控路由",
            preconditions="报销单已提交且已挂载预算项目；L3科目管控级别已确定",
            effects="根据L3科目管控级别(强管控/中心弱管控/组合管控/不管控)确定审批路径和约束力度；强管控走完整双线审批",
            parameters=["expense_id", "l3_code", "control_tag", "amount"],
            stage="阶段三",
        ),
        BehaviorDefinition(
            behavior_id="fin.expense.submit",
            name="报销提交",
            preconditions="报销人已选择挂载预算项目；报销金额在预算可用额度内(硬规则HR-001)",
            effects="报销单进入审批流程；占用预算项目可用额度(预占)",
            parameters=["expense_id", "applicant", "amount", "budget_id", "l3_code"],
            stage="阶段三",
        ),
        BehaviorDefinition(
            behavior_id="fin.approval.org_line",
            name="组织线审批",
            preconditions="报销单已提交；组织线审批路径已确定(根据金额和科目)",
            effects="沿组织架构逐级审批完成；更新报销单审批状态",
            parameters=["expense_id", "approver_chain", "current_approver", "amount"],
            stage="阶段三",
        ),
        BehaviorDefinition(
            behavior_id="fin.approval.legal_line",
            name="法人线审批",
            preconditions="报销单已通过组织线审批；财经中心预算管理部审核预算合规性",
            effects="法人线审批完成；实现双签闭环(业务+财经BP)(硬规则HR-005)",
            parameters=["expense_id", "finance_bp", "compliance_check_result"],
            stage="阶段三",
        ),
        BehaviorDefinition(
            behavior_id="fin.budget.write_off",
            name="预算核销",
            preconditions="报销单双线审批已完成；核销金额不超过预算可用额度(硬规则HR-002)",
            effects="预算项目已使用额度增加，可用额度减少；报销单状态变为已核销",
            parameters=["expense_id", "budget_id", "write_off_amount"],
            stage="阶段三",
            preconditions_struct=[
                Precondition(type="rule_passed", target="HR-002", condition="核销金额不超过预算可用额度", error_message="预算核销不可超额(HR-002)"),
                Precondition(type="status_in", target="obj_expense_report", condition="status == '已审批'", error_message="报销单未完成审批"),
            ],
            effects_struct=[
                SideEffect(target_type="obj_budget_item", field="used_amount", operation="increment", value_source="param.write_off_amount", description="已使用额度增加"),
                SideEffect(target_type="obj_budget_item", field="available_amount", operation="decrement", value_source="param.write_off_amount", description="可用额度减少"),
            ],
        ),
        BehaviorDefinition(
            behavior_id="fin.alert.create_monthly",
            name="月度预警创建",
            preconditions="月度执行进度数据已更新；执行率超过阈值(蓝105%/黄110%/红超年度预算)",
            effects="生成对应级别的预警记录；通知责任角色响应",
            parameters=["budget_id", "execution_rate", "threshold_type", "alert_level"],
            stage="阶段五",
        ),
        BehaviorDefinition(
            behavior_id="fin.alert.create_quarterly",
            name="季度预警创建",
            preconditions="季度滚动预测数据已更新；预测超年度预算比例超过阈值(蓝105%/黄110%/红115%)",
            effects="生成季度滚动预测预警记录；纳入季度经营分析会议题",
            parameters=["budget_id", "forecast_rate", "threshold_type", "alert_level"],
            stage="阶段五",
        ),
        BehaviorDefinition(
            behavior_id="fin.alert.create_milestone",
            name="里程碑预警创建",
            preconditions="里程碑延期未完成且未报备(硬规则HR-009)；或实际支出超出里程碑计划金额(硬规则HR-010)",
            effects="生成里程碑预警记录；触发支出管控(新增支出须经对应级别审批，硬规则HR-011)",
            parameters=["budget_id", "milestone_id", "delay_days", "overspend_amount", "alert_level"],
            stage="阶段五",
        ),
        BehaviorDefinition(
            behavior_id="fin.alert.escalate",
            name="预警升级",
            preconditions="红色预警或预警超时未响应",
            effects="预警升级至上级角色直至管委会；升级记录记入预警记录",
            parameters=["alert_id", "current_level", "escalate_to", "escalate_reason"],
            stage="阶段五",
            preconditions_struct=[
                Precondition(type="field_check", target="obj_alert_record", condition="alert_level == '红色' or hours_since_alert > response_hours", error_message="仅红色或超时预警可升级"),
            ],
            effects_struct=[
                SideEffect(target_type="obj_alert_record", field="escalated_to", operation="set", value_source="param.escalate_to", description="预警升级至上级角色"),
            ],
        ),
        BehaviorDefinition(
            behavior_id="fin.alert.close",
            name="预警闭环",
            preconditions="预警已响应且响应方案已确认(双签闭环)；未闭环预警已在经营分析会中专项汇报(硬规则HR-012)",
            effects="预警状态变为已闭环；闭环记录记入预警记录",
            parameters=["alert_id", "resolution", "confirmed_by", "report_in_meeting"],
            stage="阶段五/六",
            preconditions_struct=[
                Precondition(type="rule_passed", target="HR-013", condition="双签闭环：响应人≠确认人且响应≥20字", error_message="预警闭环必须双签(HR-013)"),
            ],
            effects_struct=[
                SideEffect(target_type="obj_alert_record", field="status", operation="set", value_source="'已闭环'", description="预警状态变为已闭环"),
            ],
        ),
        BehaviorDefinition(
            behavior_id="fin.analysis.3gap",
            name="3GAP分析",
            preconditions="月度/季度执行数据已更新；预警记录已汇总",
            effects="输出目标差距、执行差距、能力差距分析结果；定位问题根因",
            parameters=["analysis_period", "budget_ids", "alert_ids", "target_data", "actual_data"],
            stage="阶段四",
        ),
        BehaviorDefinition(
            behavior_id="fin.analysis.3list",
            name="3List分析",
            preconditions="3GAP分析已完成；问题根因已定位",
            effects="输出必赢清单、改善清单、资源清单；制定行动方案",
            parameters=["analysis_period", "gap_results", "action_items"],
            stage="阶段四",
        ),
        BehaviorDefinition(
            behavior_id="fin.report.monthly",
            name="月度快报出具",
            preconditions="月度执行数据已汇总；预警记录已统计",
            effects="出具月度快报，包含执行率、偏差分析和预警汇总",
            parameters=["report_period", "execution_data", "alert_summary"],
            stage="阶段七",
        ),
        BehaviorDefinition(
            behavior_id="fin.report.quarterly",
            name="季度汇报出具",
            preconditions="季度3GAP+3List分析已完成；滚动预测已更新",
            effects="出具季度汇报PPT，包含3GAP+3List分析结果、滚动预测和战略执行评估",
            parameters=["quarter", "gap_analysis", "list_analysis", "forecast", "strategy_assessment"],
            stage="阶段七",
        ),
        BehaviorDefinition(
            behavior_id="fin.pdca.monthly",
            name="月度PDCA复盘",
            preconditions="月度快报已出具；预警处理情况已汇总",
            effects="完成月度PDCA复盘，检查预警闭环率、执行偏差改善情况",
            parameters=["month", "alert_closure_rate", "deviation_improvement"],
            stage="阶段六",
        ),
        BehaviorDefinition(
            behavior_id="fin.pdca.quarterly",
            name="季度PDCA复盘",
            preconditions="季度汇报已出具；3GAP+3List行动方案执行情况已评估",
            effects="完成季度PDCA复盘，评估战略执行进展、调整下季度行动方案",
            parameters=["quarter", "strategy_progress", "action_plan_adjustment"],
            stage="阶段六",
        ),
        BehaviorDefinition(
            behavior_id="fin.pdca.yearly",
            name="年度PDCA复盘",
            preconditions="年度执行数据已汇总；战略目标达成度已评估",
            effects="完成年度PDCA复盘，出具年度复盘报告；为下年度预算编制提供改进建议",
            parameters=["year", "execution_summary", "strategy_achievement", "improvement_plan"],
            stage="阶段八",
        ),
        BehaviorDefinition(
            behavior_id="fin.adjustment.transfer",
            name="预算调拨",
            preconditions="调拨原因已明确；同象限内调拨经财经中心审批，跨象限调拨须管委会批准(硬规则HR-008)",
            effects="调出方预算额度减少，调入方预算额度增加；调拨记录记入系统",
            parameters=["from_budget_id", "to_budget_id", "transfer_amount", "reason", "approver", "cross_quadrant"],
            stage="阶段六",
            preconditions_struct=[
                Precondition(type="rule_passed", target="HR-008", condition="跨象限调拨须管委会批准", error_message="跨象限调拨须管委会批准(HR-008)"),
            ],
            effects_struct=[
                SideEffect(target_type="obj_budget_item", field="annual_amount", operation="decrement", value_source="param.transfer_amount", description="调出方预算额度减少"),
                SideEffect(target_type="obj_budget_item", field="annual_amount", operation="increment", value_source="param.transfer_amount", description="调入方预算额度增加"),
            ],
        ),
        # === 现金流监控域 (模块1) ===
        BehaviorDefinition(
            behavior_id="fin.cashflow.forecast",
            name="现金流预测",
            preconditions="收入预算+支出预算+历史付款模式数据已就绪",
            effects="输出未来3/6/12个月现金流预测，区分经营/投资/筹资三类活动",
            parameters=["period", "horizon_months", "activity_type"],
            stage="阶段八",
        ),
        BehaviorDefinition(
            behavior_id="fin.cashflow.liquidity_alert",
            name="资金缺口预警",
            preconditions="现金流预测完成；预测净现金流低于安全阈值",
            effects="触发资金缺口预警，通知财务负责人",
            parameters=["period", "gap_amount", "threshold"],
            stage="阶段八",
        ),
        BehaviorDefinition(
            behavior_id="fin.cashflow.profit_cash_gap",
            name="利润现金流差异分析",
            preconditions="利润表和现金流量表数据已就绪",
            effects="输出利润与现金流的差异分析，识别差异来源(应收/应付/折旧/摊销)",
            parameters=["period", "profit_amount", "cash_flow_amount"],
            stage="阶段八",
        ),
        BehaviorDefinition(
            behavior_id="fin.cashflow.receipt_payment_match",
            name="收支匹配分析",
            preconditions="付款排期和收款预测数据已就绪",
            effects="输出收支时间差分析，识别流动性风险窗口",
            parameters=["period"],
            stage="阶段八",
        ),
        # === 情景规划域 (模块2) ===
        BehaviorDefinition(
            behavior_id="fin.scenario.create",
            name="情景创建",
            preconditions="预算周期已确定；至少定义基准和悲观两个情景的假设条件",
            effects="创建新情景，含假设条件和对应预算方案",
            parameters=["name", "scenario_type", "assumptions"],
            stage="阶段一",
        ),
        BehaviorDefinition(
            behavior_id="fin.scenario.compare",
            name="情景对比",
            preconditions="至少两个情景已编制完成",
            effects="输出多情景预算对比分析，识别关键差异和风险点",
            parameters=["scenario_ids"],
            stage="阶段一",
        ),
        BehaviorDefinition(
            behavior_id="fin.scenario.elastic_adjust",
            name="弹性调整",
            preconditions="实际业务量数据已更新；弹性系数已设定",
            effects="基于实际业务量自动调整预算额度，调整幅度不超过基准±30%",
            parameters=["budget_id", "actual_volume", "elasticity_coefficient"],
            stage="阶段二/五",
        ),
        BehaviorDefinition(
            behavior_id="fin.scenario.stress_test",
            name="压力测试",
            preconditions="至少一个压力测试情景已定义",
            effects="输出极端情景下的财务压力测试结果，评估集团承受能力",
            parameters=["scenario_id", "stress_factors"],
            stage="阶段一/八",
        ),
        BehaviorDefinition(
            behavior_id="fin.scenario.emergency_allocate",
            name="紧急调拨",
            preconditions="预算储备金可用余额充足；紧急调拨原因已明确",
            effects="从预算储备金紧急调拨资金，须经管委会批准，5个工作日内补办正式手续",
            parameters=["reserve_id", "budget_id", "amount", "reason"],
            stage="阶段六",
        ),
        # === 影响评估域 (模块3) ===
        BehaviorDefinition(
            behavior_id="fin.impact.assess",
            name="影响评估",
            preconditions="操作类型和参数已确定",
            effects="评估操作对预算/费用/预警/现金流/战略五个域的全链路影响",
            parameters=["operation_type", "target_id", "change_amount"],
            stage="全阶段",
        ),
        BehaviorDefinition(
            behavior_id="fin.impact.trace",
            name="影响追踪",
            preconditions="影响链已创建",
            effects="追踪已发生操作的实际影响，更新影响链状态",
            parameters=["chain_id"],
            stage="全阶段",
        ),
        BehaviorDefinition(
            behavior_id="fin.impact.mitigate",
            name="影响缓解",
            preconditions="影响评估完成且存在负面影响",
            effects="对负面影响提出缓解方案，自动关联到预警或行动项",
            parameters=["chain_id", "mitigation_type"],
            stage="全阶段",
        ),
        # === 零基预算域 (模块4) ===
        BehaviorDefinition(
            behavior_id="fin.zbb.initiate",
            name="零基审视启动",
            preconditions="年度预算编制周期已启动",
            effects="创建零基审视，初始化决策单元",
            parameters=["period", "total_budget_constraint"],
            stage="阶段一",
        ),
        BehaviorDefinition(
            behavior_id="fin.zbb.create_package",
            name="决策包编制",
            preconditions="决策单元已创建",
            effects="为每个决策单元编制最低/当前/增强三个层级的预算方案",
            parameters=["unit_id", "level", "amount", "justification"],
            stage="阶段一",
        ),
        BehaviorDefinition(
            behavior_id="fin.zbb.rank",
            name="决策包排序",
            preconditions="所有决策包已编制完成",
            effects="按战略价值排序所有决策包，为预算合成提供依据",
            parameters=["review_id"],
            stage="阶段一",
        ),
        BehaviorDefinition(
            behavior_id="fin.zbb.synthesize",
            name="零基预算合成",
            preconditions="决策包已排序；总额约束已确定",
            effects="基于排序和总额约束合成最终零基预算",
            parameters=["review_id", "total_budget"],
            stage="阶段一",
        ),
        # === 成本中心域 (模块5) ===
        BehaviorDefinition(
            behavior_id="fin.costcenter.set_standard",
            name="标准成本设定",
            preconditions="成本中心已创建；成本项目已定义",
            effects="设定成本中心的标准成本(标准用量×标准单价)",
            parameters=["cost_center_id", "cost_item", "standard_quantity", "standard_price"],
            stage="阶段一",
        ),
        BehaviorDefinition(
            behavior_id="fin.costcenter.variance_analysis",
            name="差异分析",
            preconditions="标准成本已设定；实际成本数据已收集",
            effects="输出实际成本vs标准成本的差异分析(价格差异+用量差异)",
            parameters=["cost_center_id", "period"],
            stage="阶段四/五",
        ),
        BehaviorDefinition(
            behavior_id="fin.costcenter.allocate",
            name="成本分摊",
            preconditions="分摊规则已定义；源成本数据已收集",
            effects="共享成本按规则分摊到各成本中心",
            parameters=["allocation_rule_id", "period"],
            stage="阶段四",
        ),
        BehaviorDefinition(
            behavior_id="fin.costcenter.settle",
            name="内部结算",
            preconditions="内部转移价格已设定；服务量已确认",
            effects="成本中心间按内部转移价格完成服务费用结算",
            parameters=["provider_id", "consumer_id", "service_volume", "transfer_price"],
            stage="阶段四",
        ),
        # === HCP合规域 (模块6) ===
        BehaviorDefinition(
            behavior_id="fin.hcp.verify",
            name="HCP身份验证",
            preconditions="HCP基本信息已录入",
            effects="验证HCP身份和资质，更新资质状态",
            parameters=["hcp_id"],
            stage="阶段三",
        ),
        BehaviorDefinition(
            behavior_id="fin.hcp.compliance_check",
            name="互动合规检查",
            preconditions="HCP互动记录已提交",
            effects="检查HCP互动是否符合合规规则(阳光法案/反腐败法/企业政策)",
            parameters=["interaction_id"],
            stage="阶段三",
        ),
        BehaviorDefinition(
            behavior_id="fin.hcp.payment_limit_check",
            name="付款限额检查",
            preconditions="HCP付款申请已提交；HCP身份已验证",
            effects="检查HCP年度付款总额是否超过合规限额",
            parameters=["hcp_id", "payment_amount"],
            stage="阶段三",
        ),
        BehaviorDefinition(
            behavior_id="fin.hcp.aggregate_risk",
            name="聚合风险分析",
            preconditions="HCP互动和付款数据已汇总",
            effects="分析HCP互动的聚合风险(频率/金额/区域)，识别异常模式",
            parameters=["hcp_id", "period"],
            stage="阶段五",
        ),
        # === 管线管理域 (模块7) ===
        BehaviorDefinition(
            behavior_id="fin.pipeline.advance",
            name="管线阶段推进",
            preconditions="Go/No-Go决策已完成且结果为Go",
            effects="管线推进到下一阶段，更新预算分配",
            parameters=["pipeline_id", "target_stage", "go_nogo_decision"],
            stage="全阶段",
        ),
        BehaviorDefinition(
            behavior_id="fin.pipeline.terminate",
            name="管线终止/暂停",
            preconditions="No-Go决策已完成或暂停决策已批准",
            effects="管线终止或暂停，释放剩余预算",
            parameters=["pipeline_id", "action", "reason"],
            stage="全阶段",
        ),
        BehaviorDefinition(
            behavior_id="fin.rnd.dual_budget",
            name="研发双口径预算编制",
            preconditions="研发项目已创建",
            effects="编制财务口径+管理口径的独立预算，记录口径差异",
            parameters=["project_id", "finance_amount", "management_amount"],
            stage="阶段一",
        ),
        BehaviorDefinition(
            behavior_id="fin.rnd.cro_payment",
            name="CRO付款管理",
            preconditions="CRO合同已签订；里程碑已定义",
            effects="里程碑完成触发CRO付款，未完成不可付款",
            parameters=["milestone_id", "cro_contract_id", "payment_amount"],
            stage="阶段三",
        ),
        BehaviorDefinition(
            behavior_id="fin.rnd.multi_center_allocate",
            name="多中心分摊",
            preconditions="临床试验多中心协议已签订",
            effects="按协议比例分摊临床试验费用到各中心",
            parameters=["trial_id", "total_cost", "allocation_ratios"],
            stage="阶段三/四",
        ),
        BehaviorDefinition(
            behavior_id="fin.rnd.efficiency_analysis",
            name="研发效能分析",
            preconditions="研发项目执行数据已收集",
            effects="分析研发投入产出效能(研发费用率/管线推进率/里程碑达成率)",
            parameters=["period", "project_ids"],
            stage="阶段四",
        ),
        # === 经营分析会域 (模块8-9) ===
        BehaviorDefinition(
            behavior_id="fin.report.signoff",
            name="报告签发",
            preconditions="报告已编制完成",
            effects="报告走签发流程(编制→审核→签发→发布)",
            parameters=["report_id", "author", "reviewer", "signer"],
            stage="阶段七",
        ),
        BehaviorDefinition(
            behavior_id="fin.report.executive_brief",
            name="高管简报生成",
            preconditions="经营分析数据已就绪",
            effects="基于三聚焦范式生成高管简报(聚焦问题/聚焦原因/聚焦行动)",
            parameters=["period", "key_metrics"],
            stage="阶段七",
        ),
        BehaviorDefinition(
            behavior_id="fin.meeting.generate_agenda",
            name="经营分析会议程生成",
            preconditions="预警/3GAP/执行率数据已汇总",
            effects="自动生成经营分析会议程，包含未闭环预警专项议题",
            parameters=["meeting_type", "period"],
            stage="阶段六/七",
        ),
        BehaviorDefinition(
            behavior_id="fin.meeting.record_resolution",
            name="决议记录",
            preconditions="经营分析会已召开",
            effects="记录会议决议(责任人/截止日/预期成果)",
            parameters=["meeting_id", "resolution_content", "owner", "deadline"],
            stage="阶段六/七",
        ),
        BehaviorDefinition(
            behavior_id="fin.meeting.track_resolution",
            name="决议追踪",
            preconditions="会议决议已记录",
            effects="追踪决议执行进度，超时自动预警",
            parameters=["resolution_id", "progress", "risk_flag"],
            stage="阶段六/七/八",
        ),
        BehaviorDefinition(
            behavior_id="fin.meeting.cross_center_compare",
            name="跨中心对比",
            preconditions="多中心经营数据已收集",
            effects="多中心经营数据横向对比，识别优秀实践和薄弱环节",
            parameters=["period", "center_ids"],
            stage="阶段四",
        ),
    ]

    _BEHAVIORS = {b.behavior_id: b for b in definitions}


def get_all_behaviors() -> dict[str, BehaviorDefinition]:
    _init_behaviors()
    return _BEHAVIORS.copy()


def get_behaviors_for_scene(scene_id: str) -> list[BehaviorDefinition]:
    _init_behaviors()
    behavior_ids = _SCENE_BEHAVIOR_MAP.get(scene_id, [])
    return [b for b in _BEHAVIORS.values() if b.behavior_id in behavior_ids]


def get_behavior(behavior_id: str) -> Optional[BehaviorDefinition]:
    _init_behaviors()
    return _BEHAVIORS.get(behavior_id)
