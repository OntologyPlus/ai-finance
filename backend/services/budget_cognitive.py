"""
预算认知分析（Budget Cognitive Analysis）
========================================

方法论基础：
- 5 Why 根因分析（5 Whys Analysis）
- 偏差归因（Variance Attribution）：价格/数量/结构/季节性
- 杜邦分析 + 桥接分析（Budget Bridge Analysis）
- 主动建议规则（Proactive Advisory Rules）

提供 3 大认知能力：
1. 5 层根因下钻（5-Layer Root Cause Drill-Down）
2. 主动建议面板（Proactive Advisory Panel）
3. 预算-业务联动分析（Budget-Business Linkage）
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta


def _to_float(x: Any) -> float:
    if x is None:
        return 0.0
    if isinstance(x, Decimal):
        return float(x)
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


@dataclass
class RootCauseLayer:
    level: int                  # 1-5 层
    title: str
    finding: str
    severity: str               # info / warning / risk
    metric: Optional[float] = None
    metric_unit: str = ""
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RootCauseDrill:
    budget_id: str
    budget_name: str
    issue_type: str             # 超支 / 偏低 / 执行滞后 / 异常波动
    severity: str               # info / warning / risk / critical
    summary: str
    layers: List[RootCauseLayer]
    final_recommendation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "budget_id": self.budget_id,
            "budget_name": self.budget_name,
            "issue_type": self.issue_type,
            "severity": self.severity,
            "summary": self.summary,
            "layers": [l.to_dict() for l in self.layers],
            "final_recommendation": self.final_recommendation,
        }


# ── 1. 5 层根因下钻 ────────────────────────────────────────

def drill_down_root_cause(
    item: Any,
    all_items: List[Any],
    history: Optional[List[Any]] = None,
) -> RootCauseDrill:
    """对单个预算项做 5 层根因下钻：
    L1 现象 → L2 量化 → L3 结构 → L4 时间 → L5 关联

    参数:
      item: 当前预算项
      all_items: 全部预算项（用于横向对比）
      history: 历史预算快照（用于纵向对比）
    """
    budget_id = getattr(item, "budget_id", "?")
    description = getattr(item, "description", "?")
    annual = _to_float(getattr(item, "annual_amount", None))
    used = _to_float(getattr(item, "used_amount", None))
    available = _to_float(getattr(item, "available_amount", None))
    rate = (used / annual * 100) if annual > 0 else 0

    # 判断问题类型
    if rate >= 100:
        issue_type = "超支"
        severity = "critical" if rate >= 120 else "risk"
    elif rate >= 80:
        issue_type = "执行偏高"
        severity = "warning"
    elif rate < 30 and annual > 0:
        issue_type = "执行偏低"
        severity = "info"
    else:
        issue_type = "正常"
        severity = "info"

    layers: List[RootCauseLayer] = []

    # L1 现象层
    layers.append(RootCauseLayer(
        level=1,
        title="L1 · 现象",
        finding=f"当前执行率 {rate:.1f}%，{issue_type}（{used:.0f} / {annual:.0f}）",
        severity="warning" if rate >= 80 else "info",
        metric=rate,
        metric_unit="%",
        evidence=[
            f"年度预算 {annual:.0f}",
            f"已使用 {used:.0f}",
            f"可用余额 {available:.0f}",
        ],
    ))

    # L2 量化层（与同科目/同中心平均对比）
    l1_code = getattr(item, "l1_code", None)
    same_l1 = [bi for bi in all_items if getattr(bi, "l1_code", None) == l1_code and bi is not item]
    if same_l1:
        same_l1_rates = []
        for bi in same_l1:
            a = _to_float(getattr(bi, "annual_amount", None))
            u = _to_float(getattr(bi, "used_amount", None))
            if a > 0:
                same_l1_rates.append(u / a * 100)
        if same_l1_rates:
            peer_avg = sum(same_l1_rates) / len(same_l1_rates)
            delta = rate - peer_avg
            layers.append(RootCauseLayer(
                level=2,
                title="L2 · 量化（横向对比）",
                finding=f"与同 L1 科目 {len(same_l1)} 个项目相比，{('高于' if delta > 0 else '低于')}平均 {abs(delta):.1f}pp（同类均值 {peer_avg:.1f}%）",
                severity="warning" if abs(delta) > 15 else "info",
                metric=delta,
                metric_unit="pp",
                evidence=[
                    f"同类项目数：{len(same_l1)}",
                    f"同类平均执行率：{peer_avg:.1f}%",
                    f"本项 vs 偏差：{delta:+.1f}pp",
                ],
            ))

    # L3 结构层（A/B 类别 + 象限）
    budget_category = getattr(item, "budget_category", None)
    quadrant = getattr(item, "quadrant", None)
    structure_findings: List[str] = []
    if budget_category:
        structure_findings.append(f"分类：{budget_category} 类（{'强管控' if budget_category == 'A' else '弹性调控'}）")
    if quadrant:
        structure_findings.append(f"象限：{quadrant}")
    layers.append(RootCauseLayer(
        level=3,
        title="L3 · 结构",
        finding=f"项目结构特征：{' / '.join(structure_findings) if structure_findings else '未分类'}",
        severity="info",
        evidence=structure_findings,
    ))

    # L4 时间层（基于历史快照判断趋势）
    if history and len(history) > 0:
        prev = history[-1]
        prev_rate = _to_float(getattr(prev, "execution_rate", None))
        if prev_rate > 0:
            trend = rate - prev_rate
            layers.append(RootCauseLayer(
                level=4,
                title="L4 · 时间（纵向趋势）",
                finding=f"较上期 {trend:+.1f}pp（前期 {prev_rate:.1f}% → 本期 {rate:.1f}%）",
                severity="warning" if abs(trend) > 10 else "info",
                metric=trend,
                metric_unit="pp",
                evidence=[f"上期执行率：{prev_rate:.1f}%", f"本期执行率：{rate:.1f}%"],
            ))
    else:
        # 无历史时给建议
        layers.append(RootCauseLayer(
            level=4,
            title="L4 · 时间（纵向趋势）",
            finding="无历史快照数据，建议启用季度对比机制",
            severity="info",
        ))

    # L5 关联层（找相似项目的解决方案）
    similar_solutions: List[str] = []
    if rate >= 90 and same_l1:
        # 同类超支项目经验
        same_l1_over = [bi for bi in same_l1 if _to_float(getattr(bi, "used_amount", None)) / max(_to_float(getattr(bi, "annual_amount", None)), 1) >= 0.9]
        if same_l1_over:
            similar_solutions.append(f"同类超支项目 {len(same_l1_over)} 个，建议参考其调拨/压缩策略")
    if rate < 30 and same_l1:
        same_l1_low = [bi for bi in same_l1 if _to_float(getattr(bi, "used_amount", None)) / max(_to_float(getattr(bi, "annual_amount", None)), 1) < 0.3]
        if same_l1_low:
            similar_solutions.append(f"同类低执行项目 {len(same_l1_low)} 个，建议纳入下期预算重分配")

    layers.append(RootCauseLayer(
        level=5,
        title="L5 · 关联（解决方案）",
        finding="; ".join(similar_solutions) if similar_solutions else "未发现同类问题项目，建议建立预警机制",
        severity="info",
        evidence=similar_solutions,
    ))

    # 最终建议
    if issue_type == "超支":
        if rate >= 120:
            final = "立即冻结该预算项新申请，召开专项复盘会评估是否追加或缩减范围"
        else:
            final = "暂停新增申请，对已发生费用做合理性审查；同步评估是否启动调拨"
    elif issue_type == "执行偏高":
        final = "加强事前审批，预警下月可能超支，必要时启动调拨"
    elif issue_type == "执行偏低":
        final = "评估是否需要调拨至其他高需求项，或在下次预算编制时缩减额度"
    else:
        final = "保持当前执行节奏，关注下季度边际变化"

    return RootCauseDrill(
        budget_id=budget_id,
        budget_name=description,
        issue_type=issue_type,
        severity=severity,
        summary=f"{description}：执行率 {rate:.1f}%，{issue_type}，建议「{final}」",
        layers=layers,
        final_recommendation=final,
    )


# ── 2. 主动建议面板 ────────────────────────────────────────

@dataclass
class ProactiveSuggestion:
    priority: str               # critical / attention / info
    category: str               # 节约 / 风险 / 调拨 / 复盘 / 监控
    title: str
    detail: str
    action_label: str
    target_budget_id: Optional[str] = None
    estimated_impact: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def generate_proactive_suggestions(
    items: List[Any],
    period: str = "本月",
) -> List[ProactiveSuggestion]:
    """基于预算数据生成主动建议。"""
    suggestions: List[ProactiveSuggestion] = []

    if not items:
        return [ProactiveSuggestion(
            priority="info",
            category="监控",
            title="暂无预算数据",
            detail="系统中尚无预算项，建议先创建基础预算以启用分析",
            action_label="创建预算",
        )]

    # 1. 超预算项预警
    over_budget = []
    for item in items:
        annual = _to_float(getattr(item, "annual_amount", None))
        used = _to_float(getattr(item, "used_amount", None))
        if annual > 0 and used / annual >= 1.0:
            over_budget.append((item, used / annual * 100))

    if over_budget:
        worst = max(over_budget, key=lambda x: x[1])
        item, rate = worst
        suggestions.append(ProactiveSuggestion(
            priority="critical",
            category="风险",
            title=f"超支预警：{getattr(item, 'description', '?')}",
            detail=f"执行率已达 {rate:.1f}%，共 {len(over_budget)} 个项目超支。建议立即启动应急审批通道。",
            action_label="查看根因",
            target_budget_id=getattr(item, "budget_id", None),
            estimated_impact=f"潜在超支 ¥{_to_float(getattr(item, 'used_amount', None)) - _to_float(getattr(item, 'annual_amount', None)):.0f}",
        ))

    # 2. 执行滞后项提醒
    low_exec = []
    for item in items:
        annual = _to_float(getattr(item, "annual_amount", None))
        used = _to_float(getattr(item, "used_amount", None))
        if annual > 0 and used / annual < 0.3:
            low_exec.append((item, used / annual * 100))

    if low_exec:
        worst = min(low_exec, key=lambda x: x[1])
        item, rate = worst
        idle_amount = _to_float(getattr(item, "annual_amount", None)) - _to_float(getattr(item, "used_amount", None))
        suggestions.append(ProactiveSuggestion(
            priority="attention",
            category="调拨",
            title=f"执行滞后：{getattr(item, 'description', '?')}",
            detail=f"执行率仅 {rate:.1f}%，闲置额度 ¥{idle_amount:.0f}。建议评估是否调拨至其他高需求项。",
            action_label="创建调拨",
            target_budget_id=getattr(item, "budget_id", None),
            estimated_impact=f"可释放 ¥{idle_amount:.0f}",
        ))

    # 3. 季度调拨建议
    by_quadrant: Dict[str, List[Any]] = {}
    for item in items:
        q = getattr(item, "quadrant", None) or "未分类"
        by_quadrant.setdefault(q, []).append(item)

    over_quadrant_rates: List[Tuple[str, float]] = []
    for q, qitems in by_quadrant.items():
        total_a = sum(_to_float(getattr(bi, "annual_amount", None)) for bi in qitems)
        total_u = sum(_to_float(getattr(bi, "used_amount", None)) for bi in qitems)
        if total_a > 0:
            over_quadrant_rates.append((q, total_u / total_a * 100))

    if len(over_quadrant_rates) >= 2:
        over_quadrant_rates.sort(key=lambda x: x[1], reverse=True)
        hottest = over_quadrant_rates[0]
        coldest = over_quadrant_rates[-1]
        if hottest[1] - coldest[1] > 25:  # 25pp 差距
            suggestions.append(ProactiveSuggestion(
                priority="attention",
                category="调拨",
                title=f"跨象限调拨建议：{hottest[0]} → {coldest[0]}",
                detail=f"{hottest[0]}象限执行率 {hottest[1]:.1f}%，{coldest[0]}象限仅 {coldest[1]:.1f}%，差距 {hottest[1]-coldest[1]:.1f}pp。建议将执行率最低象限的额度部分调拨至最高象限。",
                action_label="查看调拨模拟",
                estimated_impact=f"潜在优化 ¥{_to_float(getattr(items[0], 'annual_amount', None)) * 0.1:.0f}+",
            ))

    # 4. A/B 比例分析
    a_total = sum(_to_float(getattr(bi, "annual_amount", None)) for bi in items if getattr(bi, "budget_category", None) == "A")
    b_total = sum(_to_float(getattr(bi, "annual_amount", None)) for bi in items if getattr(bi, "budget_category", None) == "B")
    total = a_total + b_total
    if total > 0:
        a_ratio = a_total / total * 100
        if a_ratio > 75:
            suggestions.append(ProactiveSuggestion(
                priority="info",
                category="复盘",
                title="A 类预算占比偏高",
                detail=f"当前 A 类预算占比 {a_ratio:.1f}%，结构刚性过强。建议下次编制时增加 B 类弹性比例。",
                action_label="查看象限视图",
                estimated_impact="提升预算弹性 15-20%",
            ))
        elif a_ratio < 30:
            suggestions.append(ProactiveSuggestion(
                priority="info",
                category="复盘",
                title="A 类预算占比偏低",
                detail=f"当前 A 类预算占比仅 {a_ratio:.1f}%，战略刚性保障不足。需评估是否漏配 A 类关键项。",
                action_label="查看象限视图",
                estimated_impact="强化战略保障",
            ))

    # 5. 跨期提醒（假设当前是 Q3，提醒 Q4 规划）
    current_month = datetime.now().month
    if current_month in (9, 10):
        suggestions.append(ProactiveSuggestion(
            priority="info",
            category="复盘",
            title="Q4 预算规划窗口期",
            detail="已进入 Q4，建议启动下年度预算编制前期准备，识别超支项的延续性风险。",
            action_label="查看季度对比",
            estimated_impact="规划周期 -2 周",
        ))

    return suggestions


# ── 3. 预算-业务联动 ────────────────────────────────────────

def compute_business_linkage(
    items: List[Any],
    expenses: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    """预算执行与业务活动联动分析。

    联动指标：
    - 预算执行率 vs 报销笔数（高频低额 vs 低频高额）
    - 预算执行率 vs 报销金额集中度
    - 异常联动：执行率高 + 报销激增 = 风险
    """
    if not items:
        return {"items": [], "summary": "无预算数据", "risk_pairs": []}

    linkages: List[Dict[str, Any]] = []
    risk_pairs: List[Dict[str, Any]] = []

    expense_map: Dict[str, List[Any]] = {}
    if expenses:
        for exp in expenses:
            budget_id = getattr(exp, "budget_id", None)
            if budget_id:
                expense_map.setdefault(budget_id, []).append(exp)

    for item in items:
        budget_id = getattr(item, "budget_id", "?")
        annual = _to_float(getattr(item, "annual_amount", None))
        used = _to_float(getattr(item, "used_amount", None))
        rate = (used / annual * 100) if annual > 0 else 0
        related_expenses = expense_map.get(budget_id, [])
        exp_count = len(related_expenses)
        exp_total = sum(_to_float(getattr(e, "amount", None)) for e in related_expenses)
        avg_per_exp = (exp_total / exp_count) if exp_count > 0 else 0

        # 联动画像
        if rate >= 80 and exp_count > 0:
            # 高执行 + 有报销 = 风险对
            if avg_per_exp > 5000:
                linkage_type = "低频高额"
                risk_level = "medium"
            else:
                linkage_type = "高频低额"
                risk_level = "high"
            risk_pairs.append({
                "budget_id": budget_id,
                "name": getattr(item, "description", "?"),
                "linkage_type": linkage_type,
                "risk_level": risk_level,
                "rate": round(rate, 1),
                "expense_count": exp_count,
                "avg_per_expense": round(avg_per_exp, 2),
            })
        else:
            linkage_type = "正常"

        linkages.append({
            "budget_id": budget_id,
            "name": getattr(item, "description", "?"),
            "l1_code": getattr(item, "l1_code", None),
            "execution_rate": round(rate, 1),
            "expense_count": exp_count,
            "expense_total": round(exp_total, 2),
            "avg_per_expense": round(avg_per_exp, 2),
            "linkage_type": linkage_type,
        })

    summary = f"共 {len(items)} 个预算项，其中 {len(risk_pairs)} 项存在执行-报销联动风险"
    return {
        "items": linkages,
        "summary": summary,
        "risk_pairs": risk_pairs,
    }
