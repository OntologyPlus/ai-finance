"""MySQL persistence for DecisionRecord (P2)."""
from sqlalchemy import JSON, Column, DateTime, Float, String, Text, func

from models.database import Base


class DecisionRecordRow(Base):
    __tablename__ = "decision_record"

    decision_id = Column(String(32), primary_key=True, comment="决策ID")
    category = Column(String(64), nullable=False, index=True, comment="决策类别")
    scenario = Column(Text, nullable=False, comment="情境描述")
    outcome = Column(String(32), nullable=False, comment="approved/rejected/blocked/...")
    reasoning = Column(Text, nullable=False, default="", comment="理由")
    confidence = Column(Float, nullable=False, default=1.0, comment="置信度")
    decision_maker = Column(String(64), nullable=False, comment="决策人/Agent")
    actor_type = Column(String(32), nullable=False, default="software_agent")
    scene_id = Column(String(64), nullable=True, comment="激活场景")
    entity_ids = Column(JSON, nullable=False, default=list, comment="关联实例ID")
    applied_rule_ids = Column(JSON, nullable=False, default=list, comment="命中规则")
    oag_block_sources = Column(JSON, nullable=False, default=list)
    tool_sequence = Column(JSON, nullable=False, default=list)
    sandbox_id = Column(String(32), nullable=True)
    hook_id = Column(String(80), nullable=True)
    valid_from = Column(DateTime, nullable=True)
    valid_until = Column(DateTime, nullable=True)
    recorded_at = Column(DateTime, nullable=False, server_default=func.now())
    extra_metadata = Column("metadata", JSON, nullable=False, default=dict)
