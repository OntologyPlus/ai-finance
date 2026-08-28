"""
智能现金流调拨建议引擎

按《经营分析方法论.md》§4.2 现金流分析 + §4.1 主动建议实现：
- 当流动性缺口发生时，智能推荐从哪个资金池拨付
- 优先级：保留下方资金流动性 > 调拨成本 > 调拨时效
- 触发主动建议（critical 级别）：ProactiveAdvisor 集成入口
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.cash_flow import CashPool


@dataclass
class TransferRecommendation:
    """单笔调拨建议"""
    from_pool_id: int
    from_pool_name: str
    to_pool_id: int
    to_pool_name: str
    amount: float
    priority: int  # 1=最高
    reasoning: str
    risk_score: float  # 0-1，越低越安全
    estimated_days: int  # 预计到账天数


@dataclass
class TransferPlan:
    """调拨计划（多笔组合）"""
    gap_amount: float
    total_recommended: float
    coverage_pct: float
    recommendations: List[TransferRecommendation]
    unmeet_amount: float  # 仍无法覆盖的金额
    fallback_action: str
    signal_light: str
    light_reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gap_amount": round(self.gap_amount, 2),
            "total_recommended": round(self.total_recommended, 2),
            "coverage_pct": round(self.coverage_pct * 100, 2),
            "recommendations": [
                {
                    "from_pool_id": r.from_pool_id,
                    "from_pool_name": r.from_pool_name,
                    "to_pool_id": r.to_pool_id,
                    "to_pool_name": r.to_pool_name,
                    "amount": round(r.amount, 2),
                    "priority": r.priority,
                    "reasoning": r.reasoning,
                    "risk_score": round(r.risk_score, 3),
                    "estimated_days": r.estimated_days,
                }
                for r in self.recommendations
            ],
            "unmeet_amount": round(self.unmeet_amount, 2),
            "fallback_action": self.fallback_action,
            "signal_light": self.signal_light,
            "light_reason": self.light_reason,
        }


class CashflowAdvisorEngine:
    """智能调拨建议引擎

    核心算法（按方法论 §4.2）：
    1. 收集所有活跃资金池
    2. 对每个资金池计算"安全可调出金额" = balance - min_balance - alert_threshold
    3. 按风险评分（越低越优先）排序
    4. 按优先级累加，直到覆盖 gap
    5. 不足部分给出 fallback action（融资/AR 催收/延期付款）
    """

    def __init__(self) -> None:
        self.today = datetime.now()

    async def recommend_transfer(
        self,
        db: AsyncSession,
        target_pool_id: int,
        gap_amount: float,
        horizon_days: int = 7,
    ) -> TransferPlan:
        """为指定目标资金池生成调拨建议

        Args:
            db: 异步数据库会话
            target_pool_id: 目标资金池（接收调入）
            gap_amount: 缺口金额
            horizon_days: 期望到账天数

        Returns:
            TransferPlan 调拨计划
        """
        # 拉取所有活跃资金池
        pools = await self._fetch_active_pools(db)
        if not pools:
            return TransferPlan(
                gap_amount=gap_amount,
                total_recommended=0.0,
                coverage_pct=0.0,
                recommendations=[],
                unmeet_amount=gap_amount,
                fallback_action="无可用资金池，建议启动外部融资",
                signal_light="red",
                light_reason="无活跃资金池可调拨",
            )

        target = next((p for p in pools if p.id == target_pool_id), None)
        if not target:
            return TransferPlan(
                gap_amount=gap_amount,
                total_recommended=0.0,
                coverage_pct=0.0,
                recommendations=[],
                unmeet_amount=gap_amount,
                fallback_action=f"目标资金池 #{target_pool_id} 不存在",
                signal_light="red",
                light_reason=f"目标资金池 #{target_pool_id} 不存在",
            )

        # 计算各池"安全可调出"金额
        candidates: List[Dict[str, Any]] = []
        for p in pools:
            if p.id == target_pool_id:
                continue
            safe_amount = max(0.0, p.total_balance - p.min_balance - p.alert_threshold)
            if safe_amount <= 0:
                continue
            # 风险评分：基于"剩余流动性比例"和"调拨到目标池距离"（简化：池内金额越多越安全）
            liquidity_ratio = (p.total_balance - p.min_balance) / max(p.total_balance, 1.0)
            risk_score = 1.0 - liquidity_ratio  # 流动性越高风险越低
            candidates.append({
                "pool": p,
                "safe_amount": safe_amount,
                "risk_score": risk_score,
                "estimated_days": self._estimate_transfer_days(p, target),
            })

        # 按优先级排序：(1) 到账天数最少 (2) 风险最低
        candidates.sort(key=lambda c: (c["estimated_days"], c["risk_score"]))

        recommendations: List[TransferRecommendation] = []
        remaining_gap = gap_amount
        for idx, cand in enumerate(candidates):
            if remaining_gap <= 0:
                break
            amount = min(remaining_gap, cand["safe_amount"])
            rec = TransferRecommendation(
                from_pool_id=cand["pool"].id,
                from_pool_name=cand["pool"].pool_name,
                to_pool_id=target.id,
                to_pool_name=target.pool_name,
                amount=amount,
                priority=idx + 1,
                reasoning=(
                    f"从「{cand['pool'].pool_name}」调拨 {amount:,.0f}，"
                    f"调拨后该池保留 {cand['pool'].total_balance - amount:,.0f} "
                    f"（最低 {cand['pool'].min_balance:,.0f}）"
                ),
                risk_score=cand["risk_score"],
                estimated_days=cand["estimated_days"],
            )
            recommendations.append(rec)
            remaining_gap -= amount

        total_recommended = sum(r.amount for r in recommendations)
        coverage_pct = (total_recommended / gap_amount) if gap_amount > 0 else 1.0
        unmeet = max(0.0, remaining_gap)

        if unmeet > 0:
            fallback = self._build_fallback_action(unmeet, target)
            signal = "red"
            reason = f"调拨建议可覆盖 {coverage_pct*100:.1f}%，缺口 {unmeet:,.0f} 需 fallback"
        elif coverage_pct >= 0.9:
            signal = "green"
            reason = f"调拨建议可覆盖 {coverage_pct*100:.1f}%，流动性风险解除"
            fallback = "无需 fallback"
        else:
            signal = "yellow"
            reason = f"调拨建议可覆盖 {coverage_pct*100:.1f}%，部分缓解"
            fallback = "建议加强回款以减少对外调拨依赖"

        return TransferPlan(
            gap_amount=gap_amount,
            total_recommended=total_recommended,
            coverage_pct=coverage_pct,
            recommendations=recommendations,
            unmeet_amount=unmeet,
            fallback_action=fallback,
            signal_light=signal,
            light_reason=reason,
        )

    def _estimate_transfer_days(self, from_pool: CashPool, to_pool: CashPool) -> int:
        """估算调拨到账天数（简化：同法人 1 天，跨法人 3 天，跨行 5 天）"""
        # 实际场景应基于池的"法人归属"和"开户行"
        # 这里用 ID 差异作为简化代理（同 id 簇 = 1 天）
        if from_pool.id == to_pool.id:
            return 0
        return 1  # 简化默认值

    def _build_fallback_action(self, unmeet: float, target: CashPool) -> str:
        if unmeet > 1_000_000:
            return f"缺口 {unmeet:,.0f} 超过内部调拨能力，建议启动银行融资或动用授信额度"
        elif unmeet > 100_000:
            return f"缺口 {unmeet:,.0f} 建议：① 加强 60+ 天 AR 催收 ② 延后非紧急付款"
        else:
            return f"小额缺口 {unmeet:,.0f} 建议：调整下周付款节奏即可覆盖"

    async def _fetch_active_pools(self, db: AsyncSession) -> List[CashPool]:
        stmt = select(CashPool).where(CashPool.status == "活跃")
        result = await db.execute(stmt)
        return list(result.scalars().all())
