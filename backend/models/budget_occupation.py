from __future__ import annotations
from sqlalchemy import Column, DateTime, Float, Integer, String, func
from models.database import Base


class BudgetOccupation(Base):
    __tablename__ = "budget_occupations"
    id = Column(Integer, primary_key=True, autoincrement=True)
    budget_id = Column(String(50), nullable=False, comment="预算项目ID")
    expense_id = Column(String(50), comment="关联报销单号")
    occupied_amount = Column(Float, default=0, comment="占用金额")
    status = Column(String(20), default="占用中", comment="占用中/已释放/已核销")
    occupied_at = Column(DateTime, server_default=func.now())
    released_at = Column(DateTime, comment="释放时间")
