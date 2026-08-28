from typing import Any, Optional

from pydantic import BaseModel, Field

from ontology.rules.hard_rules import RuleResult


class ReasoningRuleDefinition(BaseModel):
    rule_id: str
    name: str
    description: str
    learning_source: str


_REASONING_RULES: dict[str, ReasoningRuleDefinition] = {}

_CONFIDENCE_STORE: dict[str, float] = {}

_LEARNED_PATTERNS: dict[str, dict[str, Any]] = {}


def _init_reasoning_rules() -> None:
    global _REASONING_RULES, _CONFIDENCE_STORE
    if _REASONING_RULES:
        return

    definitions = [
        ReasoningRuleDefinition(
            rule_id="RR-001",
            name="差旅费与项目数量正相关",
            description="差旅费支出与项目数量呈正相关关系，项目数量增加时差旅费应相应增加，偏差过大需关注",
            learning_source="历史差旅费与项目数量的回归分析",
        ),
        ReasoningRuleDefinition(
            rule_id="RR-002",
            name="招待费与渠道拓展阶段关联",
            description="招待费支出与渠道拓展阶段强相关，渠道拓展初期招待费占比偏高，成熟期应逐步下降",
            learning_source="历史招待费与渠道拓展阶段的关联分析",
        ),
        ReasoningRuleDefinition(
            rule_id="RR-003",
            name="培训费季节性波动模式",
            description="培训费支出呈现季节性波动，Q1和Q3为培训高峰期，Q2和Q4相对较低，偏差超出季节模式需关注",
            learning_source="历史培训费月度/季度数据的时间序列分析",
        ),
        ReasoningRuleDefinition(
            rule_id="RR-004",
            name="预算执行率与剩余时间非线性关系",
            description="预算执行率与剩余时间呈非线性关系，前低后高为正常模式，前高后低可能存在突击花钱风险",
            learning_source="历史预算执行率与时间进度的S曲线拟合分析",
        ),
        ReasoningRuleDefinition(
            rule_id="RR-005",
            name="研发里程碑延期对后续节点传导效应",
            description="研发项目里程碑延期会对后续里程碑产生传导效应，延期天数呈放大趋势，需提前预警和调整计划",
            learning_source="历史研发项目里程碑延期数据的传导效应分析",
        ),
    ]

    _REASONING_RULES = {r.rule_id: r for r in definitions}
    _CONFIDENCE_STORE = {
        "RR-001": 0.7,
        "RR-002": 0.65,
        "RR-003": 0.75,
        "RR-004": 0.7,
        "RR-005": 0.6,
    }


def _rr001_travel_project_correlation(context: dict, llm_client=None) -> RuleResult:
    confidence = _CONFIDENCE_STORE.get("RR-001", 0.7)
    travel_expense = context.get("travel_expense", 0)
    project_count = context.get("project_count", 0)
    avg_travel_per_project = context.get("avg_travel_per_project")
    learned_pattern = _LEARNED_PATTERNS.get("RR-001", {})

    if avg_travel_per_project is None and learned_pattern:
        avg_travel_per_project = learned_pattern.get("avg_travel_per_project", 0)

    if avg_travel_per_project and avg_travel_per_project > 0 and project_count > 0:
        expected_travel = avg_travel_per_project * project_count
        deviation_ratio = abs(travel_expense - expected_travel) / expected_travel if expected_travel > 0 else 0
        if deviation_ratio > 0.3:
            return RuleResult(
                rule_id="RR-001",
                rule_type="reasoning",
                rule_desc="差旅费与项目数量正相关",
                passed=True,
                output="PASS",
                confidence=confidence,
                reasoning=f"差旅费{travel_expense}元与{project_count}个项目的预期差旅费{expected_travel:.0f}元偏差{deviation_ratio:.1%}，超过30%偏差阈值，建议关注差旅费合理性",
            )
        return RuleResult(
            rule_id="RR-001",
            rule_type="reasoning",
            rule_desc="差旅费与项目数量正相关",
            passed=True,
            output="PASS",
            confidence=confidence,
            reasoning=f"差旅费{travel_expense}元与{project_count}个项目的预期差旅费{expected_travel:.0f}元偏差{deviation_ratio:.1%}，在合理范围内",
        )

    return RuleResult(
        rule_id="RR-001",
        rule_type="reasoning",
        rule_desc="差旅费与项目数量正相关",
        passed=True,
        output="PASS",
        confidence=confidence * 0.5,
        reasoning="缺少历史基准数据或项目数量为0，无法进行差旅费与项目数量的相关性判断，建议补充历史数据",
    )


def _rr002_entertainment_channel_phase(context: dict, llm_client=None) -> RuleResult:
    confidence = _CONFIDENCE_STORE.get("RR-002", 0.65)
    entertainment_expense = context.get("entertainment_expense", 0)
    channel_phase = context.get("channel_phase", "unknown")
    total_expense = context.get("total_expense", 1)
    entertainment_ratio = entertainment_expense / total_expense if total_expense > 0 else 0
    learned_pattern = _LEARNED_PATTERNS.get("RR-002", {})
    phase_thresholds = learned_pattern.get("phase_thresholds", {
        "initial": 0.15,
        "growth": 0.10,
        "mature": 0.06,
        "decline": 0.04,
    })

    threshold = phase_thresholds.get(channel_phase, 0.10)
    if entertainment_ratio > threshold:
        return RuleResult(
            rule_id="RR-002",
            rule_type="reasoning",
            rule_desc="招待费与渠道拓展阶段关联",
            passed=True,
            output="PASS",
            confidence=confidence,
            reasoning=f"招待费占比{entertainment_ratio:.1%}超过{channel_phase}阶段阈值{threshold:.1%}，建议关注招待费合理性",
        )
    return RuleResult(
        rule_id="RR-002",
        rule_type="reasoning",
        rule_desc="招待费与渠道拓展阶段关联",
        passed=True,
        output="PASS",
        confidence=confidence,
        reasoning=f"招待费占比{entertainment_ratio:.1%}在{channel_phase}阶段阈值{threshold:.1%}范围内，正常",
    )


def _rr003_training_seasonal(context: dict, llm_client=None) -> RuleResult:
    confidence = _CONFIDENCE_STORE.get("RR-003", 0.75)
    training_expense = context.get("training_expense", 0)
    quarter = context.get("quarter", "Q1")
    annual_training_budget = context.get("annual_training_budget", 0)
    learned_pattern = _LEARNED_PATTERNS.get("RR-003", {})
    seasonal_weights = learned_pattern.get("seasonal_weights", {
        "Q1": 0.35,
        "Q2": 0.15,
        "Q3": 0.35,
        "Q4": 0.15,
    })

    expected_ratio = seasonal_weights.get(quarter, 0.25)
    expected_expense = annual_training_budget * expected_ratio if annual_training_budget > 0 else 0
    if expected_expense > 0:
        deviation = abs(training_expense - expected_expense) / expected_expense
        if deviation > 0.5:
            return RuleResult(
                rule_id="RR-003",
                rule_type="reasoning",
                rule_desc="培训费季节性波动模式",
                passed=True,
                output="PASS",
                confidence=confidence,
                reasoning=f"{quarter}培训费{training_expense}元与季节性预期{expected_expense:.0f}元偏差{deviation:.1%}，超过50%偏差阈值，建议关注培训费合理性",
            )
        return RuleResult(
            rule_id="RR-003",
            rule_type="reasoning",
            rule_desc="培训费季节性波动模式",
            passed=True,
            output="PASS",
            confidence=confidence,
            reasoning=f"{quarter}培训费{training_expense}元与季节性预期{expected_expense:.0f}元偏差{deviation:.1%}，在合理范围内",
        )

    return RuleResult(
        rule_id="RR-003",
        rule_type="reasoning",
        rule_desc="培训费季节性波动模式",
        passed=True,
        output="PASS",
        confidence=confidence * 0.5,
        reasoning="缺少年度培训预算数据，无法进行季节性波动判断",
    )


def _rr004_execution_time_nonlinear(context: dict, llm_client=None) -> RuleResult:
    confidence = _CONFIDENCE_STORE.get("RR-004", 0.7)
    execution_rate = context.get("execution_rate", 0)
    time_progress = context.get("time_progress", 0)
    learned_pattern = _LEARNED_PATTERNS.get("RR-004", {})
    s_curve_params = learned_pattern.get("s_curve_params", {
        "early_threshold": 0.3,
        "late_threshold": 0.7,
    })

    early_threshold = s_curve_params["early_threshold"]
    late_threshold = s_curve_params["late_threshold"]

    if time_progress < early_threshold and execution_rate > time_progress * 2:
        return RuleResult(
            rule_id="RR-004",
            rule_type="reasoning",
            rule_desc="预算执行率与剩余时间非线性关系",
            passed=True,
            output="PASS",
            confidence=confidence,
            reasoning=f"时间进度{time_progress:.0%}时执行率已达{execution_rate:.0%}，前期执行过快，可能存在预算使用不合理风险",
        )
    if time_progress > late_threshold and execution_rate < time_progress * 0.6:
        return RuleResult(
            rule_id="RR-004",
            rule_type="reasoning",
            rule_desc="预算执行率与剩余时间非线性关系",
            passed=True,
            output="PASS",
            confidence=confidence,
            reasoning=f"时间进度{time_progress:.0%}时执行率仅{execution_rate:.0%}，后期可能存在突击花钱风险",
        )
    return RuleResult(
        rule_id="RR-004",
        rule_type="reasoning",
        rule_desc="预算执行率与剩余时间非线性关系",
        passed=True,
        output="PASS",
        confidence=confidence,
        reasoning=f"时间进度{time_progress:.0%}，执行率{execution_rate:.0%}，执行节奏正常",
    )


def _rr005_milestone_delay_propagation(context: dict, llm_client=None) -> RuleResult:
    confidence = _CONFIDENCE_STORE.get("RR-005", 0.6)
    current_delay_days = context.get("current_delay_days", 0)
    remaining_milestones = context.get("remaining_milestones", 0)
    learned_pattern = _LEARNED_PATTERNS.get("RR-005", {})
    amplification_factor = learned_pattern.get("amplification_factor", 1.5)

    if current_delay_days > 0 and remaining_milestones > 0:
        estimated_total_delay = 0
        delay = current_delay_days
        for i in range(remaining_milestones):
            estimated_total_delay += delay
            delay = int(delay * amplification_factor)

        return RuleResult(
            rule_id="RR-005",
            rule_type="reasoning",
            rule_desc="研发里程碑延期对后续节点传导效应",
            passed=True,
            output="PASS",
            confidence=confidence,
            reasoning=f"当前里程碑延期{current_delay_days}天，剩余{remaining_milestones}个里程碑，按传导放大系数{amplification_factor}估算累计延期约{estimated_total_delay}天，建议调整后续里程碑计划",
        )

    return RuleResult(
        rule_id="RR-005",
        rule_type="reasoning",
        rule_desc="研发里程碑延期对后续节点传导效应",
        passed=True,
        output="PASS",
        confidence=confidence,
        reasoning="当前里程碑未延期或无后续里程碑，无需进行传导效应分析",
    )


_REASONING_RULE_CHECKS: dict[str, callable] = {
    "RR-001": _rr001_travel_project_correlation,
    "RR-002": _rr002_entertainment_channel_phase,
    "RR-003": _rr003_training_seasonal,
    "RR-004": _rr004_execution_time_nonlinear,
    "RR-005": _rr005_milestone_delay_propagation,
}


class ReasoningRuleEngine:
    def __init__(self) -> None:
        _init_reasoning_rules()

    def execute(self, rule_id: str, context: dict, llm_client=None) -> RuleResult:
        check_fn = _REASONING_RULE_CHECKS.get(rule_id)
        if check_fn is None:
            return RuleResult(
                rule_id=rule_id,
                rule_type="reasoning",
                rule_desc="未知推理规则",
                passed=True,
                output="PASS",
                confidence=0.0,
                reasoning=f"推理规则{rule_id}不存在",
            )
        return check_fn(context, llm_client)

    def learn_from_data(self, rule_id: str, historical_data: dict) -> None:
        _init_reasoning_rules()
        if rule_id not in _REASONING_RULES:
            return
        _LEARNED_PATTERNS[rule_id] = historical_data
        if rule_id == "RR-001" and "avg_travel_per_project" in historical_data:
            _CONFIDENCE_STORE[rule_id] = min(0.9, _CONFIDENCE_STORE.get(rule_id, 0.7) + 0.05)
        elif rule_id == "RR-002" and "phase_thresholds" in historical_data:
            _CONFIDENCE_STORE[rule_id] = min(0.9, _CONFIDENCE_STORE.get(rule_id, 0.65) + 0.05)
        elif rule_id == "RR-003" and "seasonal_weights" in historical_data:
            _CONFIDENCE_STORE[rule_id] = min(0.9, _CONFIDENCE_STORE.get(rule_id, 0.75) + 0.05)
        elif rule_id == "RR-004" and "s_curve_params" in historical_data:
            _CONFIDENCE_STORE[rule_id] = min(0.9, _CONFIDENCE_STORE.get(rule_id, 0.7) + 0.05)
        elif rule_id == "RR-005" and "amplification_factor" in historical_data:
            _CONFIDENCE_STORE[rule_id] = min(0.9, _CONFIDENCE_STORE.get(rule_id, 0.6) + 0.05)

    def get_confidence(self, rule_id: str) -> float:
        _init_reasoning_rules()
        return _CONFIDENCE_STORE.get(rule_id, 0.0)

    def get_rule(self, rule_id: str) -> ReasoningRuleDefinition | None:
        _init_reasoning_rules()
        return _REASONING_RULES.get(rule_id)

    def get_all_rules(self) -> dict[str, ReasoningRuleDefinition]:
        _init_reasoning_rules()
        return _REASONING_RULES.copy()
