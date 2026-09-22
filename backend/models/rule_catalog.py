"""Rule catalog versions pinned onto DecisionRecord metadata."""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy import JSON

from models.database import Base


class RuleCatalogVersion(Base):
    """硬规则目录版本：正文哈希，审核结论钉此版本。"""

    __tablename__ = "rule_catalog_version"
    __table_args__ = (UniqueConstraint("rule_set_code", "version_no", name="uk_rule_set_version_no"),)

    version_id = Column(String(24), primary_key=True)
    rule_set_code = Column(String(64), nullable=False, default="HARD_RULES", index=True)
    version_no = Column(Integer, nullable=False)
    content_sha256 = Column(String(64), nullable=False, index=True)
    content_json = Column(JSON, nullable=False)
    change_note = Column(String(512), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now())


class DecisionRulePin(Base):
    """决策 ↔ 规则版本钉扎。不改 DecisionRecordRow 列。"""

    __tablename__ = "decision_rule_pin"

    pin_id = Column(String(24), primary_key=True)
    decision_id = Column(String(32), ForeignKey("decision_record.decision_id"), nullable=False, index=True)
    rule_version_id = Column(String(24), ForeignKey("rule_catalog_version.version_id"), nullable=False)
    rule_content_sha256 = Column(String(64), nullable=False)
    applied_rule_ids = Column(JSON, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
