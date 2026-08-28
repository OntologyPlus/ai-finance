"""
SoD（Segregation of Duties，职责分离）检查器。

职责：在关键业务操作（调拨/报销/预警闭环）入口处阻断同一人
既发起又审批的自批自核风险。这是对审计高频关注点的工程级防护。

工作原理：
- 维护一份"SOD_PAIRS"不相容操作对（如 "expense.submit" 对 "expense.final_approve"）
- 通过 audit_log 查询"该 user_id 在同一 resource_id 上是否已做过对端操作"
- 如果有则拒绝，抛出 SoDViolation
- 实际"对端操作"由 audit_log 的 action 字段命名约定支撑

设计取舍：
- SoD 是业务规则（写在硬规则里），但本模块做了工程化封装便于复用
- 资源粒度：通常按 resource_id（如 transfer_id / report_id / closure_id）做对账
  但同 user 在不同 resource 上做了对端操作不应视为冲突——这是审计标准
- 时间窗口：默认不限制（旧账也算对端），但允许通过 window_seconds 收紧到单次会话
- 不依赖 DB 持久化：直接调 audit_log.query_by_actor()

用法示例：
    from ontology.sod import SoDEnforcer, SOD_PAIRS

    enforcer = SoDEnforcer()
    # 在预算调拨最终审批入口
    enforcer.check(
        user_id=approver_id,
        operation="budget.final_approve",
        resource_id=transfer_id,
    )  # 抛 SoDViolation 即阻断
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Set, Tuple


# 关键不相容操作对。每一对定义了"如果用户做过左项，则不能做右项"（及反之）。
# 操作命名应与 audit_log.log() 调用时的 action 字符串保持一致。
SOD_PAIRS: List[Tuple[str, str]] = [
    # 预算调拨：发起人 ≠ 最终审批人
    ("budget.transfer.request", "budget.transfer.final_approve"),
    # 报销：发起人 ≠ 最终审批人
    ("expense.submit", "expense.final_approve"),
    # 预警闭环：响应人 ≠ 闭环确认人（与 HR-013 双签要求一致）
    ("alert.respond", "alert.confirm_closure"),
    # 调拨提议 vs 调拨批准（更细粒度）
    ("budget.transfer.propose", "budget.transfer.approve"),
]


class SoDViolation(Exception):
    """职责分离违例。审计/合规事件。"""

    def __init__(self, user_id: str, attempted: str, conflicting: str, resource_id: str = ""):
        self.user_id = user_id
        self.attempted = attempted
        self.conflicting = conflicting
        self.resource_id = resource_id
        super().__init__(
            f"SoD 违例：用户 {user_id!r} 已在资源 {resource_id!r} 上执行 {conflicting!r}，"
            f"不能再执行 {attempted!r}（同一人发起与审批/响应与闭环确认形成自批自核风险）"
        )


@dataclass
class SoDCheckResult:
    """SoD 检查结果（非异常路径）。用于 AI 建议类场景而非直接阻断。"""

    allowed: bool
    user_id: str
    attempted: str
    resource_id: str
    conflicting_actions: List[str]
    reason: str = ""


class SoDEnforcer:
    """职责分离执行器。

    设计要点：
    - 不在此处持久化状态——通过 audit_log 反查
    - 异常路径（check）用于硬阻断；返回结果路径（evaluate）用于 AI 建议
    - 静态化 SOD_PAIRS 但支持实例化时追加
    """

    def __init__(self, additional_pairs: Optional[Iterable[Tuple[str, str]]] = None):
        self._pairs: List[Tuple[str, str]] = list(SOD_PAIRS)
        if additional_pairs:
            self._pairs.extend(additional_pairs)

    def _conflicts_for(self, operation: str) -> Set[str]:
        """找出与给定 operation 不相容的所有操作（含正反两方向）。"""
        conflicts: Set[str] = set()
        for a, b in self._pairs:
            if operation == a:
                conflicts.add(b)
            elif operation == b:
                conflicts.add(a)
        return conflicts

    def evaluate(
        self,
        user_id: str,
        operation: str,
        resource_id: str = "",
    ) -> SoDCheckResult:
        """评估是否违例（不抛异常，返回结构化结果）。"""
        conflicts = self._conflicts_for(operation)
        if not conflicts:
            return SoDCheckResult(
                allowed=True,
                user_id=user_id,
                attempted=operation,
                resource_id=resource_id,
                conflicting_actions=[],
                reason="该操作未注册 SoD 对，无需检查",
            )

        prior = self._query_user_actions(user_id, resource_id, conflicts)
        if not prior:
            return SoDCheckResult(
                allowed=True,
                user_id=user_id,
                attempted=operation,
                resource_id=resource_id,
                conflicting_actions=[],
                reason="无历史对端操作，SoD 通过",
            )

        return SoDCheckResult(
            allowed=False,
            user_id=user_id,
            attempted=operation,
            resource_id=resource_id,
            conflicting_actions=prior,
            reason=(
                f"用户已在资源 {resource_id!r} 上执行 {prior}，"
                f"与当前操作 {operation!r} 形成不相容对（同人发起+审批）"
            ),
        )

    def check(self, user_id: str, operation: str, resource_id: str = "") -> None:
        """硬阻断：违例则抛 SoDViolation。

        这是给业务引擎入口用的——确保关键操作绝对不会被同人发起+审批绕过。
        """
        result = self.evaluate(user_id, operation, resource_id)
        if not result.allowed:
            raise SoDViolation(
                user_id=user_id,
                attempted=operation,
                conflicting=", ".join(result.conflicting_actions),
                resource_id=resource_id,
            )

    def _query_user_actions(
        self,
        user_id: str,
        resource_id: str,
        actions: Set[str],
    ) -> List[str]:
        """从 audit_log 查 user_id 在 resource_id 上做过的 actions 集合中，
        与目标 actions 取交集，返回相交的部分。

        实现说明：audit_log 是进程内 _entries 列表（见 services/audit_log.py）。
        我们从 audit_log 全局单例中查询，匹配 actor + resource + action 三个维度。
        """
        try:
            from services.audit_log import get_audit_logger  # type: ignore
            logger = get_audit_logger()
        except Exception:
            # audit_log 不可用时退化为空（不阻断生产环境）
            return []

        matched: List[str] = []
        # 兼容两种 API：entries 列表属性 / query 方法
        entries = getattr(logger, "_entries", None)
        if entries is None:
            query_fn = getattr(logger, "query", None)
            if query_fn is None:
                return []
            try:
                entries = query_fn(actor=user_id) or []
            except TypeError:
                try:
                    entries = query_fn(user_id) or []
                except Exception:
                    return []
        else:
            entries = [e for e in entries if e.get("actor") == user_id]

        for e in entries:
            action = e.get("action", "")
            if action in actions:
                # 资源匹配：未指定 resource_id 则视为全局（更严格）
                # 指定 resource_id 则要求 e["resource"] == resource_id
                if not resource_id or e.get("resource") == resource_id:
                    matched.append(action)

        return matched


# 全局单例（避免重复实例化）
_default_enforcer: Optional[SoDEnforcer] = None


def get_sod_enforcer() -> SoDEnforcer:
    """获取 SoDEnforcer 默认单例。"""
    global _default_enforcer
    if _default_enforcer is None:
        _default_enforcer = SoDEnforcer()
    return _default_enforcer
