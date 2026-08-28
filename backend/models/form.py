from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime, JSON, Enum as SAEnum
from models.database import Base
from datetime import datetime


class FormTemplate(Base):
    __tablename__ = "form_template"
    id = Column(String(64), primary_key=True)
    form_code = Column(String(32), unique=True, nullable=False)
    form_name = Column(String(128), nullable=False)
    form_type = Column(String(32), nullable=False)
    category = Column(String(32), nullable=False)
    description = Column(Text, default="")
    fields = Column(JSON, default=list)
    version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class FormSubmission(Base):
    __tablename__ = "form_submission"
    id = Column(String(64), primary_key=True)
    submission_id = Column(String(64), unique=True, nullable=False)
    form_code = Column(String(32), nullable=False)
    form_name = Column(String(128), nullable=False)
    submitter_id = Column(String(64), nullable=False)
    submitter_name = Column(String(64), default="")
    org_id = Column(String(64), default="")
    status = Column(String(32), default="已提交")
    field_values = Column(JSON, default=dict)
    attachments = Column(JSON, default=list)
    related_entity_type = Column(String(32), default="")
    related_entity_id = Column(String(64), default="")
    submitted_at = Column(DateTime, default=datetime.now)
    reviewed_at = Column(DateTime, nullable=True)
    reviewer_id = Column(String(64), default="")
    review_comment = Column(Text, default="")
