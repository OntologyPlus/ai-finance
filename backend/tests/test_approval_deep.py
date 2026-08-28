"""
审批流程深化模块单元测试
========================

覆盖 v7.0 新增的：
- ApprovalRouter: 智能审批人推荐
- ApprovalBottleneckEngine: 瓶颈智能识别
- 动态阈值 ORM: ApprovalThresholdConfig + ApproverProfile

运行：cd backend && pytest tests/test_approval_deep.py -v
"""
from __future__ import annotations

import sys
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engines.approval_bottleneck import ApprovalBottleneckEngine
from engines.approval_router import ApprovalRouter
from models.approval_config import ApprovalThresholdConfig, ApproverProfile


# ────── 1. 智能审批人推荐 ──────


class TestApprovalRouter:
    """智能审批人推荐"""

    @pytest.mark.asyncio
    async def test_recommend_with_matching_profiles(self, mock_db):
        """有匹配画像时返回 Top N"""
        p1 = MagicMock(spec=ApproverProfile)
        p1.user_id = "u001"
        p1.user_name = "张三"
        p1.role = "部门负责人"
        p1.center_id = "C001"
        p1.avg_response_hours = 12.0
        p1.total_approved = 50
        p1.reject_rate = 0.05
        p1.delegation_count = 1
        p1.is_active = 1
        p1.preferred_categories = None
        p1.active_hours = None
        p1.created_at = datetime.now()
        p1.updated_at = datetime.now()

        p2 = MagicMock(spec=ApproverProfile)
        p2.user_id = "u002"
        p2.user_name = "李四"
        p2.role = "部门负责人"
        p2.center_id = "C001"
        p2.avg_response_hours = 36.0
        p2.total_approved = 200
        p2.reject_rate = 0.10
        p2.delegation_count = 2
        p2.is_active = 1
        p2.preferred_categories = None
        p2.active_hours = None
        p2.created_at = datetime.now()
        p2.updated_at = datetime.now()

        async def fake_execute(stmt):
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [p1, p2]
            return mock_result
        mock_db.execute = fake_execute

        router = ApprovalRouter()
        result = await router.recommend_approvers(
            mock_db, target_role="部门负责人", center_id="C001", amount=50000
        )
        assert len(result.recommendations) == 2
        # p1 响应更快，应排第一
        assert result.recommendations[0].user_id == "u001"
        assert result.recommendations[0].confidence >= result.recommendations[1].confidence
        assert result.signal_light in ("green", "yellow")

    @pytest.mark.asyncio
    async def test_recommend_no_profiles(self, mock_db):
        """无匹配画像时给出 fallback"""
        async def fake_execute(stmt):
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            return mock_result
        mock_db.execute = fake_execute

        router = ApprovalRouter()
        result = await router.recommend_approvers(
            mock_db, target_role="部门负责人", center_id="C001"
        )
        assert result.recommendations == []
        assert result.signal_light == "red"
        assert result.fallback  # 非空

    @pytest.mark.asyncio
    async def test_confidence_calculation(self, mock_db):
        """置信度计算：中心匹配 + 速度 + 驳回率"""
        p = MagicMock(spec=ApproverProfile)
        p.user_id = "u001"
        p.user_name = "u001"
        p.role = "中心总经理"
        p.center_id = "C001"  # 中心匹配
        p.avg_response_hours = 8.0  # 响应快
        p.total_approved = 100  # 经验丰富
        p.reject_rate = 0.02  # 驳回率低
        p.delegation_count = 0
        p.is_active = 1
        p.preferred_categories = None
        p.active_hours = None
        p.created_at = datetime.now()
        p.updated_at = datetime.now()

        async def fake_execute(stmt):
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [p]
            return mock_result
        mock_db.execute = fake_execute

        router = ApprovalRouter()
        result = await router.recommend_approvers(
            mock_db, target_role="中心总经理", center_id="C001"
        )
        # 高匹配 + 快响应 + 低驳回 → 高置信度
        assert result.recommendations[0].confidence >= 0.7
        assert result.signal_light == "green"

    @pytest.mark.asyncio
    async def test_low_confidence_yellow(self, mock_db):
        """低置信度 → 黄色信号"""
        p = MagicMock(spec=ApproverProfile)
        p.user_id = "u001"
        p.user_name = "u001"
        p.role = "财经BP"
        p.center_id = "C999"  # 中心不匹配
        p.avg_response_hours = 60.0  # 响应慢
        p.total_approved = 5
        p.reject_rate = 0.30  # 驳回率高
        p.delegation_count = 5
        p.is_active = 1
        p.preferred_categories = None
        p.active_hours = None
        p.created_at = datetime.now()
        p.updated_at = datetime.now()

        async def fake_execute(stmt):
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [p]
            return mock_result
        mock_db.execute = fake_execute

        router = ApprovalRouter()
        result = await router.recommend_approvers(
            mock_db, target_role="财经BP", center_id="C001"
        )
        # 低质量画像 → 黄/红
        assert result.signal_light in ("yellow", "red")


# ────── 2. 审批瓶颈识别 ──────


class TestBottleneckEngine:
    """审批瓶颈智能识别"""

    @pytest.mark.asyncio
    async def test_no_records(self, mock_db):
        """无记录 → 绿灯"""
        async def fake_execute(stmt):
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            return mock_result
        mock_db.execute = fake_execute

        engine = ApprovalBottleneckEngine()
        result = await engine.analyze_bottlenecks(mock_db, period="2024-06")
        assert result.signal_light == "green"
        assert result.bottlenecks == []
        assert result.worst_step is None

    @pytest.mark.asyncio
    async def test_critical_bottleneck_detected(self, mock_db):
        """critical 瓶颈被识别（平均时长 > 72h）"""
        records = []
        # 步骤 1 耗时 5h（健康）
        for i in range(5):
            r = MagicMock()
            r.approval_step = 1
            r.approver_role = "直属主管"
            r.created_at = datetime(2024, 6, 1, 9, 0, 0)
            r.approved_at = datetime(2024, 6, 1, 14, 0, 0)  # 5h
            r.is_overdue = False
            r.approval_action = "通过"
            records.append(r)
        # 步骤 2 耗时 96h（critical）
        for i in range(5):
            r = MagicMock()
            r.approval_step = 2
            r.approver_role = "中心总经理"
            r.created_at = datetime(2024, 6, 1, 9, 0, 0)
            r.approved_at = datetime(2024, 6, 5, 9, 0, 0)  # 96h
            r.is_overdue = True
            r.approval_action = "通过"
            records.append(r)

        async def fake_execute(stmt):
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = records
            return mock_result
        mock_db.execute = fake_execute

        engine = ApprovalBottleneckEngine()
        result = await engine.analyze_bottlenecks(mock_db, period="2024-06")
        assert result.signal_light == "red"
        assert result.worst_step == "中心总经理"
        assert any(b.severity == "critical" for b in result.bottlenecks)

    @pytest.mark.asyncio
    async def test_healthy_and_bottleneck_steps_separated(self, mock_db):
        """健康步骤和瓶颈步骤分离"""
        records = []
        for i in range(3):
            r = MagicMock()
            r.approval_step = 1
            r.approver_role = "直属主管"
            r.created_at = datetime(2024, 6, 1, 9, 0, 0)
            r.approved_at = datetime(2024, 6, 1, 13, 0, 0)  # 4h
            r.is_overdue = False
            r.approval_action = "通过"
            records.append(r)
        # 瓶颈步骤
        for i in range(3):
            r = MagicMock()
            r.approval_step = 2
            r.approver_role = "财经BP"
            r.created_at = datetime(2024, 6, 1, 9, 0, 0)
            r.approved_at = datetime(2024, 6, 4, 17, 0, 0)  # 80h
            r.is_overdue = True
            r.approval_action = "通过"
            records.append(r)

        async def fake_execute(stmt):
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = records
            return mock_result
        mock_db.execute = fake_execute

        engine = ApprovalBottleneckEngine()
        result = await engine.analyze_bottlenecks(mock_db, period="2024-06")
        assert "直属主管" in result.healthy_steps
        assert any(b.step_name == "财经BP" for b in result.bottlenecks)

    @pytest.mark.asyncio
    async def test_top_n_bottlenecks(self, mock_db):
        """Top N 瓶颈数控制"""
        records = []
        for step_idx in range(1, 6):
            r = MagicMock()
            r.approval_step = step_idx
            r.approver_role = f"步骤{step_idx}"
            r.created_at = datetime(2024, 6, 1, 9, 0, 0)
            r.approved_at = datetime(2024, 6, 5, 9, 0, 0)  # 100h
            r.is_overdue = True
            r.approval_action = "通过"
            records.append(r)

        async def fake_execute(stmt):
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = records
            return mock_result
        mock_db.execute = fake_execute

        engine = ApprovalBottleneckEngine()
        result = await engine.analyze_bottlenecks(mock_db, period="2024-06", top_n=3)
        assert len(result.bottlenecks) == 3

    @pytest.mark.asyncio
    async def test_severity_judgment(self):
        """严重度判定逻辑"""
        engine = ApprovalBottleneckEngine()
        # low: 短时长 + 低超时率
        assert engine._judge_severity(2.0, 0.01) == "low"
        # medium: 48h + 10%
        assert engine._judge_severity(48.0, 0.10) == "medium"
        # high: 60h
        assert engine._judge_severity(60.0, 0.20) == "high"
        # critical: 80h
        assert engine._judge_severity(80.0, 0.40) == "critical"


# ────── 3. 动态阈值 ORM ──────


class TestApprovalThresholdConfig:
    """审批动态阈值配置 ORM"""

    def test_default_tiers(self):
        """默认 5 档阈值（通过显式构造测试）"""
        cfg = ApprovalThresholdConfig(
            config_name="默认配置",
            tier1_amount=50000,
            tier2_amount=100000,
            tier3_amount=500000,
            tier4_amount=1000000,
            tier5_amount=5000000,
            tier1_role="直属主管",
            tier5_role="分管副总裁",
        )
        assert cfg.tier1_amount == 50000
        assert cfg.tier2_amount == 100000
        assert cfg.tier3_amount == 500000
        assert cfg.tier4_amount == 1000000
        assert cfg.tier5_amount == 5000000
        assert cfg.tier1_role == "直属主管"
        assert cfg.tier5_role == "分管副总裁"

    def test_custom_tiers(self):
        """自定义阈值"""
        cfg = ApprovalThresholdConfig(
            config_name="科研中心配置",
            center_id="R001",
            tier1_amount=10000,
            tier2_amount=50000,
            tier3_amount=200000,
            tier4_amount=500000,
            tier5_amount=2000000,
            tier1_role="项目负责人",
            tier5_role="科研副总裁",
        )
        assert cfg.center_id == "R001"
        assert cfg.tier3_amount == 200000
        assert cfg.tier5_role == "科研副总裁"

    def test_tablename(self):
        """表名正确"""
        assert ApprovalThresholdConfig.__tablename__ == "approval_threshold_configs"
        assert ApproverProfile.__tablename__ == "approver_profiles"
