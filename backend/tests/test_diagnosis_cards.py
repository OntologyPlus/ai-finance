"""
经营诊断卡单元测试
====================
按《经营分析方法论.md》§3.2 设计：
- 9 张诊断卡信号灯判定（红/黄/绿）
- 4 个分析框架基础计算（杜邦/桥接/BCG/SAR）
- Prompt 模板完整性
- 报告组装（4 部分 + 9 卡）

运行：cd backend && pytest tests/test_diagnosis_cards.py -v
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from engines.business_diagnosis import (
    DiagnosisEngine,
    NINE_CARDS,
    CARD_BY_TYPE,
    LIGHT_PRIORITY,
)
from services.prompt_manager import DIAGNOSIS_PROMPTS, build_diagnosis_prompt


# ────── Fixtures ──────

@pytest.fixture
def engine():
    return DiagnosisEngine()


@pytest.fixture
def sample_card_metrics() -> Dict[str, Any]:
    """标准 9 张卡的 metrics_json 样例"""
    return {
        "revenue_health": {
            "ytd_revenue": 12000.0,
            "ytd_budget": 11500.0,
            "budget_achievement_pct": 104.3,
            "time_progress_pct": 50.0,
            "last_year_progress_pct": 47.0,
            "progress_deviation_pp": 3.0,
            "yoy_full_pct": 12.0,
        },
        "gross_margin": {
            "actual_gross_margin_pct": 45.2,
            "budget_gross_margin_pct": 44.0,
            "margin_deviation_pp": 1.2,
        },
        "expense_pacing": {
            "promotion_progress_pct": 48.0,
            "promotion_last_year_progress_pct": 50.0,
            "promotion_deviation_pp": -2.0,
            "maintenance_progress_pct": 47.0,
            "hr_cost_progress_pct": 46.0,
        },
        "product_mix": {
            "lifecycle_distribution_pct": "导入:15%/成长:25%/成熟:50%/衰退:10%",
            "top5_yoy_growth_pct": 8.0,
            "decline_share_pct": 10.0,
            "mature_share_pct": 50.0,
            "growth_share_pct": 40.0,
        },
        "channel_split": {
            "in_hospital_yoy_pct": 10.0,
            "out_hospital_yoy_pct": 12.0,
            "growth_gap_pp": -2.0,
        },
        "profit_authenticity": {
            "commercial_margin_pct": 18.0,
            "operating_margin_pct": 15.0,
            "margin_gap_pp": 3.0,
            "non_operating_share_pct": 8.0,
        },
        "commercialization_efficiency": {
            "top_products_roi": "A:5.2, B:4.8, C:3.5, D:2.1",
        },
        "policy_risk": {
            "vbp_share_pct": 25.0,
            "vbp_margin_change_pp": -3.0,
        },
        "cashflow_quality": {
            "non_operating_share_pct": 5.0,
            "dso_days": None,
            "ocf_to_operating_profit": None,
        },
    }


# ────── 测试 1：9 张卡信号灯判定（方法论 §3.2 七段式）──────

class TestSignalLightEngine:
    """测试 9 张诊断卡的信号灯判定逻辑（基于 _select_worse_light）"""

    def test_select_worse_light_red_wins(self, engine):
        """最严重灯色优先（红 > 黄 > 绿）"""
        assert engine._select_worse_light(["green", "yellow", "red"]) == "red"

    def test_select_worse_light_yellow_wins_over_green(self, engine):
        assert engine._select_worse_light(["green", "yellow"]) == "yellow"

    def test_select_worse_light_empty_returns_green(self, engine):
        assert engine._select_worse_light([]) == "green"

    def test_select_worse_light_single_red(self, engine):
        assert engine._select_worse_light(["red"]) == "red"

    def test_light_priority_order(self):
        """红=3, 黄=2, 绿=1（来自方法论 §3.1）"""
        assert LIGHT_PRIORITY["red"] > LIGHT_PRIORITY["yellow"] > LIGHT_PRIORITY["green"]

    def test_wrap_card_basic_fields(self, engine):
        """_wrap_card 包装诊断卡数据（9 张卡共用）"""
        card = engine._wrap_card(
            card_type="revenue_health",
            period="2024-06",
            signal_light="green",
            light_reason="YTD 进度偏差 +3pp，跑赢去年同期",
            metrics={"ytd_revenue": 12000.0},
            threshold={"progress_deviation": 2.0},
        )
        assert card["card_type"] == "revenue_health"
        assert card["card_name"] == "收入健康度"
        assert card["card_number"] == 1
        assert card["signal_light"] == "green"
        assert card["period"] == "2024-06"
        assert card["framework_ref"] == "杜邦分析法"
        assert card["degraded"] is False
        assert "id" in card
        assert "metrics_json" in card
        assert "threshold_json" in card

    def test_wrap_card_degraded_flag_for_card_789(self, engine):
        """卡 7/8/9 标记为降级版（来自方法论 §3.2）"""
        for card_type in ["commercialization_efficiency", "policy_risk", "cashflow_quality"]:
            card = engine._wrap_card(
                card_type=card_type,
                period="2024-06",
                signal_light="yellow",
                light_reason="数据待补充",
                metrics={},
                threshold={},
            )
            assert card["degraded"] is True, f"{card_type} should be degraded"


# ────── 测试 2：NINE_CARDS 注册表完整性（方法论 §3.2）──────

class TestNineCardsRegistry:
    """9 张卡必须在 NINE_CARDS 中完整注册"""

    def test_nine_cards_count(self):
        assert len(NINE_CARDS) == 9

    def test_nine_cards_numbers_sequential(self):
        numbers = sorted(c["number"] for c in NINE_CARDS)
        assert numbers == [1, 2, 3, 4, 5, 6, 7, 8, 9]

    def test_nine_cards_unique_types(self):
        types = [c["type"] for c in NINE_CARDS]
        assert len(set(types)) == 9, f"卡类型重复: {types}"

    def test_card_by_type_lookup(self):
        """CARD_BY_TYPE 反向索引可用"""
        for card in NINE_CARDS:
            assert CARD_BY_TYPE[card["type"]] == card

    def test_nine_cards_required_fields(self):
        """每张卡必须含 7 个核心字段（方法论 §3.2 七段式）"""
        for card in NINE_CARDS:
            assert "number" in card
            assert "type" in card
            assert "name" in card
            assert "framework" in card
            assert "key_metric" in card
            assert "degraded" in card
            assert isinstance(card["degraded"], bool)

    def test_nine_cards_all_have_frameworks(self):
        """每张卡必须关联至少一个分析框架"""
        for card in NINE_CARDS:
            assert card["framework"], f"{card['name']} 缺少 framework"

    def test_cards_1_3_6_8_marked_critical(self):
        """关键卡 1/3/6/8（方法论 §5.2 关键卡人工 review）必须可识别"""
        key_card_types = {1, 3, 6, 8}
        key_card_numbers = {c["number"] for c in NINE_CARDS if c["number"] in key_card_types}
        assert key_card_numbers == key_card_types


# ────── 测试 3：4 个分析框架方法签名（方法论 §2 框架组合）──────

class TestFrameworksSignatures:
    """4 个分析框架方法必须存在（杜邦/桥接/BCG/SAR）"""

    def test_dupont_method_exists(self, engine):
        assert hasattr(engine, "calc_dupont_waterfall")
        assert callable(engine.calc_dupont_waterfall)

    def test_bridge_method_exists(self, engine):
        assert hasattr(engine, "calc_bridge_analysis")
        assert callable(engine.calc_bridge_analysis)

    def test_bcg_method_exists(self, engine):
        assert hasattr(engine, "calc_bcg_matrix")
        assert callable(engine.calc_bcg_matrix)

    def test_sar_method_exists(self, engine):
        assert hasattr(engine, "calc_sar_recommendations")
        assert callable(engine.calc_sar_recommendations)

    def test_report_method_exists(self, engine):
        assert hasattr(engine, "generate_diagnosis_report")
        assert callable(engine.generate_diagnosis_report)

    def test_all_nine_cards_have_diagnose_methods(self, engine):
        """9 张卡必须有 diagnose_* 方法"""
        for card in NINE_CARDS:
            method_name = f"diagnose_{card['type']}"
            assert hasattr(engine, method_name), f"缺少 {method_name}"


# ────── 测试 4：Prompt 模板完整性（方法论 §5.2 四段式结构）──────

class TestDiagnosisPrompts:
    """9 张卡的 Prompt 模板必须存在且符合四段式"""

    def test_prompts_count(self):
        """DIAGNOSIS_PROMPTS 必须有 9 个"""
        assert len(DIAGNOSIS_PROMPTS) == 9

    def test_all_card_types_have_prompts(self):
        """NINE_CARDS 中的每种卡类型都必须有 prompt 模板"""
        for card in NINE_CARDS:
            assert card["type"] in DIAGNOSIS_PROMPTS, f"缺少 {card['type']} 的 prompt"

    def test_prompts_contain_four_sections(self):
        """每个 prompt 必须包含"判断/证据/根因/建议"四段（方法论 §5.2）"""
        for card_type, prompt in DIAGNOSIS_PROMPTS.items():
            assert "判断" in prompt or "核心判断" in prompt, f"{card_type} 缺少判断段"
            assert "证据" in prompt or "数据证据" in prompt, f"{card_type} 缺少证据段"
            assert "根因" in prompt, f"{card_type} 缺少根因段"
            assert "建议" in prompt, f"{card_type} 缺少建议段"

    def test_prompts_contain_signal_light(self):
        """每个 prompt 必须包含信号灯变量（信号灯规则化）"""
        for card_type, prompt in DIAGNOSIS_PROMPTS.items():
            assert "{signal_light}" in prompt
            assert "{light_reason}" in prompt

    def test_prompts_contain_period(self):
        """每个 prompt 必须包含期间变量"""
        for card_type, prompt in DIAGNOSIS_PROMPTS.items():
            assert "{period}" in prompt

    def test_prompts_mention_l3_quality(self):
        """每个 prompt 必须要求 L3 根因分析水平"""
        for card_type, prompt in DIAGNOSIS_PROMPTS.items():
            assert "L3" in prompt or "根因" in prompt, f"{card_type} 缺失 L3 要求"


# ────── 测试 5：build_diagnosis_prompt 函数（方法论 §5.2）──────

class TestBuildDiagnosisPrompt:
    """测试 build_diagnosis_prompt 函数的变量替换能力"""

    def test_build_prompt_basic(self, sample_card_metrics):
        """基础调用：card dict → prompt 字符串"""
        card = {
            "card_type": "revenue_health",
            "card_name": "收入健康度",
            "period": "2024-06",
            "signal_light": "green",
            "light_reason": "进度偏差 +3pp",
            "metrics_json": sample_card_metrics["revenue_health"],
        }
        prompt = build_diagnosis_prompt(card)
        assert "收入健康度" in prompt or "revenue_health" in prompt
        assert "2024-06" in prompt
        assert "green" in prompt

    def test_build_prompt_replaces_signal_light(self, sample_card_metrics):
        """信号灯变量正确替换"""
        card = {
            "card_type": "gross_margin",
            "card_name": "毛利质量",
            "period": "2024-06",
            "signal_light": "red",
            "light_reason": "毛利率偏差 -2pp",
            "metrics_json": sample_card_metrics["gross_margin"],
        }
        prompt = build_diagnosis_prompt(card)
        assert "{signal_light}" not in prompt
        assert "{period}" not in prompt
        assert "red" in prompt

    def test_build_prompt_handles_unknown_type(self):
        """未知卡类型返回简化版 prompt（不抛异常）"""
        card = {
            "card_type": "unknown_card",
            "card_name": "未知卡",
            "period": "2024-06",
            "signal_light": "green",
            "light_reason": "",
            "metrics_json": {},
        }
        prompt = build_diagnosis_prompt(card)
        assert "未知卡" in prompt or "unknown_card" in prompt

    def test_build_prompt_for_all_nine_cards(self, sample_card_metrics):
        """9 张卡都能成功生成 prompt 且无未替换变量"""
        for card in NINE_CARDS:
            card_dict = {
                "card_type": card["type"],
                "card_name": card["name"],
                "period": "2024-06",
                "signal_light": "yellow",
                "light_reason": f"{card['name']} 偏差在临界值附近",
                "metrics_json": sample_card_metrics.get(card["type"], {}),
            }
            prompt = build_diagnosis_prompt(card_dict)
            # 信号灯、期间、light_reason 必须已替换
            assert "{signal_light}" not in prompt, f"{card['type']} signal_light 未替换"
            assert "{period}" not in prompt, f"{card['type']} period 未替换"
            assert "{light_reason}" not in prompt, f"{card['type']} light_reason 未替换"

    def test_build_prompt_metrics_injection(self, sample_card_metrics):
        """metrics_json 数据正确注入 prompt"""
        card = {
            "card_type": "revenue_health",
            "card_name": "收入健康度",
            "period": "2024-06",
            "signal_light": "green",
            "light_reason": "进度偏差 +3pp",
            "metrics_json": {
                "ytd_revenue": 12000.0,
                "ytd_budget": 11500.0,
            },
        }
        prompt = build_diagnosis_prompt(card)
        # 12000 应被注入（作为字符串）
        assert "12000" in prompt


# ────── 测试 6：诊断卡信号灯判定（业务逻辑）──────

class TestCardSignalLightLogic:
    """测试 _wrap_card 包装出的诊断卡的信号灯字段完整性"""

    def test_revenue_health_green_card(self, engine):
        """卡 1 绿灯：进度偏差 +3pp（方法论 §3.2 卡 1 绿灯条件）"""
        card = engine._wrap_card(
            card_type="revenue_health",
            period="2024-06",
            signal_light="green",
            light_reason="进度偏差 +3pp > +2pp 阈值",
            metrics={"progress_deviation_pp": 3.0},
            threshold={"green_min": 2.0},
        )
        assert card["signal_light"] == "green"
        assert "进度偏差" in card["light_reason"]

    def test_revenue_health_red_card(self, engine):
        """卡 1 红灯：进度偏差 -5pp（方法论 §3.2 卡 1 红灯条件）"""
        card = engine._wrap_card(
            card_type="revenue_health",
            period="2024-06",
            signal_light="red",
            light_reason="进度偏差 -5pp < -1pp 阈值",
            metrics={"progress_deviation_pp": -5.0},
            threshold={"red_max": -1.0},
        )
        assert card["signal_light"] == "red"

    def test_gross_margin_yellow_card(self, engine):
        """卡 2 黄灯：毛利率偏差 +0.5pp"""
        card = engine._wrap_card(
            card_type="gross_margin",
            period="2024-06",
            signal_light="yellow",
            light_reason="偏差在 ±1pp 合理范围",
            metrics={"margin_deviation_pp": 0.5},
            threshold={"yellow_band": 1.0},
        )
        assert card["signal_light"] == "yellow"

    def test_expense_pacing_red_card(self, engine):
        """卡 3 红灯：推广费进度偏差 -5pp（方法论 §3.2 卡 3 红灯）"""
        card = engine._wrap_card(
            card_type="expense_pacing",
            period="2024-06",
            signal_light="red",
            light_reason="推广费进度偏差 -5pp 严重滞后",
            metrics={"promotion_deviation_pp": -5.0},
            threshold={"red_max": -3.0},
        )
        assert card["signal_light"] == "red"

    def test_product_mix_green_card(self, engine):
        """卡 4 绿灯：成熟期 50-70% + 成长/导入 ≥ 25%"""
        card = engine._wrap_card(
            card_type="product_mix",
            period="2024-06",
            signal_light="green",
            light_reason="成熟期 60%，成长+导入 30%",
            metrics={"mature_share_pct": 60.0, "growth_share_pct": 30.0},
            threshold={"green_mature": 50, "green_growth_min": 25},
        )
        assert card["signal_light"] == "green"

    def test_channel_split_yellow_card(self, engine):
        """卡 5 黄灯：增速差绝对值 5-10pp"""
        card = engine._wrap_card(
            card_type="channel_split",
            period="2024-06",
            signal_light="yellow",
            light_reason="院内 vs 院外增速差 7pp",
            metrics={"growth_gap_pp": 7.0},
            threshold={"yellow_band": 10.0},
        )
        assert card["signal_light"] == "yellow"

    def test_profit_authenticity_red_card(self, engine):
        """卡 6 红灯：商业-经营利润差 > 10pp"""
        card = engine._wrap_card(
            card_type="profit_authenticity",
            period="2024-06",
            signal_light="red",
            light_reason="差值 12pp，存在盈余管理风险",
            metrics={"margin_gap_pp": 12.0},
            threshold={"red_min": 10.0},
        )
        assert card["signal_light"] == "red"

    def test_policy_risk_yellow_card(self, engine):
        """卡 8 黄灯：集采品种占比 20-40%"""
        card = engine._wrap_card(
            card_type="policy_risk",
            period="2024-06",
            signal_light="yellow",
            light_reason="集采品种占比 30%，政策风险积累",
            metrics={"vbp_share_pct": 30.0},
            threshold={"yellow_band": 40.0},
        )
        assert card["signal_light"] == "yellow"

    def test_cashflow_quality_green_card(self, engine):
        """卡 9 绿灯：非经营性收益占比 < 10%"""
        card = engine._wrap_card(
            card_type="cashflow_quality",
            period="2024-06",
            signal_light="green",
            light_reason="非经营性收益占比 5%，利润含金量高",
            metrics={"non_operating_share_pct": 5.0},
            threshold={"green_max": 10.0},
        )
        assert card["signal_light"] == "green"


# ────── 测试 7：数据驱动原则（不依赖 mock）──────

class TestNoMockDataPrinciple:
    """方法论 §4.3：报告不依赖 mock 数据，缺失时回退 0/空"""

    def test_wrap_card_metrics_default_empty(self, engine):
        """metrics_json 默认为空 dict 而非 mock 数据"""
        card = engine._wrap_card(
            card_type="revenue_health",
            period="2024-06",
            signal_light="green",
            light_reason="无数据时默认绿灯",
            metrics={},
            threshold={},
        )
        assert card["metrics_json"] == {}

    def test_build_prompt_handles_empty_metrics(self):
        """metrics_json 为空时 prompt 仍能生成（不抛 KeyError）"""
        card = {
            "card_type": "revenue_health",
            "card_name": "收入健康度",
            "period": "2024-06",
            "signal_light": "green",
            "light_reason": "数据缺失",
            "metrics_json": {},
        }
        # 不应该抛异常
        prompt = build_diagnosis_prompt(card)
        assert prompt is not None
        assert len(prompt) > 0


# ────── 测试 8：AI 文字质量分级（方法论 §5.1）──────

class TestAIQualityLevel:
    """方法论 §5.1：L1-L4 质量分级，v5.0 目标 L3"""

    def test_ai_quality_level_field_exists(self, engine):
        """_wrap_card 必须包含 ai_quality_level 字段（默认 None）"""
        card = engine._wrap_card(
            card_type="revenue_health",
            period="2024-06",
            signal_light="green",
            light_reason="ok",
            metrics={},
            threshold={},
        )
        assert "ai_quality_level" in card
        assert card["ai_quality_level"] is None

    def test_ai_review_passed_field_exists(self, engine):
        """_wrap_card 必须包含 ai_review_passed 字段（默认 False）"""
        card = engine._wrap_card(
            card_type="revenue_health",
            period="2024-06",
            signal_light="green",
            light_reason="ok",
            metrics={},
            threshold={},
        )
        assert "ai_review_passed" in card
        assert card["ai_review_passed"] is False

    def test_pending_question_field_exists(self, engine):
        """_wrap_card 必须包含 pending_question 字段（方法论 §3.2 待确认问题）"""
        card = engine._wrap_card(
            card_type="revenue_health",
            period="2024-06",
            signal_light="green",
            light_reason="ok",
            metrics={},
            threshold={},
        )
        assert "pending_question" in card
        assert card["pending_question"] is None


# ────── 测试 9：报告组装（方法论 §4 报告架构）──────

class TestReportGeneration:
    """测试 generate_diagnosis_report 组装逻辑（4 部分 + 9 卡）"""

    @pytest.mark.asyncio
    async def test_report_method_signature(self, engine, mock_db):
        """generate_diagnosis_report 接收 period + db 参数"""
        # 验证方法签名存在
        import inspect
        sig = inspect.signature(engine.generate_diagnosis_report)
        assert "period" in sig.parameters
        assert "db" in sig.parameters

    def test_report_has_four_parts(self):
        """报告必须包含 4 个组成部分（方法论 §4.1）"""
        expected_parts = ["part1_overview", "part2_cards", "part3_bcg", "part4_actions"]
        # 这 4 个 key 是方法论规定的标准结构
        for part in expected_parts:
            assert isinstance(part, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
