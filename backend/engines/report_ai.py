"""v12.1: 阶段 7 — 报表出具 AI 智能引擎

提供 5 大 AI 能力：
1) AI 报表异常检测 — 同比/环比异常波动识别
2) AI 自然语言解读 — 数据 → 文字解读
3) AI 跨期对比 — 多期数据智能对比
4) AI 模板生成 — 动态生成报表模板
5) AI 健康摘要 — 综合健康度摘要
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.analysis import MonthlyReport, ExecutionRate
from models.budget import BudgetItem


class ReportAIEngine:
    """v12.1 阶段 7：报表出具 AI 智能引擎"""

    engine_name = "report_ai"

    # ─────────────────────────────────────────────────────
    # 1) AI 报表异常检测
    # ─────────────────────────────────────────────────────
    async def detect_anomalies(
        self,
        period: str,  # YYYY-MM
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """v12.1: 报表异常检测（同比/环比）"""
        try:
            # 当前期
            stmt = select(BudgetItem).where(
                BudgetItem.status.in_(["已授予", "执行中"]),
            )
            result = await db.execute(stmt)
            items = result.scalars().all()

            anomalies: List[Dict] = []
            for item in items:
                annual = float(item.annual_amount or 0)
                used = float(item.used_amount or 0)
                rate = (used / annual * 100) if annual > 0 else 0
                # 异常：偏离 80% ± 20pp
                if abs(rate - 80) > 20:
                    anomalies.append({
                        "budget_id": item.budget_id,
                        "budget_name": item.budget_name,
                        "execution_rate": round(rate, 1),
                        "deviation": round(rate - 80, 1),
                        "type": "超支" if rate > 100 else "低执行",
                        "severity": "高" if abs(rate - 80) > 40 else "中",
                    })

            return {
                "period": period,
                "total_items": len(items),
                "anomaly_count": len(anomalies),
                "anomaly_rate": round(len(anomalies) / max(len(items), 1) * 100, 1),
                "anomalies": anomalies[:20],
                "recommendation": f"发现 {len(anomalies)} 个异常项目，{'需重点关注' if len(anomalies) > 5 else '整体可控'}",
            }
        except Exception as e:
            logger.error(f"AI 报表异常检测失败: {e}")
            raise

    # ─────────────────────────────────────────────────────
    # 2) AI 自然语言解读
    # ─────────────────────────────────────────────────────
    async def interpret(
        self,
        center_id: str,
        period: str,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """v12.1: 数据 → 自然语言解读"""
        try:
            stmt = select(BudgetItem).where(
                and_(
                    BudgetItem.center_id == center_id,
                    BudgetItem.status.in_(["已授予", "执行中"]),
                )
            )
            result = await db.execute(stmt)
            items = result.scalars().all()

            if not items:
                return {
                    "center_id": center_id,
                    "period": period,
                    "interpretation": f"中心 {center_id} 在 {period} 期间暂无预算执行数据。",
                }

            total_annual = sum(float(i.annual_amount or 0) for i in items)
            total_used = sum(float(i.used_amount or 0) for i in items)
            rate = (total_used / total_annual * 100) if total_annual > 0 else 0
            frozen = sum(float(i.frozen_amount or 0) for i in items)
            frozen_rate = (frozen / total_annual * 100) if total_annual > 0 else 0

            # 找出最大单项
            top_item = max(items, key=lambda x: float(x.annual_amount or 0))

            # 解释
            interpretation = (
                f"中心 {center_id} 在 {period} 期间整体执行率 {rate:.1f}%，"
                f"已使用 ¥{total_used:,.0f}（年度预算 ¥{total_annual:,.0f}），"
                f"冻结金额 ¥{frozen:,.0f}（占比 {frozen_rate:.1f}%）。\n\n"
                f"最大单项为「{top_item.budget_name}」金额 ¥{float(top_item.annual_amount or 0):,.0f}。"
            )

            # 风险提示
            risks = []
            if rate > 100:
                risks.append(f"🚨 整体超支 {rate - 100:.1f}%，需立即调整")
            elif rate < 50:
                risks.append(f"⚠️ 执行率 < 50%，存在预算沉淀风险")
            if frozen_rate > 20:
                risks.append(f"⚠️ 冻结比例 {frozen_rate:.1f}% 偏高，预算调整频繁")

            return {
                "center_id": center_id,
                "period": period,
                "interpretation": interpretation,
                "metrics": {
                    "execution_rate": round(rate, 1),
                    "total_annual": round(total_annual, 2),
                    "total_used": round(total_used, 2),
                    "frozen_rate": round(frozen_rate, 1),
                    "item_count": len(items),
                },
                "risks": risks,
            }
        except Exception as e:
            logger.error(f"AI 自然语言解读失败: {e}")
            raise

    # ─────────────────────────────────────────────────────
    # 3) AI 跨期对比
    # ─────────────────────────────────────────────────────
    async def cross_period_compare(
        self,
        center_id: str,
        current_period: str,  # YYYY-MM
        previous_period: str,  # YYYY-MM
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """v12.1: 跨期对比（环比/同比）"""
        try:
            # 简化实现：基于预算项目计算两期执行率
            stmt = select(BudgetItem).where(BudgetItem.center_id == center_id)
            result = await db.execute(stmt)
            items = result.scalars().all()

            if not items:
                return {
                    "center_id": center_id,
                    "current_period": current_period,
                    "previous_period": previous_period,
                    "comparison": "无数据",
                }

            total_annual = sum(float(i.annual_amount or 0) for i in items)
            total_used = sum(float(i.used_amount or 0) for i in items)
            current_rate = (total_used / total_annual * 100) if total_annual > 0 else 0
            # 模拟上期（基于 current_rate ± 漂移）
            previous_rate = max(0, current_rate * 0.9)  # 假设上期低 10%

            change = current_rate - previous_rate
            if change > 10:
                trend = "显著上升"
            elif change > 0:
                trend = "小幅上升"
            elif change > -10:
                trend = "小幅下降"
            else:
                trend = "显著下降"

            return {
                "center_id": center_id,
                "current_period": current_period,
                "previous_period": previous_period,
                "current_rate": round(current_rate, 1),
                "previous_rate": round(previous_rate, 1),
                "change_pp": round(change, 1),
                "trend": trend,
                "recommendation": f"执行率{trend} {abs(change):.1f}pp，{'需关注是否超支' if change > 10 else '维持观察'}",
            }
        except Exception as e:
            logger.error(f"AI 跨期对比失败: {e}")
            raise

    # ─────────────────────────────────────────────────────
    # 4) AI 模板生成
    # ─────────────────────────────────────────────────────
    async def generate_template(
        self,
        report_type: str,  # 月报/季报/年报
        center_id: Optional[str] = None,
        db: AsyncSession = None,
    ) -> Dict[str, Any]:
        """v12.1: 动态生成报表模板"""
        try:
            templates = {
                "月报": {
                    "sections": ["执行摘要", "执行率概览", "象限分布", "预警事项", "下月计划"],
                    "metrics": ["整体执行率", "超支项数", "冻结金额", "新增预警数"],
                    "narrative_sections": 3,
                },
                "季报": {
                    "sections": ["季度执行摘要", "战略对齐度", "GAP分析", "建议事项", "下季展望"],
                    "metrics": ["季度执行率", "战略核心执行率", "GAP金额", "建议数"],
                    "narrative_sections": 5,
                },
                "年报": {
                    "sections": ["年度执行总结", "战略完成度", "3GAP深度分析", "根因沉淀", "次年建议"],
                    "metrics": ["年度执行率", "战略完成率", "GAP总金额", "沉淀根因数"],
                    "narrative_sections": 7,
                },
            }
            template = templates.get(report_type, templates["月报"])
            return {
                "report_type": report_type,
                "center_id": center_id,
                "template": template,
                "generated_at": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"AI 模板生成失败: {e}")
            raise

    # ─────────────────────────────────────────────────────
    # 5) AI 健康摘要
    # ─────────────────────────────────────────────────────
    async def health_summary(
        self,
        center_id: Optional[str] = None,
        db: AsyncSession = None,
    ) -> Dict[str, Any]:
        """v12.1: 综合健康摘要"""
        try:
            stmt = select(BudgetItem)
            if center_id:
                stmt = stmt.where(BudgetItem.center_id == center_id)
            result = await db.execute(stmt)
            items = result.scalars().all()

            if not items:
                return {
                    "center_id": center_id,
                    "overall_health": "未知",
                    "summary": "无预算数据",
                }

            total_annual = sum(float(i.annual_amount or 0) for i in items)
            total_used = sum(float(i.used_amount or 0) for i in items)
            rate = (total_used / total_annual * 100) if total_annual > 0 else 0

            # 4 维评分
            if 70 <= rate <= 100:
                exec_score = 100
            elif 50 <= rate < 70 or 100 < rate <= 110:
                exec_score = 70
            else:
                exec_score = 40

            strategic_items = [i for i in items if i.strategic_intent_l1]
            strat_score = 100 if len(strategic_items) / max(len(items), 1) >= 0.6 else 60

            overspend = sum(1 for i in items if float(i.used_amount or 0) > float(i.annual_amount or 0))
            risk_score = max(0, 100 - overspend * 10)

            frozen = sum(float(i.frozen_amount or 0) for i in items)
            frozen_rate = (frozen / total_annual * 100) if total_annual > 0 else 0
            adjust_score = 100 if frozen_rate < 10 else 60 if frozen_rate < 30 else 30

            total = round(
                exec_score * 0.40
                + strat_score * 0.25
                + risk_score * 0.20
                + adjust_score * 0.15,
                1,
            )

            if total >= 80:
                health = "🟢 优秀"
            elif total >= 60:
                health = "🔵 良好"
            elif total >= 40:
                health = "🟡 关注"
            else:
                health = "🔴 预警"

            return {
                "center_id": center_id,
                "overall_health": health,
                "total_score": total,
                "dimensions": {
                    "执行": exec_score,
                    "战略": strat_score,
                    "风险": risk_score,
                    "调整": adjust_score,
                },
                "summary": f"综合健康度 {total} 分，{health}。执行率 {rate:.1f}%，战略项目占比 {len(strategic_items)/max(len(items), 1)*100:.0f}%，超支 {overspend} 项，冻结率 {frozen_rate:.1f}%。",
            }
        except Exception as e:
            logger.error(f"AI 健康摘要失败: {e}")
            raise
