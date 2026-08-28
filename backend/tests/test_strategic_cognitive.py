"""Strategic Cognitive Engine unit tests (v9.0 E.1)."""
import sys
from pathlib import Path
from types import SimpleNamespace

# 注入 backend 根目录到 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.strategic_cognitive import (
    compute_risk_gauge,
    build_impact_chain,
    compute_gap_analysis,
    _to_float,
)


def make_initiative(**kwargs):
    defaults = {
        "initiative_id": "INI-001",
        "initiative_name": "测试举措",
        "strategic_intent_l1": "全渠道商业化",
        "strategic_intent_l2": "产品线A×华北",
        "owner_center": "C-001",
        "owner_manager": "张三",
        "kpi_target": 1000.0,
        "kpi_actual": 800.0,
        "budget_allocated": 500.0,
        "status": "执行中",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def make_allocation(**kwargs):
    defaults = {
        "allocation_id": "AL-001",
        "budget_id": "B-001",
        "quarter": "Q1",
        "planned_amount": 100.0,
        "actual_amount": 60.0,
        "milestone_achieved": "部分达成",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def make_budget(**kwargs):
    defaults = {
        "budget_id": "B-001",
        "description": "市场推广预算",
        "annual_amount": 1000.0,
        "used_amount": 600.0,
        "strategic_intent_l1": "全渠道商业化",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# ── Test 1: Risk Gauge basic ──
def test_risk_gauge_basic():
    initiatives = [
        make_initiative(initiative_id="INI-001", kpi_target=1000, kpi_actual=800),
        make_initiative(initiative_id="INI-002", kpi_target=500, kpi_actual=400, priority="high"),
        make_initiative(initiative_id="INI-003", priority="low"),
    ]
    allocations = [make_allocation(), make_allocation(allocation_id="AL-002", actual_amount=80)]
    budget_items = [make_budget()]

    gauge = compute_risk_gauge(initiatives, allocations, budget_items)
    assert 0 <= gauge.overall_score <= 100
    assert gauge.grade in ("A", "B", "C", "D")
    assert gauge.risk_level in ("low", "medium", "high", "critical")
    assert len(gauge.dimensions) == 5
    assert sum(d.weight for d in gauge.dimensions) == 1.0  # 权重和 = 1.0
    print(f"  Risk Gauge: {gauge.overall_score:.1f}分 ({gauge.grade}级, {gauge.risk_label})")


# ── Test 2: Risk Gauge empty ──
def test_risk_gauge_empty():
    gauge = compute_risk_gauge([], [], [])
    assert gauge.overall_score == 0.0
    assert gauge.grade == "D"
    assert "无战略举措" in gauge.risk_label
    print(f"  Empty Risk Gauge: {gauge.risk_label}")


# ── Test 3: Risk Gauge all high KPI gap (worse case) ──
def test_risk_gauge_worst():
    initiatives = [
        make_initiative(initiative_id="INI-001", kpi_target=1000, kpi_actual=100),  # 90% 偏差
    ]
    allocations = [make_allocation(actual_amount=5)]  # 5% 执行
    gauge = compute_risk_gauge(initiatives, allocations, [])
    # 90% KPI 偏差 + 5% 执行，应明显低于正常水平
    assert gauge.overall_score < 75, f"Expected <75, got {gauge.overall_score}"
    # 至少触发一个高风险等级
    assert gauge.risk_level in ("high", "critical"), f"Expected high/critical, got {gauge.risk_level}"
    print(f"  Worst Case Risk Gauge: {gauge.overall_score:.1f}分 ({gauge.grade}级 / {gauge.risk_level})")


# ── Test 4: Impact Chain ──
def test_impact_chain():
    ini = make_initiative(initiative_id="INI-001", kpi_target=1000, kpi_actual=900)
    allocations = [
        make_allocation(allocation_id="AL-001", actual_amount=80),
        make_allocation(allocation_id="AL-002", actual_amount=120),  # 超支
    ]
    budget_items = [
        make_budget(budget_id="B-001", description="预算A"),
        make_budget(budget_id="B-002", description="预算B"),
    ]

    chain = build_impact_chain(ini, allocations, budget_items)
    assert chain.level == "intent"
    assert len(chain.children) == 1
    ini_node = chain.children[0]
    assert ini_node.level == "initiative"
    assert ini_node.status == "achieved"  # 90% 达成 = achieved
    assert len(ini_node.children) >= 1
    print(f"  Impact Chain: {chain.name} → {ini_node.name} (status={ini_node.status})")


# ── Test 5: Gap Analysis ──
def test_gap_analysis():
    initiatives = [
        make_initiative(strategic_intent_l1="全渠道商业化", kpi_target=1000, kpi_actual=900),
        make_initiative(initiative_id="INI-002", strategic_intent_l1="全渠道商业化", kpi_target=500, kpi_actual=200),
        make_initiative(initiative_id="INI-003", strategic_intent_l1="创新研发", kpi_target=800, kpi_actual=750),
    ]
    budget_items = [
        make_budget(strategic_intent_l1="全渠道商业化", annual_amount=1000, used_amount=800),
        make_budget(budget_id="B-002", strategic_intent_l1="创新研发", annual_amount=500, used_amount=400),
    ]

    gap = compute_gap_analysis(initiatives, budget_items, [])
    assert "gaps" in gap
    assert "summary" in gap
    assert len(gap["gaps"]) == 2  # 2 个不同 intent

    # 验证每个 gap 的字段
    for g in gap["gaps"]:
        assert "intent" in g
        assert "achievement_rate" in g
        assert "status" in g
        assert "suggestions" in g
    print(f"  Gap Analysis: {gap['summary']}")


# ── Test 6: to_float helper ──
def test_to_float():
    from decimal import Decimal
    assert _to_float(None) == 0.0
    assert _to_float(Decimal("100.5")) == 100.5
    assert _to_float("123") == 123.0
    assert _to_float("invalid") == 0.0
    print(f"  _to_float: OK")


if __name__ == "__main__":
    print("Running Strategic Cognitive tests...")
    test_to_float()
    test_risk_gauge_basic()
    test_risk_gauge_empty()
    test_risk_gauge_worst()
    test_impact_chain()
    test_gap_analysis()
    print("\n✅ All tests passed!")
