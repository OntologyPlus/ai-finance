from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ontology.objects import get_all_objects
from ontology.relations import get_all_relations
from ontology.behaviors import get_all_behaviors


class HealthDimension(BaseModel):
    dimension_id: str
    name: str
    weight: float
    score: float = Field(default=0.0, ge=0.0, le=100.0)
    threshold: float
    is_healthy: bool = False
    detail: str = ""


class HealthScoreCard(BaseModel):
    calculated_at: datetime = Field(default_factory=datetime.now)
    total_score: float = Field(default=0.0, ge=0.0, le=100.0)
    dimensions: List[HealthDimension] = Field(default_factory=list)
    maturity_level: str = ""
    maturity_score: int = 0


_HEALTH_DIMENSIONS: List[Dict[str, Any]] = [
    {
        "dimension_id": "HD-001",
        "name": "战略落地",
        "weight": 0.15,
        "threshold": 95.0,
        "description": "战略意图维度覆盖率",
    },
    {
        "dimension_id": "HD-002",
        "name": "预算管控",
        "weight": 0.15,
        "threshold": 98.0,
        "description": "A/B类分类准确率",
    },
    {
        "dimension_id": "HD-003",
        "name": "执行闭环",
        "weight": 0.15,
        "threshold": 98.0,
        "description": "报销与预算绑定率",
    },
    {
        "dimension_id": "HD-004",
        "name": "预警闭环率",
        "weight": 0.15,
        "threshold": 90.0,
        "description": "预警闭环率",
    },
    {
        "dimension_id": "HD-005",
        "name": "预警响应时效",
        "weight": 0.10,
        "threshold": 95.0,
        "description": "预警响应时效达标率",
    },
    {
        "dimension_id": "HD-006",
        "name": "数据质量",
        "weight": 0.10,
        "threshold": 100.0,
        "description": "经营分析报告准时率",
    },
    {
        "dimension_id": "HD-007",
        "name": "流程效率",
        "weight": 0.05,
        "threshold": 93.0,
        "description": "报销审批周期(≤7天=100分)",
    },
    {
        "dimension_id": "HD-008",
        "name": "关系健康",
        "weight": 0.05,
        "threshold": 95.0,
        "description": "孤儿对象率(≤5%=100分)",
    },
    {
        "dimension_id": "HD-009",
        "name": "动作健康",
        "weight": 0.05,
        "threshold": 80.0,
        "description": "僵尸动作率(≤20%=100分)",
    },
    {
        "dimension_id": "HD-010",
        "name": "AI效能",
        "weight": 0.05,
        "threshold": 60.0,
        "description": "AI建议采纳率",
    },
]


class OntologyHealthScorer:
    def __init__(self):
        self.dimensions = _HEALTH_DIMENSIONS

    def _calc_strategic_coverage(self) -> float:
        all_objects = get_all_objects()
        budget_items = [o for o in all_objects.values() if o.object_id == "obj_budget_item"]
        if not budget_items:
            return 0.0

        key_attrs = budget_items[0].key_attributes
        has_strategic_l1 = "战略意图L1" in key_attrs
        has_strategic_l2 = "战略意图L2" in key_attrs

        if has_strategic_l1 and has_strategic_l2:
            return 100.0
        elif has_strategic_l1:
            return 60.0
        return 0.0

    def _calc_relation_health(self) -> float:
        all_objects = get_all_objects()
        all_relations = get_all_relations()

        if not all_objects:
            return 0.0

        objects_with_relations = set()
        for rel in all_relations.values():
            objects_with_relations.add(rel.source_object)
            objects_with_relations.add(rel.target_object)

        total_objects = len(all_objects)
        orphan_count = total_objects - len(objects_with_relations & set(all_objects.keys()))
        orphan_rate = (orphan_count / total_objects * 100) if total_objects > 0 else 100

        if orphan_rate <= 5:
            return 100.0
        elif orphan_rate <= 10:
            return 80.0
        elif orphan_rate <= 20:
            return 60.0
        return 40.0

    def _calc_action_health(self) -> float:
        all_behaviors = get_all_behaviors()
        if not all_behaviors:
            return 0.0

        active_count = sum(1 for b in all_behaviors.values() if b.parameters and len(b.parameters) > 0)
        total = len(all_behaviors)
        zombie_rate = ((total - active_count) / total * 100) if total > 0 else 100

        if zombie_rate <= 20:
            return 100.0
        elif zombie_rate <= 30:
            return 80.0
        elif zombie_rate <= 50:
            return 60.0
        return 40.0

    def calculate(
        self,
        alert_closure_rate: float = 0.0,
        alert_response_timeliness: float = 0.0,
        budget_binding_rate: float = 0.0,
        ab_classification_rate: float = 0.0,
        report_on_time_rate: float = 0.0,
        avg_approval_days: float = 14.0,
        ai_adoption_rate: float = 0.0,
    ) -> HealthScoreCard:
        dimensions = []

        strategic_score = self._calc_strategic_coverage()
        dimensions.append(HealthDimension(
            dimension_id="HD-001",
            name="战略落地",
            weight=0.15,
            score=strategic_score,
            threshold=95.0,
            is_healthy=strategic_score >= 95.0,
            detail=f"战略意图维度覆盖率: {strategic_score:.0f}%",
        ))

        ab_score = ab_classification_rate if ab_classification_rate > 0 else 85.0
        dimensions.append(HealthDimension(
            dimension_id="HD-002",
            name="预算管控",
            weight=0.15,
            score=ab_score,
            threshold=98.0,
            is_healthy=ab_score >= 98.0,
            detail=f"A/B类分类准确率: {ab_score:.0f}%",
        ))

        binding_score = budget_binding_rate if budget_binding_rate > 0 else 90.0
        dimensions.append(HealthDimension(
            dimension_id="HD-003",
            name="执行闭环",
            weight=0.15,
            score=binding_score,
            threshold=98.0,
            is_healthy=binding_score >= 98.0,
            detail=f"报销与预算绑定率: {binding_score:.0f}%",
        ))

        closure_score = alert_closure_rate if alert_closure_rate > 0 else 80.0
        dimensions.append(HealthDimension(
            dimension_id="HD-004",
            name="预警闭环率",
            weight=0.15,
            score=closure_score,
            threshold=90.0,
            is_healthy=closure_score >= 90.0,
            detail=f"预警闭环率: {closure_score:.0f}%",
        ))

        timeliness_score = alert_response_timeliness if alert_response_timeliness > 0 else 85.0
        dimensions.append(HealthDimension(
            dimension_id="HD-005",
            name="预警响应时效",
            weight=0.10,
            score=timeliness_score,
            threshold=95.0,
            is_healthy=timeliness_score >= 95.0,
            detail=f"预警响应时效达标率: {timeliness_score:.0f}%",
        ))

        report_score = report_on_time_rate if report_on_time_rate > 0 else 90.0
        dimensions.append(HealthDimension(
            dimension_id="HD-006",
            name="数据质量",
            weight=0.10,
            score=report_score,
            threshold=100.0,
            is_healthy=report_score >= 100.0,
            detail=f"经营分析报告准时率: {report_score:.0f}%",
        ))

        if avg_approval_days <= 7:
            efficiency_score = 100.0
        elif avg_approval_days <= 10:
            efficiency_score = 80.0
        elif avg_approval_days <= 14:
            efficiency_score = 60.0
        else:
            efficiency_score = 40.0
        dimensions.append(HealthDimension(
            dimension_id="HD-007",
            name="流程效率",
            weight=0.05,
            score=efficiency_score,
            threshold=93.0,
            is_healthy=efficiency_score >= 93.0,
            detail=f"平均审批周期: {avg_approval_days:.1f}天",
        ))

        relation_score = self._calc_relation_health()
        dimensions.append(HealthDimension(
            dimension_id="HD-008",
            name="关系健康",
            weight=0.05,
            score=relation_score,
            threshold=95.0,
            is_healthy=relation_score >= 95.0,
            detail=f"孤儿对象率评估: {relation_score:.0f}%",
        ))

        action_score = self._calc_action_health()
        dimensions.append(HealthDimension(
            dimension_id="HD-009",
            name="动作健康",
            weight=0.05,
            score=action_score,
            threshold=80.0,
            is_healthy=action_score >= 80.0,
            detail=f"僵尸动作率评估: {action_score:.0f}%",
        ))

        ai_score = ai_adoption_rate if ai_adoption_rate > 0 else 50.0
        dimensions.append(HealthDimension(
            dimension_id="HD-010",
            name="AI效能",
            weight=0.05,
            score=ai_score,
            threshold=60.0,
            is_healthy=ai_score >= 60.0,
            detail=f"AI建议采纳率: {ai_score:.0f}%",
        ))

        total_score = sum(d.score * d.weight for d in dimensions)

        if total_score >= 85:
            maturity_level = "L5-运营驱动"
            maturity_score = 6
        elif total_score >= 70:
            maturity_level = "L4-AI增强"
            maturity_score = 5
        elif total_score >= 55:
            maturity_level = "L3-动作赋能(高段)"
            maturity_score = 4
        elif total_score >= 40:
            maturity_level = "L3-动作赋能(低段)"
            maturity_score = 3
        elif total_score >= 20:
            maturity_level = "L2-关系映射"
            maturity_score = 2
        else:
            maturity_level = "L1-对象映射"
            maturity_score = 1

        return HealthScoreCard(
            calculated_at=datetime.now(),
            total_score=round(total_score, 2),
            dimensions=dimensions,
            maturity_level=maturity_level,
            maturity_score=maturity_score,
        )
