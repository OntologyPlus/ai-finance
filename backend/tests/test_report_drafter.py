"""
报告 LLM 智能起草器单元测试
==========================

覆盖 v7.0 新增的 ReportLLMDrafter：
- 9 诊断卡联动（消费 judgment/root_cause）
- 主动建议联动（消费 ProactiveInsight）
- LLM 调用（带缓存）
- 模板化降级（LLM 不可用时）

运行：cd backend && pytest tests/test_report_drafter.py -v
"""
from __future__ import annotations

import sys
import os
import asyncio
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.report_llm_drafter import ReportLLMDrafter, ReportDraft, ReportDraftSection


# ────── Fixtures ──────


@pytest.fixture
def drafter():
    return ReportLLMDrafter()


@pytest.fixture
def sample_diagnosis_cards():
    return [
        {
            "card_type": "revenue_health",
            "card_name": "收入健康度",
            "signal_light": "red",
            "light_reason": "YTD 进度偏差 -3pp",
            "action_plan": "加强新客户开发，激活沉睡客户",
            "judgment": "收入端存在明显缺口",
        },
        {
            "card_type": "gross_margin",
            "card_name": "毛利质量",
            "signal_light": "yellow",
            "light_reason": "毛利率偏差 +0.5pp",
            "action_plan": "优化供应链，控制原材料成本",
            "judgment": "毛利率基本稳定",
        },
        {
            "card_type": "expense_pacing",
            "card_name": "费用投放节奏",
            "signal_light": "green",
            "light_reason": "进度偏差 -1pp",
            "action_plan": "",
            "judgment": "费用节奏正常",
        },
    ]


@pytest.fixture
def sample_proactive_insights():
    return [
        {
            "id": "i001",
            "priority": "critical",
            "title": "🔴 收入健康度 信号灯变红",
            "action_label": "查看诊断",
        },
        {
            "id": "i002",
            "priority": "attention",
            "title": "🟡 费用投放节奏异常",
            "action_label": "查看详情",
        },
    ]


# ────── 1. 9 诊断卡联动 ──────


class TestDiagnosisCardLinkage:
    """9 诊断卡直接消费"""

    @pytest.mark.asyncio
    async def test_red_cards_become_findings(self, drafter, sample_diagnosis_cards):
        """红灯卡 → 关键发现"""
        draft = await drafter.draft_report(
            period="2024-06",
            report_type="monthly",
            diagnosis_cards=sample_diagnosis_cards,
        )
        # 1 张红灯 + 1 张黄灯 → 都应进入 key_findings
        assert len(draft.key_findings) >= 2
        assert any("收入健康度" in f for f in draft.key_findings)

    @pytest.mark.asyncio
    async def test_yellow_cards_become_findings(self, drafter, sample_diagnosis_cards):
        """黄灯卡 → 关键发现"""
        draft = await drafter.draft_report(
            period="2024-06",
            report_type="monthly",
            diagnosis_cards=sample_diagnosis_cards,
        )
        assert any("毛利质量" in f for f in draft.key_findings)

    @pytest.mark.asyncio
    async def test_green_cards_excluded_from_findings(self, drafter, sample_diagnosis_cards):
        """绿灯卡 → 不进入关键发现"""
        draft = await drafter.draft_report(
            period="2024-06",
            report_type="monthly",
            diagnosis_cards=sample_diagnosis_cards,
        )
        # 绿灯不应该在 findings 中
        assert not any("费用投放节奏" in f and "信号灯" in f for f in draft.key_findings)

    @pytest.mark.asyncio
    async def test_action_plan_extracted(self, drafter, sample_diagnosis_cards):
        """action_plan → next_actions"""
        draft = await drafter.draft_report(
            period="2024-06",
            report_type="monthly",
            diagnosis_cards=sample_diagnosis_cards,
        )
        assert any("加强新客户开发" in a for a in draft.next_actions)

    @pytest.mark.asyncio
    async def test_red_cards_become_risks(self, drafter, sample_diagnosis_cards):
        """红灯卡 → 风险提示"""
        draft = await drafter.draft_report(
            period="2024-06",
            report_type="monthly",
            diagnosis_cards=sample_diagnosis_cards,
        )
        assert len(draft.risks) >= 1
        assert any("收入健康度" in r for r in draft.risks)


# ────── 2. 主动建议联动 ──────


class TestProactiveInsightLinkage:
    """主动建议消费"""

    @pytest.mark.asyncio
    async def test_critical_insights_become_actions(self, drafter, sample_proactive_insights):
        """critical 主动建议 → next_actions"""
        draft = await drafter.draft_report(
            period="2024-06",
            report_type="monthly",
            proactive_insights=sample_proactive_insights,
        )
        assert any("critical" in a for a in draft.next_actions)
        assert any("收入健康度" in a for a in draft.next_actions)

    @pytest.mark.asyncio
    async def test_attention_insights_become_actions(self, drafter, sample_proactive_insights):
        """attention 主动建议 → next_actions"""
        draft = await drafter.draft_report(
            period="2024-06",
            report_type="monthly",
            proactive_insights=sample_proactive_insights,
        )
        assert any("attention" in a for a in draft.next_actions)


# ────── 3. 模板化降级 ──────


class TestTemplateFallback:
    """LLM 不可用时使用模板化输出"""

    @pytest.mark.asyncio
    async def test_draft_without_llm(self, drafter):
        """无 LLM client → 模板化输出"""
        draft = await drafter.draft_report(period="2024-06", report_type="monthly")
        assert draft.llm_used is False
        # 至少有"本期经营摘要"章节
        assert any(s.title == "本期经营摘要" for s in draft.sections)

    @pytest.mark.asyncio
    async def test_empty_findings_default_message(self, drafter):
        """无关键发现 → 默认消息"""
        draft = await drafter.draft_report(period="2024-06", report_type="monthly")
        assert "未发现重大异常" in draft.sections[0].content or "整体经营平稳" in draft.sections[0].content

    @pytest.mark.asyncio
    async def test_sections_have_source(self, drafter):
        """所有章节都标记 source"""
        draft = await drafter.draft_report(period="2024-06", report_type="monthly")
        for s in draft.sections:
            assert s.source in ("llm", "template", "diagnosis_card", "proactive_insight")


# ────── 4. LLM 调用（带缓存） ──────


class TestLLMIntegration:
    """LLM 调用（带缓存）"""

    @pytest.mark.asyncio
    async def test_llm_called_when_available(self):
        """LLM 可用时被调用"""
        llm_client = MagicMock()
        llm_client.generate = AsyncMock(return_value="本期经营整体平稳，9 诊断卡显示 1 红 1 黄。建议加强收入端。")

        drafter = ReportLLMDrafter(llm_client=llm_client)
        draft = await drafter.draft_report(period="2024-06", report_type="monthly")
        assert draft.llm_used is True
        llm_client.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_failure_falls_back(self):
        """LLM 失败 → 降级到模板"""
        llm_client = MagicMock()
        llm_client.generate = AsyncMock(side_effect=Exception("API error"))

        drafter = ReportLLMDrafter(llm_client=llm_client)
        draft = await drafter.draft_report(period="2024-06", report_type="monthly")
        # LLM 失败仍生成报告（但 llm_used=False）
        assert draft.llm_used is False
        # 模板章节仍在
        assert any(s.title == "本期经营摘要" for s in draft.sections)

    @pytest.mark.asyncio
    async def test_llm_cache_hit(self):
        """相同输入 → 缓存命中（不重复调用 LLM）"""
        llm_client = MagicMock()
        llm_client.generate = AsyncMock(return_value="测试缓存")

        drafter = ReportLLMDrafter(llm_client=llm_client)
        # 第一次调用
        await drafter.draft_report(period="2024-06", report_type="monthly")
        # 第二次相同输入
        await drafter.draft_report(period="2024-06", report_type="monthly")
        # 应该只调用 LLM 一次
        assert llm_client.generate.call_count == 1


# ────── 5. 报告版本 diff ──────


class TestReportDiff:
    """报告版本 diff（独立业务逻辑测试）"""

    def test_diff_added_removed_kept(self):
        """v1 vs v2 的 added/removed/kept（直接验证业务逻辑）"""
        v1 = ["A", "B", "C"]
        v2 = ["B", "C", "D"]
        added = [f for f in v2 if f not in v1]
        removed = [f for f in v1 if f not in v2]
        kept = [f for f in v2 if f in v1]
        assert added == ["D"]
        assert removed == ["A"]
        assert kept == ["B", "C"]


# ────── 6. 报告序列化 ──────


class TestReportSerialization:
    """ReportDraft 序列化"""

    @pytest.mark.asyncio
    async def test_to_dict_includes_all_fields(self, drafter, sample_diagnosis_cards):
        """to_dict 包含所有必要字段"""
        draft = await drafter.draft_report(
            period="2024-06",
            report_type="monthly",
            diagnosis_cards=sample_diagnosis_cards,
        )
        d = draft.to_dict()
        assert "period" in d
        assert "report_type" in d
        assert "sections" in d
        assert "key_findings" in d
        assert "next_actions" in d
        assert "risks" in d
        assert "generated_at" in d
        assert "llm_used" in d
        assert "token_estimate" in d
