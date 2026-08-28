"""Persist DecisionRecord to MySQL (optional) and GraphStore; query chain / precedents.

MySQL remains SoT when a session is provided. Graph is a projection:
  :Decision -[:BASED_ON]-> entity
  :Decision -[:APPLIED_POLICY]-> HR-* / SR-* / SOD-*
  earlier Decision -[:CAUSED]-> later Decision
"""
from __future__ import annotations

from typing import Any

from loguru import logger

from ontology.decision_record import DecisionActorType, DecisionOutcome, DecisionRecord
from storage.graph_store import GraphStore
from storage.runtime import get_active_graph_store

REL_BASED_ON = "BASED_ON"
REL_APPLIED_POLICY = "APPLIED_POLICY"
REL_CAUSED = "CAUSED"

_SCENE_BY_CATEGORY: dict[str, str] = {
    "expense_submit": "fin.expense_reimbursement",
    "expense_approve": "fin.expense_reimbursement",
    "expense_reject": "fin.expense_reimbursement",
    "budget_write_off": "fin.expense_reimbursement",
    "approval_final": "fin.expense_reimbursement",
    "budget_grant": "fin.budget_grant",
    "budget_b2a": "fin.b_class_management",
    "budget_transfer": "fin.budget_adjustment",
    "alert_respond": "fin.alert_response",
    "alert_closure": "fin.alert_response",
    "alert_escalate": "fin.alert_response",
}

_SKIP_ENTITY_PREFIX = ("DEC-", "WO-", "AP-", "CL-", "ES-", "HR-", "TF-", "INV-", "MS-")
_STRATEGIC_RELS = ("rel_benchmark", "rel_belong", "rel_drive")


def _rule_set(ids: list[str] | None) -> frozenset[str]:
    return frozenset(ids or [])


class DecisionRecorder:
    """In-process index plus optional MySQL row + GraphStore projection."""

    def __init__(self) -> None:
        self._by_id: dict[str, DecisionRecord] = {}

    def reset(self) -> None:
        self._by_id.clear()

    def get(self, decision_id: str) -> DecisionRecord | None:
        return self._by_id.get(decision_id)

    def all_records(self) -> list[DecisionRecord]:
        return list(self._by_id.values())

    def list_for_entity(self, entity_id: str) -> list[DecisionRecord]:
        found = [r for r in self._by_id.values() if entity_id in r.entity_ids]
        found.sort(key=lambda r: r.recorded_at)
        return found

    def find_precedents(
        self,
        category: str,
        applied_rule_ids: list[str],
        *,
        limit: int = 10,
        exclude_id: str | None = None,
    ) -> list[DecisionRecord]:
        target = _rule_set(applied_rule_ids)
        matches = [
            r
            for r in self._by_id.values()
            if r.category == category
            and _rule_set(r.applied_rule_ids) == target
            and r.decision_id != exclude_id
        ]
        matches.sort(key=lambda r: r.recorded_at, reverse=True)
        return matches[:limit]

    async def record(
        self,
        rec: DecisionRecord,
        *,
        db: Any | None = None,
        store: GraphStore | None = None,
        caused_by: str | None = None,
    ) -> DecisionRecord:
        if not rec.scene_id:
            rec = rec.model_copy(update={"scene_id": _SCENE_BY_CATEGORY.get(rec.category)})
        self._by_id[rec.decision_id] = rec
        if db is not None:
            await self._persist_mysql(rec, db)
        target = store if store is not None else get_active_graph_store()
        if target is not None:
            await self._project_graph(rec, target, caused_by=caused_by)
        return rec

    def _from_row(self, row: Any) -> DecisionRecord:
        recorded = row.recorded_at
        if recorded is not None and getattr(recorded, "tzinfo", None) is None:
            from datetime import timezone

            recorded = recorded.replace(tzinfo=timezone.utc)
        return DecisionRecord(
            decision_id=row.decision_id,
            category=row.category,
            scenario=row.scenario,
            outcome=DecisionOutcome(row.outcome),
            reasoning=row.reasoning or "",
            confidence=float(row.confidence or 1.0),
            decision_maker=row.decision_maker,
            actor_type=DecisionActorType(row.actor_type or DecisionActorType.SOFTWARE_AGENT.value),
            scene_id=row.scene_id,
            entity_ids=list(row.entity_ids or []),
            applied_rule_ids=list(row.applied_rule_ids or []),
            oag_block_sources=list(row.oag_block_sources or []),
            tool_sequence=list(row.tool_sequence or []),
            sandbox_id=row.sandbox_id,
            hook_id=row.hook_id,
            valid_from=row.valid_from,
            valid_until=row.valid_until,
            recorded_at=recorded,
            metadata=dict(row.extra_metadata or {}),
        )

    async def hydrate_from_db(self, db: Any, store: GraphStore | None = None) -> int:
        from sqlalchemy import select

        from models.decision import DecisionRecordRow

        try:
            result = await db.execute(select(DecisionRecordRow))
            rows = list(result.scalars().all())
        except Exception as exc:
            logger.warning(f"Decision hydrate skipped: {exc}")
            return 0
        rows.sort(key=lambda r: r.recorded_at or r.decision_id)
        for row in rows:
            rec = self._from_row(row)
            self._by_id[rec.decision_id] = rec
        target = store if store is not None else get_active_graph_store()
        if target is not None:
            for rec in sorted(self._by_id.values(), key=lambda r: r.recorded_at):
                try:
                    await self._project_graph(rec, target, caused_by=None)
                except Exception as exc:
                    logger.warning(f"Decision graph hydrate skipped {rec.decision_id}: {exc}")
        logger.info(f"Decision hydrate loaded {len(rows)} records")
        return len(rows)

    async def _persist_mysql(self, rec: DecisionRecord, db: Any) -> None:
        from models.decision import DecisionRecordRow

        row = DecisionRecordRow(
            decision_id=rec.decision_id,
            category=rec.category,
            scenario=rec.scenario,
            outcome=rec.outcome.value,
            reasoning=rec.reasoning,
            confidence=rec.confidence,
            decision_maker=rec.decision_maker,
            actor_type=rec.actor_type.value,
            scene_id=rec.scene_id,
            entity_ids=list(rec.entity_ids),
            applied_rule_ids=list(rec.applied_rule_ids),
            oag_block_sources=list(rec.oag_block_sources),
            tool_sequence=list(rec.tool_sequence),
            sandbox_id=rec.sandbox_id,
            hook_id=rec.hook_id,
            valid_from=rec.valid_from,
            valid_until=rec.valid_until,
            recorded_at=rec.recorded_at.replace(tzinfo=None) if rec.recorded_at.tzinfo else rec.recorded_at,
            extra_metadata=dict(rec.metadata),
        )
        db.add(row)
        try:
            await db.flush()
        except Exception as exc:
            logger.warning(f"Decision MySQL persist skipped: {exc}")

    async def _ensure_node(
        self,
        store: GraphStore,
        node_id: str,
        labels: list[str],
        properties: dict[str, Any] | None = None,
    ) -> None:
        existing = await store.get_node(node_id)
        if existing is None:
            await store.upsert_node(node_id, labels, properties)
            return
        merged_labels = list(dict.fromkeys([*existing.labels, *labels]))
        merged_props = dict(existing.properties)
        if properties:
            merged_props.update(properties)
        await store.upsert_node(node_id, merged_labels, merged_props)

    async def _project_graph(
        self,
        rec: DecisionRecord,
        store: GraphStore,
        *,
        caused_by: str | None,
    ) -> None:
        props = rec.model_dump(mode="json")
        await self._ensure_node(store, rec.decision_id, ["Decision"], props)

        for entity_id in rec.entity_ids:
            await self._ensure_node(store, entity_id, ["Instance"])
            await store.upsert_edge(
                f"{rec.decision_id}:{REL_BASED_ON}:{entity_id}",
                rec.decision_id,
                entity_id,
                REL_BASED_ON,
            )

        for rule_id in rec.applied_rule_ids:
            await self._ensure_node(store, rule_id, ["Policy"], {"rule_id": rule_id})
            await store.upsert_edge(
                f"{rec.decision_id}:{REL_APPLIED_POLICY}:{rule_id}",
                rec.decision_id,
                rule_id,
                REL_APPLIED_POLICY,
            )

        predecessor = caused_by
        if predecessor is None:
            predecessor = self._latest_predecessor(rec)
        if predecessor and predecessor in self._by_id:
            await self._ensure_node(store, predecessor, ["Decision"])
            await store.upsert_edge(
                f"{predecessor}:{REL_CAUSED}:{rec.decision_id}",
                predecessor,
                rec.decision_id,
                REL_CAUSED,
            )

    def _latest_predecessor(self, rec: DecisionRecord) -> str | None:
        if not rec.entity_ids:
            return None
        primary = rec.entity_ids[0]
        earlier = [
            r
            for r in self._by_id.values()
            if r.decision_id != rec.decision_id
            and r.recorded_at <= rec.recorded_at
            and primary in r.entity_ids
        ]
        if not earlier:
            return None
        earlier.sort(key=lambda r: r.recorded_at)
        return earlier[-1].decision_id

    async def trace_decision_chain(
        self,
        decision_id: str,
        *,
        store: GraphStore | None = None,
        max_hops: int = 6,
    ) -> dict[str, Any]:
        rec = self._by_id.get(decision_id)
        target = store if store is not None else get_active_graph_store()
        hops: list[dict[str, Any]] = []
        if target is not None and await target.get_node(decision_id) is not None:
            hops = await self._walk_decision_rels(target, decision_id, max_hops)
        return {
            "decision_id": decision_id,
            "decision": rec.model_dump(mode="json") if rec else None,
            "hops": hops,
        }

    async def _walk_decision_rels(
        self,
        store: GraphStore,
        start_id: str,
        max_hops: int,
    ) -> list[dict[str, Any]]:
        rels = (REL_CAUSED, REL_BASED_ON, REL_APPLIED_POLICY)
        visited = {start_id}
        hops: list[dict[str, Any]] = []
        frontier = [start_id]
        for _ in range(max(1, max_hops)):
            nxt: list[str] = []
            for nid in frontier:
                for rel in rels:
                    for direction in ("out", "in"):
                        neighbors = await store.neighbors(
                            nid, direction=direction, rel_type=rel, max_hops=1
                        )
                        for node in neighbors:
                            if node.node_id in visited:
                                continue
                            visited.add(node.node_id)
                            hops.append(
                                {
                                    "from": nid,
                                    "to": node.node_id,
                                    "rel": rel,
                                    "direction": direction,
                                    "labels": list(node.labels),
                                }
                            )
                            nxt.append(node.node_id)
            frontier = nxt
            if not frontier:
                break
        return hops

    async def explain_expense(
        self,
        expense_id: str,
        *,
        store: GraphStore | None = None,
    ) -> dict[str, Any]:
        """Who approved, which HR, which budget, upstream strategic initiative."""
        recs = self.list_for_entity(expense_id)
        approvers: list[str] = []
        rules: list[str] = []
        budget_ids: list[str] = []
        for rec in recs:
            if rec.category in ("expense_approve", "approval_final") and rec.outcome in (
                DecisionOutcome.APPROVED,
                DecisionOutcome.EXECUTED,
            ):
                if rec.decision_maker not in approvers:
                    approvers.append(rec.decision_maker)
            for rule_id in rec.applied_rule_ids:
                if rule_id not in rules:
                    rules.append(rule_id)
            meta_budget = rec.metadata.get("budget_id")
            if meta_budget and str(meta_budget) not in budget_ids:
                budget_ids.append(str(meta_budget))
            for eid in rec.entity_ids:
                if eid == expense_id or eid in budget_ids:
                    continue
                if any(eid.startswith(p) for p in _SKIP_ENTITY_PREFIX):
                    continue
                budget_ids.append(eid)

        strategic: list[str] = []
        target = store if store is not None else get_active_graph_store()
        if target is not None:
            for budget_id in budget_ids:
                for rel in _STRATEGIC_RELS:
                    for node in await target.neighbors(
                        budget_id, direction="out", rel_type=rel, max_hops=2
                    ):
                        if "Decision" in node.labels or "Policy" in node.labels:
                            continue
                        if node.node_id not in strategic and node.node_id != budget_id:
                            strategic.append(node.node_id)

        return {
            "expense_id": expense_id,
            "approvers": approvers,
            "applied_rule_ids": rules,
            "budget_ids": budget_ids,
            "strategic_initiatives": strategic,
            "decisions": [r.model_dump(mode="json") for r in recs],
        }


_recorder: DecisionRecorder | None = None


def get_decision_recorder() -> DecisionRecorder:
    global _recorder
    if _recorder is None:
        _recorder = DecisionRecorder()
    return _recorder


def set_decision_recorder(recorder: DecisionRecorder | None) -> None:
    global _recorder
    _recorder = recorder


async def emit_decision(
    *,
    category: str,
    scenario: str,
    outcome: DecisionOutcome | str,
    reasoning: str = "",
    decision_maker: str = "system",
    actor_type: DecisionActorType = DecisionActorType.SOFTWARE_AGENT,
    entity_ids: list[str] | None = None,
    applied_rule_ids: list[str] | None = None,
    hook_id: str | None = None,
    scene_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    db: Any | None = None,
    caused_by: str | None = None,
) -> DecisionRecord | None:
    """Record a Decision; never raise into the business write path."""
    try:
        if isinstance(outcome, str):
            outcome = DecisionOutcome(outcome)
        rec = DecisionRecord(
            category=category,
            scenario=scenario,
            outcome=outcome,
            reasoning=reasoning,
            decision_maker=decision_maker,
            actor_type=actor_type,
            entity_ids=list(entity_ids or []),
            applied_rule_ids=list(applied_rule_ids or []),
            hook_id=hook_id,
            scene_id=scene_id,
            metadata=dict(metadata or {}),
        )
        return await get_decision_recorder().record(rec, db=db, caused_by=caused_by)
    except Exception as exc:
        logger.warning(f"emit_decision failed (non-blocking): {exc}")
        return None
