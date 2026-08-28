"""Ontology graph queries — GraphStore Protocol only.

MySQL remains SoT. This module never talks to a Neo4j driver and never
issues a full graph wipe.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from loguru import logger
from pydantic import BaseModel, Field

from ontology.instances import ObjectInstance, OntologyInstanceManager, get_instance_manager
from storage.graph_store import GraphStore, MemoryGraphStore
from storage.runtime import get_active_graph_store


class GraphQueryResult(BaseModel):
    objects: List[Dict[str, Any]] = Field(default_factory=list)
    relations: List[Dict[str, Any]] = Field(default_factory=list)
    paths: List[List[str]] = Field(default_factory=list, description="路径，每条路径是instance_id列表")
    total_count: int = 0


_DIR_MAP = {"source": "out", "target": "in", "both": "both"}


class OntologyGraphQuery:
    def __init__(
        self,
        instance_manager: OntologyInstanceManager,
        store: GraphStore | None = None,
        neo4j_driver: Any = None,
    ) -> None:
        self._manager = instance_manager
        if store is not None:
            self._store = store
        elif neo4j_driver is not None:
            # Backward-compatible constructor: wrap driver, do not keep it.
            from storage.dual_write import DualWriteGraphStore
            from storage.graph_store import MemoryGraphStore as Mem
            from storage.neo4j_store import Neo4jGraphStore

            memory = Mem()
            try:
                remote = Neo4jGraphStore(neo4j_driver)
                self._store = DualWriteGraphStore(memory, remote)
            except Exception as exc:
                logger.warning(f"Neo4j wrap failed, using memory: {exc}")
                self._store = memory
        else:
            self._store = get_active_graph_store() or MemoryGraphStore()

    @property
    def store(self) -> GraphStore:
        return self._store

    def rebuild_adjacency(self) -> None:
        """Kept for callers. GraphStore is updated incrementally; no adjacency rebuild."""
        return None

    async def find_by_type(
        self,
        type_id: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[ObjectInstance]:
        results = await self._manager.query_objects(type_id=type_id)
        if filters:
            for key, value in filters.items():
                results = [inst for inst in results if inst.attributes.get(key) == value]
        return results

    async def find_related(
        self,
        instance_id: str,
        relation_type_id: Optional[str] = None,
        direction: str = "both",
        max_depth: int = 1,
    ) -> GraphQueryResult:
        store_dir = _DIR_MAP.get(direction, "both")
        neighbors = await self._store.neighbors(
            instance_id,
            direction=store_dir,  # type: ignore[arg-type]
            rel_type=relation_type_id,
            max_hops=max(1, max_depth),
        )
        neighbor_ids = {n.node_id for n in neighbors}
        objects_list: List[Dict[str, Any]] = []
        for node in neighbors:
            inst = await self._manager.get_object_instance(node.node_id)
            if inst is not None:
                objects_list.append(
                    {
                        "instance_id": inst.instance_id,
                        "type_id": inst.type_id,
                        "attributes": inst.attributes,
                        "status": inst.status,
                    }
                )
            else:
                objects_list.append(
                    {
                        "instance_id": node.node_id,
                        "type_id": node.properties.get("type_id"),
                        "attributes": node.properties,
                        "status": node.properties.get("status"),
                    }
                )

        relations_list: List[Dict[str, Any]] = []
        seen_rel: Set[str] = set()
        related_rels = await self._manager.get_relations_for_object(instance_id, direction="both")
        for rel in related_rels:
            if relation_type_id is not None and rel.type_id != relation_type_id:
                continue
            other = (
                rel.target_instance_id
                if rel.source_instance_id == instance_id
                else rel.source_instance_id
            )
            if other not in neighbor_ids and max_depth <= 1:
                continue
            if rel.instance_id in seen_rel:
                continue
            seen_rel.add(rel.instance_id)
            relations_list.append(
                {
                    "instance_id": rel.instance_id,
                    "type_id": rel.type_id,
                    "source_instance_id": rel.source_instance_id,
                    "target_instance_id": rel.target_instance_id,
                    "attributes": rel.attributes,
                }
            )

        return GraphQueryResult(
            objects=objects_list,
            relations=relations_list,
            total_count=len(objects_list),
        )

    async def find_path(self, source_id: str, target_id: str, max_depth: int = 5) -> List[List[str]]:
        paths = await self._store.find_paths(source_id, target_id, max_hops=max(1, max_depth))
        return [p.node_ids for p in paths]

    async def aggregate_by_field(
        self,
        type_id: str,
        field: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, int]:
        instances = await self.find_by_type(type_id, filters)
        result: Dict[str, int] = {}
        for inst in instances:
            value = inst.attributes.get(field)
            key = str(value) if value is not None else "__none__"
            result[key] = result.get(key, 0) + 1
        return result

    async def traverse_and_filter(
        self,
        start_id: str,
        relation_type_id: str,
        direction: str = "source",
        filter_fn=None,
    ) -> List[ObjectInstance]:
        store_dir = _DIR_MAP.get(direction, "out")
        neighbors = await self._store.neighbors(
            start_id,
            direction=store_dir,  # type: ignore[arg-type]
            rel_type=relation_type_id,
            max_hops=1,
        )
        results: List[ObjectInstance] = []
        seen: Set[str] = set()
        for node in neighbors:
            if node.node_id in seen:
                continue
            seen.add(node.node_id)
            neighbor = await self._manager.get_object_instance(node.node_id)
            if neighbor is None:
                continue
            if filter_fn is None or filter_fn(neighbor):
                results.append(neighbor)
        return results

    async def sync_to_neo4j(self) -> int:
        """Incremental upsert of current instances. Does not wipe the graph."""
        from ontology.graph_projection import hydrate_from_instances

        return await hydrate_from_instances(self._manager, store=self._store)


_graph_query: Optional[OntologyGraphQuery] = None


def get_graph_query() -> OntologyGraphQuery:
    global _graph_query
    if _graph_query is None:
        store = get_active_graph_store()
        _graph_query = OntologyGraphQuery(get_instance_manager(), store=store)
    return _graph_query


def set_graph_query(query: OntologyGraphQuery | None) -> None:
    global _graph_query
    _graph_query = query
