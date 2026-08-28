from __future__ import annotations

from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer, String, Text, JSON, func
)

from models.database import Base


class ImpactChain(Base):
    __tablename__ = "impact_chains"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_operation = Column(String(200), nullable=False, comment="源头操作")
    operation_type = Column(String(50), comment="操作类型(budget_change/expense_overrun/strategic_shift)")
    operation_params = Column(JSON, default=dict, comment="操作参数")
    affected_domains = Column(JSON, default=list, comment="影响域列表")
    overall_risk = Column(String(10), default="低", comment="总体风险等级(低/中/高)")
    status = Column(String(20), default="已评估", comment="已评估/已追踪/已缓解")
    created_at = Column(DateTime, server_default=func.now())


class ImpactNode(Base):
    __tablename__ = "impact_nodes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chain_id = Column(Integer, nullable=False, comment="所属影响链ID")
    impact_domain = Column(String(50), nullable=False, comment="影响域(budget/expense/alert/cashflow/strategic)")
    impact_description = Column(Text, comment="影响描述")
    impact_severity = Column(String(10), default="低", comment="影响程度(低/中/高)")
    impact_details = Column(JSON, default=dict, comment="影响详情")
    mitigation_suggestion = Column(Text, comment="缓解方案")
    created_at = Column(DateTime, server_default=func.now())


# ─── v8.0 Module I：决策沙盘 + 影响归因 + Pareto ───────────────


class DecisionSandbox(Base):
    """决策沙盘：执行前模拟影响（v8.0 Module I-A）"""
    __tablename__ = "decision_sandboxes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_name = Column(String(200), nullable=False, comment="场景名称")
    operation_type = Column(String(50), nullable=False, comment="操作类型")
    operation_params = Column(JSON, default=dict, comment="操作参数")
    prediction = Column(JSON, default=dict, comment="预测结果（5 域影响）")
    overall_risk = Column(String(10), default="低", comment="总体风险")
    reversibility = Column(String(20), default="可逆", comment="可逆性：可逆/部分可逆/不可逆")
    confidence = Column(Float, default=0.0, comment="预测置信度 0-1")
    pareto_score = Column(Float, default=0.0, comment="Pareto 综合得分")
    status = Column(String(20), default="已模拟", comment="已模拟/已执行/已废弃")
    created_at = Column(DateTime, server_default=func.now())


class ImpactAttribution(Base):
    """影响归因：反向追溯（v8.0 Module I-C）"""
    __tablename__ = "impact_attributions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    target_metric = Column(String(100), nullable=False, comment="目标指标")
    target_period = Column(String(20), comment="目标期间")
    observed_value = Column(Float, comment="观测值")
    baseline_value = Column(Float, comment="基线值")
    delta = Column(Float, comment="变化量")
    root_operations = Column(JSON, default=list, comment="根操作列表（贡献度排序）")
    confidence = Column(Float, default=0.0, comment="归因置信度")
    explanation = Column(Text, comment="自然语言解释")
    created_at = Column(DateTime, server_default=func.now())


class ParetoFrontier(Base):
    """Pareto 前沿：多目标优化（v8.0 Module I-D）"""
    __tablename__ = "pareto_frontiers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_id = Column(Integer, comment="关联沙盘场景 ID")
    objective_budget_compliance = Column(Float, comment="目标 1: 预算合规度 0-100")
    objective_business_impact = Column(Float, comment="目标 2: 业务影响度 0-100")
    objective_strategic_alignment = Column(Float, comment="目标 3: 战略对齐度 0-100")
    objective_cashflow_stability = Column(Float, comment="目标 4: 现金流稳定性 0-100")
    is_pareto_optimal = Column(Boolean, default=False, comment="是否 Pareto 最优")
    rank = Column(Integer, default=0, comment="综合排名")
    solution_params = Column(JSON, default=dict, comment="方案参数")
    created_at = Column(DateTime, server_default=func.now())
