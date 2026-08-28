"""
报告 LLM 智能起草器

按《经营分析方法论.md》§4.3 报告输出 + §3.1 信号灯机制实现：
- LLM 智能起草"关键发现"和"下一步建议"章节
- 9 诊断卡联动：直接消费 judgment/root_cause/action_plan
- 主动建议联动：消费 ProactiveInsight 关键事件
- 降级策略：LLM 不可用时使用模板化输出
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger


@dataclass
class ReportDraftSection:
    """报告章节草稿"""
    title: str
    content: str
    source: str  # "llm" / "template" / "diagnosis_card" / "proactive_insight"
    priority: int = 0
    citations: List[str] = field(default_factory=list)  # 引用的数据来源


@dataclass
class ReportDraft:
    """完整报告草稿"""
    period: str
    report_type: str  # monthly/quarterly/annual/special
    sections: List[ReportDraftSection]
    key_findings: List[str]
    next_actions: List[str]
    risks: List[str]
    generated_at: str
    llm_used: bool
    token_estimate: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "period": self.period,
            "report_type": self.report_type,
            "sections": [
                {
                    "title": s.title,
                    "content": s.content,
                    "source": s.source,
                    "priority": s.priority,
                    "citations": s.citations,
                }
                for s in self.sections
            ],
            "key_findings": self.key_findings,
            "next_actions": self.next_actions,
            "risks": self.risks,
            "generated_at": self.generated_at,
            "llm_used": self.llm_used,
            "token_estimate": self.token_estimate,
        }


class ReportLLMDrafter:
    """报告 LLM 智能起草器

    设计原则：
    - LLM 调用是可选的（降级到模板）
    - 9 诊断卡和主动建议是"硬性内容源"（确保报告与系统数据一致）
    - LLM 负责"叙述优化"和"上下文衔接"
    """

    def __init__(self, llm_client: Optional[Any] = None) -> None:
        self.llm_client = llm_client  # None 表示 LLM 不可用
        self.cache: Dict[str, str] = {}  # 简单 LRU 缓存

    async def draft_report(
        self,
        period: str,
        report_type: str,
        diagnosis_cards: Optional[List[Dict[str, Any]]] = None,
        proactive_insights: Optional[List[Dict[str, Any]]] = None,
        budget_summary: Optional[Dict[str, Any]] = None,
        alert_summary: Optional[Dict[str, Any]] = None,
    ) -> ReportDraft:
        """起草报告

        Args:
            period: 统计期间 YYYY-MM
            report_type: 报告类型
            diagnosis_cards: 9 诊断卡数据（v6.0 输出）
            proactive_insights: 主动建议列表
            budget_summary: 预算汇总
            alert_summary: 预警汇总

        Returns:
            ReportDraft 完整草稿
        """
        sections: List[ReportDraftSection] = []
        key_findings: List[str] = []
        next_actions: List[str] = []
        risks: List[str] = []
        token_estimate = 0
        llm_used = False

        # 1. 关键发现（9 诊断卡直接消费）
        if diagnosis_cards:
            for card in diagnosis_cards:
                if card.get("signal_light") in ("yellow", "red"):
                    key_findings.append(
                        f"【{card.get('card_name', '诊断卡')}】{card.get('light_reason', '')}"
                    )
                    if card.get("action_plan"):
                        next_actions.append(
                            f"{card.get('card_name')}：{card.get('action_plan')[:80]}"
                        )
                    if card.get("signal_light") == "red":
                        risks.append(
                            f"红灯卡：{card.get('card_name')} - {card.get('light_reason', '')}"
                        )

        # 2. 主动建议作为"下一步建议"输入
        if proactive_insights:
            for ins in proactive_insights[:5]:  # Top 5
                if ins.get("priority") in ("critical", "attention"):
                    next_actions.append(
                        f"[{ins.get('priority', 'info')}] {ins.get('title', '')}: {ins.get('action_label', '查看')}"
                    )

        # 3. 预算汇总（如有）
        budget_text = ""
        if budget_summary:
            rate = budget_summary.get("overall_execution_rate", 0)
            budget_text = f"本期整体预算执行率 {rate:.1f}%"
            key_findings.append(budget_text)

        # 4. 预警汇总（如有）
        alert_text = ""
        if alert_summary:
            red = alert_summary.get("by_level", {}).get("红色", 0)
            open_count = alert_summary.get("by_status", {}).get("开放", 0)
            if red > 0 or open_count > 10:
                alert_text = f"本期红色预警 {red} 条，开放预警 {open_count} 条"
                key_findings.append(alert_text)

        # 5. LLM 智能起草（叙述章节）
        if self.llm_client is not None:
            try:
                llm_section = await self._llm_draft_section(
                    period, report_type, key_findings, next_actions, risks
                )
                if llm_section:
                    sections.append(llm_section)
                    llm_used = True
                    token_estimate = llm_section.content.__len__() * 2  # 估算
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[report_drafter] LLM 起草失败，降级到模板: {e}")

        # 6. 模板化章节（兜底）
        sections.append(ReportDraftSection(
            title="本期经营摘要",
            content=self._template_executive_summary(
                period, report_type, key_findings
            ),
            source="template",
            priority=1,
            citations=["9 诊断卡数据", "预算执行表", "预警看板"],
        ))

        sections.append(ReportDraftSection(
            title="关键发现与根因",
            content=self._template_key_findings(key_findings),
            source="diagnosis_card",
            priority=2,
            citations=[c.get("card_name", "") for c in (diagnosis_cards or [])],
        ))

        if next_actions:
            sections.append(ReportDraftSection(
                title="下一步建议",
                content=self._template_next_actions(next_actions),
                source="proactive_insight",
                priority=3,
                citations=[ins.get("title", "") for ins in (proactive_insights or [])[:5]],
            ))

        if risks:
            sections.append(ReportDraftSection(
                title="风险提示",
                content=self._template_risks(risks),
                source="diagnosis_card",
                priority=4,
                citations=["红灯诊断卡"],
            ))

        return ReportDraft(
            period=period,
            report_type=report_type,
            sections=sections,
            key_findings=key_findings,
            next_actions=next_actions,
            risks=risks,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            llm_used=llm_used,
            token_estimate=token_estimate,
        )

    # ────── LLM 起草（带缓存） ──────

    async def _llm_draft_section(
        self,
        period: str,
        report_type: str,
        key_findings: List[str],
        next_actions: List[str],
        risks: List[str],
    ) -> Optional[ReportDraftSection]:
        """调用 LLM 起草经营摘要章节（带缓存）"""
        if self.llm_client is None:
            return None
        cache_key = hashlib.md5(
            json.dumps([period, report_type, key_findings, next_actions, risks], sort_keys=True).encode()
        ).hexdigest()
        if cache_key in self.cache:
            return ReportDraftSection(
                title="LLM 智能摘要",
                content=self.cache[cache_key],
                source="llm",
                priority=0,
            )
        # 调用 LLM
        prompt = self._build_llm_prompt(period, report_type, key_findings, next_actions, risks)
        try:
            response = await self.llm_client.generate(prompt)
            self.cache[cache_key] = response
            return ReportDraftSection(
                title="LLM 智能摘要",
                content=response,
                source="llm",
                priority=0,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[llm_draft] LLM call failed: {e}")
            return None

    def _build_llm_prompt(
        self, period: str, report_type: str,
        key_findings: List[str], next_actions: List[str], risks: List[str],
    ) -> str:
        return f"""你是 CFO 智能助手。请基于以下 {period} {report_type} 报告数据，起草一份 200-300 字的"本期经营摘要"。

【关键发现】
{chr(10).join('- ' + f for f in key_findings) if key_findings else '- 暂无'}

【下一步建议】
{chr(10).join('- ' + a for a in next_actions) if next_actions else '- 暂无'}

【风险提示】
{chr(10).join('- ' + r for r in risks) if risks else '- 暂无'}

要求：
1. 结构：现状-根因-行动 三段式
2. 用语：财务专业、客观、有数据支撑
3. 长度：200-300 字
4. 输出：纯文本（不要 Markdown）
"""

    # ────── 模板化章节 ──────

    def _template_executive_summary(
        self, period: str, report_type: str, key_findings: List[str]
    ) -> str:
        if not key_findings:
            return f"{period} {report_type}：整体经营平稳，各项指标处于预期范围内。"
        top3 = key_findings[:3]
        summary = f"{period} {report_type}：本期共发现 {len(key_findings)} 项关键事项。"
        summary += "其中："
        for i, f in enumerate(top3, 1):
            summary += f"（{i}）{f}；"
        return summary

    def _template_key_findings(self, findings: List[str]) -> str:
        if not findings:
            return "本期未发现重大异常。\n"
        return "\n".join(f"• {f}" for f in findings) + "\n"

    def _template_next_actions(self, actions: List[str]) -> str:
        return "\n".join(f"▶ {a}" for a in actions) + "\n"

    def _template_risks(self, risks: List[str]) -> str:
        return "\n".join(f"⚠ {r}" for r in risks) + "\n"
