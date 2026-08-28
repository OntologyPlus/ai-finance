"""
费用异常检测引擎 — 单笔/群体/趋势三类异常识别
按经营分析方法论 §4.5 实施：Z-score + 群体偏离 + 趋势突增
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.expense import ExpenseReport


# 异常类型
ANOMALY_TYPES = (
    "single_amount",       # 单笔金额异常
    "single_category",     # 单笔品类异常
    "group_center",        # 群体中心异常
    "group_category",      # 群体品类异常
    "trend_period",        # 趋势突增（环比/同比）
    "frequency",           # 频次异常
    "timing",              # 时段异常（月末/季末突击）
    "duplicate_suspect",   # 疑似重复
)


class ExpenseAnomalyEngine:
    """费用异常检测引擎：单笔/群体/趋势 + 严重度评分"""

    def __init__(self):
        self.engine_name = "expense_anomaly"

    # ─── 单笔异常检测 ───────────────────────────────────────

    async def detect_single_anomaly(
        self,
        expense: ExpenseReport,
        historical: List[ExpenseReport],
        z_threshold: float = 2.0,
    ) -> List[Dict[str, Any]]:
        """单笔异常检测
        - 金额偏离：z-score vs 申请人历史金额分布
        - 品类偏离：本次 l1_code 是否为申请人历史常用
        - 时段异常：是否月末/季末/年末
        """
        anomalies: List[Dict[str, Any]] = []

        # 1) 金额偏离（z-score）
        if historical:
            amounts = [float(e.amount) for e in historical if e.amount]
            if len(amounts) >= 5:
                mean = statistics.mean(amounts)
                std = statistics.stdev(amounts) if len(amounts) > 1 else 0.0
                if std > 0:
                    z = (float(expense.amount) - mean) / std
                    if abs(z) >= z_threshold:
                        anomalies.append({
                            "type": "single_amount",
                            "severity": "high" if abs(z) >= 3.0 else "medium",
                            "z_score": round(z, 2),
                            "amount": float(expense.amount),
                            "mean_amount": round(mean, 2),
                            "std_amount": round(std, 2),
                            "detail": f"金额 {float(expense.amount):.0f} 偏离申请人历史均值 {mean:.0f} 的 {z:.1f} 倍标准差",
                        })

        # 2) 品类偏离：本次 l1_code 是否在历史前 3 中
        if historical:
            hist_l1 = [e.l1_code for e in historical if e.l1_code]
            if hist_l1:
                counter: Dict[str, int] = defaultdict(int)
                for c in hist_l1:
                    counter[c] += 1
                top3 = set(k for k, _ in sorted(counter.items(), key=lambda x: -x[1])[:3])
                if expense.l1_code and expense.l1_code not in top3:
                    anomalies.append({
                        "type": "single_category",
                        "severity": "low",
                        "expense_l1": expense.l1_code,
                        "applicant_top3": list(top3),
                        "detail": f"本次 l1_code={expense.l1_code} 不在申请人常用 Top3 内（{sorted(top3)}）",
                    })

        # 3) 时段异常：月末/季末/年末
        if expense.created_at:
            dt = expense.created_at
            is_month_end = dt.day >= 25
            is_quarter_end = dt.month in (3, 6, 9, 12) and dt.day >= 25
            is_year_end = dt.month == 12 and dt.day >= 20
            if is_year_end or is_quarter_end:
                anomalies.append({
                    "type": "timing",
                    "severity": "high" if is_year_end else "medium",
                    "submit_date": dt.strftime("%Y-%m-%d"),
                    "detail": f"{'年末' if is_year_end else '季末'} 25 日后提交，可能存在突击报销",
                })
            elif is_month_end:
                anomalies.append({
                    "type": "timing",
                    "severity": "low",
                    "submit_date": dt.strftime("%Y-%m-%d"),
                    "detail": "月末提交，请关注预算执行节奏",
                })

        return anomalies

    # ─── 群体异常检测 ───────────────────────────────────────

    async def detect_group_anomalies(
        self,
        db: AsyncSession,
        period: str,  # YYYY-MM
        center_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """群体异常检测
        - 中心维度：本期 vs 上期同中心总金额偏离
        - 品类维度：本期 vs 上期同 l1_code 总金额偏离
        """
        anomalies: List[Dict[str, Any]] = []

        # 解析期间
        try:
            cur_start = datetime.strptime(period, "%Y-%m")
        except ValueError:
            return anomalies
        cur_end = (cur_start + timedelta(days=32)).replace(day=1)
        prev_end = cur_start
        prev_start = (cur_start - timedelta(days=1)).replace(day=1)

        # 1) 中心维度
        center_stmt = (
            select(ExpenseReport.center_id, func.sum(ExpenseReport.amount).label("total"))
            .where(and_(
                ExpenseReport.created_at >= cur_start,
                ExpenseReport.created_at < cur_end,
            ))
            .group_by(ExpenseReport.center_id)
        )
        if center_id:
            center_stmt = center_stmt.where(ExpenseReport.center_id == center_id)
        result = await db.execute(center_stmt)
        cur_centers = {row[0]: float(row[1] or 0) for row in result.all()}

        prev_stmt = (
            select(ExpenseReport.center_id, func.sum(ExpenseReport.amount).label("total"))
            .where(and_(
                ExpenseReport.created_at >= prev_start,
                ExpenseReport.created_at < prev_end,
            ))
            .group_by(ExpenseReport.center_id)
        )
        if center_id:
            prev_stmt = prev_stmt.where(ExpenseReport.center_id == center_id)
        result = await db.execute(prev_stmt)
        prev_centers = {row[0]: float(row[1] or 0) for row in result.all()}

        for cid, cur_total in cur_centers.items():
            prev_total = prev_centers.get(cid, 0.0)
            if prev_total <= 0:
                continue
            mom_pct = (cur_total - prev_total) / prev_total * 100
            if abs(mom_pct) >= 50:  # 环比 ±50% 视为异常
                anomalies.append({
                    "type": "group_center",
                    "severity": "high" if abs(mom_pct) >= 100 else "medium",
                    "dimension": "center",
                    "center_id": cid,
                    "current_total": round(cur_total, 2),
                    "previous_total": round(prev_total, 2),
                    "mom_pct": round(mom_pct, 2),
                    "period": period,
                    "detail": f"中心 {cid} 本期报销 {cur_total:.0f}，环比 {mom_pct:+.1f}%（上期 {prev_total:.0f}）",
                })

        # 2) 品类维度
        cat_stmt = (
            select(ExpenseReport.l1_code, func.sum(ExpenseReport.amount).label("total"))
            .where(and_(
                ExpenseReport.created_at >= cur_start,
                ExpenseReport.created_at < cur_end,
            ))
            .group_by(ExpenseReport.l1_code)
        )
        result = await db.execute(cat_stmt)
        cur_cats = {row[0]: float(row[1] or 0) for row in result.all()}

        prev_cat_stmt = (
            select(ExpenseReport.l1_code, func.sum(ExpenseReport.amount).label("total"))
            .where(and_(
                ExpenseReport.created_at >= prev_start,
                ExpenseReport.created_at < prev_end,
            ))
            .group_by(ExpenseReport.l1_code)
        )
        result = await db.execute(prev_cat_stmt)
        prev_cats = {row[0]: float(row[1] or 0) for row in result.all()}

        for code, cur_total in cur_cats.items():
            prev_total = prev_cats.get(code, 0.0)
            if prev_total <= 0:
                continue
            mom_pct = (cur_total - prev_total) / prev_total * 100
            if abs(mom_pct) >= 40:
                anomalies.append({
                    "type": "group_category",
                    "severity": "high" if abs(mom_pct) >= 80 else "medium",
                    "dimension": "l1_code",
                    "l1_code": code,
                    "current_total": round(cur_total, 2),
                    "previous_total": round(prev_total, 2),
                    "mom_pct": round(mom_pct, 2),
                    "period": period,
                    "detail": f"L1 科目 {code} 本期 {cur_total:.0f}，环比 {mom_pct:+.1f}%（上期 {prev_total:.0f}）",
                })

        return anomalies

    # ─── 趋势异常检测（YoY） ─────────────────────────────────

    async def detect_trend_anomalies(
        self,
        db: AsyncSession,
        period: str,
        center_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """趋势异常（同比/环比突增）
        - 同比：本年同期 vs 去年同期
        - 环比：本期 vs 上期
        """
        anomalies: List[Dict[str, Any]] = []

        try:
            cur_start = datetime.strptime(period, "%Y-%m")
        except ValueError:
            return anomalies
        cur_end = (cur_start + timedelta(days=32)).replace(day=1)

        # 同比期间（去年同期）
        yoy_start = cur_start.replace(year=cur_start.year - 1)
        yoy_end = (yoy_start + timedelta(days=32)).replace(day=1)

        conditions = [
            ExpenseReport.created_at >= cur_start,
            ExpenseReport.created_at < cur_end,
        ]
        yoy_conditions = [
            ExpenseReport.created_at >= yoy_start,
            ExpenseReport.created_at < yoy_end,
        ]
        if center_id:
            conditions.append(ExpenseReport.center_id == center_id)
            yoy_conditions.append(ExpenseReport.center_id == center_id)

        # 当前期间总额
        stmt = select(
            func.count(ExpenseReport.expense_id).label("count"),
            func.sum(ExpenseReport.amount).label("total"),
        ).where(and_(*conditions))
        result = await db.execute(stmt)
        row = result.first()
        cur_count = int(row[0] or 0) if row else 0
        cur_total = float(row[1] or 0) if row else 0.0

        # 去年同期
        stmt = select(
            func.count(ExpenseReport.expense_id).label("count"),
            func.sum(ExpenseReport.amount).label("total"),
        ).where(and_(*yoy_conditions))
        result = await db.execute(stmt)
        row = result.first()
        yoy_count = int(row[0] or 0) if row else 0
        yoy_total = float(row[1] or 0) if row else 0.0

        if yoy_total > 0:
            yoy_pct = (cur_total - yoy_total) / yoy_total * 100
            if abs(yoy_pct) >= 30:
                anomalies.append({
                    "type": "trend_period",
                    "severity": "high" if abs(yoy_pct) >= 60 else "medium",
                    "period": period,
                    "current_total": round(cur_total, 2),
                    "yoy_total": round(yoy_total, 2),
                    "yoy_pct": round(yoy_pct, 2),
                    "cur_count": cur_count,
                    "yoy_count": yoy_count,
                    "detail": f"本期报销 {cur_total:.0f}，同比 {yoy_pct:+.1f}%（去年 {yoy_total:.0f}）",
                })

        return anomalies

    # ─── 综合：扫描指定期间的所有异常 ──────────────────────

    async def scan_period(
        self,
        db: AsyncSession,
        period: str,
        center_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """扫描指定期间所有异常（单笔 + 群体 + 趋势）
        返回：
        - single: 单笔异常列表
        - group: 群体异常列表
        - trend: 趋势异常列表
        - summary: 汇总（按类型 + 严重度）
        """
        try:
            cur_start = datetime.strptime(period, "%Y-%m")
        except ValueError:
            return {"error": f"无效期间格式: {period}，应为 YYYY-MM"}
        cur_end = (cur_start + timedelta(days=32)).replace(day=1)

        # 拉取本期所有报销单
        conditions = [
            ExpenseReport.created_at >= cur_start,
            ExpenseReport.created_at < cur_end,
        ]
        if center_id:
            conditions.append(ExpenseReport.center_id == center_id)
        stmt = select(ExpenseReport).where(and_(*conditions))
        result = await db.execute(stmt)
        cur_expenses = result.scalars().all()

        # 拉取历史报销单（同一申请人最近 6 月）
        single_anomalies: List[Dict[str, Any]] = []
        applicant_ids = {e.applicant_id for e in cur_expenses if e.applicant_id}
        for applicant_id in applicant_ids:
            hist_start = (cur_start - timedelta(days=180))
            hist_stmt = select(ExpenseReport).where(and_(
                ExpenseReport.applicant_id == applicant_id,
                ExpenseReport.created_at >= hist_start,
                ExpenseReport.created_at < cur_start,
            ))
            result = await db.execute(hist_stmt)
            historical = result.scalars().all()

            for expense in [e for e in cur_expenses if e.applicant_id == applicant_id]:
                anomalies = await self.detect_single_anomaly(expense, historical)
                for a in anomalies:
                    a["expense_id"] = expense.expense_id
                    a["applicant_id"] = applicant_id
                    a["center_id"] = expense.center_id
                    single_anomalies.append(a)

        # 群体异常
        group_anomalies = await self.detect_group_anomalies(db, period, center_id)

        # 趋势异常
        trend_anomalies = await self.detect_trend_anomalies(db, period, center_id)

        # 汇总
        all_anomalies = single_anomalies + group_anomalies + trend_anomalies
        severity_count = {"high": 0, "medium": 0, "low": 0}
        type_count: Dict[str, int] = defaultdict(int)
        for a in all_anomalies:
            sev = a.get("severity", "low")
            severity_count[sev] = severity_count.get(sev, 0) + 1
            type_count[a.get("type", "unknown")] += 1

        return {
            "period": period,
            "center_id": center_id,
            "single": single_anomalies,
            "group": group_anomalies,
            "trend": trend_anomalies,
            "summary": {
                "total_anomalies": len(all_anomalies),
                "by_severity": severity_count,
                "by_type": dict(type_count),
                "expense_count": len(cur_expenses),
            },
        }
