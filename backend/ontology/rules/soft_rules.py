from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from ontology.rules.hard_rules import RuleResult


class SoftRuleDefinition(BaseModel):
    rule_id: str
    name: str
    description: str
    default_params: dict = Field(default_factory=dict)


_SOFT_RULES: dict[str, SoftRuleDefinition] = {}

_DEFAULT_PARAMS: dict[str, dict] = {
    "SR-001": {"blue_threshold": 80, "unit": "%", "description": "月度执行进度蓝色阈值(执行率<目标*80%触发)"},
    "SR-002": {"yellow_threshold": 60, "unit": "%", "description": "月度执行进度黄色阈值(执行率<目标*60%触发)"},
    "SR-003": {"red_threshold": 40, "unit": "%", "description": "月度执行进度红色阈值(执行率<目标*40%触发)"},
    "SR-004": {"blue_threshold": 80, "unit": "%", "description": "季度滚动预测蓝色阈值(预测率<目标*80%触发)"},
    "SR-005": {"yellow_threshold": 60, "unit": "%", "description": "季度滚动预测黄色阈值(预测率<目标*60%触发)"},
    "SR-006": {"red_threshold": 40, "unit": "%", "description": "季度滚动预测红色阈值(预测率<目标*40%触发)"},
    "SR-007": {"max_ratio_percentage": 30, "unit": "%", "description": "B类膨胀比例上限"},
    "SR-008": {"deviation_amount": 500000, "unit": "CNY", "description": "单项目/单供应商偏差红色阈值"},
    "SR-009": {"approval_threshold": 50000, "unit": "CNY", "description": "部门负责人审批金额门槛"},
    "SR-010": {"approval_threshold": 200000, "unit": "CNY", "description": "中心总经理审批金额门槛"},
    "SR-011": {
        "annual_budget_threshold": 500000,
        "single_item_threshold": 200000,
        "unit": "CNY",
        "description": "项目化管理门槛(年度预算超50万或新增项目单笔超20万)",
    },
    "SR-012": {"intangible_yellow": 110, "intangible_red": 130, "engineering_yellow": 120, "engineering_red": 150, "fixed_asset_yellow": 120, "fixed_asset_red": 150, "description": "B1资本支出专项阈值"},
    "SR-013": {"ind_yellow": 110, "nda_yellow": 120, "phase3_yellow": 130, "description": "B2研发支出专项阈值"},
    "SR-014": {"travel_single_limit": 50000, "consulting_over_ratio": 110, "total_over_ratio": 110, "description": "B3维持性支出专项阈值"},
    "SR-015": {"yellow_ratio": 110, "blue_ratio": 105, "compliance_oriented": True, "description": "B4税务支出专项阈值"},
    "SR-016": {"sales_yellow": 120, "sales_red": 150, "market_blue": 100, "medical_yellow": 115, "medical_red": 150, "patient_yellow": 110, "patient_red": 130, "policy_yellow": 120, "dev_yellow": 130, "dev_red": 160, "description": "B5市场推广专项阈值"},
    "SR-017": {"salary_yellow": 105, "social_security_blue": 105, "headcount_blue": 105, "headcount_yellow": 110, "headcount_red": 120, "description": "B6人力成本专项阈值"},
    "SR-018": {"procurement_blue": 80, "processing_yellow": 110, "processing_red": 130, "production_yellow": 110, "production_red": 130, "description": "B7货物支出专项阈值"},
    "SR-019": {"single_item_red": 5000000, "stage_gate_ratio": 100, "description": "B8股权投资专项阈值"},
    "SR-020": {"interest_blue": 105, "fee_single_limit": 10000, "description": "B9财务费用专项阈值"},
    "SR-021": {"develop_min": 25, "develop_max": 50, "shrink_min": 10, "shrink_max": 25, "stable_min": 20, "stable_max": 40, "explore_min": 10, "explore_max": 25, "unit": "%", "description": "象限组合失衡判定阈值(各象限预算占比参考范围)"},
    "SR-022": {"execution_rate_closure_rate_gap": 20, "closure_rate_light_score_gap": 1.5, "unit": "%/分", "description": "指标间一致性校验阈值"},
}

_current_params: dict[str, dict] = {}

_param_update_log: list[dict] = []


def _init_soft_rules() -> None:
    global _SOFT_RULES, _current_params
    if _SOFT_RULES:
        return

    definitions = [
        SoftRuleDefinition(rule_id="SR-001", name="月度执行进度蓝色阈值", description="月度预算执行率低于目标执行率的80%时触发蓝色预警", default_params=_DEFAULT_PARAMS["SR-001"]),
        SoftRuleDefinition(rule_id="SR-002", name="月度执行进度黄色阈值", description="月度预算执行率低于目标执行率的60%时触发黄色预警", default_params=_DEFAULT_PARAMS["SR-002"]),
        SoftRuleDefinition(rule_id="SR-003", name="月度执行进度红色阈值", description="月度预算执行率低于目标执行率的40%时触发红色预警", default_params=_DEFAULT_PARAMS["SR-003"]),
        SoftRuleDefinition(rule_id="SR-004", name="季度滚动预测蓝色阈值", description="季度滚动预测执行率低于目标执行率的80%时触发蓝色预警", default_params=_DEFAULT_PARAMS["SR-004"]),
        SoftRuleDefinition(rule_id="SR-005", name="季度滚动预测黄色阈值", description="季度滚动预测执行率低于目标执行率的60%时触发黄色预警", default_params=_DEFAULT_PARAMS["SR-005"]),
        SoftRuleDefinition(rule_id="SR-006", name="季度滚动预测红色阈值", description="季度滚动预测执行率低于目标执行率的40%时触发红色预警", default_params=_DEFAULT_PARAMS["SR-006"]),
        SoftRuleDefinition(rule_id="SR-007", name="B类膨胀比例上限", description="B类预算实际授予总额占B类预算年度总额的比例不得超过30%", default_params=_DEFAULT_PARAMS["SR-007"]),
        SoftRuleDefinition(rule_id="SR-008", name="单项目/单供应商偏差红色阈值", description="单个项目或单个供应商的预算偏差超过50万元时触发红色预警", default_params=_DEFAULT_PARAMS["SR-008"]),
        SoftRuleDefinition(rule_id="SR-009", name="部门负责人审批金额门槛", description="报销金额超过5万元须部门负责人审批", default_params=_DEFAULT_PARAMS["SR-009"]),
        SoftRuleDefinition(rule_id="SR-010", name="中心总经理审批金额门槛", description="报销金额超过20万元须中心总经理审批", default_params=_DEFAULT_PARAMS["SR-010"]),
        SoftRuleDefinition(rule_id="SR-011", name="项目化管理门槛", description="年度预算超过50万或新增项目单笔超过20万的预算项目须纳入项目化管理", default_params=_DEFAULT_PARAMS["SR-011"]),
        SoftRuleDefinition(rule_id="SR-012", name="B1资本支出专项阈值", description="B1资本支出各子项执行率专项预警阈值", default_params=_DEFAULT_PARAMS["SR-012"]),
        SoftRuleDefinition(rule_id="SR-013", name="B2研发支出专项阈值", description="B2研发支出各子项执行率专项预警阈值", default_params=_DEFAULT_PARAMS["SR-013"]),
        SoftRuleDefinition(rule_id="SR-014", name="B3维持性支出专项阈值", description="B3维持性支出各子项执行率专项预警阈值", default_params=_DEFAULT_PARAMS["SR-014"]),
        SoftRuleDefinition(rule_id="SR-015", name="B4税务支出专项阈值", description="B4税务支出执行率专项预警阈值", default_params=_DEFAULT_PARAMS["SR-015"]),
        SoftRuleDefinition(rule_id="SR-016", name="B5市场推广专项阈值", description="B5市场推广各子项执行率专项预警阈值", default_params=_DEFAULT_PARAMS["SR-016"]),
        SoftRuleDefinition(rule_id="SR-017", name="B6人力成本专项阈值", description="B6人力成本各子项执行率专项预警阈值", default_params=_DEFAULT_PARAMS["SR-017"]),
        SoftRuleDefinition(rule_id="SR-018", name="B7货物支出专项阈值", description="B7货物支出各子项执行率专项预警阈值", default_params=_DEFAULT_PARAMS["SR-018"]),
        SoftRuleDefinition(rule_id="SR-019", name="B8股权投资专项阈值", description="B8股权投资各子项执行率专项预警阈值", default_params=_DEFAULT_PARAMS["SR-019"]),
        SoftRuleDefinition(rule_id="SR-020", name="B9财务费用专项阈值", description="B9财务费用各子项执行率专项预警阈值", default_params=_DEFAULT_PARAMS["SR-020"]),
        SoftRuleDefinition(rule_id="SR-021", name="象限组合失衡判定", description="各象限预算占比偏离参考范围时触发告警", default_params=_DEFAULT_PARAMS["SR-021"]),
        SoftRuleDefinition(rule_id="SR-022", name="指标间一致性校验", description="执行率+闭环率+灯色评分逻辑一致性校验", default_params=_DEFAULT_PARAMS["SR-022"]),
    ]

    _SOFT_RULES = {r.rule_id: r for r in definitions}
    _current_params = {rule_id: params.copy() for rule_id, params in _DEFAULT_PARAMS.items()}


def _sr001_monthly_blue(context: dict, params: dict) -> RuleResult:
    execution_rate = context.get("execution_rate", 0)
    target_rate = context.get("target_execution_rate", 100)
    blue_threshold = params.get("blue_threshold", 80)
    threshold_value = target_rate * blue_threshold / 100
    if execution_rate < threshold_value:
        return RuleResult(
            rule_id="SR-001",
            rule_type="soft",
            rule_desc=f"月度执行进度蓝色阈值(执行率<目标{target_rate}%×{blue_threshold}%={threshold_value:.1f}%)",
            passed=False,
            output="PASS",
            confidence=0.9,
            reasoning=f"月度执行率{execution_rate}%低于蓝色阈值{threshold_value:.1f}%，执行进度不足，建议关注",
        )
    return RuleResult(
        rule_id="SR-001",
        rule_type="soft",
        rule_desc=f"月度执行进度蓝色阈值(执行率<目标{target_rate}%×{blue_threshold}%={threshold_value:.1f}%)",
        passed=True,
        output="PASS",
        confidence=0.9,
        reasoning=f"月度执行率{execution_rate}%不低于蓝色阈值{threshold_value:.1f}%，正常",
    )


def _sr002_monthly_yellow(context: dict, params: dict) -> RuleResult:
    execution_rate = context.get("execution_rate", 0)
    target_rate = context.get("target_execution_rate", 100)
    yellow_threshold = params.get("yellow_threshold", 60)
    threshold_value = target_rate * yellow_threshold / 100
    if execution_rate < threshold_value:
        return RuleResult(
            rule_id="SR-002",
            rule_type="soft",
            rule_desc=f"月度执行进度黄色阈值(执行率<目标{target_rate}%×{yellow_threshold}%={threshold_value:.1f}%)",
            passed=False,
            output="PASS",
            confidence=0.85,
            reasoning=f"月度执行率{execution_rate}%低于黄色阈值{threshold_value:.1f}%，执行严重不足，需要关注并分析原因",
        )
    return RuleResult(
        rule_id="SR-002",
        rule_type="soft",
        rule_desc=f"月度执行进度黄色阈值(执行率<目标{target_rate}%×{yellow_threshold}%={threshold_value:.1f}%)",
        passed=True,
        output="PASS",
        confidence=0.85,
        reasoning=f"月度执行率{execution_rate}%不低于黄色阈值{threshold_value:.1f}%",
    )


def _sr003_monthly_red(context: dict, params: dict) -> RuleResult:
    execution_rate = context.get("execution_rate", 0)
    target_rate = context.get("target_execution_rate", 100)
    red_threshold = params.get("red_threshold", 40)
    threshold_value = target_rate * red_threshold / 100
    if execution_rate < threshold_value:
        return RuleResult(
            rule_id="SR-003",
            rule_type="soft",
            rule_desc=f"月度执行进度红色阈值(执行率<目标{target_rate}%×{red_threshold}%={threshold_value:.1f}%)",
            passed=False,
            output="PASS",
            confidence=0.8,
            reasoning=f"月度执行率{execution_rate}%低于红色阈值{threshold_value:.1f}%，执行极度不足，须立即处理",
        )
    return RuleResult(
        rule_id="SR-003",
        rule_type="soft",
        rule_desc=f"月度执行进度红色阈值(执行率<目标{target_rate}%×{red_threshold}%={threshold_value:.1f}%)",
        passed=True,
        output="PASS",
        confidence=0.8,
        reasoning=f"月度执行率{execution_rate}%不低于红色阈值{threshold_value:.1f}%",
    )


def _sr004_quarterly_blue(context: dict, params: dict) -> RuleResult:
    forecast_rate = context.get("forecast_rate", 0)
    target_rate = context.get("target_execution_rate", 100)
    blue_threshold = params.get("blue_threshold", 80)
    threshold_value = target_rate * blue_threshold / 100
    if forecast_rate < threshold_value:
        return RuleResult(
            rule_id="SR-004",
            rule_type="soft",
            rule_desc=f"季度滚动预测蓝色阈值(预测率<目标{target_rate}%×{blue_threshold}%={threshold_value:.1f}%)",
            passed=False,
            output="PASS",
            confidence=0.85,
            reasoning=f"季度滚动预测执行率{forecast_rate}%低于蓝色阈值{threshold_value:.1f}%，建议关注",
        )
    return RuleResult(
        rule_id="SR-004",
        rule_type="soft",
        rule_desc=f"季度滚动预测蓝色阈值(预测率<目标{target_rate}%×{blue_threshold}%={threshold_value:.1f}%)",
        passed=True,
        output="PASS",
        confidence=0.85,
        reasoning=f"季度滚动预测执行率{forecast_rate}%不低于蓝色阈值{threshold_value:.1f}%，正常",
    )


def _sr005_quarterly_yellow(context: dict, params: dict) -> RuleResult:
    forecast_rate = context.get("forecast_rate", 0)
    target_rate = context.get("target_execution_rate", 100)
    yellow_threshold = params.get("yellow_threshold", 60)
    threshold_value = target_rate * yellow_threshold / 100
    if forecast_rate < threshold_value:
        return RuleResult(
            rule_id="SR-005",
            rule_type="soft",
            rule_desc=f"季度滚动预测黄色阈值(预测率<目标{target_rate}%×{yellow_threshold}%={threshold_value:.1f}%)",
            passed=False,
            output="PASS",
            confidence=0.8,
            reasoning=f"季度滚动预测执行率{forecast_rate}%低于黄色阈值{threshold_value:.1f}%，需要关注并分析原因",
        )
    return RuleResult(
        rule_id="SR-005",
        rule_type="soft",
        rule_desc=f"季度滚动预测黄色阈值(预测率<目标{target_rate}%×{yellow_threshold}%={threshold_value:.1f}%)",
        passed=True,
        output="PASS",
        confidence=0.8,
        reasoning=f"季度滚动预测执行率{forecast_rate}%不低于黄色阈值{threshold_value:.1f}%，正常",
    )


def _sr006_quarterly_red(context: dict, params: dict) -> RuleResult:
    forecast_rate = context.get("forecast_rate", 0)
    target_rate = context.get("target_execution_rate", 100)
    red_threshold = params.get("red_threshold", 40)
    threshold_value = target_rate * red_threshold / 100
    if forecast_rate < threshold_value:
        return RuleResult(
            rule_id="SR-006",
            rule_type="soft",
            rule_desc=f"季度滚动预测红色阈值(预测率<目标{target_rate}%×{red_threshold}%={threshold_value:.1f}%)",
            passed=False,
            output="PASS",
            confidence=0.75,
            reasoning=f"季度滚动预测执行率{forecast_rate}%低于红色阈值{threshold_value:.1f}%，须立即处理",
        )
    return RuleResult(
        rule_id="SR-006",
        rule_type="soft",
        rule_desc=f"季度滚动预测红色阈值(预测率<目标{target_rate}%×{red_threshold}%={threshold_value:.1f}%)",
        passed=True,
        output="PASS",
        confidence=0.75,
        reasoning=f"季度滚动预测执行率{forecast_rate}%不低于红色阈值{threshold_value:.1f}%，正常",
    )


def _sr007_b_class_expansion(context: dict, params: dict) -> RuleResult:
    b_granted_total = context.get("b_granted_total", 0)
    b_annual_total = context.get("b_annual_total", 1)
    max_ratio = params.get("max_ratio_percentage", 30)
    actual_ratio = (b_granted_total / b_annual_total * 100) if b_annual_total > 0 else 0
    if actual_ratio > max_ratio:
        return RuleResult(
            rule_id="SR-007",
            rule_type="soft",
            rule_desc=f"B类膨胀比例上限({max_ratio}%)",
            passed=False,
            output="PASS",
            confidence=0.85,
            reasoning=f"B类预算膨胀比例{actual_ratio:.1f}%超过上限{max_ratio}%，需要管控",
        )
    return RuleResult(
        rule_id="SR-007",
        rule_type="soft",
        rule_desc=f"B类膨胀比例上限({max_ratio}%)",
        passed=True,
        output="PASS",
        confidence=0.85,
        reasoning=f"B类预算膨胀比例{actual_ratio:.1f}%未超过上限{max_ratio}%，正常",
    )


def _sr008_deviation_threshold(context: dict, params: dict) -> RuleResult:
    deviation_amount = context.get("deviation_amount", 0)
    threshold = params.get("deviation_amount", 500000)
    if deviation_amount > threshold:
        return RuleResult(
            rule_id="SR-008",
            rule_type="soft",
            rule_desc=f"单项目/单供应商偏差红色阈值({threshold}元)",
            passed=False,
            output="PASS",
            confidence=0.8,
            reasoning=f"偏差金额{deviation_amount}元超过红色阈值{threshold}元，触发红色预警",
        )
    return RuleResult(
        rule_id="SR-008",
        rule_type="soft",
        rule_desc=f"单项目/单供应商偏差红色阈值({threshold}元)",
        passed=True,
        output="PASS",
        confidence=0.8,
        reasoning=f"偏差金额{deviation_amount}元未超过红色阈值{threshold}元，正常",
    )


def _sr009_dept_head_threshold(context: dict, params: dict) -> RuleResult:
    expense_amount = context.get("expense_amount", 0)
    threshold = params.get("approval_threshold", 50000)
    needs_dept_head = expense_amount > threshold
    if needs_dept_head:
        return RuleResult(
            rule_id="SR-009",
            rule_type="soft",
            rule_desc=f"部门负责人审批金额门槛({threshold}元)",
            passed=True,
            output="PASS",
            confidence=0.9,
            reasoning=f"报销金额{expense_amount}元超过门槛{threshold}元，须部门负责人审批",
        )
    return RuleResult(
        rule_id="SR-009",
        rule_type="soft",
        rule_desc=f"部门负责人审批金额门槛({threshold}元)",
        passed=True,
        output="PASS",
        confidence=0.9,
        reasoning=f"报销金额{expense_amount}元未超过门槛{threshold}元，无需部门负责人审批",
    )


def _sr010_center_head_threshold(context: dict, params: dict) -> RuleResult:
    expense_amount = context.get("expense_amount", 0)
    threshold = params.get("approval_threshold", 200000)
    needs_center_head = expense_amount > threshold
    if needs_center_head:
        return RuleResult(
            rule_id="SR-010",
            rule_type="soft",
            rule_desc=f"中心总经理审批金额门槛({threshold}元)",
            passed=True,
            output="PASS",
            confidence=0.9,
            reasoning=f"报销金额{expense_amount}元超过门槛{threshold}元，须中心总经理审批",
        )
    return RuleResult(
        rule_id="SR-010",
        rule_type="soft",
        rule_desc=f"中心总经理审批金额门槛({threshold}元)",
        passed=True,
        output="PASS",
        confidence=0.9,
        reasoning=f"报销金额{expense_amount}元未超过门槛{threshold}元，无需中心总经理审批",
    )


def _sr011_project_management_threshold(context: dict, params: dict) -> RuleResult:
    annual_budget = context.get("annual_budget", 0)
    single_item_amount = context.get("single_item_amount", 0)
    annual_threshold = params.get("annual_budget_threshold", 500000)
    single_threshold = params.get("single_item_threshold", 200000)
    needs_project_mgmt = annual_budget > annual_threshold or single_item_amount > single_threshold
    if needs_project_mgmt:
        return RuleResult(
            rule_id="SR-011",
            rule_type="soft",
            rule_desc=f"项目化管理门槛(年度>{annual_threshold}元或单笔>{single_threshold}元)",
            passed=True,
            output="PASS",
            confidence=0.9,
            reasoning="预算项目满足项目化管理门槛，须纳入项目化管理",
        )
    return RuleResult(
        rule_id="SR-011",
        rule_type="soft",
        rule_desc=f"项目化管理门槛(年度>{annual_threshold}元或单笔>{single_threshold}元)",
        passed=True,
        output="PASS",
        confidence=0.9,
        reasoning="预算项目未满足项目化管理门槛，按通用管控执行",
    )


def _sr012_b1_capital(context: dict, params: dict) -> RuleResult:
    l1_code = context.get("l1_code", "")
    used_ratio = context.get("used_ratio", 100)
    if l1_code != "B1":
        return RuleResult(rule_id="SR-012", rule_type="soft", rule_desc="B1资本支出专项阈值", passed=True, output="PASS", confidence=0.9, reasoning="非B1科目，不适用本规则")
    sub_type = context.get("sub_type", "")
    alert_level = "正常"
    if sub_type == "无形资产":
        if used_ratio >= params.get("intangible_red", 130):
            alert_level = "红色"
        elif used_ratio >= params.get("intangible_yellow", 110):
            alert_level = "黄色"
    elif sub_type == "在建工程":
        if used_ratio >= params.get("engineering_red", 150):
            alert_level = "红色"
        elif used_ratio >= params.get("engineering_yellow", 120):
            alert_level = "黄色"
    elif sub_type == "固定资产":
        if used_ratio >= params.get("fixed_asset_red", 150):
            alert_level = "红色"
        elif used_ratio >= params.get("fixed_asset_yellow", 120):
            alert_level = "黄色"
    passed = alert_level == "正常"
    return RuleResult(rule_id="SR-012", rule_type="soft", rule_desc=f"B1资本支出专项阈值({sub_type})", passed=passed, output="PASS", confidence=0.85, reasoning=f"B1资本支出{sub_type}执行率{used_ratio}%，预警级别: {alert_level}")


def _sr013_b2_rd(context: dict, params: dict) -> RuleResult:
    l1_code = context.get("l1_code", "")
    used_ratio = context.get("used_ratio", 100)
    if l1_code != "B2":
        return RuleResult(rule_id="SR-013", rule_type="soft", rule_desc="B2研发支出专项阈值", passed=True, output="PASS", confidence=0.9, reasoning="非B2科目，不适用本规则")
    sub_type = context.get("sub_type", "")
    alert_level = "正常"
    if sub_type == "IND":
        if used_ratio >= params.get("ind_yellow", 110):
            alert_level = "黄色"
    elif sub_type == "NDA":
        if used_ratio >= params.get("nda_yellow", 120):
            alert_level = "黄色"
    elif sub_type == "Phase3":
        if used_ratio >= params.get("phase3_yellow", 130):
            alert_level = "黄色"
    passed = alert_level == "正常"
    return RuleResult(rule_id="SR-013", rule_type="soft", rule_desc=f"B2研发支出专项阈值({sub_type})", passed=passed, output="PASS", confidence=0.85, reasoning=f"B2研发支出{sub_type}执行率{used_ratio}%，预警级别: {alert_level}")


def _sr014_b3_maintenance(context: dict, params: dict) -> RuleResult:
    l1_code = context.get("l1_code", "")
    used_ratio = context.get("used_ratio", 100)
    if l1_code != "B3":
        return RuleResult(rule_id="SR-014", rule_type="soft", rule_desc="B3维持性支出专项阈值", passed=True, output="PASS", confidence=0.9, reasoning="非B3科目，不适用本规则")
    sub_type = context.get("sub_type", "")
    alert_level = "正常"
    if sub_type == "差旅":
        single_amount = context.get("single_amount", 0)
        if single_amount > params.get("travel_single_limit", 50000):
            alert_level = "黄色"
    elif sub_type == "咨询":
        if used_ratio >= params.get("consulting_over_ratio", 110):
            alert_level = "黄色"
    elif sub_type == "总额":
        if used_ratio >= params.get("total_over_ratio", 110):
            alert_level = "黄色"
    passed = alert_level == "正常"
    return RuleResult(rule_id="SR-014", rule_type="soft", rule_desc=f"B3维持性支出专项阈值({sub_type})", passed=passed, output="PASS", confidence=0.85, reasoning=f"B3维持性支出{sub_type}预警级别: {alert_level}")


def _sr015_b4_tax(context: dict, params: dict) -> RuleResult:
    l1_code = context.get("l1_code", "")
    used_ratio = context.get("used_ratio", 100)
    if l1_code != "B4":
        return RuleResult(rule_id="SR-015", rule_type="soft", rule_desc="B4税务支出专项阈值", passed=True, output="PASS", confidence=0.9, reasoning="非B4科目，不适用本规则")
    alert_level = "正常"
    if used_ratio >= params.get("yellow_ratio", 110):
        alert_level = "黄色"
    elif used_ratio <= params.get("blue_ratio", 105):
        alert_level = "蓝色"
    compliance_oriented = params.get("compliance_oriented", True)
    passed = alert_level == "正常"
    return RuleResult(rule_id="SR-015", rule_type="soft", rule_desc="B4税务支出专项阈值", passed=passed, output="PASS", confidence=0.85, reasoning=f"B4税务支出执行率{used_ratio}%，预警级别: {alert_level}，合规导向: {compliance_oriented}")


def _sr016_b5_marketing(context: dict, params: dict) -> RuleResult:
    l1_code = context.get("l1_code", "")
    used_ratio = context.get("used_ratio", 100)
    if l1_code != "B5":
        return RuleResult(rule_id="SR-016", rule_type="soft", rule_desc="B5市场推广专项阈值", passed=True, output="PASS", confidence=0.9, reasoning="非B5科目，不适用本规则")
    sub_type = context.get("sub_type", "")
    alert_level = "正常"
    if sub_type == "销售费用":
        if used_ratio >= params.get("sales_red", 150):
            alert_level = "红色"
        elif used_ratio >= params.get("sales_yellow", 120):
            alert_level = "黄色"
    elif sub_type == "市场活动":
        if used_ratio <= params.get("market_blue", 100):
            alert_level = "蓝色"
    elif sub_type == "医学":
        if used_ratio >= params.get("medical_red", 150):
            alert_level = "红色"
        elif used_ratio >= params.get("medical_yellow", 115):
            alert_level = "黄色"
    elif sub_type == "患者":
        if used_ratio >= params.get("patient_red", 130):
            alert_level = "红色"
        elif used_ratio >= params.get("patient_yellow", 110):
            alert_level = "黄色"
    elif sub_type == "政策":
        if used_ratio >= params.get("policy_yellow", 120):
            alert_level = "黄色"
    elif sub_type == "发展":
        if used_ratio >= params.get("dev_red", 160):
            alert_level = "红色"
        elif used_ratio >= params.get("dev_yellow", 130):
            alert_level = "黄色"
    passed = alert_level == "正常"
    return RuleResult(rule_id="SR-016", rule_type="soft", rule_desc=f"B5市场推广专项阈值({sub_type})", passed=passed, output="PASS", confidence=0.85, reasoning=f"B5市场推广{sub_type}执行率{used_ratio}%，预警级别: {alert_level}")


def _sr017_b6_hr(context: dict, params: dict) -> RuleResult:
    l1_code = context.get("l1_code", "")
    used_ratio = context.get("used_ratio", 100)
    if l1_code != "B6":
        return RuleResult(rule_id="SR-017", rule_type="soft", rule_desc="B6人力成本专项阈值", passed=True, output="PASS", confidence=0.9, reasoning="非B6科目，不适用本规则")
    sub_type = context.get("sub_type", "")
    alert_level = "正常"
    if sub_type == "薪酬":
        if used_ratio >= params.get("salary_yellow", 105):
            alert_level = "黄色"
    elif sub_type == "社保":
        if used_ratio <= params.get("social_security_blue", 105):
            alert_level = "蓝色"
    elif sub_type == "编制":
        if used_ratio >= params.get("headcount_red", 120):
            alert_level = "红色"
        elif used_ratio >= params.get("headcount_yellow", 110):
            alert_level = "黄色"
        elif used_ratio <= params.get("headcount_blue", 105):
            alert_level = "蓝色"
    passed = alert_level == "正常"
    return RuleResult(rule_id="SR-017", rule_type="soft", rule_desc=f"B6人力成本专项阈值({sub_type})", passed=passed, output="PASS", confidence=0.85, reasoning=f"B6人力成本{sub_type}执行率{used_ratio}%，预警级别: {alert_level}")


def _sr018_b7_goods(context: dict, params: dict) -> RuleResult:
    l1_code = context.get("l1_code", "")
    used_ratio = context.get("used_ratio", 100)
    if l1_code != "B7":
        return RuleResult(rule_id="SR-018", rule_type="soft", rule_desc="B7货物支出专项阈值", passed=True, output="PASS", confidence=0.9, reasoning="非B7科目，不适用本规则")
    sub_type = context.get("sub_type", "")
    alert_level = "正常"
    if sub_type == "采购":
        if used_ratio <= params.get("procurement_blue", 80):
            alert_level = "蓝色"
    elif sub_type == "加工":
        if used_ratio >= params.get("processing_red", 130):
            alert_level = "红色"
        elif used_ratio >= params.get("processing_yellow", 110):
            alert_level = "黄色"
    elif sub_type == "生产":
        if used_ratio >= params.get("production_red", 130):
            alert_level = "红色"
        elif used_ratio >= params.get("production_yellow", 110):
            alert_level = "黄色"
    passed = alert_level == "正常"
    return RuleResult(rule_id="SR-018", rule_type="soft", rule_desc=f"B7货物支出专项阈值({sub_type})", passed=passed, output="PASS", confidence=0.85, reasoning=f"B7货物支出{sub_type}执行率{used_ratio}%，预警级别: {alert_level}")


def _sr019_b8_equity(context: dict, params: dict) -> RuleResult:
    l1_code = context.get("l1_code", "")
    used_ratio = context.get("used_ratio", 100)
    if l1_code != "B8":
        return RuleResult(rule_id="SR-019", rule_type="soft", rule_desc="B8股权投资专项阈值", passed=True, output="PASS", confidence=0.9, reasoning="非B8科目，不适用本规则")
    alert_level = "正常"
    single_item_amount = context.get("single_item_amount", 0)
    if single_item_amount >= params.get("single_item_red", 5000000):
        alert_level = "红色"
    if used_ratio >= params.get("stage_gate_ratio", 100):
        alert_level = alert_level if alert_level == "红色" else "黄色"
    passed = alert_level == "正常"
    return RuleResult(rule_id="SR-019", rule_type="soft", rule_desc="B8股权投资专项阈值", passed=passed, output="PASS", confidence=0.85, reasoning=f"B8股权投资执行率{used_ratio}%，单笔{single_item_amount}元，预警级别: {alert_level}")


def _sr020_b9_finance(context: dict, params: dict) -> RuleResult:
    l1_code = context.get("l1_code", "")
    used_ratio = context.get("used_ratio", 100)
    if l1_code != "B9":
        return RuleResult(rule_id="SR-020", rule_type="soft", rule_desc="B9财务费用专项阈值", passed=True, output="PASS", confidence=0.9, reasoning="非B9科目，不适用本规则")
    alert_level = "正常"
    sub_type = context.get("sub_type", "")
    if sub_type == "利息":
        if used_ratio <= params.get("interest_blue", 105):
            alert_level = "蓝色"
    elif sub_type == "手续费":
        single_amount = context.get("single_amount", 0)
        if single_amount > params.get("fee_single_limit", 10000):
            alert_level = "黄色"
    passed = alert_level == "正常"
    return RuleResult(rule_id="SR-020", rule_type="soft", rule_desc=f"B9财务费用专项阈值({sub_type})", passed=passed, output="PASS", confidence=0.85, reasoning=f"B9财务费用{sub_type}执行率{used_ratio}%，预警级别: {alert_level}")


def _sr021_quadrant_imbalance(context: dict, params: dict) -> RuleResult:
    quadrant_ratios = context.get("quadrant_ratios", {})
    if not quadrant_ratios:
        return RuleResult(rule_id="SR-021", rule_type="soft", rule_desc="象限组合失衡判定", passed=True, output="PASS", confidence=0.9, reasoning="无象限分布数据，跳过校验")
    violations = []
    ranges = {
        "发展": (params.get("develop_min", 25), params.get("develop_max", 50)),
        "收缩": (params.get("shrink_min", 10), params.get("shrink_max", 25)),
        "稳定": (params.get("stable_min", 20), params.get("stable_max", 40)),
        "探索": (params.get("explore_min", 10), params.get("explore_max", 25)),
    }
    for quadrant, ratio in quadrant_ratios.items():
        if quadrant in ranges:
            lo, hi = ranges[quadrant]
            if ratio < lo or ratio > hi:
                violations.append(f"{quadrant}象限占比{ratio}%偏离参考范围[{lo}%-{hi}%]")
    if violations:
        return RuleResult(
            rule_id="SR-021", rule_type="soft",
            rule_desc="象限组合失衡判定",
            passed=False, output="PASS", confidence=0.85,
            reasoning="象限组合失衡：" + "；".join(violations),
        )
    return RuleResult(rule_id="SR-021", rule_type="soft", rule_desc="象限组合失衡判定", passed=True, output="PASS", confidence=0.85, reasoning="象限组合分布正常")


def _sr022_metric_consistency(context: dict, params: dict) -> RuleResult:
    execution_rate = context.get("execution_rate")
    closure_rate = context.get("closure_rate")
    light_score = context.get("light_score")
    if execution_rate is None or closure_rate is None:
        return RuleResult(rule_id="SR-022", rule_type="soft", rule_desc="指标间一致性校验", passed=True, output="PASS", confidence=0.9, reasoning="缺少执行率或闭环率数据，跳过校验")
    inconsistencies = []
    er_cr_gap = params.get("execution_rate_closure_rate_gap", 20)
    # Check 1: execution rate high but closure rate low
    if execution_rate > 90 and closure_rate < 80:
        inconsistencies.append(f"执行率{execution_rate}%高但闭环率{closure_rate}%低，可能存在预警响应不及时")
    # Check 2: closure rate and light score consistency
    if light_score is not None:
        cr_ls_gap = params.get("closure_rate_light_score_gap", 1.5)
        expected_light = max(1, min(4, (100 - closure_rate) / 25))
        if abs(light_score - expected_light) > cr_ls_gap:
            inconsistencies.append(f"闭环率{closure_rate}%与灯色评分{light_score}不一致")
    if inconsistencies:
        return RuleResult(
            rule_id="SR-022", rule_type="soft",
            rule_desc="指标间一致性校验",
            passed=False, output="PASS", confidence=0.8,
            reasoning="指标间一致性异常：" + "；".join(inconsistencies),
        )
    return RuleResult(rule_id="SR-022", rule_type="soft", rule_desc="指标间一致性校验", passed=True, output="PASS", confidence=0.8, reasoning="指标间逻辑一致性正常")


_SOFT_RULE_CHECKS: dict[str, callable] = {
    "SR-001": _sr001_monthly_blue,
    "SR-002": _sr002_monthly_yellow,
    "SR-003": _sr003_monthly_red,
    "SR-004": _sr004_quarterly_blue,
    "SR-005": _sr005_quarterly_yellow,
    "SR-006": _sr006_quarterly_red,
    "SR-007": _sr007_b_class_expansion,
    "SR-008": _sr008_deviation_threshold,
    "SR-009": _sr009_dept_head_threshold,
    "SR-010": _sr010_center_head_threshold,
    "SR-011": _sr011_project_management_threshold,
    "SR-012": _sr012_b1_capital,
    "SR-013": _sr013_b2_rd,
    "SR-014": _sr014_b3_maintenance,
    "SR-015": _sr015_b4_tax,
    "SR-016": _sr016_b5_marketing,
    "SR-017": _sr017_b6_hr,
    "SR-018": _sr018_b7_goods,
    "SR-019": _sr019_b8_equity,
    "SR-020": _sr020_b9_finance,
    "SR-021": _sr021_quadrant_imbalance,
    "SR-022": _sr022_metric_consistency,
}


class SoftRuleEngine:
    def __init__(self) -> None:
        _init_soft_rules()

    def load_params(self, yaml_path: str | Path) -> None:
        global _current_params
        path = Path(yaml_path)
        if not path.exists():
            return
        with open(path, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
        for rule_id, params in loaded.items():
            if rule_id in _current_params:
                _current_params[rule_id].update(params)

    def execute(self, rule_id: str, context: dict) -> RuleResult:
        check_fn = _SOFT_RULE_CHECKS.get(rule_id)
        if check_fn is None:
            return RuleResult(
                rule_id=rule_id,
                rule_type="soft",
                rule_desc="未知软规则",
                passed=False,
                output="PASS",
                confidence=0.0,
                reasoning=f"软规则{rule_id}不存在",
            )
        params = _current_params.get(rule_id, {})
        return check_fn(context, params)

    def update_param(self, rule_id: str, param_name: str, new_value, approver: str) -> None:
        _init_soft_rules()
        if rule_id not in _current_params:
            return
        old_value = _current_params[rule_id].get(param_name)
        _current_params[rule_id][param_name] = new_value
        _param_update_log.append({
            "rule_id": rule_id,
            "param_name": param_name,
            "old_value": old_value,
            "new_value": new_value,
            "approver": approver,
        })

    def get_all_params(self) -> dict:
        _init_soft_rules()
        return {rule_id: params.copy() for rule_id, params in _current_params.items()}

    def get_rule(self, rule_id: str) -> SoftRuleDefinition | None:
        _init_soft_rules()
        return _SOFT_RULES.get(rule_id)

    def get_all_rules(self) -> dict[str, SoftRuleDefinition]:
        _init_soft_rules()
        return _SOFT_RULES.copy()
