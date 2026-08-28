from __future__ import annotations
from sqlalchemy import Column, DateTime, Float, Integer, String, Text, JSON, func
from models.database import Base


class ZBBReview(Base):
    __tablename__ = "zbb_reviews"
    id = Column(Integer, primary_key=True, autoincrement=True)
    period = Column(String(10), nullable=False, comment="审视期 YYYY")
    status = Column(String(20), default="启动", comment="启动/编制中/排序中/已审批/已执行")
    total_budget_constraint = Column(Float, default=0, comment="总预算约束")
    decision_unit_count = Column(Integer, default=0, comment="决策单元数量")
    created_at = Column(DateTime, server_default=func.now())


class ZBBDecisionUnit(Base):
    __tablename__ = "zbb_decision_units"
    id = Column(Integer, primary_key=True, autoincrement=True)
    review_id = Column(Integer, nullable=False, comment="所属审视ID")
    name = Column(String(200), nullable=False, comment="单元名称")
    owner = Column(String(100), comment="负责人")
    scope = Column(Text, comment="范围描述")
    rank = Column(Integer, default=0, comment="排序")
    strategic_value_score = Column(Float, default=0, comment="战略价值评分0-100")
    created_at = Column(DateTime, server_default=func.now())


class ZBBPackage(Base):
    __tablename__ = "zbb_packages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    unit_id = Column(Integer, nullable=False, comment="决策单元ID")
    level = Column(String(20), nullable=False, comment="最低/当前/增强")
    amount = Column(Float, default=0, comment="金额")
    justification = Column(Text, comment="必要性说明")
    strategic_alignment = Column(Float, default=0, comment="战略对齐度0-100")
    created_at = Column(DateTime, server_default=func.now())
