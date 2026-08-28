"""
v12.0: 八阶段血缘追踪服务 (Lineage Tracker)

设计目标：实现"一笔报销→SP 战略举措"的完整血缘追溯，
支撑设计哲学 1 (数据自产自销) 和 4 (本体驱动)。

支持的追溯链：
  报销单 → 预算项目 → 象限 → 战略举措 → SP/BP
  预警记录 → 预算项目 → 象限 → 战略举措
  预算项目 → 战略举措 → SP/BP
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class LineageNode:
    """血缘图节点"""

    def __init__(
        self,
        node_id: str,
        node_type: str,
        label: str,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.node_id = node_id
        self.node_type = node_type
        self.label = label
        self.meta = meta or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "label": self.label,
            "meta": self.meta,
        }


class LineageEdge:
    """血缘图边（关系）"""

    def __init__(self, source: str, target: str, relation: str, meta: Optional[Dict[str, Any]] = None) -> None:
        self.source = source
        self.target = target
        self.relation = relation
        self.meta = meta or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "meta": self.meta,
        }


class LineageTracker:
    """跨阶段血缘查询（SP→BP→预算→报销→预警→报告→次年）"""

    MAX_DEPTH = 5  # 最大追溯深度（D1 决策）

    def __init__(self) -> None:
        self._cache: Dict[str, Any] = {}

    async def trace_expense(self, expense_id: str, db: AsyncSession) -> Dict[str, Any]:
        """报销→预算→象限→战略举措→SP"""
        from models.expense import ExpenseReport
        from models.budget import BudgetItem, BudgetSubjectL3, BudgetSubjectL2, BudgetSubjectL1
        from models.strategic import StrategicInitiative, StrategicPlan
        from models.organization import Organization

        nodes: List[LineageNode] = []
        edges: List[LineageEdge] = []
        seen: set[str] = set()

        # 1. 报销单
        expense = await db.get(ExpenseReport, expense_id)
        if expense is None:
            return {"nodes": [], "edges": [], "summary": "报销单不存在", "depth": 0}

        nodes.append(LineageNode(
            node_id=f"expense:{expense_id}",
            node_type="expense",
            label=f"报销单 {expense_id}",
            meta={"amount": getattr(expense, "amount", None), "status": getattr(expense, "status", None)},
        ))
        seen.add(f"expense:{expense_id}")

        # 2. 预算项目（如有）
        budget_id = getattr(expense, "budget_id", None)
        if budget_id:
            budget = await db.get(BudgetItem, budget_id)
            if budget:
                self._add_budget_chain(
                    budget, nodes, edges, seen,
                )

        return self._build_result(nodes, edges, depth=len(nodes))

    async def trace_alert(self, alert_id: str, db: AsyncSession) -> Dict[str, Any]:
        """预警→预算→象限→战略举措"""
        from models.alert import AlertRecord
        from models.budget import BudgetItem

        nodes: List[LineageNode] = []
        edges: List[LineageEdge] = []
        seen: set[str] = set()

        # 1. 预警记录
        alert = await db.get(AlertRecord, alert_id)
        if alert is None:
            return {"nodes": [], "edges": [], "summary": "预警不存在", "depth": 0}

        nodes.append(LineageNode(
            node_id=f"alert:{alert_id}",
            node_type="alert",
            label=f"预警 {alert_id}",
            meta={
                "level": getattr(alert, "alert_level", None),
                "type": getattr(alert, "alert_type", None),
                "status": getattr(alert, "alert_status", None),
            },
        ))
        seen.add(f"alert:{alert_id}")

        # 2. 关联预算
        budget_id = getattr(alert, "budget_id", None)
        if budget_id:
            budget = await db.get(BudgetItem, budget_id)
            if budget:
                self._add_budget_chain(budget, nodes, edges, seen)

        return self._build_result(nodes, edges, depth=len(nodes))

    async def trace_budget(self, budget_id: str, db: AsyncSession) -> Dict[str, Any]:
        """预算→象限→战略举措→SP/BP"""
        from models.budget import BudgetItem

        nodes: List[LineageNode] = []
        edges: List[LineageEdge] = []
        seen: set[str] = set()

        budget = await db.get(BudgetItem, budget_id)
        if budget is None:
            return {"nodes": [], "edges": [], "summary": "预算不存在", "depth": 0}

        self._add_budget_chain(budget, nodes, edges, seen)
        return self._build_result(nodes, edges, depth=len(nodes))

    def _add_budget_chain(
        self,
        budget: Any,
        nodes: List[LineageNode],
        edges: List[LineageEdge],
        seen: set[str],
    ) -> None:
        """添加预算→L3→L2→L1→象限→战略举措→SP 的链路"""
        from models.budget import BudgetSubjectL3, BudgetSubjectL2, BudgetSubjectL1
        from models.strategic import StrategicInitiative, StrategicPlan

        budget_id = getattr(budget, "budget_id", None)
        if not budget_id:
            return

        # 预算项
        budget_node_id = f"budget:{budget_id}"
        if budget_node_id not in seen:
            nodes.append(LineageNode(
                node_id=budget_node_id,
                node_type="budget",
                label=f"预算 {budget.budget_name or budget_id}",
                meta={
                    "category": getattr(budget, "budget_category", None),
                    "quadrant": getattr(budget, "quadrant", None),
                    "annual_amount": float(getattr(budget, "annual_amount", 0) or 0),
                    "status": getattr(budget, "status", None),
                },
            ))
            seen.add(budget_node_id)

        # L3 科目
        l3_code = getattr(budget, "l3_code", None)
        if l3_code:
            # L3 node 需来自 budget 的 l3_code 字段
            l3_node_id = f"l3:{l3_code}"
            if l3_node_id not in seen:
                # v12.0: 简化 — 不查 DB，直接构造 L3 节点
                nodes.append(LineageNode(
                    node_id=l3_node_id,
                    node_type="l3",
                    label=f"L3 {l3_code}",
                    meta={"l3_code": l3_code, "control_tag": getattr(budget, "control_tag", None)},
                ))
                seen.add(l3_node_id)
            edges.append(LineageEdge(budget_node_id, l3_node_id, "挂载到"))

        # 象限
        quadrant = getattr(budget, "quadrant", None)
        if quadrant:
            q_node_id = f"quadrant:{quadrant}"
            if q_node_id not in seen:
                nodes.append(LineageNode(
                    node_id=q_node_id,
                    node_type="quadrant",
                    label=f"象限 {quadrant}",
                    meta={"quadrant": quadrant},
                ))
                seen.add(q_node_id)
            edges.append(LineageEdge(budget_node_id, q_node_id, "归属象限"))

        # 战略举措
        initiative_id = getattr(budget, "strategy_initiative_id", None) or getattr(budget, "initiative_id", None)
        if initiative_id:
            init_node_id = f"initiative:{initiative_id}"
            if init_node_id not in seen:
                nodes.append(LineageNode(
                    node_id=init_node_id,
                    node_type="initiative",
                    label=f"战略举措 {initiative_id}",
                    meta={"initiative_id": initiative_id},
                ))
                seen.add(init_node_id)
            edges.append(LineageEdge(init_node_id, budget_node_id, "驱动预算"))

            # SP/BP（v12.0 简化：只标记 ID，不深查）
            sp_node_id = f"sp:bp:{initiative_id[:4] if initiative_id else 'unknown'}"
            if sp_node_id not in seen:
                nodes.append(LineageNode(
                    node_id=sp_node_id,
                    node_type="sp_bp",
                    label=f"SP/BP（{initiative_id[:4]}...）",
                    meta={"source": "战略规划"},
                ))
                seen.add(sp_node_id)
            edges.append(LineageEdge(sp_node_id, init_node_id, "解码出"))

    def _build_result(
        self,
        nodes: List[LineageNode],
        edges: List[LineageEdge],
        depth: int,
    ) -> Dict[str, Any]:
        """构造最终返回结果"""
        return {
            "nodes": [n.to_dict() for n in nodes],
            "edges": [e.to_dict() for e in edges],
            "summary": self._build_summary(nodes),
            "depth": min(depth, self.MAX_DEPTH),
            "total_nodes": len(nodes),
            "total_edges": len(edges),
        }

    def _build_summary(self, nodes: List[LineageNode]) -> str:
        """构造血缘链路摘要"""
        type_map: Dict[str, int] = {}
        for n in nodes:
            type_map[n.node_type] = type_map.get(n.node_type, 0) + 1

        order = ["sp_bp", "initiative", "quadrant", "l3", "budget", "expense", "alert", "report"]
        parts: List[str] = []
        for t in order:
            if t in type_map:
                label_map = {
                    "sp_bp": "SP/BP",
                    "initiative": "战略举措",
                    "quadrant": "象限",
                    "l3": "L3科目",
                    "budget": "预算",
                    "expense": "报销",
                    "alert": "预警",
                    "report": "报告",
                }
                parts.append(f"{label_map.get(t, t)}×{type_map[t]}")
        return " → ".join(parts) if parts else "无血缘链路"


# 全局单例
_lineage_tracker: Optional[LineageTracker] = None


def get_lineage_tracker() -> LineageTracker:
    """获取 LineageTracker 单例"""
    global _lineage_tracker
    if _lineage_tracker is None:
        _lineage_tracker = LineageTracker()
    return _lineage_tracker
