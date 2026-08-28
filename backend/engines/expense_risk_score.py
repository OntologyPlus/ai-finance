"""
费用风险评分引擎 — 5 维度加权评分
按经营分析方法论 §4.5 实施：金额/品类/频次/时段/历史
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from statistics import median, pstdev
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.expense import ExpenseReport


# 5 维度权重
WEIGHTS = {
    "amount": 0.30,      # 金额偏离
    "category": 0.20,    # 品类偏离
    "frequency": 0.20,   # 频次偏离
    "timing": 0.15,      # 时段异常
    "history": 0.15,     # 历史问题
}

SEVERITY_BANDS = [
    (0, 30, "low"),       # 0-30 低风险
    (30, 60, "medium"),   # 30-60 中风险
    (60, 80, "high"),     # 60-80 高风险
    (80, 100, "critical"),  # 80-100 严重
]


class ExpenseRiskScoreEngine:
    """费用风险评分引擎：5 维度加权"""

    def __init__(self):
        self.engine_name = "expense_risk_score"

    @staticmethod
    def _band(score: float) -> str:
        for lo, hi, name in SEVERITY_BANDS:
            if lo <= score < hi:
                return name
        return "critical"

    @staticmethod
    def _amount_score(
        expense_amount: float,
        hist_amounts: List[float],
    ) -> float:
        """金额偏离分（0-100）
        - 取申请人历史金额分布
        - 偏离度 = (amount - median) / max(median, 1)
        - 偏离度 0-50% → 0-30 分
        - 偏离度 50-100% → 30-60 分
        - 偏离度 100-200% → 60-85 分
        - 偏离度 > 200% → 85-100 分
        """
        if not hist_amounts or expense_amount <= 0:
            return 0.0
        med = median(hist_amounts)
        if med <= 0:
            return 0.0
        deviation = (expense_amount - med) / med
        if deviation == 0:
            return 0.0
        if deviation < 0:
            # 比历史中位数小，风险更低
            return max(0.0, 30.0 * (1 + deviation / 0.5)) if deviation >= -0.5 else 0.0
        if deviation < 0.5:
            return 30.0 * (deviation / 0.5)
        if deviation < 1.0:
            return 30.0 + 30.0 * ((deviation - 0.5) / 0.5)
        if deviation < 2.0:
            return 60.0 + 25.0 * ((deviation - 1.0) / 1.0)
        return min(100.0, 85.0 + 15.0 * min(1.0, (deviation - 2.0) / 1.0))

    @staticmethod
    def _category_score(
        expense_l1: Optional[str],
        hist_l1: List[str],
    ) -> float:
        """品类偏离分（0-100）
        - 申请人历史最常用 L1 → 0 分
        - 次常用 → 25 分
        - 不在历史 → 70 分
        - 完全无历史 → 50 分
        """
        if not expense_l1:
            return 0.0
        if not hist_l1:
            return 50.0
        counter: Dict[str, int] = defaultdict(int)
        for c in hist_l1:
            counter[c] += 1
        sorted_codes = sorted(counter.items(), key=lambda x: -x[1])
        total = sum(counter.values())

        for idx, (code, count) in enumerate(sorted_codes):
            if code == expense_l1:
                # 排得越靠前分越低
                ratio = count / total
                if idx == 0:
                    return 0.0
                if idx == 1:
                    return 25.0 * (1 - ratio)
                return 40.0 * (1 - ratio)
        return 70.0

    @staticmethod
    def _frequency_score(
        cur_period_count: int,
        hist_period_counts: List[int],
    ) -> float:
        """频次偏离分（0-100）
        - 本期报销次数 vs 历史同期中位数
        - 偏离度 = (cur - median) / max(median, 1)
        """
        if not hist_period_counts or cur_period_count <= 0:
            return 0.0
        med = median(hist_period_counts)
        if med <= 0:
            return 0.0
        deviation = (cur_period_count - med) / med
        if deviation <= 0:
            return 0.0
        if deviation < 0.5:
            return 30.0 * (deviation / 0.5)
        if deviation < 1.0:
            return 30.0 + 30.0 * ((deviation - 0.5) / 0.5)
        if deviation < 2.0:
            return 60.0 + 25.0 * ((deviation - 1.0) / 1.0)
        return min(100.0, 85.0 + 15.0 * min(1.0, (deviation - 2.0) / 1.0))

    @staticmethod
    def _timing_score(created_at: Optional[datetime]) -> float:
        """时段异常分（0-100）
        - 月末（25-31 日）→ 30 分
        - 季末（3/6/9/12 月 25-31 日）→ 60 分
        - 年末（12 月 20-31 日）→ 90 分
        - 正常时段 → 0 分
        """
        if not created_at:
            return 0.0
        d = created_at
        is_year_end = d.month == 12 and d.day >= 20
        is_quarter_end = d.month in (3, 6, 9, 12) and d.day >= 25
        is_month_end = d.day >= 25
        if is_year_end:
            return 90.0
        if is_quarter_end:
            return 60.0
        if is_month_end:
            return 30.0
        return 0.0

    @staticmethod
    def _history_score(
        applicant_id: str,
        rejection_count: int,
        total_count: int,
    ) -> float:
        """历史问题分（0-100）
        - 历史驳回率
        - 0% → 0 分
        - 5% → 30 分
        - 10% → 60 分
        - 20% → 90 分
        """
        if not applicant_id or total_count <= 0:
            return 0.0
        rate = rejection_count / total_count
        if rate <= 0.02:
            return 0.0
        if rate < 0.05:
            return 30.0 * ((rate - 0.02) / 0.03)
        if rate < 0.10:
            return 30.0 + 30.0 * ((rate - 0.05) / 0.05)
        if rate < 0.20:
            return 60.0 + 30.0 * ((rate - 0.10) / 0.10)
        return min(100.0, 90.0 + 10.0 * min(1.0, (rate - 0.20) / 0.20))

    # ─── 主入口：对单笔报销评分 ───────────────────────────

    async def score_expense(
        self,
        expense: ExpenseReport,
        hist_expenses: List[ExpenseReport],
        hist_rejection_count: int = 0,
    ) -> Dict[str, Any]:
        """对单笔报销打分
        Args:
            expense: 待评分的报销单
            hist_expenses: 同一申请人历史报销（不含本期）
            hist_rejection_count: 历史驳回次数
        """
        applicant_id = expense.applicant_id
        hist_amounts = [float(e.amount) for e in hist_expenses if e.amount]
        hist_l1 = [e.l1_code for e in hist_expenses if e.l1_code]

        # 计算各维度分
        amount_s = self._amount_score(float(expense.amount or 0), hist_amounts)
        category_s = self._category_score(expense.l1_code, hist_l1)
        frequency_s = self._frequency_score(
            1,  # 本期本次
            [1] * len(hist_expenses),  # 历史每期 1 笔（简化）
        )
        timing_s = self._timing_score(expense.created_at)
        history_s = self._history_score(
            applicant_id or "",
            hist_rejection_count,
            len(hist_expenses) + 1,  # 包含本次
        )

        # 加权汇总
        total = (
            amount_s * WEIGHTS["amount"]
            + category_s * WEIGHTS["category"]
            + frequency_s * WEIGHTS["frequency"]
            + timing_s * WEIGHTS["timing"]
            + history_s * WEIGHTS["history"]
        )
        total = round(min(100.0, max(0.0, total)), 2)
        band = self._band(total)

        # 行动建议
        if band == "critical":
            action = "auto_reject"
            action_label = "🚫 自动驳回（>80 分），需人工申诉"
        elif band == "high":
            action = "manual_review"
            action_label = "⚠️ 需人工审核（60-80 分）"
        elif band == "medium":
            action = "fast_track"
            action_label = "⏩ 简化审核（30-60 分）"
        else:
            action = "auto_approve"
            action_label = "✅ 自动通过（<30 分）"

        return {
            "expense_id": expense.expense_id,
            "applicant_id": applicant_id,
            "total_score": total,
            "band": band,
            "action": action,
            "action_label": action_label,
            "dimension_scores": {
                "amount": round(amount_s, 2),
                "category": round(category_s, 2),
                "frequency": round(frequency_s, 2),
                "timing": round(timing_s, 2),
                "history": round(history_s, 2),
            },
            "weights": WEIGHTS,
        }

    async def score_batch(
        self,
        db: AsyncSession,
        period: str,
        center_id: Optional[str] = None,
        top_n: int = 20,
    ) -> Dict[str, Any]:
        """批量评分：本期所有报销
        Returns:
        - scores: 评分列表（按分数降序）
        - summary: 汇总（按 band 分布）
        - top_risks: 最高风险 TopN
        """
        try:
            cur_start = datetime.strptime(period, "%Y-%m")
        except ValueError:
            return {"error": f"无效期间格式: {period}，应为 YYYY-MM"}
        cur_end = (cur_start + timedelta(days=32)).replace(day=1)
        hist_start = cur_start - timedelta(days=180)

        # 拉取本期报销
        conditions = [
            ExpenseReport.created_at >= cur_start,
            ExpenseReport.created_at < cur_end,
        ]
        if center_id:
            conditions.append(ExpenseReport.center_id == center_id)
        stmt = select(ExpenseReport).where(and_(*conditions))
        result = await db.execute(stmt)
        cur_expenses = result.scalars().all()

        if not cur_expenses:
            return {
                "period": period,
                "scores": [],
                "summary": {"total": 0, "by_band": {}},
                "top_risks": [],
            }

        # 拉取所有申请人历史
        applicant_ids = {e.applicant_id for e in cur_expenses if e.applicant_id}
        hist_map: Dict[str, List[ExpenseReport]] = {}
        for aid in applicant_ids:
            stmt = select(ExpenseReport).where(and_(
                ExpenseReport.applicant_id == aid,
                ExpenseReport.created_at >= hist_start,
                ExpenseReport.created_at < cur_start,
            ))
            result = await db.execute(stmt)
            hist_map[aid] = result.scalars().all()

        # 评分
        scores: List[Dict[str, Any]] = []
        for expense in cur_expenses:
            aid = expense.applicant_id or ""
            hist = hist_map.get(aid, [])
            score = await self.score_expense(expense, hist)
            scores.append(score)

        scores.sort(key=lambda x: -x["total_score"])

        # 汇总
        band_count: Dict[str, int] = defaultdict(int)
        for s in scores:
            band_count[s["band"]] += 1

        return {
            "period": period,
            "center_id": center_id,
            "scores": scores,
            "summary": {
                "total": len(scores),
                "by_band": dict(band_count),
                "avg_score": round(sum(s["total_score"] for s in scores) / max(len(scores), 1), 2),
            },
            "top_risks": scores[:top_n],
        }
