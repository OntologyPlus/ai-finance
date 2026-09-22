"""Budget version snapshots, adjustment diffs, and formula/source reasons."""
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import JSON

from models.database import Base


class BudgetVersion(Base):
    """预算正式/草稿版本。数字变更必须出版本，禁止覆盖。"""

    __tablename__ = "budget_version"
    __table_args__ = (UniqueConstraint("budget_year", "version_no", name="uk_budget_year_version_no"),)

    version_id = Column(String(24), primary_key=True)
    budget_year = Column(Integer, nullable=False, index=True)
    version_no = Column(String(16), nullable=False, comment="V1/V2")
    parent_version_id = Column(String(24), nullable=True)
    status = Column(String(16), nullable=False, default="DRAFT", comment="DRAFT/FROZEN/SUPERSEDED")
    is_current = Column(Boolean, nullable=False, default=False)
    change_summary = Column(String(512), nullable=True)
    formula_version = Column(String(64), nullable=True)
    created_by = Column(String(50), nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class BudgetVersionItem(Base):
    """版本内每个 BudgetItem 的金额快照。"""

    __tablename__ = "budget_version_item"
    __table_args__ = (UniqueConstraint("version_id", "budget_id", name="uk_version_budget_item"),)

    item_id = Column(String(24), primary_key=True)
    version_id = Column(String(24), ForeignKey("budget_version.version_id"), nullable=False, index=True)
    budget_id = Column(String(20), ForeignKey("budget_item.budget_id"), nullable=False, index=True)
    annual_amount = Column(Numeric(15, 2), nullable=False, default=0)
    granted_amount = Column(Numeric(15, 2), nullable=False, default=0)
    frozen_amount = Column(Numeric(15, 2), nullable=False, default=0)
    used_amount = Column(Numeric(15, 2), nullable=False, default=0)
    available_amount = Column(Numeric(15, 2), nullable=False, default=0)
    snapshot_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class BudgetAdjustmentRecord(Base):
    """调整 diff：金额/参数/组织/公式，记 before/after。"""

    __tablename__ = "budget_adjustment_record"

    adjustment_id = Column(String(24), primary_key=True)
    from_version_id = Column(String(24), ForeignKey("budget_version.version_id"), nullable=True)
    to_version_id = Column(String(24), ForeignKey("budget_version.version_id"), nullable=True)
    adjustment_type = Column(
        String(32),
        nullable=False,
        comment="AMOUNT/PARAMETER/ORG/FORMULA",
    )
    amount_direction = Column(String(16), nullable=True, comment="increase/decrease/transfer")
    target_type = Column(String(16), nullable=False, default="BUDGET", comment="BUDGET/ORG/GROUP")
    target_id = Column(String(64), nullable=False)
    related_budget_id = Column(String(20), ForeignKey("budget_item.budget_id"), nullable=True)
    module_code = Column(String(32), nullable=True, comment="INCOME/PROMOTION/PEOPLE/MAINTENANCE/RD/PROFIT")
    before_json = Column(JSON, nullable=False)
    after_json = Column(JSON, nullable=False)
    reason = Column(String(1024), nullable=False, default="")
    formula_text = Column(Text, nullable=True)
    status = Column(String(16), nullable=False, default="待审批")
    created_by = Column(String(50), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class BudgetReason(Base):
    """测算理由：公式 + 参数 + 资料 locator。"""

    __tablename__ = "budget_reason"

    reason_id = Column(String(24), primary_key=True)
    version_id = Column(String(24), ForeignKey("budget_version.version_id"), nullable=True, index=True)
    data_scope = Column(String(16), nullable=False, default="DRAFT", comment="DRAFT/VERSION")
    target_type = Column(String(16), nullable=False, default="BUDGET")
    target_id = Column(String(64), nullable=False)
    target_name = Column(String(128), nullable=True)
    module_code = Column(String(32), nullable=False, default="AMOUNT")
    formula_text = Column(Text, nullable=True)
    parameter_json = Column(JSON, nullable=True)
    source_json = Column(JSON, nullable=True, comment="文件/Sheet/单元格定位")
    reason_text = Column(Text, nullable=False)
    risk_text = Column(Text, nullable=True)
    created_by = Column(String(50), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
