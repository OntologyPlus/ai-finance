from sqlalchemy import Column, String, Text, Integer, Float, DateTime, JSON, Enum as SAEnum
from models.database import Base
from datetime import datetime


class Contract(Base):
    __tablename__ = "contract"
    id = Column(String(64), primary_key=True)
    contract_code = Column(String(64), unique=True, nullable=False)
    contract_name = Column(String(256), nullable=False)
    contract_type = Column(String(32), nullable=False)
    vendor_name = Column(String(128), default="")
    amount = Column(Float, default=0)
    paid_amount = Column(Float, default=0)
    currency = Column(String(8), default="CNY")
    sign_date = Column(DateTime, nullable=True)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    department_id = Column(String(64), default="")
    responsible_person = Column(String(64), default="")
    budget_id = Column(String(64), default="")
    l1_code = Column(String(8), default="")
    status = Column(String(32), default="执行中")
    payment_terms = Column(JSON, default=list)
    attachments = Column(JSON, default=list)
    description = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
