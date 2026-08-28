from sqlalchemy import Column, String, Text, Integer, DateTime, JSON
from models.database import Base
from datetime import datetime


class ArchiveRecord(Base):
    __tablename__ = "archive_record"
    id = Column(String(64), primary_key=True)
    archive_code = Column(String(64), unique=True, nullable=False)
    archive_type = Column(String(32), nullable=False)
    title = Column(String(256), nullable=False)
    related_entity_type = Column(String(32), default="")
    related_entity_id = Column(String(64), default="")
    physical_location = Column(String(256), default="")
    electronic_path = Column(String(512), default="")
    retention_years = Column(Integer, default=3)
    archived_by = Column(String(64), default="")
    archived_at = Column(DateTime, default=datetime.now)
    status = Column(String(32), default="已归档")
    tags = Column(JSON, default=list)
    description = Column(Text, default="")
