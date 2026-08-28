"""
现金流账龄分析引擎（AR/AP Aging）

按《经营分析方法论.md》§3.1 信号灯机制 + §4.2 现金流分析实现：
- 应收账款（AR）账龄 4 段分析：0-30/31-60/61-90/90+ 天
- 应付账款（AP）账龄 4 段分析：0-30/31-60/61-90/90+ 天
- 加权平均账龄（WAA）
- 坏账风险评估（90+ 占比 > 20% 为高风险）
- 9 卡 cashflow_quality 联动（账龄异常 → 信号灯转红）
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.cash_flow import PaymentSchedule, ReceiptForecast


class AgingBucket(str, Enum):
    """账龄 4 段（按方法论 §4.2）"""
    BUCKET_0_30 = "0-30"   # 健康
    BUCKET_31_60 = "31-60"  # 关注
    BUCKET_61_90 = "61-90"  # 风险
    BUCKET_90_PLUS = "90+"  # 严重风险


# 各段健康度判定阈值
HEALTH_THRESHOLDS = {
    "green": {"high_risk_pct_max": 0.05, "waa_days_max": 30},
    "yellow": {"high_risk_pct_max": 0.20, "waa_days_max": 60},
    "red": {"high_risk_pct_max": 1.01, "waa_days_max": 365},
}


@dataclass
class AgingReport:
    """账龄分析报告"""
    as_of_date: str
    total_amount: float
    total_count: int
    buckets: Dict[str, Dict[str, Any]]  # {bucket: {amount, count, pct, items}}
    weighted_avg_age_days: float
    high_risk_pct: float                # 90+ 占比
    signal_light: str                    # green/yellow/red
    light_reason: str
    bad_debt_risk_amount: float          # 90+ 金额
    top_overdue_items: List[Dict[str, Any]]  # Top N 逾期明细

    def to_dict(self) -> Dict[str, Any]:
        return {
            "as_of_date": self.as_of_date,
            "total_amount": round(self.total_amount, 2),
            "total_count": self.total_count,
            "buckets": {
                k: {
                    "amount": round(v["amount"], 2),
                    "count": v["count"],
                    "pct": round(v["pct"] * 100, 2),
                    "items": v.get("items", [])[:5],  # 每段只保留前 5 条
                }
                for k, v in self.buckets.items()
            },
            "weighted_avg_age_days": round(self.weighted_avg_age_days, 1),
            "high_risk_pct": round(self.high_risk_pct * 100, 2),
            "signal_light": self.signal_light,
            "light_reason": self.light_reason,
            "bad_debt_risk_amount": round(self.bad_debt_risk_amount, 2),
            "top_overdue_items": self.top_overdue_items[:10],
        }


class CashflowAgingEngine:
    """现金流账龄分析引擎（AR/AP Aging）

    设计目标：
    - 替换原 cash_flow_engine.py 的简化算法
    - 真实消费 ReceiptForecast（应收）/ PaymentSchedule（应付）
    - 输出方法论级账龄分析（4 段 + WAA + 信号灯）
    """

    def __init__(self) -> None:
        self.today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # ────── 应收账款（AR）账龄 ──────

    async def analyze_receivable_aging(
        self, db: AsyncSession, as_of: Optional[datetime] = None
    ) -> AgingReport:
        """AR 账龄分析（基于 ReceiptForecast）"""
        as_of = as_of or self.today
        # 仅取未收回的预测（actual_date 为空）
        stmt = select(ReceiptForecast).where(ReceiptForecast.actual_date.is_(None))
        result = await db.execute(stmt)
        rows = result.scalars().all()
        return self._build_aging_report(
            rows, as_of, kind="AR",
            date_attr="forecast_date", amount_attr="forecast_amount",
        )

    # ────── 应付账款（AP）账龄 ──────

    async def analyze_payable_aging(
        self, db: AsyncSession, as_of: Optional[datetime] = None
    ) -> AgingReport:
        """AP 账龄分析（基于 PaymentSchedule）"""
        as_of = as_of or self.today
        # 仅取未付款的计划
        stmt = select(PaymentSchedule).where(PaymentSchedule.actual_date.is_(None))
        result = await db.execute(stmt)
        rows = result.scalars().all()
        return self._build_aging_report(
            rows, as_of, kind="AP",
            date_attr="planned_date", amount_attr="planned_amount",
        )

    # ────── 核心：构建账龄报告 ──────

    def _build_aging_report(
        self,
        rows: List,
        as_of: datetime,
        kind: str,
        date_attr: str,
        amount_attr: str,
    ) -> AgingReport:
        """通用账龄报告构建（4 段 + WAA + 信号灯）"""
        buckets: Dict[str, Dict[str, Any]] = {
            AgingBucket.BUCKET_0_30.value: {"amount": 0.0, "count": 0, "pct": 0.0, "items": []},
            AgingBucket.BUCKET_31_60.value: {"amount": 0.0, "count": 0, "pct": 0.0, "items": []},
            AgingBucket.BUCKET_61_90.value: {"amount": 0.0, "count": 0, "pct": 0.0, "items": []},
            AgingBucket.BUCKET_90_PLUS.value: {"amount": 0.0, "count": 0, "pct": 0.0, "items": []},
        }
        total_amount = 0.0
        total_weighted_age = 0.0  # 用于 WAA 计算
        overdue_items: List[Dict[str, Any]] = []

        for row in rows:
            row_date = getattr(row, date_attr)
            amount = getattr(row, amount_attr) or 0.0
            if not row_date or amount <= 0:
                continue
            # 账龄天数 = 当前 - 计划日（AR 取 forecast_date, AP 取 planned_date）
            age_days = (as_of - row_date).days
            if age_days < 0:
                bucket_key = AgingBucket.BUCKET_0_30.value  # 未到期
            elif age_days <= 30:
                bucket_key = AgingBucket.BUCKET_0_30.value
            elif age_days <= 60:
                bucket_key = AgingBucket.BUCKET_31_60.value
            elif age_days <= 90:
                bucket_key = AgingBucket.BUCKET_61_90.value
            else:
                bucket_key = AgingBucket.BUCKET_90_PLUS.value

            buckets[bucket_key]["amount"] += amount
            buckets[bucket_key]["count"] += 1
            total_amount += amount
            total_weighted_age += age_days * amount

            item = {
                "id": row.id,
                "name": getattr(row, "customer_name", None) or getattr(row, "vendor_name", None) or f"#{row.id}",
                "amount": round(amount, 2),
                "age_days": age_days,
                "date": row_date.strftime("%Y-%m-%d"),
                "kind": kind,
            }
            buckets[bucket_key]["items"].append(item)
            if age_days > 30:  # 逾期明细
                overdue_items.append(item)

        # 计算占比
        for b in buckets.values():
            b["pct"] = (b["amount"] / total_amount) if total_amount > 0 else 0.0
            b["items"].sort(key=lambda x: -x["amount"])

        waa_days = (total_weighted_age / total_amount) if total_amount > 0 else 0.0
        high_risk_amount = buckets[AgingBucket.BUCKET_90_PLUS.value]["amount"]
        high_risk_pct = (high_risk_amount / total_amount) if total_amount > 0 else 0.0

        # 信号灯判定（按方法论 §3.1）
        if (
            high_risk_pct <= HEALTH_THRESHOLDS["green"]["high_risk_pct_max"]
            and waa_days <= HEALTH_THRESHOLDS["green"]["waa_days_max"]
        ):
            signal_light = "green"
            light_reason = f"高风险(90+)占比 {high_risk_pct*100:.1f}% ≤ 5% 且加权账龄 {waa_days:.0f}天 ≤ 30天"
        elif (
            high_risk_pct <= HEALTH_THRESHOLDS["yellow"]["high_risk_pct_max"]
            and waa_days <= HEALTH_THRESHOLDS["yellow"]["waa_days_max"]
        ):
            signal_light = "yellow"
            light_reason = f"高风险(90+)占比 {high_risk_pct*100:.1f}% 或加权账龄 {waa_days:.0f}天 处于关注区"
        else:
            signal_light = "red"
            light_reason = (
                f"高风险(90+)占比 {high_risk_pct*100:.1f}% > 20% 或 "
                f"加权账龄 {waa_days:.0f}天 > 60天，提示严重{kind}风险"
            )

        overdue_items.sort(key=lambda x: -x["amount"])
        return AgingReport(
            as_of_date=as_of.strftime("%Y-%m-%d"),
            total_amount=total_amount,
            total_count=len(rows),
            buckets=buckets,
            weighted_avg_age_days=waa_days,
            high_risk_pct=high_risk_pct,
            signal_light=signal_light,
            light_reason=light_reason,
            bad_debt_risk_amount=high_risk_amount,
            top_overdue_items=overdue_items,
        )
