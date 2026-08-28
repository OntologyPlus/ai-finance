from __future__ import annotations
from sqlalchemy import Column, DateTime, Float, Integer, String, Text, JSON, func
from models.database import Base


class BusinessReviewMeeting(Base):
    __tablename__ = "business_review_meetings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_type = Column(String(20), nullable=False, comment="月度/季度")
    meeting_date = Column(DateTime, comment="会议日期")
    period = Column(String(10), comment="分析期间")
    agenda = Column(JSON, default=list, comment="议程")
    participants = Column(JSON, default=list, comment="参会人员")
    resolution_count = Column(Integer, default=0, comment="决议数量")
    status = Column(String(20), default="计划中", comment="计划中/已召开/已完成")
    created_at = Column(DateTime, server_default=func.now())


class MeetingResolution(Base):
    __tablename__ = "meeting_resolutions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_id = Column(Integer, nullable=False, comment="所属会议ID")
    content = Column(Text, nullable=False, comment="决议内容")
    owner = Column(String(100), comment="责任人")
    deadline = Column(DateTime, comment="截止日期")
    completion_status = Column(String(20), default="待执行", comment="待执行/执行中/已完成/已逾期/已取消")
    progress = Column(Float, default=0, comment="进度百分比")
    created_at = Column(DateTime, server_default=func.now())


class ResolutionTracking(Base):
    __tablename__ = "resolution_trackings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    resolution_id = Column(Integer, nullable=False, comment="决议ID")
    progress_percent = Column(Float, default=0, comment="进度百分比")
    latest_update = Column(Text, comment="最新进展")
    risk_flag = Column(String(10), default="无", comment="无/低/中/高")
    next_report_date = Column(DateTime, comment="下次汇报日期")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
