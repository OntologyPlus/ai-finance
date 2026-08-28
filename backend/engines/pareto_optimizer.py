"""
Pareto 前沿优化引擎 — v8.0 Module I-D
按 `经营分析方法论.md` §4.4 治理流程深化：
多目标平衡分析

4 目标：
1. 预算合规度 (Budget Compliance) — 高 = 合规
2. 业务影响度 (Business Impact) — 高 = 强正向
3. 战略对齐度 (Strategic Alignment) — 高 = 对齐战略
4. 现金流稳定性 (Cashflow Stability) — 高 = 稳定

方法：
- 枚举候选方案
- 评估每个方案在 4 维目标上的得分
- 识别 Pareto 最优解（不存在另一个方案在所有维度都更优）
- 加权得分用于排序
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import math
import random

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.impact_assessment import ParetoFrontier, DecisionSandbox
from models.budget import BudgetItem
from models.strategic import StrategicInitiative


# 4 个目标权重（默认；可配置）
DEFAULT_WEIGHTS = {
    "budget_compliance": 0.30,
    "business_impact": 0.30,
    "strategic_alignment": 0.20,
    "cashflow_stability": 0.20,
}


class ParetoOptimizer:
    """Pareto 前沿优化引擎"""

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or DEFAULT_WEIGHTS

    async def optimize(
        self,
        candidates: List[Dict[str, Any]],
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """
        优化多个候选方案，返回 Pareto 前沿

        candidates 格式:
        [
            {
                "id": "方案1",
                "params": {...},
                "scores": {
                    "budget_compliance": 0-100,
                    "business_impact": 0-100,
                    "strategic_alignment": 0-100,
                    "cashflow_stability": 0-100,
                }
            },
            ...
        ]
        """
        if not candidates:
            return {"pareto_optimal": [], "ranked": [], "summary": {}}

        # 1. 评估每个候选
        evaluated = []
        for cand in candidates:
            scores = cand.get("scores", {})
            # 补全缺失维度
            scores = {
                "budget_compliance": scores.get("budget_compliance", 50),
                "business_impact": scores.get("business_impact", 50),
                "strategic_alignment": scores.get("strategic_alignment", 50),
                "cashflow_stability": scores.get("cashflow_stability", 50),
            }
            weighted_score = self._weighted_score(scores)
            evaluated.append({
                "id": cand.get("id", f"方案{len(evaluated)+1}"),
                "params": cand.get("params", {}),
                "scores": scores,
                "weighted_score": weighted_score,
            })

        # 2. 识别 Pareto 最优
        pareto_optimal = self._find_pareto_frontier(evaluated)

        # 3. 综合排序
        ranked = sorted(
            evaluated, key=lambda x: x["weighted_score"], reverse=True
        )
        for i, r in enumerate(ranked):
            r["rank"] = i + 1
            r["is_pareto_optimal"] = r in pareto_optimal

        # 4. 摘要
        summary = self._generate_summary(evaluated, pareto_optimal)

        # 5. 存储
        if db:
            for r in ranked:
                pf = ParetoFrontier(
                    objective_budget_compliance=r["scores"]["budget_compliance"],
                    objective_business_impact=r["scores"]["business_impact"],
                    objective_strategic_alignment=r["scores"]["strategic_alignment"],
                    objective_cashflow_stability=r["scores"]["cashflow_stability"],
                    is_pareto_optimal=r["is_pareto_optimal"],
                    rank=r["rank"],
                    solution_params=r["params"],
                )
                db.add(pf)
            await db.flush()

        return {
            "pareto_optimal": [r for r in ranked if r["is_pareto_optimal"]],
            "ranked": ranked,
            "summary": summary,
            "weights": self.weights,
        }

    def _weighted_score(self, scores: Dict[str, float]) -> float:
        """加权综合得分"""
        return round(
            scores["budget_compliance"] * self.weights["budget_compliance"]
            + scores["business_impact"] * self.weights["business_impact"]
            + scores["strategic_alignment"] * self.weights["strategic_alignment"]
            + scores["cashflow_stability"] * self.weights["cashflow_stability"],
            2,
        )

    def _find_pareto_frontier(
        self, evaluated: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """识别 Pareto 前沿"""
        pareto = []
        for i, cand in enumerate(evaluated):
            dominated = False
            cand_scores = cand["scores"]
            for j, other in enumerate(evaluated):
                if i == j:
                    continue
                other_scores = other["scores"]
                # 支配判定：other 在所有维度 >= cand，且至少一个维度 >
                if self._dominates(other_scores, cand_scores):
                    dominated = True
                    break
            if not dominated:
                pareto.append(cand)
        return pareto

    @staticmethod
    def _dominates(a: Dict[str, float], b: Dict[str, float]) -> bool:
        """a 是否支配 b（4 目标都 >= 且至少一个 >）"""
        at_least_one_better = False
        for dim in ("budget_compliance", "business_impact",
                    "strategic_alignment", "cashflow_stability"):
            if a[dim] < b[dim]:
                return False
            if a[dim] > b[dim]:
                at_least_one_better = True
        return at_least_one_better

    def _generate_summary(
        self,
        evaluated: List[Dict[str, Any]],
        pareto: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """生成摘要"""
        if not evaluated:
            return {}
        avg_scores = {
            dim: round(
                sum(e["scores"][dim] for e in evaluated) / len(evaluated), 2
            )
            for dim in ("budget_compliance", "business_impact",
                        "strategic_alignment", "cashflow_stability")
        }
        return {
            "total_candidates": len(evaluated),
            "pareto_optimal_count": len(pareto),
            "avg_scores": avg_scores,
            "best_weighted": max(e["weighted_score"] for e in evaluated),
            "worst_weighted": min(e["weighted_score"] for e in evaluated),
        }

    # ═══════════════════════════════════════════════════════════
    # 自动生成候选方案
    # ═══════════════════════════════════════════════════════════

    async def auto_candidates_from_budget_change(
        self,
        budget_id: str,
        original_amount: float,
        db: Optional[AsyncSession] = None,
    ) -> List[Dict[str, Any]]:
        """从预算变更自动生成候选方案"""
        # 几种典型调整方案
        adjustment_pcts = [-0.30, -0.15, -0.05, 0, 0.05, 0.15, 0.30]
        candidates = []
        for pct in adjustment_pcts:
            new_amount = original_amount * (1 + pct)
            candidates.append({
                "id": f"调整{pct*100:+.0f}%",
                "params": {
                    "budget_id": budget_id,
                    "original_amount": original_amount,
                    "new_amount": new_amount,
                    "adjustment_pct": pct,
                },
                "scores": {
                    # 减少预算：合规↑ 影响↓ 战略↓ 现金流↑
                    # 增加预算：合规↓ 影响↑ 战略↑ 现金流↓
                    "budget_compliance": self._compliance_score(pct),
                    "business_impact": self._impact_score(pct),
                    "strategic_alignment": self._strategic_score(pct),
                    "cashflow_stability": self._cashflow_score(pct),
                },
            })
        return candidates

    @staticmethod
    def _compliance_score(adjustment_pct: float) -> float:
        """预算合规度：减少→高，过度增加→低"""
        if adjustment_pct < 0:
            return min(100, 80 + abs(adjustment_pct) * 50)
        if adjustment_pct == 0:
            return 70
        return max(40, 70 - adjustment_pct * 80)

    @staticmethod
    def _impact_score(adjustment_pct: float) -> float:
        """业务影响度：适度增加→高"""
        if adjustment_pct > 0.10:
            return 85
        if adjustment_pct > 0:
            return 70
        if adjustment_pct == 0:
            return 60
        if adjustment_pct > -0.10:
            return 50
        return max(20, 40 + adjustment_pct * 100)

    @staticmethod
    def _strategic_score(adjustment_pct: float) -> float:
        """战略对齐度：增加投资→对齐"""
        if adjustment_pct >= 0:
            return min(95, 60 + adjustment_pct * 100)
        return max(30, 60 + adjustment_pct * 80)

    @staticmethod
    def _cashflow_score(adjustment_pct: float) -> float:
        """现金流稳定性：减少→释放现金→稳定"""
        if adjustment_pct < 0:
            return min(95, 70 + abs(adjustment_pct) * 80)
        if adjustment_pct == 0:
            return 65
        return max(35, 65 - adjustment_pct * 100)

    async def get_pareto_history(
        self, db: AsyncSession, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """获取历史 Pareto 优化记录"""
        stmt = select(ParetoFrontier).order_by(
            ParetoFrontier.created_at.desc()
        ).limit(limit)
        result = await db.execute(stmt)
        records = result.scalars().all()
        return [
            {
                "id": r.id,
                "scores": {
                    "budget_compliance": r.objective_budget_compliance,
                    "business_impact": r.objective_business_impact,
                    "strategic_alignment": r.objective_strategic_alignment,
                    "cashflow_stability": r.objective_cashflow_stability,
                },
                "is_pareto_optimal": r.is_pareto_optimal,
                "rank": r.rank,
                "params": r.solution_params,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ]
