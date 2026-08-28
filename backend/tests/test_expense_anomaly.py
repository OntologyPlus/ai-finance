"""
费用异常 + 风险评分 + 预算消耗预测 单元测试
"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from engines.expense_anomaly import ExpenseAnomalyEngine, ANOMALY_TYPES
from engines.expense_risk_score import (
    ExpenseRiskScoreEngine,
    SEVERITY_BANDS,
    WEIGHTS,
)
from engines.budget_burn_predictor import BudgetBurnPredictor, SEASONAL_FACTORS


# ──────────────── Fixtures ────────────────


def make_expense(
    expense_id: str = "EX001",
    amount: float = 1000.0,
    l1_code: str = "A1",
    l2_code: str = "A101",
    l3_code: str = "A10101",
    applicant_id: str = "U001",
    center_id: str = "C01",
    status: str = "待审批",
    created_at: datetime = None,
):
    """构造 ExpenseReport 模拟对象"""
    return SimpleNamespace(
        expense_id=expense_id,
        amount=amount,
        l1_code=l1_code,
        l2_code=l2_code,
        l3_code=l3_code,
        applicant_id=applicant_id,
        center_id=center_id,
        status=status,
        created_at=created_at or datetime(2024, 6, 15),
    )


# ──────────────── ExpenseAnomalyEngine ────────────────


class TestExpenseAnomalyEngine:
    """费用异常检测引擎测试"""

    def setup_method(self):
        self.engine = ExpenseAnomalyEngine()

    @pytest.mark.asyncio
    async def test_amount_zscore_normal(self):
        """正常金额不应触发异常"""
        # 历史 10 笔，金额均值 1000，标准差 100
        historical = [
            make_expense(expense_id=f"EX{i}", amount=1000 + i * 10)
            for i in range(10)
        ]
        expense = make_expense(expense_id="EX_NEW", amount=1050)
        anomalies = await self.engine.detect_single_anomaly(expense, historical)
        amount_anomalies = [a for a in anomalies if a["type"] == "single_amount"]
        assert len(amount_anomalies) == 0

    @pytest.mark.asyncio
    async def test_amount_zscore_extreme(self):
        """极端偏离金额应触发异常"""
        historical = [
            make_expense(expense_id=f"EX{i}", amount=1000 + i * 10)
            for i in range(10)
        ]
        # 异常金额 = 历史均值的 10 倍
        expense = make_expense(expense_id="EX_NEW", amount=10000)
        anomalies = await self.engine.detect_single_anomaly(expense, historical)
        amount_anomalies = [a for a in anomalies if a["type"] == "single_amount"]
        assert len(amount_anomalies) == 1
        assert amount_anomalies[0]["z_score"] > 2.0
        assert amount_anomalies[0]["severity"] in ("high", "medium")

    @pytest.mark.asyncio
    async def test_category_deviation(self):
        """品类偏离应触发异常"""
        historical = [
            make_expense(expense_id=f"EX{i}", l1_code="A1")
            for i in range(10)
        ]
        # 申请人从不用 B2
        expense = make_expense(expense_id="EX_NEW", l1_code="B2")
        anomalies = await self.engine.detect_single_anomaly(expense, historical)
        cat_anomalies = [a for a in anomalies if a["type"] == "single_category"]
        assert len(cat_anomalies) == 1
        assert "B2" in cat_anomalies[0]["expense_l1"]

    @pytest.mark.asyncio
    async def test_timing_year_end(self):
        """年末提交应触发异常"""
        historical = [make_expense(expense_id=f"EX{i}") for i in range(5)]
        expense = make_expense(
            expense_id="EX_NEW",
            created_at=datetime(2024, 12, 28),  # 年末
        )
        anomalies = await self.engine.detect_single_anomaly(expense, historical)
        timing_anomalies = [a for a in anomalies if a["type"] == "timing"]
        assert len(timing_anomalies) == 1
        assert timing_anomalies[0]["severity"] == "high"

    @pytest.mark.asyncio
    async def test_timing_quarter_end(self):
        """季末提交应触发异常"""
        historical = [make_expense(expense_id=f"EX{i}") for i in range(5)]
        expense = make_expense(
            expense_id="EX_NEW",
            created_at=datetime(2024, 9, 28),  # 季末
        )
        anomalies = await self.engine.detect_single_anomaly(expense, historical)
        timing_anomalies = [a for a in anomalies if a["type"] == "timing"]
        assert len(timing_anomalies) >= 1
        assert any(a["severity"] == "medium" for a in timing_anomalies)

    @pytest.mark.asyncio
    async def test_empty_history(self):
        """无历史数据时不报错"""
        expense = make_expense(expense_id="EX_NEW", amount=5000)
        anomalies = await self.engine.detect_single_anomaly(expense, [])
        # 无历史时不触发异常（不计算 z-score）
        amount_anomalies = [a for a in anomalies if a["type"] == "single_amount"]
        assert len(amount_anomalies) == 0

    @pytest.mark.asyncio
    async def test_group_anomalies_with_mock_db(self):
        """群体异常检测（mock DB）"""
        # 模拟 DB 两次查询的返回
        cur_data = [("C01", 200000.0), ("C02", 50000.0)]
        prev_data = [("C01", 100000.0), ("C02", 45000.0)]

        mock_db = MagicMock()
        # 第一次执行（中心维度当期）
        mock_result1 = MagicMock()
        mock_result1.all.return_value = cur_data
        # 第二次执行（中心维度上期）
        mock_result2 = MagicMock()
        mock_result2.all.return_value = prev_data
        # 第三次、四次（品类维度）
        mock_result3 = MagicMock()
        mock_result3.all.return_value = []
        mock_result4 = MagicMock()
        mock_result4.all.return_value = []

        mock_db.execute = AsyncMock(side_effect=[
            mock_result1, mock_result2, mock_result3, mock_result4
        ])

        anomalies = await self.engine.detect_group_anomalies(mock_db, "2024-06")
        # C01 环比 +100% 应触发
        assert len(anomalies) >= 1
        assert any(a["center_id"] == "C01" for a in anomalies)
        assert any(a["mom_pct"] >= 50 for a in anomalies)

    @pytest.mark.asyncio
    async def test_trend_yoy(self):
        """同比异常检测（mock DB）"""
        mock_db = MagicMock()
        # 第一次执行（当前期间）
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, i: [200, 200000.0][i] if i < 2 else None
        mock_result1 = MagicMock()
        mock_result1.first.return_value = [200, 200000.0]
        # 第二次执行（去年同期）
        mock_result2 = MagicMock()
        mock_result2.first.return_value = [150, 100000.0]

        mock_db.execute = AsyncMock(side_effect=[mock_result1, mock_result2])

        anomalies = await self.engine.detect_trend_anomalies(mock_db, "2024-06")
        # 同比 +100% 应触发
        assert len(anomalies) >= 1
        assert any(a["yoy_pct"] >= 30 for a in anomalies)


# ──────────────── ExpenseRiskScoreEngine ────────────────


class TestExpenseRiskScoreEngine:
    """费用风险评分引擎测试"""

    def setup_method(self):
        self.engine = ExpenseRiskScoreEngine()

    def test_amount_score_zero(self):
        """金额为 0 时分数为 0"""
        assert self.engine._amount_score(0, [100, 200, 300]) == 0.0

    def test_amount_score_normal(self):
        """金额接近中位数时分数较低"""
        # 中位数 = 1000，本次 = 1000
        score = self.engine._amount_score(1000, [800, 900, 1000, 1100, 1200])
        assert score == 0.0

    def test_amount_score_high(self):
        """金额远高于中位数时分数较高"""
        score = self.engine._amount_score(5000, [800, 900, 1000, 1100, 1200])
        assert score >= 60.0  # 偏离 400%

    def test_category_score_top1(self):
        """申请人最常用 L1 → 0 分"""
        score = self.engine._category_score("A1", ["A1"] * 10)
        assert score == 0.0

    def test_category_score_unknown(self):
        """不在历史 → 70 分"""
        score = self.engine._category_score("B2", ["A1"] * 10)
        assert score == 70.0

    def test_category_score_empty_history(self):
        """无历史 → 50 分"""
        score = self.engine._category_score("A1", [])
        assert score == 50.0

    def test_frequency_score_normal(self):
        """频次正常时分数较低"""
        score = self.engine._frequency_score(1, [1, 1, 2, 1, 1])
        assert score < 30.0

    def test_frequency_score_high(self):
        """频次远高于历史时分数较高"""
        score = self.engine._frequency_score(5, [1, 1, 2, 1, 1])
        assert score >= 60.0

    def test_timing_year_end(self):
        """年末时段分数高"""
        score = self.engine._timing_score(datetime(2024, 12, 25))
        assert score == 90.0

    def test_timing_quarter_end(self):
        """季末时段分数中等"""
        score = self.engine._timing_score(datetime(2024, 9, 28))
        assert score == 60.0

    def test_timing_normal(self):
        """正常时段分数为 0"""
        score = self.engine._timing_score(datetime(2024, 6, 15))
        assert score == 0.0

    def test_history_score_clean(self):
        """无历史驳回 → 0 分"""
        score = self.engine._history_score("U001", 0, 10)
        assert score == 0.0

    def test_history_score_high(self):
        """高驳回率 → 高分"""
        score = self.engine._history_score("U001", 3, 10)  # 30%
        assert score >= 90.0

    @pytest.mark.asyncio
    async def test_score_expense_low_risk(self):
        """低风险报销应得 low band"""
        historical = [
            make_expense(expense_id=f"EX{i}", amount=1000, l1_code="A1", status="已审批")
            for i in range(10)
        ]
        expense = make_expense(expense_id="EX_NEW", amount=1000, l1_code="A1")
        score = await self.engine.score_expense(expense, historical, 0)
        assert score["band"] == "low"
        assert score["action"] == "auto_approve"
        assert score["total_score"] < 30

    @pytest.mark.asyncio
    async def test_score_expense_critical(self):
        """极端高风险报销应得 critical band"""
        historical = [
            make_expense(expense_id=f"EX{i}", amount=1000, l1_code="A1")
            for i in range(10)
        ]
        expense = make_expense(
            expense_id="EX_NEW",
            amount=10000,  # 10 倍
            l1_code="Z9",  # 不在历史
            created_at=datetime(2024, 12, 28),  # 年末
        )
        score = await self.engine.score_expense(expense, historical, 5)  # 50% 驳回
        assert score["band"] in ("critical", "high")
        assert score["action"] in ("auto_reject", "manual_review")
        assert score["total_score"] >= 60

    def test_band_classification(self):
        """分数段位分类正确"""
        assert self.engine._band(10) == "low"
        assert self.engine._band(45) == "medium"
        assert self.engine._band(70) == "high"
        assert self.engine._band(90) == "critical"

    def test_weights_sum_to_one(self):
        """5 维度权重之和为 1"""
        total = sum(WEIGHTS.values())
        assert abs(total - 1.0) < 0.001


# ──────────────── BudgetBurnPredictor ────────────────


class TestBudgetBurnPredictor:
    """预算消耗预测器测试"""

    def setup_method(self):
        self.engine = BudgetBurnPredictor()

    def test_linear_regression_perfect(self):
        """完美线性关系"""
        xs = [0, 1, 2, 3, 4]
        ys = [10, 20, 30, 40, 50]
        slope, intercept = self.engine._linear_regression(xs, ys)
        assert abs(slope - 10) < 0.001
        assert abs(intercept - 10) < 0.001

    def test_linear_regression_constant(self):
        """常数 y"""
        xs = [0, 1, 2, 3]
        ys = [50, 50, 50, 50]
        slope, intercept = self.engine._linear_regression(xs, ys)
        assert abs(slope) < 0.001
        assert abs(intercept - 50) < 0.001

    def test_linear_regression_empty(self):
        """空数据"""
        slope, intercept = self.engine._linear_regression([], [])
        assert slope == 0.0
        assert intercept == 0.0

    def test_confidence_high(self):
        """MAPE < 10% → high"""
        assert self.engine._confidence(0.05) == "high"
        assert self.engine._confidence(0.09) == "high"

    def test_confidence_medium(self):
        """MAPE 10-20% → medium"""
        assert self.engine._confidence(0.15) == "medium"

    def test_confidence_low(self):
        """MAPE 20-30% → low"""
        assert self.engine._confidence(0.25) == "low"

    def test_confidence_very_low(self):
        """MAPE > 30% → very_low"""
        assert self.engine._confidence(0.50) == "very_low"

    def test_seasonal_factors_exist_for_all_months(self):
        """季节因子覆盖 12 月"""
        for m in range(1, 13):
            assert m in SEASONAL_FACTORS
            assert 0.5 <= SEASONAL_FACTORS[m] <= 1.5

    @pytest.mark.asyncio
    async def test_predict_full_year_no_history(self):
        """无历史数据时返回 warning"""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await self.engine.predict_full_year(mock_db, "B001")
        assert "warning" in result
        assert result["confidence"] == "very_low"

    @pytest.mark.asyncio
    async def test_predict_budget_runway_no_history(self):
        """无历史时跑道为 None"""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await self.engine.predict_budget_runway(mock_db, "B001")
        assert result["runway_months"] is None

    @pytest.mark.asyncio
    async def test_predict_budget_runway_normal(self):
        """正常跑道计算"""
        # 模拟 6 月历史：平均 1000/月
        history_rows = [
            ("2024-01", 1000), ("2024-02", 1000), ("2024-03", 1000),
            ("2024-04", 1000), ("2024-05", 1000), ("2024-06", 1000),
        ]
        mock_budget = SimpleNamespace(
            budget_id="B001",
            annual_amount=12000.0,  # 1 年预算
            used_amount=3000.0,  # 已用 3 月
        )
        mock_db = MagicMock()
        # 第一次：拉取历史（fetch_monthly_consumption → .all()）
        mock_result1 = MagicMock()
        mock_result1.all.return_value = history_rows
        # 第二次：拉取 budget（select(BudgetItem) → .scalar_one_or_none()）
        mock_result2 = MagicMock()
        mock_result2.scalar_one_or_none.return_value = mock_budget

        # 顺序执行两次 execute
        mock_db.execute = AsyncMock(side_effect=[mock_result1, mock_result2])

        result = await self.engine.predict_budget_runway(mock_db, "B001")
        # available = 12000 - 3000 = 9000
        # avg_monthly = 1000
        # runway = 9 月
        assert result["runway_months"] == 9.0
        assert result["risk_level"] == "low"
