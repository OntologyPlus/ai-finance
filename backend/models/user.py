from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.sql import func
from models.database import Base
import enum


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    CFO = "cfo"
    CENTER_MANAGER = "center_manager"
    DEPT_HEAD = "dept_head"
    FINANCE_BP = "finance_bp"
    EMPLOYEE = "employee"


class User(Base):
    __tablename__ = "users"

    user_id = Column(String(20), primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(100), nullable=False)
    role = Column(String(20), nullable=False, default=UserRole.EMPLOYEE.value)
    center_id = Column(String(10))
    department_id = Column(String(10))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    last_login = Column(DateTime)
