from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, JSON, func

from models.database import Base


class Scenario(Base):
    __tablename__ = "scenarios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, comment="情景名称")
    scenario_type = Column(String(20), nullable=False, comment="乐观/基准/悲观/压力测试")
    period = Column(String(10), comment="预算周期 YYYY")
    assumptions = Column(JSON, default=dict, comment="情景假设条件")
    budget_summary = Column(JSON, default=dict, comment="预算概要")
    status = Column(String(20), default="草稿", comment="草稿/已审批/已执行/已归档")
    created_at = Column(DateTime, server_default=func.now())


class ElasticBudget(Base):
    __tablename__ = "elastic_budgets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    budget_id = Column(String(50), nullable=False, comment="预算项目ID")
    driver_metric = Column(String(100), comment="驱动指标名称")
    base_volume = Column(Float, default=0, comment="基准业务量")
    base_amount = Column(Float, default=0, comment="基准金额")
    elasticity_coefficient = Column(Float, default=1.0, comment="弹性系数")
    current_volume = Column(Float, default=0, comment="当前业务量")
    adjusted_amount = Column(Float, default=0, comment="调整后金额")
    max_adjustment_ratio = Column(Float, default=0.3, comment="最大调整比例")
    created_at = Column(DateTime, server_default=func.now())


class BudgetReserve(Base):
    __tablename__ = "budget_reserves"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reserve_name = Column(String(200), nullable=False, comment="储备名称")
    total_amount = Column(Float, default=0, comment="总额")
    used_amount = Column(Float, default=0, comment="已用金额")
    available_amount = Column(Float, default=0, comment="可用金额")
    approval_required = Column(Integer, default=1, comment="是否需要审批 1=是")
    created_at = Column(DateTime, server_default=func.now())
