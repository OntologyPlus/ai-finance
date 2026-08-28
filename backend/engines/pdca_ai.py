"""v12.1: 阶段 6 — PDCA 复盘 AI 智能引擎

提供 5 大 AI 能力：
1) AI 复盘叙事 — 自动生成 PDCA 复盘报告
2) AI 根因沉淀 — 跨周期根因跟踪
3) AI 建议闭环 — 建议项的执行追踪
4) AI 经验沉淀 — 知识库更新
5) AI 次年建议 — 基于本年数据生成下年改进建议
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.analysis import GapAnalysis, ListAnalysis, MonthlyReport
from models.budget import BudgetItem
from models.alert import AlertRecord


class PDCAAIEngine:
    """v12.1 阶段 6：PDCA 复盘 AI 智能引擎"""

    engine_name = "pdca_ai"

    # ─────────────────────────────────────────────────────
    # 1) AI 复盘叙事
    # ─────────────────────────────────────────────────────
    async def generate_review(
        self,
        period: str,  # YYYY
        center_id: Optional[str] = None,
        db: AsyncSession = None,
    ) -> Dict[str, Any]:
        """v12.1: 自动生成 PDCA 复盘报告（4 段式）"""
        try:
            stmt = select(BudgetItem)
            if center_id:
                stmt = stmt.where(BudgetItem.center_id == center_id)
            result = await db.execute(stmt)
            items = result.scalars().all()

            if not items:
                return {
                    "period": period,
                    "center_id": center_id,
                    "review": "无预算数据",
                    "highlights": [],
                    "issues": [],
                    "improvements": [],
                }

            # Plan
            total_annual = sum(float(i.annual_amount or 0) for i in items)
            strategic_items = [i for i in items if i.strategic_intent_l1]
            strategic_amount = sum(float(i.annual_amount or 0) for i in strategic_items)
            plan_summary = f"年度预算 ¥{total_annual:,.0f}，战略核心项目 {len(strategic_items)} 个（¥{strategic_amount:,.0f}）"

            # Do
            total_used = sum(float(i.used_amount or 0) for i in items)
            overall_rate = (total_used / total_annual * 100) if total_annual > 0 else 0
            do_summary = f"实际执行 ¥{total_used:,.0f}，执行率 {overall_rate:.1f}%"

            # Check
            overspend = [i for i in items if float(i.used_amount or 0) > float(i.annual_amount or 0)]
            underuse = [i for i in items if float(i.annual_amount or 0) > 0 and float(i.used_amount or 0) / float(i.annual_amount or 0) < 0.5]
            check_highlights = []
            check_issues = []
            if overall_rate >= 80 and overall_rate <= 100:
                check_highlights.append("整体执行节奏健康")
            if overspend:
                check_issues.append(f"{len(overspend)} 个项目超支（最高 {max(float(i.used_amount or 0) - float(i.annual_amount or 0) for i in overspend):,.0f}）")
            if underuse:
                check_issues.append(f"{len(underuse)} 个项目执行率 < 50%（沉淀风险）")

            # Act
            improvements = []
            if overspend:
                improvements.append("建立预算预警机制（80% 触发橙色，95% 触发红色）")
            if underuse:
                improvements.append("Q3 中期复盘调整预算（避免年末大量沉淀）")
            if overall_rate > 100:
                improvements.append("重新校准预算编制方法（参考历史执行率 + 战略权重）")
            if not improvements:
                improvements.append("维持现有机制，季度回顾节奏")

            review = (
                f"【P】{plan_summary}。"
                f"【D】{do_summary}。"
                f"【C】{' / '.join(check_highlights) if check_highlights else '需关注'}；{' / '.join(check_issues) if check_issues else '无重大问题'}。"
                f"【A】{' / '.join(improvements)}"
            )

            return {
                "period": period,
                "center_id": center_id,
                "review": review,
                "highlights": check_highlights,
                "issues": check_issues,
                "improvements": improvements,
                "metrics": {
                    "total_annual": round(total_annual, 2),
                    "total_used": round(total_used, 2),
                    "execution_rate": round(overall_rate, 1),
                    "strategic_items": len(strategic_items),
                    "overspend_count": len(overspend),
                    "underuse_count": len(underuse),
                },
            }
        except Exception as e:
            logger.error(f"AI 复盘叙事失败: {e}")
            raise

    # ─────────────────────────────────────────────────────
    # 2) AI 根因沉淀
    # ─────────────────────────────────────────────────────
    async def persist_root_causes(
        self,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """v12.1: 根因沉淀 — 提取高频根因到知识库"""
        try:
            # 拉取所有 GapAnalysis 中的根因
            stmt = select(GapAnalysis)
            result = await db.execute(stmt)
            gaps = result.scalars().all()

            # 根因关键词聚类
            cause_counter: Counter = Counter()
            cause_samples: Dict[str, List] = defaultdict(list)
            for g in gaps:
                if g.root_cause:
                    # 简单关键词提取（取前 20 字作为分类 key）
                    key = g.root_cause[:20].strip()
                    cause_counter[key] += 1
                    if len(cause_samples[key]) < 3:
                        cause_samples[key].append({
                            "gap_id": g.gap_id,
                            "period": g.period,
                            "detail": g.root_cause,
                        })

            top_causes = []
            for key, count in cause_counter.most_common(10):
                top_causes.append({
                    "root_cause_pattern": key,
                    "occurrence_count": count,
                    "samples": cause_samples[key],
                    "severity": "高频" if count >= 5 else "中频" if count >= 3 else "低频",
                })

            return {
                "total_gap_analyses": len(gaps),
                "unique_root_causes": len(cause_counter),
                "top_persistent_causes": top_causes,
                "recommendation": "建议将高频根因纳入下年度预算编制标准 / 培训材料",
            }
        except Exception as e:
            logger.error(f"AI 根因沉淀失败: {e}")
            raise

    # ─────────────────────────────────────────────────────
    # 3) AI 建议闭环
    # ─────────────────────────────────────────────────────
    async def track_recommendations(
        self,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """v12.1: 建议闭环追踪 — 统计建议项的执行情况"""
        try:
            # 从 GapAnalysis 的 recommendations 字段中提取
            stmt = select(GapAnalysis)
            result = await db.execute(stmt)
            gaps = result.scalars().all()

            all_recommendations: List[Dict] = []
            for g in gaps:
                if g.recommendations:
                    try:
                        recs = json.loads(g.recommendations) if isinstance(g.recommendations, str) else g.recommendations
                        for r in recs:
                            all_recommendations.append({
                                "gap_id": g.gap_id,
                                "period": g.period,
                                "recommendation": r,
                            })
                    except (json.JSONDecodeError, TypeError):
                        pass

            return {
                "total_gaps": len(gaps),
                "total_recommendations": len(all_recommendations),
                "avg_recommendations_per_gap": round(len(all_recommendations) / max(len(gaps), 1), 2),
                "recommendations": all_recommendations[:20],
                "recommendation": "建立建议项执行台账（责任人/截止时间/状态）",
            }
        except Exception as e:
            logger.error(f"AI 建议闭环失败: {e}")
            raise

    # ─────────────────────────────────────────────────────
    # 4) AI 经验沉淀
    # ─────────────────────────────────────────────────────
    async def extract_lessons(
        self,
        period: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """v12.1: 经验沉淀 — 提取可复用的经验"""
        try:
            stmt = select(GapAnalysis).where(GapAnalysis.period.like(f"{period[:7]}%"))
            result = await db.execute(stmt)
            gaps = result.scalars().all()

            lessons: List[Dict] = []
            for g in gaps:
                if g.lessons_learned:
                    lessons.append({
                        "gap_id": g.gap_id,
                        "period": g.period,
                        "lesson": g.lessons_learned,
                    })

            return {
                "period": period,
                "gap_count": len(gaps),
                "lesson_count": len(lessons),
                "lessons": lessons,
                "recommendation": "将经验沉淀到知识库，供次年预算编制参考",
            }
        except Exception as e:
            logger.error(f"AI 经验沉淀失败: {e}")
            raise

    # ─────────────────────────────────────────────────────
    # 5) AI 次年建议
    # ─────────────────────────────────────────────────────
    async def next_cycle_suggestion(
        self,
        center_id: Optional[str],
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """v12.1: 次年改进建议 — 基于本年数据"""
        try:
            stmt = select(BudgetItem)
            if center_id:
                stmt = stmt.where(BudgetItem.center_id == center_id)
            result = await db.execute(stmt)
            items = result.scalars().all()

            suggestions: List[Dict] = []
            for item in items:
                annual = float(item.annual_amount or 0)
                used = float(item.used_amount or 0)
                rate = (used / annual * 100) if annual > 0 else 0
                if rate > 100:
                    suggestions.append({
                        "type": "追加",
                        "budget_id": item.budget_id,
                        "budget_name": item.budget_name,
                        "this_year_rate": round(rate, 1),
                        "next_year_suggestion": f"追加 {round((rate - 100) / 100 * annual, 0):,.0f}（{rate - 100:.0f}%）",
                        "priority": "高",
                    })
                elif rate < 50 and annual > 0:
                    suggestions.append({
                        "type": "核减",
                        "budget_id": item.budget_id,
                        "budget_name": item.budget_name,
                        "this_year_rate": round(rate, 1),
                        "next_year_suggestion": f"核减至 {round(used * 1.2, 0):,.0f}（执行率仅 {rate:.0f}%）",
                        "priority": "中",
                    })
                elif 50 <= rate <= 100:
                    suggestions.append({
                        "type": "维持",
                        "budget_id": item.budget_id,
                        "budget_name": item.budget_name,
                        "this_year_rate": round(rate, 1),
                        "next_year_suggestion": f"维持 {annual:,.0f}（执行率 {rate:.0f}%）",
                        "priority": "低",
                    })

            suggestion_summary = {
                "追加": sum(1 for s in suggestions if s["type"] == "追加"),
                "核减": sum(1 for s in suggestions if s["type"] == "核减"),
                "维持": sum(1 for s in suggestions if s["type"] == "维持"),
            }

            return {
                "center_id": center_id,
                "total_items": len(items),
                "suggestion_summary": suggestion_summary,
                "suggestions": suggestions,
            }
        except Exception as e:
            logger.error(f"AI 次年建议失败: {e}")
            raise
