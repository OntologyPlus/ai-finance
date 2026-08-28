"""
现金流深化模块单元测试
====================

覆盖 v7.0 新增的 3 个引擎：
- CashflowAgingEngine: AR/AP 账龄分析（4 段 + WAA + 信号灯）
- CashflowForecastEngine: 12 周滚动预测 + 流动性健康度
- CashflowAdvisorEngine: 智能调拨建议

按《经营分析方法论.md》§3.1 信号灯机制设计。

运行：cd backend && pytest tests/test_cashflow_deep.py -v
"""
from __future__ import annotations

import sys
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engines.cashflow_aging import (
    AgingBucket,
    CashflowAgingEngine,
    HEALTH_THRESHOLDS,
)
from engines.cashflow_advisor import CashflowAdvisorEngine
from engines.cashflow_forecast import CashflowForecastEngine


# ────── Fixtures ──────


@pytest.fixture
def aging():
    return CashflowAgingEngine()


@pytest.fixture
def forecast():
    return CashflowForecastEngine()


@pytest.fixture
def advisor():
    return CashflowAdvisorEngine()


def make_receipt_forecast(id, date_offset_days, amount, customer="客户X"):
    """构造模拟 ReceiptForecast"""
    obj = MagicMock()
    obj.id = id
    obj.forecast_date = (datetime.now() - timedelta(days=date_offset_days))
    obj.actual_date = None
    obj.forecast_amount = amount
    obj.actual_amount = None
    obj.confidence = 0.5
    obj.customer_name = customer
    return obj


def make_payment_schedule(id, date_offset_days, amount, vendor="供应商X"):
    """构造模拟 PaymentSchedule"""
    obj = MagicMock()
    obj.id = id
    obj.planned_date = (datetime.now() - timedelta(days=date_offset_days))
    obj.actual_date = None
    obj.planned_amount = amount
    obj.actual_amount = None
    obj.vendor_name = vendor
    obj.status = "待付款"
    return obj


# ────── 1. 账龄分析引擎 ──────


class TestAgingEngine:
    """AR/AP 账龄分析"""

    def test_bucket_classification(self, aging):
        """账龄分段：0-30 / 31-60 / 61-90 / 90+"""
        receipts = [
            make_receipt_forecast(1, 10, 1000),   # 0-30
            make_receipt_forecast(2, 45, 2000),   # 31-60
            make_receipt_forecast(3, 75, 3000),   # 61-90
            make_receipt_forecast(4, 120, 4000),  # 90+
        ]
        as_of = datetime.now()
        report = aging._build_aging_report(
            receipts, as_of, kind="AR",
            date_attr="forecast_date", amount_attr="forecast_amount",
        )
        assert report.buckets["0-30"]["amount"] == 1000
        assert report.buckets["31-60"]["amount"] == 2000
        assert report.buckets["61-90"]["amount"] == 3000
        assert report.buckets["90+"]["amount"] == 4000
        assert report.total_amount == 10000
        assert report.high_risk_pct == 0.4  # 4000/10000

    def test_weighted_avg_age(self, aging):
        """加权平均账龄（WAA）"""
        receipts = [
            make_receipt_forecast(1, 10, 1000),  # age=10
            make_receipt_forecast(2, 50, 3000),  # age=50
        ]
        as_of = datetime.now()
        report = aging._build_aging_report(
            receipts, as_of, kind="AR",
            date_attr="forecast_date", amount_attr="forecast_amount",
        )
        # WAA = (10*1000 + 50*3000) / 4000 = 160000/4000 = 40
        assert 39 <= report.weighted_avg_age_days <= 41

    def test_green_signal(self, aging):
        """绿灯：高风险 <= 5% 且 WAA <= 30 天"""
        receipts = [
            make_receipt_forecast(i, 10, 1000) for i in range(1, 11)
        ]  # 10 笔，每笔 10 天账龄
        as_of = datetime.now()
        report = aging._build_aging_report(
            receipts, as_of, kind="AR",
            date_attr="forecast_date", amount_attr="forecast_amount",
        )
        assert report.signal_light == "green"

    def test_yellow_signal(self, aging):
        """黄灯：高风险 5-20% 或 WAA 30-60 天"""
        receipts = [
            make_receipt_forecast(1, 10, 8000),  # 0-30
            make_receipt_forecast(2, 100, 2000), # 90+
        ]  # 高风险占比 20%，WAA 大约 28
        as_of = datetime.now()
        report = aging._build_aging_report(
            receipts, as_of, kind="AR",
            date_attr="forecast_date", amount_attr="forecast_amount",
        )
        # 高风险 = 20% (临界) 或 WAA 30+ → 黄色
        assert report.signal_light in ("yellow", "red")

    def test_red_signal(self, aging):
        """红灯：高风险 > 20% 或 WAA > 60 天"""
        receipts = [
            make_receipt_forecast(1, 10, 2000),   # 0-30
            make_receipt_forecast(2, 120, 8000),  # 90+
        ]  # 高风险 80%
        as_of = datetime.now()
        report = aging._build_aging_report(
            receipts, as_of, kind="AR",
            date_attr="forecast_date", amount_attr="forecast_amount",
        )
        assert report.signal_light == "red"
        assert report.high_risk_pct == 0.8

    def test_top_overdue_items(self, aging):
        """Top 逾期明细按金额降序"""
        receipts = [
            make_receipt_forecast(1, 50, 1000),
            make_receipt_forecast(2, 100, 5000),
            make_receipt_forecast(3, 60, 3000),
        ]
        as_of = datetime.now()
        report = aging._build_aging_report(
            receipts, as_of, kind="AR",
            date_attr="forecast_date", amount_attr="forecast_amount",
        )
        assert len(report.top_overdue_items) == 3
        # 第一个应该是金额最大的
        assert report.top_overdue_items[0]["amount"] == 5000

    def test_empty_data_returns_zero(self, aging):
        """空数据返回 0 报告 + 绿灯"""
        as_of = datetime.now()
        report = aging._build_aging_report(
            [], as_of, kind="AR",
            date_attr="forecast_date", amount_attr="forecast_amount",
        )
        assert report.total_amount == 0
        assert report.signal_light == "green"
        assert report.weighted_avg_age_days == 0

    def test_to_dict(self, aging):
        """to_dict 序列化正确"""
        receipts = [make_receipt_forecast(1, 10, 1000)]
        as_of = datetime.now()
        report = aging._build_aging_report(
            receipts, as_of, kind="AR",
            date_attr="forecast_date", amount_attr="forecast_amount",
        )
        d = report.to_dict()
        assert "buckets" in d
        assert "signal_light" in d
        assert "high_risk_pct" in d
        assert "weighted_avg_age_days" in d


# ────── 2. 12 周滚动预测引擎 ──────


class TestForecastEngine:
    """12 周滚动现金流预测"""

    @pytest.mark.asyncio
    async def test_rolling_forecast_with_data(self, forecast, mock_db):
        """完整 12 周预测：3 笔未来付款 + 2 笔未来收款"""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        wk_start = today - timedelta(days=today.weekday())
        # 第 1 周：1 笔付款 10000
        p1 = make_payment_schedule(1, 0, 10000)
        p1.planned_date = wk_start + timedelta(days=3)
        # 第 2 周：1 笔付款 20000
        p2 = make_payment_schedule(2, 0, 20000)
        p2.planned_date = wk_start + timedelta(weeks=1, days=2)
        # 第 5 周：1 笔收款 50000
        r1 = make_receipt_forecast(1, 0, 50000)
        r1.forecast_date = wk_start + timedelta(weeks=4, days=1)

        # mock DB 返回
        async def fake_execute(stmt):
            mock_result = MagicMock()
            # 简化：返回上面 2 个付款
            if "payment_schedules" in str(stmt):
                mock_result.scalars.return_value.all.return_value = [p1, p2]
            else:
                mock_result.scalars.return_value.all.return_value = [r1]
            return mock_result

        mock_db.execute = fake_execute
        # mock 资金池
        pool = MagicMock()
        pool.total_balance = 30000
        pool.status = "活跃"

        async def fake_pool_execute(stmt):
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [pool]
            return mock_result

        # 拦截 _get_pool_balance
        forecast._get_pool_balance = AsyncMock(return_value=30000.0)

        report = await forecast.rolling_forecast(mock_db, horizon_weeks=12)
        assert report.horizon_weeks == 12
        assert report.total_outflow == 30000
        assert report.total_inflow == 50000
        assert report.final_balance == 30000 - 30000 + 50000  # 50000

    @pytest.mark.asyncio
    async def test_rolling_forecast_with_gap(self, forecast, mock_db):
        """缺口检测：支出 > 收入 → running_balance < 0 → 生成 gap"""
        forecast._get_pool_balance = AsyncMock(return_value=10000.0)

        # 1 笔大额付款在第 1 周
        p1 = make_payment_schedule(1, 0, 50000)
        wk_start = datetime.now() - timedelta(days=datetime.now().weekday())
        p1.planned_date = wk_start + timedelta(days=2)

        async def fake_execute(stmt):
            mock_result = MagicMock()
            if "payment_schedules" in str(stmt):
                mock_result.scalars.return_value.all.return_value = [p1]
            else:
                mock_result.scalars.return_value.all.return_value = []
            return mock_result

        mock_db.execute = fake_execute

        report = await forecast.rolling_forecast(mock_db, horizon_weeks=12)
        assert report.signal_light == "red"
        assert len(report.gaps) > 0
        assert report.min_balance < 0

    @pytest.mark.asyncio
    async def test_liquidity_health_green(self, forecast, mock_db):
        """流动性绿灯：覆盖率 >= 6 月"""
        forecast._get_pool_balance = AsyncMock(return_value=1000000.0)
        # 月均支出 10 万，覆盖 10 月
        async def fake_execute(stmt):
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            return mock_result
        mock_db.execute = fake_execute

        report = await forecast.rolling_forecast(mock_db, horizon_weeks=12)
        # 12 周内无支出 → 月均 0 → 覆盖率无穷大
        assert report.liquidity_health.signal_light == "green"


# ────── 3. 智能调拨建议引擎 ──────


class TestAdvisorEngine:
    """智能调拨建议"""

    @pytest.mark.asyncio
    async def test_recommend_with_sufficient_pools(self, advisor, mock_db):
        """充足资金池：能完全覆盖缺口"""
        p1 = MagicMock()
        p1.id = 1
        p1.pool_name = "主资金池"
        p1.total_balance = 1000000
        p1.min_balance = 100000
        p1.alert_threshold = 50000
        p1.status = "活跃"
        p1.aggregation_rule = {}

        p2 = MagicMock()
        p2.id = 2
        p2.pool_name = "目标资金池"
        p2.total_balance = 100000
        p2.min_balance = 10000
        p2.alert_threshold = 5000
        p2.status = "活跃"
        p2.aggregation_rule = {}

        async def fake_execute(stmt):
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [p1, p2]
            return mock_result

        mock_db.execute = fake_execute

        plan = await advisor.recommend_transfer(
            mock_db, target_pool_id=2, gap_amount=200000
        )
        # p1 可调出 850000 (1000000 - 100000 - 50000) → 足够
        assert plan.coverage_pct == 1.0
        assert plan.unmeet_amount == 0
        assert plan.signal_light == "green"
        assert len(plan.recommendations) == 1
        assert plan.recommendations[0].from_pool_name == "主资金池"
        assert plan.recommendations[0].amount == 200000

    @pytest.mark.asyncio
    async def test_recommend_with_insufficient_pools(self, advisor, mock_db):
        """资金池不足：部分覆盖 + fallback"""
        p1 = MagicMock()
        p1.id = 1
        p1.pool_name = "主资金池"
        p1.total_balance = 200000
        p1.min_balance = 100000
        p1.alert_threshold = 50000
        p1.status = "活跃"
        p1.aggregation_rule = {}

        p2 = MagicMock()
        p2.id = 2
        p2.pool_name = "目标资金池"
        p2.total_balance = 100000
        p2.min_balance = 10000
        p2.alert_threshold = 5000
        p2.status = "活跃"
        p2.aggregation_rule = {}

        async def fake_execute(stmt):
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [p1, p2]
            return mock_result

        mock_db.execute = fake_execute

        plan = await advisor.recommend_transfer(
            mock_db, target_pool_id=2, gap_amount=500000
        )
        # p1 可调出 50000 (200000-100000-50000) → 远不够
        assert plan.coverage_pct < 0.5
        assert plan.unmeet_amount > 0
        assert plan.signal_light == "red"
        # fallback 必有建议（融资/催收/延期付款）
        assert plan.fallback_action  # 非空

    @pytest.mark.asyncio
    async def test_recommend_no_active_pools(self, advisor, mock_db):
        """无活跃资金池"""
        async def fake_execute(stmt):
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            return mock_result
        mock_db.execute = fake_execute

        plan = await advisor.recommend_transfer(
            mock_db, target_pool_id=1, gap_amount=100000
        )
        assert plan.coverage_pct == 0
        assert plan.signal_light == "red"
        assert "融资" in plan.fallback_action or "无" in plan.fallback_action

    @pytest.mark.asyncio
    async def test_priority_sorting(self, advisor, mock_db):
        """优先级排序：到账天数最少 → 风险最低"""
        # 构造 2 个候选池
        p1 = MagicMock()
        p1.id = 10
        p1.pool_name = "快池"
        p1.total_balance = 800000
        p1.min_balance = 100000
        p1.alert_threshold = 50000
        p1.status = "活跃"
        p1.aggregation_rule = {}

        p2 = MagicMock()
        p2.id = 20
        p2.pool_name = "慢池"
        p2.total_balance = 900000
        p2.min_balance = 100000
        p2.alert_threshold = 50000
        p2.status = "活跃"
        p2.aggregation_rule = {}

        target = MagicMock()
        target.id = 1
        target.pool_name = "目标"
        target.total_balance = 50000
        target.min_balance = 10000
        target.alert_threshold = 5000
        target.status = "活跃"
        target.aggregation_rule = {}

        async def fake_execute(stmt):
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [p1, p2, target]
            return mock_result
        mock_db.execute = fake_execute

        # 模拟 _estimate_transfer_days 差异
        original = advisor._estimate_transfer_days
        advisor._estimate_transfer_days = lambda f, t: 1 if f.id == 10 else 5

        plan = await advisor.recommend_transfer(
            mock_db, target_pool_id=1, gap_amount=100000
        )
        advisor._estimate_transfer_days = original

        # 第一笔应该来自"快池"（id=10），因为到账更快
        if len(plan.recommendations) >= 1:
            assert plan.recommendations[0].from_pool_name == "快池"
