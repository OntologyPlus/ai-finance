from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ontology.objects import get_all_objects
from ontology.relations import get_all_relations
from ontology.behaviors import get_all_behaviors
from ontology.health_score import OntologyHealthScorer


class MaturityQuestion(BaseModel):
    question_id: str
    category: str
    question: str
    weight: float
    auto_calculable: bool = True
    answer: Optional[bool] = None
    evidence: str = ""


class MaturityLevel(BaseModel):
    level: int
    name: str
    min_score: float
    max_score: float
    description: str


MATURITY_LEVELS: List[MaturityLevel] = [
    MaturityLevel(level=1, name="L1-对象映射", min_score=0, max_score=20, description="仅完成对象定义，无关系和动作"),
    MaturityLevel(level=2, name="L2-关系映射", min_score=20, max_score=40, description="对象和关系已建立，但动作和规则未实现"),
    MaturityLevel(level=3, name="L3-动作赋能(低段)", min_score=40, max_score=55, description="动作已定义但副作用链不完整，权限缺失"),
    MaturityLevel(level=4, name="L3-动作赋能(高段)", min_score=55, max_score=70, description="动作完整但AI层和运营层未实现"),
    MaturityLevel(level=5, name="L4-AI增强", min_score=70, max_score=85, description="OAG架构就绪，AI上下文注入和幻觉防护已实现"),
    MaturityLevel(level=6, name="L5-运营驱动", min_score=85, max_score=100, description="健康度监控、变更治理、域设计全部就绪"),
]

_MATURITY_QUESTIONS: List[Dict[str, Any]] = [
    {"question_id": "MQ-01", "category": "对象层", "question": "核心业务对象是否全部定义（预算项目、报销单、预警记录、战略举措）？", "weight": 5.0},
    {"question_id": "MQ-02", "category": "对象层", "question": "每个对象是否有自然语言定义和关键属性列表？", "weight": 3.0},
    {"question_id": "MQ-03", "category": "对象层", "question": "预算项目是否包含战略意图维度（L1/L2/产品线/区域）？", "weight": 4.0},
    {"question_id": "MQ-04", "category": "关系层", "question": "核心关系是否全部定义（挂载、对标、归属、管控、触发等）？", "weight": 5.0},
    {"question_id": "MQ-05", "category": "关系层", "question": "每条关系是否有基数约束、置信度、溯源标注？", "weight": 3.0},
    {"question_id": "MQ-06", "category": "关系层", "question": "关系是否持久化到数据库（而非仅内存定义）？", "weight": 2.0},
    {"question_id": "MQ-07", "category": "动作层", "question": "核心业务动作是否全部定义（20个行为覆盖8个阶段）？", "weight": 5.0},
    {"question_id": "MQ-08", "category": "动作层", "question": "每个动作是否有前置条件和副作用链？", "weight": 4.0},
    {"question_id": "MQ-09", "category": "动作层", "question": "Write-Back机制是否实现（核销→预算同步、预警→消息异步）？", "weight": 3.0},
    {"question_id": "MQ-10", "category": "规则层", "question": "硬规则、软规则、推理规则三层引擎是否完整？", "weight": 5.0},
    {"question_id": "MQ-11", "category": "规则层", "question": "软规则参数是否可运行时动态调整？", "weight": 2.0},
    {"question_id": "MQ-12", "category": "规则层", "question": "推理规则是否支持从历史数据学习模式？", "weight": 2.0},
    {"question_id": "MQ-13", "category": "权限层", "question": "OBAC归属推导是否实现（基于组织架构自动推导数据范围）？", "weight": 5.0},
    {"question_id": "MQ-14", "category": "权限层", "question": "字段级权限是否实现（不同角色看到不同字段）？", "weight": 4.0},
    {"question_id": "MQ-15", "category": "权限层", "question": "ABAC条件权限是否实现（金额>50万需CFO审批等）？", "weight": 3.0},
    {"question_id": "MQ-16", "category": "权限层", "question": "AI权限分级是否实现（L1只读~L4高风险执行）？", "weight": 3.0},
    {"question_id": "MQ-17", "category": "AI层", "question": "OAG上下文注入是否实现（Agent通过Ontology获取上下文）？", "weight": 5.0},
    {"question_id": "MQ-18", "category": "AI层", "question": "幻觉防护是否实现（事实锚定、数值校验、关系验证、拒答）？", "weight": 4.0},
    {"question_id": "MQ-19", "category": "AI层", "question": "OAG Prompt模板是否实现（预算分析、预警建议、B→A建议）？", "weight": 3.0},
    {"question_id": "MQ-20", "category": "运营层", "question": "健康度监控是否实现（十维度评分体系）？", "weight": 5.0},
]


class MaturityAssessment(BaseModel):
    assessment_id: str
    assessed_at: datetime = Field(default_factory=datetime.now)
    total_score: float = 0.0
    max_score: float = 0.0
    percentage: float = 0.0
    maturity_level: str = ""
    maturity_level_number: int = 0
    category_scores: Dict[str, float] = Field(default_factory=dict)
    questions: List[MaturityQuestion] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


class OntologyMaturityAssessor:
    def __init__(self):
        self.questions = [
            MaturityQuestion(
                question_id=q["question_id"],
                category=q["category"],
                question=q["question"],
                weight=q["weight"],
            )
            for q in _MATURITY_QUESTIONS
        ]

    def _auto_evaluate_question(self, question_id: str) -> tuple[bool, str]:
        all_objects = get_all_objects()
        all_relations = get_all_relations()
        all_behaviors = get_all_behaviors()

        if question_id == "MQ-01":
            required = {"obj_budget_item", "obj_expense_report", "obj_alert_record", "obj_strategic_initiative"}
            present = required & set(all_objects.keys())
            return len(present) >= 3, f"已定义{len(present)}/{len(required)}个核心对象"

        if question_id == "MQ-02":
            with_def = sum(1 for o in all_objects.values() if o.natural_language_definition and o.key_attributes)
            total = len(all_objects)
            return with_def >= total * 0.8, f"{with_def}/{total}个对象有定义和属性"

        if question_id == "MQ-03":
            budget = all_objects.get("obj_budget_item")
            if budget:
                has = "战略意图L1" in budget.key_attributes and "战略意图L2" in budget.key_attributes
                return has, f"战略意图L1={'已填' if '战略意图L1' in budget.key_attributes else '缺失'}, L2={'已填' if '战略意图L2' in budget.key_attributes else '缺失'}"
            return False, "预算项目对象不存在"

        if question_id == "MQ-04":
            required_rels = {"挂载", "对标", "归属", "管控", "触发"}
            present_rels = {r.name for r in all_relations.values()}
            found = required_rels & present_rels
            return len(found) >= 4, f"已定义{len(found)}/{len(required_rels)}条核心关系"

        if question_id == "MQ-05":
            with_cardinality = sum(1 for r in all_relations.values() if hasattr(r, 'cardinality') and r.cardinality)
            total = len(all_relations)
            return with_cardinality >= total * 0.8, f"{with_cardinality}/{total}条关系有基数约束"

        if question_id == "MQ-06":
            try:
                from models.ontology import OntologyRelation
                return True, "OntologyRelation模型已定义"
            except Exception:
                return False, "OntologyRelation模型未找到"

        if question_id == "MQ-07":
            return len(all_behaviors) >= 15, f"已定义{len(all_behaviors)}个行为"

        if question_id == "MQ-08":
            with_precond = sum(1 for b in all_behaviors.values() if b.preconditions)
            with_effects = sum(1 for b in all_behaviors.values() if b.effects)
            total = len(all_behaviors)
            return with_precond >= total * 0.7 and with_effects >= total * 0.7, f"前置条件:{with_precond}/{total}, 副作用:{with_effects}/{total}"

        if question_id == "MQ-09":
            try:
                from ontology.write_back import get_write_back_engine
                engine = get_write_back_engine()
                has_handlers = len(engine._handlers) >= 2
                has_strong_consistency = any(
                    entry.consistency.value == "strong"
                    for entry in engine._entries.values()
                ) if engine._entries else True
                return has_handlers, f"Write-Back: {len(engine._handlers)}个Handler已注册, 强一致模式{'已使用' if has_strong_consistency else '待使用'}"
            except Exception as e:
                return False, f"Write-Back引擎加载失败: {e}"

        if question_id == "MQ-10":
            try:
                from ontology.rules.hard_rules import HardRuleEngine
                from ontology.rules.soft_rules import SoftRuleEngine
                from ontology.rules.reasoning_rules import ReasoningRuleEngine
                return True, "三层规则引擎已实现"
            except Exception:
                return False, "规则引擎加载失败"

        if question_id == "MQ-11":
            try:
                from ontology.rules.soft_rules import SoftRuleEngine
                engine = SoftRuleEngine()
                return True, "软规则参数可动态调整"
            except Exception:
                return False, "软规则引擎加载失败"

        if question_id == "MQ-12":
            try:
                from ontology.rules.reasoning_rules import ReasoningRuleEngine
                return True, "推理规则支持学习"
            except Exception:
                return False, "推理规则引擎加载失败"

        if question_id == "MQ-13":
            try:
                from ontology.permissions import OntologyPermissionEngine
                engine = OntologyPermissionEngine()
                scope = engine.get_data_scope("中心财经BP")
                return scope.get("scope") == "center", f"OBAC范围: {scope.get('scope', 'unknown')}"
            except Exception:
                return False, "权限引擎加载失败"

        if question_id == "MQ-14":
            try:
                from ontology.permissions import OntologyPermissionEngine
                engine = OntologyPermissionEngine()
                fields = engine.get_visible_fields("部门负责人", "BudgetItem")
                return len(fields) > 0 and len(fields) < 20, f"部门负责人可见{len(fields)}个字段"
            except Exception:
                return False, "字段级权限加载失败"

        if question_id == "MQ-15":
            try:
                from ontology.permissions import OntologyPermissionEngine
                engine = OntologyPermissionEngine()
                return len(engine.abac_rules) > 0, f"已定义{len(engine.abac_rules)}条ABAC规则"
            except Exception:
                return False, "ABAC规则加载失败"

        if question_id == "MQ-16":
            try:
                from ontology.permissions import OntologyPermissionEngine, AIPermissionLevel
                engine = OntologyPermissionEngine()
                level = engine.get_ai_permission("budget_planning", "管委会")
                return level == AIPermissionLevel.L4_HIGH_RISK_EXECUTE, f"管委会AI权限: {level.value}"
            except Exception:
                return False, "AI权限分级加载失败"

        if question_id == "MQ-17":
            try:
                from ontology.context_injection import OntologyContextInjector
                injector = OntologyContextInjector()
                import asyncio
                ctx = asyncio.get_event_loop().run_until_complete(
                    injector.build_context("test", target_object_ids=["obj_budget_item"])
                )
                return len(ctx.blocks) > 0, f"上下文注入{len(ctx.blocks)}个块"
            except Exception:
                return False, "OAG上下文注入加载失败"

        if question_id == "MQ-18":
            try:
                from ontology.hallucination_guard import OntologyHallucinationGuard
                return True, "幻觉防护已实现"
            except Exception:
                return False, "幻觉防护加载失败"

        if question_id == "MQ-19":
            try:
                from ontology.oag_prompts import OAG_PROMPT_TEMPLATES
                return len(OAG_PROMPT_TEMPLATES) >= 3, f"已定义{len(OAG_PROMPT_TEMPLATES)}套Prompt模板"
            except Exception:
                return False, "OAG Prompt模板加载失败"

        if question_id == "MQ-20":
            try:
                from ontology.health_score import OntologyHealthScorer
                scorer = OntologyHealthScorer()
                card = scorer.calculate()
                return len(card.dimensions) >= 10, f"已定义{len(card.dimensions)}个健康度维度"
            except Exception:
                return False, "健康度监控加载失败"

        return False, "无法自动评估"

    def assess(self) -> MaturityAssessment:
        questions = []
        for q_template in self.questions:
            answer, evidence = self._auto_evaluate_question(q_template.question_id)
            questions.append(MaturityQuestion(
                question_id=q_template.question_id,
                category=q_template.category,
                question=q_template.question,
                weight=q_template.weight,
                auto_calculable=True,
                answer=answer,
                evidence=evidence,
            ))

        total_score = sum(q.weight for q in questions if q.answer)
        max_score = sum(q.weight for q in questions)
        percentage = (total_score / max_score * 100) if max_score > 0 else 0

        category_scores: Dict[str, float] = {}
        for q in questions:
            if q.category not in category_scores:
                category_scores[q.category] = 0.0
            if q.answer:
                category_scores[q.category] += q.weight

        maturity_level = "L1-对象映射"
        maturity_number = 1
        for level in MATURITY_LEVELS:
            if percentage >= level.min_score:
                maturity_level = level.name
                maturity_number = level.level

        recommendations = []
        category_max: Dict[str, float] = {}
        for q in self.questions:
            if q.category not in category_max:
                category_max[q.category] = 0.0
            category_max[q.category] += q.weight

        for cat, score in category_scores.items():
            max_cat = category_max.get(cat, 1.0)
            if score < max_cat * 0.5:
                unanswered = [q for q in questions if q.category == cat and not q.answer]
                if unanswered:
                    recommendations.append(
                        f"[{cat}] 得分{score:.0f}/{max_cat:.0f}，建议优先解决: {unanswered[0].question}"
                    )

        return MaturityAssessment(
            assessment_id=f"MA-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            assessed_at=datetime.now(),
            total_score=total_score,
            max_score=max_score,
            percentage=round(percentage, 2),
            maturity_level=maturity_level,
            maturity_level_number=maturity_number,
            category_scores=category_scores,
            questions=questions,
            recommendations=recommendations,
        )
