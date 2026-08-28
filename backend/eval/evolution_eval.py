from typing import Any, Dict, List


class EvolutionEvalCases:
    @staticmethod
    def get_cases() -> List[Dict[str, Any]]:
        return [
            {
                "case_id": "EVO-001",
                "category": "rule_change_passthrough",
                "description": "软规则参数变更应传递到规则引擎",
                "rule_id": "SR-001",
                "context": {"execution_rate": 108},
                "expected": {"passed": False},
            },
            {
                "case_id": "EVO-002",
                "category": "rule_change_passthrough",
                "description": "推理规则学习后置信度应提升",
                "rule_id": "RR-001",
                "context": {"travel_expense": 100000, "project_count": 5, "avg_travel_per_project": 18000},
                "expected": {"passed": True},
            },
            {
                "case_id": "EVO-003",
                "category": "rule_change_passthrough",
                "description": "硬规则不可被软规则覆盖",
                "rule_id": "HR-001",
                "context": {"budget_id": None, "has_budget": False},
                "expected": {"passed": False, "output": "BLOCK"},
            },
            {
                "case_id": "EVO-004",
                "category": "rollback_mechanism",
                "description": "回滚后规则应恢复默认参数",
                "rule_id": "SR-001",
                "context": {"execution_rate": 106},
                "expected": {"passed": False},
            },
            {
                "case_id": "EVO-005",
                "category": "rollback_mechanism",
                "description": "回滚后硬规则仍应正常执行",
                "rule_id": "HR-004",
                "context": {"budget_category": "A", "has_pre_approval": False},
                "expected": {"passed": False, "output": "BLOCK"},
            },
            {
                "case_id": "EVO-006",
                "category": "rollback_mechanism",
                "description": "回滚后推理规则应保持学习结果",
                "rule_id": "RR-003",
                "context": {"training_expense": 100000, "quarter": "Q1", "annual_training_budget": 400000},
                "expected": {"passed": True},
            },
            {
                "case_id": "EVO-007",
                "category": "safety_boundary",
                "description": "安全边界-硬规则不可被修改",
                "rule_id": "HR-001",
                "context": {"budget_id": None, "has_budget": False},
                "expected": {"passed": False, "output": "BLOCK"},
            },
            {
                "case_id": "EVO-008",
                "category": "safety_boundary",
                "description": "安全边界-软规则输出始终为PASS",
                "rule_id": "SR-001",
                "context": {"execution_rate": 120},
                "expected": {"output": "PASS"},
            },
            {
                "case_id": "EVO-009",
                "category": "safety_boundary",
                "description": "安全边界-推理规则不可覆盖硬规则",
                "rule_id": "HR-003",
                "context": {"alert_triggered": True, "expense_approved": True},
                "expected": {"passed": False, "output": "BLOCK"},
            },
            {
                "case_id": "EVO-010",
                "category": "safety_boundary",
                "description": "安全边界-规则变更须审批",
                "rule_id": "HR-007",
                "context": {"ratio_decided_by_committee": False},
                "expected": {"passed": False, "output": "BLOCK"},
            },
            {
                "case_id": "EVO-011",
                "category": "safety_boundary",
                "description": "安全边界-所有规则变更须可追溯",
                "rule_id": "SR-007",
                "context": {"b_granted_total": 400000, "b_annual_total": 1000000},
                "expected": {"passed": False, "output": "PASS"},
            },
        ]
