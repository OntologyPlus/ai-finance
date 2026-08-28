"""
影响归因 + Pareto 优化器单元测试 — v8.0 Module I-C/D
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from services.impact_attribution import (
    ImpactAttributionService,
    _ATTRIBUTABLE_METRICS,
)
from engines.pareto_optimizer import (
    ParetoOptimizer, DEFAULT_WEIGHTS,
)


# ─── Fixtures ──────────────────────────────────────


@pytest.fixture
def attribution_service():
    return ImpactAttributionService()


@pytest.fixture
def pareto_optimizer():
    return ParetoOptimizer()


@pytest.fixture
def mock_db():
    """构造一个让 db.execute() 可链式调用的 mock"""
    db = AsyncMock()

    empty_result = MagicMock()
    empty_result.scalar_one_or_none = MagicMock(return_value=None)
    empty_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    empty_result.all = MagicMock(return_value=[])

    db.add = MagicMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock(return_value=empty_result)
    return db


# ═══════════════════════════════════════════════════════════
# 影响归因测试
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_attribute_basic(attribution_service, mock_db):
    """基础归因测试"""
    result = await attribution_service.attribute(
        target_metric="execution_rate",
        target_period="2026-05",
        observed_value=85.0,
        db=mock_db,
    )

    assert result["target_metric"] == "execution_rate"
    assert result["target_metric_label"] == "预算执行率"
    assert result["observed_value"] == 85.0
    assert "delta" in result
    assert "explanation" in result
    assert "confidence" in result
    assert 0 <= result["confidence"] <= 1


@pytest.mark.asyncio
async def test_attribute_invalid_metric(attribution_service, mock_db):
    """非法指标"""
    with pytest.raises(ValueError, match="Unsupported metric"):
        await attribution_service.attribute(
            target_metric="invalid_metric",
            target_period="2026-05",
            observed_value=85.0,
            db=mock_db,
        )


@pytest.mark.asyncio
async def test_attribute_explanation(attribution_service, mock_db):
    """自然语言解释生成"""
    result = await attribution_service.attribute(
        target_metric="alert_count",
        target_period="2026-05",
        observed_value=15.0,
        db=mock_db,
    )

    assert "预警数量" in result["explanation"]
    assert "上升" in result["explanation"] or "下降" in result["explanation"]


def test_operation_metric_relevance(attribution_service):
    """操作-指标相关性"""
    # 战略调整 → 战略覆盖率 = 高相关
    r1 = attribution_service._operation_metric_relevance(
        "strategic_shift", "strategic_coverage"
    )
    assert r1 >= 0.9
    # 预算变更 → 执行率 = 高相关
    r2 = attribution_service._operation_metric_relevance(
        "budget_change", "execution_rate"
    )
    assert r2 >= 0.8
    # 战略调整 → 预警数 = 低相关
    r3 = attribution_service._operation_metric_relevance(
        "strategic_shift", "alert_count"
    )
    assert r3 <= 0.5


def test_calculate_attribution_confidence(attribution_service):
    """归因置信度"""
    # 无归因 = 低置信度
    conf1 = attribution_service._calculate_attribution_confidence(
        [], 10.0, 50.0
    )
    assert conf1 <= 0.2
    # 单一归因 + 显著变化 = 较高
    attributions = [
        {"contribution": 80, "operation_id": "op1"},
        {"contribution": 20, "operation_id": "op2"},
    ]
    conf2 = attribution_service._calculate_attribution_confidence(
        attributions, 30.0, 50.0
    )
    assert conf2 >= 0.5


def test_generate_explanation(attribution_service):
    """自然语言解释生成"""
    # 单一归因
    top1 = [{"contribution": 70, "description": "预算调减"}]
    expl = attribution_service._generate_explanation(
        "execution_rate", 50.0, 80.0, 30.0, top1
    )
    assert "预算执行率" in expl
    assert "上升" in expl
    assert "预算调减" in expl
    # 空归因
    expl_empty = attribution_service._generate_explanation(
        "execution_rate", 50.0, 80.0, 30.0, []
    )
    assert "暂无显著归因" in expl_empty


def test_attribute_supported_metrics():
    """支持的归因指标列表"""
    assert "execution_rate" in _ATTRIBUTABLE_METRICS
    assert "overrun_rate" in _ATTRIBUTABLE_METRICS
    assert "alert_count" in _ATTRIBUTABLE_METRICS
    assert "roi" in _ATTRIBUTABLE_METRICS


# ═══════════════════════════════════════════════════════════
# Pareto 优化器测试
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_pareto_optimize_basic(pareto_optimizer, mock_db):
    """Pareto 基础优化"""
    candidates = [
        {
            "id": "方案A",
            "params": {"budget": 1000},
            "scores": {
                "budget_compliance": 80,
                "business_impact": 70,
                "strategic_alignment": 60,
                "cashflow_stability": 75,
            },
        },
        {
            "id": "方案B",
            "params": {"budget": 2000},
            "scores": {
                "budget_compliance": 50,
                "business_impact": 90,
                "strategic_alignment": 85,
                "cashflow_stability": 40,
            },
        },
    ]
    result = await pareto_optimizer.optimize(candidates, db=mock_db)

    assert "pareto_optimal" in result
    assert "ranked" in result
    assert "summary" in result
    # 2 个方案都被处理
    assert len(result["ranked"]) == 2
    # 2 个方案可能都是 Pareto 最优（无明显支配）
    assert result["summary"]["total_candidates"] == 2


@pytest.mark.asyncio
async def test_pareto_dominance(pareto_optimizer, mock_db):
    """Pareto 支配关系"""
    # 方案 B 在所有维度都不差于 A，且至少一个更优
    candidates = [
        {
            "id": "劣方案A",
            "scores": {
                "budget_compliance": 30,
                "business_impact": 30,
                "strategic_alignment": 30,
                "cashflow_stability": 30,
            },
        },
        {
            "id": "优方案B",
            "scores": {
                "budget_compliance": 80,
                "business_impact": 80,
                "strategic_alignment": 80,
                "cashflow_stability": 80,
            },
        },
    ]
    result = await pareto_optimizer.optimize(candidates, db=mock_db)
    # B 应支配 A，A 不应是 Pareto 最优
    pareto_ids = [p["id"] for p in result["pareto_optimal"]]
    assert "优方案B" in pareto_ids
    assert "劣方案A" not in pareto_ids


@pytest.mark.asyncio
async def test_pareto_empty(pareto_optimizer, mock_db):
    """空候选列表"""
    result = await pareto_optimizer.optimize([], db=mock_db)
    assert result["pareto_optimal"] == []
    assert result["ranked"] == []


def test_pareto_weighted_score(pareto_optimizer):
    """加权得分"""
    scores = {
        "budget_compliance": 80,
        "business_impact": 70,
        "strategic_alignment": 60,
        "cashflow_stability": 75,
    }
    weighted = pareto_optimizer._weighted_score(scores)
    # 80*0.3 + 70*0.3 + 60*0.2 + 75*0.2 = 24+21+12+15 = 72
    assert weighted == 72.0


def test_pareto_dominates():
    """支配判定"""
    # A 支配 B（A 全 >= B 且至少一个 >）
    a = {"budget_compliance": 80, "business_impact": 70,
         "strategic_alignment": 60, "cashflow_stability": 75}
    b = {"budget_compliance": 70, "business_impact": 70,
         "strategic_alignment": 60, "cashflow_stability": 75}
    assert ParetoOptimizer._dominates(a, b) is True

    # 不可比较
    c = {"budget_compliance": 50, "business_impact": 90,
         "strategic_alignment": 60, "cashflow_stability": 75}
    assert ParetoOptimizer._dominates(a, c) is False
    assert ParetoOptimizer._dominates(c, a) is False


def test_pareto_compliance_score():
    """合规度评分"""
    # 大幅减少 = 高
    assert ParetoOptimizer._compliance_score(-0.5) >= 90
    # 不变 = 中
    assert ParetoOptimizer._compliance_score(0) == 70
    # 大幅增加 = 低
    assert ParetoOptimizer._compliance_score(0.5) < 50


def test_pareto_impact_score():
    """业务影响度评分"""
    # 适度增加 = 高
    assert ParetoOptimizer._impact_score(0.15) >= 80
    # 大幅减少 = 低
    assert ParetoOptimizer._impact_score(-0.5) <= 40


def test_pareto_strategic_score():
    """战略对齐度评分"""
    # 增加 = 高
    assert ParetoOptimizer._strategic_score(0.2) >= 80
    # 减少 = 低
    assert ParetoOptimizer._strategic_score(-0.5) <= 40


def test_pareto_cashflow_score():
    """现金流稳定性评分"""
    # 减少 = 释放现金 = 高
    assert ParetoOptimizer._cashflow_score(-0.5) >= 90
    # 增加 = 压力 = 低
    assert ParetoOptimizer._cashflow_score(0.5) <= 40


@pytest.mark.asyncio
async def test_pareto_auto_candidates(pareto_optimizer, mock_db):
    """自动生成候选方案"""
    candidates = await pareto_optimizer.auto_candidates_from_budget_change(
        budget_id="B-001",
        original_amount=1000000,
        db=mock_db,
    )

    # 7 个候选（-30%/-15%/-5%/0/+5%/+15%/+30%）
    assert len(candidates) == 7
    # 每个候选有 4 维评分
    for c in candidates:
        scores = c["scores"]
        assert "budget_compliance" in scores
        assert "business_impact" in scores
        assert "strategic_alignment" in scores
        assert "cashflow_stability" in scores
        assert all(0 <= scores[k] <= 100 for k in scores)


@pytest.mark.asyncio
async def test_pareto_custom_weights(mock_db):
    """自定义权重"""
    optimizer = ParetoOptimizer(weights={
        "budget_compliance": 0.7,
        "business_impact": 0.1,
        "strategic_alignment": 0.1,
        "cashflow_stability": 0.1,
    })
    candidates = [
        {
            "id": "合规优先",
            "scores": {
                "budget_compliance": 100,
                "business_impact": 30,
                "strategic_alignment": 30,
                "cashflow_stability": 30,
            },
        },
        {
            "id": "影响优先",
            "scores": {
                "budget_compliance": 30,
                "business_impact": 100,
                "strategic_alignment": 100,
                "cashflow_stability": 100,
            },
        },
    ]
    result = await optimizer.optimize(candidates, db=mock_db)
    # 合规优先方案应该得分更高
    assert result["ranked"][0]["id"] == "合规优先"


def test_pareto_default_weights():
    """默认权重合理"""
    total = sum(DEFAULT_WEIGHTS.values())
    assert abs(total - 1.0) < 0.01
