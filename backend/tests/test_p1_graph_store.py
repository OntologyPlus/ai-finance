"""P1: GraphStore dual-write, incremental hydrate, OntologyGraphQuery protocol-only."""
from __future__ import annotations

from pathlib import Path

import pytest

from ontology.graph_projection import hydrate_from_instances
from ontology.graph_query import OntologyGraphQuery
from ontology.instances import OntologyInstanceManager
from storage.dual_write import DualWriteGraphStore
from storage.graph_store import GraphStore, MemoryGraphStore
from storage.runtime import set_active_graph_store


BACKEND = Path(__file__).resolve().parents[1]


class FlakyRemote(MemoryGraphStore):
    """Remote stand-in that can simulate a Neo4j outage."""

    def __init__(self) -> None:
        super().__init__()
        self.fail = False

    async def upsert_node(self, *args, **kwargs):
        if self.fail:
            raise RuntimeError("neo4j down")
        return await super().upsert_node(*args, **kwargs)

    async def upsert_edge(self, *args, **kwargs):
        if self.fail:
            raise RuntimeError("neo4j down")
        return await super().upsert_edge(*args, **kwargs)

    async def tombstone_node(self, *args, **kwargs):
        if self.fail:
            raise RuntimeError("neo4j down")
        return await super().tombstone_node(*args, **kwargs)

    async def tombstone_edge(self, *args, **kwargs):
        if self.fail:
            raise RuntimeError("neo4j down")
        return await super().tombstone_edge(*args, **kwargs)


@pytest.fixture
def isolated_store():
    set_active_graph_store(None)
    yield
    set_active_graph_store(None)


def test_no_detach_delete_in_graph_stack():
    for rel in (
        "ontology/graph_query.py",
        "ontology/graph_projection.py",
        "storage/neo4j_store.py",
        "storage/dual_write.py",
        "storage/graph_store.py",
    ):
        text = (BACKEND / rel).read_text(encoding="utf-8")
        assert "DETACH DELETE" not in text, f"{rel} still wipes the graph"


def test_neo4j_cypher_is_parameterized():
    text = (BACKEND / "storage/neo4j_store.py").read_text(encoding="utf-8")
    assert "$node_id" in text
    assert "$edge_id" in text
    assert "$source_id" in text
    assert "$rel_type" in text
    assert "*1..{max_depth}" not in text
    assert "dir_clause" not in text


def test_dual_write_is_graph_store_protocol():
    store = DualWriteGraphStore(MemoryGraphStore(), MemoryGraphStore())
    assert isinstance(store, GraphStore)


@pytest.mark.asyncio
async def test_query_survives_remote_outage(isolated_store):
    local = MemoryGraphStore()
    remote = FlakyRemote()
    store = DualWriteGraphStore(local, remote)
    set_active_graph_store(store)

    mgr = OntologyInstanceManager()
    await mgr.create_object_instance("obj_budget_item", "BUD-1", {"name": "预算A"})
    await mgr.create_object_instance("obj_expense_report", "EXP-1", {"amount": 100})
    await mgr.create_relation_instance("rel_mount", "EXP-1", "BUD-1")

    remote.fail = True
    await mgr.create_object_instance("obj_budget_quadrant", "Q-1", {"name": "发展"})
    assert store.pending_count >= 1

    gq = OntologyGraphQuery(mgr, store=store)
    related = await gq.find_related("EXP-1", direction="source", max_depth=1)
    assert related.total_count == 1
    assert related.objects[0]["instance_id"] == "BUD-1"

    paths = await gq.find_path("EXP-1", "BUD-1")
    assert paths
    assert paths[0][0] == "EXP-1"
    assert paths[0][-1] == "BUD-1"


@pytest.mark.asyncio
async def test_pending_flush_when_remote_recovers(isolated_store):
    local = MemoryGraphStore()
    remote = FlakyRemote()
    store = DualWriteGraphStore(local, remote)

    remote.fail = True
    await store.upsert_node("A", ["Instance"], {"k": 1})
    assert store.pending_count == 1
    assert await remote.get_node("A") is None
    assert await store.get_node("A") is not None

    remote.fail = False
    await store.upsert_node("B", ["Instance"], {"k": 2})
    assert store.pending_count == 0
    assert await remote.get_node("A") is not None
    assert await remote.get_node("B") is not None
    assert store.remote_healthy is True


@pytest.mark.asyncio
async def test_hydrate_is_incremental_upsert(isolated_store):
    store = MemoryGraphStore()
    set_active_graph_store(store)
    mgr = OntologyInstanceManager()
    mgr._object_instances["BUD-1"] = type("Obj", (), {
        "instance_id": "BUD-1",
        "type_id": "obj_budget_item",
        "attributes": {"name": "n"},
        "status": "active",
    })()
    mgr._relation_instances = {}

    n1 = await hydrate_from_instances(mgr, store=store)
    n2 = await hydrate_from_instances(mgr, store=store)
    assert n1 == 1
    assert n2 == 1
    assert await store.node_count() == 1
    node = await store.get_node("BUD-1")
    assert node is not None
    assert node.properties["type_id"] == "obj_budget_item"


@pytest.mark.asyncio
async def test_instance_crud_projects_and_tombstones(isolated_store):
    store = MemoryGraphStore()
    set_active_graph_store(store)
    mgr = OntologyInstanceManager()

    await mgr.create_object_instance("obj_budget_item", "BUD-1", {"name": "n"})
    assert await store.get_node("BUD-1") is not None

    await mgr.update_object_instance("BUD-1", status="执行中")
    node = await store.get_node("BUD-1")
    assert node is not None
    assert node.properties["status"] == "执行中"

    await mgr.create_object_instance("obj_expense_report", "EXP-1", {"amount": 1})
    rel = await mgr.create_relation_instance("rel_mount", "EXP-1", "BUD-1")
    assert await store.get_edge(rel.instance_id) is not None

    await mgr.delete_object_instance("EXP-1")
    assert await store.get_node("EXP-1") is None
    assert await store.get_edge(rel.instance_id) is None


@pytest.mark.asyncio
async def test_graph_query_uses_injected_store_not_driver():
    store = MemoryGraphStore()
    await store.upsert_node("A", ["Instance"])
    await store.upsert_node("B", ["Instance"])
    await store.upsert_edge("e1", "A", "B", "rel_mount")
    mgr = OntologyInstanceManager()
    gq = OntologyGraphQuery(mgr, store=store, neo4j_driver="must-be-ignored")
    assert gq.store is store
    paths = await gq.find_path("A", "B")
    assert paths == [["A", "B"]]
