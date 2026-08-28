"""GraphStore protocol and in-memory backend.

MySQL is the system of record. GraphStore is a projection:
upsert on instance events, tombstone instead of hard delete.
"""
from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Literal, Mapping, Protocol, Sequence, runtime_checkable

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GraphStoreError(ValueError):
    """Contract violation (missing node, bad hop count, etc.)."""


class GraphNode(BaseModel):
    node_id: str
    labels: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    tombstone: bool = False
    updated_at: datetime = Field(default_factory=_utc_now)


class GraphEdge(BaseModel):
    edge_id: str
    source_id: str
    target_id: str
    rel_type: str
    properties: dict[str, Any] = Field(default_factory=dict)
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    tombstone: bool = False
    updated_at: datetime = Field(default_factory=_utc_now)

    def is_valid_at(self, as_of: datetime | None) -> bool:
        if as_of is None:
            return True
        if self.valid_from is not None and as_of < self.valid_from:
            return False
        if self.valid_until is not None and as_of >= self.valid_until:
            return False
        return True


class GraphPath(BaseModel):
    node_ids: list[str]
    edge_ids: list[str]
    hops: int = 0


@runtime_checkable
class GraphStore(Protocol):
    """Backend-agnostic graph surface. No Cypher in the protocol.

    MySQL remains system of record. Implementations are projections:
    upsert on instance events, tombstone instead of hard delete.
    """

    async def upsert_node(
        self,
        node_id: str,
        labels: Sequence[str],
        properties: Mapping[str, Any] | None = None,
    ) -> GraphNode: ...

    async def upsert_edge(
        self,
        edge_id: str,
        source_id: str,
        target_id: str,
        rel_type: str,
        properties: Mapping[str, Any] | None = None,
        *,
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
    ) -> GraphEdge: ...

    async def get_node(
        self,
        node_id: str,
        *,
        include_tombstones: bool = False,
    ) -> GraphNode | None: ...

    async def get_edge(
        self,
        edge_id: str,
        *,
        include_tombstones: bool = False,
    ) -> GraphEdge | None: ...

    async def tombstone_node(self, node_id: str) -> bool: ...

    async def tombstone_edge(self, edge_id: str) -> bool: ...

    async def find_nodes(
        self,
        *,
        labels: Sequence[str] | None = None,
        properties: Mapping[str, Any] | None = None,
        limit: int = 100,
        include_tombstones: bool = False,
    ) -> list[GraphNode]: ...

    async def shortest_paths(
        self,
        source_id: str,
        target_id: str,
        *,
        max_hops: int = 5,
        max_paths: int = 8,
        rel_type: str | None = None,
        as_of: datetime | None = None,
    ) -> list[GraphPath]: ...

    async def neighbors(
        self,
        node_id: str,
        *,
        direction: Literal["out", "in", "both"] = "both",
        rel_type: str | None = None,
        max_hops: int = 1,
        as_of: datetime | None = None,
    ) -> list[GraphNode]: ...

    async def find_paths(
        self,
        source_id: str,
        target_id: str,
        *,
        max_hops: int = 5,
        max_paths: int = 20,
        rel_type: str | None = None,
        as_of: datetime | None = None,
    ) -> list[GraphPath]: ...

    async def node_count(self, *, include_tombstones: bool = False) -> int: ...


class MemoryGraphStore:
    """In-memory GraphStore. Used as Neo4j fallback in P1 and as the P0 contract fixture."""

    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: dict[str, GraphEdge] = {}
        self._out: dict[str, list[str]] = defaultdict(list)
        self._in: dict[str, list[str]] = defaultdict(list)

    async def upsert_node(
        self,
        node_id: str,
        labels: Sequence[str],
        properties: Mapping[str, Any] | None = None,
    ) -> GraphNode:
        if not node_id:
            raise GraphStoreError("node_id is required")
        existing = self._nodes.get(node_id)
        merged_props = dict(existing.properties) if existing else {}
        if properties:
            merged_props.update(properties)
        node = GraphNode(
            node_id=node_id,
            labels=list(dict.fromkeys(labels)),
            properties=merged_props,
            tombstone=False,
        )
        self._nodes[node_id] = node
        return node

    async def upsert_edge(
        self,
        edge_id: str,
        source_id: str,
        target_id: str,
        rel_type: str,
        properties: Mapping[str, Any] | None = None,
        *,
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
    ) -> GraphEdge:
        if not edge_id:
            raise GraphStoreError("edge_id is required")
        if not rel_type:
            raise GraphStoreError("rel_type is required")
        if source_id not in self._nodes or self._nodes[source_id].tombstone:
            raise GraphStoreError(f"source node not found: {source_id}")
        if target_id not in self._nodes or self._nodes[target_id].tombstone:
            raise GraphStoreError(f"target node not found: {target_id}")

        existing = self._edges.get(edge_id)
        merged_props = dict(existing.properties) if existing else {}
        if properties:
            merged_props.update(properties)
        if existing:
            self._remove_adjacency(existing)

        edge = GraphEdge(
            edge_id=edge_id,
            source_id=source_id,
            target_id=target_id,
            rel_type=rel_type,
            properties=merged_props,
            valid_from=valid_from if valid_from is not None else (existing.valid_from if existing else None),
            valid_until=valid_until if valid_until is not None else (existing.valid_until if existing else None),
            tombstone=False,
        )
        self._edges[edge_id] = edge
        self._out[source_id].append(edge_id)
        self._in[target_id].append(edge_id)
        return edge

    async def get_node(
        self,
        node_id: str,
        *,
        include_tombstones: bool = False,
    ) -> GraphNode | None:
        node = self._nodes.get(node_id)
        if node is None:
            return None
        if node.tombstone and not include_tombstones:
            return None
        return node

    async def get_edge(
        self,
        edge_id: str,
        *,
        include_tombstones: bool = False,
    ) -> GraphEdge | None:
        edge = self._edges.get(edge_id)
        if edge is None:
            return None
        if edge.tombstone and not include_tombstones:
            return None
        return edge

    async def tombstone_node(self, node_id: str) -> bool:
        node = self._nodes.get(node_id)
        if node is None:
            return False
        node.tombstone = True
        node.updated_at = _utc_now()
        for edge_id in list(self._out.get(node_id, [])) + list(self._in.get(node_id, [])):
            await self.tombstone_edge(edge_id)
        return True

    async def tombstone_edge(self, edge_id: str) -> bool:
        edge = self._edges.get(edge_id)
        if edge is None:
            return False
        edge.tombstone = True
        edge.updated_at = _utc_now()
        return True

    async def find_nodes(
        self,
        *,
        labels: Sequence[str] | None = None,
        properties: Mapping[str, Any] | None = None,
        limit: int = 100,
        include_tombstones: bool = False,
    ) -> list[GraphNode]:
        wanted_labels = set(labels or [])
        matches: list[GraphNode] = []
        for node in self._nodes.values():
            if node.tombstone and not include_tombstones:
                continue
            if wanted_labels and not wanted_labels.issubset(node.labels):
                continue
            if properties:
                if any(node.properties.get(k) != v for k, v in properties.items()):
                    continue
            matches.append(node)
            if len(matches) >= limit:
                break
        return matches

    async def shortest_paths(
        self,
        source_id: str,
        target_id: str,
        *,
        max_hops: int = 5,
        max_paths: int = 8,
        rel_type: str | None = None,
        as_of: datetime | None = None,
    ) -> list[GraphPath]:
        if max_hops < 1:
            raise GraphStoreError("max_hops must be >= 1")
        if await self.get_node(source_id) is None or await self.get_node(target_id) is None:
            return []
        if source_id == target_id:
            return [GraphPath(node_ids=[source_id], edge_ids=[], hops=0)]

        paths: list[GraphPath] = []
        queue: deque[tuple[str, list[str], list[str]]] = deque()
        queue.append((source_id, [source_id], []))
        found_hops: int | None = None

        while queue and len(paths) < max_paths:
            current, nodes, edges = queue.popleft()
            hops = len(edges)
            if found_hops is not None and hops > found_hops:
                break
            if hops >= max_hops:
                continue
            for edge in self._live_out_edges(current, rel_type=rel_type, as_of=as_of):
                nxt = edge.target_id
                if nxt in nodes:
                    continue
                next_nodes = nodes + [nxt]
                next_edges = edges + [edge.edge_id]
                if nxt == target_id:
                    found_hops = len(next_edges)
                    paths.append(GraphPath(node_ids=next_nodes, edge_ids=next_edges, hops=found_hops))
                    if len(paths) >= max_paths:
                        break
                    continue
                queue.append((nxt, next_nodes, next_edges))
        return paths

    async def neighbors(
        self,
        node_id: str,
        *,
        direction: Literal["out", "in", "both"] = "both",
        rel_type: str | None = None,
        max_hops: int = 1,
        as_of: datetime | None = None,
    ) -> list[GraphNode]:
        if await self.get_node(node_id) is None:
            return []
        seen: dict[str, GraphNode] = {}
        queue: deque[tuple[str, int]] = deque([(node_id, 0)])
        visited = {node_id}

        while queue:
            current, depth = queue.popleft()
            if depth >= max_hops:
                continue
            for edge in self._incident_edges(current, direction, rel_type, as_of):
                neighbor_id = edge.target_id if edge.source_id == current else edge.source_id
                neighbor = await self.get_node(neighbor_id)
                if neighbor is None:
                    continue
                seen[neighbor_id] = neighbor
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    queue.append((neighbor_id, depth + 1))
        return list(seen.values())

    async def find_paths(
        self,
        source_id: str,
        target_id: str,
        *,
        max_hops: int = 5,
        max_paths: int = 20,
        rel_type: str | None = None,
        as_of: datetime | None = None,
    ) -> list[GraphPath]:
        """Undirected simple paths up to max_hops (matches former in-memory BFS)."""
        if max_hops < 1:
            raise GraphStoreError("max_hops must be >= 1")
        if await self.get_node(source_id) is None or await self.get_node(target_id) is None:
            return []
        if source_id == target_id:
            return [GraphPath(node_ids=[source_id], edge_ids=[], hops=0)]

        paths: list[GraphPath] = []
        queue: deque[tuple[str, list[str], list[str]]] = deque()
        queue.append((source_id, [source_id], []))

        while queue and len(paths) < max_paths:
            current, nodes, edges = queue.popleft()
            if len(edges) >= max_hops:
                continue
            for edge in self._incident_edges(current, "both", rel_type, as_of):
                nxt = edge.target_id if edge.source_id == current else edge.source_id
                if nxt in nodes:
                    continue
                next_nodes = nodes + [nxt]
                next_edges = edges + [edge.edge_id]
                if nxt == target_id:
                    paths.append(GraphPath(node_ids=next_nodes, edge_ids=next_edges, hops=len(next_edges)))
                    if len(paths) >= max_paths:
                        break
                    continue
                queue.append((nxt, next_nodes, next_edges))
        return paths

    async def node_count(self, *, include_tombstones: bool = False) -> int:
        if include_tombstones:
            return len(self._nodes)
        return sum(1 for n in self._nodes.values() if not n.tombstone)

    def snapshot_nodes(self, *, include_tombstones: bool = False) -> list[GraphNode]:
        if include_tombstones:
            return list(self._nodes.values())
        return [n for n in self._nodes.values() if not n.tombstone]

    def snapshot_edges(self, *, include_tombstones: bool = False) -> list[GraphEdge]:
        if include_tombstones:
            return list(self._edges.values())
        return [e for e in self._edges.values() if not e.tombstone]

    def _remove_adjacency(self, edge: GraphEdge) -> None:
        if edge.edge_id in self._out.get(edge.source_id, []):
            self._out[edge.source_id] = [e for e in self._out[edge.source_id] if e != edge.edge_id]
        if edge.edge_id in self._in.get(edge.target_id, []):
            self._in[edge.target_id] = [e for e in self._in[edge.target_id] if e != edge.edge_id]

    def _live_out_edges(
        self,
        node_id: str,
        *,
        rel_type: str | None,
        as_of: datetime | None,
    ) -> list[GraphEdge]:
        result: list[GraphEdge] = []
        for edge_id in self._out.get(node_id, []):
            edge = self._edges.get(edge_id)
            if edge is None or edge.tombstone:
                continue
            if rel_type and edge.rel_type != rel_type:
                continue
            if not edge.is_valid_at(as_of):
                continue
            result.append(edge)
        return result

    def _incident_edges(
        self,
        node_id: str,
        direction: Literal["out", "in", "both"],
        rel_type: str | None,
        as_of: datetime | None,
    ) -> list[GraphEdge]:
        ids: list[str] = []
        if direction in ("out", "both"):
            ids.extend(self._out.get(node_id, []))
        if direction in ("in", "both"):
            ids.extend(self._in.get(node_id, []))
        result: list[GraphEdge] = []
        seen: set[str] = set()
        for edge_id in ids:
            if edge_id in seen:
                continue
            seen.add(edge_id)
            edge = self._edges.get(edge_id)
            if edge is None or edge.tombstone:
                continue
            if rel_type and edge.rel_type != rel_type:
                continue
            if not edge.is_valid_at(as_of):
                continue
            result.append(edge)
        return result
