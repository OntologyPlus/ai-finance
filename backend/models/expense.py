from sqlalchemy import Column, String, Enum, Text, Numeric, Boolean, DateTime, ForeignKey, func
from models.database import Base


class ExpenseReport(Base):
    __tablename__ = "expense_report"

    expense_id = Column(String(20), primary_key=True, comment="报销单号")
    applicant_id = Column(String(20), nullable=False, comment="申请人ID")
    budget_id = Column(
        String(20),
        ForeignKey("budget_item.budget_id"),
        nullable=False,
        comment="关联预算ID",
    )
    l1_code = Column(
        String(2),
        ForeignKey("budget_subject_l1.l1_code"),
        nullable=False,
        comment="费用L1科目",
    )
    l2_code = Column(
        String(5),
        ForeignKey("budget_subject_l2.l2_code"),
        nullable=True,
        comment="费用L2科目",
    )
    l3_code = Column(
        String(10),
        ForeignKey("budget_subject_l3.l3_code"),
        nullable=True,
        comment="费用L3科目",
    )
    amount = Column(Numeric(15, 2), nullable=False, comment="报销金额")
    description = Column(Text, nullable=True, comment="报销说明")
    control_tag = Column(
        Enum("强管控", "中心弱管控", "组合管控", "不管控", name="expense_control_tag_enum"),
        nullable=True,
        comment="管控标签",
    )
    status = Column(
        Enum(
            "草稿",
            "待审批",
            "组织线审批中",
            "法人线审批中",
            "已审批",
            "已驳回",
            "已核销",
            "已取消",
            name="expense_status_enum",
        ),
        nullable=False,
        default="草稿",
        comment="报销单状态",
    )
    center_id = Column(String(10), nullable=True, comment="归属中心")
    department_id = Column(String(10), nullable=True, comment="归属部门")
    legal_entity_id = Column(String(10), nullable=True, comment="法人实体ID")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")


class InvoiceRecord(Base):
    __tablename__ = "invoice_record"

    invoice_id = Column(String(20), primary_key=True, comment="发票记录ID")
    expense_id = Column(
        String(20),
        ForeignKey("expense_report.expense_id"),
        nullable=False,
        comment="关联报销单号",
    )
    invoice_number = Column(String(50), nullable=False, comment="发票号码")
    invoice_code = Column(String(50), nullable=True, comment="发票代码")
    invoice_date = Column(DateTime, nullable=True, comment="开票日期")
    invoice_amount = Column(Numeric(15, 2), nullable=True, comment="发票金额")
    invoice_type = Column(String(30), nullable=True, comment="发票类型")
    seller_name = Column(String(200), nullable=True, comment="销方名称")
    file_path = Column(String(500), nullable=True, comment="发票文件路径")
    is_duplicate = Column(Boolean, nullable=False, default=False, comment="是否重复")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")


class BudgetWriteOff(Base):
    __tablename__ = "budget_write_off"

    write_off_id = Column(String(20), primary_key=True, comment="核销记录ID")
    expense_id = Column(
        String(20),
        ForeignKey("expense_report.expense_id"),
        nullable=False,
        comment="关联报销单号",
    )
    budget_id = Column(
        String(20),
        ForeignKey("budget_item.budget_id"),
        nullable=False,
        comment="关联预算ID",
    )
    write_off_amount = Column(Numeric(15, 2), nullable=False, comment="核销金额")
    write_off_date = Column(DateTime, nullable=False, comment="核销时间")
    execution_rate = Column(Numeric(5, 2), nullable=True, comment="核销后执行率")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
