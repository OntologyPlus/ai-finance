import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import select, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from models.ontology import OntologyObjectInstance as DBObjectInstance, OntologyRelationInstance as DBRelationInstance
from ontology.objects import get_object, get_all_objects
from ontology.relations import get_relation, get_all_relations

logger = logging.getLogger(__name__)


class ObjectInstance(BaseModel):
    instance_id: str  # e.g. "BUD-2024-001"
    type_id: str  # e.g. "obj_budget_item"
    attributes: Dict[str, Any]
    status: str = "active"
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    tenant_id: Optional[str] = None


class RelationInstance(BaseModel):
    instance_id: str
    type_id: str  # e.g. "rel_mount"
    source_instance_id: str
    target_instance_id: str
    attributes: Dict[str, Any] = {}
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)


class CardinalityViolationError(Exception):
    """Raised when a relation creation violates cardinality constraints."""
    pass


class OntologyInstanceManager:
    def __init__(self, db: Optional[AsyncSession] = None) -> None:
        self._object_instances: Dict[str, ObjectInstance] = {}
        self._relation_instances: Dict[str, RelationInstance] = {}
        self._db = db

    def set_db(self, db: AsyncSession):
        self._db = db

    # ── DB ↔ Model Helpers ──────────────────────────────────────────

    def _db_to_model(self, row) -> ObjectInstance:
        return ObjectInstance(
            instance_id=row.instance_id,
            type_id=row.type_id,
            attributes=row.attributes or {},
            status=row.status,
            created_at=row.created_at,
            updated_at=row.updated_at,
            tenant_id=row.tenant_id,
        )

    def _db_rel_to_model(self, row) -> RelationInstance:
        return RelationInstance(
            instance_id=row.instance_id,
            type_id=row.type_id,
            source_instance_id=row.source_instance_id,
            target_instance_id=row.target_instance_id,
            attributes=row.attributes or {},
            valid_from=row.valid_from,
            valid_to=row.valid_to,
            created_at=row.created_at,
        )

    # ── Object Instance Operations ──────────────────────────────────

    async def create_object_instance(
        self,
        type_id: str,
        instance_id: str,
        attributes: Dict[str, Any],
        status: str = "active",
        tenant_id: Optional[str] = None,
    ) -> ObjectInstance:
        if get_object(type_id) is None:
            raise ValueError(f"Object type '{type_id}' does not exist in ontology")

        if instance_id in self._object_instances:
            raise ValueError(f"Object instance '{instance_id}' already exists")

        now = datetime.now()
        instance = ObjectInstance(
            instance_id=instance_id,
            type_id=type_id,
            attributes=attributes,
            status=status,
            created_at=now,
            updated_at=now,
            tenant_id=tenant_id,
        )
        self._object_instances[instance_id] = instance
        if self._db:
            db_obj = DBObjectInstance(
                instance_id=instance_id,
                type_id=type_id,
                attributes=attributes,
                status=status or "active",
                tenant_id=tenant_id,
            )
            self._db.add(db_obj)
            await self._db.flush()
        await self._safe_project_object(instance)
        return instance

    async def get_object_instance(self, instance_id: str) -> Optional[ObjectInstance]:
        if instance_id in self._object_instances:
            return self._object_instances[instance_id]
        if self._db:
            row = await self._db.get(DBObjectInstance, instance_id)
            if row:
                inst = self._db_to_model(row)
                self._object_instances[instance_id] = inst  # cache
                return inst
        return None

    async def update_object_instance(
        self,
        instance_id: str,
        attributes: Optional[Dict[str, Any]] = None,
        status: Optional[str] = None,
    ) -> Optional[ObjectInstance]:
        inst = await self.get_object_instance(instance_id)
        if inst is None:
            return None

        if attributes:
            inst.attributes.update(attributes)
        if status:
            inst.status = status
        inst.updated_at = datetime.now()
        self._object_instances[instance_id] = inst
        if self._db:
            row = await self._db.get(DBObjectInstance, instance_id)
            if row:
                if attributes:
                    row.attributes = inst.attributes
                if status:
                    row.status = status
                row.updated_at = inst.updated_at
                await self._db.flush()
        await self._safe_project_object(inst)
        return inst

    async def delete_object_instance(self, instance_id: str) -> ObjectInstance:
        if instance_id not in self._object_instances:
            raise ValueError(f"Object instance '{instance_id}' not found")

        inst = self._object_instances[instance_id]
        del self._object_instances[instance_id]

        # Remove all relation instances referencing this object
        rel_ids_to_remove = [
            rel_id
            for rel_id, rel in self._relation_instances.items()
            if rel.source_instance_id == instance_id or rel.target_instance_id == instance_id
        ]
        for rel_id in rel_ids_to_remove:
            del self._relation_instances[rel_id]
            await self._safe_tombstone_relation(rel_id)

        if self._db:
            await self._db.execute(sql_delete(DBObjectInstance).where(DBObjectInstance.instance_id == instance_id))
            await self._db.flush()

        await self._safe_tombstone_object(instance_id)
        return inst

    async def query_objects(
        self,
        type_id: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[ObjectInstance]:
        results = []
        if self._db and type_id is not None:
            stmt = select(DBObjectInstance).where(DBObjectInstance.type_id == type_id)
            rows = (await self._db.execute(stmt)).scalars().all()
            for row in rows:
                inst = self._db_to_model(row)
                if filters:
                    match = all(inst.attributes.get(k) == v for k, v in filters.items())
                    if not match:
                        continue
                results.append(inst)
                self._object_instances[inst.instance_id] = inst  # cache
        else:
            results = list(self._object_instances.values())
            if type_id is not None:
                results = [inst for inst in results if inst.type_id == type_id]
            if filters:
                for key, value in filters.items():
                    results = [
                        inst for inst in results if inst.attributes.get(key) == value
                    ]
        return results

    # ── Relation Instance Operations ────────────────────────────────

    async def create_relation_instance(
        self,
        type_id: str,
        source_id: str,
        target_id: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> RelationInstance:
        # Validate type_id exists
        rel_def = get_relation(type_id)
        if rel_def is None:
            raise ValueError(f"Relation type '{type_id}' does not exist in ontology")

        # Validate source and target instances exist (check memory then DB)
        if source_id not in self._object_instances:
            if self._db:
                row = await self._db.get(DBObjectInstance, source_id)
                if row:
                    self._object_instances[source_id] = self._db_to_model(row)
                else:
                    raise ValueError(f"Source instance '{source_id}' not found")
            else:
                raise ValueError(f"Source instance '{source_id}' not found")
        if target_id not in self._object_instances:
            if self._db:
                row = await self._db.get(DBObjectInstance, target_id)
                if row:
                    self._object_instances[target_id] = self._db_to_model(row)
                else:
                    raise ValueError(f"Target instance '{target_id}' not found")
            else:
                raise ValueError(f"Target instance '{target_id}' not found")

        # Check cardinality constraints
        self._check_cardinality(type_id, source_id, target_id)

        instance_id = str(uuid4())
        instance = RelationInstance(
            instance_id=instance_id,
            type_id=type_id,
            source_instance_id=source_id,
            target_instance_id=target_id,
            attributes=attributes or {},
        )
        self._relation_instances[instance_id] = instance
        if self._db:
            db_rel = DBRelationInstance(
                instance_id=instance_id,
                type_id=type_id,
                source_instance_id=source_id,
                target_instance_id=target_id,
                attributes=attributes or {},
            )
            self._db.add(db_rel)
            await self._db.flush()
        await self._safe_project_relation(instance)
        return instance

    async def get_relation_instance(self, instance_id: str) -> Optional[RelationInstance]:
        if instance_id in self._relation_instances:
            return self._relation_instances[instance_id]
        if self._db:
            row = await self._db.get(DBRelationInstance, instance_id)
            if row:
                inst = self._db_rel_to_model(row)
                self._relation_instances[instance_id] = inst  # cache
                return inst
        return None

    async def delete_relation_instance(self, instance_id: str) -> RelationInstance:
        if instance_id not in self._relation_instances:
            raise ValueError(f"Relation instance '{instance_id}' not found")
        inst = self._relation_instances[instance_id]
        del self._relation_instances[instance_id]
        if self._db:
            await self._db.execute(sql_delete(DBRelationInstance).where(DBRelationInstance.instance_id == instance_id))
            await self._db.flush()
        await self._safe_tombstone_relation(instance_id)
        return inst

    async def get_relations_for_object(
        self,
        instance_id: str,
        direction: str = "both",
    ) -> List[RelationInstance]:
        results: List[RelationInstance] = []

        if self._db:
            if direction in ("source", "both"):
                stmt = select(DBRelationInstance).where(DBRelationInstance.source_instance_id == instance_id)
                rows = (await self._db.execute(stmt)).scalars().all()
                for row in rows:
                    inst = self._db_rel_to_model(row)
                    results.append(inst)
                    self._relation_instances[inst.instance_id] = inst  # cache
            if direction in ("target", "both"):
                stmt = select(DBRelationInstance).where(DBRelationInstance.target_instance_id == instance_id)
                rows = (await self._db.execute(stmt)).scalars().all()
                for row in rows:
                    inst = self._db_rel_to_model(row)
                    results.append(inst)
                    self._relation_instances[inst.instance_id] = inst  # cache
        else:
            for rel in self._relation_instances.values():
                if direction in ("source", "both") and rel.source_instance_id == instance_id:
                    results.append(rel)
                elif direction in ("target", "both") and rel.target_instance_id == instance_id:
                    results.append(rel)

        return results

    # ── Cardinality Enforcement ─────────────────────────────────────

    def _check_cardinality(
        self,
        type_id: str,
        source_id: str,
        target_id: str,
    ) -> None:
        rel_def = get_relation(type_id)
        if rel_def is None:
            return

        cardinality = rel_def.cardinality

        if cardinality == "1:1":
            # Source can have at most 1 relation of this type
            source_count = self.count_relations(type_id, source_id, role="source")
            if source_count >= 1:
                raise CardinalityViolationError(
                    f"Cardinality violation (1:1): source instance '{source_id}' "
                    f"already has a relation of type '{type_id}'"
                )
            # Target can have at most 1 relation of this type
            target_count = self.count_relations(type_id, target_id, role="target")
            if target_count >= 1:
                raise CardinalityViolationError(
                    f"Cardinality violation (1:1): target instance '{target_id}' "
                    f"already has a relation of type '{type_id}'"
                )

        elif cardinality == "N:1":
            # Each source has at most 1 relation of this type
            source_count = self.count_relations(type_id, source_id, role="source")
            if source_count >= 1:
                raise CardinalityViolationError(
                    f"Cardinality violation (N:1): source instance '{source_id}' "
                    f"already has a relation of type '{type_id}'"
                )

        elif cardinality == "1:N":
            # Each target has at most 1 relation of this type
            target_count = self.count_relations(type_id, target_id, role="target")
            if target_count >= 1:
                raise CardinalityViolationError(
                    f"Cardinality violation (1:N): target instance '{target_id}' "
                    f"already has a relation of type '{type_id}'"
                )

        # "N:N" — no restrictions

    def count_relations(
        self,
        type_id: str,
        instance_id: str,
        role: str = "source",
    ) -> int:
        count = 0
        for rel in self._relation_instances.values():
            if rel.type_id != type_id:
                continue
            if role == "source" and rel.source_instance_id == instance_id:
                count += 1
            elif role == "target" and rel.target_instance_id == instance_id:
                count += 1
        # Note: DB count not merged here for performance; cardinality checks
        # should be done within the same session where data is fresh.
        return count

    # ── DB Cache Loading ────────────────────────────────────────────

    async def load_from_db(self, session=None):
        """从数据库加载所有实例到内存缓存"""
        db = session or self._db
        if not db:
            return
        rows = (await db.execute(select(DBObjectInstance))).scalars().all()
        for row in rows:
            self._object_instances[row.instance_id] = self._db_to_model(row)
        rel_rows = (await db.execute(select(DBRelationInstance))).scalars().all()
        for row in rel_rows:
            self._relation_instances[row.instance_id] = self._db_rel_to_model(row)
        logger.info(f"从DB加载: {len(self._object_instances)}对象实例, {len(self._relation_instances)}关系实例")

    async def _safe_project_object(self, inst: ObjectInstance) -> None:
        try:
            from ontology.graph_projection import project_object

            await project_object(inst)
        except Exception as exc:
            logger.warning(f"Graph project object {inst.instance_id} failed: {exc}")

    async def _safe_project_relation(self, rel: RelationInstance) -> None:
        try:
            from ontology.graph_projection import project_relation

            await project_relation(rel)
        except Exception as exc:
            logger.warning(f"Graph project relation {rel.instance_id} failed: {exc}")

    async def _safe_tombstone_object(self, instance_id: str) -> None:
        try:
            from ontology.graph_projection import tombstone_object

            await tombstone_object(instance_id)
        except Exception as exc:
            logger.warning(f"Graph tombstone object {instance_id} failed: {exc}")

    async def _safe_tombstone_relation(self, instance_id: str) -> None:
        try:
            from ontology.graph_projection import tombstone_relation

            await tombstone_relation(instance_id)
        except Exception as exc:
            logger.warning(f"Graph tombstone relation {instance_id} failed: {exc}")


# ── Module-level singleton ──────────────────────────────────────────

_instance_manager: Optional[OntologyInstanceManager] = None


def get_instance_manager() -> OntologyInstanceManager:
    global _instance_manager
    if _instance_manager is None:
        _instance_manager = OntologyInstanceManager()
    return _instance_manager
