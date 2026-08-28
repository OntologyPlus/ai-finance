"""P2: DecisionRecorder persist/project, HR-001 blocked eval, chain, precedents."""
from __future__ import annotations

import pytest

from engines.expense_reimbursement import ExpenseReimbursementEngine
from ontology.decision_record import DecisionActorType, DecisionOutcome
from ontology.decision_recorder import (
    DecisionRecorder,
    REL_APPLIED_POLICY,
    REL_BASED_ON,
    REL_CAUSED,
    emit_decision,
    get_decision_recorder,
    set_decision_recorder,
)
from storage.graph_store import MemoryGraphStore
from storage.runtime import set_active_graph_store


class DummyDB:
    def add(self, _obj) -> None:
        return None

    async def flush(self) -> None:
        return None

    async def get(self, *_args, **_kwargs):
        return None


@pytest.fixture
def isolated_decisions():
    recorder = DecisionRecorder()
    store = MemoryGraphStore()
    set_decision_recorder(recorder)
    set_active_graph_store(store)
    yield recorder, store
    recorder.reset()
    set_decision_recorder(None)
    set_active_graph_store(None)


@pytest.mark.asyncio
async def test_submit_without_budget_records_blocked_hr001(isolated_decisions):
    recorder, store = isolated_decisions
    engine = ExpenseReimbursementEngine()
    with pytest.raises(ValueError, match="HR-001"):
        await engine.submit_expense({"amount": 100, "applicant_id": "u1"}, DummyDB())

    recs = recorder.all_records()
    assert len(recs) == 1
    rec = recs[0]
    assert rec.category == "expense_submit"
    assert rec.outcome == DecisionOutcome.BLOCKED
    assert rec.applied_rule_ids == ["HR-001"]
    assert rec.decision_maker == "u1"
    node = await store.get_node(rec.decision_id)
    assert node is not None
    assert "Decision" in node.labels
    policy = await store.get_node("HR-001")
    assert policy is not None
    edge = await store.get_edge(f"{rec.decision_id}:{REL_APPLIED_POLICY}:HR-001")
    assert edge is not None


@pytest.mark.asyncio
async def test_write_off_chain_answers_who_hr_budget_strategy(isolated_decisions):
    recorder, store = isolated_decisions
    await store.upsert_node("EXP-1", ["Instance", "obj_expense_report"])
    await store.upsert_node("BUD-1", ["Instance", "obj_budget_item"])
    await store.upsert_node("SI-1", ["Instance", "obj_strategic_initiative"])
    await store.upsert_edge("e-bench", "BUD-1", "SI-1", "rel_benchmark")

    submit = await emit_decision(
        category="expense_submit",
        scenario="提交报销 EXP-1",
        outcome="executed",
        decision_maker="u1",
        entity_ids=["EXP-1", "BUD-1"],
        applied_rule_ids=["HR-001"],
        metadata={"budget_id": "BUD-1"},
    )
    approve = await emit_decision(
        category="approval_final",
        scenario="终审 EXP-1",
        outcome="approved",
        decision_maker="bp-wang",
        actor_type=DecisionActorType.PERSON,
        entity_ids=["EXP-1", "BUD-1"],
        applied_rule_ids=["HR-AP-002"],
        metadata={"budget_id": "BUD-1"},
    )
    write_off = await emit_decision(
        category="budget_write_off",
        scenario="核销 EXP-1",
        outcome="executed",
        decision_maker="system",
        entity_ids=["EXP-1", "BUD-1"],
        applied_rule_ids=["HR-WO-001"],
        metadata={"budget_id": "BUD-1"},
    )
    assert submit and approve and write_off

    caused = await store.get_edge(f"{submit.decision_id}:{REL_CAUSED}:{approve.decision_id}")
    assert caused is not None
    caused2 = await store.get_edge(f"{approve.decision_id}:{REL_CAUSED}:{write_off.decision_id}")
    assert caused2 is not None
    based = await store.get_edge(f"{write_off.decision_id}:{REL_BASED_ON}:EXP-1")
    assert based is not None

    explained = await recorder.explain_expense("EXP-1", store=store)
    assert explained["approvers"] == ["bp-wang"]
    assert "HR-001" in explained["applied_rule_ids"]
    assert "HR-WO-001" in explained["applied_rule_ids"]
    assert explained["budget_ids"] == ["BUD-1"]
    assert "SI-1" in explained["strategic_initiatives"]

    chain = await recorder.trace_decision_chain(write_off.decision_id, store=store)
    rels = {h["rel"] for h in chain["hops"]}
    assert REL_CAUSED in rels
    assert REL_BASED_ON in rels


@pytest.mark.asyncio
async def test_precedents_exact_category_and_rule_set(isolated_decisions):
    recorder, _store = isolated_decisions
    a = await emit_decision(
        category="expense_submit",
        scenario="s1",
        outcome="blocked",
        applied_rule_ids=["HR-001"],
        entity_ids=["EXP-A"],
    )
    await emit_decision(
        category="expense_submit",
        scenario="s2",
        outcome="blocked",
        applied_rule_ids=["HR-001"],
        entity_ids=["EXP-B"],
    )
    await emit_decision(
        category="expense_submit",
        scenario="s3",
        outcome="blocked",
        applied_rule_ids=["HR-001", "HR-002"],
        entity_ids=["EXP-C"],
    )
    await emit_decision(
        category="alert_closure",
        scenario="s4",
        outcome="executed",
        applied_rule_ids=["HR-001"],
        entity_ids=["AL-1"],
    )
    hits = recorder.find_precedents("expense_submit", ["HR-001"], exclude_id=a.decision_id)
    assert len(hits) == 1
    assert hits[0].entity_ids == ["EXP-B"]


def test_decision_recorder_is_process_singleton(isolated_decisions):
    recorder, _store = isolated_decisions
    assert get_decision_recorder() is recorder
