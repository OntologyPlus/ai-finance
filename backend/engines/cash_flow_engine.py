from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.cash_flow import CashFlowPlan, CashPool, PaymentSchedule, ReceiptForecast
from models.budget import BudgetItem
from models.expense import ExpenseReport


class CashFlowEngine:
    """现金流双线监控引擎 — 利润线+现金流线双轮驱动"""

    async def forecast_cash_flow(
        self, period: str, horizon_months: int = 3, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """现金流预测：基于收入预算+支出预算+历史付款模式"""
        if db is None:
            return {"error": "数据库连接不可用"}

        results = []
        for m in range(horizon_months):
            year, month = self._parse_period(period)
            target_month = month + m
            target_year = year + (target_month - 1) // 12
            target_month = (target_month - 1) % 12 + 1
            target_period = f"{target_year}-{target_month:02d}"

            # 经营活动
            operating_inflow = await self._estimate_operating_inflow(target_period, db)
            operating_outflow = await self._estimate_operating_outflow(target_period, db)

            # 投资活动（简化：基于历史平均）
            investing_inflow = 0.0
            investing_outflow = await self._estimate_investing_outflow(target_period, db)

            # 筹资活动（简化：基于历史平均）
            financing_inflow = 0.0
            financing_outflow = 0.0

            total_inflow = operating_inflow + investing_inflow + financing_inflow
            total_outflow = operating_outflow + investing_outflow + financing_outflow
            net = total_inflow - total_outflow

            results.append({
                "period": target_period,
                "operating": {"inflow": operating_inflow, "outflow": operating_outflow, "net": operating_inflow - operating_outflow},
                "investing": {"inflow": investing_inflow, "outflow": investing_outflow, "net": investing_inflow - investing_outflow},
                "financing": {"inflow": financing_inflow, "outflow": financing_outflow, "net": financing_inflow - financing_outflow},
                "total_inflow": total_inflow, "total_outflow": total_outflow, "net": net,
            })

        return {"period": period, "horizon_months": horizon_months, "forecasts": results}

    async def check_liquidity_gap(self, period: str, db: AsyncSession = None) -> Dict[str, Any]:
        """流动性缺口检查"""
        forecast = await self.forecast_cash_flow(period, horizon_months=3, db=db)
        if "error" in forecast:
            return forecast

        gaps = []
        for fc in forecast.get("forecasts", []):
            if fc["net"] < 0:
                gaps.append({"period": fc["period"], "gap_amount": abs(fc["net"]), "severity": "高" if abs(fc["net"]) > 1000000 else "中"})

        # 检查资金池余额
        pool_balance = await self._get_pool_balance(db)
        total_gap = sum(g["gap_amount"] for g in gaps)

        return {
            "period": period,
            "has_gap": len(gaps) > 0,
            "gaps": gaps,
            "pool_balance": pool_balance,
            "can_cover": pool_balance >= total_gap if pool_balance else False,
            "recommendation": "建议启动紧急调拨或延迟非紧急付款" if gaps else "流动性充足",
        }

    async def analyze_profit_cash_gap(self, period: str, db: AsyncSession = None) -> Dict[str, Any]:
        """利润vs现金流差异分析"""
        if db is None:
            return {"error": "数据库连接不可用"}

        # 利润（权责发生制）= 预算执行率 × 年度预算
        profit = await self._calculate_profit(period, db)

        # 现金流（收付实现制）
        forecast = await self.forecast_cash_flow(period, horizon_months=1, db=db)
        cash_flow = forecast.get("forecasts", [{}])[0].get("operating", {}).get("net", 0) if forecast.get("forecasts") else 0

        gap = profit - cash_flow

        # 分析差异来源
        sources = []
        if gap > 0:
            sources.append({"source": "应收账款", "description": "利润已确认但未收到现金", "estimated_amount": gap * 0.4})
            sources.append({"source": "折旧摊销", "description": "非现金支出减少利润但不影响现金流", "estimated_amount": gap * 0.3})
            sources.append({"source": "预付账款", "description": "已付款但未确认费用", "estimated_amount": gap * 0.2})
            sources.append({"source": "其他", "description": "其他差异", "estimated_amount": gap * 0.1})
        elif gap < 0:
            sources.append({"source": "预收账款", "description": "已收款但未确认收入", "estimated_amount": abs(gap) * 0.5})
            sources.append({"source": "应付账款", "description": "费用已发生但未付款", "estimated_amount": abs(gap) * 0.3})
            sources.append({"source": "其他", "description": "其他差异", "estimated_amount": abs(gap) * 0.2})

        return {
            "period": period,
            "profit": profit,
            "cash_flow": cash_flow,
            "gap": gap,
            "gap_ratio": gap / profit if profit != 0 else 0,
            "sources": sources,
            "interpretation": f"利润{profit:.0f}万元，经营性现金流{cash_flow:.0f}万元，差异{gap:.0f}万元" if profit else "数据不足",
        }

    async def match_receipt_payment(self, period: str, db: AsyncSession = None) -> Dict[str, Any]:
        """收支匹配分析"""
        if db is None:
            return {"error": "数据库连接不可用"}

        # 获取付款排期
        stmt = select(PaymentSchedule).where(
            PaymentSchedule.planned_date >= self._period_start(period),
            PaymentSchedule.planned_date < self._period_end(period),
        )
        result = await db.execute(stmt)
        payments = result.scalars().all()

        # 获取收款预测
        stmt2 = select(ReceiptForecast).where(
            ReceiptForecast.forecast_date >= self._period_start(period),
            ReceiptForecast.forecast_date < self._period_end(period),
        )
        result2 = await db.execute(stmt2)
        receipts = result2.scalars().all()

        total_payment = sum(p.planned_amount for p in payments)
        total_receipt = sum(r.forecast_amount for r in receipts)
        net = total_receipt - total_payment

        # 按周分析收支时间差
        weekly_analysis = self._weekly_receipt_payment_analysis(payments, receipts, period)

        return {
            "period": period,
            "total_payment": total_payment,
            "total_receipt": total_receipt,
            "net": net,
            "payment_count": len(payments),
            "receipt_count": len(receipts),
            "weekly_analysis": weekly_analysis,
            "risk_windows": [w for w in weekly_analysis if w["net"] < 0],
        }

    # === 辅助方法 ===

    def _parse_period(self, period: str) -> Tuple[int, int]:
        parts = period.split("-")
        return int(parts[0]), int(parts[1]) if len(parts) > 1 else 1

    def _period_start(self, period: str) -> datetime:
        year, month = self._parse_period(period)
        return datetime(year, month, 1)

    def _period_end(self, period: str) -> datetime:
        year, month = self._parse_period(period)
        if month == 12:
            return datetime(year + 1, 1, 1)
        return datetime(year, month + 1, 1)

    async def _estimate_operating_inflow(self, period: str, db: AsyncSession) -> float:
        """估算经营活动流入（基于历史收款模式）"""
        # 简化：基于预算项目的可用额度估算
        try:
            stmt = select(func.sum(BudgetItem.available_amount)).where(BudgetItem.status == "执行中")
            result = await db.execute(stmt)
            total = result.scalar() or 0
            return float(total) * 0.08  # 假设月度收入约为可用额度的8%
        except Exception:
            return 0.0

    async def _estimate_operating_outflow(self, period: str, db: AsyncSession) -> float:
        """估算经营活动流出（基于待付款报销单）"""
        try:
            stmt = select(func.sum(ExpenseReport.amount)).where(ExpenseReport.status == "已审批")
            result = await db.execute(stmt)
            total = result.scalar() or 0
            return float(total) * 0.7  # 70%的已审批报销会在当月付款
        except Exception:
            return 0.0

    async def _estimate_investing_outflow(self, period: str, db: AsyncSession) -> float:
        """估算投资活动流出"""
        try:
            stmt = select(func.sum(BudgetItem.annual_amount)).where(
                BudgetItem.l1_code == "B8",  # B8=资本性支出
                BudgetItem.status == "执行中",
            )
            result = await db.execute(stmt)
            total = result.scalar() or 0
            return float(total) / 12  # 月度平均
        except Exception:
            return 0.0

    async def _get_pool_balance(self, db: AsyncSession) -> float:
        """获取资金池余额"""
        try:
            stmt = select(CashPool.total_balance).limit(1)
            result = await db.execute(stmt)
            balance = result.scalar()
            return float(balance) if balance else 0.0
        except Exception:
            return 0.0

    async def _calculate_profit(self, period: str, db: AsyncSession) -> float:
        """计算利润（简化：预算执行差异）"""
        try:
            stmt = select(
                func.sum(BudgetItem.annual_amount),
                func.sum(BudgetItem.used_amount),
            ).where(BudgetItem.status == "执行中")
            result = await db.execute(stmt)
            annual, used = result.one()
            if annual and used:
                monthly_budget = float(annual) / 12
                monthly_used = float(used) / 12
                return monthly_budget - monthly_used  # 简化利润 = 预算-实际
            return 0.0
        except Exception:
            return 0.0

    def _weekly_receipt_payment_analysis(self, payments, receipts, period: str) -> List[Dict]:
        """按周分析收支"""
        weeks = []
        year, month = self._parse_period(period)
        for week in range(4):
            start_day = week * 7 + 1
            end_day = min((week + 1) * 7, 28)
            week_start = datetime(year, month, start_day)
            week_end = datetime(year, month, end_day)

            week_payment = sum(p.planned_amount for p in payments if p.planned_date and week_start <= p.planned_date <= week_end)
            week_receipt = sum(r.forecast_amount for r in receipts if r.forecast_date and week_start <= r.forecast_date <= week_end)

            weeks.append({
                "week": week + 1,
                "payment": week_payment,
                "receipt": week_receipt,
                "net": week_receipt - week_payment,
            })
        return weeks
