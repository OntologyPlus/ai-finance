"""
智能审批人推荐引擎

按《经营分析方法论.md》§4.4 治理流程实现：
- 基于历史审批模式 + 角色 + 部门匹配
- 输出 Top-N 推荐 + 置信度
- Fallback：规则推荐（无历史数据时）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.approval_config import ApproverProfile


@dataclass
class ApproverRecommendation:
    """单条推荐"""
    user_id: str
    user_name: str
    role: str
    confidence: float  # 0-1
    reasoning: str
    estimated_hours: float
    risk_score: float  # 0-1，越低越安全


@dataclass
class ApproverRecommendResult:
    """推荐结果"""
    target_role: str
    center_id: Optional[str]
    l1_code: Optional[str]
    amount: float
    recommendations: List[ApproverRecommendation]
    fallback: str  # 未找到时给出兜底建议
    signal_light: str  # green/yellow/red
    light_reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_role": self.target_role,
            "center_id": self.center_id,
            "l1_code": self.l1_code,
            "amount": self.amount,
            "recommendations": [
                {
                    "user_id": r.user_id,
                    "user_name": r.user_name,
                    "role": r.role,
                    "confidence": round(r.confidence, 3),
                    "reasoning": r.reasoning,
                    "estimated_hours": round(r.estimated_hours, 1),
                    "risk_score": round(r.risk_score, 3),
                }
                for r in self.recommendations
            ],
            "fallback": self.fallback,
            "signal_light": self.signal_light,
            "light_reason": self.light_reason,
        }


class ApprovalRouter:
    """智能审批人推荐引擎

    排序规则（按方法论 §4.4）：
    1. 角色匹配（target_role 必匹配）
    2. 中心匹配（center_id 优先）
    3. 响应速度（avg_response_hours 越低越好）
    4. 驳回率（reject_rate 越低越好）
    5. 委派率（delegation_count 越低越好）
    """

    async def recommend_approvers(
        self,
        db: AsyncSession,
        target_role: str,
        center_id: Optional[str] = None,
        l1_code: Optional[str] = None,
        amount: float = 0.0,
        top_n: int = 3,
    ) -> ApproverRecommendResult:
        """推荐审批人

        Args:
            db: 异步数据库会话
            target_role: 目标角色（直属主管/部门负责人/财经BP/中心总经理/分管副总裁）
            center_id: 中心ID（优先匹配）
            l1_code: L1 科目代码（用于偏好匹配）
            amount: 审批金额（用于风险评估）
            top_n: 返回 Top N 个

        Returns:
            ApproverRecommendResult 推荐结果
        """
        # 1. 拉取所有匹配的审批人画像
        stmt = select(ApproverProfile).where(
            and_(
                ApproverProfile.role == target_role,
                ApproverProfile.is_active == 1,
            )
        )
        if center_id:
            stmt = stmt.where(
                (ApproverProfile.center_id == center_id) | (ApproverProfile.center_id.is_(None))
            )
        result = await db.execute(stmt)
        profiles = result.scalars().all()

        if not profiles:
            return ApproverRecommendResult(
                target_role=target_role,
                center_id=center_id,
                l1_code=l1_code,
                amount=amount,
                recommendations=[],
                fallback=f"无角色为「{target_role}」的活跃审批人，建议检查用户/角色配置",
                signal_light="red",
                light_reason=f"无可用审批人（角色={target_role}, 中心={center_id}）",
            )

        # 2. 计算综合得分（多维度）
        recommendations: List[ApproverRecommendation] = []
        for p in profiles:
            # 中心匹配加成
            center_match = 1.0 if (p.center_id == center_id or not p.center_id) else 0.5
            # 响应速度得分（24h 内为 1.0，48h+ 为 0.0）
            speed_score = max(0.0, min(1.0, 1.0 - (p.avg_response_hours - 12) / 36))
            # 驳回率反向得分
            reject_score = 1.0 - (p.reject_rate or 0.0)
            # 委派率反向得分
            delegation_score = max(0.0, 1.0 - (p.delegation_count or 0) / 10)
            # 综合得分（加权）
            confidence = (
                0.3 * center_match
                + 0.3 * speed_score
                + 0.2 * reject_score
                + 0.1 * delegation_score
                + 0.1 * min(1.0, (p.total_approved or 0) / 50)  # 经验加成
            )
            # 风险评分（金额越大风险越高）
            risk_score = min(1.0, amount / 1_000_000) if amount > 0 else 0.0

            reasoning = self._build_reasoning(p, center_match, speed_score, reject_score)
            recommendations.append(ApproverRecommendation(
                user_id=p.user_id,
                user_name=p.user_name or p.user_id,
                role=p.role,
                confidence=round(confidence, 3),
                reasoning=reasoning,
                estimated_hours=p.avg_response_hours or 24.0,
                risk_score=round(risk_score, 3),
            ))

        # 3. 排序 + Top N
        recommendations.sort(key=lambda r: -r.confidence)
        top_recs = recommendations[:top_n]

        # 4. 信号灯判定
        if not top_recs:
            signal = "red"
            reason = "无可用推荐"
        elif top_recs[0].confidence >= 0.7:
            signal = "green"
            reason = f"Top1 推荐置信度 {top_recs[0].confidence*100:.0f}%，质量良好"
        elif top_recs[0].confidence >= 0.4:
            signal = "yellow"
            reason = f"Top1 推荐置信度 {top_recs[0].confidence*100:.0f}%，建议人工确认"
        else:
            signal = "red"
            reason = f"Top1 推荐置信度仅 {top_recs[0].confidence*100:.0f}%，建议补全画像数据"

        return ApproverRecommendResult(
            target_role=target_role,
            center_id=center_id,
            l1_code=l1_code,
            amount=amount,
            recommendations=top_recs,
            fallback="",
            signal_light=signal,
            light_reason=reason,
        )

    def _build_reasoning(
        self, profile: ApproverProfile, center_match: float,
        speed_score: float, reject_score: float
    ) -> str:
        reasons = []
        if center_match >= 1.0 and profile.center_id:
            reasons.append(f"同中心({profile.center_id})")
        elif center_match >= 0.5:
            reasons.append("跨中心可处理")
        if speed_score >= 0.7:
            reasons.append(f"响应快({profile.avg_response_hours:.0f}h)")
        if reject_score >= 0.9:
            reasons.append(f"驳回率低({(profile.reject_rate or 0)*100:.0f}%)")
        elif reject_score < 0.5:
            reasons.append(f"⚠驳回率高({(profile.reject_rate or 0)*100:.0f}%)")
        if (profile.total_approved or 0) >= 100:
            reasons.append(f"经验({profile.total_approved}单)")
        return "、".join(reasons) if reasons else "默认推荐"
