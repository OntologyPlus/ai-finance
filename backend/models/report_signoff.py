from __future__ import annotations
from sqlalchemy import Column, DateTime, Float, Integer, String, Text, JSON, func
from models.database import Base


class ReportSignoff(Base):
    __tablename__ = "report_signoffs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(String(50), nullable=False, comment="报告ID")
    report_type = Column(String(50), comment="月度快报/季度汇报/年度复盘")
    period = Column(String(10), comment="报告期")
    author = Column(String(100), comment="编制人")
    reviewer = Column(String(100), comment="审核人")
    signer = Column(String(100), comment="签发人")
    status = Column(String(20), default="编制中", comment="编制中/待审核/待签发/已签发/已发布/已驳回")
    signoff_date = Column(DateTime, comment="签发日期")
    publish_date = Column(DateTime, comment="发布日期")
    created_at = Column(DateTime, server_default=func.now())


class ExecutiveBrief(Base):
    __tablename__ = "executive_briefs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    period = Column(String(10), nullable=False, comment="报告期")
    focus_problem = Column(Text, comment="聚焦问题")
    focus_cause = Column(Text, comment="聚焦原因")
    focus_action = Column(Text, comment="聚焦行动")
    key_metrics = Column(JSON, default=dict, comment="关键指标")
    risk_alerts = Column(JSON, default=list, comment="风险提示")
    status = Column(String(20), default="草稿")
    created_at = Column(DateTime, server_default=func.now())
