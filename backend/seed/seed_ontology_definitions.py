import json

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from ontology.objects import get_all_objects
from ontology.relations import get_all_relations
from ontology.behaviors import get_all_behaviors
from ontology.scenes import get_all_scenes
from models.ontology import OntologyObject, OntologyRelation, OntologyBehavior, OntologyScene


async def seed_ontology_definitions(db: AsyncSession) -> None:
    """从内存中的本体定义向数据库的本体定义表写入种子数据，使用 upsert 模式。"""

    # --- Seed ontology_object ---
    objects = get_all_objects()
    obj_count = 0
    for obj in objects.values():
        existing = await db.get(OntologyObject, obj.object_id)
        if existing:
            continue
        db.add(OntologyObject(
            object_id=obj.object_id,
            object_name=obj.name,
            object_type=obj.category,
            natural_language_def=obj.natural_language_definition,
            key_attributes=json.dumps(obj.key_attributes, ensure_ascii=False),
            participating_relations=json.dumps(obj.participating_relations, ensure_ascii=False),
            is_active=True,
        ))
        obj_count += 1
    logger.info(f"ontology_object: seeded {obj_count} new records (total definitions: {len(objects)})")

    # --- Seed ontology_relation ---
    relations = get_all_relations()
    rel_count = 0
    for rel in relations.values():
        existing = await db.get(OntologyRelation, rel.relation_id)
        if existing:
            continue
        db.add(OntologyRelation(
            relation_id=rel.relation_id,
            relation_name=rel.name,
            source_object_id=rel.source_object,
            target_object_id=rel.target_object,
            scene_condition=json.dumps(rel.scene_condition, ensure_ascii=False) if rel.scene_condition else None,
            semantic_description=rel.semantic_description,
            cardinality=rel.cardinality,
            confidence=float(rel.confidence),
            provenance=rel.provenance,
            is_bidirectional=rel.is_bidirectional,
            reverse_relation_id=rel.reverse_relation_id,
            is_active=True,
        ))
        rel_count += 1
    logger.info(f"ontology_relation: seeded {rel_count} new records (total definitions: {len(relations)})")

    # --- Seed ontology_behavior ---
    behaviors = get_all_behaviors()
    beh_count = 0
    for beh in behaviors.values():
        existing = await db.get(OntologyBehavior, beh.behavior_id)
        if existing:
            continue
        db.add(OntologyBehavior(
            behavior_id=beh.behavior_id,
            behavior_name=beh.name,
            preconditions=beh.preconditions,
            effects=beh.effects,
            parameters=json.dumps(beh.parameters, ensure_ascii=False),
            stage=beh.stage,
            is_active=True,
        ))
        beh_count += 1
    logger.info(f"ontology_behavior: seeded {beh_count} new records (total definitions: {len(behaviors)})")

    # --- Seed ontology_scene ---
    scenes = get_all_scenes()
    sc_count = 0
    for sc in scenes.values():
        existing = await db.get(OntologyScene, sc.scene_id)
        if existing:
            continue
        db.add(OntologyScene(
            scene_id=sc.scene_id,
            scene_name=sc.name,
            description=sc.description,
            activation_condition=json.dumps(sc.activation_condition, ensure_ascii=False) if sc.activation_condition else None,
            activated_objects=json.dumps(sc.activated_objects, ensure_ascii=False),
            activated_relations=json.dumps(sc.activated_relations, ensure_ascii=False),
            activated_rules=json.dumps(sc.activated_rules, ensure_ascii=False),
            activated_behaviors=json.dumps(sc.activated_behaviors, ensure_ascii=False),
            corresponding_stage=sc.stage,
            is_active=True,
        ))
        sc_count += 1
    logger.info(f"ontology_scene: seeded {sc_count} new records (total definitions: {len(scenes)})")
