"""
审批瓶颈智能识别引擎

按《经营分析方法论.md》§4.4 治理流程实现：
- 按链路步骤聚合审批时长
- 识别最慢步骤（瓶颈）
- 计算超时率 + 根因分析
- 主动建议联动（瓶颈步骤 → ProactiveAdvisor 催办）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.approval import ApprovalRecord


@dataclass
class BottleneckStep:
    """单个瓶颈步骤"""
    step_name: str
    step_index: int
    avg_duration_hours: float
    max_duration_hours: float
    total_count: int
    pending_count: int
    timeout_count: int
    timeout_rate: float
    severity: str  # low/medium/high/critical
    root_cause: str
    suggestion: str


@dataclass
class BottleneckAnalysis:
    """瓶颈分析结果"""
    period: str
    total_records: int
    overall_avg_hours: float
    overall_timeout_rate: float
    bottlenecks: List[BottleneckStep]  # Top N
    healthy_steps: List[str]  # 健康步骤
    worst_step: Optional[str]
    signal_light: str
    light_reason: str
    recommendations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "period": self.period,
            "total_records": self.total_records,
            "overall_avg_hours": round(self.overall_avg_hours, 1),
            "overall_timeout_rate": round(self.overall_timeout_rate * 100, 2),
            "bottlenecks": [
                {
                    "step_name": b.step_name,
                    "step_index": b.step_index,
                    "avg_duration_hours": round(b.avg_duration_hours, 1),
                    "max_duration_hours": round(b.max_duration_hours, 1),
                    "total_count": b.total_count,
                    "pending_count": b.pending_count,
                    "timeout_count": b.timeout_count,
                    "timeout_rate": round(b.timeout_rate * 100, 2),
                    "severity": b.severity,
                    "root_cause": b.root_cause,
                    "suggestion": b.suggestion,
                }
                for b in self.bottlenecks
            ],
            "healthy_steps": self.healthy_steps,
            "worst_step": self.worst_step,
            "signal_light": self.signal_light,
            "light_reason": self.light_reason,
            "recommendations": self.recommendations,
        }


class ApprovalBottleneckEngine:
    """审批瓶颈智能识别引擎

    设计目标：
    - 按审批步骤分组（step_index + step_name）
    - 识别 Top 3 瓶颈步骤
    - 根因分析（基于时长分布 + 超时率）
    - 输出可操作建议
    """

    # 超时阈值（小时）
    TIMEOUT_THRESHOLDS = {
        "low": 24,      # < 24h
        "medium": 48,   # 24-48h
        "high": 72,     # 48-72h
        "critical": 72,  # > 72h
    }
    # 超时率分级
    TIMEOUT_RATE_THRESHOLDS = {
        "low": 0.05,     # < 5%
        "medium": 0.15,  # 5-15%
        "high": 0.30,    # 15-30%
        "critical": 0.30,  # > 30%
    }

    async def analyze_bottlenecks(
        self,
        db: AsyncSession,
        period: Optional[str] = None,
        top_n: int = 3,
    ) -> BottleneckAnalysis:
        """分析审批瓶颈

        Args:
            db: 异步数据库会话
            period: 统计期 YYYY-MM（None=全量）
            top_n: Top N 瓶颈

        Returns:
            BottleneckAnalysis
        """
        period = period or datetime.now().strftime("%Y-%m")

        # 1. 拉取本期所有审批记录
        stmt = select(ApprovalRecord)
        if period:
            # 按 created_at 的年月过滤（YYYY-MM）
            try:
                year, month = period.split("-")
                start = datetime(int(year), int(month), 1)
                if int(month) == 12:
                    end = datetime(int(year) + 1, 1, 1)
                else:
                    end = datetime(int(year), int(month) + 1, 1)
                stmt = stmt.where(
                    ApprovalRecord.created_at >= start,
                    ApprovalRecord.created_at < end,
                )
            except (ValueError, AttributeError):
                pass  # period 格式无效时不过滤
        result = await db.execute(stmt)
        records = result.scalars().all()

        if not records:
            return BottleneckAnalysis(
                period=period,
                total_records=0,
                overall_avg_hours=0.0,
                overall_timeout_rate=0.0,
                bottlenecks=[],
                healthy_steps=[],
                worst_step=None,
                signal_light="green",
                light_reason=f"本期 {period} 无审批记录",
                recommendations=[],
            )

        # 2. 按 approval_step + approver_role 分组聚合
        step_stats: Dict[tuple, List[ApprovalRecord]] = {}
        for r in records:
            key = (r.approval_step or 0, r.approver_role or "未知")
            step_stats.setdefault(key, []).append(r)

        # 3. 计算每步的瓶颈指标
        bottlenecks: List[BottleneckStep] = []
        healthy_steps: List[str] = []
        all_durations: List[float] = []
        all_timeouts = 0

        for (idx, name), group in step_stats.items():
            # 计算时长：approved_at - created_at（如果有）
            durations = []
            for r in group:
                if r.approved_at and r.created_at:
                    dur = (r.approved_at - r.created_at).total_seconds() / 3600
                    durations.append(dur)
            timeouts = sum(1 for r in group if r.is_overdue)
            total = len(group)
            pending = sum(1 for r in group if r.approval_action == "待审批")
            timeout_rate = (timeouts / total) if total > 0 else 0
            avg_dur = sum(durations) / len(durations) if durations else 0
            max_dur = max(durations) if durations else 0
            all_durations.extend(durations)
            all_timeouts += timeouts

            # 严重度判定（结合时长 + 超时率）
            severity = self._judge_severity(avg_dur, timeout_rate)
            root_cause = self._analyze_root_cause(group, avg_dur, timeout_rate)
            suggestion = self._suggest_for_severity(severity, name, avg_dur, timeout_rate)

            step = BottleneckStep(
                step_name=name,
                step_index=idx,
                avg_duration_hours=avg_dur,
                max_duration_hours=max_dur,
                total_count=total,
                pending_count=pending,
                timeout_count=timeouts,
                timeout_rate=timeout_rate,
                severity=severity,
                root_cause=root_cause,
                suggestion=suggestion,
            )
            if severity in ("high", "critical"):
                bottlenecks.append(step)
            else:
                healthy_steps.append(name)

        # 4. 排序取 Top N
        bottlenecks.sort(key=lambda b: (
            -{"critical": 4, "high": 3, "medium": 2, "low": 1}.get(b.severity, 0),
            -b.timeout_rate,
            -b.avg_duration_hours,
        ))
        bottlenecks = bottlenecks[:top_n]

        # 5. 整体信号灯
        overall_avg = sum(all_durations) / len(all_durations) if all_durations else 0
        overall_timeout_rate = all_timeouts / len(records) if records else 0
        worst_step = bottlenecks[0].step_name if bottlenecks else None

        if any(b.severity == "critical" for b in bottlenecks):
            signal = "red"
            reason = f"存在 critical 瓶颈步骤（{worst_step}）"
        elif any(b.severity == "high" for b in bottlenecks):
            signal = "yellow"
            reason = f"存在 high 瓶颈步骤（{worst_step}），建议关注"
        elif overall_timeout_rate > 0.10:
            signal = "yellow"
            reason = f"整体超时率 {overall_timeout_rate*100:.1f}% > 10%"
        else:
            signal = "green"
            reason = f"整体超时率 {overall_timeout_rate*100:.1f}%，运行良好"

        # 6. 输出建议
        recommendations = [b.suggestion for b in bottlenecks]

        return BottleneckAnalysis(
            period=period,
            total_records=len(records),
            overall_avg_hours=overall_avg,
            overall_timeout_rate=overall_timeout_rate,
            bottlenecks=bottlenecks,
            healthy_steps=healthy_steps,
            worst_step=worst_step,
            signal_light=signal,
            light_reason=reason,
            recommendations=recommendations,
        )

    def _judge_severity(self, avg_hours: float, timeout_rate: float) -> str:
        if avg_hours > self.TIMEOUT_THRESHOLDS["critical"] or timeout_rate > self.TIMEOUT_RATE_THRESHOLDS["high"]:
            return "critical"
        if avg_hours > self.TIMEOUT_THRESHOLDS["high"] or timeout_rate > self.TIMEOUT_RATE_THRESHOLDS["medium"]:
            return "high"
        if avg_hours > self.TIMEOUT_THRESHOLDS["medium"] or timeout_rate > self.TIMEOUT_RATE_THRESHOLDS["low"]:
            return "medium"
        return "low"

    def _analyze_root_cause(
        self, group: List[ApprovalRecord], avg_hours: float, timeout_rate: float
    ) -> str:
        if timeout_rate > 0.30:
            return f"超时率 {timeout_rate*100:.0f}% 异常高，可能存在审批人缺席/委派集中"
        if avg_hours > 72:
            return f"平均时长 {avg_hours:.0f}h 远超预期，可能存在审批链路过长"
        if timeout_rate > 0.15:
            return f"超时率 {timeout_rate*100:.0f}% 偏高，建议关注"
        return "正常范围"

    def _suggest_for_severity(
        self, severity: str, step_name: str, avg_hours: float, timeout_rate: float
    ) -> str:
        if severity == "critical":
            return f"【{step_name}】紧急：平均 {avg_hours:.0f}h / 超时率 {timeout_rate*100:.0f}%，建议启动催办 + 增配审批人"
        if severity == "high":
            return f"【{step_name}】建议：平均 {avg_hours:.0f}h 偏长，可设置自动催办"
        if severity == "medium":
            return f"【{step_name}】关注：{avg_hours:.0f}h 内响应"
        return f"【{step_name}】健康"
