"""Pipeline Cognitive Engine unit tests (v9.0 E.3)."""
import sys
from pathlib import Path
from types import SimpleNamespace

# 注入 backend 根目录到 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.pipeline_cognitive import (
    evaluate_pipeline_value,
    compute_value_matrix,
    evaluate_go_nogo,
    PIPELINE_STAGES_LIST,
)


def make_pipeline(**kwargs):
    defaults = {
        "pipeline_id": "PL-001",
        "name": "X-2026创新药",
        "indication": "肿瘤",
        "current_stage": "II期临床",
        "total_budget": 5000.0,
        "consumed_budget": 1500.0,
        "status": "active",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def make_project(**kwargs):
    defaults = {
        "project_id": "PJ-001",
        "pipeline_id": "PL-001",
        "name": "II期临床研究",
        "status": "进行中",
        "execution_rate": 50.0,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def make_trial(**kwargs):
    defaults = {
        "trial_id": "CT-001",
        "pipeline_id": "PL-001",
        "name": "X-2026-PhaseII",
        "phase": "II期",
        "status": "进行中",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# ── 1. 价值评估 ──────────────────────────────────────────

def test_value_basic_fields():
    p = make_pipeline()
    val = evaluate_pipeline_value(p, [p])
    # 必备字段
    for k in [
        "pipeline_id", "name", "indication", "current_stage",
        "stage_probability", "cumulative_probability",
        "peak_sales", "net_margin",
        "expected_value", "total_invested", "risk_adjusted_npv",
        "value_tier", "recommendation",
    ]:
        assert hasattr(val, k), f"缺少字段 {k}"
    print(f"✓ test_value_basic_fields: {val.name} value_tier={val.value_tier}")


def test_value_stage_probability():
    """不同阶段的累计成功率应不同"""
    p_discovery = make_pipeline(current_stage="发现", total_budget=2000)
    p_phase2 = make_pipeline(current_stage="II期临床", total_budget=2000)
    p_launched = make_pipeline(current_stage="上市", total_budget=2000)

    v_discovery = evaluate_pipeline_value(p_discovery, [p_discovery])
    v_phase2 = evaluate_pipeline_value(p_phase2, [p_phase2])
    v_launched = evaluate_pipeline_value(p_launched, [p_launched])

    # 上市 = 1.0（已实现）
    assert v_launched.cumulative_probability == 1.0
    # 累计概率应严格大于 0
    assert v_discovery.cumulative_probability > 0
    assert v_phase2.cumulative_probability > 0
    # 较后阶段（II期）剩余步骤少，累计概率应高于早期（发现）
    # 发现：0.7*0.5*0.3*0.2*0.85 ≈ 0.018
    # II期：0.3*0.2*0.85 ≈ 0.051
    assert v_phase2.cumulative_probability > v_discovery.cumulative_probability
    print(f"✓ test_value_stage_probability: 发现={v_discovery.cumulative_probability:.3f}, II期={v_phase2.cumulative_probability:.3f}, 上市=1.000")


def test_value_tier_classification():
    """价值分层：S/A/B/C"""
    # 高价值：肿瘤 + 上市阶段
    p_high = make_pipeline(current_stage="上市", indication="肿瘤", total_budget=50000)
    v_high = evaluate_pipeline_value(p_high, [p_high])
    assert v_high.value_tier in ("S", "A", "B", "C")

    # 低价值：罕见病 + 发现阶段 + 小预算
    p_low = make_pipeline(current_stage="发现", indication="罕见病", total_budget=500)
    v_low = evaluate_pipeline_value(p_low, [p_low])

    # 高价值的预期价值应远高于低价值
    assert v_high.expected_value > v_low.expected_value
    print(f"✓ test_value_tier_classification: 高={v_high.expected_value}({v_high.value_tier}), 低={v_low.expected_value}({v_low.value_tier})")


def test_value_indication_classification():
    """适应症分类"""
    for ind in ["肿瘤", "心血管", "免疫", "罕见病", "未知领域"]:
        p = make_pipeline(indication=ind)
        val = evaluate_pipeline_value(p, [p])
        assert val.peak_sales > 0
    print(f"✓ test_value_indication_classification: 5 种适应症均可分类")


def test_value_recommendation():
    """价值建议应给出可操作内容"""
    p = make_pipeline(consumed_budget=10000, total_budget=5000)  # 超支
    val = evaluate_pipeline_value(p, [p])
    assert val.recommendation and len(val.recommendation) > 5
    print(f"✓ test_value_recommendation: {val.recommendation[:60]}")


# ── 2. 价值矩阵 ──────────────────────────────────────────

def test_matrix_empty():
    matrix = compute_value_matrix([])
    assert matrix["pipelines"] == []
    assert matrix["summary"]["total_pipelines"] == 0
    assert matrix["quadrants"]["明星"] == []
    print("✓ test_matrix_empty: 空数据返回空结构")


def test_matrix_basic():
    pipelines = [
        make_pipeline(pipeline_id="PL-001", name="A", indication="肿瘤", total_budget=20000, current_stage="III期临床"),
        make_pipeline(pipeline_id="PL-002", name="B", indication="罕见病", total_budget=1000, current_stage="发现"),
        make_pipeline(pipeline_id="PL-003", name="C", indication="心血管", total_budget=5000, current_stage="II期临床"),
    ]
    matrix = compute_value_matrix(pipelines)
    assert matrix["summary"]["total_pipelines"] == 3
    assert len(matrix["pipelines"]) == 3
    # 4 个象限都要有 key
    for q in ["明星", "问号", "金牛", "瘦狗"]:
        assert q in matrix["quadrants"]
    # S/A/B/C 分层计数
    assert sum(matrix["summary"]["tier_counts"].values()) == 3
    print(f"✓ test_matrix_basic: 3 管线，4 象限分布: {[(q, len(ids)) for q, ids in matrix['quadrants'].items()]}")


def test_matrix_bcg_quadrants():
    """BCG 象限分配：每个管线应落入 4 象限之一"""
    pipelines = [make_pipeline(pipeline_id=f"PL-{i:03d}", name=f"P{i}") for i in range(5)]
    matrix = compute_value_matrix(pipelines)
    total_in_quadrants = sum(len(ids) for ids in matrix["quadrants"].values())
    assert total_in_quadrants == 5
    print(f"✓ test_matrix_bcg_quadrants: 5 管线全部分配到象限")


# ── 3. Go/No-Go 决策 ──────────────────────────────────────

def test_gonogo_basic_fields():
    p = make_pipeline()
    proj = make_project()
    trial = make_trial()
    decision = evaluate_go_nogo(p, [proj], [trial])
    for k in [
        "pipeline_id", "name", "current_stage", "total_score",
        "decision", "confidence", "factors", "risk_factors", "enablers", "next_action",
    ]:
        assert k in decision.to_dict(), f"缺少字段 {k}"
    print(f"✓ test_gonogo_basic_fields: {decision.decision} ({decision.total_score:.1f})")


def test_gonogo_5_factors():
    """5 因素评估"""
    p = make_pipeline()
    decision = evaluate_go_nogo(p, [], [])
    factors = decision.factors
    assert len(factors) == 5
    factor_names = [f.name for f in factors]
    assert "科学性" in factor_names
    assert "临床数据" in factor_names
    assert "竞争格局" in factor_names
    assert "商业前景" in factor_names
    assert "财务可行性" in factor_names
    # 权重合计应为 1.0
    total_weight = sum(f.weight for f in factors)
    assert abs(total_weight - 1.0) < 0.01
    print(f"✓ test_gonogo_5_factors: 5 因素齐全，权重合计={total_weight:.2f}")


def test_gonogo_decision_thresholds():
    """不同总分对应不同决策"""
    # 高分：晚期阶段 + 充足预算
    p_high = make_pipeline(current_stage="III期临床", total_budget=10000, consumed_budget=4000)
    proj_high = make_project(status="已完成", execution_rate=100)
    trial_high = make_trial(status="已完成")
    d_high = evaluate_go_nogo(p_high, [proj_high], [trial_high])
    assert d_high.decision in ("Go", "Conditional")

    # 低分：早期阶段 + 严重超支
    p_low = make_pipeline(current_stage="发现", total_budget=1000, consumed_budget=2000)
    d_low = evaluate_go_nogo(p_low, [], [])
    assert d_low.decision in ("No-Go", "Conditional")

    print(f"✓ test_gonogo_decision_thresholds: 高分={d_high.decision}({d_high.total_score:.1f}), 低分={d_low.decision}({d_low.total_score:.1f})")


def test_gonogo_finance_factor():
    """财务可行性：消耗率影响评分（3 个区间：<50%, 50-80%, 80-100%）"""
    p_low = make_pipeline(total_budget=1000, consumed_budget=200)    # 20% → 85分
    p_mid = make_pipeline(total_budget=1000, consumed_budget=600)    # 60% → 70分
    p_high = make_pipeline(total_budget=1000, consumed_budget=900)   # 90% → 40分

    d_low = evaluate_go_nogo(p_low, [], [])
    d_mid = evaluate_go_nogo(p_mid, [], [])
    d_high = evaluate_go_nogo(p_high, [], [])

    fin_low = next(f for f in d_low.factors if f.name == "财务可行性")
    fin_mid = next(f for f in d_mid.factors if f.name == "财务可行性")
    fin_high = next(f for f in d_high.factors if f.name == "财务可行性")

    assert fin_low.score > fin_mid.score > fin_high.score
    print(f"✓ test_gonogo_finance_factor: 20%={fin_low.score:.0f}, 60%={fin_mid.score:.0f}, 90%={fin_high.score:.0f}")


def test_gonogo_science_factor():
    """科学性：阶段越后分数越高"""
    p_early = make_pipeline(current_stage="发现")
    p_late = make_pipeline(current_stage="III期临床")

    d_early = evaluate_go_nogo(p_early, [], [])
    d_late = evaluate_go_nogo(p_late, [], [])

    sci_early = next(f for f in d_early.factors if f.name == "科学性")
    sci_late = next(f for f in d_late.factors if f.name == "科学性")

    assert sci_late.score > sci_early.score
    print(f"✓ test_gonogo_science_factor: 发现={sci_early.score:.0f}, III期={sci_late.score:.0f}")


def test_gonogo_to_dict():
    p = make_pipeline()
    decision = evaluate_go_nogo(p, [], [])
    d = decision.to_dict()
    assert "factors" in d
    assert len(d["factors"]) == 5
    assert all("score" in f and "weight" in f and "assessment" in f for f in d["factors"])
    print("✓ test_gonogo_to_dict: dict 结构完整")


if __name__ == "__main__":
    # 价值评估
    test_value_basic_fields()
    test_value_stage_probability()
    test_value_tier_classification()
    test_value_indication_classification()
    test_value_recommendation()

    # 价值矩阵
    test_matrix_empty()
    test_matrix_basic()
    test_matrix_bcg_quadrants()

    # Go/No-Go
    test_gonogo_basic_fields()
    test_gonogo_5_factors()
    test_gonogo_decision_thresholds()
    test_gonogo_finance_factor()
    test_gonogo_science_factor()
    test_gonogo_to_dict()

    print("\n✅ All Module E.3 pipeline cognitive tests passed!")
