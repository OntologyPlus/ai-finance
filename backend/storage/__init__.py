"""Storage abstractions. Layer 0; ontology/engines depend on this, never the reverse."""

from storage.dual_write import DualWriteGraphStore
from storage.graph_store import (
    GraphEdge,
    GraphNode,
    GraphPath,
    GraphStore,
    GraphStoreError,
    MemoryGraphStore,
)
from storage.runtime import get_active_graph_store, init_graph_store, set_active_graph_store

__all__ = [
    "DualWriteGraphStore",
    "GraphEdge",
    "GraphNode",
    "GraphPath",
    "GraphStore",
    "GraphStoreError",
    "MemoryGraphStore",
    "get_active_graph_store",
    "init_graph_store",
    "set_active_graph_store",
]
