from typing import Literal

from pydantic import BaseModel, Field


class RuleResult(BaseModel):
    rule_id: str
    rule_type: Literal["hard", "soft", "reasoning"] = "hard"
    rule_desc: str
    passed: bool
    output: Literal["PASS", "BLOCK"]
    confidence: float = 1.0
    reasoning: str


class HardRuleDefinition(BaseModel):
    rule_id: str
    name: str
    description: str
    violation_handling: str = ""


def _hr001_expense_must_have_budget(context: dict) -> RuleResult:
    expense_budget_id = context.get("budget_id")
    has_budget = context.get("has_budget", False)
    if not expense_budget_id or not has_budget:
        return RuleResult(
            rule_id="HR-001",
            rule_desc="支出必须有对应预算",
            passed=False,
            output="BLOCK",
            reasoning="报销单未挂载到任何预算项目，或挂载的预算项目不存在，违反'支出必须有对应预算'硬规则",
        )
    return RuleResult(
        rule_id="HR-001",
        rule_desc="支出必须有对应预算",
        passed=True,
        output="PASS",
        reasoning=f"报销单已挂载到预算项目{expense_budget_id}，符合'支出必须有对应预算'硬规则",
    )


def _hr002_writeoff_no_overage(context: dict) -> RuleResult:
    write_off_amount = context.get("write_off_amount", 0)
    available_amount = context.get("available_amount", 0)
    if write_off_amount > available_amount:
        return RuleResult(
            rule_id="HR-002",
            rule_desc="预算核销不可超额",
            passed=False,
            output="BLOCK",
            reasoning=f"核销金额{write_off_amount}超过预算可用额度{available_amount}，违反'预算核销不可超额'硬规则",
        )
    return RuleResult(
        rule_id="HR-002",
        rule_desc="预算核销不可超额",
        passed=True,
        output="PASS",
        reasoning=f"核销金额{write_off_amount}在预算可用额度{available_amount}范围内，符合'预算核销不可超额'硬规则",
    )


def _hr003_alert_not_overrun_permit(context: dict) -> RuleResult:
    alert_triggered = context.get("alert_triggered", False)
    expense_approved = context.get("expense_approved", False)
    if alert_triggered and expense_approved:
        return RuleResult(
            rule_id="HR-003",
            rule_desc="预警触发≠超支许可",
            passed=False,
            output="BLOCK",
            reasoning="预警已触发但支出仍被批准通过，违反'预警触发≠超支许可'硬规则，预警触发后应限制支出而非放行",
        )
    return RuleResult(
        rule_id="HR-003",
        rule_desc="预警触发≠超支许可",
        passed=True,
        output="PASS",
        reasoning="未出现预警触发后放行支出的情况，符合'预警触发≠超支许可'硬规则",
    )


def _hr004_a_class_approve_first(context: dict) -> RuleResult:
    budget_category = context.get("budget_category", "")
    has_pre_approval = context.get("has_pre_approval", False)
    if budget_category == "A" and not has_pre_approval:
        return RuleResult(
            rule_id="HR-004",
            rule_desc="先批后用(A类预算)",
            passed=False,
            output="BLOCK",
            reasoning="A类预算项目未经过预先审批即执行支出，违反'先批后用(A类预算)'硬规则",
        )
    return RuleResult(
        rule_id="HR-004",
        rule_desc="先批后用(A类预算)",
        passed=True,
        output="PASS",
        reasoning="A类预算项目已预先审批或非A类预算，符合'先批后用(A类预算)'硬规则",
    )


def _hr005_dual_sign_closure(context: dict) -> RuleResult:
    business_bp_signed = context.get("business_bp_signed", False)
    finance_bp_signed = context.get("finance_bp_signed", False)
    if not business_bp_signed or not finance_bp_signed:
        return RuleResult(
            rule_id="HR-005",
            rule_desc="双签闭环(业务+财经BP)",
            passed=False,
            output="BLOCK",
            reasoning=f"双签未完成：业务BP签认={business_bp_signed}，财经BP签认={finance_bp_signed}，违反'双签闭环(业务+财经BP)'硬规则",
        )
    return RuleResult(
        rule_id="HR-005",
        rule_desc="双签闭环(业务+财经BP)",
        passed=True,
        output="PASS",
        reasoning="业务BP和财经BP均已签认，双签闭环完成，符合'双签闭环(业务+财经BP)'硬规则",
    )


def _hr006_tax_declaration_complete(context: dict) -> RuleResult:
    tax_data_complete = context.get("tax_data_complete", False)
    tax_data_accurate = context.get("tax_data_accurate", False)
    if not tax_data_complete or not tax_data_accurate:
        return RuleResult(
            rule_id="HR-006",
            rule_desc="税务申报数据必须完整准确",
            passed=False,
            output="BLOCK",
            reasoning=f"税务申报数据不满足要求：完整={tax_data_complete}，准确={tax_data_accurate}，违反'税务申报数据必须完整准确'硬规则",
        )
    return RuleResult(
        rule_id="HR-006",
        rule_desc="税务申报数据必须完整准确",
        passed=True,
        output="PASS",
        reasoning="税务申报数据完整且准确，符合'税务申报数据必须完整准确'硬规则",
    )


def _hr007_committee_decides_ratio(context: dict) -> RuleResult:
    ratio_decided_by_committee = context.get("ratio_decided_by_committee", False)
    if not ratio_decided_by_committee:
        return RuleResult(
            rule_id="HR-007",
            rule_desc="战略预算组合比例由管委会决定",
            passed=False,
            output="BLOCK",
            reasoning="战略预算组合比例未经管委会决定，违反'战略预算组合比例由管委会决定'硬规则",
        )
    return RuleResult(
        rule_id="HR-007",
        rule_desc="战略预算组合比例由管委会决定",
        passed=True,
        output="PASS",
        reasoning="战略预算组合比例已由管委会决定，符合'战略预算组合比例由管委会决定'硬规则",
    )


def _hr008_cross_quadrant_committee_approval(context: dict) -> RuleResult:
    cross_quadrant = context.get("cross_quadrant", False)
    committee_approved = context.get("committee_approved", False)
    if cross_quadrant and not committee_approved:
        return RuleResult(
            rule_id="HR-008",
            rule_desc="跨象限调拨须管委会批准",
            passed=False,
            output="BLOCK",
            reasoning="跨象限调拨未经管委会批准，违反'跨象限调拨须管委会批准'硬规则",
        )
    return RuleResult(
        rule_id="HR-008",
        rule_desc="跨象限调拨须管委会批准",
        passed=True,
        output="PASS",
        reasoning="非跨象限调拨或已获管委会批准，符合'跨象限调拨须管委会批准'硬规则",
    )


def _hr009_milestone_delay_report(context: dict) -> RuleResult:
    milestone_delayed = context.get("milestone_delayed", False)
    delay_reported = context.get("delay_reported", False)
    proceeding_next = context.get("proceeding_next", False)
    if milestone_delayed and not delay_reported and proceeding_next:
        return RuleResult(
            rule_id="HR-009",
            rule_desc="里程碑延期未完成报备不得自行推进下一里程碑",
            passed=False,
            output="BLOCK",
            reasoning="里程碑延期未完成报备即自行推进下一里程碑，违反'里程碑延期未完成报备不得自行推进下一里程碑'硬规则",
        )
    return RuleResult(
        rule_id="HR-009",
        rule_desc="里程碑延期未完成报备不得自行推进下一里程碑",
        passed=True,
        output="PASS",
        reasoning="里程碑未延期或已报备或未自行推进，符合'里程碑延期未完成报备不得自行推进下一里程碑'硬规则",
    )


def _hr010_actual_not_exceed_milestone(context: dict) -> RuleResult:
    actual_amount = context.get("actual_amount", 0)
    milestone_planned_amount = context.get("milestone_planned_amount", 0)
    if actual_amount > milestone_planned_amount:
        return RuleResult(
            rule_id="HR-010",
            rule_desc="实际支出不得超出里程碑计划金额",
            passed=False,
            output="BLOCK",
            reasoning=f"实际支出{actual_amount}超出里程碑计划金额{milestone_planned_amount}，违反'实际支出不得超出里程碑计划金额'硬规则",
        )
    return RuleResult(
        rule_id="HR-010",
        rule_desc="实际支出不得超出里程碑计划金额",
        passed=True,
        output="PASS",
        reasoning=f"实际支出{actual_amount}未超出里程碑计划金额{milestone_planned_amount}，符合'实际支出不得超出里程碑计划金额'硬规则",
    )


def _hr011_alert_expense_approval(context: dict) -> RuleResult:
    alert_triggered = context.get("alert_triggered", False)
    new_expense_has_approval = context.get("new_expense_has_approval", False)
    has_new_expense = context.get("has_new_expense", False)
    if alert_triggered and has_new_expense and not new_expense_has_approval:
        return RuleResult(
            rule_id="HR-011",
            rule_desc="里程碑预警触发后新增支出须经对应级别审批",
            passed=False,
            output="BLOCK",
            reasoning="里程碑预警触发后新增支出未经对应级别审批，违反'里程碑预警触发后新增支出须经对应级别审批'硬规则",
        )
    return RuleResult(
        rule_id="HR-011",
        rule_desc="里程碑预警触发后新增支出须经对应级别审批",
        passed=True,
        output="PASS",
        reasoning="无预警触发或新增支出已获对应级别审批，符合'里程碑预警触发后新增支出须经对应级别审批'硬规则",
    )


def _hr012_unclosed_alert_in_meeting(context: dict) -> RuleResult:
    has_unclosed_alert = context.get("has_unclosed_alert", False)
    reported_in_meeting = context.get("reported_in_meeting", False)
    if has_unclosed_alert and not reported_in_meeting:
        return RuleResult(
            rule_id="HR-012",
            rule_desc="未闭环预警须在经营分析会中专项汇报",
            passed=False,
            output="BLOCK",
            reasoning="存在未闭环预警但未在经营分析会中专项汇报，违反'未闭环预警须在经营分析会中专项汇报'硬规则",
        )
    return RuleResult(
        rule_id="HR-012",
        rule_desc="未闭环预警须在经营分析会中专项汇报",
        passed=True,
        output="PASS",
        reasoning="无未闭环预警或已在经营分析会中专项汇报，符合'未闭环预警须在经营分析会中专项汇报'硬规则",
    )


def _hr013_alert_closure_dual_sign(context: dict) -> RuleResult:
    business_response = context.get("business_response", "")
    business_responder = context.get("business_responder", "")
    bp_confirmation = context.get("bp_confirmation", "")
    bp_confirmer = context.get("bp_confirmer", "")

    if not business_response or len(business_response.strip()) < 20:
        return RuleResult(
            rule_id="HR-013",
            rule_desc="预警闭环必须双签(业务响应≥20字+财经BP确认)",
            passed=False,
            output="BLOCK",
            reasoning=f"业务响应不满足要求：{'内容为空' if not business_response else f'字数不足({len(business_response.strip())}字<20字)'}，违反'预警闭环必须双签'硬规则",
        )

    if not bp_confirmation:
        return RuleResult(
            rule_id="HR-013",
            rule_desc="预警闭环必须双签(业务响应≥20字+财经BP确认)",
            passed=False,
            output="BLOCK",
            reasoning="财经BP确认意见为空，违反'预警闭环必须双签'硬规则",
        )

    if business_responder and bp_confirmer and business_responder == bp_confirmer:
        return RuleResult(
            rule_id="HR-013",
            rule_desc="预警闭环必须双签(业务响应≥20字+财经BP确认)",
            passed=False,
            output="BLOCK",
            reasoning=f"业务响应人({business_responder})与财经BP确认人({bp_confirmer})为同一人，违反'双签必须由不同人员完成'硬规则",
        )

    return RuleResult(
        rule_id="HR-013",
        rule_desc="预警闭环必须双签(业务响应≥20字+财经BP确认)",
        passed=True,
        output="PASS",
        reasoning="业务响应和财经BP确认均已完成且由不同人员签认，双签闭环有效",
    )


def _hr014_budget_grant_requires_strategic_intent(context: dict) -> RuleResult:
    budget_status = context.get("budget_status", "")
    strategic_intent_l1 = context.get("strategic_intent_l1", "")
    strategic_intent_l2 = context.get("strategic_intent_l2", "")

    if budget_status in ("已授予", "执行中") and (not strategic_intent_l1 or not strategic_intent_l2):
        return RuleResult(
            rule_id="HR-014",
            rule_desc="预算授予时战略意图维度不能为空",
            passed=False,
            output="BLOCK",
            reasoning=f"预算项目状态为'{budget_status}'但战略意图维度不完整(L1={'已填' if strategic_intent_l1 else '空'}, L2={'已填' if strategic_intent_l2 else '空'})，违反'预算授予时战略意图维度不能为空'硬规则",
        )
    return RuleResult(
        rule_id="HR-014",
        rule_desc="预算授予时战略意图维度不能为空",
        passed=True,
        output="PASS",
        reasoning="预算项目战略意图维度完整或尚未授予，符合'预算授予时战略意图维度不能为空'硬规则",
    )


def _hr015_expense_time_limit(context: dict) -> RuleResult:
    from datetime import date, timedelta
    expense_date = context.get("expense_date")
    submit_date = context.get("submit_date")
    if expense_date is None:
        return RuleResult(
            rule_id="HR-015",
            rule_desc="报销时效限制",
            passed=False,
            output="BLOCK",
            reasoning="费用发生日期为空，违反'报销时效限制'硬规则",
        )
    if isinstance(expense_date, str):
        from datetime import datetime as dt
        expense_date = dt.strptime(expense_date, "%Y-%m-%d").date()
    if submit_date is None:
        submit_date = date.today()
    elif isinstance(submit_date, str):
        from datetime import datetime as dt
        submit_date = dt.strptime(submit_date, "%Y-%m-%d").date()

    expense_year = expense_date.year
    submit_year = submit_date.year

    if expense_year < submit_year:
        deadline = date(submit_year, 3, 31)
        if submit_date > deadline:
            return RuleResult(
                rule_id="HR-015",
                rule_desc="报销时效限制",
                passed=False,
                output="BLOCK",
                reasoning=f"跨年度费用须在次年3月31日前报销，费用发生日期{expense_date}，截止日期{deadline}，提交日期{submit_date}，违反'报销时效限制'硬规则",
            )
    else:
        max_allowed = expense_date + timedelta(days=90)
        if submit_date > max_allowed:
            return RuleResult(
                rule_id="HR-015",
                rule_desc="报销时效限制",
                passed=False,
                output="BLOCK",
                reasoning=f"费用发生日期距今超过3个月，费用发生日期{expense_date}，最迟报销日期{max_allowed}，提交日期{submit_date}，违反'报销时效限制'硬规则",
            )
    return RuleResult(
        rule_id="HR-015",
        rule_desc="报销时效限制",
        passed=True,
        output="PASS",
        reasoning="费用发生日期在报销时效内，符合'报销时效限制'硬规则",
    )


def _hr016_cashflow_forecast_horizon(context: dict) -> RuleResult:
    horizon_months = context.get("horizon_months", 0)
    if horizon_months < 3:
        return RuleResult(
            rule_id="HR-016",
            rule_desc="现金流预测必须覆盖至少3个月",
            passed=False,
            output="BLOCK",
            reasoning="现金流预测覆盖期限不足3个月，违反'现金流预测必须覆盖至少3个月'硬规则",
        )
    return RuleResult(
        rule_id="HR-016",
        rule_desc="现金流预测必须覆盖至少3个月",
        passed=True,
        output="PASS",
        reasoning=f"现金流预测覆盖{horizon_months}个月，符合'现金流预测必须覆盖至少3个月'硬规则",
    )


def _hr017_liquidity_gap_must_report(context: dict) -> RuleResult:
    has_gap = context.get("has_gap", False)
    gap_reported = context.get("gap_reported", False)
    if has_gap and not gap_reported:
        return RuleResult(
            rule_id="HR-017",
            rule_desc="流动性缺口必须上报",
            passed=False,
            output="BLOCK",
            reasoning="存在流动性缺口但未上报，违反'流动性缺口必须上报'硬规则",
        )
    return RuleResult(
        rule_id="HR-017",
        rule_desc="流动性缺口必须上报",
        passed=True,
        output="PASS",
        reasoning="无流动性缺口或已上报，符合'流动性缺口必须上报'硬规则",
    )


def _hr018_profit_cash_gap_analysis(context: dict) -> RuleResult:
    gap_ratio = context.get("gap_ratio", 0)
    special_analysis_done = context.get("special_analysis_done", False)
    if abs(gap_ratio) > 0.2 and not special_analysis_done:
        return RuleResult(
            rule_id="HR-018",
            rule_desc="利润现金流差异超过20%须专项分析",
            passed=False,
            output="BLOCK",
            reasoning="利润与现金流差异超过20%但未进行专项分析，违反硬规则",
        )
    return RuleResult(
        rule_id="HR-018",
        rule_desc="利润现金流差异超过20%须专项分析",
        passed=True,
        output="PASS",
        reasoning="利润与现金流差异在20%以内或已进行专项分析，符合硬规则",
    )


def _hr019_scenario_pessimistic_required(context: dict) -> RuleResult:
    has_pessimistic_scenario = context.get("has_pessimistic_scenario", False)
    if not has_pessimistic_scenario:
        return RuleResult(
            rule_id="HR-019",
            rule_desc="情景规划必须包含悲观情景",
            passed=False,
            output="BLOCK",
            reasoning="情景规划未包含悲观情景，违反'情景规划必须包含悲观情景'硬规则",
        )
    return RuleResult(
        rule_id="HR-019",
        rule_desc="情景规划必须包含悲观情景",
        passed=True,
        output="PASS",
        reasoning="情景规划已包含悲观情景，符合'情景规划必须包含悲观情景'硬规则",
    )


def _hr020_elastic_adjustment_limit(context: dict) -> RuleResult:
    adjustment_ratio = context.get("adjustment_ratio", 0)
    if abs(adjustment_ratio) > 0.3:
        return RuleResult(
            rule_id="HR-020",
            rule_desc="弹性调整幅度不得超过30%",
            passed=False,
            output="BLOCK",
            reasoning="弹性调整幅度超过30%，违反'弹性调整幅度不得超过30%'硬规则",
        )
    return RuleResult(
        rule_id="HR-020",
        rule_desc="弹性调整幅度不得超过30%",
        passed=True,
        output="PASS",
        reasoning=f"弹性调整幅度{adjustment_ratio}在30%以内，符合'弹性调整幅度不得超过30%'硬规则",
    )


def _hr021_stress_test_revenue_decline(context: dict) -> RuleResult:
    stress_revenue_decline = context.get("stress_revenue_decline", 0)
    if stress_revenue_decline < 0.3:
        return RuleResult(
            rule_id="HR-021",
            rule_desc="压力测试必须包含收入下降30%情景",
            passed=False,
            output="BLOCK",
            reasoning="压力测试未包含收入下降30%的情景，违反硬规则",
        )
    return RuleResult(
        rule_id="HR-021",
        rule_desc="压力测试必须包含收入下降30%情景",
        passed=True,
        output="PASS",
        reasoning="压力测试已包含收入下降30%的情景，符合硬规则",
    )


def _hr022_emergency_allocation_committee(context: dict) -> RuleResult:
    is_emergency = context.get("is_emergency", False)
    committee_approved = context.get("committee_approved", False)
    if is_emergency and not committee_approved:
        return RuleResult(
            rule_id="HR-022",
            rule_desc="紧急调拨须经管委会批准",
            passed=False,
            output="BLOCK",
            reasoning="紧急调拨未经管委会批准，违反'紧急调拨须经管委会批准'硬规则",
        )
    return RuleResult(
        rule_id="HR-022",
        rule_desc="紧急调拨须经管委会批准",
        passed=True,
        output="PASS",
        reasoning="非紧急调拨或已获管委会批准，符合'紧急调拨须经管委会批准'硬规则",
    )


def _hr023_impact_assessment_five_domains(context: dict) -> RuleResult:
    assessed_domains_count = context.get("assessed_domains_count", 0)
    if assessed_domains_count < 5:
        return RuleResult(
            rule_id="HR-023",
            rule_desc="影响评估必须覆盖5个域",
            passed=False,
            output="BLOCK",
            reasoning="影响评估未覆盖全部5个域(预算/费用/预警/现金流/战略)，违反硬规则",
        )
    return RuleResult(
        rule_id="HR-023",
        rule_desc="影响评估必须覆盖5个域",
        passed=True,
        output="PASS",
        reasoning="影响评估已覆盖全部5个域(预算/费用/预警/现金流/战略)，符合硬规则",
    )


def _hr024_high_risk_report_committee(context: dict) -> RuleResult:
    overall_risk = context.get("overall_risk", "")
    reported_to_committee = context.get("reported_to_committee", False)
    if overall_risk == "高" and not reported_to_committee:
        return RuleResult(
            rule_id="HR-024",
            rule_desc="高风险影响须上报管委会",
            passed=False,
            output="BLOCK",
            reasoning="影响评估结果为高风险但未上报管委会，违反硬规则",
        )
    return RuleResult(
        rule_id="HR-024",
        rule_desc="高风险影响须上报管委会",
        passed=True,
        output="PASS",
        reasoning="影响评估非高风险或已上报管委会，符合硬规则",
    )


def _hr025_zbb_minimum_package(context: dict) -> RuleResult:
    minimum_package_deferred = context.get("minimum_package_deferred", False)
    if minimum_package_deferred:
        return RuleResult(
            rule_id="HR-025",
            rule_desc="零基预算最低包必须保障",
            passed=False,
            output="BLOCK",
            reasoning="最低级别决策包被暂缓，违反'零基预算最低包必须保障'硬规则",
        )
    return RuleResult(
        rule_id="HR-025",
        rule_desc="零基预算最低包必须保障",
        passed=True,
        output="PASS",
        reasoning="最低级别决策包未被暂缓，符合'零基预算最低包必须保障'硬规则",
    )


def _hr026_hcp_verify_before_payment(context: dict) -> RuleResult:
    hcp_verified = context.get("hcp_verified", False)
    has_payment = context.get("has_payment", False)
    if not hcp_verified and has_payment:
        return RuleResult(
            rule_id="HR-026",
            rule_desc="HCP付款前必须验证身份",
            passed=False,
            output="BLOCK",
            reasoning="HCP未完成身份验证即进行付款，违反'付款前必须验证HCP身份'硬规则",
        )
    return RuleResult(
        rule_id="HR-026",
        rule_desc="HCP付款前必须验证身份",
        passed=True,
        output="PASS",
        reasoning="HCP已完成身份验证或无付款操作，符合'付款前必须验证HCP身份'硬规则",
    )


def _hr027_hcp_annual_payment_limit(context: dict) -> RuleResult:
    annual_payment_total = context.get("annual_payment_total", 0)
    payment_limit = context.get("payment_limit", 0)
    if annual_payment_total > payment_limit:
        return RuleResult(
            rule_id="HR-027",
            rule_desc="HCP年度付款不得超过限额",
            passed=False,
            output="BLOCK",
            reasoning="HCP年度付款总额超过限额，违反'年度付款不得超过限额'硬规则",
        )
    return RuleResult(
        rule_id="HR-027",
        rule_desc="HCP年度付款不得超过限额",
        passed=True,
        output="PASS",
        reasoning="HCP年度付款总额在限额内，符合'年度付款不得超过限额'硬规则",
    )


def _hr028_hcp_interaction_record_complete(context: dict) -> RuleResult:
    interaction_record_complete = context.get("interaction_record_complete", False)
    if not interaction_record_complete:
        return RuleResult(
            rule_id="HR-028",
            rule_desc="HCP互动记录必须完整",
            passed=False,
            output="BLOCK",
            reasoning="HCP互动记录不完整，违反'互动记录必须完整'硬规则",
        )
    return RuleResult(
        rule_id="HR-028",
        rule_desc="HCP互动记录必须完整",
        passed=True,
        output="PASS",
        reasoning="HCP互动记录完整，符合'互动记录必须完整'硬规则",
    )


def _hr029_hcp_monthly_interaction_review(context: dict) -> RuleResult:
    monthly_interaction_count = context.get("monthly_interaction_count", 0)
    review_triggered = context.get("review_triggered", False)
    if monthly_interaction_count > 3 and not review_triggered:
        return RuleResult(
            rule_id="HR-029",
            rule_desc="HCP月度互动超过3次须审查",
            passed=False,
            output="BLOCK",
            reasoning="HCP月度互动超过3次但未触发审查，违反硬规则",
        )
    return RuleResult(
        rule_id="HR-029",
        rule_desc="HCP月度互动超过3次须审查",
        passed=True,
        output="PASS",
        reasoning="HCP月度互动未超过3次或已触发审查，符合硬规则",
    )


def _hr030_pipeline_go_nogo_decision(context: dict) -> RuleResult:
    has_go_nogo_decision = context.get("has_go_nogo_decision", False)
    if not has_go_nogo_decision:
        return RuleResult(
            rule_id="HR-030",
            rule_desc="管线推进必须经过Go/No-Go决策",
            passed=False,
            output="BLOCK",
            reasoning="管线阶段推进未经Go/No-Go决策，违反硬规则",
        )
    return RuleResult(
        rule_id="HR-030",
        rule_desc="管线推进必须经过Go/No-Go决策",
        passed=True,
        output="PASS",
        reasoning="管线阶段推进已经过Go/No-Go决策，符合硬规则",
    )


def _hr031_nogo_termination_eval(context: dict) -> RuleResult:
    go_nogo = context.get("go_nogo", "")
    termination_eval_started = context.get("termination_eval_started", False)
    if go_nogo == "No-Go" and not termination_eval_started:
        return RuleResult(
            rule_id="HR-031",
            rule_desc="No-Go决策须进入终止评估",
            passed=False,
            output="BLOCK",
            reasoning="No-Go决策后未进入终止评估流程，违反硬规则",
        )
    return RuleResult(
        rule_id="HR-031",
        rule_desc="No-Go决策须进入终止评估",
        passed=True,
        output="PASS",
        reasoning="非No-Go决策或已进入终止评估流程，符合硬规则",
    )


def _hr032_terminated_pipeline_budget_release(context: dict) -> RuleResult:
    pipeline_terminated = context.get("pipeline_terminated", False)
    budget_released = context.get("budget_released", False)
    if pipeline_terminated and not budget_released:
        return RuleResult(
            rule_id="HR-032",
            rule_desc="终止管线须释放剩余预算",
            passed=False,
            output="BLOCK",
            reasoning="管线已终止但未释放剩余预算，违反硬规则",
        )
    return RuleResult(
        rule_id="HR-032",
        rule_desc="终止管线须释放剩余预算",
        passed=True,
        output="PASS",
        reasoning="管线未终止或已释放剩余预算，符合硬规则",
    )


def _hr033_suspended_pipeline_budget_freeze(context: dict) -> RuleResult:
    pipeline_suspended = context.get("pipeline_suspended", False)
    execution_not_frozen = context.get("execution_not_frozen", False)
    if pipeline_suspended and execution_not_frozen:
        return RuleResult(
            rule_id="HR-033",
            rule_desc="暂停管线保留预算但冻结执行",
            passed=False,
            output="BLOCK",
            reasoning="管线已暂停但预算未冻结，违反'暂停管线保留预算但冻结执行'硬规则",
        )
    return RuleResult(
        rule_id="HR-033",
        rule_desc="暂停管线保留预算但冻结执行",
        passed=True,
        output="PASS",
        reasoning="管线未暂停或预算已冻结，符合'暂停管线保留预算但冻结执行'硬规则",
    )


def _hr034_clinical_trial_ethics(context: dict) -> RuleResult:
    has_ethics_approval = context.get("has_ethics_approval", False)
    is_clinical_trial = context.get("is_clinical_trial", False)
    if is_clinical_trial and not has_ethics_approval:
        return RuleResult(
            rule_id="HR-034",
            rule_desc="临床试验费用必须关联伦理批件",
            passed=False,
            output="BLOCK",
            reasoning="临床试验费用未关联伦理批件，违反'临床试验费用必须关联伦理批件'硬规则",
        )
    return RuleResult(
        rule_id="HR-034",
        rule_desc="临床试验费用必须关联伦理批件",
        passed=True,
        output="PASS",
        reasoning="临床试验费用已关联伦理批件或非临床试验费用，符合硬规则",
    )


def _hr035_academic_promotion_verification(context: dict) -> RuleResult:
    is_academic_promotion = context.get("is_academic_promotion", False)
    has_third_party_verification = context.get("has_third_party_verification", False)
    if is_academic_promotion and not has_third_party_verification:
        return RuleResult(
            rule_id="HR-035",
            rule_desc="学术推广费须第三方签到验证",
            passed=False,
            output="BLOCK",
            reasoning="学术推广费未通过第三方签到验证，违反'学术推广费须第三方签到验证'硬规则",
        )
    return RuleResult(
        rule_id="HR-035",
        rule_desc="学术推广费须第三方签到验证",
        passed=True,
        output="PASS",
        reasoning="学术推广费已通过第三方签到验证或非学术推广费用，符合硬规则",
    )


_HARD_RULES: dict[str, HardRuleDefinition] = {}

_HARD_RULE_CHECKS: dict[str, callable] = {
    "HR-001": _hr001_expense_must_have_budget,
    "HR-002": _hr002_writeoff_no_overage,
    "HR-003": _hr003_alert_not_overrun_permit,
    "HR-004": _hr004_a_class_approve_first,
    "HR-005": _hr005_dual_sign_closure,
    "HR-006": _hr006_tax_declaration_complete,
    "HR-007": _hr007_committee_decides_ratio,
    "HR-008": _hr008_cross_quadrant_committee_approval,
    "HR-009": _hr009_milestone_delay_report,
    "HR-010": _hr010_actual_not_exceed_milestone,
    "HR-011": _hr011_alert_expense_approval,
    "HR-012": _hr012_unclosed_alert_in_meeting,
    "HR-013": _hr013_alert_closure_dual_sign,
    "HR-014": _hr014_budget_grant_requires_strategic_intent,
    "HR-015": _hr015_expense_time_limit,
    "HR-016": _hr016_cashflow_forecast_horizon,
    "HR-017": _hr017_liquidity_gap_must_report,
    "HR-018": _hr018_profit_cash_gap_analysis,
    "HR-019": _hr019_scenario_pessimistic_required,
    "HR-020": _hr020_elastic_adjustment_limit,
    "HR-021": _hr021_stress_test_revenue_decline,
    "HR-022": _hr022_emergency_allocation_committee,
    "HR-023": _hr023_impact_assessment_five_domains,
    "HR-024": _hr024_high_risk_report_committee,
    "HR-025": _hr025_zbb_minimum_package,
    "HR-026": _hr026_hcp_verify_before_payment,
    "HR-027": _hr027_hcp_annual_payment_limit,
    "HR-028": _hr028_hcp_interaction_record_complete,
    "HR-029": _hr029_hcp_monthly_interaction_review,
    "HR-030": _hr030_pipeline_go_nogo_decision,
    "HR-031": _hr031_nogo_termination_eval,
    "HR-032": _hr032_terminated_pipeline_budget_release,
    "HR-033": _hr033_suspended_pipeline_budget_freeze,
    "HR-034": _hr034_clinical_trial_ethics,
    "HR-035": _hr035_academic_promotion_verification,
}


def _init_hard_rules() -> None:
    global _HARD_RULES
    if _HARD_RULES:
        return

    definitions = [
        HardRuleDefinition(rule_id="HR-001", name="支出必须有对应预算", description="任何支出必须挂载到有效的预算项目，无预算不得支出"),
        HardRuleDefinition(rule_id="HR-002", name="预算核销不可超额", description="预算核销金额不得超过预算项目可用额度"),
        HardRuleDefinition(rule_id="HR-003", name="预警触发≠超支许可", description="预警触发不代表超支被许可，预警后仍需限制支出"),
        HardRuleDefinition(rule_id="HR-004", name="先批后用(A类预算)", description="A类预算必须先审批后使用，不得先支后批"),
        HardRuleDefinition(rule_id="HR-005", name="双签闭环(业务+财经BP)", description="预警响应和费用审批须经业务BP和财经BP双签确认"),
        HardRuleDefinition(rule_id="HR-006", name="税务申报数据必须完整准确", description="税务申报数据必须完整且准确，不得遗漏或错误"),
        HardRuleDefinition(rule_id="HR-007", name="战略预算组合比例由管委会决定", description="战略预算的组合比例必须由管委会决定，其他角色无权调整"),
        HardRuleDefinition(rule_id="HR-008", name="跨象限调拨须管委会批准", description="跨象限的预算调拨必须经管委会批准，不得自行调拨"),
        HardRuleDefinition(rule_id="HR-009", name="里程碑延期未完成报备不得自行推进下一里程碑", description="里程碑延期且未完成报备的，不得自行推进下一里程碑"),
        HardRuleDefinition(rule_id="HR-010", name="实际支出不得超出里程碑计划金额", description="实际支出金额不得超过里程碑计划金额"),
        HardRuleDefinition(rule_id="HR-011", name="里程碑预警触发后新增支出须经对应级别审批", description="里程碑预警触发后，新增支出必须经过对应级别的审批"),
        HardRuleDefinition(rule_id="HR-012", name="未闭环预警须在经营分析会中专项汇报", description="未闭环的预警必须在经营分析会中进行专项汇报"),
        HardRuleDefinition(rule_id="HR-013", name="预警闭环必须双签", description="预警闭环必须由业务单元提交整改方案(≥20字)和财经BP确认意见，且两者不能为同一人"),
        HardRuleDefinition(rule_id="HR-014", name="预算授予时战略意图维度不能为空", description="预算项目授予或执行时，战略意图L1(三大战略方向)和L2(产品线×区域)必须填写"),
        HardRuleDefinition(rule_id="HR-015", name="报销时效限制", description="费用发生日期距今不超过3个月；跨年度费用须在次年3月31日前报销"),
        HardRuleDefinition(rule_id="HR-016", name="现金流预测必须覆盖至少3个月", description="现金流预测的覆盖期限不得少于3个月"),
        HardRuleDefinition(rule_id="HR-017", name="流动性缺口必须上报", description="存在流动性缺口时必须进行上报"),
        HardRuleDefinition(rule_id="HR-018", name="利润现金流差异超过20%须专项分析", description="利润与现金流差异超过20%时必须进行专项分析"),
        HardRuleDefinition(rule_id="HR-019", name="情景规划必须包含悲观情景", description="情景规划中必须包含悲观情景"),
        HardRuleDefinition(rule_id="HR-020", name="弹性调整幅度不得超过30%", description="弹性调整幅度不得超过30%"),
        HardRuleDefinition(rule_id="HR-021", name="压力测试必须包含收入下降30%情景", description="压力测试必须包含收入下降30%的情景"),
        HardRuleDefinition(rule_id="HR-022", name="紧急调拨须经管委会批准", description="紧急调拨必须经管委会批准"),
        HardRuleDefinition(rule_id="HR-023", name="影响评估必须覆盖5个域", description="影响评估必须覆盖预算/费用/预警/现金流/战略全部5个域"),
        HardRuleDefinition(rule_id="HR-024", name="高风险影响须上报管委会", description="影响评估结果为高风险时必须上报管委会"),
        HardRuleDefinition(rule_id="HR-025", name="零基预算最低包必须保障", description="零基预算中最低级别决策包不得被暂缓"),
        HardRuleDefinition(rule_id="HR-026", name="HCP付款前必须验证身份", description="向HCP付款前必须完成身份验证"),
        HardRuleDefinition(rule_id="HR-027", name="HCP年度付款不得超过限额", description="HCP年度付款总额不得超过限额"),
        HardRuleDefinition(rule_id="HR-028", name="HCP互动记录必须完整", description="HCP互动记录必须完整"),
        HardRuleDefinition(rule_id="HR-029", name="HCP月度互动超过3次须审查", description="HCP月度互动超过3次时必须触发审查"),
        HardRuleDefinition(rule_id="HR-030", name="管线推进必须经过Go/No-Go决策", description="管线阶段推进必须经过Go/No-Go决策"),
        HardRuleDefinition(rule_id="HR-031", name="No-Go决策须进入终止评估", description="No-Go决策后必须进入终止评估流程"),
        HardRuleDefinition(rule_id="HR-032", name="终止管线须释放剩余预算", description="管线终止后必须释放剩余预算"),
        HardRuleDefinition(rule_id="HR-033", name="暂停管线保留预算但冻结执行", description="管线暂停后保留预算但必须冻结执行"),
        HardRuleDefinition(rule_id="HR-034", name="临床试验费用关联伦理批件", description="临床试验费用必须关联伦理批件，无批件不得付款"),
        HardRuleDefinition(rule_id="HR-035", name="学术推广费第三方验证", description="学术推广费须通过第三方签到验证，确保活动真实性"),
    ]

    _HARD_RULES = {r.rule_id: r for r in definitions}


class HardRuleEngine:
    def __init__(self) -> None:
        _init_hard_rules()

    def execute(self, rule_id: str, context: dict) -> RuleResult:
        check_fn = _HARD_RULE_CHECKS.get(rule_id)
        if check_fn is None:
            return RuleResult(
                rule_id=rule_id,
                rule_desc="未知硬规则",
                passed=False,
                output="BLOCK",
                reasoning=f"硬规则{rule_id}不存在",
            )
        return check_fn(context)

    def execute_all(self, context: dict) -> list[RuleResult]:
        _init_hard_rules()
        results = []
        for rule_id in _HARD_RULES:
            results.append(self.execute(rule_id, context))
        return results

    def check_any_blocked(self, results: list[RuleResult]) -> bool:
        return any(r.output == "BLOCK" for r in results)

    def get_rule(self, rule_id: str) -> HardRuleDefinition | None:
        _init_hard_rules()
        return _HARD_RULES.get(rule_id)

    def get_all_rules(self) -> dict[str, HardRuleDefinition]:
        _init_hard_rules()
        return _HARD_RULES.copy()
