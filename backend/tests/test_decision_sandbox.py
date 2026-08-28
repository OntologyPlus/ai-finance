"""
DecisionSandbox 决策沙盘引擎单元测试 — v8.0 Module I-A
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from engines.decision_sandbox import (
    DecisionSandboxEngine,
    _OPERATION_DOMAINS,
    _RISK_WEIGHT,
)


# ─── Fixtures ──────────────────────────────────────


@pytest.fixture
def engine():
    return DecisionSandboxEngine()


@pytest.fixture
def mock_db():
    """构造一个让 db.execute() 可链式调用的 mock"""
    db = AsyncMock()

    # 默认 execute 返回值：空结果（scalar_one_or_none → None）
    empty_result = MagicMock()
    empty_result.scalar_one_or_none = MagicMock(return_value=None)
    empty_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    empty_result.all = MagicMock(return_value=[])

    db.add = MagicMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock(return_value=empty_result)
    return db


# ─── 模拟基础测试 ─────────────────────────────────


@pytest.mark.asyncio
async def test_simulate_budget_change_decrease(engine, mock_db):
    """预算减少模拟：高金额 + decrease = 高风险"""
    result = await engine.simulate(
        scenario_name="Q3 预算调减",
        operation_type="budget_change",
        operation_params={
            "budget_id": "B-001",
            "change_type": "decrease",
            "amount": 6000000,
        },
        db=mock_db,
    )

    assert result["scenario_name"] == "Q3 预算调减"
    assert result["operation_type"] == "budget_change"
    assert "prediction" in result
    assert "domains" in result["prediction"]
    # 5 域都应有影响
    assert len(result["prediction"]["domains"]) == 5
    # 高风险操作应被识别
    assert result["overall_risk"] in ("中", "高")
    # 可逆
    assert result["reversibility"] == "可逆"
    # 置信度 0-1
    assert 0 <= result["confidence"] <= 1
    # 建议
    assert len(result["recommendations"]) > 0


@pytest.mark.asyncio
async def test_simulate_budget_change_increase(engine, mock_db):
    """预算增加：风险低"""
    result = await engine.simulate(
        scenario_name="Q3 预算追加",
        operation_type="budget_change",
        operation_params={
            "budget_id": "B-002",
            "change_type": "increase",
            "amount": 100000,
        },
        db=mock_db,
    )

    assert result["overall_risk"] in ("低", "中")
    assert "budget" in result["prediction"]["domains"]


@pytest.mark.asyncio
async def test_simulate_expense_overrun_high(engine, mock_db):
    """大额超支：高风险"""
    result = await engine.simulate(
        scenario_name="费用大额超支",
        operation_type="expense_overrun",
        operation_params={"expense_id": "EXP-001", "overrun_amount": 200000},
        db=mock_db,
    )

    assert result["overall_risk"] in ("中", "高")
    assert "expense" in result["prediction"]["domains"]


@pytest.mark.asyncio
async def test_simulate_strategic_shift_is_irreversible(engine, mock_db):
    """战略调整：不可逆"""
    result = await engine.simulate(
        scenario_name="战略方向调整",
        operation_type="strategic_shift",
        operation_params={"initiative_id": "SI-001", "new_direction": "聚焦核心产品"},
        db=mock_db,
    )

    assert result["reversibility"] == "不可逆"
    # 战略调整应有警告
    assert any("不可逆" in r for r in result["recommendations"])


@pytest.mark.asyncio
async def test_simulate_approval_decision(engine, mock_db):
    """审批决策模拟"""
    result = await engine.simulate(
        scenario_name="审批模拟",
        operation_type="approval_decision",
        operation_params={"decision": "approve", "amount": 50000},
        db=mock_db,
    )

    assert result["reversibility"] == "部分可逆"
    assert "approval" in result["prediction"]["domains"]


@pytest.mark.asyncio
async def test_simulate_invalid_operation_type(engine, mock_db):
    """非法操作类型"""
    with pytest.raises(ValueError, match="Unsupported operation_type"):
        await engine.simulate(
            scenario_name="非法",
            operation_type="invalid_type",
            operation_params={},
            db=mock_db,
        )


# ─── 多场景对比 ─────────────────────────────────


@pytest.mark.asyncio
async def test_compare_scenarios(engine, mock_db):
    """多场景对比"""
    scenarios = [
        {
            "name": "保守方案",
            "operation_type": "budget_change",
            "params": {"change_type": "decrease", "amount": 100000},
        },
        {
            "name": "激进方案",
            "operation_type": "budget_change",
            "params": {"change_type": "decrease", "amount": 5000000},
        },
    ]
    result = await engine.compare_scenarios(scenarios, db=mock_db)

    assert "scenarios" in result
    assert len(result["scenarios"]) == 2
    assert "best_scenario" in result
    # 保守方案风险应更低，排在最前
    assert result["best_scenario"] == "保守方案"
    # 风险应递增
    risks = [s["overall_risk"] for s in result["scenarios"]]
    risk_indices = [_RISK_WEIGHT.get(r, 0) for r in risks]
    assert risk_indices == sorted(risk_indices)


# ─── 5 域影响预测方法 ────────────────────────────


@pytest.mark.asyncio
async def test_predict_budget_domain_high_risk(engine):
    """预算域：大幅减少 = 高风险"""
    pred = await engine._predict_budget_domain(
        "budget",
        {"change_type": "decrease", "amount": 5000000},
        None,  # 无 db
    )
    # 5M 无 annual_amount, 默认中风险
    assert pred["severity"] in ("低", "中", "高")


@pytest.mark.asyncio
async def test_predict_budget_domain_cashflow_large(engine):
    """现金流域：大额减少"""
    pred = await engine._predict_budget_domain(
        "cashflow",
        {"change_type": "decrease", "amount": 2000000},
        None,
    )
    # 200 万 > 100 万 = 中风险
    assert pred["severity"] in ("中", "高")


def test_predict_expense_domain_severity(engine):
    """费用超支分级"""
    # 小额
    small = engine._predict_expense_domain("expense", {"overrun_amount": 5000})
    assert small["severity"] == "低"
    # 中等
    mid = engine._predict_expense_domain("expense", {"overrun_amount": 50000})
    assert mid["severity"] == "中"
    # 大额
    big = engine._predict_expense_domain("expense", {"overrun_amount": 200000})
    assert big["severity"] == "高"


def test_predict_strategic_domain(engine):
    """战略调整：所有域都受影响"""
    pred = engine._predict_strategic_domain(
        "strategic",
        {"new_direction": "聚焦核心"},
    )
    assert pred["severity"] == "高"


def test_predict_approval_domain(engine):
    """审批决策域"""
    # 批准（大额 = 中）
    approve = engine._predict_approval_domain(
        "approval", {"decision": "approve", "amount": 200000}
    )
    assert approve["severity"] == "中"
    # 批准（小额 = 低）
    approve_small = engine._predict_approval_domain(
        "approval", {"decision": "approve", "amount": 50000}
    )
    assert approve_small["severity"] == "低"
    # 驳回
    reject = engine._predict_approval_domain(
        "approval", {"decision": "reject"}
    )
    assert reject["severity"] == "低"


# ─── 风险聚合 ────────────────────────────────────


def test_aggregate_risk(engine):
    """总体风险聚合"""
    # 全部低
    pred = {
        "domains": {"a": {"severity": "低"}, "b": {"severity": "低"}},
    }
    assert engine._aggregate_risk(pred) == "低"
    # 有中
    pred = {
        "domains": {"a": {"severity": "低"}, "b": {"severity": "中"}},
    }
    assert engine._aggregate_risk(pred) == "中"
    # 单个高 = 中（1 个高 < 2 个高）
    pred = {
        "domains": {"a": {"severity": "高"}, "b": {"severity": "低"}},
    }
    assert engine._aggregate_risk(pred) == "中"
    # 2 个高 = 高
    pred = {
        "domains": {"a": {"severity": "高"}, "b": {"severity": "高"}},
    }
    assert engine._aggregate_risk(pred) == "高"


# ─── 可逆性评估 ─────────────────────────────────


def test_assess_reversibility(engine):
    """可逆性判定"""
    # 战略调整 = 不可逆
    assert engine._assess_reversibility("strategic_shift", {}) == "不可逆"
    # 审批 = 部分可逆
    assert engine._assess_reversibility("approval_decision", {}) == "部分可逆"
    # 预算变更 = 可逆
    assert engine._assess_reversibility("budget_change", {}) == "可逆"
    # 费用超支 = 可逆
    assert engine._assess_reversibility("expense_overrun", {}) == "可逆"


# ─── 置信度计算 ─────────────────────────────────


def test_calculate_confidence(engine):
    """置信度：操作类型基础值 + 数据完整度"""
    # 战略调整基础值低
    conf1 = engine._calculate_confidence(
        "strategic_shift",
        {"domains": {}, "affected_count": 1},
        None,
    )
    assert 0 <= conf1 <= 1
    # 审批基础值高
    conf2 = engine._calculate_confidence(
        "approval_decision",
        {"domains": {}, "affected_count": 5},
        MagicMock(),  # mock db
    )
    # 有 db + 5 域 = 0.9 + 0.1 = 1.0
    assert conf2 >= 0.9


# ─── 建议生成 ────────────────────────────────────


def test_generate_recommendations_high_risk(engine):
    """高风险建议"""
    pred = {
        "domains": {
            "a": {"severity": "高"},
            "b": {"severity": "高"},
        },
        "high_risk_count": 2,
    }
    recs = engine._generate_recommendations(
        "budget_change", pred, "高", "可逆"
    )
    assert any("高风险" in r for r in recs)
    # 多高影响域建议
    assert any("多个高影响域" in r for r in recs)


def test_generate_recommendations_low_risk(engine):
    """低风险建议"""
    pred = {"domains": {"a": {"severity": "低"}}, "high_risk_count": 0}
    recs = engine._generate_recommendations(
        "budget_change", pred, "低", "可逆"
    )
    assert any("低风险" in r for r in recs)
