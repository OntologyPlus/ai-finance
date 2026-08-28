from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field


class AIPermissionLevel(str, Enum):
    L1_READONLY = "L1-只读"
    L2_SUGGEST = "L2-建议"
    L3_LOW_RISK_EXECUTE = "L3-低风险执行"
    L4_HIGH_RISK_EXECUTE = "L4-高风险执行"


class ObjectType(str, Enum):
    BUDGET_ITEM = "BudgetItem"
    EXPENSE_REPORT = "ExpenseReport"
    ALERT_RECORD = "AlertRecord"
    STRATEGIC_INITIATIVE = "StrategicInitiative"
    MANAGEMENT_REPORT = "ManagementReport"


class ABACOperator(str, Enum):
    GT = ">"          # greater than
    GTE = ">="        # greater than or equal
    LT = "<"          # less than
    LTE = "<="        # less than or equal
    EQ = "=="         # equal
    NEQ = "!="        # not equal
    IN = "in"         # value in list
    NOT_IN = "not_in" # value not in list
    BETWEEN = "between"  # value between [min, max]
    CONTAINS = "contains"  # string contains


class RoleType(str, Enum):
    COMMITTEE = "管委会"
    BUDGET_DEPT = "财经中心预算管理部"
    CENTER_BP = "中心财经BP"
    OPS_DEPT = "运营中心经营管理部"
    HR_CENTER = "人力中心"
    CENTER_GM = "中心总经理"
    DEPT_HEAD = "部门负责人"
    EMPLOYEE = "员工"


_OBJECT_FIELD_VISIBILITY: Dict[str, Dict[str, Set[str]]] = {
    ObjectType.BUDGET_ITEM: {
        RoleType.COMMITTEE: {
            "budget_id", "budget_name", "budget_category", "l1_code", "l2_code", "l3_code",
            "quadrant", "strategy_initiative_id", "annual_amount", "granted_amount",
            "frozen_amount", "used_amount", "available_amount", "grant_percentage",
            "status", "center_id", "department_id", "project_id",
            "strategic_intent_l1", "strategic_intent_l2", "product_line", "region",
        },
        RoleType.BUDGET_DEPT: {
            "budget_id", "budget_name", "budget_category", "l1_code", "l2_code", "l3_code",
            "quadrant", "strategy_initiative_id", "annual_amount", "granted_amount",
            "frozen_amount", "used_amount", "available_amount", "grant_percentage",
            "status", "center_id", "department_id", "project_id",
            "strategic_intent_l1", "strategic_intent_l2", "product_line", "region",
        },
        RoleType.CENTER_BP: {
            "budget_id", "budget_name", "budget_category", "l1_code", "l2_code", "l3_code",
            "quadrant", "strategy_initiative_id", "annual_amount", "granted_amount",
            "frozen_amount", "used_amount", "available_amount", "grant_percentage",
            "status", "center_id", "department_id", "project_id",
            "strategic_intent_l1", "strategic_intent_l2", "product_line", "region",
        },
        RoleType.CENTER_GM: {
            "budget_id", "budget_name", "budget_category", "l1_code", "l2_code", "l3_code",
            "quadrant", "annual_amount", "granted_amount", "used_amount",
            "available_amount", "status", "center_id", "department_id",
            "strategic_intent_l1", "product_line", "region",
        },
        RoleType.DEPT_HEAD: {
            "budget_id", "budget_name", "budget_category", "l1_code",
            "annual_amount", "used_amount", "available_amount", "status",
            "strategic_intent_l1", "product_line",
        },
        RoleType.EMPLOYEE: {
            "budget_id", "budget_name", "budget_category", "l1_code",
            "available_amount", "status",
        },
    },
    ObjectType.EXPENSE_REPORT: {
        RoleType.COMMITTEE: {
            "expense_id", "applicant_id", "budget_id", "l1_code", "l2_code", "l3_code",
            "amount", "description", "control_tag", "status", "center_id",
            "department_id", "legal_entity_id",
        },
        RoleType.BUDGET_DEPT: {
            "expense_id", "applicant_id", "budget_id", "l1_code", "l2_code", "l3_code",
            "amount", "description", "control_tag", "status", "center_id",
            "department_id", "legal_entity_id",
        },
        RoleType.CENTER_BP: {
            "expense_id", "applicant_id", "budget_id", "l1_code", "l2_code", "l3_code",
            "amount", "description", "control_tag", "status", "center_id",
            "department_id", "legal_entity_id",
        },
        RoleType.CENTER_GM: {
            "expense_id", "applicant_id", "budget_id", "l1_code",
            "amount", "status", "center_id", "department_id",
        },
        RoleType.DEPT_HEAD: {
            "expense_id", "applicant_id", "budget_id", "l1_code",
            "amount", "status", "department_id",
        },
        RoleType.EMPLOYEE: {
            "expense_id", "budget_id", "amount", "status",
        },
    },
    ObjectType.ALERT_RECORD: {
        RoleType.COMMITTEE: {
            "alert_id", "alert_level", "alert_type", "alert_status", "l1_code",
            "budget_id", "trigger_value", "threshold_value", "deviation_rate",
            "responsible_person", "response_deadline", "response_hours",
            "notification_targets",
        },
        RoleType.BUDGET_DEPT: {
            "alert_id", "alert_level", "alert_type", "alert_status", "l1_code",
            "budget_id", "trigger_value", "threshold_value", "deviation_rate",
            "responsible_person", "response_deadline", "response_hours",
            "notification_targets",
        },
        RoleType.CENTER_BP: {
            "alert_id", "alert_level", "alert_type", "alert_status", "l1_code",
            "budget_id", "trigger_value", "threshold_value", "deviation_rate",
            "responsible_person", "response_deadline",
        },
        RoleType.CENTER_GM: {
            "alert_id", "alert_level", "alert_type", "alert_status", "l1_code",
            "budget_id", "trigger_value", "deviation_rate",
        },
        RoleType.DEPT_HEAD: {
            "alert_id", "alert_level", "alert_type", "alert_status", "l1_code",
            "deviation_rate",
        },
        RoleType.EMPLOYEE: set(),
    },
}

_OBAC_SCOPE: Dict[str, Dict[str, str]] = {
    RoleType.COMMITTEE: {"scope": "all", "description": "管委会可见全部数据"},
    RoleType.BUDGET_DEPT: {"scope": "all", "description": "财经中心预算管理部可见全部数据"},
    RoleType.CENTER_BP: {"scope": "center", "description": "中心财经BP可见本中心数据"},
    RoleType.CENTER_GM: {"scope": "center", "description": "中心总经理可见本中心数据"},
    RoleType.DEPT_HEAD: {"scope": "department", "description": "部门负责人可见本部门数据"},
    RoleType.OPS_DEPT: {"scope": "all", "description": "运营中心经营管理部可见全部数据(经营分析需要)"},
    RoleType.HR_CENTER: {"scope": "l1_b6", "description": "人力中心可见B6人力成本相关数据"},
    RoleType.EMPLOYEE: {"scope": "own", "description": "员工仅可见本人相关数据"},
}

_ABAC_RULES: List[Dict[str, Any]] = [
    {
        "rule_id": "ABAC-001",
        "name": "大额支出CFO审批",
        "condition": {"field": "amount", "operator": ">", "value": 500000},
        "action": "require_approval",
        "approver_role": RoleType.BUDGET_DEPT,
        "description": "金额超过50万需财经中心预算管理部审批",
    },
    {
        "rule_id": "ABAC-002",
        "name": "超期费用不可报销",
        "condition": {"field": "days_since_expense", "operator": ">", "value": 90},
        "action": "block",
        "description": "费用发生后超过90天不可报销",
    },
    {
        "rule_id": "ABAC-003",
        "name": "预警超时自动升级",
        "condition": {"field": "hours_since_alert", "operator": ">", "value": "response_hours"},
        "action": "auto_escalate",
        "description": "预警超过响应时限自动升级",
    },
    {
        "rule_id": "ABAC-004",
        "name": "跨中心数据不可见",
        "condition": {"field": "center_id", "operator": "!=", "value": "user_center_id"},
        "action": "hide",
        "applies_to": [RoleType.CENTER_BP, RoleType.CENTER_GM, RoleType.DEPT_HEAD],
        "description": "非本中心数据对中心级角色不可见",
    },
]

_AI_PERMISSION_MATRIX: Dict[str, Dict[str, AIPermissionLevel]] = {
    "budget_planning": {
        RoleType.COMMITTEE: AIPermissionLevel.L4_HIGH_RISK_EXECUTE,
        RoleType.BUDGET_DEPT: AIPermissionLevel.L3_LOW_RISK_EXECUTE,
        RoleType.CENTER_BP: AIPermissionLevel.L2_SUGGEST,
        RoleType.CENTER_GM: AIPermissionLevel.L2_SUGGEST,
        RoleType.DEPT_HEAD: AIPermissionLevel.L1_READONLY,
        RoleType.EMPLOYEE: AIPermissionLevel.L1_READONLY,
    },
    "expense_reimbursement": {
        RoleType.COMMITTEE: AIPermissionLevel.L3_LOW_RISK_EXECUTE,
        RoleType.BUDGET_DEPT: AIPermissionLevel.L3_LOW_RISK_EXECUTE,
        RoleType.CENTER_BP: AIPermissionLevel.L3_LOW_RISK_EXECUTE,
        RoleType.CENTER_GM: AIPermissionLevel.L2_SUGGEST,
        RoleType.DEPT_HEAD: AIPermissionLevel.L2_SUGGEST,
        RoleType.EMPLOYEE: AIPermissionLevel.L2_SUGGEST,
    },
    "alert_monitoring": {
        RoleType.COMMITTEE: AIPermissionLevel.L3_LOW_RISK_EXECUTE,
        RoleType.BUDGET_DEPT: AIPermissionLevel.L4_HIGH_RISK_EXECUTE,
        RoleType.CENTER_BP: AIPermissionLevel.L3_LOW_RISK_EXECUTE,
        RoleType.CENTER_GM: AIPermissionLevel.L2_SUGGEST,
        RoleType.DEPT_HEAD: AIPermissionLevel.L1_READONLY,
        RoleType.EMPLOYEE: AIPermissionLevel.L1_READONLY,
    },
    "budget_adjustment": {
        RoleType.COMMITTEE: AIPermissionLevel.L4_HIGH_RISK_EXECUTE,
        RoleType.BUDGET_DEPT: AIPermissionLevel.L3_LOW_RISK_EXECUTE,
        RoleType.CENTER_BP: AIPermissionLevel.L2_SUGGEST,
        RoleType.CENTER_GM: AIPermissionLevel.L2_SUGGEST,
        RoleType.DEPT_HEAD: AIPermissionLevel.L1_READONLY,
        RoleType.EMPLOYEE: AIPermissionLevel.L1_READONLY,
    },
    "b2a_conversion": {
        RoleType.COMMITTEE: AIPermissionLevel.L4_HIGH_RISK_EXECUTE,
        RoleType.BUDGET_DEPT: AIPermissionLevel.L3_LOW_RISK_EXECUTE,
        RoleType.CENTER_BP: AIPermissionLevel.L2_SUGGEST,
        RoleType.CENTER_GM: AIPermissionLevel.L1_READONLY,
        RoleType.DEPT_HEAD: AIPermissionLevel.L1_READONLY,
        RoleType.EMPLOYEE: AIPermissionLevel.L1_READONLY,
    },
    "report_generation": {
        RoleType.COMMITTEE: AIPermissionLevel.L3_LOW_RISK_EXECUTE,
        RoleType.BUDGET_DEPT: AIPermissionLevel.L3_LOW_RISK_EXECUTE,
        RoleType.CENTER_BP: AIPermissionLevel.L3_LOW_RISK_EXECUTE,
        RoleType.CENTER_GM: AIPermissionLevel.L2_SUGGEST,
        RoleType.DEPT_HEAD: AIPermissionLevel.L1_READONLY,
        RoleType.EMPLOYEE: AIPermissionLevel.L1_READONLY,
    },
}


class ABACRuleStructured(BaseModel):
    rule_id: str
    name: str
    field: str           # the field to check
    operator: ABACOperator
    value: Any           # the value to compare against (single value, list for IN, tuple for BETWEEN)
    action: str          # "block", "require_approval", "auto_escalate", "hide"
    description: str = ""


class PermissionCheckResult(BaseModel):
    allowed: bool
    reason: str
    ai_level: Optional[AIPermissionLevel] = None
    requires_human_confirm: bool = False


class OntologyPermissionEngine:
    _ORG_HIERARCHY = {
        # center -> departments mapping for hierarchical derivation
        "研发中心": ["研发一部", "研发二部", "研发三部"],
        "营销中心": ["市场部", "销售部", "渠道部"],
        "运营中心": ["运营管理部", "客户服务部"],
    }

    def __init__(self):
        self.field_visibility = _OBJECT_FIELD_VISIBILITY
        self.obac_scope = _OBAC_SCOPE
        self.abac_rules = _ABAC_RULES
        self.ai_permissions = _AI_PERMISSION_MATRIX

    def get_visible_fields(
        self, role_type: str, object_type: str
    ) -> Set[str]:
        obj_map = self.field_visibility.get(object_type, {})
        return obj_map.get(role_type, set())

    def filter_object_fields(
        self, role_type: str, object_type: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        visible = self.get_visible_fields(role_type, object_type)
        if not visible:
            return {}
        return {k: v for k, v in data.items() if k in visible}

    def get_data_scope(self, role_type: str) -> Dict[str, str]:
        return self.obac_scope.get(role_type, {"scope": "own", "description": "默认仅可见本人数据"})

    def is_data_in_scope(
        self, role_type: str, user_center_id: Optional[str],
        user_department_id: Optional[str], user_employee_id: Optional[str],
        data_center_id: Optional[str], data_department_id: Optional[str],
        data_employee_id: Optional[str], data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        scope_info = self.get_data_scope(role_type)
        scope = scope_info["scope"]

        if scope == "all":
            return True
        if scope == "center":
            if user_center_id is not None and user_center_id == data_center_id:
                return True
            # Hierarchical OBAC: center role can also see data from departments under that center
            if user_center_id is not None and user_center_id in self._ORG_HIERARCHY:
                child_depts = self._ORG_HIERARCHY[user_center_id]
                if data_department_id in child_depts:
                    return True
            return False
        if scope == "department":
            return user_department_id is not None and user_department_id == data_department_id
        if scope == "own":
            return user_employee_id is not None and user_employee_id == data_employee_id
        if scope == "l1_b6":
            # Filter by checking if the data has a field "l1_code" == "B6"
            if data is not None and data.get("l1_code") == "B6":
                return True
            # Fallback to original behavior if no data dict provided
            return data_center_id is not None and user_center_id == data_center_id
        return False

    def check_abac_rules(
        self, context: Dict[str, Any], role_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        triggered = []
        for rule in self.abac_rules:
            if "applies_to" in rule and role_type and role_type not in rule["applies_to"]:
                continue

            field = rule["condition"]["field"]
            operator = rule["condition"]["operator"]
            value = rule["condition"]["value"]
            actual = context.get(field)

            if actual is None:
                continue

            if operator == ">" and isinstance(value, (int, float)):
                if actual > value:
                    triggered.append(rule)
            elif operator == "!=" and isinstance(value, str) and value.startswith("user_"):
                user_value = context.get(value)
                if actual != user_value:
                    triggered.append(rule)
            elif operator == ">" and value == "response_hours":
                threshold = context.get("response_hours", 72)
                if actual > threshold:
                    triggered.append(rule)

        return triggered

    def evaluate_abac_structured(self, context: Dict[str, Any], rules: Optional[List[ABACRuleStructured]] = None) -> List[ABACRuleStructured]:
        """评估结构化ABAC规则，返回被触发的规则列表"""
        if rules is None:
            rules = self._get_default_structured_rules()

        triggered = []
        for rule in rules:
            field_value = context.get(rule.field)
            if field_value is None:
                continue

            triggered_flag = False
            if rule.operator == ABACOperator.GT:
                triggered_flag = float(field_value) > float(rule.value)
            elif rule.operator == ABACOperator.GTE:
                triggered_flag = float(field_value) >= float(rule.value)
            elif rule.operator == ABACOperator.LT:
                triggered_flag = float(field_value) < float(rule.value)
            elif rule.operator == ABACOperator.LTE:
                triggered_flag = float(field_value) <= float(rule.value)
            elif rule.operator == ABACOperator.EQ:
                triggered_flag = field_value == rule.value
            elif rule.operator == ABACOperator.NEQ:
                triggered_flag = field_value != rule.value
            elif rule.operator == ABACOperator.IN:
                triggered_flag = field_value in rule.value
            elif rule.operator == ABACOperator.NOT_IN:
                triggered_flag = field_value not in rule.value
            elif rule.operator == ABACOperator.BETWEEN:
                triggered_flag = rule.value[0] <= float(field_value) <= rule.value[1]
            elif rule.operator == ABACOperator.CONTAINS:
                triggered_flag = str(rule.value) in str(field_value)

            if triggered_flag:
                triggered.append(rule)

        return triggered

    def _get_default_structured_rules(self) -> List[ABACRuleStructured]:
        return [
            ABACRuleStructured(rule_id="ABAC-S001", name="大额支出CFO审批", field="amount", operator=ABACOperator.GT, value=500000, action="require_approval", description="金额超50万需财经中心预算管理部审批"),
            ABACRuleStructured(rule_id="ABAC-S002", name="超期费用不可报销", field="days_since_expense", operator=ABACOperator.GT, value=90, action="block", description="费用发生后超过90天不可报销"),
            ABACRuleStructured(rule_id="ABAC-S003", name="预警超时自动升级", field="hours_since_alert", operator=ABACOperator.GT, value=48, action="auto_escalate", description="预警超过响应时限自动升级"),
            ABACRuleStructured(rule_id="ABAC-S004", name="跨中心数据不可见", field="center_id", operator=ABACOperator.NEQ, value="", action="hide", description="非本中心数据对中心级角色不可见"),
            ABACRuleStructured(rule_id="ABAC-S005", name="预算执行率超限", field="execution_rate", operator=ABACOperator.GTE, value=1.1, action="require_approval", description="执行率超110%需额外审批"),
            ABACRuleStructured(rule_id="ABAC-S006", name="B类膨胀超限", field="b_class_inflation_rate", operator=ABACOperator.GTE, value=0.3, action="require_approval", description="B类膨胀率超30%需审批"),
        ]

    def get_ai_permission(
        self, scene: str, role_type: str
    ) -> AIPermissionLevel:
        scene_perms = self.ai_permissions.get(scene, {})
        return scene_perms.get(role_type, AIPermissionLevel.L1_READONLY)

    def check_ai_action(
        self, scene: str, role_type: str, action_type: str
    ) -> PermissionCheckResult:
        level = self.get_ai_permission(scene, role_type)

        if action_type == "read":
            return PermissionCheckResult(
                allowed=True,
                reason=f"AI权限等级{level.value}，允许读取",
                ai_level=level,
            )
        elif action_type == "suggest":
            if level in (AIPermissionLevel.L2_SUGGEST, AIPermissionLevel.L3_LOW_RISK_EXECUTE, AIPermissionLevel.L4_HIGH_RISK_EXECUTE):
                return PermissionCheckResult(
                    allowed=True,
                    reason=f"AI权限等级{level.value}，允许提供建议",
                    ai_level=level,
                )
            return PermissionCheckResult(
                allowed=False,
                reason=f"AI权限等级{level.value}，不允许提供建议",
                ai_level=level,
            )
        elif action_type == "execute_low_risk":
            if level in (AIPermissionLevel.L3_LOW_RISK_EXECUTE, AIPermissionLevel.L4_HIGH_RISK_EXECUTE):
                return PermissionCheckResult(
                    allowed=True,
                    reason=f"AI权限等级{level.value}，允许执行低风险操作",
                    ai_level=level,
                )
            return PermissionCheckResult(
                allowed=False,
                reason=f"AI权限等级{level.value}，不允许执行低风险操作",
                ai_level=level,
            )
        elif action_type == "execute_high_risk":
            if level == AIPermissionLevel.L4_HIGH_RISK_EXECUTE:
                return PermissionCheckResult(
                    allowed=True,
                    reason=f"AI权限等级{level.value}，允许执行高风险操作，但需人类确认",
                    ai_level=level,
                    requires_human_confirm=True,
                )
            return PermissionCheckResult(
                allowed=False,
                reason=f"AI权限等级{level.value}，不允许执行高风险操作",
                ai_level=level,
            )

        return PermissionCheckResult(
            allowed=False,
            reason=f"未知操作类型{action_type}",
            ai_level=level,
        )
