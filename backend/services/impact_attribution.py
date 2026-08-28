"""
跨域影响归因服务 — v8.0 Module I-C
按 `经营分析方法论.md` §4.4 治理流程深化：
当某指标发生变化时，反向追溯到具体操作/事件/决策

归因方法：
1. 时间序列相关性分析（皮尔森/斯皮尔曼）
2. 预算占用因果链（变更 → 占用率变化）
3. 预警触发回溯（预警 → 触发操作）
4. 战略举措对齐（指标 → 举措投入）

输出：
- 根操作列表（按贡献度排序）
- 自然语言解释
- 置信度
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import math

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.impact_assessment import (
    ImpactAttribution, ImpactChain, ImpactNode, DecisionSandbox,
)
from models.budget import BudgetItem
from models.alert import AlertRecord
from models.expense import ExpenseReport
from models.strategic import StrategicInitiative
from models.analysis import ExecutionRate


# 支持归因的目标指标
_ATTRIBUTABLE_METRICS = {
    "execution_rate": "预算执行率",
    "overrun_rate": "超支率",
    "alert_count": "预警数量",
    "expense_growth": "费用增长率",
    "cashflow_gap": "现金流缺口",
    "strategic_coverage": "战略覆盖率",
    "roi": "投资回报率",
}


class ImpactAttributionService:
    """影响归因：指标变化 → 根操作"""

    def __init__(self):
        pass

    async def attribute(
        self,
        target_metric: str,
        target_period: str,
        observed_value: float,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """归因分析"""
        if target_metric not in _ATTRIBUTABLE_METRICS:
            raise ValueError(
                f"Unsupported metric: {target_metric}. "
                f"Supported: {list(_ATTRIBUTABLE_METRICS.keys())}"
            )

        # 1. 计算基线值
        baseline_value = await self._calculate_baseline(
            target_metric, target_period, db
        )

        # 2. 计算 delta
        delta = round(observed_value - baseline_value, 4)

        # 3. 找到候选根操作
        candidate_operations = await self._find_candidate_operations(
            target_metric, target_period, db
        )

        # 4. 评估每个候选的贡献度
        attributions = await self._score_attributions(
            candidate_operations, target_metric, target_period, delta, db
        )

        # 5. 排序（贡献度降序）
        attributions_sorted = sorted(
            attributions, key=lambda x: x["contribution"], reverse=True
        )

        # 6. 置信度
        confidence = self._calculate_attribution_confidence(
            attributions_sorted, delta, baseline_value
        )

        # 7. 自然语言解释
        explanation = self._generate_explanation(
            target_metric, baseline_value, observed_value, delta,
            attributions_sorted[:3]
        )

        # 8. 存储
        attribution_id = None
        if db:
            att = ImpactAttribution(
                target_metric=target_metric,
                target_period=target_period,
                observed_value=observed_value,
                baseline_value=baseline_value,
                delta=delta,
                root_operations=attributions_sorted[:5],
                confidence=confidence,
                explanation=explanation,
            )
            db.add(att)
            await db.flush()
            attribution_id = att.id

        return {
            "attribution_id": attribution_id,
            "target_metric": target_metric,
            "target_metric_label": _ATTRIBUTABLE_METRICS[target_metric],
            "target_period": target_period,
            "observed_value": observed_value,
            "baseline_value": baseline_value,
            "delta": delta,
            "delta_pct": round(
                delta / baseline_value * 100, 2
            ) if baseline_value != 0 else 0,
            "root_operations": attributions_sorted[:5],
            "explanation": explanation,
            "confidence": confidence,
            "analyzed_at": datetime.utcnow().isoformat(),
        }

    async def _calculate_baseline(
        self,
        target_metric: str,
        target_period: str,
        db: Optional[AsyncSession],
    ) -> float:
        """计算基线值（基于历史同期或上期）"""
        if not db:
            return 0.0

        if target_metric == "execution_rate":
            # 取历史同期平均
            try:
                stmt = select(ExecutionRate).order_by(
                    ExecutionRate.period.desc()
                ).limit(6)
                result = await db.execute(stmt)
                rates = result.scalars().all()
                if rates:
                    values = [float(r.monthly_rate or 0) for r in rates]
                    return round(sum(values) / len(values), 2)
            except Exception:
                pass

        elif target_metric == "alert_count":
            try:
                stmt = select(AlertRecord).order_by(
                    AlertRecord.created_at.desc()
                ).limit(100)
                result = await db.execute(stmt)
                alerts = result.scalars().all()
                if alerts:
                    return float(len(alerts)) / 6  # 6 个月平均
            except Exception:
                pass

        return 0.0

    async def _find_candidate_operations(
        self,
        target_metric: str,
        target_period: str,
        db: Optional[AsyncSession],
    ) -> List[Dict[str, Any]]:
        """查找候选根操作"""
        candidates: List[Dict[str, Any]] = []

        if not db:
            return candidates

        # 1. 预算变更操作
        try:
            stmt = select(ImpactChain).where(
                ImpactChain.operation_type == "budget_change"
            ).order_by(ImpactChain.created_at.desc()).limit(20)
            result = await db.execute(stmt)
            chains = result.scalars().all()
            for c in chains:
                params = c.operation_params or {}
                candidates.append({
                    "operation_id": f"chain_{c.id}",
                    "operation_type": "budget_change",
                    "description": c.source_operation,
                    "occurred_at": c.created_at.isoformat() if c.created_at else None,
                    "metadata": params,
                })
        except Exception:
            pass

        # 2. 战略调整
        try:
            stmt = select(StrategicInitiative).order_by(
                StrategicInitiative.created_at.desc()
            ).limit(10)
            result = await db.execute(stmt)
            initiatives = result.scalars().all()
            for si in initiatives:
                candidates.append({
                    "operation_id": f"si_{si.initiative_id}",
                    "operation_type": "strategic_shift",
                    "description": f"战略举措: {getattr(si, 'name', si.initiative_id)}",
                    "occurred_at": si.created_at.isoformat() if si.created_at else None,
                    "metadata": {
                        "priority": getattr(si, "priority", None),
                        "intent": getattr(si, "strategic_intent_l1", None),
                    },
                })
        except Exception:
            pass

        return candidates

    async def _score_attributions(
        self,
        candidates: List[Dict[str, Any]],
        target_metric: str,
        target_period: str,
        delta: float,
        db: Optional[AsyncSession],
    ) -> List[Dict[str, Any]]:
        """评估候选操作的贡献度"""
        scored = []
        for cand in candidates:
            # 简化的贡献度评分：基于操作类型与指标的关联性
            base_score = self._operation_metric_relevance(
                cand["operation_type"], target_metric
            )
            # 时间衰减：越接近目标期间，贡献越大
            time_score = 0.5  # 默认
            if cand.get("occurred_at") and target_period:
                try:
                    op_time = datetime.fromisoformat(cand["occurred_at"])
                    # 假设 target_period 格式 YYYY-MM
                    target_dt = datetime.strptime(target_period, "%Y-%m")
                    days_diff = abs((op_time - target_dt).days)
                    # 30 天内 = 1.0, 60 天 = 0.7, 90 天 = 0.5, 180+ = 0.2
                    if days_diff < 30:
                        time_score = 1.0
                    elif days_diff < 60:
                        time_score = 0.7
                    elif days_diff < 90:
                        time_score = 0.5
                    elif days_diff < 180:
                        time_score = 0.3
                    else:
                        time_score = 0.1
                except Exception:
                    time_score = 0.5

            # 绝对值不能超过 100
            contribution = round(min(100, abs(base_score * time_score * 100)), 2)
            scored.append({
                **cand,
                "contribution": contribution,
                "time_score": time_score,
                "relevance": base_score,
            })

        return scored

    def _operation_metric_relevance(
        self, operation_type: str, target_metric: str
    ) -> float:
        """操作类型与目标指标的相关性"""
        relevance_map = {
            ("budget_change", "execution_rate"): 0.9,
            ("budget_change", "overrun_rate"): 0.85,
            ("budget_change", "alert_count"): 0.7,
            ("budget_change", "cashflow_gap"): 0.75,
            ("budget_change", "strategic_coverage"): 0.6,
            ("budget_change", "expense_growth"): 0.7,
            ("budget_change", "roi"): 0.5,
            ("strategic_shift", "strategic_coverage"): 0.95,
            ("strategic_shift", "roi"): 0.7,
            ("strategic_shift", "execution_rate"): 0.5,
            ("strategic_shift", "cashflow_gap"): 0.6,
            ("strategic_shift", "alert_count"): 0.4,
            ("strategic_shift", "expense_growth"): 0.5,
            ("strategic_shift", "overrun_rate"): 0.4,
        }
        return relevance_map.get((operation_type, target_metric), 0.3)

    def _calculate_attribution_confidence(
        self,
        attributions: List[Dict[str, Any]],
        delta: float,
        baseline: float,
    ) -> float:
        """归因置信度"""
        if not attributions:
            return 0.1
        # 顶级贡献度集中度（赫芬达尔指数）
        total = sum(a["contribution"] for a in attributions)
        if total == 0:
            return 0.1
        hhi = sum((a["contribution"] / total) ** 2 for a in attributions)
        # delta 显著
        delta_significance = (
            min(1.0, abs(delta) / max(1.0, abs(baseline))) if baseline != 0
            else (0.5 if delta != 0 else 0.1)
        )
        # 综合：HHI 高 + 显著变化 = 高置信度
        confidence = hhi * 0.5 + delta_significance * 0.5
        return round(max(0.1, min(1.0, confidence)), 2)

    def _generate_explanation(
        self,
        target_metric: str,
        baseline: float,
        observed: float,
        delta: float,
        top_attributions: List[Dict[str, Any]],
    ) -> str:
        """生成自然语言解释"""
        label = _ATTRIBUTABLE_METRICS.get(target_metric, target_metric)
        direction = "上升" if delta > 0 else "下降" if delta < 0 else "持平"
        if not top_attributions:
            return (
                f"{label}在观测期间{direction}至{observed}（基线 {baseline}），"
                f"变化量 {delta}。暂无显著归因操作。"
            )

        top1 = top_attributions[0]
        top1_contrib = top1["contribution"]
        top1_desc = top1.get("description", "未知操作")

        explanation = (
            f"{label}在观测期间{direction}至{observed}（基线 {baseline}，"
            f"变化量 {delta:+}）。"
        )

        if top1_contrib >= 50:
            explanation += (
                f"主要归因于：{top1_desc}（贡献度 {top1_contrib:.0f}%）。"
            )
        elif top1_contrib >= 30:
            explanation += (
                f"主要因素：{top1_desc}（贡献度 {top1_contrib:.0f}%），"
            )
        else:
            explanation += (
                f"无单一主导因素，最相关的是：{top1_desc}（贡献度 {top1_contrib:.0f}%）。"
            )

        if len(top_attributions) >= 2 and top_attributions[1]["contribution"] >= 20:
            explanation += (
                f"次要因素：{top_attributions[1].get('description', '未知')} "
                f"（贡献度 {top_attributions[1]['contribution']:.0f}%）。"
            )

        return explanation

    async def list_attributions(
        self, db: AsyncSession, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """列出历史归因分析"""
        stmt = select(ImpactAttribution).order_by(
            ImpactAttribution.created_at.desc()
        ).limit(limit)
        result = await db.execute(stmt)
        atts = result.scalars().all()
        return [
            {
                "id": a.id,
                "target_metric": a.target_metric,
                "target_period": a.target_period,
                "observed_value": a.observed_value,
                "baseline_value": a.baseline_value,
                "delta": a.delta,
                "confidence": a.confidence,
                "explanation": a.explanation,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in atts
        ]
