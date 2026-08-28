"""
RoleDashboardEngine 单元测试 — v8.0 模块 H
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from engines.role_dashboard import RoleDashboardEngine, SUPPORTED_ROLES


def make_mock_db():
    """创建 mock DB"""
    db = MagicMock()
    db.execute = AsyncMock()
    return db


class TestRoleDashboardEngineBasic:
    """基础功能测试"""

    def test_supported_roles(self):
        assert "cfo" in SUPPORTED_ROLES
        assert "center_lead" in SUPPORTED_ROLES
        assert "product_manager" in SUPPORTED_ROLES

    def test_engine_instantiation(self):
        engine = RoleDashboardEngine()
        assert engine is not None

    @pytest.mark.asyncio
    async def test_invalid_role_raises(self):
        engine = RoleDashboardEngine()
        db = make_mock_db()
        with pytest.raises(ValueError, match="Unsupported role"):
            await engine.build(role="invalid", db=db)


class TestRoleDashboardBuildCFO:
    """CFO 视图测试"""

    @pytest.mark.asyncio
    async def test_cfo_returns_dict(self):
        engine = RoleDashboardEngine()
        db = make_mock_db()

        # 设置 mock：3 次 execute（budget, alerts, strategic）
        # 第一次：预算项
        budget_mock = MagicMock()
        budget_scalars = MagicMock()
        budget_scalars.all = MagicMock(return_value=[])
        budget_mock.scalars = MagicMock(return_value=budget_scalars)

        # 第二次：预警
        alert_mock = MagicMock()
        alert_scalars = MagicMock()
        alert_scalars.all = MagicMock(return_value=[])
        alert_mock.scalars = MagicMock(return_value=alert_scalars)

        # 第三次：战略举措
        si_mock = MagicMock()
        si_scalars = MagicMock()
        si_scalars.all = MagicMock(return_value=[])
        si_mock.scalars = MagicMock(return_value=si_scalars)

        db.execute = AsyncMock(side_effect=[budget_mock, alert_mock, si_mock])

        result = await engine.build(role="cfo", db=db, period="2024-09")

        assert result["role"] == "cfo"
        assert "title" in result
        assert "kpis" in result
        assert "diagnosis_cards" in result
        assert "frameworks" in result
        # 9 卡都有
        assert len(result["diagnosis_cards"]) == 9
        # 4 框架都有
        assert len(result["frameworks"]) == 4


class TestRoleDashboardBuildCenterLead:
    """中心负责人视图测试"""

    @pytest.mark.asyncio
    async def test_center_lead_returns_dict(self):
        engine = RoleDashboardEngine()
        db = make_mock_db()

        # 设置 mock 调用序列：
        # 1) center_id 查询 (select BudgetItem.center_id distinct limit 1)
        # 2) budget 聚合
        # 3) alerts 查询
        # 4) ExecutionRate 3gap
        # 5) budget items for 3list
        # 6) pending approvals count
        center_mock = MagicMock()
        center_mock.scalar_one_or_none = MagicMock(return_value="C01")

        budget_scalars = MagicMock()
        budget_scalars.all = MagicMock(return_value=[])
        budget_mock = MagicMock()
        budget_mock.scalars = MagicMock(return_value=budget_scalars)

        alert_scalars = MagicMock()
        alert_scalars.all = MagicMock(return_value=[])
        alert_mock = MagicMock()
        alert_mock.scalars = MagicMock(return_value=alert_scalars)

        rate_mock = MagicMock()
        rate_mock.scalar_one_or_none = MagicMock(return_value=None)

        approval_mock = MagicMock()
        approval_mock.scalar = MagicMock(return_value=0)

        db.execute = AsyncMock(side_effect=[
            center_mock,        # 中心 ID 查询
            budget_mock,        # 预算项
            alert_mock,         # 预警
            rate_mock,          # 3gap
            budget_mock,        # 3list
            approval_mock,      # pending count
        ])

        result = await engine.build(role="center_lead", db=db, center_id="C01")

        assert result["role"] == "center_lead"
        assert result["center_id"] == "C01"
        assert "three_gap" in result
        assert "three_list" in result


class TestRoleDashboardBuildProductManager:
    """品种经理视图测试"""

    @pytest.mark.asyncio
    async def test_product_manager_returns_dict(self):
        engine = RoleDashboardEngine()
        db = make_mock_db()

        budget_scalars = MagicMock()
        budget_scalars.all = MagicMock(return_value=[])
        budget_mock = MagicMock()
        budget_mock.scalars = MagicMock(return_value=budget_scalars)

        alert_scalars = MagicMock()
        alert_scalars.all = MagicMock(return_value=[])
        alert_mock = MagicMock()
        alert_mock.scalars = MagicMock(return_value=alert_scalars)

        db.execute = AsyncMock(side_effect=[budget_mock, alert_mock])

        result = await engine.build(role="product_manager", db=db, l1_code="01")

        assert result["role"] == "product_manager"
        assert result["l1_code"] == "01"
        assert "roi_summary" in result
        assert "policy_risk" in result
        assert "product_distribution" in result


class TestRoleDashboardHelpers:
    """辅助方法测试"""

    def test_compute_roi_empty(self):
        from engines.role_dashboard import RoleDashboardEngine
        result = RoleDashboardEngine._compute_roi([])
        assert result["high_count"] == 0
        assert result["medium_count"] == 0
        assert result["low_count"] == 0

    def test_assess_policy_risk_low(self):
        from engines.role_dashboard import RoleDashboardEngine
        risk = RoleDashboardEngine._assess_policy_risk([], [])
        assert risk["risk_level"] == "低"

    def test_assess_policy_risk_high(self):
        from engines.role_dashboard import RoleDashboardEngine
        # 模拟 L1-01 预算项 + 红色预警
        item = MagicMock()
        item.l1_code = "01"
        alerts = [{"level": "红色", "type": "test"}]
        risk = RoleDashboardEngine._assess_policy_risk([item], alerts)
        assert risk["risk_level"] == "高"
