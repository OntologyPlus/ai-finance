from sqlalchemy import Column, String, Enum, Text, Boolean, Integer, DateTime, ForeignKey, func
from models.database import Base


class ApprovalRecord(Base):
    __tablename__ = "approval_record"

    approval_id = Column(String(20), primary_key=True, comment="审批记录编号")
    expense_id = Column(
        String(20),
        ForeignKey("expense_report.expense_id"),
        nullable=False,
        comment="报销单号",
    )
    approval_line = Column(
        Enum("组织管理线", "法人架构线", name="approval_line_enum"),
        nullable=False,
        comment="审批线路",
    )
    approval_step = Column(Integer, nullable=False, comment="审批步骤序号")
    approver_id = Column(String(20), nullable=False, comment="审批人ID")
    approver_role = Column(
        Enum("部门负责人", "中心总经理", "法人财务负责人", "法人或授权人", "战略审核", name="approver_role_enum"),
        nullable=False,
        comment="审批人角色",
    )
    approval_action = Column(
        Enum("通过", "驳回", "待审批", name="approval_action_enum"),
        nullable=False,
        default="待审批",
        comment="审批动作",
    )
    approval_comment = Column(Text, nullable=True, comment="审批意见")
    approved_at = Column(DateTime, nullable=True, comment="审批时间")
    deadline = Column(DateTime, nullable=True, comment="审批截止时间")
    is_overdue = Column(Boolean, nullable=False, default=False, comment="是否超时")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
