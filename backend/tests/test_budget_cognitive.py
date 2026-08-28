"""Budget Cognitive Engine unit tests (v9.0 E.2)."""
import sys
from pathlib import Path
from types import SimpleNamespace

# 注入 backend 根目录到 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.budget_cognitive import (
    drill_down_root_cause,
    generate_proactive_suggestions,
    compute_business_linkage,
)


def make_budget_item(**kwargs):
    defaults = {
        "budget_id": "B-001",
        "description": "测试预算项",
        "l1_code": "01",
        "l2_code": "0101",
        "annual_amount": 1000.0,
        "used_amount": 500.0,
        "available_amount": 500.0,
        "budget_category": "A",
        "quadrant": "发展",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def make_expense(**kwargs):
    defaults = {
        "expense_id": "E-001",
        "budget_id": "B-001",
        "amount": 1000.0,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# ── 1. 5 层根因下钻 ────────────────────────────────────────

def test_drill_normal():
    item = make_budget_item(annual_amount=1000, used_amount=500)
    # 提供同 L1 同类项目以触发 L2 横向对比层
    peer = make_budget_item(budget_id="B-peer", annual_amount=1000, used_amount=500, l1_code="01")
    drill = drill_down_root_cause(item, [item, peer])
    assert drill.issue_type == "正常"
    assert drill.severity == "info"
    assert len(drill.layers) == 5
    assert drill.layers[0].level == 1
    assert drill.layers[4].level == 5
    assert "正常" in drill.final_recommendation or "保持" in drill.final_recommendation
    print(f"✓ test_drill_normal: {drill.summary[:50]}...")


def test_drill_over_budget_critical():
    item = make_budget_item(annual_amount=1000, used_amount=1300)
    drill = drill_down_root_cause(item, [item])
    assert drill.issue_type == "超支"
    assert drill.severity == "critical"
    assert "冻结" in drill.final_recommendation or "复盘" in drill.final_recommendation
    # 验证 L1 现象
    assert "130" in drill.layers[0].finding or "超支" in drill.layers[0].finding
    print(f"✓ test_drill_over_budget_critical: severity={drill.severity}")


def test_drill_over_budget_risk():
    item = make_budget_item(annual_amount=1000, used_amount=1050)
    drill = drill_down_root_cause(item, [item])
    assert drill.issue_type == "超支"
    assert drill.severity == "risk"
    print(f"✓ test_drill_over_budget_risk: severity={drill.severity}")


def test_drill_high_execution():
    item = make_budget_item(annual_amount=1000, used_amount=850)
    drill = drill_down_root_cause(item, [item])
    assert drill.issue_type == "执行偏高"
    assert drill.severity == "warning"
    print(f"✓ test_drill_high_execution: severity={drill.severity}")


def test_drill_low_execution():
    item = make_budget_item(annual_amount=1000, used_amount=200)
    drill = drill_down_root_cause(item, [item])
    assert drill.issue_type == "执行偏低"
    assert drill.severity == "info"
    print(f"✓ test_drill_low_execution: severity={drill.severity}")


def test_drill_horizontal_comparison():
    """L2 横向对比：与同 L1 科目对比"""
    target = make_budget_item(budget_id="B-target", annual_amount=1000, used_amount=950, l1_code="01")
    same_l1_low = make_budget_item(budget_id="B-low", annual_amount=1000, used_amount=200, l1_code="01")
    same_l1_med = make_budget_item(budget_id="B-med", annual_amount=1000, used_amount=500, l1_code="01")
    diff_l1 = make_budget_item(budget_id="B-diff", annual_amount=1000, used_amount=500, l1_code="02")

    drill = drill_down_root_cause(target, [target, same_l1_low, same_l1_med, diff_l1])
    # 应有 L2 量化层
    l2 = next((l for l in drill.layers if l.level == 2), None)
    assert l2 is not None, "应包含 L2 量化层"
    assert "01" in str(l2.evidence) or "同类" in l2.finding
    print(f"✓ test_drill_horizontal_comparison: {l2.finding[:50]}")


def test_drill_with_history():
    """L4 纵向趋势：有历史时显示趋势"""
    target = make_budget_item(annual_amount=1000, used_amount=600)
    history_item = SimpleNamespace(execution_rate=40.0)
    drill = drill_down_root_cause(target, [target], history=[history_item])
    l4 = next((l for l in drill.layers if l.level == 4), None)
    assert l4 is not None
    # 应该提到 +20pp 趋势
    assert "20" in l4.finding or "pp" in l4.finding
    print(f"✓ test_drill_with_history: {l4.finding[:50]}")


def test_drill_similar_solutions():
    """L5 关联：超支时找同类项目"""
    target = make_budget_item(budget_id="B-target", annual_amount=1000, used_amount=1000, l1_code="01")
    similar = make_budget_item(budget_id="B-similar", annual_amount=1000, used_amount=950, l1_code="01")
    drill = drill_down_root_cause(target, [target, similar])
    l5 = next((l for l in drill.layers if l.level == 5), None)
    assert l5 is not None
    # 应发现同类超支
    assert "同类" in l5.finding or "超支" in l5.finding
    print(f"✓ test_drill_similar_solutions: {l5.finding[:60]}")


def test_drill_to_dict():
    item = make_budget_item(annual_amount=1000, used_amount=500)
    peer = make_budget_item(budget_id="B-peer", annual_amount=1000, used_amount=500, l1_code="01")
    drill = drill_down_root_cause(item, [item, peer])
    d = drill.to_dict()
    assert d["budget_id"] == "B-001"
    assert "layers" in d
    assert len(d["layers"]) == 5
    assert "final_recommendation" in d
    print(f"✓ test_drill_to_dict: dict keys OK")


# ── 2. 主动建议面板 ────────────────────────────────────────

def test_suggestions_empty():
    suggestions = generate_proactive_suggestions([])
    assert len(suggestions) == 1
    assert suggestions[0].priority == "info"
    assert "暂无" in suggestions[0].title
    print(f"✓ test_suggestions_empty: {suggestions[0].title}")


def test_suggestions_over_budget():
    items = [
        make_budget_item(budget_id="B1", description="超支项", annual_amount=1000, used_amount=1100, quadrant="发展"),
        make_budget_item(budget_id="B2", description="正常项", annual_amount=1000, used_amount=500, quadrant="稳定"),
    ]
    suggestions = generate_proactive_suggestions(items)
    critical = [s for s in suggestions if s.priority == "critical"]
    assert len(critical) >= 1, "应有 critical 超支预警"
    assert any("超支" in s.title for s in critical)
    print(f"✓ test_suggestions_over_budget: {len(critical)} critical items")


def test_suggestions_low_execution():
    items = [
        make_budget_item(budget_id="B1", description="低执行", annual_amount=1000, used_amount=200, quadrant="稳定"),
    ]
    suggestions = generate_proactive_suggestions(items)
    low_exec = [s for s in suggestions if "执行滞后" in s.title or "低执行" in s.title]
    assert len(low_exec) >= 1
    assert low_exec[0].priority == "attention"
    print(f"✓ test_suggestions_low_execution: 触发调拨建议")


def test_suggestions_cross_quadrant():
    """跨象限调拨建议"""
    items = [
        make_budget_item(budget_id="B1", description="a", annual_amount=1000, used_amount=900, quadrant="发展"),
        make_budget_item(budget_id="B2", description="b", annual_amount=1000, used_amount=100, quadrant="收缩"),
    ]
    suggestions = generate_proactive_suggestions(items)
    cross = [s for s in suggestions if "跨象限" in s.title or "调拨" in s.category]
    # 应该至少有一条调拨相关
    assert any(s.category == "调拨" for s in suggestions)
    print(f"✓ test_suggestions_cross_quadrant: 触发 {sum(1 for s in suggestions if s.category == '调拨')} 条调拨建议")


def test_suggestions_ab_ratio_high():
    """A 类占比过高"""
    items = [
        make_budget_item(budget_id="B1", annual_amount=800, used_amount=100, budget_category="A"),
        make_budget_item(budget_id="B2", annual_amount=200, used_amount=50, budget_category="B"),
    ]
    suggestions = generate_proactive_suggestions(items)
    ab = [s for s in suggestions if "A 类预算占比" in s.title]
    assert len(ab) >= 1
    print(f"✓ test_suggestions_ab_ratio_high: {ab[0].title}")


def test_suggestions_ab_ratio_low():
    """A 类占比过低"""
    items = [
        make_budget_item(budget_id="B1", annual_amount=200, used_amount=50, budget_category="A"),
        make_budget_item(budget_id="B2", annual_amount=800, used_amount=100, budget_category="B"),
    ]
    suggestions = generate_proactive_suggestions(items)
    ab = [s for s in suggestions if "A 类预算占比" in s.title]
    assert len(ab) >= 1
    assert "偏低" in ab[0].title
    print(f"✓ test_suggestions_ab_ratio_low: {ab[0].title}")


# ── 3. 预算-业务联动 ────────────────────────────────────────

def test_linkage_empty():
    result = compute_business_linkage([])
    assert result["items"] == []
    assert result["risk_pairs"] == []
    print("✓ test_linkage_empty: 空数据返回空结构")


def test_linkage_no_expenses():
    items = [make_budget_item(annual_amount=1000, used_amount=500)]
    result = compute_business_linkage(items, expenses=None)
    assert len(result["items"]) == 1
    assert result["items"][0]["linkage_type"] == "正常"
    assert result["items"][0]["expense_count"] == 0
    print(f"✓ test_linkage_no_expenses: {result['summary']}")


def test_linkage_high_freq_low_amount_risk():
    """高频低额风险对：执行率高 + 多笔小额报销"""
    item = make_budget_item(annual_amount=1000, used_amount=850, budget_id="B-001")
    expenses = [
        make_expense(expense_id=f"E{i}", budget_id="B-001", amount=100) for i in range(20)
    ]
    result = compute_business_linkage([item], expenses)
    risk_pairs = result["risk_pairs"]
    assert len(risk_pairs) == 1
    assert risk_pairs[0]["linkage_type"] == "高频低额"
    assert risk_pairs[0]["risk_level"] == "high"
    print(f"✓ test_linkage_high_freq_low_amount_risk: {risk_pairs[0]['name']}")


def test_linkage_low_freq_high_amount_risk():
    """低频高额风险对：执行率高 + 单笔大额"""
    item = make_budget_item(annual_amount=1000, used_amount=850, budget_id="B-002")
    expenses = [
        make_expense(expense_id="E1", budget_id="B-002", amount=10000),
        make_expense(expense_id="E2", budget_id="B-002", amount=8000),
    ]
    result = compute_business_linkage([item], expenses)
    risk_pairs = result["risk_pairs"]
    assert len(risk_pairs) == 1
    assert risk_pairs[0]["linkage_type"] == "低频高额"
    assert risk_pairs[0]["risk_level"] == "medium"
    print(f"✓ test_linkage_low_freq_high_amount_risk: avg={risk_pairs[0]['avg_per_expense']}")


def test_linkage_normal_low_execution():
    """低执行无风险对"""
    item = make_budget_item(annual_amount=1000, used_amount=200, budget_id="B-003")
    expenses = [make_expense(budget_id="B-003", amount=200)]
    result = compute_business_linkage([item], expenses)
    assert len(result["risk_pairs"]) == 0
    assert result["items"][0]["linkage_type"] == "正常"
    print("✓ test_linkage_normal_low_execution: 无风险对")


def test_linkage_mixed_items():
    """混合场景：多个项目有不同联动类型"""
    items = [
        make_budget_item(budget_id="B-A", annual_amount=1000, used_amount=900),
        make_budget_item(budget_id="B-B", annual_amount=1000, used_amount=300),
    ]
    expenses = [
        make_expense(expense_id=f"E{i}", budget_id="B-A", amount=500) for i in range(5)
    ] + [
        make_expense(expense_id="E-low", budget_id="B-B", amount=300)
    ]
    result = compute_business_linkage(items, expenses)
    # B-A 应该是高频低额
    # B-B 应该是正常（执行率 < 80）
    assert len(result["items"]) == 2
    summary_count = result["summary"]
    assert "联动" in summary_count
    print(f"✓ test_linkage_mixed_items: {result['summary']}")


def test_linkage_no_matching_expenses():
    """报销 budget_id 不匹配预算项"""
    item = make_budget_item(budget_id="B-001", annual_amount=1000, used_amount=500)
    expenses = [make_expense(budget_id="B-OTHER", amount=100)]
    result = compute_business_linkage([item], expenses)
    assert result["items"][0]["expense_count"] == 0
    assert len(result["risk_pairs"]) == 0
    print("✓ test_linkage_no_matching_expenses: 正确处理无匹配")


if __name__ == "__main__":
    # 5 层根因下钻
    test_drill_normal()
    test_drill_over_budget_critical()
    test_drill_over_budget_risk()
    test_drill_high_execution()
    test_drill_low_execution()
    test_drill_horizontal_comparison()
    test_drill_with_history()
    test_drill_similar_solutions()
    test_drill_to_dict()

    # 主动建议
    test_suggestions_empty()
    test_suggestions_over_budget()
    test_suggestions_low_execution()
    test_suggestions_cross_quadrant()
    test_suggestions_ab_ratio_high()
    test_suggestions_ab_ratio_low()

    # 业务联动
    test_linkage_empty()
    test_linkage_no_expenses()
    test_linkage_high_freq_low_amount_risk()
    test_linkage_low_freq_high_amount_risk()
    test_linkage_normal_low_execution()
    test_linkage_mixed_items()
    test_linkage_no_matching_expenses()

    print("\n✅ All Module E.2 budget cognitive tests passed!")
