from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.scenario import Scenario, ElasticBudget, BudgetReserve


class ScenarioEngine:
    """情景规划与弹性预算引擎"""

    async def create_scenario(
        self, name: str, scenario_type: str, assumptions: Dict, period: str = "", db: AsyncSession = None
    ) -> Scenario:
        """创建情景"""
        scenario = Scenario(
            name=name,
            scenario_type=scenario_type,
            assumptions=assumptions,
            period=period,
        )
        if db:
            db.add(scenario)
            await db.flush()
        return scenario

    async def compare_scenarios(
        self, scenario_ids: List[int], db: AsyncSession = None
    ) -> Dict[str, Any]:
        """多情景对比分析"""
        if db is None:
            return {"error": "数据库连接不可用"}

        scenarios = []
        for sid in scenario_ids:
            stmt = select(Scenario).where(Scenario.id == sid)
            result = await db.execute(stmt)
            scenario = result.scalar_one_or_none()
            if scenario:
                scenarios.append({
                    "id": scenario.id,
                    "name": scenario.name,
                    "type": scenario.scenario_type,
                    "assumptions": scenario.assumptions,
                    "budget_summary": scenario.budget_summary,
                })

        if len(scenarios) < 2:
            return {"error": "至少需要两个情景进行对比"}

        # 对比分析
        comparison = {
            "scenarios": scenarios,
            "key_differences": self._identify_differences(scenarios),
            "risk_assessment": self._assess_risks(scenarios),
            "recommendation": self._generate_recommendation(scenarios),
        }
        return comparison

    async def apply_elastic_adjustment(
        self, budget_id: str, actual_volume: float, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """弹性调整：基于实际业务量自动调整预算额度"""
        if db is None:
            return {"error": "数据库连接不可用"}

        stmt = select(ElasticBudget).where(ElasticBudget.budget_id == budget_id)
        result = await db.execute(stmt)
        elastic = result.scalar_one_or_none()

        if elastic is None:
            return {"error": f"预算项目 {budget_id} 无弹性预算配置"}

        # 计算调整
        volume_ratio = actual_volume / elastic.base_volume if elastic.base_volume > 0 else 1.0
        raw_adjusted = elastic.base_amount * volume_ratio * elastic.elasticity_coefficient

        # 限制调整幅度
        max_up = elastic.base_amount * (1 + elastic.max_adjustment_ratio)
        max_down = elastic.base_amount * (1 - elastic.max_adjustment_ratio)
        adjusted = max(min(raw_adjusted, max_up), max_down)

        # 更新
        elastic.current_volume = actual_volume
        elastic.adjusted_amount = adjusted
        await db.flush()

        return {
            "budget_id": budget_id,
            "base_amount": elastic.base_amount,
            "base_volume": elastic.base_volume,
            "actual_volume": actual_volume,
            "volume_ratio": volume_ratio,
            "elasticity_coefficient": elastic.elasticity_coefficient,
            "raw_adjusted": raw_adjusted,
            "adjusted_amount": adjusted,
            "adjustment_ratio": (adjusted - elastic.base_amount) / elastic.base_amount if elastic.base_amount > 0 else 0,
            "capped": raw_adjusted != adjusted,
        }

    async def run_stress_test(
        self, scenario_id: int, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """压力测试：极端情景下的财务压力测试"""
        if db is None:
            return {"error": "数据库连接不可用"}

        stmt = select(Scenario).where(Scenario.id == scenario_id)
        result = await db.execute(stmt)
        scenario = result.scalar_one_or_none()

        if scenario is None:
            return {"error": f"情景 {scenario_id} 不存在"}

        assumptions = scenario.assumptions or {}

        # 标准压力测试：收入下降30%+成本上升20%
        stress_factors = {
            "revenue_decline": assumptions.get("revenue_decline", 0.3),
            "cost_increase": assumptions.get("cost_increase", 0.2),
            "exchange_rate_impact": assumptions.get("exchange_rate_impact", 0.0),
        }

        # 计算压力影响
        base_revenue = assumptions.get("base_revenue", 100000000)
        base_cost = assumptions.get("base_cost", 80000000)

        stressed_revenue = base_revenue * (1 - stress_factors["revenue_decline"])
        stressed_cost = base_cost * (1 + stress_factors["cost_increase"])
        stressed_profit = stressed_revenue - stressed_cost

        return {
            "scenario_id": scenario_id,
            "scenario_name": scenario.name,
            "stress_factors": stress_factors,
            "base": {"revenue": base_revenue, "cost": base_cost, "profit": base_revenue - base_cost},
            "stressed": {"revenue": stressed_revenue, "cost": stressed_cost, "profit": stressed_profit},
            "profit_change": stressed_profit - (base_revenue - base_cost),
            "survival_months": max(0, stressed_profit / abs(stressed_cost) * 12) if stressed_profit > 0 else 0,
            "recommendation": "集团可承受此压力" if stressed_profit > 0 else "建议启动紧急调拨和成本削减计划",
        }

    async def emergency_allocation(
        self, reserve_id: int, budget_id: str, amount: float, reason: str, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """紧急调拨：从预算储备金紧急调拨资金"""
        if db is None:
            return {"error": "数据库连接不可用"}

        stmt = select(BudgetReserve).where(BudgetReserve.id == reserve_id)
        result = await db.execute(stmt)
        reserve = result.scalar_one_or_none()

        if reserve is None:
            return {"error": f"预算储备 {reserve_id} 不存在"}

        if reserve.available_amount < amount:
            return {"error": f"储备可用余额不足: 可用{reserve.available_amount}, 需要{amount}"}

        if reserve.approval_required:
            return {
                "status": "pending_approval",
                "message": "紧急调拨须经管委会批准，请在5个工作日内补办正式调拨手续",
                "reserve_id": reserve_id,
                "budget_id": budget_id,
                "amount": amount,
                "reason": reason,
            }

        # 执行调拨
        reserve.used_amount += amount
        reserve.available_amount -= amount
        await db.flush()

        return {
            "status": "completed",
            "reserve_id": reserve_id,
            "budget_id": budget_id,
            "amount": amount,
            "remaining_reserve": reserve.available_amount,
            "message": "紧急调拨完成",
        }

    def _identify_differences(self, scenarios: List[Dict]) -> List[Dict]:
        """识别情景间关键差异"""
        if len(scenarios) < 2:
            return []
        diffs = []
        keys = set()
        for s in scenarios:
            if s.get("assumptions"):
                keys.update(s["assumptions"].keys())
        for key in keys:
            values = [s.get("assumptions", {}).get(key, "N/A") for s in scenarios]
            if len(set(str(v) for v in values)) > 1:
                diffs.append({"assumption": key, "values": dict(zip([s["name"] for s in scenarios], values))})
        return diffs

    def _assess_risks(self, scenarios: List[Dict]) -> Dict[str, Any]:
        """评估情景风险"""
        pessimistic = [s for s in scenarios if s["type"] == "悲观"]
        if pessimistic:
            return {"highest_risk_scenario": pessimistic[0]["name"], "risk_level": "高"}
        return {"risk_level": "中"}

    def _generate_recommendation(self, scenarios: List[Dict]) -> str:
        """生成情景对比建议"""
        types = [s["type"] for s in scenarios]
        if "悲观" in types and "基准" in types:
            return "建议以基准情景执行，同时制定悲观情景的应急预案"
        return "建议补充更多情景进行对比分析"
