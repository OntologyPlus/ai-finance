from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ontology.objects import get_all_objects
from ontology.relations import get_all_relations
from ontology.behaviors import get_all_behaviors


class DebtType(str, Enum):
    STRATEGIC_INTENT = "strategic_intent_debt"
    AB_CLASSIFICATION = "ab_classification_debt"
    DUAL_SIGN = "dual_sign_debt"
    RELATION_MISSING = "relation_missing_debt"
    ACTION_SIDE_EFFECT = "action_side_effect_debt"
    PERMISSION_OBAC = "permission_obac_debt"


class DebtSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DebtRecord(BaseModel):
    debt_id: str
    debt_type: DebtType
    severity: DebtSeverity
    title: str
    description: str
    affected_object_ids: List[str] = Field(default_factory=list)
    affected_relation_ids: List[str] = Field(default_factory=list)
    detected_at: datetime = Field(default_factory=datetime.now)
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    remediation: str = ""


class TechDebtReport(BaseModel):
    report_id: str
    generated_at: datetime = Field(default_factory=datetime.now)
    total_debts: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    debts: List[DebtRecord] = Field(default_factory=list)
    summary: str = ""


class OntologyTechDebtScanner:
    def __init__(self):
        self._debt_counter = 0

    def _next_debt_id(self) -> str:
        self._debt_counter += 1
        return f"DEBT-{self._debt_counter:04d}"

    def scan_strategic_intent_debt(self) -> List[DebtRecord]:
        debts = []
        all_objects = get_all_objects()

        budget_obj = all_objects.get("obj_budget_item")
        if budget_obj:
            has_l1 = "战略意图L1" in budget_obj.key_attributes
            has_l2 = "战略意图L2" in budget_obj.key_attributes
            if not has_l1 or not has_l2:
                debts.append(DebtRecord(
                    debt_id=self._next_debt_id(),
                    debt_type=DebtType.STRATEGIC_INTENT,
                    severity=DebtSeverity.CRITICAL,
                    title="预算项目缺少战略意图维度",
                    description=f"预算项目对象缺少战略意图属性(L1={'已填' if has_l1 else '缺失'}, L2={'已填' if has_l2 else '缺失'})，导致预算与战略脱钩",
                    affected_object_ids=["obj_budget_item"],
                    remediation="在BudgetItem模型和Ontology对象中补充strategic_intent_l1/l2/product_line/region属性",
                ))
        else:
            debts.append(DebtRecord(
                debt_id=self._next_debt_id(),
                debt_type=DebtType.STRATEGIC_INTENT,
                severity=DebtSeverity.CRITICAL,
                title="预算项目对象不存在",
                description="Ontology中缺少预算项目对象定义",
                affected_object_ids=[],
                remediation="创建obj_budget_item对象定义",
            ))

        return debts

    def scan_ab_classification_debt(self) -> List[DebtRecord]:
        debts = []
        all_objects = get_all_objects()

        budget_obj = all_objects.get("obj_budget_item")
        if budget_obj:
            has_category = "A/B类别" in budget_obj.key_attributes
            has_quadrant = any(
                "象限" in attr for attr in budget_obj.key_attributes
            )
            if not has_category:
                debts.append(DebtRecord(
                    debt_id=self._next_debt_id(),
                    debt_type=DebtType.AB_CLASSIFICATION,
                    severity=DebtSeverity.HIGH,
                    title="预算项目缺少A/B类别属性",
                    description="预算项目对象缺少A/B类别属性，无法区分确定性支出和弹性支出，管控力度无法差异化",
                    affected_object_ids=["obj_budget_item"],
                    remediation="在BudgetItem中确保budget_category字段正确设置",
                ))

        return debts

    def scan_dual_sign_debt(self) -> List[DebtRecord]:
        debts = []

        try:
            from ontology.rules.hard_rules import HardRuleEngine
            engine = HardRuleEngine()
            hr013 = engine.get_rule("HR-013")
            if hr013 is None:
                debts.append(DebtRecord(
                    debt_id=self._next_debt_id(),
                    debt_type=DebtType.DUAL_SIGN,
                    severity=DebtSeverity.CRITICAL,
                    title="缺少预警双签硬规则",
                    description="Ontology中缺少HR-013预警闭环必须双签硬规则，预警闭环可能流于形式",
                    affected_object_ids=["obj_alert_record"],
                    remediation="在hard_rules.py中新增HR-013硬规则",
                ))
        except Exception:
            debts.append(DebtRecord(
                debt_id=self._next_debt_id(),
                debt_type=DebtType.DUAL_SIGN,
                severity=DebtSeverity.HIGH,
                title="无法检查双签硬规则",
                description="硬规则引擎加载失败，无法确认双签规则是否存在",
                remediation="检查hard_rules.py是否正确加载",
            ))

        return debts

    def scan_relation_missing_debt(self) -> List[DebtRecord]:
        debts = []
        all_objects = get_all_objects()
        all_relations = get_all_relations()

        objects_with_relations = set()
        for rel in all_relations.values():
            objects_with_relations.add(rel.source_object)
            objects_with_relations.add(rel.target_object)

        for obj_id, obj in all_objects.items():
            if obj_id not in objects_with_relations and obj.participating_relations:
                debts.append(DebtRecord(
                    debt_id=self._next_debt_id(),
                    debt_type=DebtType.RELATION_MISSING,
                    severity=DebtSeverity.MEDIUM,
                    title=f"对象 {obj.name} 声明参与关系但未被任何关系引用",
                    description=f"对象 {obj_id}({obj.name}) 声明参与关系 {obj.participating_relations}，但在关系定义中未被引用为源或目标对象",
                    affected_object_ids=[obj_id],
                    remediation=f"检查对象 {obj.name} 的参与关系是否正确，或补充缺失的关系定义",
                ))

        expense_obj = all_objects.get("obj_expense_report")
        if expense_obj:
            has_mount = any(
                r.name == "挂载" for r in all_relations.values()
            )
            if not has_mount:
                debts.append(DebtRecord(
                    debt_id=self._next_debt_id(),
                    debt_type=DebtType.RELATION_MISSING,
                    severity=DebtSeverity.CRITICAL,
                    title="报销单与预算项目缺少挂载关系",
                    description="报销单与预算项目之间缺少显式挂载关系，支出无法追溯到预算来源",
                    affected_object_ids=["obj_expense_report", "obj_budget_item"],
                    remediation="在relations.py中新增报销单→预算项目的挂载关系",
                ))

        return debts

    def scan_action_side_effect_debt(self) -> List[DebtRecord]:
        debts = []
        all_behaviors = get_all_behaviors()

        for beh_id, beh in all_behaviors.items():
            effects = beh.effects if isinstance(beh.effects, list) else [beh.effects] if beh.effects else []
            has_write_back = any(
                "写回" in str(e) or "更新" in str(e) or "同步" in str(e) or "核销" in str(e)
                for e in effects
            )
            if not has_write_back and beh.parameters:
                debts.append(DebtRecord(
                    debt_id=self._next_debt_id(),
                    debt_type=DebtType.ACTION_SIDE_EFFECT,
                    severity=DebtSeverity.MEDIUM,
                    title=f"行为 {beh.name} 缺少Write-Back副作用",
                    description=f"行为 {beh_id}({beh.name}) 有参数定义但副作用链中缺少写回操作，执行后数据不会同步更新",
                    affected_object_ids=[],
                    remediation=f"在行为 {beh.name} 的effects中补充Write-Back副作用描述",
                ))

        return debts

    def scan_permission_obac_debt(self) -> List[DebtRecord]:
        debts = []

        try:
            from ontology.permissions import OntologyPermissionEngine
            engine = OntologyPermissionEngine()
            scope = engine.get_data_scope("中心财经BP")
            if scope.get("scope") != "center":
                debts.append(DebtRecord(
                    debt_id=self._next_debt_id(),
                    debt_type=DebtType.PERMISSION_OBAC,
                    severity=DebtSeverity.HIGH,
                    title="OBAC归属推导未正确配置",
                    description="中心财经BP的数据范围不是center级别，OBAC归属推导可能未生效",
                    remediation="检查permissions.py中的OBAC_SCOPE配置",
                ))
        except Exception:
            debts.append(DebtRecord(
                debt_id=self._next_debt_id(),
                debt_type=DebtType.PERMISSION_OBAC,
                severity=DebtSeverity.HIGH,
                title="权限引擎加载失败",
                description="无法加载OntologyPermissionEngine，OBAC可能未实现",
                remediation="检查permissions.py是否正确实现",
            ))

        return debts

    def scan_all(self) -> TechDebtReport:
        all_debts: List[DebtRecord] = []
        all_debts.extend(self.scan_strategic_intent_debt())
        all_debts.extend(self.scan_ab_classification_debt())
        all_debts.extend(self.scan_dual_sign_debt())
        all_debts.extend(self.scan_relation_missing_debt())
        all_debts.extend(self.scan_action_side_effect_debt())
        all_debts.extend(self.scan_permission_obac_debt())

        critical = sum(1 for d in all_debts if d.severity == DebtSeverity.CRITICAL)
        high = sum(1 for d in all_debts if d.severity == DebtSeverity.HIGH)
        medium = sum(1 for d in all_debts if d.severity == DebtSeverity.MEDIUM)
        low = sum(1 for d in all_debts if d.severity == DebtSeverity.LOW)

        summary_parts = []
        if critical > 0:
            summary_parts.append(f"{critical}个严重债务")
        if high > 0:
            summary_parts.append(f"{high}个高级债务")
        if medium > 0:
            summary_parts.append(f"{medium}个中级债务")
        if low > 0:
            summary_parts.append(f"{low}个低级债务")

        summary = f"共发现{len(all_debts)}项技术债务: {', '.join(summary_parts) if summary_parts else '无'}"

        return TechDebtReport(
            report_id=f"TDR-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            generated_at=datetime.now(),
            total_debts=len(all_debts),
            critical_count=critical,
            high_count=high,
            medium_count=medium,
            low_count=low,
            debts=all_debts,
            summary=summary,
        )
