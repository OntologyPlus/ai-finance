from sqlalchemy import Column, String, Text, Integer, DateTime, JSON
from models.database import Base
from datetime import datetime


class PendingItem(Base):
    __tablename__ = "pending_item"

    id = Column(String(64), primary_key=True)
    source_type = Column(String(32), nullable=False)
    source_id = Column(String(64), default="")
    source_year = Column(Integer, nullable=False)
    title = Column(String(256), nullable=False)
    description = Column(Text, default="")
    priority = Column(String(16), default="medium")
    assigned_to = Column(String(64), default="")
    status = Column(String(32), default="待解决")
    resolution = Column(Text, default="")
    target_year = Column(Integer, nullable=False)
    tags = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.now)
    resolved_at = Column(DateTime, nullable=True)
