"""Neo4j GraphStore backend.

All user values go through query parameters. Variable-length hop bounds are
taken from a clamped integer whitelist (1..8), never from raw strings.
Relationship type is stored as property `rel_type` on a single `:RELATED`
edge type so Cypher never interpolates ontology type ids.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Literal, Mapping, Sequence

from loguru import logger

from storage.graph_store import GraphEdge, GraphNode, GraphPath, GraphStoreError

_MAX_HOPS = 8
_INSTANCE_LABEL = "Instance"
_REL_TYPE = "RELATED"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _clamp_hops(max_hops: int) -> int:
    try:
        hops = int(max_hops)
    except (TypeError, ValueError) as exc:
        raise GraphStoreError("max_hops must be an integer") from exc
    return max(1, min(hops, _MAX_HOPS))


def _hop_pattern(max_hops: int) -> str:
    hops = _clamp_hops(max_hops)
    return f"[r:{_REL_TYPE}*1..{hops}]"


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    return json.dumps(value, ensure_ascii=False, default=str)


def _props_for_neo4j(properties: Mapping[str, Any] | None) -> dict[str, Any]:
    return {k: _jsonable(v) for k, v in (properties or {}).items()}


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _node_from_record(raw: Mapping[str, Any]) -> GraphNode:
    props = dict(raw)
    node_id = str(props.pop("node_id", "") or props.get("instance_id", ""))
    tombstone = bool(props.pop("tombstone", False))
    labels_csv = props.pop("labels_csv", "") or ""
    labels = [part for part in str(labels_csv).split(",") if part] or [_INSTANCE_LABEL]
    updated = _parse_dt(props.pop("updated_at", None)) or _utc_now()
    props.pop("instance_id", None)
    return GraphNode(
        node_id=node_id,
        labels=labels,
        properties=props,
        tombstone=tombstone,
        updated_at=updated,
    )


class Neo4jGraphStore:
    """Async Neo4j driver adapter. Missing driver methods raise GraphStoreError."""

    def __init__(self, driver: Any, database: str | None = None) -> None:
        if driver is None:
            raise GraphStoreError("Neo4j driver is required")
        self._driver = driver
        self._database = database
        self._indexes_ready = False

    async def _run(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        await self._ensure_indexes()
        session_kwargs: dict[str, Any] = {}
        if self._database:
            session_kwargs["database"] = self._database
        async with self._driver.session(**session_kwargs) as session:
            result = await session.run(cypher, params or {})
            return await result.data()

    async def _ensure_indexes(self) -> None:
        if self._indexes_ready:
            return
        statements = [
            "CREATE CONSTRAINT instance_node_id IF NOT EXISTS "
            f"FOR (n:{_INSTANCE_LABEL}) REQUIRE n.node_id IS UNIQUE",
            f"CREATE INDEX related_edge_id IF NOT EXISTS FOR ()-[r:{_REL_TYPE}]-() ON (r.edge_id)",
        ]
        session_kwargs: dict[str, Any] = {}
        if self._database:
            session_kwargs["database"] = self._database
        try:
            async with self._driver.session(**session_kwargs) as session:
                for stmt in statements:
                    try:
                        await session.run(stmt)
                    except Exception as exc:
                        logger.debug(f"Neo4j index/constraint skipped: {exc}")
            self._indexes_ready = True
        except Exception as exc:
            logger.warning(f"Neo4j index setup failed: {exc}")
            self._indexes_ready = True

    async def upsert_node(
        self,
        node_id: str,
        labels: Sequence[str],
        properties: Mapping[str, Any] | None = None,
    ) -> GraphNode:
        if not node_id:
            raise GraphStoreError("node_id is required")
        now = _utc_now()
        labels_csv = ",".join(dict.fromkeys(labels)) if labels else _INSTANCE_LABEL
        props = _props_for_neo4j(properties)
        await self._run(
            f"MERGE (n:{_INSTANCE_LABEL} {{node_id: $node_id}}) "
            "SET n.instance_id = $node_id, "
            "    n.tombstone = false, "
            "    n.updated_at = $updated_at, "
            "    n.labels_csv = $labels_csv, "
            "    n += $props",
            {
                "node_id": node_id,
                "updated_at": now.isoformat(),
                "labels_csv": labels_csv,
                "props": props,
            },
        )
        return GraphNode(
            node_id=node_id,
            labels=list(dict.fromkeys(labels)) or [_INSTANCE_LABEL],
            properties=dict(properties or {}),
            tombstone=False,
            updated_at=now,
        )

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
        if not edge_id or not rel_type:
            raise GraphStoreError("edge_id and rel_type are required")
        now = _utc_now()
        props = _props_for_neo4j(properties)
        records = await self._run(
            f"MATCH (a:{_INSTANCE_LABEL} {{node_id: $source_id}}) "
            f"MATCH (b:{_INSTANCE_LABEL} {{node_id: $target_id}}) "
            "WHERE coalesce(a.tombstone, false) = false "
            "  AND coalesce(b.tombstone, false) = false "
            f"OPTIONAL MATCH (a)-[old:{_REL_TYPE} {{edge_id: $edge_id}}]->() "
            "DELETE old "
            f"CREATE (a)-[r:{_REL_TYPE}]->(b) "
            "SET r.edge_id = $edge_id, "
            "    r.rel_type = $rel_type, "
            "    r.tombstone = false, "
            "    r.updated_at = $updated_at, "
            "    r.valid_from = $valid_from, "
            "    r.valid_until = $valid_until, "
            "    r += $props "
            "RETURN r.edge_id AS edge_id",
            {
                "source_id": source_id,
                "target_id": target_id,
                "edge_id": edge_id,
                "rel_type": rel_type,
                "updated_at": now.isoformat(),
                "valid_from": valid_from.isoformat() if valid_from else None,
                "valid_until": valid_until.isoformat() if valid_until else None,
                "props": props,
            },
        )
        if not records:
            raise GraphStoreError(f"source or target node not found: {source_id} -> {target_id}")
        return GraphEdge(
            edge_id=edge_id,
            source_id=source_id,
            target_id=target_id,
            rel_type=rel_type,
            properties=dict(properties or {}),
            valid_from=valid_from,
            valid_until=valid_until,
            tombstone=False,
            updated_at=now,
        )

    async def get_node(
        self,
        node_id: str,
        *,
        include_tombstones: bool = False,
    ) -> GraphNode | None:
        records = await self._run(
            f"MATCH (n:{_INSTANCE_LABEL} {{node_id: $node_id}}) "
            "WHERE $include_tombstones OR coalesce(n.tombstone, false) = false "
            "RETURN n",
            {"node_id": node_id, "include_tombstones": include_tombstones},
        )
        if not records:
            return None
        raw = records[0]["n"]
        return _node_from_record(dict(raw))

    async def get_edge(
        self,
        edge_id: str,
        *,
        include_tombstones: bool = False,
    ) -> GraphEdge | None:
        records = await self._run(
            f"MATCH (a:{_INSTANCE_LABEL})-[r:{_REL_TYPE} {{edge_id: $edge_id}}]->(b:{_INSTANCE_LABEL}) "
            "WHERE $include_tombstones OR coalesce(r.tombstone, false) = false "
            "RETURN r, a.node_id AS source_id, b.node_id AS target_id",
            {"edge_id": edge_id, "include_tombstones": include_tombstones},
        )
        if not records:
            return None
        rel = dict(records[0]["r"])
        return GraphEdge(
            edge_id=str(rel.get("edge_id", edge_id)),
            source_id=records[0]["source_id"],
            target_id=records[0]["target_id"],
            rel_type=str(rel.get("rel_type", "")),
            properties={k: v for k, v in rel.items() if k not in {
                "edge_id", "rel_type", "tombstone", "updated_at", "valid_from", "valid_until",
            }},
            valid_from=_parse_dt(rel.get("valid_from")),
            valid_until=_parse_dt(rel.get("valid_until")),
            tombstone=bool(rel.get("tombstone", False)),
            updated_at=_parse_dt(rel.get("updated_at")) or _utc_now(),
        )

    async def tombstone_node(self, node_id: str) -> bool:
        records = await self._run(
            f"MATCH (n:{_INSTANCE_LABEL} {{node_id: $node_id}}) "
            "SET n.tombstone = true, n.updated_at = $updated_at "
            f"WITH n OPTIONAL MATCH (n)-[r:{_REL_TYPE}]-() "
            "SET r.tombstone = true, r.updated_at = $updated_at "
            "RETURN n.node_id AS node_id",
            {"node_id": node_id, "updated_at": _utc_now().isoformat()},
        )
        return bool(records)

    async def tombstone_edge(self, edge_id: str) -> bool:
        records = await self._run(
            f"MATCH ()-[r:{_REL_TYPE} {{edge_id: $edge_id}}]->() "
            "SET r.tombstone = true, r.updated_at = $updated_at "
            "RETURN r.edge_id AS edge_id",
            {"edge_id": edge_id, "updated_at": _utc_now().isoformat()},
        )
        return bool(records)

    async def find_nodes(
        self,
        *,
        labels: Sequence[str] | None = None,
        properties: Mapping[str, Any] | None = None,
        limit: int = 100,
        include_tombstones: bool = False,
    ) -> list[GraphNode]:
        records = await self._run(
            f"MATCH (n:{_INSTANCE_LABEL}) "
            "WHERE ($include_tombstones OR coalesce(n.tombstone, false) = false) "
            "RETURN n LIMIT $limit",
            {"include_tombstones": include_tombstones, "limit": int(limit)},
        )
        wanted_labels = set(labels or [])
        wanted_props = dict(properties or {})
        nodes: list[GraphNode] = []
        for row in records:
            node = _node_from_record(dict(row["n"]))
            if wanted_labels and not wanted_labels.issubset(node.labels):
                continue
            if wanted_props and any(node.properties.get(k) != v for k, v in wanted_props.items()):
                continue
            nodes.append(node)
        return nodes

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
        hops = _clamp_hops(max_hops)
        pattern = _hop_pattern(hops)
        as_of_s = as_of.isoformat() if as_of else None
        records = await self._run(
            f"MATCH path = (a:{_INSTANCE_LABEL} {{node_id: $source_id}})-{pattern}-(b:{_INSTANCE_LABEL} {{node_id: $target_id}}) "
            "WHERE size(relationships(path)) <= $max_hops "
            "  AND ALL(n IN nodes(path) WHERE coalesce(n.tombstone, false) = false) "
            "  AND ALL(rel IN relationships(path) WHERE coalesce(rel.tombstone, false) = false) "
            "  AND ($rel_type IS NULL OR ALL(rel IN relationships(path) WHERE rel.rel_type = $rel_type)) "
            "  AND ($as_of IS NULL OR ALL(rel IN relationships(path) WHERE "
            "        (rel.valid_from IS NULL OR rel.valid_from <= $as_of) AND "
            "        (rel.valid_until IS NULL OR rel.valid_until > $as_of))) "
            "RETURN [n IN nodes(path) | n.node_id] AS node_ids, "
            "       [rel IN relationships(path) | rel.edge_id] AS edge_ids "
            "ORDER BY size(relationships(path)) ASC "
            "LIMIT $max_paths",
            {
                "source_id": source_id,
                "target_id": target_id,
                "max_hops": hops,
                "rel_type": rel_type,
                "as_of": as_of_s,
                "max_paths": int(max_paths),
            },
        )
        return [
            GraphPath(
                node_ids=row.get("node_ids") or [],
                edge_ids=row.get("edge_ids") or [],
                hops=len(row.get("edge_ids") or []),
            )
            for row in records
            if row.get("node_ids")
        ]

    async def neighbors(
        self,
        node_id: str,
        *,
        direction: Literal["out", "in", "both"] = "both",
        rel_type: str | None = None,
        max_hops: int = 1,
        as_of: datetime | None = None,
    ) -> list[GraphNode]:
        hops = _clamp_hops(max_hops)
        pattern = _hop_pattern(hops)
        if direction == "out":
            match = f"(a:{_INSTANCE_LABEL} {{node_id: $node_id}})-{pattern}->(b:{_INSTANCE_LABEL})"
        elif direction == "in":
            match = f"(a:{_INSTANCE_LABEL} {{node_id: $node_id}})<-{pattern}-(b:{_INSTANCE_LABEL})"
        else:
            match = f"(a:{_INSTANCE_LABEL} {{node_id: $node_id}})-{pattern}-(b:{_INSTANCE_LABEL})"
        as_of_s = as_of.isoformat() if as_of else None
        records = await self._run(
            f"MATCH {match} "
            "WHERE coalesce(a.tombstone, false) = false "
            "  AND coalesce(b.tombstone, false) = false "
            "  AND ALL(rel IN r WHERE coalesce(rel.tombstone, false) = false) "
            "  AND ($rel_type IS NULL OR ALL(rel IN r WHERE rel.rel_type = $rel_type)) "
            "  AND ($as_of IS NULL OR ALL(rel IN r WHERE "
            "        (rel.valid_from IS NULL OR rel.valid_from <= $as_of) AND "
            "        (rel.valid_until IS NULL OR rel.valid_until > $as_of))) "
            "RETURN DISTINCT b",
            {"node_id": node_id, "rel_type": rel_type, "as_of": as_of_s},
        )
        return [_node_from_record(dict(row["b"])) for row in records]

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
        return await self.shortest_paths(
            source_id,
            target_id,
            max_hops=max_hops,
            max_paths=max_paths,
            rel_type=rel_type,
            as_of=as_of,
        )

    async def node_count(self, *, include_tombstones: bool = False) -> int:
        records = await self._run(
            f"MATCH (n:{_INSTANCE_LABEL}) "
            "WHERE $include_tombstones OR coalesce(n.tombstone, false) = false "
            "RETURN count(n) AS c",
            {"include_tombstones": include_tombstones},
        )
        if not records:
            return 0
        return int(records[0].get("c") or 0)
