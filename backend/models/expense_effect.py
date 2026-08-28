from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime, Date, ForeignKey, func
from models.database import Base


class ExpenseEffectTracking(Base):
    """报销效果跟踪"""
    __tablename__ = "expense_effect_tracking"

    tracking_id = Column(String(20), primary_key=True, comment="跟踪ID")
    expense_id = Column(
        String(20),
        ForeignKey("expense_report.expense_id"),
        nullable=False,
        comment="报销单号",
    )
    budget_id = Column(
        String(20),
        ForeignKey("budget_item.budget_id"),
        nullable=False,
        comment="预算ID",
    )
    expected_outcome = Column(Text, comment="预期效果")
    actual_outcome = Column(Text, comment="实际效果")
    effect_score = Column(Integer, comment="效果评分1-5")
    evaluation_date = Column(DateTime, comment="评估日期")
    evaluation_deadline = Column(Date, comment="评估截止日期")
    status = Column(String(20), default="待评估", comment="状态(待评估/已评估/已逾期)")
    evaluator_id = Column(String(20), comment="评估人ID")
    follow_up_required = Column(Boolean, default=False, comment="是否需要跟进")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
