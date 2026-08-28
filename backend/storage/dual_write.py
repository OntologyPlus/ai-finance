"""Write-through GraphStore: Memory is always complete; Neo4j is best-effort.

Reads always hit local memory so queries survive a Neo4j outage.
Failed remote writes are queued and replayed on the next successful remote call.
"""
from __future__ import annotations

from typing import Any, Literal, Mapping, Sequence

from loguru import logger

from storage.graph_store import GraphEdge, GraphNode, GraphPath, MemoryGraphStore

_PENDING_REPLAY_LIMIT = 5000


class DualWriteGraphStore:
    def __init__(self, local: MemoryGraphStore, remote: Any | None = None) -> None:
        self.local = local
        self.remote = remote
        self._pending: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self._flushing = False
        self.remote_healthy = remote is not None

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    async def upsert_node(
        self,
        node_id: str,
        labels: Sequence[str],
        properties: Mapping[str, Any] | None = None,
    ) -> GraphNode:
        result = await self.local.upsert_node(node_id, labels, properties)
        await self._mirror("upsert_node", (node_id, labels, properties), {})
        return result

    async def upsert_edge(
        self,
        edge_id: str,
        source_id: str,
        target_id: str,
        rel_type: str,
        properties: Mapping[str, Any] | None = None,
        *,
        valid_from=None,
        valid_until=None,
    ) -> GraphEdge:
        result = await self.local.upsert_edge(
            edge_id,
            source_id,
            target_id,
            rel_type,
            properties,
            valid_from=valid_from,
            valid_until=valid_until,
        )
        await self._mirror(
            "upsert_edge",
            (edge_id, source_id, target_id, rel_type, properties),
            {"valid_from": valid_from, "valid_until": valid_until},
        )
        return result

    async def get_node(self, node_id: str, *, include_tombstones: bool = False) -> GraphNode | None:
        return await self.local.get_node(node_id, include_tombstones=include_tombstones)

    async def get_edge(self, edge_id: str, *, include_tombstones: bool = False) -> GraphEdge | None:
        return await self.local.get_edge(edge_id, include_tombstones=include_tombstones)

    async def tombstone_node(self, node_id: str) -> bool:
        result = await self.local.tombstone_node(node_id)
        await self._mirror("tombstone_node", (node_id,), {})
        return result

    async def tombstone_edge(self, edge_id: str) -> bool:
        result = await self.local.tombstone_edge(edge_id)
        await self._mirror("tombstone_edge", (edge_id,), {})
        return result

    async def find_nodes(self, **kwargs) -> list[GraphNode]:
        return await self.local.find_nodes(**kwargs)

    async def shortest_paths(self, source_id: str, target_id: str, **kwargs) -> list[GraphPath]:
        return await self.local.shortest_paths(source_id, target_id, **kwargs)

    async def neighbors(
        self,
        node_id: str,
        *,
        direction: Literal["out", "in", "both"] = "both",
        rel_type: str | None = None,
        max_hops: int = 1,
        as_of=None,
    ) -> list[GraphNode]:
        return await self.local.neighbors(
            node_id,
            direction=direction,
            rel_type=rel_type,
            max_hops=max_hops,
            as_of=as_of,
        )

    async def find_paths(self, source_id: str, target_id: str, **kwargs) -> list[GraphPath]:
        return await self.local.find_paths(source_id, target_id, **kwargs)

    async def node_count(self, *, include_tombstones: bool = False) -> int:
        return await self.local.node_count(include_tombstones=include_tombstones)

    async def flush_pending(self) -> int:
        if self._flushing or self.remote is None or not self._pending:
            return 0
        if len(self._pending) > _PENDING_REPLAY_LIMIT:
            logger.warning(
                f"Graph pending queue {len(self._pending)} exceeds limit; "
                "clearing and marking remote for full resync from memory"
            )
            self._pending.clear()
            await self.resync_remote_from_memory()
            return 0

        self._flushing = True
        flushed = 0
        try:
            while self._pending:
                method, args, kwargs = self._pending[0]
                await getattr(self.remote, method)(*args, **kwargs)
                self._pending.pop(0)
                flushed += 1
            self.remote_healthy = True
        except Exception as exc:
            self.remote_healthy = False
            logger.warning(f"Neo4j pending replay stopped after {flushed} ops: {exc}")
        finally:
            self._flushing = False
        return flushed

    async def resync_remote_from_memory(self) -> int:
        if self.remote is None:
            return 0
        count = 0
        try:
            for node in self.local.snapshot_nodes():
                await self.remote.upsert_node(node.node_id, node.labels, node.properties)
                count += 1
            for edge in self.local.snapshot_edges():
                await self.remote.upsert_edge(
                    edge.edge_id,
                    edge.source_id,
                    edge.target_id,
                    edge.rel_type,
                    edge.properties,
                    valid_from=edge.valid_from,
                    valid_until=edge.valid_until,
                )
                count += 1
            self.remote_healthy = True
            self._pending.clear()
        except Exception as exc:
            self.remote_healthy = False
            logger.warning(f"Neo4j resync from memory failed: {exc}")
        return count

    async def _mirror(self, method: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        if self.remote is None:
            return
        try:
            await getattr(self.remote, method)(*args, **kwargs)
            self.remote_healthy = True
            await self.flush_pending()
        except Exception as exc:
            self.remote_healthy = False
            self._pending.append((method, args, kwargs))
            logger.warning(f"Neo4j {method} failed, queued ({self.pending_count} pending): {exc}")
