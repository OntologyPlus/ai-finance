"""
12 周滚动现金流预测引擎

按《经营分析方法论.md》§4.2 现金流分析 + §3.1 信号灯机制实现：
- 12 周滚动预测（消费 PaymentSchedule/ReceiptForecast）
- 现金池覆盖率健康度（>= 6 月绿，3-6 黄，< 3 红）
- 缺口预警 + 主动建议联动（critical liquidity gap）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.cash_flow import CashPool, PaymentSchedule, ReceiptForecast


@dataclass
class WeeklyCashflow:
    """单周现金流预测"""
    week: int
    week_start: str
    week_end: str
    planned_inflow: float
    planned_outflow: float
    net: float
    running_balance: float  # 滚动余额
    source_inflow_count: int
    source_outflow_count: int
    signal: str  # ok / warn / critical


@dataclass
class LiquidityHealth:
    """流动性健康度评分"""
    cash_pool_total: float
    monthly_avg_outflow: float
    coverage_months: float
    signal_light: str  # green / yellow / red
    light_reason: str
    recommendation: str


@dataclass
class LiquidityGap:
    """流动性缺口预警"""
    week: int
    week_start: str
    week_end: str
    gap_amount: float
    severity: str  # low / medium / high / critical
    cumulative_gap: float
    suggested_action: str


@dataclass
class RollingForecastReport:
    """12 周滚动预测报告"""
    as_of_date: str
    horizon_weeks: int
    initial_balance: float
    weekly_forecasts: List[WeeklyCashflow]
    total_inflow: float
    total_outflow: float
    final_balance: float
    liquidity_health: LiquidityHealth
    gaps: List[LiquidityGap]
    min_balance: float
    min_balance_week: int
    signal_light: str  # green / yellow / red
    light_reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "as_of_date": self.as_of_date,
            "horizon_weeks": self.horizon_weeks,
            "initial_balance": round(self.initial_balance, 2),
            "weekly_forecasts": [
                {
                    "week": w.week,
                    "week_start": w.week_start,
                    "week_end": w.week_end,
                    "planned_inflow": round(w.planned_inflow, 2),
                    "planned_outflow": round(w.planned_outflow, 2),
                    "net": round(w.net, 2),
                    "running_balance": round(w.running_balance, 2),
                    "source_inflow_count": w.source_inflow_count,
                    "source_outflow_count": w.source_outflow_count,
                    "signal": w.signal,
                }
                for w in self.weekly_forecasts
            ],
            "total_inflow": round(self.total_inflow, 2),
            "total_outflow": round(self.total_outflow, 2),
            "final_balance": round(self.final_balance, 2),
            "liquidity_health": {
                "cash_pool_total": round(self.liquidity_health.cash_pool_total, 2),
                "monthly_avg_outflow": round(self.liquidity_health.monthly_avg_outflow, 2),
                "coverage_months": round(self.liquidity_health.coverage_months, 2),
                "signal_light": self.liquidity_health.signal_light,
                "light_reason": self.liquidity_health.light_reason,
                "recommendation": self.liquidity_health.recommendation,
            },
            "gaps": [
                {
                    "week": g.week,
                    "week_start": g.week_start,
                    "week_end": g.week_end,
                    "gap_amount": round(g.gap_amount, 2),
                    "severity": g.severity,
                    "cumulative_gap": round(g.cumulative_gap, 2),
                    "suggested_action": g.suggested_action,
                }
                for g in self.gaps
            ],
            "min_balance": round(self.min_balance, 2),
            "min_balance_week": self.min_balance_week,
            "signal_light": self.signal_light,
            "light_reason": self.light_reason,
        }


class CashflowForecastEngine:
    """12 周滚动现金流预测引擎

    设计目标：
    - 替换原 cash_flow_engine.py 中的简化 _estimate_* 方法
    - 真实消费 ReceiptForecast/PaymentSchedule
    - 输出周度滚动预测 + 流动性健康度 + 缺口预警
    - 主动建议联动（critical gap → ProactiveAdvisor）
    """

    DEFAULT_HORIZON_WEEKS = 12
    LIQUIDITY_GREEN_MONTHS = 6.0
    LIQUIDITY_YELLOW_MONTHS = 3.0

    def __init__(self) -> None:
        self.today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        # 本周一（周一为周开始）
        self.week_start = self.today - timedelta(days=self.today.weekday())

    # ────── 核心入口：12 周滚动预测 ──────

    async def rolling_forecast(
        self,
        db: AsyncSession,
        horizon_weeks: int = DEFAULT_HORIZON_WEEKS,
        initial_balance: Optional[float] = None,
    ) -> RollingForecastReport:
        """12 周滚动现金流预测

        Args:
            db: 异步数据库会话
            horizon_weeks: 预测周数（默认 12）
            initial_balance: 初始现金池余额（None 则从 DB 读取）

        Returns:
            RollingForecastReport 周度预测 + 健康度 + 缺口
        """
        if initial_balance is None:
            initial_balance = await self._get_pool_balance(db)

        # 拉取所有未来 N 周的付款计划和回款预测
        horizon_end = self.week_start + timedelta(weeks=horizon_weeks)
        payments = await self._fetch_payments(db, self.week_start, horizon_end)
        receipts = await self._fetch_receipts(db, self.week_start, horizon_end)

        # 按周聚合
        weekly_forecasts: List[WeeklyCashflow] = []
        running = initial_balance
        total_inflow = 0.0
        total_outflow = 0.0
        min_balance = initial_balance
        min_balance_week = 0
        gaps: List[ LiquidityGap] = []
        cumulative_gap = 0.0

        for w in range(horizon_weeks):
            wk_start = self.week_start + timedelta(weeks=w)
            wk_end = wk_start + timedelta(days=6)
            wk_in = sum(
                r.forecast_amount for r in receipts
                if r.forecast_date and wk_start <= r.forecast_date <= wk_end
            )
            wk_out = sum(
                p.planned_amount for p in payments
                if p.planned_date and wk_start <= p.planned_date <= wk_end
            )
            wk_in_count = sum(
                1 for r in receipts
                if r.forecast_date and wk_start <= r.forecast_date <= wk_end
            )
            wk_out_count = sum(
                1 for p in payments
                if p.planned_date and wk_start <= p.planned_date <= wk_end
            )
            net = wk_in - wk_out
            running += net
            total_inflow += wk_in
            total_outflow += wk_out

            # 周度信号
            if running < 0:
                wk_signal = "critical"
            elif running < initial_balance * 0.3:
                wk_signal = "warn"
            else:
                wk_signal = "ok"

            # 缺口检测（running < 0 或低于阈值）
            if running < 0:
                gap_amount = abs(running)
                cumulative_gap += gap_amount
                severity = "critical" if gap_amount > initial_balance * 0.5 else "high"
                suggested = self._suggest_action_for_gap(gap_amount, w, horizon_weeks)
                gaps.append(LiquidityGap(
                    week=w + 1,
                    week_start=wk_start.strftime("%Y-%m-%d"),
                    week_end=wk_end.strftime("%Y-%m-%d"),
                    gap_amount=gap_amount,
                    severity=severity,
                    cumulative_gap=cumulative_gap,
                    suggested_action=suggested,
                ))

            if running < min_balance:
                min_balance = running
                min_balance_week = w + 1

            weekly_forecasts.append(WeeklyCashflow(
                week=w + 1,
                week_start=wk_start.strftime("%Y-%m-%d"),
                week_end=wk_end.strftime("%Y-%m-%d"),
                planned_inflow=wk_in,
                planned_outflow=wk_out,
                net=net,
                running_balance=running,
                source_inflow_count=wk_in_count,
                source_outflow_count=wk_out_count,
                signal=wk_signal,
            ))

        # 流动性健康度（按月均支出折算）
        monthly_avg_outflow = (total_outflow / horizon_weeks) * 4.33  # 周转月
        coverage_months = initial_balance / monthly_avg_outflow if monthly_avg_outflow > 0 else 99.0
        liquidity_health = self._build_liquidity_health(
            initial_balance, monthly_avg_outflow, coverage_months, gaps
        )

        # 整体信号灯
        if min_balance < 0:
            signal_light = "red"
            light_reason = f"第 {min_balance_week} 周余额跌至 {min_balance:.0f}（负值），现金流将断裂"
        elif liquidity_health.signal_light == "red":
            signal_light = "red"
            light_reason = liquidity_health.light_reason
        elif any(g.severity in ("high", "critical") for g in gaps):
            signal_light = "yellow"
            light_reason = f"未来 12 周内有 {sum(1 for g in gaps if g.severity in ('high','critical'))} 周高风险缺口"
        else:
            signal_light = "green"
            light_reason = f"未来 12 周最低余额 {min_balance:.0f}，流动性覆盖率 {coverage_months:.1f} 月"

        return RollingForecastReport(
            as_of_date=self.today.strftime("%Y-%m-%d"),
            horizon_weeks=horizon_weeks,
            initial_balance=initial_balance,
            weekly_forecasts=weekly_forecasts,
            total_inflow=total_inflow,
            total_outflow=total_outflow,
            final_balance=running,
            liquidity_health=liquidity_health,
            gaps=gaps,
            min_balance=min_balance,
            min_balance_week=min_balance_week,
            signal_light=signal_light,
            light_reason=light_reason,
        )

    # ────── 流动性健康度评估 ──────

    def _build_liquidity_health(
        self,
        cash_pool: float,
        monthly_outflow: float,
        coverage_months: float,
        gaps: List[LiquidityGap],
    ) -> LiquidityHealth:
        if coverage_months >= self.LIQUIDITY_GREEN_MONTHS and not gaps:
            signal = "green"
            reason = f"现金池覆盖 {coverage_months:.1f} 月支出 ≥ 6 月，流动性充裕"
            rec = "保持当前回款节奏，关注 60+ 天账龄"
        elif coverage_months >= self.LIQUIDITY_YELLOW_MONTHS:
            signal = "yellow"
            reason = f"现金池覆盖 {coverage_months:.1f} 月支出，处于关注区（3-6 月）"
            rec = "建议加大回款催收，延后非紧急付款"
        else:
            signal = "red"
            reason = f"现金池覆盖 {coverage_months:.1f} 月支出 < 3 月，存在断裂风险"
            rec = "紧急：启动融资/调拨/AR 催收三轨并进"
        return LiquidityHealth(
            cash_pool_total=cash_pool,
            monthly_avg_outflow=monthly_outflow,
            coverage_months=coverage_months,
            signal_light=signal,
            light_reason=reason,
            recommendation=rec,
        )

    def _suggest_action_for_gap(self, gap_amount: float, week: int, horizon: int) -> str:
        if gap_amount > 1_000_000:
            return f"紧急：第 {week+1} 周缺口 {gap_amount:,.0f}，建议立即启动融资或大额资金调拨"
        elif gap_amount > 100_000:
            return f"建议：第 {week+1} 周缺口 {gap_amount:,.0f}，优先催收 90+ 天应收账款"
        else:
            return f"建议：第 {week+1} 周小额缺口 {gap_amount:,.0f}，可延后非紧急付款"

    # ────── 数据访问 ──────

    async def _fetch_payments(
        self, db: AsyncSession, start: datetime, end: datetime
    ) -> List[PaymentSchedule]:
        stmt = select(PaymentSchedule).where(
            PaymentSchedule.planned_date >= start,
            PaymentSchedule.planned_date <= end,
            PaymentSchedule.actual_date.is_(None),  # 仅未付款
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def _fetch_receipts(
        self, db: AsyncSession, start: datetime, end: datetime
    ) -> List[ReceiptForecast]:
        stmt = select(ReceiptForecast).where(
            ReceiptForecast.forecast_date >= start,
            ReceiptForecast.forecast_date <= end,
            ReceiptForecast.actual_date.is_(None),
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def _get_pool_balance(self, db: AsyncSession) -> float:
        try:
            stmt = select(CashPool).where(CashPool.status == "活跃")
            result = await db.execute(stmt)
            pools = result.scalars().all()
            return sum(p.total_balance for p in pools) if pools else 0.0
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[forecast] get_pool_balance failed: {e}")
            return 0.0
