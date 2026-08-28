"""Active GraphStore handle. ontology.instances projects here; no reverse imports."""
from __future__ import annotations

from typing import Any, Optional

from loguru import logger

from storage.dual_write import DualWriteGraphStore
from storage.graph_store import GraphStore, MemoryGraphStore

_active: GraphStore | None = None


def set_active_graph_store(store: GraphStore | None) -> None:
    global _active
    _active = store


def get_active_graph_store() -> GraphStore | None:
    return _active


async def init_graph_store(
    neo4j_driver: Any | None = None,
    database: str | None = None,
) -> GraphStore:
    """Build Memory + optional Neo4j dual-write store and register it as active."""
    memory = MemoryGraphStore()
    remote = None
    if neo4j_driver is not None:
        try:
            from storage.neo4j_store import Neo4jGraphStore

            remote = Neo4jGraphStore(neo4j_driver, database=database)
        except Exception as exc:
            logger.warning(f"Neo4jGraphStore init failed, memory-only: {exc}")
            remote = None

    store: GraphStore
    if remote is not None:
        store = DualWriteGraphStore(memory, remote)
        logger.info("GraphStore: DualWrite (Memory + Neo4j)")
    else:
        store = memory
        logger.info("GraphStore: Memory only")

    set_active_graph_store(store)
    return store
