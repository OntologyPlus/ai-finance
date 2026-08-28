"""Decision as a first-class record.

Persisted by DecisionRecorder (MySQL + GraphStore) on mutating engine paths.
Distinct from engines.decision_sandbox.DecisionSandboxEngine (pre-execution
simulation). This record is post-execution or a blocked attempt.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_decision_id() -> str:
    return f"DEC-{uuid4().hex[:12]}"


class DecisionActorType(str, Enum):
    PERSON = "person"
    SOFTWARE_AGENT = "software_agent"
    ORGANIZATION = "organization"


class DecisionOutcome(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    BLOCKED = "blocked"
    SUGGESTED = "suggested"
    EXECUTED = "executed"
    REVERSED = "reversed"


class DecisionRecord(BaseModel):
    """Auditable decision produced by a person or FinanceAgent.

    Required join keys for later provenance / policy replay:
    scene_id, applied_rule_ids, entity_ids, tool_sequence.
    """

    decision_id: str = Field(default_factory=new_decision_id)
    category: str = Field(description="expense_submit / alert_closure / budget_grant / ...")
    scenario: str = Field(description="Human-readable situation that was decided")
    outcome: DecisionOutcome
    reasoning: str = ""
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    decision_maker: str = Field(description="user_id or agent name")
    actor_type: DecisionActorType = DecisionActorType.SOFTWARE_AGENT
    scene_id: str | None = None
    entity_ids: list[str] = Field(default_factory=list, description="Ontology/business instance IDs")
    applied_rule_ids: list[str] = Field(default_factory=list, description="HR-* / SR-* / SOD-* hit on this decision")
    oag_block_sources: list[str] = Field(default_factory=list)
    tool_sequence: list[str] = Field(default_factory=list)
    sandbox_id: str | None = Field(default=None, description="Optional link to a prior DecisionSandbox run")
    hook_id: str | None = Field(default=None, description="WriteHook.hook_id that produced this record")
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    recorded_at: datetime = Field(default_factory=_utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("category")
    @classmethod
    def category_not_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("category is required")
        return stripped
