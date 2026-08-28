"""
审批动态阈值配置 ORM

按《经营分析方法论.md》§4.4 治理流程实现：
- 审批阈值可数据库配置（替代硬编码 100 万/50 万/25 万/10 万/5 万）
- 支持按中心/科目类型/法人等维度差异化
- 热更新（无需重启服务）
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, func

from models.database import Base


class ApprovalThresholdConfig(Base):
    """审批动态阈值配置"""
    __tablename__ = "approval_threshold_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_name = Column(String(100), nullable=False, comment="配置名称")
    center_id = Column(String(20), comment="中心ID（NULL=全局）")
    l1_code = Column(String(20), comment="L1 科目代码（NULL=全部）")
    legal_entity = Column(String(50), comment="法人（NULL=全部）")

    # 5 档阈值
    tier1_amount = Column(Float, default=50000, comment="Tier1 阈值（含）")
    tier2_amount = Column(Float, default=100000, comment="Tier2 阈值（含）")
    tier3_amount = Column(Float, default=500000, comment="Tier3 阈值（含）")
    tier4_amount = Column(Float, default=1000000, comment="Tier4 阈值（含）")
    tier5_amount = Column(Float, default=5000000, comment="Tier5 阈值")

    # 对应审批人角色（JSON 字符串）
    tier1_role = Column(String(50), default="直属主管")
    tier2_role = Column(String(50), default="部门负责人")
    tier3_role = Column(String(50), default="财经BP")
    tier4_role = Column(String(50), default="中心总经理")
    tier5_role = Column(String(50), default="分管副总裁")

    # 元数据
    is_active = Column(Integer, default=1, comment="1=启用 / 0=禁用")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


class ApprovalBottleneckRecord(Base):
    """审批瓶颈记录（按链路步骤聚合）"""
    __tablename__ = "approval_bottleneck_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    period = Column(String(10), nullable=False, comment="统计期 YYYY-MM")
    step_name = Column(String(50), nullable=False, comment="审批步骤")
    step_index = Column(Integer, comment="步骤序号")
    avg_duration_hours = Column(Float, comment="平均处理时长（小时）")
    max_duration_hours = Column(Float, comment="最大处理时长")
    pending_count = Column(Integer, default=0, comment="待处理数")
    timeout_count = Column(Integer, default=0, comment="超时数")
    total_count = Column(Integer, default=0, comment="总处理数")
    severity = Column(String(20), comment="严重度：low/medium/high/critical")
    root_cause = Column(Text, comment="根因分析")
    created_at = Column(DateTime, server_default=func.now())


class ApproverProfile(Base):
    """审批人画像（用于智能推荐）"""
    __tablename__ = "approver_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), nullable=False, comment="审批人ID")
    user_name = Column(String(100), comment="审批人姓名")
    role = Column(String(50), nullable=False, comment="角色")
    center_id = Column(String(20), comment="中心")

    # 历史模式
    avg_response_hours = Column(Float, default=24.0, comment="平均响应时长")
    total_approved = Column(Integer, default=0, comment="累计审批数")
    reject_rate = Column(Float, default=0.0, comment="驳回率")
    delegation_count = Column(Integer, default=0, comment="委派次数")

    # 偏好（JSON 字符串）
    preferred_categories = Column(Text, comment="偏好处理的科目类型 JSON")
    active_hours = Column(Text, comment="活跃时段 JSON")

    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
