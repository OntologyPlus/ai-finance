from sqlalchemy import Column, String, Text, Boolean, DateTime, Integer, Numeric
from sqlalchemy.sql import func
from models.database import Base


class Milestone(Base):
    """B类预算里程碑"""
    __tablename__ = "milestone"

    milestone_id = Column(String(20), primary_key=True, comment="里程碑ID")
    budget_id = Column(String(20), nullable=False, comment="关联预算项目ID")
    name = Column(String(200), nullable=False, comment="里程碑名称")
    planned_date = Column(DateTime, comment="计划完成日期")
    actual_date = Column(DateTime, comment="实际完成日期")
    status = Column(
        String(20),
        nullable=False,
        default="pending",
        comment="pending/completed/overdue/cancelled",
    )
    evidence = Column(Text, comment="完成证据")
    quarter = Column(Integer, comment="季度(1-4)")
    amount_release = Column(Numeric(15, 2), comment="完成后释放金额")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
