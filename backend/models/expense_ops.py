"""Operational expense layer absorbed from production audit schema.

Companion tables only — ExpenseReport header is unchanged (HIGH blast radius).
"""
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy import JSON

from models.database import Base


class ExpenseLine(Base):
    """科目行：来源单 × 预算 × 科目，分列申请/预审/实核金额。"""

    __tablename__ = "expense_line"

    line_id = Column(String(24), primary_key=True, comment="费用行ID")
    expense_id = Column(
        String(20),
        ForeignKey("expense_report.expense_id"),
        nullable=False,
        index=True,
        comment="报销单号",
    )
    seq_no = Column(Integer, nullable=False, default=1, comment="行序号")
    source_bill_type = Column(
        String(32),
        nullable=False,
        default="NONE",
        comment="ACTIVITY/TRAVEL/CONTRACT/BORROW/NONE",
    )
    source_id = Column(String(64), nullable=True, comment="来源单ID")
    source_code = Column(String(64), nullable=True, comment="来源单号")
    source_name = Column(String(256), nullable=True, comment="来源名称")
    budget_id = Column(String(20), ForeignKey("budget_item.budget_id"), nullable=True)
    l1_code = Column(String(2), nullable=True)
    l2_code = Column(String(5), nullable=True)
    l3_code = Column(String(10), nullable=True)
    duty_center_id = Column(String(20), nullable=True, comment="责任中心")
    apply_money = Column(Numeric(18, 2), nullable=False, default=0, comment="申请金额")
    pre_pass_money = Column(Numeric(18, 2), nullable=True, comment="预审金额")
    real_money = Column(Numeric(18, 2), nullable=True, comment="实核金额")
    offset_money = Column(Numeric(18, 2), nullable=True, comment="冲抵借款")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ExpenseSettlement(Base):
    """头表金额状态（1:1），避免改 ExpenseReport 列。"""

    __tablename__ = "expense_settlement"

    expense_id = Column(
        String(20),
        ForeignKey("expense_report.expense_id"),
        primary_key=True,
        comment="报销单号",
    )
    apply_money = Column(Numeric(18, 2), nullable=False, default=0)
    pre_pass_money = Column(Numeric(18, 2), nullable=True)
    real_money = Column(Numeric(18, 2), nullable=True)
    pay_money = Column(Numeric(18, 2), nullable=True)
    offset_money = Column(Numeric(18, 2), nullable=True)
    currency = Column(String(16), nullable=False, default="CNY")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class InvoiceMerchantProfile(Base):
    """发票销方工商/风险画像。"""

    __tablename__ = "invoice_merchant_profile"

    profile_id = Column(String(24), primary_key=True)
    invoice_id = Column(
        String(20),
        ForeignKey("invoice_record.invoice_id"),
        nullable=True,
        index=True,
    )
    expense_id = Column(String(20), ForeignKey("expense_report.expense_id"), nullable=True, index=True)
    seller_name = Column(String(512), nullable=False)
    credit_code = Column(String(128), nullable=True, comment="统一社会信用代码")
    legal_person_name = Column(String(128), nullable=True)
    industry = Column(String(256), nullable=True)
    reg_status = Column(String(64), nullable=True)
    risk_summaries_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class OcrRun(Base):
    """一次 OCR 批任务。"""

    __tablename__ = "ocr_run"

    run_id = Column(String(24), primary_key=True)
    expense_id = Column(String(20), ForeignKey("expense_report.expense_id"), nullable=True, index=True)
    invoice_id = Column(String(20), ForeignKey("invoice_record.invoice_id"), nullable=True)
    provider = Column(String(32), nullable=False, default="pending")
    status = Column(String(16), nullable=False, default="pending")
    progress_total = Column(Integer, nullable=False, default=0)
    progress_done = Column(Integer, nullable=False, default=0)
    error_msg = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    finished_at = Column(DateTime, nullable=True)


class OcrImage(Base):
    """OCR 单图结果。"""

    __tablename__ = "ocr_image"

    image_id = Column(String(24), primary_key=True)
    run_id = Column(String(24), ForeignKey("ocr_run.run_id"), nullable=False, index=True)
    invoice_id = Column(String(20), ForeignKey("invoice_record.invoice_id"), nullable=True)
    image_url = Column(String(2048), nullable=False)
    status = Column(String(16), nullable=False, default="pending")
    doc_type = Column(String(64), nullable=True)
    confidence = Column(Float, nullable=True)
    ocr_raw = Column(JSON, nullable=True)
    reused_from_image_id = Column(String(24), nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class ThreeFlowMismatch(Base):
    """三流不一致：销方 / 收款人 / 水单商户。"""

    __tablename__ = "three_flow_mismatch"

    mismatch_id = Column(String(24), primary_key=True)
    expense_id = Column(String(20), ForeignKey("expense_report.expense_id"), nullable=False, index=True)
    invoice_id = Column(String(20), ForeignKey("invoice_record.invoice_id"), nullable=True)
    seller_name = Column(String(512), nullable=True)
    seller_tax_no = Column(String(128), nullable=True)
    payee_name = Column(String(512), nullable=True)
    merchant_name = Column(String(512), nullable=True)
    status = Column(
        String(32),
        nullable=False,
        default="pending",
        comment="pending/confirmed_same/confirmed_diff/whitelisted",
    )
    whitelist_id = Column(String(24), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ThreeFlowWhitelist(Base):
    """三流主体白名单。"""

    __tablename__ = "three_flow_whitelist"
    __table_args__ = (
        Index("ix_three_flow_wl_tax", "seller_tax_no"),
    )

    whitelist_id = Column(String(24), primary_key=True)
    seller_name = Column(String(512), nullable=True)
    seller_tax_no = Column(String(128), nullable=True)
    payee_name = Column(String(512), nullable=True)
    merchant_name = Column(String(512), nullable=True)
    reason = Column(String(512), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now())
