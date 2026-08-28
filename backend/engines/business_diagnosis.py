"""
经营诊断卡引擎（9 张诊断卡 + 4 个分析框架）

依据《经营分析方法论.md》设计：
- 9 张诊断卡：收入健康度/毛利质量/费用投放节奏/品种结构/渠道分化/
              利润真实性/商业化效率/政策风险/现金流质量
- 4 个分析框架：杜邦/桥接/BCG/SAR
- 信号灯机制：🔴/🟡/🟢（规则驱动，非 AI 主观）
- 三段式 AI Prompt：判断-证据-根因-建议
"""
from __future__ import annotations

import json
import math
import uuid
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.analysis import DiagnosisCard, DiagnosisReport, BudgetHealthScore
from models.ontology import OntologyRule
from services.prompt_manager import DIAGNOSIS_PROMPTS, build_diagnosis_prompt


# ───── 9 张卡定义 ─────

NINE_CARDS: List[Dict[str, Any]] = [
    {
        "number": 1,
        "type": "revenue_health",
        "name": "收入健康度",
        "framework": "杜邦分析法",
        "key_metric": "YTD 收入进度偏差 vs 去年同期",
        "degraded": False,
    },
    {
        "number": 2,
        "type": "gross_margin",
        "name": "毛利质量",
        "framework": "杜邦分析法",
        "key_metric": "实际毛利率 - 预算毛利率 偏差",
        "degraded": False,
    },
    {
        "number": 3,
        "type": "expense_pacing",
        "name": "费用投放节奏",
        "framework": "杜邦分析法 + 桥接分析",
        "key_metric": "推广费/维持费/人力三层 YTD 进度偏差（与去年同期比）",
        "degraded": False,
    },
    {
        "number": 4,
        "type": "product_mix",
        "name": "品种结构",
        "framework": "BCG 矩阵 + 产品生命周期",
        "key_metric": "生命周期分布 + Top 5 品种同比",
        "degraded": False,
    },
    {
        "number": 5,
        "type": "channel_split",
        "name": "渠道分化",
        "framework": "全渠道战略 + 渠道管理",
        "key_metric": "院内 vs 院外增速差",
        "degraded": False,
    },
    {
        "number": 6,
        "type": "profit_authenticity",
        "name": "利润真实性",
        "framework": "盈余管理检测",
        "key_metric": "商业利润率 - 经营利润率 差值",
        "degraded": False,
    },
    {
        "number": 7,
        "type": "commercialization_efficiency",
        "name": "商业化效率",
        "framework": "营销 ROI + CLV",
        "key_metric": "品种推广费 ROI（收入杠杆系数）",
        "degraded": True,  # 降级为收入杠杆系数版
    },
    {
        "number": 8,
        "type": "policy_risk",
        "name": "政策风险监控",
        "framework": "DID + 情景分析",
        "key_metric": "集采品种收入占比 + 集采品种毛利率",
        "degraded": True,  # 降级为暴露监控版
    },
    {
        "number": 9,
        "type": "cashflow_quality",
        "name": "现金流质量",
        "framework": "盈余质量 + 现金流分析",
        "key_metric": "非经营性收益占比 + DSO",
        "degraded": True,  # 降级为非经损益占比版
    },
]

CARD_BY_TYPE: Dict[str, Dict[str, Any]] = {c["type"]: c for c in NINE_CARDS}

# 信号灯判定顺序（最严重优先）
LIGHT_PRIORITY = {"red": 3, "yellow": 2, "green": 1}


# ───── 诊断卡引擎 ─────


class DiagnosisEngine:
    """9 张诊断卡 + 4 个分析框架 引擎"""

    def __init__(self):
        self.engine_name = "business_diagnosis"

    # ─────────── 通用方法 ───────────

    def _make_id(self, prefix: str = "DC") -> str:
        return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"

    def _select_worse_light(self, lights: List[str]) -> str:
        """多触发条件取最严重灯色"""
        if not lights:
            return "green"
        return max(lights, key=lambda x: LIGHT_PRIORITY.get(x, 0))

    def _wrap_card(
        self,
        card_type: str,
        period: str,
        signal_light: str,
        light_reason: str,
        metrics: Dict[str, Any],
        threshold: Dict[str, Any],
    ) -> Dict[str, Any]:
        """包装诊断卡数据"""
        meta = CARD_BY_TYPE[card_type]
        return {
            "id": self._make_id(),
            "period": period,
            "card_type": card_type,
            "card_number": meta["number"],
            "card_name": meta["name"],
            "framework_ref": meta["framework"],
            "degraded": meta["degraded"],
            "signal_light": signal_light,
            "light_reason": light_reason,
            "metrics_json": metrics,
            "threshold_json": threshold,
            # AI 生成字段默认空，调用方填充
            "judgment": None,
            "evidence": None,
            "root_cause": None,
            "actions": None,
            "pending_question": None,
            "ai_quality_level": None,
            "ai_review_passed": False,
        }

    # ─────────── 卡 1：收入健康度 ───────────

    async def diagnose_revenue_health(
        self, period: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """卡1：收入健康度
        - YTD 进度偏差 vs 去年同期
        - 全口径/存量同比增速
        - 预算达成率 vs 时间进度
        - 中心/渠道/品种三层下钻
        """
        year_str, month_str = period.split("-")
        month_num = int(month_str)
        time_progress_pct = (month_num / 12) * 100  # 时间进度百分比

        try:
            from models.budget import BudgetItem

            # 当年 YTD 实际收入（不含税）
            current_year_revenue = await self._sum_revenue(
                db, year=year_str, month_max=month_num, version="实际"
            )
            # 去年同期 YTD
            prev_year = str(int(year_str) - 1)
            last_year_revenue = await self._sum_revenue(
                db, year=prev_year, month_max=month_num, version="实际"
            )
            # YTD 预算（按当季÷3 派生）
            ytd_budget = await self._calc_ytd_budget(
                db, year=year_str, month_max=month_num
            )

            # 核心指标
            ytd_revenue = float(current_year_revenue or 0)
            ytd_last = float(last_year_revenue or 0)
            ytd_budget_val = float(ytd_budget or 0)

            ytd_progress = (
                (ytd_revenue / ytd_budget_val * 100) if ytd_budget_val > 0 else 0
            )
            last_progress = (
                (ytd_last / ytd_budget_val * 100) if ytd_budget_val > 0 else 0
            )
            progress_deviation = ytd_progress - last_progress
            budget_achievement = ytd_progress
            time_progress = time_progress_pct
            budget_gap = time_progress - budget_achievement

            yoy_full = (
                ((ytd_revenue - ytd_last) / ytd_last * 100) if ytd_last > 0 else 0
            )

            # 中心分项
            center_breakdown = await self._revenue_by_center(
                db, year=year_str, month_max=month_num
            )
            # 渠道分项
            channel_breakdown = await self._revenue_by_channel(
                db, year=year_str, month_max=month_num
            )
            # Top 5 品种
            top5_products = await self._revenue_by_product_top_n(
                db, year=year_str, month_max=month_num, n=5
            )

            metrics = {
                "ytd_revenue": round(ytd_revenue, 2),
                "ytd_budget": round(ytd_budget_val, 2),
                "ytd_last_year": round(ytd_last, 2),
                "ytd_progress_pct": round(ytd_progress, 2),
                "last_year_progress_pct": round(last_progress, 2),
                "progress_deviation_pp": round(progress_deviation, 2),
                "budget_achievement_pct": round(budget_achievement, 2),
                "time_progress_pct": round(time_progress, 2),
                "budget_gap_pp": round(budget_gap, 2),
                "yoy_full_pct": round(yoy_full, 2),
                "center_breakdown": center_breakdown,
                "channel_breakdown": channel_breakdown,
                "top5_products": top5_products,
            }

            # 信号灯判定
            lights = []
            reason_parts = []
            if progress_deviation > 2 and budget_achievement >= time_progress:
                lights.append("green")
                reason_parts.append(f"进度偏差 +{progress_deviation:.1f}pp 超预期")
            elif progress_deviation < -1:
                lights.append("red")
                reason_parts.append(f"进度偏差 {progress_deviation:.1f}pp 掉队")
            elif budget_gap > 3:
                lights.append("red")
                reason_parts.append(f"预算落后时间进度 {budget_gap:.1f}pp")
            elif -1 <= progress_deviation <= 2:
                lights.append("yellow")
                reason_parts.append(f"进度偏差 {progress_deviation:.1f}pp 在合理区间")

            signal = self._select_worse_light(lights) if lights else "green"
            threshold = {
                "green_rule": "progress_deviation > 2 AND budget_achievement >= time_progress",
                "yellow_rule": "-1 <= progress_deviation <= 2",
                "red_rule": "progress_deviation < -1 OR budget_gap > 3",
            }
            return self._wrap_card(
                "revenue_health",
                period,
                signal,
                "; ".join(reason_parts) or "数据正常",
                metrics,
                threshold,
            )
        except Exception as e:
            logger.error(f"[diagnosis] revenue_health failed: {e}")
            return self._wrap_card(
                "revenue_health",
                period,
                "yellow",
                f"数据计算异常: {e}",
                {"error": str(e)},
                {},
            )

    # ─────────── 卡 2：毛利质量 ───────────

    async def diagnose_gross_margin(
        self, period: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """卡2：毛利质量
        - 实际毛利率 - 预算毛利率 偏差
        - 倒减法两因素分解
        """
        year_str, month_str = period.split("-")
        month_num = int(month_str)
        try:
            actual_margin = await self._calc_gross_margin(
                db, year=year_str, month_max=month_num, version="实际"
            )
            budget_margin = await self._calc_gross_margin(
                db, year=year_str, month_max=month_num, version="预算"
            )
            margin_deviation = actual_margin - budget_margin

            # Top 10 品种毛利率
            top10_margin = await self._top10_product_margin(
                db, year=year_str, month_max=month_num
            )

            metrics = {
                "actual_gross_margin_pct": round(actual_margin, 2),
                "budget_gross_margin_pct": round(budget_margin, 2),
                "margin_deviation_pp": round(margin_deviation, 2),
                "top10_margin": top10_margin,
            }

            lights = []
            reason_parts = []
            if margin_deviation > 1:
                lights.append("green")
                reason_parts.append(
                    f"毛利率提升 +{margin_deviation:.1f}pp，超预算"
                )
            elif -1 <= margin_deviation <= 1:
                lights.append("yellow")
                reason_parts.append(
                    f"毛利率偏差 {margin_deviation:.1f}pp，在合理区间"
                )
            else:
                lights.append("red")
                reason_parts.append(
                    f"毛利率下降 {abs(margin_deviation):.1f}pp，赚钱能力恶化"
                )

            signal = self._select_worse_light(lights) if lights else "green"
            threshold = {
                "green_rule": "margin_deviation > +1pp",
                "yellow_rule": "-1pp <= margin_deviation <= +1pp",
                "red_rule": "margin_deviation < -1pp",
            }
            return self._wrap_card(
                "gross_margin",
                period,
                signal,
                "; ".join(reason_parts) or "数据正常",
                metrics,
                threshold,
            )
        except Exception as e:
            logger.error(f"[diagnosis] gross_margin failed: {e}")
            return self._wrap_card(
                "gross_margin",
                period,
                "yellow",
                f"数据计算异常: {e}",
                {"error": str(e)},
                {},
            )

    # ─────────── 卡 3：费用投放节奏 ───────────

    async def diagnose_expense_pacing(
        self, period: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """卡3：费用投放节奏
        - 推广费/维持费/人力三层 YTD 进度偏差（与去年同期比）
        - 推广费占收入比趋势
        """
        year_str, month_str = period.split("-")
        month_num = int(month_str)
        try:
            # 推广费
            promo_ytd = await self._sum_expense_by_level(
                db, year=year_str, month_max=month_num, level="市场推广"
            )
            promo_last_ytd = await self._sum_expense_by_level(
                db,
                year=str(int(year_str) - 1),
                month_max=month_num,
                level="市场推广",
            )
            promo_budget_ytd = await self._calc_ytd_budget_by_level(
                db, year=year_str, month_max=month_num, level="市场推广"
            )

            promo_progress = (
                (promo_ytd / promo_budget_ytd * 100) if promo_budget_ytd > 0 else 0
            )
            promo_last_progress = (
                (promo_last_ytd / promo_budget_ytd * 100) if promo_budget_ytd > 0
                else 0
            )
            promo_deviation = promo_progress - promo_last_progress

            # 维持费
            maint_ytd = await self._sum_expense_by_level_like(
                db, year=year_str, month_max=month_num, levels=["维持费用", "前台", "中台", "后台"]
            )
            maint_last_ytd = await self._sum_expense_by_level_like(
                db,
                year=str(int(year_str) - 1),
                month_max=month_num,
                levels=["维持费用", "前台", "中台", "后台"],
            )
            maint_budget_ytd = await self._calc_ytd_budget_by_level_like(
                db, year=year_str, month_max=month_num, levels=["维持费用", "前台", "中台", "后台"]
            )
            maint_progress = (
                (maint_ytd / maint_budget_ytd * 100) if maint_budget_ytd > 0 else 0
            )
            maint_last_progress = (
                (maint_last_ytd / maint_budget_ytd * 100) if maint_budget_ytd > 0
                else 0
            )
            maint_deviation = maint_progress - maint_last_progress

            # 人力成本
            hr_ytd = await self._sum_expense_by_level(
                db, year=year_str, month_max=month_num, level="人力成本"
            )
            hr_last_ytd = await self._sum_expense_by_level(
                db,
                year=str(int(year_str) - 1),
                month_max=month_num,
                level="人力成本",
            )
            hr_budget_ytd = await self._calc_ytd_budget_by_level(
                db, year=year_str, month_max=month_num, level="人力成本"
            )
            hr_progress = (
                (hr_ytd / hr_budget_ytd * 100) if hr_budget_ytd > 0 else 0
            )
            hr_last_progress = (
                (hr_last_ytd / hr_budget_ytd * 100) if hr_budget_ytd > 0 else 0
            )
            hr_deviation = hr_progress - hr_last_progress

            # 收入与推广费比
            ytd_revenue = await self._sum_revenue(
                db, year=year_str, month_max=month_num, version="实际"
            )
            promo_to_revenue = (
                (promo_ytd / ytd_revenue * 100) if ytd_revenue > 0 else 0
            )

            metrics = {
                "promotion": {
                    "ytd_actual": round(promo_ytd, 2),
                    "ytd_budget": round(promo_budget_ytd, 2),
                    "progress_pct": round(promo_progress, 2),
                    "last_year_progress_pct": round(promo_last_progress, 2),
                    "deviation_pp": round(promo_deviation, 2),
                },
                "maintenance": {
                    "ytd_actual": round(maint_ytd, 2),
                    "ytd_budget": round(maint_budget_ytd, 2),
                    "progress_pct": round(maint_progress, 2),
                    "last_year_progress_pct": round(maint_last_progress, 2),
                    "deviation_pp": round(maint_deviation, 2),
                },
                "hr_cost": {
                    "ytd_actual": round(hr_ytd, 2),
                    "ytd_budget": round(hr_budget_ytd, 2),
                    "progress_pct": round(hr_progress, 2),
                    "last_year_progress_pct": round(hr_last_progress, 2),
                    "deviation_pp": round(hr_deviation, 2),
                },
                "promo_to_revenue_pct": round(promo_to_revenue, 2),
            }

            lights = []
            reason_parts = []
            # 主要看推广费
            if promo_deviation < -3:
                lights.append("red")
                reason_parts.append(
                    f"推广费投放滞后 {abs(promo_deviation):.1f}pp，Q3-Q4 补投压力大"
                )
            elif -3 <= promo_deviation <= -1:
                lights.append("yellow")
                reason_parts.append(
                    f"推广费进度偏差 {promo_deviation:.1f}pp，需关注"
                )
            else:
                lights.append("green")
                reason_parts.append(f"推广费节奏正常 ({promo_deviation:.1f}pp)")

            signal = self._select_worse_light(lights) if lights else "green"
            threshold = {
                "green_rule": "promo_deviation > -1pp",
                "yellow_rule": "-3pp <= promo_deviation <= -1pp",
                "red_rule": "promo_deviation < -3pp",
            }
            return self._wrap_card(
                "expense_pacing",
                period,
                signal,
                "; ".join(reason_parts),
                metrics,
                threshold,
            )
        except Exception as e:
            logger.error(f"[diagnosis] expense_pacing failed: {e}")
            return self._wrap_card(
                "expense_pacing",
                period,
                "yellow",
                f"数据计算异常: {e}",
                {"error": str(e)},
                {},
            )

    # ─────────── 卡 4：品种结构 ───────────

    async def diagnose_product_mix(
        self, period: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """卡4：品种结构
        - 生命周期分布（导入/成长/成熟/衰退）
        - Top 5/10 品种同比增速
        - 衰退期品种占比
        """
        year_str, month_str = period.split("-")
        month_num = int(month_str)
        try:
            lifecycle_dist = await self._product_lifecycle_distribution(
                db, year=year_str, month_max=month_num
            )
            top5_growth = await self._top_n_product_yoy(
                db,
                year=year_str,
                month_max=month_num,
                n=5,
            )
            decline_share = lifecycle_dist.get("衰退", 0)

            mature_share = lifecycle_dist.get("成熟", 0)
            growth_share = lifecycle_dist.get("成长", 0) + lifecycle_dist.get(
                "导入", 0
            )

            metrics = {
                "lifecycle_distribution_pct": {
                    k: round(v, 2) for k, v in lifecycle_dist.items()
                },
                "top5_yoy_growth_pct": top5_growth,
                "decline_share_pct": round(decline_share, 2),
                "mature_share_pct": round(mature_share, 2),
                "growth_share_pct": round(growth_share, 2),
            }

            lights = []
            reason_parts = []
            if 50 <= mature_share <= 70 and growth_share >= 25:
                lights.append("green")
                reason_parts.append(
                    f"成熟期占比 {mature_share:.1f}%, 成长+导入 {growth_share:.1f}%, 引擎健康"
                )
            elif mature_share > 70 or growth_share < 15:
                lights.append("yellow")
                reason_parts.append(
                    f"成熟期 {mature_share:.1f}%, 增长引擎老化风险"
                )
            if decline_share > 15 and any(g < 0 for g in top5_growth.values()):
                lights.append("red")
                reason_parts.append(
                    f"衰退期品种占比 {decline_share:.1f}%, Top 5 负增长"
                )

            signal = self._select_worse_light(lights) if lights else "green"
            threshold = {
                "green_rule": "50%<=mature<=70% AND growth>=25%",
                "yellow_rule": "mature>70% OR growth<15%",
                "red_rule": "decline>15% AND top5_yoy<0",
            }
            return self._wrap_card(
                "product_mix",
                period,
                signal,
                "; ".join(reason_parts) or "结构合理",
                metrics,
                threshold,
            )
        except Exception as e:
            logger.error(f"[diagnosis] product_mix failed: {e}")
            return self._wrap_card(
                "product_mix",
                period,
                "yellow",
                f"数据计算异常: {e}",
                {"error": str(e)},
                {},
            )

    # ─────────── 卡 5：渠道分化 ───────────

    async def diagnose_channel_split(
        self, period: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """卡5：渠道分化
        - 院内 vs 院外增速差
        - G/非G/EC/W/A 细分增速
        """
        year_str, month_str = period.split("-")
        month_num = int(month_str)
        try:
            # 院内 G vs 院外（非G）
            current_split = await self._revenue_by_channel_split(
                db, year=year_str, month_max=month_num
            )
            last_split = await self._revenue_by_channel_split(
                db, year=str(int(year_str) - 1), month_max=month_num
            )

            in_hospital_yoy = current_split.get("in_yoy", 0)
            out_hospital_yoy = current_split.get("out_yoy", 0)
            growth_gap = in_hospital_yoy - out_hospital_yoy
            abs_gap = abs(growth_gap)

            metrics = {
                "in_hospital_yoy_pct": round(in_hospital_yoy, 2),
                "out_hospital_yoy_pct": round(out_hospital_yoy, 2),
                "growth_gap_pp": round(growth_gap, 2),
                "channel_breakdown": current_split.get("breakdown", {}),
            }

            lights = []
            reason_parts = []
            if abs_gap < 5:
                lights.append("green")
                reason_parts.append(
                    f"院内院外增速差 {growth_gap:.1f}pp，结构均衡"
                )
            elif abs_gap < 10:
                lights.append("yellow")
                reason_parts.append(
                    f"渠道分化 {abs_gap:.1f}pp，需关注边际趋势"
                )
            else:
                lights.append("red")
                reason_parts.append(
                    f"渠道严重失衡 {abs_gap:.1f}pp，存在结构性风险"
                )

            signal = self._select_worse_light(lights) if lights else "green"
            threshold = {
                "green_rule": "abs(growth_gap) < 5pp",
                "yellow_rule": "5pp <= abs(growth_gap) < 10pp",
                "red_rule": "abs(growth_gap) >= 10pp",
            }
            return self._wrap_card(
                "channel_split",
                period,
                signal,
                "; ".join(reason_parts),
                metrics,
                threshold,
            )
        except Exception as e:
            logger.error(f"[diagnosis] channel_split failed: {e}")
            return self._wrap_card(
                "channel_split",
                period,
                "yellow",
                f"数据计算异常: {e}",
                {"error": str(e)},
                {},
            )

    # ─────────── 卡 6：利润真实性 ───────────

    async def diagnose_profit_authenticity(
        self, period: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """卡6：利润真实性
        - 商业利润率 - 经营利润率 差值
        - 差值来源分解（研发/财务/非经营性损益）
        """
        year_str, month_str = period.split("-")
        month_num = int(month_str)
        try:
            operating_profit_rate = await self._calc_operating_profit_rate(
                db, year=year_str, month_max=month_num
            )
            business_profit_rate = await self._calc_business_profit_rate(
                db, year=year_str, month_max=month_num
            )
            diff = business_profit_rate - operating_profit_rate

            # 非经营性损益占比
            non_op_share = await self._non_operating_ratio(
                db, year=year_str, month_max=month_num
            )

            metrics = {
                "business_profit_rate_pct": round(business_profit_rate, 2),
                "operating_profit_rate_pct": round(operating_profit_rate, 2),
                "diff_pp": round(diff, 2),
                "non_operating_share_pct": round(non_op_share, 2),
            }

            lights = []
            reason_parts = []
            if diff < 5 and non_op_share < 10:
                lights.append("green")
                reason_parts.append(
                    f"差值 {diff:.1f}pp，非经损益 {non_op_share:.1f}%，利润质量高"
                )
            elif diff < 10 and non_op_share < 30:
                lights.append("yellow")
                reason_parts.append(
                    f"差值 {diff:.1f}pp，非经损益 {non_op_share:.1f}%，需评估"
                )
            else:
                lights.append("red")
                reason_parts.append(
                    f"差值 {diff:.1f}pp 或非经损益 {non_op_share:.1f}%，利润质量存疑"
                )

            signal = self._select_worse_light(lights) if lights else "green"
            threshold = {
                "green_rule": "diff < 5pp AND non_op < 10%",
                "yellow_rule": "diff < 10pp AND non_op < 30%",
                "red_rule": "diff >= 10pp OR non_op >= 30%",
            }
            return self._wrap_card(
                "profit_authenticity",
                period,
                signal,
                "; ".join(reason_parts),
                metrics,
                threshold,
            )
        except Exception as e:
            logger.error(f"[diagnosis] profit_authenticity failed: {e}")
            return self._wrap_card(
                "profit_authenticity",
                period,
                "yellow",
                f"数据计算异常: {e}",
                {"error": str(e)},
                {},
            )

    # ─────────── 卡 7：商业化效率（降级版）───────────

    async def diagnose_commercialization_efficiency(
        self, period: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """卡7：商业化效率（降级为收入杠杆系数版）
        完整版需品种级毛利数据，Phase 1 暂用收入杠杆系数
        """
        year_str, month_str = period.split("-")
        month_num = int(month_str)
        try:
            # 推广费 / 收入（整体杠杆）
            promo_total = await self._sum_expense_by_level(
                db, year=year_str, month_max=month_num, level="市场推广"
            )
            revenue_total = await self._sum_revenue(
                db, year=year_str, month_max=month_num, version="实际"
            )
            leverage = (
                (revenue_total / promo_total) if promo_total > 0 else 0
            )

            # 品种级 ROI（仅统计有推广费且非基础费用的品种）
            product_roi = await self._product_level_roi(
                db, year=year_str, month_max=month_num
            )

            metrics = {
                "overall_leverage_ratio": round(leverage, 2),
                "promo_to_revenue_pct": round(
                    (promo_total / revenue_total * 100) if revenue_total > 0 else 0,
                    2,
                ),
                "product_roi_top10": product_roi[:10],
                "degraded_note": "完整版需品种级毛利数据，Phase 1 用收入杠杆系数",
            }

            # 信号灯：以推广费占收入比为主
            promo_ratio = (
                (promo_total / revenue_total * 100) if revenue_total > 0 else 0
            )
            lights = []
            reason_parts = []
            if 15 <= promo_ratio <= 25:
                lights.append("green")
                reason_parts.append(
                    f"推广费占收入 {promo_ratio:.1f}%，在合理区间"
                )
            elif promo_ratio < 15 or promo_ratio > 30:
                lights.append("red")
                reason_parts.append(
                    f"推广费占收入 {promo_ratio:.1f}%，偏离合理区间"
                )
            else:
                lights.append("yellow")
                reason_parts.append(
                    f"推广费占收入 {promo_ratio:.1f}%，需关注"
                )

            signal = self._select_worse_light(lights) if lights else "yellow"
            threshold = {
                "green_rule": "15% <= promo_ratio <= 25%",
                "yellow_rule": "边缘区间",
                "red_rule": "promo_ratio < 15% OR > 30%",
            }
            return self._wrap_card(
                "commercialization_efficiency",
                period,
                signal,
                "; ".join(reason_parts),
                metrics,
                threshold,
            )
        except Exception as e:
            logger.error(f"[diagnosis] commercialization_efficiency failed: {e}")
            return self._wrap_card(
                "commercialization_efficiency",
                period,
                "yellow",
                f"数据计算异常: {e}",
                {"error": str(e)},
                {},
            )

    # ─────────── 卡 8：政策风险（降级为暴露监控版）───────────

    async def diagnose_policy_risk(
        self, period: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """卡8：政策风险（降级为暴露监控版）
        完整版需 VBP 政策台账，Phase 1 仅做已标记集采品种的暴露监控
        """
        year_str, month_str = period.split("-")
        month_num = int(month_str)
        try:
            vbp_revenue = await self._sum_vbp_revenue(
                db, year=year_str, month_max=month_num
            )
            total_revenue = await self._sum_revenue(
                db, year=year_str, month_max=month_num, version="实际"
            )
            vbp_share = (
                (vbp_revenue / total_revenue * 100) if total_revenue > 0 else 0
            )

            vbp_margin = await self._vbp_gross_margin(
                db, year=year_str, month_max=month_num
            )
            non_vbp_margin = await self._non_vbp_gross_margin(
                db, year=year_str, month_max=month_num
            )

            metrics = {
                "vbp_revenue_share_pct": round(vbp_share, 2),
                "vbp_gross_margin_pct": round(vbp_margin, 2),
                "non_vbp_gross_margin_pct": round(non_vbp_margin, 2),
                "margin_gap_pp": round(non_vbp_margin - vbp_margin, 2),
                "degraded_note": "完整版需 VBP 政策台账（批次/降价/执行日），Phase 1 仅做暴露监控",
            }

            lights = []
            reason_parts = []
            if vbp_share < 20:
                lights.append("green")
                reason_parts.append(
                    f"集采品种占比 {vbp_share:.1f}%，政策风险可控"
                )
            elif vbp_share < 40:
                lights.append("yellow")
                reason_parts.append(
                    f"集采品种占比 {vbp_share:.1f}%，需提前布局"
                )
            else:
                lights.append("red")
                reason_parts.append(
                    f"集采品种占比 {vbp_share:.1f}%，政策风险已显化"
                )

            signal = self._select_worse_light(lights) if lights else "green"
            threshold = {
                "green_rule": "vbp_share < 20%",
                "yellow_rule": "20% <= vbp_share < 40%",
                "red_rule": "vbp_share >= 40%",
            }
            return self._wrap_card(
                "policy_risk",
                period,
                signal,
                "; ".join(reason_parts),
                metrics,
                threshold,
            )
        except Exception as e:
            logger.error(f"[diagnosis] policy_risk failed: {e}")
            return self._wrap_card(
                "policy_risk",
                period,
                "yellow",
                f"数据计算异常: {e}",
                {"error": str(e)},
                {},
            )

    # ─────────── 卡 9：现金流质量（降级版）───────────

    async def diagnose_cashflow_quality(
        self, period: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """卡9：现金流质量（降级为非经损益占比版）
        完整版需应收账款与现金流数据
        """
        year_str, month_str = period.split("-")
        month_num = int(month_str)
        try:
            non_op_share = await self._non_operating_ratio(
                db, year=year_str, month_max=month_num
            )
            # DSO 暂不可计算
            dso = None

            metrics = {
                "non_operating_share_pct": round(non_op_share, 2),
                "dso_days": dso,
                "ocf_to_operating_profit": None,
                "degraded_note": "DSO/收现比/OCF 需财务系统补充应收账款与现金流数据",
            }

            lights = []
            reason_parts = []
            if non_op_share < 10:
                lights.append("green")
                reason_parts.append(
                    f"非经损益占比 {non_op_share:.1f}%，利润含金量高"
                )
            elif non_op_share < 30:
                lights.append("yellow")
                reason_parts.append(
                    f"非经损益占比 {non_op_share:.1f}%，需关注"
                )
            else:
                lights.append("red")
                reason_parts.append(
                    f"非经损益占比 {non_op_share:.1f}%，利润含金量存疑"
                )

            signal = self._select_worse_light(lights) if lights else "yellow"
            threshold = {
                "green_rule": "non_op_share < 10%",
                "yellow_rule": "10% <= non_op_share < 30%",
                "red_rule": "non_op_share >= 30%",
            }
            return self._wrap_card(
                "cashflow_quality",
                period,
                signal,
                "; ".join(reason_parts),
                metrics,
                threshold,
            )
        except Exception as e:
            logger.error(f"[diagnosis] cashflow_quality failed: {e}")
            return self._wrap_card(
                "cashflow_quality",
                period,
                "yellow",
                f"数据计算异常: {e}",
                {"error": str(e)},
                {},
            )

    # ─────────── 4 个分析框架 ───────────

    async def calc_dupont_waterfall(
        self, period: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """杜邦管理版瀑布图数据
        经营利润率 = 毛利率 - 推广费率 - 维持费率 - 人力费率 - 研发费率
        """
        year_str, month_str = period.split("-")
        month_num = int(month_str)
        try:
            revenue = (
                await self._sum_revenue(
                    db, year=year_str, month_max=month_num, version="实际"
                )
                or 0
            )
            if revenue <= 0:
                return {"error": "收入为零，无法计算", "items": []}

            gross_margin_rate = (
                await self._calc_gross_margin(
                    db, year=year_str, month_max=month_num, version="实际"
                )
                or 0
            )
            promo_rate = (
                await self._sum_expense_rate(
                    db,
                    year=year_str,
                    month_max=month_num,
                    level="市场推广",
                    revenue=revenue,
                )
                or 0
            )
            maint_rate = (
                await self._sum_expense_level_like_rate(
                    db,
                    year=year_str,
                    month_max=month_num,
                    levels=["维持费用", "前台", "中台", "后台"],
                    revenue=revenue,
                )
                or 0
            )
            hr_rate = (
                await self._sum_expense_rate(
                    db, year=year_str, month_max=month_num, level="人力成本", revenue=revenue
                )
                or 0
            )
            rnd_rate = (
                await self._sum_expense_level_like_rate(
                    db,
                    year=year_str,
                    month_max=month_num,
                    levels=["研发", "研发维持", "研发人力", "研发及注册"],
                    revenue=revenue,
                )
                or 0
            )

            operating_rate = (
                gross_margin_rate - promo_rate - maint_rate - hr_rate - rnd_rate
            )

            items = [
                {"name": "毛利率", "value": round(gross_margin_rate, 2), "type": "base"},
                {"name": "推广费率", "value": round(-promo_rate, 2), "type": "minus"},
                {"name": "维持费率", "value": round(-maint_rate, 2), "type": "minus"},
                {"name": "人力费率", "value": round(-hr_rate, 2), "type": "minus"},
                {"name": "研发费率", "value": round(-rnd_rate, 2), "type": "minus"},
                {"name": "经营利润率", "value": round(operating_rate, 2), "type": "result"},
            ]
            return {
                "items": items,
                "revenue": round(float(revenue), 2),
                "period": period,
                "summary": f"经营利润率 {operating_rate:.1f}% = 毛利率 {gross_margin_rate:.1f}% - 推广 {promo_rate:.1f}% - 维持 {maint_rate:.1f}% - 人力 {hr_rate:.1f}% - 研发 {rnd_rate:.1f}%",
            }
        except Exception as e:
            logger.error(f"[diagnosis] dupont_waterfall failed: {e}")
            return {"error": str(e), "items": []}

    async def calc_bridge_analysis(
        self, period: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """桥接分析（5步利润桥接）
        预算经营利润 → 收入量差 → 毛利率差 → 推广费节奏差
        → 维持费节奏差 → 人力成本节奏差 = 实际经营利润
        """
        year_str, month_str = period.split("-")
        month_num = int(month_str)
        try:
            budget_op_profit = await self._calc_operating_profit(
                db, year=year_str, month_max=month_num, version="预算"
            )
            actual_op_profit = await self._calc_operating_profit(
                db, year=year_str, month_max=month_num, version="实际"
            )

            # 收入量差 = (实际收入 - 预算收入) × 预算毛利率
            actual_revenue = (
                await self._sum_revenue(
                    db, year=year_str, month_max=month_num, version="实际"
                )
                or 0
            )
            budget_revenue = (
                await self._sum_revenue(
                    db, year=year_str, month_max=month_num, version="预算"
                )
                or 0
            )
            budget_margin = (
                await self._calc_gross_margin(
                    db, year=year_str, month_max=month_num, version="预算"
                )
                or 0
            )
            revenue_volume_diff = (actual_revenue - budget_revenue) * (
                budget_margin / 100
            )

            # 毛利率差 = 实际收入 × (实际毛利率 - 预算毛利率)
            actual_margin = (
                await self._calc_gross_margin(
                    db, year=year_str, month_max=month_num, version="实际"
                )
                or 0
            )
            margin_diff = actual_revenue * ((actual_margin - budget_margin) / 100)

            # 费用节奏差
            promo_actual = await self._sum_expense_by_level(
                db, year=year_str, month_max=month_num, level="市场推广"
            )
            promo_budget = await self._calc_ytd_budget_by_level(
                db, year=year_str, month_max=month_num, level="市场推广"
            )
            promo_diff = -(promo_actual - promo_budget)

            maint_actual = await self._sum_expense_by_level_like(
                db,
                year=year_str,
                month_max=month_num,
                levels=["维持费用", "前台", "中台", "后台"],
            )
            maint_budget = await self._calc_ytd_budget_by_level_like(
                db,
                year=year_str,
                month_max=month_num,
                levels=["维持费用", "前台", "中台", "后台"],
            )
            maint_diff = -(maint_actual - maint_budget)

            hr_actual = await self._sum_expense_by_level(
                db, year=year_str, month_max=month_num, level="人力成本"
            )
            hr_budget = await self._calc_ytd_budget_by_level(
                db, year=year_str, month_max=month_num, level="人力成本"
            )
            hr_diff = -(hr_actual - hr_budget)

            steps = [
                {"name": "预算经营利润", "value": round(float(budget_op_profit), 2)},
                {"name": "收入量差", "value": round(float(revenue_volume_diff), 2)},
                {"name": "毛利率差", "value": round(float(margin_diff), 2)},
                {"name": "推广费节奏差", "value": round(float(promo_diff), 2)},
                {"name": "维持费节奏差", "value": round(float(maint_diff), 2)},
                {"name": "人力成本节奏差", "value": round(float(hr_diff), 2)},
                {"name": "实际经营利润", "value": round(float(actual_op_profit), 2)},
            ]
            return {
                "steps": steps,
                "period": period,
                "summary": f"预算 {budget_op_profit:.0f} → 实际 {actual_op_profit:.0f}，差异 {actual_op_profit - budget_op_profit:.0f}",
            }
        except Exception as e:
            logger.error(f"[diagnosis] bridge_analysis failed: {e}")
            return {"error": str(e), "steps": []}

    async def calc_bcg_matrix(
        self, period: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """BCG 四象限分类
        - 横轴：增长率（预算达成率）
        - 纵轴：收入规模
        - 颜色：产品生命周期
        """
        try:
            products = await self._product_bcg_data(db, period)
            # 分类
            quadrants = {"明星": [], "现金牛": [], "问题": [], "瘦狗": []}
            for p in products:
                growth = p.get("yoy_growth", 0)
                revenue = p.get("revenue", 0)
                # 简化分类：以中位数为界
                median_growth = 0
                median_revenue = (
                    sum(pr.get("revenue", 0) for pr in products) / len(products)
                    if products
                    else 0
                )
                if growth > median_growth and revenue > median_revenue:
                    p["quadrant"] = "明星"
                elif growth <= median_growth and revenue > median_revenue:
                    p["quadrant"] = "现金牛"
                elif growth > median_growth and revenue <= median_revenue:
                    p["quadrant"] = "问题"
                else:
                    p["quadrant"] = "瘦狗"
                quadrants[p["quadrant"]].append(p)

            strategies = {
                "明星": "加大投入，培育新增长点",
                "现金牛": "维持投入，专注利润转化",
                "问题": "3-6 个月观察期，评估潜力",
                "瘦狗": "评估是否退出",
            }
            return {
                "products": products,
                "quadrants": quadrants,
                "strategies": strategies,
                "period": period,
                "summary": f"共 {len(products)} 个品种：明星 {len(quadrants['明星'])} / 现金牛 {len(quadrants['现金牛'])} / 问题 {len(quadrants['问题'])} / 瘦狗 {len(quadrants['瘦狗'])}",
            }
        except Exception as e:
            logger.error(f"[diagnosis] bcg_matrix failed: {e}")
            return {"error": str(e), "products": [], "quadrants": {}}

    async def calc_sar_recommendations(
        self, period: str, db: AsyncSession, card_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """SAR 框架行动建议
        - S: 当前月度结果距年度目标多远
        - A: 下月 3-5 件关键行动
        - R: 预期效果（Q3/Q4 变化）
        """
        try:
            # 统计信号灯
            red_cards = [c for c in card_results if c.get("signal_light") == "red"]
            yellow_cards = [c for c in card_results if c.get("signal_light") == "yellow"]
            green_cards = [c for c in card_results if c.get("signal_light") == "green"]

            # 战略对齐（S）
            strategy = {
                "current_health": (
                    "健康" if not red_cards
                    else "存在重大风险" if len(red_cards) >= 3
                    else "需重点关注"
                ),
                "red_count": len(red_cards),
                "yellow_count": len(yellow_cards),
                "green_count": len(green_cards),
                "red_cards": [c.get("card_name") for c in red_cards],
                "yellow_cards": [c.get("card_name") for c in yellow_cards],
            }

            # 关键行动（A）：基于红黄灯卡生成
            actions = []
            for card in red_cards + yellow_cards[:3]:
                actions.append(
                    {
                        "card": card.get("card_name"),
                        "card_type": card.get("card_type"),
                        "suggestion": card.get("actions")
                        or f"关注 {card.get('card_name')}，制定专项计划",
                        "pending_question": card.get("pending_question")
                        or f"请 {card.get('card_name')} 负责人确认下一步方案",
                        "priority": "high" if card.get("signal_light") == "red" else "medium",
                    }
                )
            if not actions:
                actions.append(
                    {
                        "card": "整体",
                        "card_type": "all",
                        "suggestion": "维持当前经营节奏；Q3 提前部署新品放量；警惕高基数下的边际放缓",
                        "pending_question": "Q3 经营目标是否需要根据当前进度调整？",
                        "priority": "low",
                    }
                )

            # 预期结果（R）
            results = {
                "if_actions_executed": [
                    "红黄灯卡转绿灯，预算达成率提升",
                    "下月预算进度偏差收窄至 ±1pp 内",
                    "全年预算达成率达 95%+",
                ],
                "if_no_action": [
                    f"红黄灯卡继续恶化，预计 Q3 触发 {len(red_cards) * 2} 条新预警",
                    "全年预算完成率 < 90%",
                ],
            }
            return {
                "strategy": strategy,
                "actions": actions[:5],
                "results": results,
                "period": period,
                "summary": f"{strategy['current_health']}，建议执行 {len(actions)} 项关键行动",
            }
        except Exception as e:
            logger.error(f"[diagnosis] sar_recommendations failed: {e}")
            return {"error": str(e), "actions": []}

    # ─────────── 报告组装 ───────────

    async def generate_diagnosis_report(
        self, period: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """组装完整诊断报告（4部分+9卡）"""
        try:
            # 1. 跑 9 张卡
            card_results: List[Dict[str, Any]] = []
            for card in NINE_CARDS:
                method = getattr(self, f"diagnose_{card['type']}", None)
                if method:
                    result = await method(period, db)
                    card_results.append(result)

            # 2. 跑 4 框架
            dupont = await self.calc_dupont_waterfall(period, db)
            bridge = await self.calc_bridge_analysis(period, db)
            bcg = await self.calc_bcg_matrix(period, db)
            sar = await self.calc_sar_recommendations(period, db, card_results)

            # 3. 提取 Top 3-5 核心判断
            red_cards = [c for c in card_results if c.get("signal_light") == "red"]
            top_judgments = []
            for c in red_cards[:3]:
                top_judgments.append(
                    {
                        "card": c.get("card_name"),
                        "light": c.get("signal_light"),
                        "judgment": c.get("light_reason"),
                    }
                )
            if not top_judgments:
                yellow_cards = [c for c in card_results if c.get("signal_light") == "yellow"]
                for c in yellow_cards[:3]:
                    top_judgments.append(
                        {
                            "card": c.get("card_name"),
                            "light": c.get("signal_light"),
                            "judgment": c.get("light_reason"),
                        }
                    )

            report = {
                "id": self._make_id("DR"),
                "period": period,
                "status": "generated",
                "part1_overview": {
                    "dupont": dupont,
                    "top_judgments": top_judgments,
                },
                "part2_cards": card_results,
                "part3_bcg": bcg,
                "part4_sar": sar,
                "summary": {
                    "red_count": len(red_cards),
                    "yellow_count": len([c for c in card_results if c.get("signal_light") == "yellow"]),
                    "green_count": len([c for c in card_results if c.get("signal_light") == "green"]),
                },
            }
            return report
        except Exception as e:
            logger.error(f"[diagnosis] generate_report failed: {e}")
            return {"error": str(e), "period": period, "status": "failed"}

    # ─────────── AI 生成（L3 根因分析）───────────

    async def ai_generate_card_text(
        self, card: Dict[str, Any], db: AsyncSession
    ) -> Dict[str, Any]:
        """调用 LLM 生成诊断卡的四段式文字（判断-证据-根因-建议）"""
        card_type = card.get("card_type")
        if card_type not in DIAGNOSIS_PROMPTS:
            return {
                **card,
                "judgment": card.get("light_reason", ""),
                "evidence": "数据计算完成",
                "root_cause": "需进一步分析",
                "actions": "请业务负责人关注",
                "pending_question": f"请确认 {card.get('card_name')} 的下一步行动",
                "ai_quality_level": "L2",
            }

        prompt = build_diagnosis_prompt(card)
        try:
            from utils.llm_client import get_llm_client

            llm = get_llm_client()
            response = await llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=800,
            )
            content = response.get("content", "") if isinstance(response, dict) else str(response)
            parsed = self._parse_four_segment(content)
            return {
                **card,
                "judgment": parsed.get("judgment", ""),
                "evidence": parsed.get("evidence", ""),
                "root_cause": parsed.get("root_cause", ""),
                "actions": parsed.get("actions", ""),
                "pending_question": parsed.get("pending_question", ""),
                "ai_quality_level": "L3" if parsed.get("root_cause") else "L2",
            }
        except Exception as e:
            logger.warning(f"[diagnosis] ai_generate failed for {card_type}, fallback to template: {e}")
            return self._fallback_template(card)

    def _parse_four_segment(self, content: str) -> Dict[str, str]:
        """解析四段式 AI 输出"""
        result = {
            "judgment": "",
            "evidence": "",
            "root_cause": "",
            "actions": "",
            "pending_question": "",
        }
        lines = content.split("\n")
        current_key = None
        for line in lines:
            line = line.strip()
            if "核心判断" in line or "1." in line and "判断" in line:
                current_key = "judgment"
                line = line.split("：", 1)[-1] if "：" in line else line.split(".", 1)[-1]
            elif "数据证据" in line or "2." in line and "证据" in line:
                current_key = "evidence"
                line = line.split("：", 1)[-1] if "：" in line else line.split(".", 1)[-1]
            elif "根因" in line or "3." in line and "根因" in line:
                current_key = "root_cause"
                line = line.split("：", 1)[-1] if "：" in line else line.split(".", 1)[-1]
            elif "行动建议" in line or "4." in line and "建议" in line:
                current_key = "actions"
                line = line.split("：", 1)[-1] if "：" in line else line.split(".", 1)[-1]
            elif "待" in line and "确认" in line:
                current_key = "pending_question"
                line = line.split("：", 1)[-1] if "：" in line else line

            if current_key and line:
                result[current_key] = (
                    (result[current_key] + " " + line).strip() if result[current_key] else line
                )
        return result

    def _fallback_template(self, card: Dict[str, Any]) -> Dict[str, Any]:
        """无 LLM 时的模板回退"""
        light = card.get("signal_light", "green")
        name = card.get("card_name", "")
        return {
            **card,
            "judgment": f"{name} 当前信号灯 {light}：{card.get('light_reason', '')}",
            "evidence": "详细数据见 metrics_json 字段",
            "root_cause": "需进一步分析（LLM 不可用，使用模板）",
            "actions": "请业务负责人关注并制定方案",
            "pending_question": f"请确认 {name} 的下一步行动",
            "ai_quality_level": "L2",
        }

    # ─────────── 工具方法（DB 查询封装）───────────

    async def _sum_revenue(
        self, db, year: str, month_max: int, version: str
    ) -> float:
        """求收入合计（不含税）"""
        try:
            from sqlalchemy import text
            result = await db.execute(
                text(
                    """
                    SELECT COALESCE(SUM(不含税销售收入), 0)
                    FROM revenue_table
                    WHERE 年度 = :year AND 月份 <= :month
                      AND 版本分类 = :version
                      AND 内部收入 = 0
                    """
                ),
                {"year": int(year), "month": month_max, "version": version},
            )
            val = result.scalar() or 0
            return float(val)
        except Exception as e:
            logger.debug(f"[_sum_revenue] fallback: {e}")
            return 0.0

    async def _calc_ytd_budget(
        self, db, year: str, month_max: int
    ) -> float:
        """YTD 预算（按当季÷3 派生）"""
        try:
            from sqlalchemy import text
            result = await db.execute(
                text(
                    """
                    SELECT COALESCE(SUM(不含税销售收入) / 3 * :q_months, 0) as ytd_budget
                    FROM revenue_table
                    WHERE 年度 = :year AND 月份 = 12
                      AND 版本分类 = '预算'
                      AND 季度分类 = :quarter
                    """
                ),
                {
                    "year": int(year),
                    "quarter": f"Q{(month_max - 1) // 3 + 1}",
                    "q_months": month_max - ((month_max - 1) // 3) * 3,
                },
            )
            val = result.scalar() or 0
            return float(val)
        except Exception as e:
            logger.debug(f"[_calc_ytd_budget] fallback: {e}")
            return 0.0

    async def _calc_gross_margin(
        self, db, year: str, month_max: int, version: str
    ) -> float:
        """毛利率 = (收入 - 总成本) / 收入 * 100"""
        try:
            from sqlalchemy import text
            result = await db.execute(
                text(
                    """
                    SELECT
                      COALESCE(SUM(不含税销售收入), 0) as revenue,
                      COALESCE(SUM(总成本), 0) as cost
                    FROM revenue_table
                    WHERE 年度 = :year AND 月份 <= :month
                      AND 版本分类 = :version
                      AND 内部收入 = 0
                    """
                ),
                {"year": int(year), "month": month_max, "version": version},
            )
            row = result.fetchone()
            if row and row[0] and row[0] > 0:
                return float((row[0] - row[1]) / row[0] * 100)
            return 0.0
        except Exception as e:
            logger.debug(f"[_calc_gross_margin] fallback: {e}")
            return 0.0

    async def _sum_expense_by_level(
        self, db, year: str, month_max: int, level: str
    ) -> float:
        """按层级属性求费用合计"""
        try:
            from sqlalchemy import text
            result = await db.execute(
                text(
                    """
                    SELECT COALESCE(SUM(费用金额), 0)
                    FROM expense_table
                    WHERE 年 = :year AND 月 <= :month
                      AND 层级属性 = :level
                    """
                ),
                {"year": int(year), "month": month_max, "level": level},
            )
            val = result.scalar() or 0
            return float(val)
        except Exception as e:
            logger.debug(f"[_sum_expense_by_level] fallback: {e}")
            return 0.0

    async def _sum_expense_by_level_like(
        self, db, year: str, month_max: int, levels: List[str]
    ) -> float:
        """按层级属性 LIKE 求费用合计"""
        try:
            from sqlalchemy import text
            placeholders = ",".join([f":l{i}" for i in range(len(levels))])
            params = {"year": int(year), "month": month_max}
            for i, lv in enumerate(levels):
                params[f"l{i}"] = lv
            result = await db.execute(
                text(
                    f"""
                    SELECT COALESCE(SUM(费用金额), 0)
                    FROM expense_table
                    WHERE 年 = :year AND 月 <= :month
                      AND 层级属性 IN ({placeholders})
                    """
                ),
                params,
            )
            val = result.scalar() or 0
            return float(val)
        except Exception as e:
            logger.debug(f"[_sum_expense_by_level_like] fallback: {e}")
            return 0.0

    async def _calc_ytd_budget_by_level(
        self, db, year: str, month_max: int, level: str
    ) -> float:
        """YTD 预算（按层级）"""
        try:
            from sqlalchemy import text
            result = await db.execute(
                text(
                    """
                    SELECT COALESCE(SUM(费用金额) / 3 * :q_months, 0)
                    FROM expense_table
                    WHERE 年 = :year AND 月 = 12
                      AND 层级属性 = :level
                      AND 季度分类 = :quarter
                    """
                ),
                {
                    "year": int(year),
                    "level": level,
                    "quarter": f"Q{(month_max - 1) // 3 + 1}",
                    "q_months": month_max - ((month_max - 1) // 3) * 3,
                },
            )
            val = result.scalar() or 0
            return float(val)
        except Exception as e:
            logger.debug(f"[_calc_ytd_budget_by_level] fallback: {e}")
            return 0.0

    async def _calc_ytd_budget_by_level_like(
        self, db, year: str, month_max: int, levels: List[str]
    ) -> float:
        try:
            from sqlalchemy import text
            placeholders = ",".join([f":l{i}" for i in range(len(levels))])
            params = {
                "year": int(year),
                "quarter": f"Q{(month_max - 1) // 3 + 1}",
                "q_months": month_max - ((month_max - 1) // 3) * 3,
            }
            for i, lv in enumerate(levels):
                params[f"l{i}"] = lv
            result = await db.execute(
                text(
                    f"""
                    SELECT COALESCE(SUM(费用金额) / 3 * :q_months, 0)
                    FROM expense_table
                    WHERE 年 = :year AND 月 = 12
                      AND 层级属性 IN ({placeholders})
                      AND 季度分类 = :quarter
                    """
                ),
                params,
            )
            val = result.scalar() or 0
            return float(val)
        except Exception as e:
            logger.debug(f"[_calc_ytd_budget_by_level_like] fallback: {e}")
            return 0.0

    async def _sum_expense_rate(
        self, db, year: str, month_max: int, level: str, revenue: float
    ) -> float:
        """层级费用率"""
        if revenue <= 0:
            return 0.0
        amount = await self._sum_expense_by_level(db, year, month_max, level)
        return (amount / revenue) * 100

    async def _sum_expense_level_like_rate(
        self, db, year: str, month_max: int, levels: List[str], revenue: float
    ) -> float:
        if revenue <= 0:
            return 0.0
        amount = await self._sum_expense_by_level_like(db, year, month_max, levels)
        return (amount / revenue) * 100

    async def _revenue_by_center(
        self, db, year: str, month_max: int
    ) -> List[Dict[str, Any]]:
        try:
            from sqlalchemy import text
            result = await db.execute(
                text(
                    """
                    SELECT 所属中心, COALESCE(SUM(不含税销售收入), 0) as revenue
                    FROM revenue_table
                    WHERE 年度 = :year AND 月份 <= :month
                      AND 版本分类 = '实际' AND 内部收入 = 0
                    GROUP BY 所属中心
                    ORDER BY revenue DESC
                    LIMIT 10
                    """
                ),
                {"year": int(year), "month": month_max},
            )
            return [
                {"center": r[0], "revenue": float(r[1])}
                for r in result.fetchall()
            ]
        except Exception as e:
            logger.debug(f"[_revenue_by_center] fallback: {e}")
            return []

    async def _revenue_by_channel(
        self, db, year: str, month_max: int
    ) -> List[Dict[str, Any]]:
        try:
            from sqlalchemy import text
            result = await db.execute(
                text(
                    """
                    SELECT 集合, COALESCE(SUM(不含税销售收入), 0) as revenue
                    FROM revenue_table
                    WHERE 年度 = :year AND 月份 <= :month
                      AND 版本分类 = '实际' AND 内部收入 = 0
                    GROUP BY 集合
                    ORDER BY revenue DESC
                    """
                ),
                {"year": int(year), "month": month_max},
            )
            return [
                {"channel": r[0], "revenue": float(r[1])}
                for r in result.fetchall()
            ]
        except Exception as e:
            logger.debug(f"[_revenue_by_channel] fallback: {e}")
            return []

    async def _revenue_by_product_top_n(
        self, db, year: str, month_max: int, n: int
    ) -> List[Dict[str, Any]]:
        try:
            from sqlalchemy import text
            result = await db.execute(
                text(
                    """
                    SELECT 大品种, COALESCE(SUM(不含税销售收入), 0) as revenue
                    FROM revenue_table
                    WHERE 年度 = :year AND 月份 <= :month
                      AND 版本分类 = '实际' AND 内部收入 = 0
                    GROUP BY 大品种
                    ORDER BY revenue DESC
                    LIMIT :n
                    """
                ),
                {"year": int(year), "month": month_max, "n": n},
            )
            return [
                {"product": r[0], "revenue": float(r[1])}
                for r in result.fetchall()
            ]
        except Exception as e:
            logger.debug(f"[_revenue_by_product_top_n] fallback: {e}")
            return []

    async def _product_lifecycle_distribution(
        self, db, year: str, month_max: int
    ) -> Dict[str, float]:
        try:
            from sqlalchemy import text
            result = await db.execute(
                text(
                    """
                    SELECT 产品生命周期, COALESCE(SUM(不含税销售收入), 0) as revenue
                    FROM revenue_table
                    WHERE 年度 = :year AND 月份 <= :month
                      AND 版本分类 = '实际' AND 内部收入 = 0
                      AND 产品生命周期 IS NOT NULL AND 产品生命周期 != ''
                    GROUP BY 产品生命周期
                    """
                ),
                {"year": int(year), "month": month_max},
            )
            total = sum(float(r[1]) for r in result.fetchall())
            if total <= 0:
                return {}
            result = await db.execute(
                text(
                    """
                    SELECT 产品生命周期, COALESCE(SUM(不含税销售收入), 0) as revenue
                    FROM revenue_table
                    WHERE 年度 = :year AND 月份 <= :month
                      AND 版本分类 = '实际' AND 内部收入 = 0
                      AND 产品生命周期 IS NOT NULL AND 产品生命周期 != ''
                    GROUP BY 产品生命周期
                    """
                ),
                {"year": int(year), "month": month_max},
            )
            dist = {}
            for r in result.fetchall():
                dist[r[0]] = float(r[1]) / total * 100
            return dist
        except Exception as e:
            logger.debug(f"[_product_lifecycle_distribution] fallback: {e}")
            return {}

    async def _top_n_product_yoy(
        self, db, year: str, month_max: int, n: int
    ) -> Dict[str, float]:
        try:
            from sqlalchemy import text
            cur = await db.execute(
                text(
                    """
                    SELECT 大品种, COALESCE(SUM(不含税销售收入), 0) as revenue
                    FROM revenue_table
                    WHERE 年度 = :year AND 月份 <= :month
                      AND 版本分类 = '实际' AND 内部收入 = 0
                    GROUP BY 大品种
                    ORDER BY revenue DESC
                    LIMIT :n
                    """
                ),
                {"year": int(year), "month": month_max, "n": n},
            )
            current = {r[0]: float(r[1]) for r in cur.fetchall()}

            prev = await db.execute(
                text(
                    """
                    SELECT 大品种, COALESCE(SUM(不含税销售收入), 0) as revenue
                    FROM revenue_table
                    WHERE 年度 = :year AND 月份 <= :month
                      AND 版本分类 = '实际' AND 内部收入 = 0
                    GROUP BY 大品种
                    """
                ),
                {"year": int(year) - 1, "month": month_max},
            )
            last_year = {r[0]: float(r[1]) for r in prev.fetchall()}

            yoy = {}
            for product, rev in current.items():
                last = last_year.get(product, 0)
                if last > 0:
                    yoy[product] = round((rev - last) / last * 100, 2)
                else:
                    yoy[product] = 100.0 if rev > 0 else 0.0
            return yoy
        except Exception as e:
            logger.debug(f"[_top_n_product_yoy] fallback: {e}")
            return {}

    async def _revenue_by_channel_split(
        self, db, year: str, month_max: int
    ) -> Dict[str, Any]:
        try:
            from sqlalchemy import text
            cur = await db.execute(
                text(
                    """
                    SELECT
                      CASE WHEN 集合 = 'G' THEN 'in_hospital' ELSE 'out_hospital' END as type,
                      COALESCE(SUM(不含税销售收入), 0) as revenue
                    FROM revenue_table
                    WHERE 年度 = :year AND 月份 <= :month
                      AND 版本分类 = '实际' AND 内部收入 = 0
                    GROUP BY type
                    """
                ),
                {"year": int(year), "month": month_max},
            )
            current = {r[0]: float(r[1]) for r in cur.fetchall()}

            prev = await db.execute(
                text(
                    """
                    SELECT
                      CASE WHEN 集合 = 'G' THEN 'in_hospital' ELSE 'out_hospital' END as type,
                      COALESCE(SUM(不含税销售收入), 0) as revenue
                    FROM revenue_table
                    WHERE 年度 = :year AND 月份 <= :month
                      AND 版本分类 = '实际' AND 内部收入 = 0
                    GROUP BY type
                    """
                ),
                {"year": int(year) - 1, "month": month_max},
            )
            last_year = {r[0]: float(r[1]) for r in prev.fetchall()}

            in_cur = current.get("in_hospital", 0)
            in_last = last_year.get("in_hospital", 0)
            out_cur = current.get("out_hospital", 0)
            out_last = last_year.get("out_hospital", 0)
            in_yoy = ((in_cur - in_last) / in_last * 100) if in_last > 0 else 0
            out_yoy = ((out_cur - out_last) / out_last * 100) if out_last > 0 else 0

            return {
                "in_yoy": in_yoy,
                "out_yoy": out_yoy,
                "breakdown": {
                    "in_hospital": {"current": in_cur, "last_year": in_last},
                    "out_hospital": {"current": out_cur, "last_year": out_last},
                },
            }
        except Exception as e:
            logger.debug(f"[_revenue_by_channel_split] fallback: {e}")
            return {"in_yoy": 0, "out_yoy": 0, "breakdown": {}}

    async def _top10_product_margin(
        self, db, year: str, month_max: int
    ) -> List[Dict[str, Any]]:
        try:
            from sqlalchemy import text
            result = await db.execute(
                text(
                    """
                    SELECT 大品种,
                      COALESCE(SUM(不含税销售收入), 0) as revenue,
                      COALESCE(SUM(总成本), 0) as cost
                    FROM revenue_table
                    WHERE 年度 = :year AND 月份 <= :month
                      AND 版本分类 = '实际' AND 内部收入 = 0
                    GROUP BY 大品种
                    ORDER BY revenue DESC
                    LIMIT 10
                    """
                ),
                {"year": int(year), "month": month_max},
            )
            result_list = []
            for r in result.fetchall():
                rev, cost = float(r[1]), float(r[2])
                margin = ((rev - cost) / rev * 100) if rev > 0 else 0
                result_list.append(
                    {"product": r[0], "revenue": rev, "margin_pct": round(margin, 2)}
                )
            return result_list
        except Exception as e:
            logger.debug(f"[_top10_product_margin] fallback: {e}")
            return []

    async def _calc_operating_profit(
        self, db, year: str, month_max: int, version: str
    ) -> float:
        """经营利润 = 毛利 - 推广费 - 维持费 - 人力成本 - 研发费"""
        try:
            revenue = (
                await self._sum_revenue(
                    db, year=year, month_max=month_max, version=version
                )
                or 0
            )
            cost = revenue - (revenue * (
                await self._calc_gross_margin(
                    db, year=year, month_max=month_max, version=version
                )
                or 0
            ) / 100)
            gross_profit = revenue - cost

            promo = await self._sum_expense_by_level(
                db, year=year, month_max=month_max, level="市场推广"
            )
            maint = await self._sum_expense_by_level_like(
                db,
                year=year,
                month_max=month_max,
                levels=["维持费用", "前台", "中台", "后台"],
            )
            hr = await self._sum_expense_by_level(
                db, year=year, month_max=month_max, level="人力成本"
            )
            rnd = await self._sum_expense_by_level_like(
                db,
                year=year,
                month_max=month_max,
                levels=["研发", "研发维持", "研发人力", "研发及注册"],
            )
            return gross_profit - promo - maint - hr - rnd
        except Exception as e:
            logger.debug(f"[_calc_operating_profit] fallback: {e}")
            return 0.0

    async def _calc_operating_profit_rate(
        self, db, year: str, month_max: int
    ) -> float:
        op = await self._calc_operating_profit(
            db, year, month_max, version="实际"
        )
        rev = await self._sum_revenue(
            db, year=year, month_max=month_max, version="实际"
        )
        return (op / rev * 100) if rev > 0 else 0

    async def _calc_business_profit_rate(
        self, db, year: str, month_max: int
    ) -> float:
        """商业利润 = 经营利润 + 研发费用 + 财务费用"""
        op = await self._calc_operating_profit(
            db, year, month_max, version="实际"
        )
        rnd = await self._sum_expense_by_level_like(
            db,
            year=year,
            month_max=month_max,
            levels=["研发", "研发维持", "研发人力", "研发及注册"],
        )
        fin = await self._sum_expense_by_level(
            db, year=year, month_max=month_max, level="财务费用"
        )
        rev = await self._sum_revenue(
            db, year=year, month_max=month_max, version="实际"
        )
        business = op + rnd + fin
        return (business / rev * 100) if rev > 0 else 0

    async def _non_operating_ratio(
        self, db, year: str, month_max: int
    ) -> float:
        """非经营性损益占经营利润比"""
        try:
            from sqlalchemy import text
            result = await db.execute(
                text(
                    """
                    SELECT COALESCE(SUM(费用金额), 0)
                    FROM expense_table
                    WHERE 年 = :year AND 月 <= :month
                      AND 层级属性 = '非经营性损益'
                      AND 所属中心 = '（集团）'
                    """
                ),
                {"year": int(year), "month": month_max},
            )
            non_op = float(result.scalar() or 0)
            op = await self._calc_operating_profit(
                db, year, month_max, version="实际"
            )
            return (abs(non_op) / abs(op) * 100) if op != 0 else 0
        except Exception as e:
            logger.debug(f"[_non_operating_ratio] fallback: {e}")
            return 0.0

    async def _sum_vbp_revenue(
        self, db, year: str, month_max: int
    ) -> float:
        try:
            from sqlalchemy import text
            result = await db.execute(
                text(
                    """
                    SELECT COALESCE(SUM(不含税销售收入), 0)
                    FROM revenue_table
                    WHERE 年度 = :year AND 月份 <= :month
                      AND 版本分类 = '实际' AND 内部收入 = 0
                      AND (品种类型 = '集采' OR 品种类型 = '集采品种' OR 品种驱动 = 'VBP')
                    """
                ),
                {"year": int(year), "month": month_max},
            )
            return float(result.scalar() or 0)
        except Exception as e:
            logger.debug(f"[_sum_vbp_revenue] fallback: {e}")
            return 0.0

    async def _vbp_gross_margin(
        self, db, year: str, month_max: int
    ) -> float:
        try:
            from sqlalchemy import text
            result = await db.execute(
                text(
                    """
                    SELECT
                      COALESCE(SUM(不含税销售收入), 0) as revenue,
                      COALESCE(SUM(总成本), 0) as cost
                    FROM revenue_table
                    WHERE 年度 = :year AND 月份 <= :month
                      AND 版本分类 = '实际' AND 内部收入 = 0
                      AND (品种类型 = '集采' OR 品种类型 = '集采品种' OR 品种驱动 = 'VBP')
                    """
                ),
                {"year": int(year), "month": month_max},
            )
            row = result.fetchone()
            if row and row[0] and row[0] > 0:
                return float((row[0] - row[1]) / row[0] * 100)
            return 0.0
        except Exception as e:
            logger.debug(f"[_vbp_gross_margin] fallback: {e}")
            return 0.0

    async def _non_vbp_gross_margin(
        self, db, year: str, month_max: int
    ) -> float:
        try:
            from sqlalchemy import text
            result = await db.execute(
                text(
                    """
                    SELECT
                      COALESCE(SUM(不含税销售收入), 0) as revenue,
                      COALESCE(SUM(总成本), 0) as cost
                    FROM revenue_table
                    WHERE 年度 = :year AND 月份 <= :month
                      AND 版本分类 = '实际' AND 内部收入 = 0
                      AND NOT (品种类型 = '集采' OR 品种类型 = '集采品种' OR 品种驱动 = 'VBP')
                    """
                ),
                {"year": int(year), "month": month_max},
            )
            row = result.fetchone()
            if row and row[0] and row[0] > 0:
                return float((row[0] - row[1]) / row[0] * 100)
            return 0.0
        except Exception as e:
            logger.debug(f"[_non_vbp_gross_margin] fallback: {e}")
            return 0.0

    async def _product_level_roi(
        self, db, year: str, month_max: int
    ) -> List[Dict[str, Any]]:
        """品种级 ROI（收入/推广费）"""
        try:
            from sqlalchemy import text
            result = await db.execute(
                text(
                    """
                    SELECT r.大品种,
                      COALESCE(SUM(r.不含税销售收入), 0) as revenue,
                      COALESCE((
                        SELECT SUM(费用金额) FROM expense_table e
                        WHERE e.大品种 = r.大品种
                          AND e.层级属性 = '市场推广'
                          AND e.年 = :year AND e.月 <= :month
                      ), 0) as promo
                    FROM revenue_table r
                    WHERE r.年度 = :year AND r.月份 <= :month
                      AND r.版本分类 = '实际' AND r.内部收入 = 0
                      AND r.大品种 != '大品种=基础费用'
                    GROUP BY r.大品种
                    HAVING promo > 0
                    ORDER BY revenue DESC
                    LIMIT 50
                    """
                ),
                {"year": int(year), "month": month_max},
            )
            roi_list = []
            for r in result.fetchall():
                rev, promo = float(r[1]), float(r[2])
                roi = rev / promo if promo > 0 else 0
                roi_list.append(
                    {
                        "product": r[0],
                        "revenue": round(rev, 2),
                        "promo": round(promo, 2),
                        "roi": round(roi, 2),
                    }
                )
            return roi_list
        except Exception as e:
            logger.debug(f"[_product_level_roi] fallback: {e}")
            return []

    async def _product_bcg_data(
        self, db, period: str
    ) -> List[Dict[str, Any]]:
        try:
            year_str, month_str = period.split("-")
            month_num = int(month_str)
            from sqlalchemy import text
            cur = await db.execute(
                text(
                    """
                    SELECT 大品种, 产品生命周期, COALESCE(SUM(不含税销售收入), 0) as revenue
                    FROM revenue_table
                    WHERE 年度 = :year AND 月份 <= :month
                      AND 版本分类 = '实际' AND 内部收入 = 0
                    GROUP BY 大品种, 产品生命周期
                    """
                ),
                {"year": int(year_str), "month": month_num},
            )
            current = {
                r[0]: {"revenue": float(r[2]), "lifecycle": r[1]}
                for r in cur.fetchall()
            }
            prev = await db.execute(
                text(
                    """
                    SELECT 大品种, COALESCE(SUM(不含税销售收入), 0) as revenue
                    FROM revenue_table
                    WHERE 年度 = :year AND 月份 <= :month
                      AND 版本分类 = '实际' AND 内部收入 = 0
                    GROUP BY 大品种
                    """
                ),
                {"year": int(year_str) - 1, "month": month_num},
            )
            last_year = {r[0]: float(r[1]) for r in prev.fetchall()}

            products = []
            for p, info in current.items():
                rev = info["revenue"]
                last = last_year.get(p, 0)
                yoy = ((rev - last) / last * 100) if last > 0 else 0
                products.append(
                    {
                        "product": p,
                        "revenue": round(rev, 2),
                        "lifecycle": info["lifecycle"],
                        "yoy_growth": round(yoy, 2),
                    }
                )
            return sorted(products, key=lambda x: x["revenue"], reverse=True)
        except Exception as e:
            logger.debug(f"[_product_bcg_data] fallback: {e}")
            return []


# ─────────── 信号灯规则加载器（v3.0 新增）───────────

import os
from pathlib import Path as _Path


_DIAGNOSIS_RULES_PATH = _Path(__file__).parent.parent / "ontology" / "rules" / "diagnosis_rules.yaml"
_DIAGNOSIS_RULES_CACHE: Dict[str, Any] = {}
_DIAGNOSIS_RULES_LOADED = False


def load_signal_light_rules(force_reload: bool = False) -> Dict[str, Any]:
    """从 YAML 加载 9 张诊断卡的信号灯规则

    加载失败时返回空字典（引擎将使用内置硬编码阈值）
    """
    global _DIAGNOSIS_RULES_CACHE, _DIAGNOSIS_RULES_LOADED
    if _DIAGNOSIS_RULES_LOADED and not force_reload:
        return _DIAGNOSIS_RULES_CACHE

    try:
        import yaml as _yaml

        if not _DIAGNOSIS_RULES_PATH.exists():
            logger.debug(f"[signal_rules] yaml not found at {_DIAGNOSIS_RULES_PATH}")
            _DIAGNOSIS_RULES_LOADED = True
            return _DIAGNOSIS_RULES_CACHE
        with open(_DIAGNOSIS_RULES_PATH, "r", encoding="utf-8") as f:
            _DIAGNOSIS_RULES_CACHE = _yaml.safe_load(f) or {}
        _DIAGNOSIS_RULES_LOADED = True
        logger.info(f"[signal_rules] loaded {len(_DIAGNOSIS_RULES_CACHE)} card rules from yaml")
    except Exception as e:
        logger.warning(f"[signal_rules] load failed: {e}, fallback to engine defaults")
        _DIAGNOSIS_RULES_LOADED = True
    return _DIAGNOSIS_RULES_CACHE


def get_signal_light_thresholds(card_type: str) -> Dict[str, Any]:
    """获取指定诊断卡的信号灯阈值（供前端展示）"""
    rules = load_signal_light_rules()
    card_rules = rules.get(card_type, {})
    return card_rules.get("thresholds", {})


def evaluate_signal_light(card_type: str, metrics: Dict[str, Any]) -> Optional[str]:
    """根据 YAML 规则评估信号灯（如果规则可用）

    Returns:
        'red' / 'yellow' / 'green' / None（None 表示规则不可用，走引擎默认）
    """
    rules = load_signal_light_rules()
    card_rules = rules.get(card_type, {})
    if not card_rules:
        return None

    # 准备求值命名空间（metrics 中的字段直接作为变量）
    ns: Dict[str, Any] = {}
    for k, v in (metrics or {}).items():
        if isinstance(v, (int, float, bool)):
            ns[k] = v
    # 常用别名映射
    ns.setdefault("abs", abs)

    # 优先级：red > yellow > green
    for level in ("red", "yellow", "green"):
        expr = card_rules.get(level)
        if not expr:
            continue
        try:
            if eval(expr, {"__builtins__": {}}, ns):
                return level
        except Exception as e:
            logger.debug(f"[signal_rules] eval failed for {card_type}.{level}: {e}")
            continue
    return None


def save_signal_light_rules(new_rules: Dict[str, Any]) -> bool:
    """写回 YAML 文件（带备份）

    Args:
        new_rules: 完整规则字典（覆盖整个文件）
    Returns:
        True 成功 / False 失败
    """
    try:
        import yaml as _yaml
        # 备份
        if _DIAGNOSIS_RULES_PATH.exists():
            backup = _DIAGNOSIS_RULES_PATH.with_suffix(".yaml.bak")
            _DIAGNOSIS_RULES_PATH.replace(backup)
        with open(_DIAGNOSIS_RULES_PATH, "w", encoding="utf-8") as f:
            _yaml.safe_dump(
                new_rules, f, allow_unicode=True, sort_keys=False, default_flow_style=False
            )
        # 重新加载
        global _DIAGNOSIS_RULES_CACHE, _DIAGNOSIS_RULES_LOADED
        _DIAGNOSIS_RULES_CACHE = new_rules
        _DIAGNOSIS_RULES_LOADED = True
        return True
    except Exception as e:
        logger.error(f"[signal_rules] save failed: {e}")
        return False
