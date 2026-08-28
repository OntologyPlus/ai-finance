"""W3C PROV-O aligned provenance entry.

P0: Pydantic contract + checksum helpers. Not persisted.
P3 will unify LineageTracker, OntologyEventBus, RuleEngine traces, and AuditLogger
onto this schema.

Mapping (no rdflib required):
    entity_id            → prov:Entity
    activity_id          → prov:Activity
    agent_id / agent_type → prov:Agent
    used_entities        → prov:used
    derived_from_id      → prov:wasDerivedFrom
    previous_version_id  → correction/version of the same fact
    timestamp            → prov:generatedAtTime
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProvenanceAgentType(str, Enum):
    PERSON = "person"
    SOFTWARE_AGENT = "software_agent"
    ORGANIZATION = "organization"


class ProvenanceEntry(BaseModel):
    entity_id: str
    entity_type: str = Field(description="object_instance / relation_instance / decision / chunk / ...")
    activity_id: str
    agent_id: str = "finance_agent"
    agent_type: ProvenanceAgentType = ProvenanceAgentType.SOFTWARE_AGENT
    is_automated: bool = True
    role: str | None = Field(default=None, description="generator / approver / reviewer")
    used_entities: list[str] = Field(default_factory=list)
    derived_from_id: str | None = None
    previous_version_id: str | None = None
    source_document: str = ""
    source_location: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    checksum: str | None = None
    previous_checksum: str | None = None
    sequence_id: int | None = None
    timestamp: datetime = Field(default_factory=_utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def payload_for_checksum(self) -> str:
        body = {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "activity_id": self.activity_id,
            "agent_id": self.agent_id,
            "agent_type": self.agent_type.value,
            "used_entities": self.used_entities,
            "derived_from_id": self.derived_from_id,
            "previous_version_id": self.previous_version_id,
            "source_document": self.source_document,
            "timestamp": self.timestamp.isoformat(),
            "sequence_id": self.sequence_id,
            "previous_checksum": self.previous_checksum,
        }
        return json.dumps(body, sort_keys=True, ensure_ascii=False, default=str)

    def compute_checksum(self) -> str:
        return hashlib.sha256(self.payload_for_checksum().encode("utf-8")).hexdigest()

    def seal(self, previous: ProvenanceEntry | None = None) -> ProvenanceEntry:
        """Return a copy with hash-chain fields filled. Does not mutate self."""
        prev_checksum = previous.checksum if previous is not None else None
        seq = 0 if previous is None else (previous.sequence_id or 0) + 1
        sealed = self.model_copy(
            update={
                "previous_checksum": prev_checksum,
                "sequence_id": seq,
                "checksum": None,
            }
        )
        return sealed.model_copy(update={"checksum": sealed.compute_checksum()})

    def verify_link(self, previous: ProvenanceEntry | None) -> bool:
        if previous is None:
            return self.previous_checksum is None and (self.sequence_id in (None, 0))
        if self.previous_checksum != previous.checksum:
            return False
        if self.checksum != self.compute_checksum():
            return False
        return True
