from sqlalchemy import Column, String, Boolean, Text, DateTime, ForeignKey, func
from models.database import Base


class Department(Base):
    __tablename__ = "department"

    dept_id = Column(String(10), primary_key=True, comment="部门ID")
    dept_name = Column(String(100), nullable=False, comment="部门名称")
    center_id = Column(String(10), nullable=True, comment="归属中心")
    parent_dept_id = Column(
        String(10),
        ForeignKey("department.dept_id"),
        nullable=True,
        comment="上级部门ID",
    )
    legal_entity_id = Column(String(10), nullable=True, comment="法人实体ID")
    is_active = Column(Boolean, nullable=False, default=True, comment="是否启用")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class Role(Base):
    __tablename__ = "role"

    role_id = Column(String(20), primary_key=True, comment="角色ID")
    role_name = Column(String(50), nullable=False, comment="角色名称")
    role_type = Column(String(30), nullable=False, comment="角色类型")
    permissions = Column(Text, nullable=True, comment="权限列表(JSON)")
    description = Column(Text, nullable=True, comment="角色描述")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")


class Employee(Base):
    __tablename__ = "employee"

    employee_id = Column(String(20), primary_key=True, comment="员工ID")
    employee_name = Column(String(50), nullable=False, comment="员工姓名")
    dept_id = Column(
        String(10),
        ForeignKey("department.dept_id"),
        nullable=True,
        comment="归属部门",
    )
    center_id = Column(String(10), nullable=True, comment="归属中心")
    role_id = Column(
        String(20),
        ForeignKey("role.role_id"),
        nullable=True,
        comment="角色ID",
    )
    email = Column(String(100), nullable=True, comment="邮箱")
    phone = Column(String(20), nullable=True, comment="手机号")
    is_active = Column(Boolean, nullable=False, default=True, comment="是否在职")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
