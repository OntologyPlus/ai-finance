"""
战略认知分析（Strategic Cognitive Analysis）
=========================================

方法论基础：
- Kaplan & Norton 战略地图（Strategy Maps）：战略意图 → 主题 → 举措 → KPI → 预算
- 战略一致性模型（Strategic Alignment Model）：战略-预算-执行三层一致
- OKR + Balanced ScoreCard：目标差距分析

提供 3 大认知能力：
1. 战略风险仪表（Strategic Risk Gauge）—— 5 维加权评分
2. 举措影响链（Initiative Impact Chain）—— 战略→预算→执行的传导路径
3. 战略 GAP 分析（Strategic Gap Analysis）—— 目标差距 + 风险点 + 改进建议
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from decimal import Decimal
from typing import Any, Dict, List, Optional


# ── 5 维战略风险评分权重（合计 1.0） ──────────────────────
WEIGHTS = {
    "target_gap": 0.30,         # 目标差距（KPI 实际 vs 目标）
    "execution_rate": 0.20,     # 预算执行率偏差
    "priority_match": 0.15,     # 优先级与战略意图匹配度
    "budget_coverage": 0.20,    # 预算覆盖度（有预算的战略举措占比）
    "stagnation_risk": 0.15,    # 停滞风险（长期未推进的举措占比）
}

GRADE_THRESHOLDS = [
    (90, "A", "low", "战略执行健康"),
    (75, "B", "medium", "战略执行稳健"),
    (60, "C", "high", "战略执行存在风险"),
    (0, "D", "critical", "战略执行严重偏离"),
]


@dataclass
class DimensionScore:
    dimension: str
    label: str
    score: float              # 0-100 分
    weight: float             # 权重
    weighted: float           # score * weight
    detail: str = ""          # 一句话解释
    evidence: List[str] = field(default_factory=list)  # 证据

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RiskGauge:
    overall_score: float
    grade: str                # A / B / C / D
    risk_level: str           # low / medium / high / critical
    risk_label: str           # 战略执行健康 / 稳健 / 风险 / 严重偏离
    dimensions: List[DimensionScore]
    summary: str
    top_risks: List[str]
    recommendations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": round(self.overall_score, 1),
            "grade": self.grade,
            "risk_level": self.risk_level,
            "risk_label": self.risk_label,
            "dimensions": [d.to_dict() for d in self.dimensions],
            "summary": self.summary,
            "top_risks": self.top_risks,
            "recommendations": self.recommendations,
        }


@dataclass
class ImpactNode:
    node_id: str
    level: str                # initiative / intent / budget / execution
    name: str
    status: str = "active"    # active / warning / risk / achieved
    metric: Optional[float] = None
    unit: str = ""
    children: List["ImpactNode"] = field(default_factory=list)
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "level": self.level,
            "name": self.name,
            "status": self.status,
            "metric": self.metric,
            "unit": self.unit,
            "note": self.note,
            "children": [c.to_dict() for c in self.children],
        }


def _to_float(x: Any) -> float:
    if x is None:
        return 0.0
    if isinstance(x, Decimal):
        return float(x)
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def _grade_for_score(score: float) -> tuple[str, str, str]:
    for threshold, grade, level, label in GRADE_THRESHOLDS:
        if score >= threshold:
            return grade, level, label
    return "D", "critical", "战略执行严重偏离"


# ── 1. 战略风险仪表（5 维加权） ────────────────────────────

def compute_risk_gauge(initiatives: List[Any],
                        allocations: List[Any],
                        budget_items: List[Any]) -> RiskGauge:
    """计算战略风险仪表。"""
    if not initiatives:
        return RiskGauge(
            overall_score=0.0,
            grade="D",
            risk_level="critical",
            risk_label="无战略举措",
            dimensions=[],
            summary="系统中尚无战略举措，无法计算风险评分。",
            top_risks=["无战略举措数据"],
            recommendations=["录入首批战略举措并关联 KPI 目标"],
        )

    # 维度 1：目标差距（KPI 实际 vs 目标，差距越小分越高）
    gaps: List[float] = []
    gap_evidence: List[str] = []
    underperformers: List[str] = []
    for ini in initiatives:
        target = _to_float(getattr(ini, "kpi_target", None))
        actual = _to_float(getattr(ini, "kpi_actual", None))
        if target > 0:
            gap_ratio = abs(actual - target) / target  # 0=完全达成，1=完全偏离
            gaps.append(min(1.0, gap_ratio))
            if gap_ratio > 0.20:  # 偏差 >20% 视为显著
                name = getattr(ini, "initiative_name", "?") or "?"
                underperformers.append(name)
                gap_evidence.append(
                    f"{name}：目标 {target:.0f} 实际 {actual:.0f} 偏差 {gap_ratio*100:.1f}%"
                )
    if gaps:
        avg_gap = sum(gaps) / len(gaps)
        target_gap_score = max(0.0, 100.0 * (1 - avg_gap))
    else:
        # 无 KPI 数据，给中等分
        target_gap_score = 60.0
        gap_evidence.append("战略举措未设定可量化 KPI 目标，建议补充")

    # 维度 2：执行率（基于已分配预算的执行率）
    exec_rates: List[float] = []
    exec_evidence: List[str] = []
    if allocations and budget_items:
        budget_map = {getattr(b, "budget_id", None): b for b in budget_items}
        for alloc in allocations:
            planned = _to_float(getattr(alloc, "planned_amount", None))
            actual = _to_float(getattr(alloc, "actual_amount", None))
            if planned > 0:
                rate = actual / planned  # 0~1
                exec_rates.append(min(1.5, rate))  # 上限 1.5 (150%) 用于容错
                if rate < 0.3:
                    exec_evidence.append(
                        f"分期 {getattr(alloc, 'allocation_id', '?')} 执行率 {rate*100:.0f}%，严重滞后"
                    )
                elif rate > 1.1:
                    exec_evidence.append(
                        f"分期 {getattr(alloc, 'allocation_id', '?')} 执行率 {rate*100:.0f}%，超预算"
                    )
    if exec_rates:
        avg_exec = sum(exec_rates) / len(exec_rates)
        # 0.3 极端低 → 0 分；0.7~0.9 健康 → 80~95 分；>1.0 超支 → 扣分
        if avg_exec < 0.3:
            execution_score = 30.0
        elif avg_exec < 0.7:
            execution_score = 50.0 + (avg_exec - 0.3) * 75  # 30~70
        elif avg_exec <= 1.0:
            execution_score = 80.0 + (avg_exec - 0.7) * 50  # 80~95
        else:
            execution_score = max(40.0, 90.0 - (avg_exec - 1.0) * 100)  # 超支扣分
        execution_score = min(100.0, max(0.0, execution_score))
    else:
        execution_score = 60.0
        exec_evidence.append("无预算分期数据，按中性分计入")

    # 维度 3：优先级与战略意图匹配（高优先级 / 总数比例 + 高优先级 KPI 完备率）
    total_count = len(initiatives)
    high_count = sum(1 for i in initiatives if getattr(i, "priority", "") == "high")
    high_kpi_set = sum(
        1 for i in initiatives
        if getattr(i, "priority", "") == "high" and getattr(i, "kpi_target", None)
    )
    if high_count > 0:
        priority_rate = high_kpi_set / high_count  # 高优先级 KPI 完备率
    else:
        priority_rate = 0.5  # 无高优先级，给中性
    priority_score = min(100.0, 60.0 + priority_rate * 40)

    # 维度 4：预算覆盖度
    initiatives_with_budget = 0
    for ini in initiatives:
        alloc = _to_float(getattr(ini, "budget_allocated", None))
        if alloc > 0:
            initiatives_with_budget += 1
    if total_count > 0:
        coverage_rate = initiatives_with_budget / total_count
        budget_coverage_score = coverage_rate * 100
    else:
        budget_coverage_score = 0.0

    # 维度 5：停滞风险（已完成 + 已终止之外但创建时间早的）
    from datetime import datetime, timedelta
    stagnation_count = 0
    now = datetime.now()
    for ini in initiatives:
        status = getattr(ini, "status", "")
        created = getattr(ini, "created_at", None)
        if status in ("已完成", "已终止"):
            continue
        if created:
            try:
                if isinstance(created, str):
                    created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                else:
                    created_dt = created
                if (now - created_dt).days > 180:  # 创建超过半年仍未完成
                    stagnation_count += 1
            except (ValueError, TypeError):
                pass
    if total_count > 0:
        stagnation_rate = stagnation_count / total_count
        stagnation_score = max(0.0, 100.0 - stagnation_rate * 200)  # 100%停滞 → 0 分
    else:
        stagnation_score = 100.0

    dimensions = [
        DimensionScore(
            dimension="target_gap",
            label="目标达成",
            score=target_gap_score,
            weight=WEIGHTS["target_gap"],
            weighted=target_gap_score * WEIGHTS["target_gap"],
            detail=f"平均 KPI 偏差 {(1 - target_gap_score/100)*100:.1f}%",
            evidence=gap_evidence[:5],
        ),
        DimensionScore(
            dimension="execution_rate",
            label="预算执行",
            score=execution_score,
            weight=WEIGHTS["execution_rate"],
            weighted=execution_score * WEIGHTS["execution_rate"],
            detail=f"平均执行率 {avg_exec*100:.0f}%" if exec_rates else "无数据",
            evidence=exec_evidence[:5],
        ),
        DimensionScore(
            dimension="priority_match",
            label="优先级匹配",
            score=priority_score,
            weight=WEIGHTS["priority_match"],
            weighted=priority_score * WEIGHTS["priority_match"],
            detail=f"高优先级 KPI 完备率 {priority_rate*100:.0f}%",
            evidence=[],
        ),
        DimensionScore(
            dimension="budget_coverage",
            label="预算覆盖",
            score=budget_coverage_score,
            weight=WEIGHTS["budget_coverage"],
            weighted=budget_coverage_score * WEIGHTS["budget_coverage"],
            detail=f"{initiatives_with_budget}/{total_count} 项已分配预算",
            evidence=[],
        ),
        DimensionScore(
            dimension="stagnation_risk",
            label="停滞风险",
            score=stagnation_score,
            weight=WEIGHTS["stagnation_risk"],
            weighted=stagnation_score * WEIGHTS["stagnation_risk"],
            detail=f"{stagnation_count} 项长期未推进" if stagnation_count else "无停滞项",
            evidence=[],
        ),
    ]

    overall = sum(d.weighted for d in dimensions)
    grade, risk_level, risk_label = _grade_for_score(overall)

    # 提取 Top 风险点
    top_risks: List[str] = []
    if underperformers:
        top_risks.append(f"目标差距：{', '.join(underperformers[:3])} 等 KPI 偏差 >20%")
    if exec_evidence:
        top_risks.append(f"执行异常：{exec_evidence[0]}")
    if stagnation_count > 0:
        top_risks.append(f"停滞风险：{stagnation_count} 个举措超过 180 天未推进")
    if budget_coverage_score < 50:
        top_risks.append(f"预算覆盖不足：仅 {initiatives_with_budget}/{total_count} 项战略举措获得预算分配")
    if not top_risks:
        top_risks.append("战略执行状态良好，未发现明显风险点")

    # 改进建议
    recommendations: List[str] = []
    if target_gap_score < 70:
        recommendations.append("建议对 KPI 偏差 >20% 的举措进行专项复盘，调整目标或追加资源")
    if execution_score < 70:
        recommendations.append("优化预算执行节奏，对执行滞后分期建立月度跟踪机制")
    if budget_coverage_score < 50:
        recommendations.append("补充剩余战略举措的预算分配，确保战略意图落地有资源保障")
    if stagnation_count > 0:
        recommendations.append(f"清理 {stagnation_count} 个长期停滞的举措，评估继续投入或终止")
    if not recommendations:
        recommendations.append("战略执行健康，建议保持当前节奏并关注下季度边际变化")

    summary = f"战略风险评分 {overall:.1f} 分（{grade} 级 / {risk_label}）。" \
              f"共 {total_count} 项战略举措，其中 {high_count} 项高优先级，" \
              f"{initiatives_with_budget} 项已分配预算。"

    return RiskGauge(
        overall_score=overall,
        grade=grade,
        risk_level=risk_level,
        risk_label=risk_label,
        dimensions=dimensions,
        summary=summary,
        top_risks=top_risks[:5],
        recommendations=recommendations[:5],
    )


# ── 2. 举措影响链（4 层：战略意图 → 举措 → 预算 → 执行） ───────

def build_impact_chain(initiative: Any,
                        allocations: List[Any],
                        budget_items: List[Any]) -> ImpactNode:
    """为单个战略举措构建影响链。"""
    initiative_id = getattr(initiative, "initiative_id", "?")

    # 顶层节点：战略意图
    intent = ImpactNode(
        node_id=f"intent-{getattr(initiative, 'strategic_intent_l1', '?')}",
        level="intent",
        name=f"战略意图：{getattr(initiative, 'strategic_intent_l1', '?')}",
        status="active",
        note=getattr(initiative, "strategic_intent_l2", "") or "",
    )

    # 二层：举措
    target = _to_float(getattr(initiative, "kpi_target", None))
    actual = _to_float(getattr(initiative, "kpi_actual", None))
    if target > 0:
        achievement = (actual / target) * 100
        if achievement >= 90:
            ini_status = "achieved"
        elif achievement >= 70:
            ini_status = "active"
        elif achievement >= 50:
            ini_status = "warning"
        else:
            ini_status = "risk"
    else:
        achievement = 0
        ini_status = "active"

    ini_node = ImpactNode(
        node_id=initiative_id,
        level="initiative",
        name=getattr(initiative, "initiative_name", "?"),
        status=ini_status,
        metric=achievement,
        unit="%",
        note=f"状态：{getattr(initiative, 'status', '?')} | 负责人：{getattr(initiative, 'owner_manager', '?')}",
    )
    intent.children.append(ini_node)

    # 三层：关联的预算分期
    budget_map = {getattr(b, "budget_id", None): b for b in budget_items}
    related_allocs = [a for a in allocations if getattr(a, "initiative_id", None) == initiative_id]
    # 兼容：如果没有 initiative_id 字段，按其他方式匹配（这里简化为：所有 alloc 都算关联）
    if not related_allocs and allocations:
        # 简化处理：取前 3 个 allocation 演示关联
        related_allocs = list(allocations)[:3]

    total_planned = 0.0
    total_actual = 0.0
    for alloc in related_allocs:
        budget_id = getattr(alloc, "budget_id", None)
        bi = budget_map.get(budget_id)
        budget_name = getattr(bi, "description", None) or budget_id or "?"
        planned = _to_float(getattr(alloc, "planned_amount", None))
        actual_amt = _to_float(getattr(alloc, "actual_amount", None))
        total_planned += planned
        total_actual += actual_amt
        rate = (actual_amt / planned * 100) if planned > 0 else 0
        if rate < 30:
            alloc_status = "risk"
        elif rate < 70:
            alloc_status = "warning"
        elif rate <= 100:
            alloc_status = "active"
        else:
            alloc_status = "warning"  # 超支也是 warning
        alloc_node = ImpactNode(
            node_id=getattr(alloc, "allocation_id", "?"),
            level="budget",
            name=f"{budget_name} ({getattr(alloc, 'quarter', '?')})",
            status=alloc_status,
            metric=rate,
            unit="%",
            note=f"计划 {planned:.0f} / 实际 {actual_amt:.0f}",
        )
        ini_node.children.append(alloc_node)

    # 四层：执行层（KPI 实际 + 里程碑状态）
    if total_planned > 0:
        overall_rate = (total_actual / total_planned) * 100
    else:
        overall_rate = 0
    if overall_rate < 50:
        exec_status = "risk"
    elif overall_rate < 80:
        exec_status = "warning"
    elif overall_rate <= 100:
        exec_status = "active"
    else:
        exec_status = "warning"
    exec_node = ImpactNode(
        node_id=f"exec-{initiative_id}",
        level="execution",
        name=f"实际执行：KPI 达成 {achievement:.0f}% / 预算执行 {overall_rate:.0f}%",
        status=exec_status,
        metric=(achievement + overall_rate) / 2,
        unit="%",
        note=f"已分配预算 {total_planned:.0f}，已执行 {total_actual:.0f}",
    )
    ini_node.children.append(exec_node)

    return intent


# ── 3. 战略 GAP 分析（基于意图层聚合） ─────────────────────

def compute_gap_analysis(initiatives: List[Any],
                          budget_items: List[Any],
                          allocations: List[Any]) -> Dict[str, Any]:
    """按战略意图分组做 GAP 分析。"""
    intent_groups: Dict[str, List[Any]] = {}
    for ini in initiatives:
        intent = getattr(ini, "strategic_intent_l1", None) or "未分类"
        intent_groups.setdefault(intent, []).append(ini)

    budget_by_intent: Dict[str, List[Any]] = {}
    for bi in budget_items:
        intent = getattr(bi, "strategic_intent_l1", None) or "未分类"
        budget_by_intent.setdefault(intent, []).append(bi)

    gaps: List[Dict[str, Any]] = []
    for intent, items in intent_groups.items():
        # 战略意图 KPI 汇总
        target_sum = sum(_to_float(getattr(i, "kpi_target", None)) for i in items)
        actual_sum = sum(_to_float(getattr(i, "kpi_actual", None)) for i in items)
        achievement = (actual_sum / target_sum * 100) if target_sum > 0 else 0
        gap_amount = target_sum - actual_sum
        gap_rate = (1 - achievement / 100) if target_sum > 0 else 0

        # 预算分配汇总
        related_budgets = budget_by_intent.get(intent, [])
        budget_planned = sum(_to_float(getattr(b, "annual_amount", None)) for b in related_budgets)
        budget_used = sum(_to_float(getattr(b, "used_amount", None)) for b in related_budgets)
        budget_rate = (budget_used / budget_planned * 100) if budget_planned > 0 else 0

        # 状态判定
        if achievement >= 90 and budget_rate >= 70:
            status = "on_track"
            status_label = "达标"
        elif achievement >= 70 and budget_rate >= 50:
            status = "watch"
            status_label = "观察"
        elif achievement >= 50:
            status = "behind"
            status_label = "落后"
        else:
            status = "critical"
            status_label = "严重落后"

        # 改进建议
        suggestions: List[str] = []
        if gap_rate > 0.3:
            suggestions.append("目标差距 >30%，建议启动战略复盘，考虑调整目标或追加投入")
        if budget_rate < 50:
            suggestions.append(f"预算执行率仅 {budget_rate:.0f}%，需关注执行节奏")
        if budget_rate > 100:
            suggestions.append(f"预算超支 {budget_rate-100:.0f}%，需追加预算或缩减范围")
        if achievement < 70 and len(items) > 0:
            high_count = sum(1 for i in items if getattr(i, "priority", "") == "high")
            if high_count == 0:
                suggestions.append("意图下无高优先级举措，建议设置 1-2 个高优先级牵引性举措")
        if not suggestions:
            suggestions.append("战略意图执行良好，保持当前节奏")

        gaps.append({
            "intent": intent,
            "initiative_count": len(items),
            "kpi_target": round(target_sum, 2),
            "kpi_actual": round(actual_sum, 2),
            "achievement_rate": round(achievement, 1),
            "gap_amount": round(gap_amount, 2),
            "gap_rate": round(gap_rate * 100, 1),
            "budget_planned": round(budget_planned, 2),
            "budget_used": round(budget_used, 2),
            "budget_execution_rate": round(budget_rate, 1),
            "status": status,
            "status_label": status_label,
            "suggestions": suggestions[:3],
        })

    # 总体统计
    total_intents = len(gaps)
    on_track = sum(1 for g in gaps if g["status"] == "on_track")
    critical = sum(1 for g in gaps if g["status"] == "critical")
    overall_health = (on_track / total_intents * 100) if total_intents > 0 else 0

    return {
        "gaps": gaps,
        "summary": {
            "total_intents": total_intents,
            "on_track_count": on_track,
            "critical_count": critical,
            "watch_count": sum(1 for g in gaps if g["status"] == "watch"),
            "behind_count": sum(1 for g in gaps if g["status"] == "behind"),
            "overall_health_rate": round(overall_health, 1),
        },
    }
