from typing import List

from pydantic import BaseModel

from ontology.objects import get_all_objects
from ontology.relations import get_all_relations
from ontology.behaviors import get_all_behaviors
from ontology.scenes import get_all_scenes
from ontology.domains import OntologyDomainManager, DomainId


class ConsistencyIssue(BaseModel):
    severity: str  # "CRITICAL" / "HIGH" / "MEDIUM" / "LOW"
    category: str  # e.g. "object_relation_ref", "scene_activation", "domain_cohesion"
    message: str
    target_id: str
    suggestion: str = ""


class OntologyConsistencyChecker:
    """启动时本体一致性检查器，验证对象、关系、场景、域之间的引用完整性。"""

    def check_all(self) -> List[ConsistencyIssue]:
        issues: List[ConsistencyIssue] = []
        issues.extend(self._check_object_relation_refs())
        issues.extend(self._check_relation_source_target())
        issues.extend(self._check_reverse_relations())
        issues.extend(self._check_scene_activations())
        issues.extend(self._check_domain_cohesion())
        issues.extend(self._check_bidirectional_consistency())
        return issues

    # ------------------------------------------------------------------
    # a) Object-Relation Reference Check
    # ------------------------------------------------------------------
    def _check_object_relation_refs(self) -> List[ConsistencyIssue]:
        """验证每个对象的 participating_relations 中的关系名称在 get_all_relations() 中存在。"""
        issues: List[ConsistencyIssue] = []
        all_objects = get_all_objects()
        all_relations = get_all_relations()
        relation_names = {rel.name for rel in all_relations.values()}

        for obj_id, obj_def in all_objects.items():
            for rel_name in obj_def.participating_relations:
                if rel_name not in relation_names:
                    issues.append(ConsistencyIssue(
                        severity="CRITICAL",
                        category="object_relation_ref",
                        message=f"对象 {obj_id} 的参与关系 '{rel_name}' 在关系注册表中不存在",
                        target_id=obj_id,
                        suggestion=f"请在 relations 中添加名称为 '{rel_name}' 的关系，或从对象 {obj_id} 的 participating_relations 中移除该引用",
                    ))
        return issues

    # ------------------------------------------------------------------
    # b) Relation Source/Target Check
    # ------------------------------------------------------------------
    def _check_relation_source_target(self) -> List[ConsistencyIssue]:
        """验证每个关系的 source_object 和 target_object 在 get_all_objects() 中存在。"""
        issues: List[ConsistencyIssue] = []
        all_objects = get_all_objects()
        all_relations = get_all_relations()
        object_ids = set(all_objects.keys())

        for rel_id, rel_def in all_relations.items():
            if rel_def.source_object not in object_ids:
                issues.append(ConsistencyIssue(
                    severity="CRITICAL",
                    category="relation_source_target",
                    message=f"关系 {rel_id} 的 source_object '{rel_def.source_object}' 在对象注册表中不存在",
                    target_id=rel_id,
                    suggestion=f"请在 objects 中添加 '{rel_def.source_object}'，或修正关系 {rel_id} 的 source_object",
                ))
            if rel_def.target_object not in object_ids:
                issues.append(ConsistencyIssue(
                    severity="CRITICAL",
                    category="relation_source_target",
                    message=f"关系 {rel_id} 的 target_object '{rel_def.target_object}' 在对象注册表中不存在",
                    target_id=rel_id,
                    suggestion=f"请在 objects 中添加 '{rel_def.target_object}'，或修正关系 {rel_id} 的 target_object",
                ))
        return issues

    # ------------------------------------------------------------------
    # c) Reverse Relation Check
    # ------------------------------------------------------------------
    def _check_reverse_relations(self) -> List[ConsistencyIssue]:
        """验证有 reverse_relation_id 的关系，其反向关系存在且反向指向回来。"""
        issues: List[ConsistencyIssue] = []
        all_relations = get_all_relations()

        for rel_id, rel_def in all_relations.items():
            if rel_def.reverse_relation_id is None:
                continue
            reverse_id = rel_def.reverse_relation_id
            reverse_rel = all_relations.get(reverse_id)
            if reverse_rel is None:
                issues.append(ConsistencyIssue(
                    severity="HIGH",
                    category="reverse_relation",
                    message=f"关系 {rel_id} 的反向关系 '{reverse_id}' 不存在",
                    target_id=rel_id,
                    suggestion=f"请添加关系 '{reverse_id}' 或清除 {rel_id} 的 reverse_relation_id",
                ))
                continue
            if reverse_rel.reverse_relation_id != rel_id:
                issues.append(ConsistencyIssue(
                    severity="HIGH",
                    category="reverse_relation",
                    message=f"关系 {rel_id} 指向反向关系 {reverse_id}，但 {reverse_id} 的 reverse_relation_id 为 '{reverse_rel.reverse_relation_id}'，未指向回 {rel_id}",
                    target_id=rel_id,
                    suggestion=f"请将关系 {reverse_id} 的 reverse_relation_id 修正为 '{rel_id}'",
                ))
        return issues

    # ------------------------------------------------------------------
    # d) Scene Activation Check
    # ------------------------------------------------------------------
    def _check_scene_activations(self) -> List[ConsistencyIssue]:
        """验证场景的 activated_objects/activated_rules/activated_behaviors 在各自注册表中存在。"""
        issues: List[ConsistencyIssue] = []
        all_objects = get_all_objects()
        all_relations = get_all_relations()
        all_behaviors = get_all_behaviors()
        all_scenes = get_all_scenes()

        object_ids = set(all_objects.keys())
        relation_names = {rel.name for rel in all_relations.values()}
        behavior_ids = set(all_behaviors.keys())
        rule_ids = self._get_all_rule_ids()

        for scene_id, scene_def in all_scenes.items():
            for obj_id in scene_def.activated_objects:
                if obj_id not in object_ids:
                    issues.append(ConsistencyIssue(
                        severity="HIGH",
                        category="scene_activation",
                        message=f"场景 {scene_id} 的 activated_objects 中 '{obj_id}' 在对象注册表中不存在",
                        target_id=scene_id,
                        suggestion=f"请添加对象 '{obj_id}' 或从场景 {scene_id} 的 activated_objects 中移除",
                    ))

            for rel_name in scene_def.activated_relations:
                if rel_name not in relation_names:
                    issues.append(ConsistencyIssue(
                        severity="HIGH",
                        category="scene_activation",
                        message=f"场景 {scene_id} 的 activated_relations 中 '{rel_name}' 在关系注册表中不存在",
                        target_id=scene_id,
                        suggestion=f"请添加名称为 '{rel_name}' 的关系或从场景 {scene_id} 的 activated_relations 中移除",
                    ))

            for rule_id in scene_def.activated_rules:
                if rule_id not in rule_ids:
                    issues.append(ConsistencyIssue(
                        severity="HIGH",
                        category="scene_activation",
                        message=f"场景 {scene_id} 的 activated_rules 中 '{rule_id}' 在规则注册表中不存在",
                        target_id=scene_id,
                        suggestion=f"请添加规则 '{rule_id}' 或从场景 {scene_id} 的 activated_rules 中移除",
                    ))

            for beh_id in scene_def.activated_behaviors:
                if beh_id not in behavior_ids:
                    issues.append(ConsistencyIssue(
                        severity="HIGH",
                        category="scene_activation",
                        message=f"场景 {scene_id} 的 activated_behaviors 中 '{beh_id}' 在行为注册表中不存在",
                        target_id=scene_id,
                        suggestion=f"请添加行为 '{beh_id}' 或从场景 {scene_id} 的 activated_behaviors 中移除",
                    ))

        return issues

    # ------------------------------------------------------------------
    # e) Domain Cohesion Check
    # ------------------------------------------------------------------
    def _check_domain_cohesion(self) -> List[ConsistencyIssue]:
        """验证每个域的 core_objects/core_relations/core_behaviors 在各自注册表中存在。"""
        issues: List[ConsistencyIssue] = []
        all_objects = get_all_objects()
        all_relations = get_all_relations()
        all_behaviors = get_all_behaviors()

        object_ids = set(all_objects.keys())
        relation_ids = set(all_relations.keys())
        behavior_ids = set(all_behaviors.keys())

        manager = OntologyDomainManager()
        for domain_id, domain_def in manager.get_all_domains().items():
            for obj_id in domain_def.core_objects:
                if obj_id not in object_ids:
                    issues.append(ConsistencyIssue(
                        severity="HIGH",
                        category="domain_cohesion",
                        message=f"域 {domain_id.value} 的 core_objects 中 '{obj_id}' 在对象注册表中不存在",
                        target_id=domain_id.value,
                        suggestion=f"请添加对象 '{obj_id}' 或从域 {domain_id.value} 的 core_objects 中移除",
                    ))

            for rel_id in domain_def.core_relations:
                if rel_id not in relation_ids:
                    issues.append(ConsistencyIssue(
                        severity="HIGH",
                        category="domain_cohesion",
                        message=f"域 {domain_id.value} 的 core_relations 中 '{rel_id}' 在关系注册表中不存在",
                        target_id=domain_id.value,
                        suggestion=f"请添加关系 '{rel_id}' 或从域 {domain_id.value} 的 core_relations 中移除",
                    ))

            for beh_id in domain_def.core_behaviors:
                if beh_id not in behavior_ids:
                    issues.append(ConsistencyIssue(
                        severity="HIGH",
                        category="domain_cohesion",
                        message=f"域 {domain_id.value} 的 core_behaviors 中 '{beh_id}' 在行为注册表中不存在",
                        target_id=domain_id.value,
                        suggestion=f"请添加行为 '{beh_id}' 或从域 {domain_id.value} 的 core_behaviors 中移除",
                    ))

        return issues

    # ------------------------------------------------------------------
    # f) Bidirectional Consistency Check
    # ------------------------------------------------------------------
    def _check_bidirectional_consistency(self) -> List[ConsistencyIssue]:
        """验证双向关系对(如 freeze/release, benchmark/drive)的双向引用一致性。"""
        issues: List[ConsistencyIssue] = []
        all_relations = get_all_relations()

        bidirectional_pairs = [
            ("rel_freeze", "rel_release"),
            ("rel_benchmark", "rel_drive"),
        ]

        for rel_a_id, rel_b_id in bidirectional_pairs:
            rel_a = all_relations.get(rel_a_id)
            rel_b = all_relations.get(rel_b_id)

            if rel_a is None and rel_b is None:
                continue

            if rel_a is not None and rel_b is not None:
                # 双方都存在，检查互相引用
                if rel_a.reverse_relation_id != rel_b_id:
                    issues.append(ConsistencyIssue(
                        severity="MEDIUM",
                        category="bidirectional_consistency",
                        message=f"双向关系对 {rel_a_id}/{rel_b_id} 不一致：{rel_a_id}.reverse_relation_id='{rel_a.reverse_relation_id}'，期望 '{rel_b_id}'",
                        target_id=rel_a_id,
                        suggestion=f"请将 {rel_a_id} 的 reverse_relation_id 设置为 '{rel_b_id}'",
                    ))
                if rel_b.reverse_relation_id != rel_a_id:
                    issues.append(ConsistencyIssue(
                        severity="MEDIUM",
                        category="bidirectional_consistency",
                        message=f"双向关系对 {rel_a_id}/{rel_b_id} 不一致：{rel_b_id}.reverse_relation_id='{rel_b.reverse_relation_id}'，期望 '{rel_a_id}'",
                        target_id=rel_b_id,
                        suggestion=f"请将 {rel_b_id} 的 reverse_relation_id 设置为 '{rel_a_id}'",
                    ))
            elif rel_a is not None:
                # rel_a 存在但 rel_b 不存在
                if rel_a.reverse_relation_id == rel_b_id:
                    issues.append(ConsistencyIssue(
                        severity="MEDIUM",
                        category="bidirectional_consistency",
                        message=f"双向关系对 {rel_a_id}/{rel_b_id} 不一致：{rel_a_id} 引用了 {rel_b_id}，但 {rel_b_id} 不存在",
                        target_id=rel_a_id,
                        suggestion=f"请添加关系 '{rel_b_id}' 或清除 {rel_a_id} 的 reverse_relation_id",
                    ))
            else:
                # rel_b 存在但 rel_a 不存在
                if rel_b.reverse_relation_id == rel_a_id:
                    issues.append(ConsistencyIssue(
                        severity="MEDIUM",
                        category="bidirectional_consistency",
                        message=f"双向关系对 {rel_a_id}/{rel_b_id} 不一致：{rel_b_id} 引用了 {rel_a_id}，但 {rel_a_id} 不存在",
                        target_id=rel_b_id,
                        suggestion=f"请添加关系 '{rel_a_id}' 或清除 {rel_b_id} 的 reverse_relation_id",
                    ))

        return issues

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _get_all_rule_ids() -> set[str]:
        """从硬规则、软规则、推理规则中收集所有规则ID。"""
        rule_ids: set[str] = set()

        from ontology.rules.hard_rules import HardRuleEngine
        hard_engine = HardRuleEngine()
        rule_ids.update(hard_engine.get_all_rules().keys())

        from ontology.rules.soft_rules import SoftRuleEngine
        soft_engine = SoftRuleEngine()
        rule_ids.update(soft_engine.get_all_rules().keys())

        from ontology.rules.reasoning_rules import ReasoningRuleEngine
        reasoning_engine = ReasoningRuleEngine()
        rule_ids.update(reasoning_engine.get_all_rules().keys())

        return rule_ids
