"""v12.0 推理轨迹反馈表（评测驱动进化）

记录审计员/业务用户对 AI 推理结果的反馈（👍/👎/准确性/建议），
用于驱动规则库的迭代与置信度校准。
"""
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, Numeric
from sqlalchemy.sql import func
from models.database import Base


class TraceFeedback(Base):
    __tablename__ = "trace_feedback"

    feedback_id = Column(String(40), primary_key=True, comment="反馈ID")
    trace_id = Column(String(30), ForeignKey("reasoning_trace.trace_id"), nullable=False, index=True, comment="关联推理轨迹")
    scene_name = Column(String(100), nullable=True, comment="场景名称（冗余）")

    # 反馈核心字段
    accuracy_score = Column(Integer, nullable=False, comment="准确性评分 1-5（5=最准确）")
    helpful = Column(Integer, nullable=True, comment="是否有帮助：1=是 / 0=否")
    comment = Column(Text, nullable=True, comment="反馈意见/改进建议")

    # 反馈人
    reviewer_id = Column(String(50), nullable=True, comment="反馈人ID")
    reviewer_role = Column(String(30), nullable=True, comment="反馈人角色（财经BP/业务/审计员）")

    # 改进建议（系统化提取）
    rule_adjust_suggestion = Column(Text, nullable=True, comment="规则调整建议（JSON）")
    confidence_calibration = Column(Numeric(5, 2), nullable=True, comment="期望置信度（用于校准）")

    created_at = Column(DateTime, server_default=func.now(), comment="反馈时间")
