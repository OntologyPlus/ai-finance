"""
预算消耗预测引擎 — 线性外推 + 季节性
按经营分析方法论 §4.5 实施：基于近 3-6 月节奏，预测本月/季度/年度消耗
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.budget import BudgetItem
from models.expense import ExpenseReport


# 季节因子（按月）
SEASONAL_FACTORS = {
    1: 0.85,   # 1 月（春节）
    2: 0.80,   # 2 月
    3: 1.10,   # 3 月（季末冲量）
    4: 0.95,
    5: 1.00,
    6: 1.10,   # 6 月（半年冲量）
    7: 0.95,
    8: 0.95,
    9: 1.10,   # 9 月（季末）
    10: 1.00,
    11: 1.00,
    12: 1.20,  # 12 月（年末冲量）
}


class BudgetBurnPredictor:
    """预算消耗预测器：线性外推 + 季节性调整"""

    def __init__(self):
        self.engine_name = "budget_burn_predictor"

    @staticmethod
    def _linear_regression(xs: List[float], ys: List[float]) -> Tuple[float, float]:
        """最小二乘线性回归
        Returns: (slope, intercept)
        """
        n = len(xs)
        if n < 2 or not ys:
            return 0.0, ys[0] if ys else 0.0
        x_mean = sum(xs) / n
        y_mean = sum(ys) / n
        num = sum((xs[i] - x_mean) * (ys[i] - y_mean) for i in range(n))
        den = sum((xs[i] - x_mean) ** 2 for i in range(n))
        if den == 0:
            return 0.0, y_mean
        slope = num / den
        intercept = y_mean - slope * x_mean
        return slope, intercept

    @staticmethod
    def _confidence(mape: float) -> str:
        """基于 MAPE 评估预测置信度
        - MAPE < 10% → high
        - 10-20% → medium
        - 20-30% → low
        - > 30% → very_low
        """
        if mape < 0.10:
            return "high"
        if mape < 0.20:
            return "medium"
        if mape < 0.30:
            return "low"
        return "very_low"

    async def fetch_monthly_consumption(
        self,
        db: AsyncSession,
        budget_id: str,
        months: int = 6,
    ) -> List[Dict[str, Any]]:
        """拉取近 N 月的预算消耗（核销金额）
        Returns: [{"period": "2024-01", "amount": 1000.0}, ...]
        """
        # MySQL: DATE_FORMAT；SQLite: strftime。统一使用 MySQL 语法（生产库为 MySQL）
        from sqlalchemy import text
        stmt = select(
            func.date_format(ExpenseReport.created_at, "%Y-%m").label("period"),
            func.sum(ExpenseReport.amount).label("amount"),
        ).where(and_(
            ExpenseReport.budget_id == budget_id,
            ExpenseReport.status.in_(["已审批", "已核销"]),
        )).group_by(text("period")).order_by(text("period")).limit(months)
        result = await db.execute(stmt)
        rows = result.all()
        return [{"period": r[0], "amount": float(r[1] or 0)} for r in rows]

    async def predict_full_year(
        self,
        db: AsyncSession,
        budget_id: str,
    ) -> Dict[str, Any]:
        """预测全年消耗
        Returns:
        - history: 历史消耗
        - linear_forecast: 线性外推预测值
        - seasonal_adjusted: 季节性调整后预测值
        - mape: 平均绝对百分比误差
        - confidence: high/medium/low/very_low
        - is_at_risk: 预测值 > 预算 * 90% 时为 True
        """
        history = await self.fetch_monthly_consumption(db, budget_id, months=6)
        if not history:
            return {
                "budget_id": budget_id,
                "history": [],
                "linear_forecast": 0.0,
                "seasonal_adjusted": 0.0,
                "mape": 1.0,
                "confidence": "very_low",
                "is_at_risk": False,
                "warning": "无历史消耗数据",
            }

        # 拉取预算总额
        stmt = select(BudgetItem).where(BudgetItem.budget_id == budget_id)
        result = await db.execute(stmt)
        budget = result.scalar_one_or_none()
        if not budget:
            return {"budget_id": budget_id, "error": f"预算项 {budget_id} 不存在"}
        annual_amount = float(budget.annual_amount or 0)

        # 线性回归
        xs = [float(i) for i in range(len(history))]
        ys = [h["amount"] for h in history]
        slope, intercept = self._linear_regression(xs, ys)

        # 外推到 12 月
        linear_full_year = sum(intercept + slope * x for x in range(12))

        # 季节性调整（按当前期间所属月份加权）
        cur_month = datetime.now().month
        season_full = sum(
            (intercept + slope * x) * SEASONAL_FACTORS.get(((cur_month - 1 + x) % 12) + 1, 1.0)
            for x in range(12)
        )

        # 计算 MAPE
        mape_sum = 0.0
        mape_count = 0
        for i, h in enumerate(history):
            predicted = intercept + slope * i
            actual = h["amount"]
            if actual > 0:
                mape_sum += abs(predicted - actual) / actual
                mape_count += 1
        mape = mape_sum / max(mape_count, 1)

        # 本月已消耗
        cur_consumed = ys[-1] if ys else 0.0
        # 预测本月剩余 = max(0, predicted - cur_consumed)
        cur_predicted_full = intercept + slope * (len(history) - 1)
        cur_remaining = max(0, cur_predicted_full - cur_consumed)

        is_at_risk = season_full > annual_amount * 0.9

        return {
            "budget_id": budget_id,
            "annual_amount": annual_amount,
            "history": history,
            "current_consumed": round(cur_consumed, 2),
            "current_predicted_full": round(cur_predicted_full, 2),
            "current_remaining": round(cur_remaining, 2),
            "linear_forecast": round(linear_full_year, 2),
            "seasonal_adjusted": round(season_full, 2),
            "seasonal_factor_avg": round(season_full / max(linear_full_year, 1), 2),
            "mape": round(mape, 4),
            "confidence": self._confidence(mape),
            "is_at_risk": is_at_risk,
            "risk_level": "high" if season_full > annual_amount else "medium" if season_full > annual_amount * 0.8 else "low",
            "trend": "increasing" if slope > 0 else "decreasing" if slope < 0 else "stable",
        }

    async def predict_budget_runway(
        self,
        db: AsyncSession,
        budget_id: str,
    ) -> Dict[str, Any]:
        """预测预算跑道（按当前消耗速度，预算还能撑几个月）"""
        history = await self.fetch_monthly_consumption(db, budget_id, months=6)
        if not history:
            return {
                "budget_id": budget_id,
                "runway_months": None,
                "warning": "无历史消耗数据",
            }

        stmt = select(BudgetItem).where(BudgetItem.budget_id == budget_id)
        result = await db.execute(stmt)
        budget = result.scalar_one_or_none()
        if not budget:
            return {"budget_id": budget_id, "error": f"预算项 {budget_id} 不存在"}
        annual_amount = float(budget.annual_amount or 0)
        used = float(budget.used_amount or 0)
        available = annual_amount - used

        # 平均月消耗
        avg_monthly = sum(h["amount"] for h in history) / len(history)
        if avg_monthly <= 0:
            return {
                "budget_id": budget_id,
                "runway_months": float("inf"),
                "avg_monthly": 0.0,
                "warning": "近 6 月无消耗",
            }

        runway = available / avg_monthly
        return {
            "budget_id": budget_id,
            "annual_amount": annual_amount,
            "used": used,
            "available": available,
            "avg_monthly": round(avg_monthly, 2),
            "runway_months": round(runway, 2),
            "risk_level": "high" if runway < 1 else "medium" if runway < 3 else "low",
        }

    async def batch_predict(
        self,
        db: AsyncSession,
        period: str,
        center_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """批量预测：本期所有预算项的全年消耗 + 跑道"""
        stmt = select(BudgetItem)
        if center_id:
            stmt = stmt.where(BudgetItem.center_id == center_id)
        result = await db.execute(stmt)
        budgets = result.scalars().all()

        predictions = []
        for budget in budgets:
            pred = await self.predict_full_year(db, budget.budget_id)
            runway = await self.predict_budget_runway(db, budget.budget_id)
            predictions.append({
                "budget_id": budget.budget_id,
                "center_id": getattr(budget, "center_id", None),
                "l1_code": getattr(budget, "l1_code", None),
                **pred,
                "runway": runway,
            })

        # 排序：按风险等级
        risk_order = {"high": 0, "medium": 1, "low": 2}
        predictions.sort(key=lambda x: (risk_order.get(x.get("risk_level", "low"), 3), -x.get("seasonal_adjusted", 0)))

        at_risk_count = sum(1 for p in predictions if p.get("is_at_risk"))

        return {
            "period": period,
            "center_id": center_id,
            "total_budgets": len(predictions),
            "at_risk_count": at_risk_count,
            "predictions": predictions,
        }
