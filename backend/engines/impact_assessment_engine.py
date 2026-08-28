from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.impact_assessment import ImpactChain, ImpactNode
from models.budget import BudgetItem


class ImpactAssessmentEngine:
    """全链路影响评估引擎 — 一变即评、一评即显"""

    async def assess_budget_change(
        self, budget_id: str, change_type: str, amount: float, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """评估预算变更影响"""
        chain = ImpactChain(
            source_operation=f"预算变更: {budget_id} {change_type} {amount}",
            operation_type="budget_change",
            operation_params={"budget_id": budget_id, "change_type": change_type, "amount": amount},
        )

        nodes = []

        # 1. 预算域影响
        budget_impact = await self._assess_budget_domain(budget_id, change_type, amount, db)
        nodes.append(ImpactNode(
            chain_id=0,  # will be set after chain is saved
            impact_domain="budget",
            impact_description=budget_impact["description"],
            impact_severity=budget_impact["severity"],
            impact_details=budget_impact,
            mitigation_suggestion=budget_impact.get("mitigation", ""),
        ))

        # 2. 费用域影响
        expense_impact = self._assess_expense_domain(budget_id, change_type, amount)
        nodes.append(ImpactNode(
            chain_id=0,
            impact_domain="expense",
            impact_description=expense_impact["description"],
            impact_severity=expense_impact["severity"],
            impact_details=expense_impact,
        ))

        # 3. 预警域影响
        alert_impact = self._assess_alert_domain(budget_id, change_type, amount)
        nodes.append(ImpactNode(
            chain_id=0,
            impact_domain="alert",
            impact_description=alert_impact["description"],
            impact_severity=alert_impact["severity"],
            impact_details=alert_impact,
        ))

        # 4. 现金流域影响
        cashflow_impact = self._assess_cashflow_domain(budget_id, change_type, amount)
        nodes.append(ImpactNode(
            chain_id=0,
            impact_domain="cashflow",
            impact_description=cashflow_impact["description"],
            impact_severity=cashflow_impact["severity"],
            impact_details=cashflow_impact,
        ))

        # 5. 战略域影响
        strategic_impact = self._assess_strategic_domain(budget_id, change_type, amount)
        nodes.append(ImpactNode(
            chain_id=0,
            impact_domain="strategic",
            impact_description=strategic_impact["description"],
            impact_severity=strategic_impact["severity"],
            impact_details=strategic_impact,
        ))

        # 计算总体风险
        severity_scores = {"低": 1, "中": 2, "高": 3}
        max_severity = max(nodes, key=lambda n: severity_scores.get(n.impact_severity, 0))
        chain.overall_risk = max_severity.impact_severity
        chain.affected_domains = list(set(n.impact_domain for n in nodes))

        # 保存到数据库
        if db:
            db.add(chain)
            await db.flush()
            for node in nodes:
                node.chain_id = chain.id
                db.add(node)
            await db.flush()

        return {
            "chain_id": chain.id if db else None,
            "source_operation": chain.source_operation,
            "overall_risk": chain.overall_risk,
            "affected_domains": chain.affected_domains,
            "impacts": [
                {
                    "domain": n.impact_domain,
                    "description": n.impact_description,
                    "severity": n.impact_severity,
                    "mitigation": n.mitigation_suggestion,
                }
                for n in nodes
            ],
        }

    async def assess_expense_overrun(
        self, expense_id: str, overrun_amount: float, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """评估费用超支影响"""
        return await self.assess_budget_change(
            budget_id=f"expense:{expense_id}",
            change_type="overrun",
            amount=overrun_amount,
            db=db,
        )

    async def assess_strategic_shift(
        self, initiative_id: str, new_direction: str, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """评估战略调整影响"""
        chain = ImpactChain(
            source_operation=f"战略调整: {initiative_id} → {new_direction}",
            operation_type="strategic_shift",
            operation_params={"initiative_id": initiative_id, "new_direction": new_direction},
            overall_risk="高",
            affected_domains=["strategic", "budget", "alert"],
        )

        return {
            "chain_id": None,
            "source_operation": chain.source_operation,
            "overall_risk": "高",
            "affected_domains": chain.affected_domains,
            "impacts": [
                {"domain": "strategic", "description": f"战略举措{initiative_id}方向调整，需重新评估预算组合", "severity": "高", "mitigation": "建议召开管委会专项会议"},
                {"domain": "budget", "description": "关联预算项目可能需要重新编制或调拨", "severity": "中", "mitigation": "启动预算调整流程"},
                {"domain": "alert", "description": "战略调整可能触发预算偏差预警", "severity": "中", "mitigation": "关注预警并准备响应方案"},
            ],
        }

    async def trace_impact(self, chain_id: int, db: AsyncSession = None) -> Dict[str, Any]:
        """追踪影响链"""
        if db is None:
            return {"error": "数据库连接不可用"}

        stmt = select(ImpactChain).where(ImpactChain.id == chain_id)
        result = await db.execute(stmt)
        chain = result.scalar_one_or_none()

        if chain is None:
            return {"error": f"影响链 {chain_id} 不存在"}

        stmt2 = select(ImpactNode).where(ImpactNode.chain_id == chain_id)
        result2 = await db.execute(stmt2)
        nodes = result2.scalars().all()

        return {
            "chain_id": chain.id,
            "source_operation": chain.source_operation,
            "overall_risk": chain.overall_risk,
            "status": chain.status,
            "nodes": [
                {"domain": n.impact_domain, "description": n.impact_description, "severity": n.impact_severity, "mitigation": n.mitigation_suggestion}
                for n in nodes
            ],
        }

    async def suggest_mitigation(self, chain_id: int, db: AsyncSession = None) -> Dict[str, Any]:
        """缓解建议"""
        trace = await self.trace_impact(chain_id, db)
        if "error" in trace:
            return trace

        mitigations = []
        for node in trace.get("nodes", []):
            if node["severity"] in ("高", "中"):
                mitigations.append({
                    "domain": node["domain"],
                    "issue": node["description"],
                    "suggestion": node.get("mitigation") or self._auto_suggest(node["domain"], node["severity"]),
                })

        return {"chain_id": chain_id, "mitigations": mitigations}

    # === 域影响评估方法 ===

    async def _assess_budget_domain(self, budget_id, change_type, amount, db) -> Dict:
        """预算域影响评估"""
        budget_item = None
        if db:
            try:
                stmt = select(BudgetItem).where(BudgetItem.budget_id == budget_id)
                result = await db.execute(stmt)
                budget_item = result.scalar_one_or_none()
            except Exception:
                pass

        if budget_item:
            available = float(budget_item.available_amount or 0)
            if change_type == "decrease" and amount > available * 0.5:
                return {"description": f"预算减少{amount}元，可用额度将大幅下降(剩余{available-amount:.0f})", "severity": "高", "mitigation": "建议从储备金调拨或调整其他预算"}
            elif change_type == "increase":
                return {"description": f"预算增加{amount}元，需确认资金来源", "severity": "低", "mitigation": "确认资金来源后执行"}

        return {"description": f"预算变更{change_type} {amount}元", "severity": "中"}

    def _assess_expense_domain(self, budget_id, change_type, amount) -> Dict:
        """费用域影响评估"""
        if change_type == "decrease":
            return {"description": "预算减少可能影响报销审批路径和管控级别", "severity": "中"}
        return {"description": "预算变更对费用执行影响较小", "severity": "低"}

    def _assess_alert_domain(self, budget_id, change_type, amount) -> Dict:
        """预警域影响评估"""
        if change_type == "decrease":
            return {"description": "预算减少可能导致执行率上升，触发预警阈值变化", "severity": "中"}
        return {"description": "预算变更对预警阈值影响较小", "severity": "低"}

    def _assess_cashflow_domain(self, budget_id, change_type, amount) -> Dict:
        """现金流域影响评估"""
        if change_type == "decrease" and amount > 1000000:
            return {"description": f"大额预算减少{amount}元，可能影响现金流计划", "severity": "中"}
        return {"description": "预算变更对现金流影响较小", "severity": "低"}

    def _assess_strategic_domain(self, budget_id, change_type, amount) -> Dict:
        """战略域影响评估"""
        if change_type == "decrease" and amount > 5000000:
            return {"description": "大额预算减少可能影响战略覆盖率", "severity": "高", "mitigation": "建议评估战略对齐度"}
        return {"description": "预算变更对战略执行影响较小", "severity": "低"}

    def _auto_suggest(self, domain: str, severity: str) -> str:
        """自动生成缓解建议"""
        suggestions = {
            "budget": "建议启动预算调整流程或从储备金调拨",
            "expense": "建议检查报销审批路径和管控级别",
            "alert": "建议关注预警阈值变化并准备响应方案",
            "cashflow": "建议更新现金流预测和付款排期",
            "strategic": "建议召开管委会专项会议评估战略影响",
        }
        return suggestions.get(domain, "建议进一步评估影响")
