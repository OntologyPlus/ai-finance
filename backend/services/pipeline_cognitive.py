"""
管线认知分析（Pipeline Cognitive Analysis）
========================================

方法论基础：
- 风险调整后净现值（rNPV）：上市概率 × 峰值销售 × 净利率 - 累计投入
- 阶段成功率模型：行业基准（发现→上市 ~10%）
- 5 因素 Go/No-Go 决策矩阵（科学/临床/竞争/商业/财务）

提供 3 大认知能力：
1. 价值评估（Value Evaluation）：预期价值 = 上市概率 × 峰值销售 × 净利率
2. Go/No-Go 决策面板：5 关键因素 + AI 综合判断
3. 管线组合视图：按象限分桶（明星/问号/金牛/瘦狗）
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple


# 行业阶段成功率（药企研发基准）
STAGE_SUCCESS_RATE: Dict[str, float] = {
    "发现": 1.00,
    "临床前": 0.70,
    "I期临床": 0.50,
    "II期临床": 0.30,
    "III期临床": 0.20,
    "注册申报": 0.85,
    "上市": 1.00,
}

# 行业平均峰值销售（万元，按适应症分）
INDICATION_PEAK_SALES: Dict[str, float] = {
    "肿瘤": 50000.0,
    "心血管": 30000.0,
    "糖尿病": 35000.0,
    "免疫": 40000.0,
    "罕见病": 20000.0,
    "抗感染": 25000.0,
    "其他": 15000.0,
}

DEFAULT_PEAK_SALES = 20000.0
DEFAULT_NET_MARGIN = 0.20  # 20%


def _to_float(x: Any, default: float = 0.0) -> float:
    if x is None:
        return default
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


# ── 1. 价值评估 ──────────────────────────────────────────

@dataclass
class PipelineValue:
    pipeline_id: str
    name: str
    indication: str
    current_stage: str
    stage_probability: float          # 当前阶段成功率
    cumulative_probability: float     # 当前阶段→上市 累计成功率
    peak_sales: float                 # 预期峰值销售（万元）
    net_margin: float                 # 净利率
    expected_value: float             # 风险调整后预期价值
    total_invested: float             # 累计已投入
    risk_adjusted_npv: float          # rNPV（粗估）
    value_tier: str                   # 价值分层：S/A/B/C
    recommendation: str               # 价值建议

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _classify_indication(indication: Optional[str]) -> Tuple[str, float]:
    """根据适应症归类，返回 (类别, 峰值销售基准)"""
    if not indication:
        return "其他", DEFAULT_PEAK_SALES
    ind_lower = str(indication).lower()
    for key, peak in INDICATION_PEAK_SALES.items():
        if key in indication or key.lower() in ind_lower:
            return key, peak
    return "其他", DEFAULT_PEAK_SALES


def _value_tier(expected_value: float) -> str:
    if expected_value >= 8000:
        return "S"
    elif expected_value >= 4000:
        return "A"
    elif expected_value >= 1500:
        return "B"
    return "C"


def evaluate_pipeline_value(
    pipeline: Any,
    all_pipelines: Optional[List[Any]] = None,
) -> PipelineValue:
    """评估单个管线的预期价值（rNPV 思路）。

    计算公式：
    - 累计成功率：从当前阶段到上市的连乘概率
    - 峰值销售：基于适应症行业基准（万元）
    - 净利率：默认 20%
    - 预期价值 = 累计成功率 × 峰值销售 × 净利率
    - rNPV = 预期价值 - 累计已投入
    """
    pipeline_id = getattr(pipeline, "pipeline_id", "?")
    name = getattr(pipeline, "name", "?")
    indication = getattr(pipeline, "indication", None) or "其他"
    current_stage = getattr(pipeline, "current_stage", "发现")
    total_budget = _to_float(getattr(pipeline, "total_budget", None))
    consumed_budget = _to_float(getattr(pipeline, "consumed_budget", None))

    # 1) 累计成功率（当前阶段→上市的连乘）
    stage_idx = PIPELINE_STAGES_LIST.index(current_stage) if current_stage in PIPELINE_STAGES_LIST else 0
    cumulative_prob = 1.0
    for s in PIPELINE_STAGES_LIST[stage_idx:]:
        cumulative_prob *= STAGE_SUCCESS_RATE.get(s, 0.5)
    stage_prob = STAGE_SUCCESS_RATE.get(current_stage, 0.5)

    # 2) 峰值销售（适应症基准 + 预算规模调整）
    cat, peak_base = _classify_indication(indication)
    # 预算 > 1 亿的管线给予 1.2x 系数
    scale_factor = 1.2 if total_budget >= 10000 else 1.0
    peak_sales = peak_base * scale_factor

    # 3) 净利率
    net_margin = DEFAULT_NET_MARGIN

    # 4) 预期价值
    expected_value = cumulative_prob * peak_sales * net_margin

    # 5) rNPV（粗估：预期价值 - 累计投入）
    risk_adjusted_npv = expected_value - consumed_budget

    # 6) 分层
    tier = _value_tier(expected_value)

    # 7) 建议
    if risk_adjusted_npv < 0 and consumed_budget > 0:
        rec = f"已投入 ¥{consumed_budget:.0f}万但 rNPV 为负，需重新评估战略价值或终止"
    elif cumulative_prob < 0.10:
        rec = f"上市概率仅 {cumulative_prob*100:.0f}%，建议 No-Go 或大幅缩减投入"
    elif expected_value >= 8000:
        rec = f"S 级高价值管线，建议加大资源倾斜，加速推进"
    elif expected_value >= 4000:
        rec = f"A 级中等价值管线，建议维持当前推进节奏"
    elif expected_value >= 1500:
        rec = f"B 级低价值管线，建议阶段性评估商业前景"
    else:
        rec = f"C 级极低价值管线，建议进入终止评估流程"

    return PipelineValue(
        pipeline_id=pipeline_id,
        name=name,
        indication=indication,
        current_stage=current_stage,
        stage_probability=round(stage_prob, 3),
        cumulative_probability=round(cumulative_prob, 3),
        peak_sales=round(peak_sales, 1),
        net_margin=net_margin,
        expected_value=round(expected_value, 1),
        total_invested=round(consumed_budget, 1),
        risk_adjusted_npv=round(risk_adjusted_npv, 1),
        value_tier=tier,
        recommendation=rec,
    )


# ── 2. 管线阶段（与 engine 同步） ──────────────────────────

PIPELINE_STAGES_LIST = ["发现", "临床前", "I期临床", "II期临床", "III期临床", "注册申报", "上市"]


def compute_value_matrix(
    pipelines: List[Any],
) -> Dict[str, Any]:
    """批量评估所有管线，生成价值矩阵数据。"""
    if not pipelines:
        return {
            "pipelines": [],
            "summary": {
                "total_pipelines": 0,
                "tier_counts": {"S": 0, "A": 0, "B": 0, "C": 0},
                "total_expected_value": 0.0,
                "total_risk_adjusted_npv": 0.0,
                "avg_expected_value": 0.0,
                "avg_cumulative_probability": 0.0,
                "message": "无管线数据",
            },
            "quadrants": {"明星": [], "问号": [], "金牛": [], "瘦狗": []},
        }

    values = [evaluate_pipeline_value(p, pipelines) for p in pipelines]

    tier_counts: Dict[str, int] = {"S": 0, "A": 0, "B": 0, "C": 0}
    total_expected = 0.0
    total_npv = 0.0
    for v in values:
        tier_counts[v.value_tier] = tier_counts.get(v.value_tier, 0) + 1
        total_expected += v.expected_value
        total_npv += v.risk_adjusted_npv

    # BCG 象限分类
    avg_value = total_expected / len(values) if values else 0
    avg_prob = sum(v.cumulative_probability for v in values) / len(values) if values else 0
    quadrants = {"明星": [], "问号": [], "金牛": [], "瘦狗": []}
    for v in values:
        if v.cumulative_probability >= avg_prob and v.expected_value >= avg_value:
            quadrants["明星"].append(v.pipeline_id)
        elif v.cumulative_probability < avg_prob and v.expected_value >= avg_value:
            quadrants["问号"].append(v.pipeline_id)
        elif v.cumulative_probability >= avg_prob and v.expected_value < avg_value:
            quadrants["金牛"].append(v.pipeline_id)
        else:
            quadrants["瘦狗"].append(v.pipeline_id)

    return {
        "pipelines": [v.to_dict() for v in values],
        "summary": {
            "total_pipelines": len(values),
            "tier_counts": tier_counts,
            "total_expected_value": round(total_expected, 1),
            "total_risk_adjusted_npv": round(total_npv, 1),
            "avg_expected_value": round(avg_value, 1),
            "avg_cumulative_probability": round(avg_prob, 3),
        },
        "quadrants": quadrants,
    }


# ── 3. Go/No-Go 决策 ──────────────────────────────────────

@dataclass
class DecisionFactor:
    name: str
    score: float                # 0-100
    weight: float               # 0-1
    weighted: float             # score * weight
    assessment: str             # 高/中/低 评估
    detail: str                 # 详细说明

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GoNoGoDecision:
    pipeline_id: str
    name: str
    current_stage: str
    total_score: float
    decision: str               # Go / No-Go / Conditional
    confidence: str             # high / medium / low
    factors: List[DecisionFactor]
    risk_factors: List[str]     # 关键风险点
    enablers: List[str]         # 关键推动因素
    next_action: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pipeline_id": self.pipeline_id,
            "name": self.name,
            "current_stage": self.current_stage,
            "total_score": round(self.total_score, 1),
            "decision": self.decision,
            "confidence": self.confidence,
            "factors": [f.to_dict() for f in self.factors],
            "risk_factors": self.risk_factors,
            "enablers": self.enablers,
            "next_action": self.next_action,
        }


def evaluate_go_nogo(
    pipeline: Any,
    projects: Optional[List[Any]] = None,
    trials: Optional[List[Any]] = None,
) -> GoNoGoDecision:
    """基于 5 关键因素做 Go/No-Go 决策。

    5 因素（权重）：
    1. 科学性 (20%)：阶段越靠后、科学确定性越高
    2. 临床数据 (25%)：根据项目/试验完成度
    3. 竞争格局 (15%)：根据管线价值分层
    4. 商业前景 (20%)：根据 rNPV
    5. 财务可行性 (20%)：根据预算消耗率

    决策阈值：
    - 总分 >= 70: Go
    - 50 <= 总分 < 70: Conditional（有条件推进）
    - 总分 < 50: No-Go
    """
    pipeline_id = getattr(pipeline, "pipeline_id", "?")
    name = getattr(pipeline, "name", "?")
    current_stage = getattr(pipeline, "current_stage", "发现")
    total_budget = _to_float(getattr(pipeline, "total_budget", None), 1.0)
    consumed_budget = _to_float(getattr(pipeline, "consumed_budget", None))
    consumption_rate = (consumed_budget / total_budget * 100) if total_budget > 0 else 0

    # 1) 科学性：阶段越后确定性越高
    if current_stage in PIPELINE_STAGES_LIST:
        stage_idx = PIPELINE_STAGES_LIST.index(current_stage)
        science_score = min(100, (stage_idx + 1) / len(PIPELINE_STAGES_LIST) * 100)
    else:
        science_score = 30
    science_assessment = "高" if science_score >= 70 else "中" if science_score >= 40 else "低"

    # 2) 临床数据：根据项目+试验完成度
    n_projects = len(projects) if projects else 0
    n_trials = len(trials) if trials else 0
    completed_projects = 0
    if projects:
        for p in projects:
            if getattr(p, "status", "") in ("已完成", "已结题", "已终止"):
                completed_projects += 1
    completed_trials = 0
    if trials:
        for t in trials:
            if getattr(t, "status", "") in ("已完成", "已结题", "已上市"):
                completed_trials += 1
    project_completion = (completed_projects / n_projects * 100) if n_projects > 0 else 50
    trial_completion = (completed_trials / n_trials * 100) if n_trials > 0 else 50
    clinical_score = (project_completion * 0.5 + trial_completion * 0.5)
    clinical_assessment = "高" if clinical_score >= 70 else "中" if clinical_score >= 40 else "低"

    # 3) 竞争格局：基于管线数量（管线多→竞争激烈）
    competition_score = 50  # 默认中
    competition_assessment = "中"
    if n_projects >= 5:
        competition_score = 30
        competition_assessment = "低"
    elif n_projects >= 2:
        competition_score = 60
        competition_assessment = "中"
    elif n_projects == 1:
        competition_score = 80
        competition_assessment = "高"
    else:
        competition_score = 50
        competition_assessment = "中"

    # 4) 商业前景：基于 rNPV
    val = evaluate_pipeline_value(pipeline)
    if val.risk_adjusted_npv >= 5000:
        commercial_score = 90
        commercial_assessment = "高"
    elif val.risk_adjusted_npv >= 0:
        commercial_score = 70
        commercial_assessment = "高"
    elif val.risk_adjusted_npv >= -2000:
        commercial_score = 50
        commercial_assessment = "中"
    else:
        commercial_score = 30
        commercial_assessment = "低"

    # 5) 财务可行性：消耗率
    if consumption_rate > 100:
        finance_score = 20
        finance_assessment = "低"
    elif consumption_rate > 80:
        finance_score = 40
        finance_assessment = "中"
    elif consumption_rate > 50:
        finance_score = 70
        finance_assessment = "高"
    else:
        finance_score = 85
        finance_assessment = "高"

    factors = [
        DecisionFactor("科学性", science_score, 0.20, science_score * 0.20, science_assessment,
                       f"当前阶段 {current_stage}，行业成功率 {STAGE_SUCCESS_RATE.get(current_stage, 0.5)*100:.0f}%"),
        DecisionFactor("临床数据", clinical_score, 0.25, clinical_score * 0.25, clinical_assessment,
                       f"{n_projects} 个项目（{completed_projects} 完成）、{n_trials} 个试验（{completed_trials} 完成）"),
        DecisionFactor("竞争格局", competition_score, 0.15, competition_score * 0.15, competition_assessment,
                       f"关联项目数 {n_projects}，竞争密度 {'激烈' if n_projects >= 5 else '适中' if n_projects >= 2 else '宽松'}"),
        DecisionFactor("商业前景", commercial_score, 0.20, commercial_score * 0.20, commercial_assessment,
                       f"rNPV {val.risk_adjusted_npv:.0f}万，价值分层 {val.value_tier}"),
        DecisionFactor("财务可行性", finance_score, 0.20, finance_score * 0.20, finance_assessment,
                       f"预算消耗率 {consumption_rate:.1f}%，累计投入 {consumed_budget:.0f}万"),
    ]

    total_score = sum(f.weighted for f in factors)

    if total_score >= 70:
        decision = "Go"
        confidence = "high"
        next_action = "推进至下一阶段，加速资源调配"
    elif total_score >= 50:
        decision = "Conditional"
        confidence = "medium"
        next_action = "有条件推进，需补强弱项因素（详见风险点）"
    else:
        decision = "No-Go"
        confidence = "low"
        next_action = "建议终止或暂停，启动终止评估流程（HR-031）"

    # 风险点（按分数从低到高）
    risk_factors = [f"{f.name}：{f.assessment}（{f.score:.0f}/100）。{f.detail}" for f in factors if f.score < 60]
    # 推动因素
    enablers = [f"{f.name}：{f.assessment}（{f.score:.0f}/100）。{f.detail}" for f in factors if f.score >= 70]

    return GoNoGoDecision(
        pipeline_id=pipeline_id,
        name=name,
        current_stage=current_stage,
        total_score=round(total_score, 1),
        decision=decision,
        confidence=confidence,
        factors=factors,
        risk_factors=risk_factors,
        enablers=enablers,
        next_action=next_action,
    )
