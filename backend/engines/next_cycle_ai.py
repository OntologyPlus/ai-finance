"""v12.1: 阶段 8 — 次年采集 AI 智能引擎

提供 5 大 AI 能力：
1) AI 次年预算建议 — 基于本年执行+历史趋势
2) AI 战略对齐 — 战略意图与预算的匹配度
3) AI 采集异常检测 — 采集数据完整性+合规性
4) AI 模板生成 — 动态采集模板
5) AI 智能建议 — 综合改进建议
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.budget import BudgetItem
from models.strategic import StrategicInitiative
from models.analysis import ExecutionRate


class NextCycleAIEngine:
    """v12.1 阶段 8：次年采集 AI 智能引擎"""

    engine_name = "next_cycle_ai"

    # ─────────────────────────────────────────────────────
    # 1) AI 次年预算建议
    # ─────────────────────────────────────────────────────
    async def budget_suggestion(
        self,
        center_id: Optional[str],
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """v12.1: 基于本年执行+历史+战略权重生成次年预算建议"""
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

                # 智能调整因子
                if rate > 110:
                    factor = 1.2  # 严重超支，加 20%
                elif rate > 100:
                    factor = 1.1
                elif rate < 30:
                    factor = 0.6
                elif rate < 50:
                    factor = 0.8
                elif 50 <= rate <= 100:
                    factor = 1.0
                else:
                    factor = 0.9

                # 战略权重加成
                if item.quadrant == "发展" and item.strategic_intent_l1:
                    factor += 0.1
                elif item.quadrant == "收缩":
                    factor -= 0.1

                suggested = round(annual * factor, 0)
                suggestions.append({
                    "budget_id": item.budget_id,
                    "budget_name": item.budget_name,
                    "l1_code": item.l1_code,
                    "quadrant": item.quadrant,
                    "this_year_amount": annual,
                    "this_year_rate": round(rate, 1),
                    "factor": round(factor, 2),
                    "next_year_suggestion": suggested,
                    "delta": round(suggested - annual, 0),
                    "action": "追加" if suggested > annual else "核减" if suggested < annual else "维持",
                })

            # 汇总
            total_this = sum(s["this_year_amount"] for s in suggestions)
            total_next = sum(s["next_year_suggestion"] for s in suggestions)
            action_count = Counter(s["action"] for s in suggestions)

            return {
                "center_id": center_id,
                "total_this_year": round(total_this, 2),
                "total_next_year": round(total_next, 2),
                "delta": round(total_next - total_this, 2),
                "delta_pct": round((total_next - total_this) / max(total_this, 1) * 100, 1),
                "action_summary": dict(action_count),
                "suggestions": suggestions,
            }
        except Exception as e:
            logger.error(f"AI 次年预算建议失败: {e}")
            raise

    # ─────────────────────────────────────────────────────
    # 2) AI 战略对齐
    # ─────────────────────────────────────────────────────
    async def strategic_alignment(
        self,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """v12.1: 战略对齐度评估"""
        try:
            stmt = select(BudgetItem)
            result = await db.execute(stmt)
            items = result.scalars().all()

            stmt_init = select(StrategicInitiative)
            result_init = await db.execute(stmt_init)
            initiatives = result_init.scalars().all()

            # 战略意图分布
            intent_distribution: Counter = Counter()
            for i in items:
                if i.strategic_intent_l1:
                    intent_distribution[i.strategic_intent_l1] += 1

            # 象限分布
            quadrant_distribution: Counter = Counter()
            for i in items:
                quadrant_distribution[i.quadrant or "未分类"] += 1

            # 战略项目占比
            strategic_items = [i for i in items if i.strategic_intent_l1]
            strategic_ratio = len(strategic_items) / max(len(items), 1) * 100

            # 对齐评分
            if strategic_ratio >= 70:
                score = 100
            elif strategic_ratio >= 50:
                score = 80
            elif strategic_ratio >= 30:
                score = 60
            else:
                score = 40

            return {
                "total_budget_items": len(items),
                "strategic_items": len(strategic_items),
                "strategic_ratio": round(strategic_ratio, 1),
                "alignment_score": score,
                "intent_distribution": dict(intent_distribution),
                "quadrant_distribution": dict(quadrant_distribution),
                "initiative_count": len(initiatives),
                "recommendation": (
                    "战略对齐度高" if score >= 80 else
                    "战略对齐度中等，建议增加战略核心项目" if score >= 60 else
                    "战略对齐度偏低，需重新审视战略-预算联动"
                ),
            }
        except Exception as e:
            logger.error(f"AI 战略对齐失败: {e}")
            raise

    # ─────────────────────────────────────────────────────
    # 3) AI 采集异常检测
    # ─────────────────────────────────────────────────────
    async def harvest_anomalies(
        self,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """v12.1: 采集数据异常检测"""
        try:
            stmt = select(BudgetItem)
            result = await db.execute(stmt)
            items = result.scalars().all()

            anomalies: List[Dict] = []
            for item in items:
                # 1) 缺失战略意图
                if not item.strategic_intent_l1 and float(item.annual_amount or 0) > 10000:
                    anomalies.append({
                        "budget_id": item.budget_id,
                        "type": "缺失战略意图",
                        "severity": "中",
                        "detail": f"金额 ¥{float(item.annual_amount or 0):,.0f} > 1万 但无战略意图",
                    })
                # 2) 缺失象限
                if not item.quadrant:
                    anomalies.append({
                        "budget_id": item.budget_id,
                        "type": "缺失象限",
                        "severity": "中",
                        "detail": "未分配象限",
                    })
                # 3) 缺失 L2
                if not item.l2_code:
                    anomalies.append({
                        "budget_id": item.budget_id,
                        "type": "缺失L2科目",
                        "severity": "低",
                        "detail": "未细化L2科目",
                    })
                # 4) 异常金额
                annual = float(item.annual_amount or 0)
                if annual <= 0:
                    anomalies.append({
                        "budget_id": item.budget_id,
                        "type": "零金额",
                        "severity": "高",
                        "detail": "年金额为 0 或缺失",
                    })
                elif annual > 10000000:  # 1000 万
                    anomalies.append({
                        "budget_id": item.budget_id,
                        "type": "超大金额",
                        "severity": "中",
                        "detail": f"年金额 ¥{annual:,.0f} > 1000万，建议拆分",
                    })

            return {
                "total_items": len(items),
                "anomaly_count": len(anomalies),
                "completeness": round((1 - len(set(a["budget_id"] for a in anomalies)) / max(len(items), 1)) * 100, 1),
                "anomalies": anomalies[:30],
                "recommendation": "建议补全缺失字段后再执行采集" if anomalies else "数据完整，无异常",
            }
        except Exception as e:
            logger.error(f"AI 采集异常检测失败: {e}")
            raise

    # ─────────────────────────────────────────────────────
    # 4) AI 采集模板生成
    # ─────────────────────────────────────────────────────
    async def generate_harvest_template(
        self,
        center_id: Optional[str] = None,
        db: AsyncSession = None,
    ) -> Dict[str, Any]:
        """v12.1: 动态生成采集模板"""
        try:
            template = {
                "version": "v12.1",
                "fields": [
                    {"name": "budget_id", "type": "string", "required": True, "example": "BG-2026-XXX"},
                    {"name": "budget_name", "type": "string", "required": True, "example": "市场推广费"},
                    {"name": "l1_code", "type": "string", "required": True, "example": "01"},
                    {"name": "l2_code", "type": "string", "required": False, "example": "01-01"},
                    {"name": "l3_code", "type": "string", "required": False, "example": "01-01-01"},
                    {"name": "strategic_intent_l1", "type": "enum", "required": True, "options": ["全渠道商业化", "创新研发", "国际化"]},
                    {"name": "quadrant", "type": "enum", "required": True, "options": ["发展", "稳定", "收缩", "探索"]},
                    {"name": "annual_amount", "type": "number", "required": True, "min": 0, "example": 1000000},
                    {"name": "priority", "type": "enum", "required": False, "options": ["high", "medium", "low"]},
                    {"name": "center_id", "type": "string", "required": True},
                    {"name": "description", "type": "string", "required": False, "max_length": 500},
                ],
                "validation_rules": [
                    "strategic_intent_l1 与 quadrant 必填",
                    "annual_amount > 0",
                    "l1_code 必须在 BudgetSubjectL1 中存在",
                ],
            }
            return {
                "center_id": center_id,
                "template": template,
                "generated_at": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"AI 采集模板生成失败: {e}")
            raise

    # ─────────────────────────────────────────────────────
    # 5) AI 智能建议
    # ─────────────────────────────────────────────────────
    async def intelligence(
        self,
        center_id: Optional[str] = None,
        db: AsyncSession = None,
    ) -> Dict[str, Any]:
        """v12.1: 综合次年智能建议"""
        try:
            budget = await self.budget_suggestion(center_id, db)
            alignment = await self.strategic_alignment(db)
            anomalies = await self.harvest_anomalies(db)

            intelligence_items: List[Dict] = []
            priority = 0

            # 来源 1: 预算调整
            for s in budget.get("suggestions", []):
                if s["action"] in ["追加", "核减"] and abs(s["delta"]) > 100000:
                    priority += 1
                    intelligence_items.append({
                        "priority": priority,
                        "category": "预算调整",
                        "title": f"{s['action']}：{s['budget_name'][:30]}",
                        "detail": f"本年 ¥{s['this_year_amount']:,.0f}（执行率 {s['this_year_rate']}%）→ 次年建议 ¥{s['next_year_suggestion']:,.0f}",
                        "delta": s["delta"],
                    })
                    if priority >= 3:
                        break

            # 来源 2: 战略对齐
            if alignment.get("alignment_score", 100) < 60:
                priority += 1
                intelligence_items.append({
                    "priority": priority,
                    "category": "战略对齐",
                    "title": f"战略对齐度 {alignment['alignment_score']} 偏低",
                    "detail": alignment.get("recommendation", ""),
                })

            # 来源 3: 采集异常
            if anomalies.get("anomaly_count", 0) > 0:
                priority += 1
                intelligence_items.append({
                    "priority": priority,
                    "category": "采集质量",
                    "title": f"{anomalies['anomaly_count']} 个采集异常",
                    "detail": f"数据完整度 {anomalies.get('completeness', 0)}%",
                })

            return {
                "center_id": center_id,
                "budget_summary": {
                    "total_this_year": budget.get("total_this_year", 0),
                    "total_next_year": budget.get("total_next_year", 0),
                    "delta_pct": budget.get("delta_pct", 0),
                },
                "alignment_score": alignment.get("alignment_score", 0),
                "anomaly_count": anomalies.get("anomaly_count", 0),
                "intelligence_items": intelligence_items,
            }
        except Exception as e:
            logger.error(f"AI 智能建议失败: {e}")
            raise
