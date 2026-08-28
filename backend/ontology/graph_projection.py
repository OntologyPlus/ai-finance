"""Project ontology instances onto the active GraphStore (incremental upsert)."""
from __future__ import annotations

from typing import Any

from loguru import logger

from storage.graph_store import GraphStore
from storage.runtime import get_active_graph_store


def _object_labels(type_id: str) -> list[str]:
    labels = ["Instance"]
    if type_id:
        labels.append(type_id)
    return labels


async def project_object(inst: Any, store: GraphStore | None = None) -> None:
    target = store if store is not None else get_active_graph_store()
    if target is None:
        return
    props = dict(inst.attributes or {})
    props["type_id"] = inst.type_id
    props["status"] = inst.status
    await target.upsert_node(inst.instance_id, _object_labels(inst.type_id), props)


async def project_relation(rel: Any, store: GraphStore | None = None) -> None:
    target = store if store is not None else get_active_graph_store()
    if target is None:
        return
    await target.upsert_edge(
        rel.instance_id,
        rel.source_instance_id,
        rel.target_instance_id,
        rel.type_id,
        dict(rel.attributes or {}),
        valid_from=getattr(rel, "valid_from", None),
        valid_until=getattr(rel, "valid_to", None) or getattr(rel, "valid_until", None),
    )


async def tombstone_object(instance_id: str, store: GraphStore | None = None) -> None:
    target = store if store is not None else get_active_graph_store()
    if target is None:
        return
    await target.tombstone_node(instance_id)


async def tombstone_relation(instance_id: str, store: GraphStore | None = None) -> None:
    target = store if store is not None else get_active_graph_store()
    if target is None:
        return
    await target.tombstone_edge(instance_id)


async def hydrate_from_instances(manager: Any, store: GraphStore | None = None) -> int:
    """Idempotent upsert of all live instances. Never wipes the remote graph."""
    target = store if store is not None else get_active_graph_store()
    if target is None:
        return 0
    count = 0
    for inst in getattr(manager, "_object_instances", {}).values():
        await project_object(inst, store=target)
        count += 1
    for rel in getattr(manager, "_relation_instances", {}).values():
        try:
            await project_relation(rel, store=target)
            count += 1
        except Exception as exc:
            logger.warning(f"Skip relation {rel.instance_id} during hydrate: {exc}")
    logger.info(f"Graph hydrate upserted {count} instance records (incremental, no wipe)")
    return count
