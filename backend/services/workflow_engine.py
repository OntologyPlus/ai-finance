from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional

from loguru import logger


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMED_OUT = "timed_out"


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkflowStep:
    step_id: str
    name: str
    action: Callable
    condition: Optional[str] = None
    timeout_seconds: int = 300
    max_retries: int = 3
    retry_delay_seconds: int = 5
    next_step: Optional[str] = None
    on_failure_step: Optional[str] = None
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: str = ""
    retries: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


@dataclass
class WorkflowDefinition:
    workflow_id: str
    name: str
    description: str
    steps: Dict[str, WorkflowStep] = field(default_factory=dict)
    initial_step: str = ""
    variables: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowExecution:
    execution_id: str
    workflow_id: str
    status: WorkflowStatus = WorkflowStatus.PENDING
    current_step: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    step_results: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: str = ""


_SAFE_OPERATORS = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    "in": lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
    "and": lambda a, b: a and b,
    "or": lambda a, b: a or b,
    "not": lambda a: not a,
    "is_none": lambda a: a is None,
    "is_not_none": lambda a: a is not None,
}


def safe_eval_condition(condition: str, context: dict) -> bool:
    if not condition or not condition.strip():
        return True

    condition = condition.strip()

    for op_str in ["!=", ">=", "<=", "==", ">", "<", " in ", " not_in "]:
        if op_str in condition:
            parts = condition.split(op_str, 1)
            if len(parts) != 2:
                continue
            left_expr = parts[0].strip()
            right_expr = parts[1].strip()

            left_val = _resolve_value(left_expr, context)
            right_val = _resolve_value(right_expr, context)

            op_fn = _SAFE_OPERATORS.get(op_str.strip())
            if op_fn:
                try:
                    return bool(op_fn(left_val, right_val))
                except (TypeError, ValueError):
                    return False

    if condition.startswith("not "):
        inner = condition[4:].strip()
        return not safe_eval_condition(inner, context)

    if " and " in condition:
        parts = condition.split(" and ", 1)
        return safe_eval_condition(parts[0], context) and safe_eval_condition(parts[1], context)

    if " or " in condition:
        parts = condition.split(" or ", 1)
        return safe_eval_condition(parts[0], context) or safe_eval_condition(parts[1], context)

    resolved = _resolve_value(condition, context)
    return bool(resolved) if resolved is not None else False


def _resolve_value(expr: str, context: dict) -> Any:
    expr = expr.strip()

    if (expr.startswith('"') and expr.endswith('"')) or (expr.startswith("'") and expr.endswith("'")):
        return expr[1:-1]

    if expr.lower() == "true":
        return True
    if expr.lower() == "false":
        return False
    if expr.lower() == "none" or expr.lower() == "null":
        return None

    try:
        if "." in expr:
            return float(expr)
        return int(expr)
    except ValueError:
        pass

    if expr in context:
        return context[expr]

    parts = expr.split(".")
    val = context
    for part in parts:
        if isinstance(val, dict):
            val = val.get(part)
        else:
            return None
    return val


class WorkflowEngine:
    def __init__(self) -> None:
        self._definitions: Dict[str, WorkflowDefinition] = {}
        self._executions: Dict[str, WorkflowExecution] = {}
        self._register_predefined_workflows()

    def register_workflow(self, definition: WorkflowDefinition) -> None:
        self._definitions[definition.workflow_id] = definition
        logger.info(f"WorkflowEngine: registered workflow '{definition.workflow_id}' ({definition.name})")

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowDefinition]:
        return self._definitions.get(workflow_id)

    def list_workflows(self) -> List[dict]:
        return [
            {"workflow_id": w.workflow_id, "name": w.name, "description": w.description}
            for w in self._definitions.values()
        ]

    async def execute(self, workflow_id: str, context: Optional[dict] = None) -> WorkflowExecution:
        definition = self._definitions.get(workflow_id)
        if definition is None:
            raise ValueError(f"Workflow '{workflow_id}' not found")

        execution = WorkflowExecution(
            execution_id=f"WFE-{len(self._executions) + 1:04d}",
            workflow_id=workflow_id,
            context=context or {},
        )
        self._executions[execution.execution_id] = execution

        execution.status = WorkflowStatus.RUNNING
        execution.started_at = datetime.now().isoformat()
        execution.current_step = definition.initial_step

        current_step_id = definition.initial_step
        while current_step_id:
            step = definition.steps.get(current_step_id)
            if step is None:
                execution.status = WorkflowStatus.FAILED
                execution.error = f"Step '{current_step_id}' not found"
                break

            if step.condition and not safe_eval_condition(step.condition, execution.context):
                step.status = StepStatus.SKIPPED
                current_step_id = step.next_step
                continue

            step.status = StepStatus.RUNNING
            step.started_at = datetime.now().isoformat()

            success = False
            for attempt in range(step.max_retries + 1):
                try:
                    result = await asyncio.wait_for(
                        self._run_step_action(step, execution.context),
                        timeout=step.timeout_seconds,
                    )
                    step.result = result
                    step.status = StepStatus.COMPLETED
                    step.completed_at = datetime.now().isoformat()
                    execution.step_results[step.step_id] = result
                    success = True
                    break
                except asyncio.TimeoutError:
                    step.retries = attempt + 1
                    logger.warning(f"WorkflowEngine: step '{step.step_id}' timed out (attempt {attempt + 1})")
                except Exception as e:
                    step.retries = attempt + 1
                    step.error = str(e)
                    logger.warning(f"WorkflowEngine: step '{step.step_id}' failed (attempt {attempt + 1}): {e}")

                if attempt < step.max_retries:
                    await asyncio.sleep(step.retry_delay_seconds)

            if not success:
                step.status = StepStatus.TIMED_OUT if "timed out" in step.error or step.retries > 0 else StepStatus.FAILED
                if step.on_failure_step:
                    current_step_id = step.on_failure_step
                    continue
                else:
                    execution.status = WorkflowStatus.FAILED
                    execution.error = f"Step '{step.step_id}' failed after {step.max_retries + 1} attempts"
                    break

            current_step_id = step.next_step

        if execution.status == WorkflowStatus.RUNNING:
            execution.status = WorkflowStatus.COMPLETED
        execution.completed_at = datetime.now().isoformat()

        logger.info(f"WorkflowEngine: workflow '{workflow_id}' execution {execution.execution_id} -> {execution.status.value}")
        return execution

    def get_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        return self._executions.get(execution_id)

    async def _run_step_action(self, step: WorkflowStep, context: dict) -> Any:
        if asyncio.iscoroutinefunction(step.action):
            return await step.action(context)
        return step.action(context)

    def _register_predefined_workflows(self) -> None:
        self.register_workflow(WorkflowDefinition(
            workflow_id="wf.expense_reimbursement",
            name="费用报销流程",
            description="员工提交报销单，经组织线+法人线双线审批后核销",
            initial_step="submit",
            steps={
                "submit": WorkflowStep(
                    step_id="submit",
                    name="提交报销单",
                    action=self._noop_action,
                    next_step="check_budget",
                ),
                "check_budget": WorkflowStep(
                    step_id="check_budget",
                    name="预算检查",
                    action=self._noop_action,
                    condition="has_budget == true",
                    next_step="route_control",
                    on_failure_step="reject_no_budget",
                ),
                "reject_no_budget": WorkflowStep(
                    step_id="reject_no_budget",
                    name="无预算驳回",
                    action=self._noop_action,
                ),
                "route_control": WorkflowStep(
                    step_id="route_control",
                    name="管控路由",
                    action=self._noop_action,
                    next_step="org_approval",
                ),
                "org_approval": WorkflowStep(
                    step_id="org_approval",
                    name="组织线审批",
                    action=self._noop_action,
                    next_step="legal_approval",
                ),
                "legal_approval": WorkflowStep(
                    step_id="legal_approval",
                    name="法人线审批",
                    action=self._noop_action,
                    condition="amount > 50000",
                    next_step="write_off",
                    on_failure_step="write_off",
                ),
                "write_off": WorkflowStep(
                    step_id="write_off",
                    name="预算核销",
                    action=self._noop_action,
                ),
            },
        ))

        self.register_workflow(WorkflowDefinition(
            workflow_id="wf.alert_closure",
            name="预警闭环流程",
            description="预警响应、双签闭环确认流程",
            initial_step="alert_trigger",
            steps={
                "alert_trigger": WorkflowStep(
                    step_id="alert_trigger",
                    name="预警触发",
                    action=self._noop_action,
                    next_step="business_response",
                ),
                "business_response": WorkflowStep(
                    step_id="business_response",
                    name="业务单元响应",
                    action=self._noop_action,
                    timeout_seconds=86400,
                    next_step="bp_confirm",
                    on_failure_step="escalate",
                ),
                "bp_confirm": WorkflowStep(
                    step_id="bp_confirm",
                    name="财经BP确认",
                    action=self._noop_action,
                    next_step="close_alert",
                    on_failure_step="escalate",
                ),
                "close_alert": WorkflowStep(
                    step_id="close_alert",
                    name="闭环确认",
                    action=self._noop_action,
                ),
                "escalate": WorkflowStep(
                    step_id="escalate",
                    name="预警升级",
                    action=self._noop_action,
                ),
            },
        ))

        self.register_workflow(WorkflowDefinition(
            workflow_id="wf.b2a_conversion",
            name="B→A转换流程",
            description="B类预算里程碑达标后转换为A类预算",
            initial_step="check_milestone",
            steps={
                "check_milestone": WorkflowStep(
                    step_id="check_milestone",
                    name="里程碑达标检查",
                    action=self._noop_action,
                    condition="milestone_achieved == true",
                    next_step="submit_conversion",
                    on_failure_step="reject_milestone",
                ),
                "reject_milestone": WorkflowStep(
                    step_id="reject_milestone",
                    name="里程碑未达标",
                    action=self._noop_action,
                ),
                "submit_conversion": WorkflowStep(
                    step_id="submit_conversion",
                    name="提交B→A转换申请",
                    action=self._noop_action,
                    next_step="committee_report",
                ),
                "committee_report": WorkflowStep(
                    step_id="committee_report",
                    name="管委会专项报告",
                    action=self._noop_action,
                    next_step="freeze_budget",
                ),
                "freeze_budget": WorkflowStep(
                    step_id="freeze_budget",
                    name="冻结额度",
                    action=self._noop_action,
                ),
            },
        ))

        self.register_workflow(WorkflowDefinition(
            workflow_id="wf.budget_adjustment",
            name="预算调整流程",
            description="预算调整与调拨，含跨象限审批",
            initial_step="submit_adjustment",
            steps={
                "submit_adjustment": WorkflowStep(
                    step_id="submit_adjustment",
                    name="提交预算调整申请",
                    action=self._noop_action,
                    next_step="check_quadrant",
                ),
                "check_quadrant": WorkflowStep(
                    step_id="check_quadrant",
                    name="检查是否跨象限",
                    action=self._noop_action,
                    condition="cross_quadrant == true",
                    next_step="committee_approval",
                    on_failure_step="finance_approval",
                ),
                "committee_approval": WorkflowStep(
                    step_id="committee_approval",
                    name="管委会审批",
                    action=self._noop_action,
                    next_step="execute_adjustment",
                    on_failure_step="reject_adjustment",
                ),
                "finance_approval": WorkflowStep(
                    step_id="finance_approval",
                    name="财经中心审批",
                    action=self._noop_action,
                    next_step="execute_adjustment",
                    on_failure_step="reject_adjustment",
                ),
                "execute_adjustment": WorkflowStep(
                    step_id="execute_adjustment",
                    name="执行预算调整",
                    action=self._noop_action,
                ),
                "reject_adjustment": WorkflowStep(
                    step_id="reject_adjustment",
                    name="调整申请驳回",
                    action=self._noop_action,
                ),
            },
        ))

    @staticmethod
    async def _noop_action(context: dict) -> dict:
        return {"status": "completed", "context": context}
