"""P0 contracts: GraphStore Protocol, DecisionRecord, ProvenanceEntry, write-hook inventory.

These tests must stay green without touching production runtimes (no wiring into
FinanceAgent / OntologyGraphQuery / APIs).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from ontology.decision_record import DecisionActorType, DecisionOutcome, DecisionRecord
from ontology.provenance import ProvenanceAgentType, ProvenanceEntry
from ontology.write_hooks import READ_ONLY_TOOLS, WRITE_HOOKS, mutating_tool_names
from storage.graph_store import GraphStore, GraphStoreError, MemoryGraphStore


def test_memory_store_is_graph_store_protocol():
    store = MemoryGraphStore()
    assert isinstance(store, GraphStore)


@pytest.mark.asyncio
async def test_upsert_get_and_find_nodes():
    store = MemoryGraphStore()
    await store.upsert_node("BUD-1", ["Instance", "Budget"], {"type_id": "obj_budget_item", "status": "执行中"})
    await store.upsert_node("EXP-1", ["Instance", "Expense"], {"type_id": "obj_expense_report"})

    node = await store.get_node("BUD-1")
    assert node is not None
    assert "Budget" in node.labels
    assert node.properties["status"] == "执行中"

    found = await store.find_nodes(labels=["Budget"], properties={"type_id": "obj_budget_item"})
    assert [n.node_id for n in found] == ["BUD-1"]
    assert await store.node_count() == 2


@pytest.mark.asyncio
async def test_upsert_edge_requires_live_nodes():
    store = MemoryGraphStore()
    with pytest.raises(GraphStoreError):
        await store.upsert_edge("e1", "missing", "also-missing", "MOUNTED")

    await store.upsert_node("BUD-1", ["Instance"])
    await store.upsert_node("EXP-1", ["Instance"])
    edge = await store.upsert_edge("e1", "EXP-1", "BUD-1", "MOUNTED", {"amount": 100})
    assert edge.rel_type == "MOUNTED"
    loaded = await store.get_edge("e1")
    assert loaded is not None
    assert loaded.properties["amount"] == 100


@pytest.mark.asyncio
async def test_tombstone_hides_node_and_incident_edges():
    store = MemoryGraphStore()
    await store.upsert_node("A", ["Instance"])
    await store.upsert_node("B", ["Instance"])
    await store.upsert_edge("e1", "A", "B", "REL")

    assert await store.tombstone_node("A") is True
    assert await store.get_node("A") is None
    assert await store.get_node("A", include_tombstones=True) is not None
    assert await store.get_edge("e1") is None
    assert await store.node_count() == 1


@pytest.mark.asyncio
async def test_shortest_paths_returns_all_shortest_not_first_edge_only():
    store = MemoryGraphStore()
    for node_id in ("budget", "quadrant", "initiative", "expense"):
        await store.upsert_node(node_id, ["Instance"])
    await store.upsert_edge("e-exp-bud", "expense", "budget", "MOUNTED")
    await store.upsert_edge("e-bud-quad", "budget", "quadrant", "BELONGS")
    await store.upsert_edge("e-bud-init", "budget", "initiative", "ALIGNED")

    paths = await store.shortest_paths("expense", "initiative", max_hops=3)
    assert len(paths) == 1
    assert paths[0].node_ids == ["expense", "budget", "initiative"]
    assert paths[0].hops == 2

    neighbors = await store.neighbors("budget", direction="out")
    neighbor_ids = {n.node_id for n in neighbors}
    assert neighbor_ids == {"quadrant", "initiative"}


@pytest.mark.asyncio
async def test_as_of_filters_bi_temporal_edges():
    store = MemoryGraphStore()
    await store.upsert_node("budget", ["Instance"])
    await store.upsert_node("q1", ["Instance"])
    await store.upsert_node("q2", ["Instance"])

    t0 = datetime(2025, 1, 1, tzinfo=timezone.utc)
    t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    await store.upsert_edge("e-old", "budget", "q1", "BELONGS", valid_from=t0, valid_until=t1)
    await store.upsert_edge("e-new", "budget", "q2", "BELONGS", valid_from=t1)

    as_of_2025 = await store.neighbors("budget", as_of=t0 + timedelta(days=10))
    as_of_2026 = await store.neighbors("budget", as_of=t1 + timedelta(days=10))
    assert [n.node_id for n in as_of_2025] == ["q1"]
    assert [n.node_id for n in as_of_2026] == ["q2"]


def test_decision_record_rejects_bad_confidence_and_empty_category():
    with pytest.raises(ValidationError):
        DecisionRecord(category="expense_submit", scenario="x", outcome=DecisionOutcome.EXECUTED, confidence=1.5)
    with pytest.raises(ValidationError):
        DecisionRecord(category="  ", scenario="x", outcome=DecisionOutcome.BLOCKED)

    rec = DecisionRecord(
        category="expense_submit",
        scenario="提交报销 EXP-1",
        outcome=DecisionOutcome.BLOCKED,
        reasoning="HR-001 无预算ID",
        decision_maker="finance",
        actor_type=DecisionActorType.SOFTWARE_AGENT,
        scene_id="fin.expense_reimbursement",
        entity_ids=["EXP-1"],
        applied_rule_ids=["HR-001"],
        hook_id="tool.submit_expense",
    )
    assert rec.decision_id.startswith("DEC-")
    assert rec.confidence == 1.0


def test_provenance_hash_chain_detects_tamper():
    first = ProvenanceEntry(
        entity_id="EXP-1",
        entity_type="object_instance",
        activity_id="expense.submit",
        agent_id="finance_agent",
        agent_type=ProvenanceAgentType.SOFTWARE_AGENT,
    ).seal()
    second = ProvenanceEntry(
        entity_id="DEC-1",
        entity_type="decision",
        activity_id="decision.record",
        used_entities=["EXP-1"],
        derived_from_id="EXP-1",
    ).seal(first)

    assert first.verify_link(None)
    assert second.verify_link(first)

    tampered = second.model_copy(update={"activity_id": "forged"})
    assert tampered.verify_link(first) is False


def test_write_hooks_cover_all_finance_tools():
    from agents.finance_agent import _TOOL_DEFINITIONS

    tool_names = {item["function"]["name"] for item in _TOOL_DEFINITIONS}
    inventoried = mutating_tool_names() | set(READ_ONLY_TOOLS)
    missing = tool_names - inventoried
    extra_mutating = mutating_tool_names() - tool_names
    overlap = mutating_tool_names() & set(READ_ONLY_TOOLS)

    assert not missing, f"tools not classified in write_hooks: {sorted(missing)}"
    assert not extra_mutating, f"write_hooks tools not in FinanceAgent: {sorted(extra_mutating)}"
    assert not overlap, f"tool listed as both mutating and read-only: {sorted(overlap)}"


def test_p2_min_hooks_are_mutating_and_named():
    p2_min = [h for h in WRITE_HOOKS if h.priority == "p2_min"]
    assert len(p2_min) >= 8
    assert all(h.mutates for h in p2_min)
    assert all(h.category for h in p2_min)
    hook_ids = {h.hook_id for h in p2_min}
    for required in (
        "tool.submit_expense",
        "tool.confirm_closure",
        "tool.write_off",
        "tool.grant_a_class",
        "api.expense.create",
        "api.alert.confirm_closure",
        "api.budget.transfer.execute",
        "api.approval.approve",
    ):
        assert required in hook_ids
