from __future__ import annotations
from sqlalchemy import Column, DateTime, Float, Integer, String, Text, JSON, func
from models.database import Base


class HCP(Base):
    __tablename__ = "hcps"
    id = Column(Integer, primary_key=True, autoincrement=True)
    hcp_id = Column(String(50), unique=True, nullable=False, comment="HCP编号")
    name = Column(String(200), nullable=False, comment="姓名")
    institution = Column(String(500), comment="所属机构")
    department = Column(String(200), comment="科室")
    specialty = Column(String(200), comment="专业领域")
    verification_status = Column(String(20), default="待验证", comment="待验证/已验证/验证失败")
    annual_interaction_count = Column(Integer, default=0, comment="年度互动次数")
    annual_payment_total = Column(Float, default=0, comment="年度付款总额")
    payment_limit = Column(Float, default=50000, comment="年度付款限额")
    created_at = Column(DateTime, server_default=func.now())


class HCPInteraction(Base):
    __tablename__ = "hcp_interactions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    hcp_id = Column(String(50), nullable=False, comment="HCP编号")
    interaction_type = Column(String(50), comment="学术会议/咨询/培训/访问")
    interaction_date = Column(DateTime, comment="互动日期")
    purpose = Column(Text, comment="互动目的")
    content_summary = Column(Text, comment="内容摘要")
    participants = Column(JSON, default=list, comment="参与人员")
    compliance_status = Column(String(20), default="待检查", comment="合规/不合规/待检查")
    created_at = Column(DateTime, server_default=func.now())


class HCPPayment(Base):
    __tablename__ = "hcp_payments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    hcp_id = Column(String(50), nullable=False, comment="HCP编号")
    payment_type = Column(String(50), comment="讲课费/咨询费/差旅费")
    amount = Column(Float, default=0, comment="付款金额")
    interaction_id = Column(Integer, comment="关联互动ID")
    approval_status = Column(String(20), default="待审批", comment="待审批/已审批/已驳回")
    created_at = Column(DateTime, server_default=func.now())


class ComplianceRule(Base):
    __tablename__ = "compliance_rules"
    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(String(50), unique=True, nullable=False, comment="规则ID")
    rule_name = Column(String(200), nullable=False, comment="规则名称")
    legal_basis = Column(String(500), comment="法规依据")
    check_logic = Column(Text, comment="检查逻辑描述")
    violation_action = Column(String(200), comment="违规处理")
    is_active = Column(Integer, default=1, comment="是否启用")
    created_at = Column(DateTime, server_default=func.now())
