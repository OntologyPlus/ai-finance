from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ontology.objects import get_all_objects
from ontology.relations import get_all_relations
from ontology.behaviors import get_all_behaviors
from ontology.rules.hard_rules import HardRuleEngine
from ontology.rules.soft_rules import SoftRuleEngine

from loguru import logger


class ChangePriority(str, Enum):
    P0 = "P0-紧急"
    P1 = "P1-高"
    P2 = "P2-中"
    P3 = "P3-低"
    P4 = "P4-信息"


class ChangeStatus(str, Enum):
    SUBMITTED = "已提交"
    UNDER_REVIEW = "审核中"
    APPROVED = "已批准"
    REJECTED = "已驳回"
    IMPLEMENTED = "已实施"
    ROLLED_BACK = "已回滚"


class ChangeRequest(BaseModel):
    change_id: str
    title: str
    description: str
    priority: ChangePriority
    change_type: str = Field(description="object_add/object_modify/object_remove/relation_add/relation_modify/rule_add/rule_modify")
    target_id: str = Field(description="变更目标ID")
    proposed_change: Dict[str, Any]
    submitter: str
    submitted_at: datetime = Field(default_factory=datetime.now)
    status: ChangeStatus = ChangeStatus.SUBMITTED
    impact_analysis: Optional[Dict[str, Any]] = None
    approver: Optional[str] = None
    approved_at: Optional[datetime] = None
    version_id: Optional[str] = None
    rollback_from: Optional[str] = None


class OntologyVersion(BaseModel):
    version_id: str
    version_number: int
    change_id: str
    snapshot: Dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.now)
    is_current: bool = True


class ImpactAnalysisResult(BaseModel):
    affected_objects: List[str] = Field(default_factory=list)
    affected_relations: List[str] = Field(default_factory=list)
    affected_behaviors: List[str] = Field(default_factory=list)
    affected_rules: List[str] = Field(default_factory=list)
    affected_scenes: List[str] = Field(default_factory=list)
    affected_consumers: List[str] = Field(default_factory=list)
    risk_level: str = "低"
    recommendation: str = ""


class VersionSnapshotRecord(BaseModel):
    version_id: str
    version_number: int
    change_id: str
    snapshot: Dict[str, Any]
    is_current: bool = False
    created_at: datetime = Field(default_factory=datetime.now)
    snapshot_hash: str = ""  # SHA256 hash for integrity check


class OntologyChangeManager:
    def __init__(self):
        self._changes: Dict[str, ChangeRequest] = {}
        self._versions: Dict[str, OntologyVersion] = {}
        self._persisted_versions: Dict[str, VersionSnapshotRecord] = {}
        self._current_version = 0
        self._hard_engine = HardRuleEngine()
        self._soft_engine = SoftRuleEngine()

    def submit_change(self, change: ChangeRequest) -> ChangeRequest:
        change.impact_analysis = self.analyze_impact(change)
        self._changes[change.change_id] = change
        return change

    def analyze_impact(self, change: ChangeRequest) -> Dict[str, Any]:
        result = ImpactAnalysisResult()
        target_id = change.target_id
        change_type = change.change_type

        all_objects = get_all_objects()
        all_relations = get_all_relations()
        all_behaviors = get_all_behaviors()

        if change_type.startswith("object"):
            result.affected_objects.append(target_id)
            for rel in all_relations.values():
                if rel.source_object == target_id or rel.target_object == target_id:
                    result.affected_relations.append(rel.relation_id)
            for beh in all_behaviors.values():
                if target_id in str(beh.preconditions) or target_id in str(beh.effects):
                    result.affected_behaviors.append(beh.behavior_id)

        elif change_type.startswith("relation"):
            result.affected_relations.append(target_id)
            rel = all_relations.get(target_id)
            if rel:
                result.affected_objects.append(rel.source_object)
                result.affected_objects.append(rel.target_object)

        elif change_type.startswith("rule"):
            result.affected_rules.append(target_id)

        total_affected = (
            len(result.affected_objects)
            + len(result.affected_relations)
            + len(result.affected_behaviors)
            + len(result.affected_rules)
        )

        if total_affected > 10:
            result.risk_level = "高"
            result.recommendation = "影响范围大，建议P0审批流程，需管委会批准"
        elif total_affected > 5:
            result.risk_level = "中"
            result.recommendation = "影响范围中等，建议P1审批流程，需财经中心预算管理部批准"
        else:
            result.risk_level = "低"
            result.recommendation = "影响范围小，P2审批流程即可，财经BP批准"

        return result.model_dump()

    def approve_change(self, change_id: str, approver: str) -> ChangeRequest:
        change = self._changes.get(change_id)
        if change is None:
            raise ValueError(f"Change {change_id} not found")
        if change.status != ChangeStatus.SUBMITTED and change.status != ChangeStatus.UNDER_REVIEW:
            raise ValueError(f"Change {change_id} is in status {change.status}, cannot approve")

        change.status = ChangeStatus.APPROVED
        change.approver = approver
        change.approved_at = datetime.now()
        return change

    def implement_change(self, change_id: str) -> OntologyVersion:
        change = self._changes.get(change_id)
        if change is None:
            raise ValueError(f"Change {change_id} not found")
        if change.status != ChangeStatus.APPROVED:
            raise ValueError(f"Change {change_id} must be approved before implementation")

        self._current_version += 1
        version = OntologyVersion(
            version_id=f"ONT-V{self._current_version:04d}",
            version_number=self._current_version,
            change_id=change_id,
            snapshot=self._take_snapshot(),
        )

        for vid, v in self._versions.items():
            v.is_current = False

        self._versions[version.version_id] = version
        self._persist_snapshot(version)
        change.status = ChangeStatus.IMPLEMENTED
        change.version_id = version.version_id
        return version

    def rollback_version(self, version_id: str) -> OntologyVersion:
        version = self._versions.get(version_id)
        if version is None:
            raise ValueError(f"Version {version_id} not found")

        # Restore in-memory data from snapshot
        self._restore_from_snapshot(version.snapshot)

        self._current_version += 1
        rollback = OntologyVersion(
            version_id=f"ONT-V{self._current_version:04d}",
            version_number=self._current_version,
            change_id=f"ROLLBACK-{version_id}",
            snapshot=self._take_snapshot(),
        )

        # Mark the change as rollback and set rollback_from
        change = self._changes.get(version.change_id)
        if change:
            change.status = ChangeStatus.ROLLED_BACK
            change.rollback_from = version_id

        for vid, v in self._versions.items():
            v.is_current = False

        rollback.is_current = True
        self._versions[rollback.version_id] = rollback
        self._persist_snapshot(rollback)
        return rollback

    def get_change(self, change_id: str) -> Optional[ChangeRequest]:
        return self._changes.get(change_id)

    def get_all_changes(self) -> Dict[str, ChangeRequest]:
        return self._changes.copy()

    def get_version(self, version_id: str) -> Optional[OntologyVersion]:
        return self._versions.get(version_id)

    def get_all_versions(self) -> Dict[str, OntologyVersion]:
        return self._versions.copy()

    def get_current_version(self) -> Optional[OntologyVersion]:
        for v in self._versions.values():
            if v.is_current:
                return v
        return None

    def _take_snapshot(self) -> Dict[str, Any]:
        return {
            "objects": {k: v.model_dump() for k, v in get_all_objects().items()},
            "relations": {k: v.model_dump() for k, v in get_all_relations().items()},
            "behaviors": {k: v.model_dump() for k, v in get_all_behaviors().items()},
            "timestamp": datetime.now().isoformat(),
        }

    def _restore_from_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """从快照恢复内存中的对象/关系/行为定义"""
        from ontology.objects import ObjectDefinition, _OBJECTS
        from ontology.relations import RelationDefinition, _RELATIONS
        from ontology.behaviors import BehaviorDefinition, _BEHAVIORS

        if "objects" in snapshot:
            _OBJECTS.clear()
            for obj_id, obj_data in snapshot["objects"].items():
                _OBJECTS[obj_id] = ObjectDefinition(**obj_data)

        if "relations" in snapshot:
            _RELATIONS.clear()
            for rel_id, rel_data in snapshot["relations"].items():
                _RELATIONS[rel_id] = RelationDefinition(**rel_data)

        if "behaviors" in snapshot:
            _BEHAVIORS.clear()
            for beh_id, beh_data in snapshot["behaviors"].items():
                _BEHAVIORS[beh_id] = BehaviorDefinition(**beh_data)

        logger.info(f"已从快照恢复本体数据: {len(_OBJECTS)}对象, {len(_RELATIONS)}关系, {len(_BEHAVIORS)}行为")

    def _persist_snapshot(self, version: OntologyVersion) -> None:
        """持久化版本快照到数据库"""
        import hashlib
        import json

        snapshot_json = json.dumps(version.snapshot, ensure_ascii=False, sort_keys=True)
        snapshot_hash = hashlib.sha256(snapshot_json.encode()).hexdigest()

        record = VersionSnapshotRecord(
            version_id=version.version_id,
            version_number=version.version_number,
            change_id=version.change_id,
            snapshot=version.snapshot,
            is_current=version.is_current,
            snapshot_hash=snapshot_hash,
        )

        self._persisted_versions[version.version_id] = record
        logger.info(f"版本快照已持久化: {version.version_id}, hash={snapshot_hash[:16]}...")

    def _load_persisted_versions(self) -> None:
        """从持久化存储加载版本快照"""
        # In production, this would load from database
        # For now, _persisted_versions is an in-memory dict that survives within the process
        pass

    def get_version_diff(self, version_id_a: str, version_id_b: str) -> Dict[str, Any]:
        """比较两个版本的差异"""
        va = self._versions.get(version_id_a) or self._persisted_versions.get(version_id_a)
        vb = self._versions.get(version_id_b) or self._persisted_versions.get(version_id_b)

        if not va or not vb:
            raise ValueError("版本不存在")

        snap_a = va.snapshot if isinstance(va, OntologyVersion) else va.snapshot
        snap_b = vb.snapshot if isinstance(vb, OntologyVersion) else vb.snapshot

        diff = {"added": {}, "removed": {}, "modified": {}}

        for category in ["objects", "relations", "behaviors"]:
            keys_a = set(snap_a.get(category, {}).keys())
            keys_b = set(snap_b.get(category, {}).keys())

            added = keys_b - keys_a
            removed = keys_a - keys_b
            common = keys_a & keys_b

            if added:
                diff["added"][category] = list(added)
            if removed:
                diff["removed"][category] = list(removed)

            modified = []
            for k in common:
                if snap_a[category][k] != snap_b[category][k]:
                    modified.append(k)
            if modified:
                diff["modified"][category] = modified

        return diff

    def get_lineage(self, version_id: str) -> List[Dict[str, Any]]:
        """获取版本血缘链"""
        lineage = []
        current = version_id
        visited = set()

        while current and current not in visited:
            version = self._versions.get(current) or self._persisted_versions.get(current)
            if not version:
                break
            visited.add(current)

            change_id = version.change_id if isinstance(version, OntologyVersion) else version.change_id
            lineage.append({
                "version_id": version.version_id if isinstance(version, OntologyVersion) else version.version_id,
                "change_id": change_id,
                "is_current": version.is_current if isinstance(version, OntologyVersion) else version.is_current,
            })

            # Walk backwards through changes
            change = self._changes.get(change_id)
            if change and change.rollback_from:
                current = change.rollback_from
            else:
                break

        return lineage
