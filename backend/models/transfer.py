from sqlalchemy import Column, String, Enum, Numeric, DateTime, ForeignKey, func
from models.database import Base


class BudgetTransferRequest(Base):
    """预算调拨请求持久化模型"""
    __tablename__ = "budget_transfer_request"

    transfer_id = Column(String(20), primary_key=True, comment="调拨请求唯一标识")
    from_budget_id = Column(
        String(20),
        ForeignKey("budget_item.budget_id"),
        nullable=False,
        comment="源预算项目ID",
    )
    to_budget_id = Column(
        String(20),
        ForeignKey("budget_item.budget_id"),
        nullable=False,
        comment="目标预算项目ID",
    )
    from_quadrant = Column(
        Enum("发展", "收缩", "稳定", "探索", name="transfer_from_quadrant_enum"),
        nullable=False,
        comment="源象限",
    )
    to_quadrant = Column(
        Enum("发展", "收缩", "稳定", "探索", name="transfer_to_quadrant_enum"),
        nullable=False,
        comment="目标象限",
    )
    amount = Column(Numeric(15, 2), nullable=False, comment="调拨金额")
    same_quadrant = Column(
        Enum("是", "否", name="same_quadrant_enum"),
        nullable=False,
        comment="是否同象限",
    )
    approval_required = Column(String(50), nullable=False, comment="审批要求")
    status = Column(
        Enum("待审批", "已审批", "已执行", "已驳回", "已取消", name="transfer_status_enum"),
        nullable=False,
        default="待审批",
        comment="调拨状态",
    )
    requested_by = Column(String(50), nullable=True, comment="申请人")
    approved_by = Column(String(50), nullable=True, comment="审批人")
    rejected_reason = Column(String(500), nullable=True, comment="驳回原因")
    executed_at = Column(DateTime, nullable=True, comment="执行时间")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
