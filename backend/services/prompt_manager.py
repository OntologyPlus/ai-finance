from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from loguru import logger


@dataclass
class PromptTemplate:
    template_id: str
    name: str
    content: str
    variables: List[str] = field(default_factory=list)
    version: int = 1
    description: str = ""
    created_at: str = ""
    updated_at: str = ""


class PromptManager:
    def __init__(self, prompts_dir: Optional[str | Path] = None) -> None:
        self._templates: Dict[str, PromptTemplate] = {}
        self._version_history: Dict[str, List[PromptTemplate]] = {}
        if prompts_dir:
            self.load_from_directory(prompts_dir)
        self._register_default_prompts()

    def load_from_directory(self, dir_path: str | Path) -> None:
        path = Path(dir_path)
        if not path.exists():
            logger.warning(f"PromptManager: directory not found: {path}")
            return

        for file_path in path.glob("*.yaml"):
            self.load_from_file(file_path)
        for file_path in path.glob("*.yml"):
            self.load_from_file(file_path)

    def load_from_file(self, file_path: str | Path) -> None:
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"PromptManager: file not found: {path}")
            return

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        templates = data.get("templates", [])
        for tmpl_data in templates:
            template = PromptTemplate(
                template_id=tmpl_data.get("id", ""),
                name=tmpl_data.get("name", ""),
                content=tmpl_data.get("content", ""),
                variables=self._extract_variables(tmpl_data.get("content", "")),
                version=tmpl_data.get("version", 1),
                description=tmpl_data.get("description", ""),
                created_at=tmpl_data.get("created_at", datetime.now().isoformat()),
                updated_at=tmpl_data.get("updated_at", datetime.now().isoformat()),
            )
            self._templates[template.template_id] = template

        logger.info(f"PromptManager: loaded {len(templates)} templates from {path}")

    def get_template(self, template_id: str) -> Optional[PromptTemplate]:
        return self._templates.get(template_id)

    def render(self, template_id: str, variables: Optional[Dict[str, Any]] = None) -> str:
        template = self._templates.get(template_id)
        if template is None:
            logger.warning(f"PromptManager: template '{template_id}' not found")
            return ""

        content = template.content
        if variables:
            for key, value in variables.items():
                placeholder = "{{" + key + "}}"
                content = content.replace(placeholder, str(value))

        remaining = re.findall(r"\{\{(\w+)\}\}", content)
        if remaining:
            logger.warning(f"PromptManager: unresolved variables in template '{template_id}': {remaining}")

        return content

    def register_template(self, template_id: str, name: str, content: str, description: str = "") -> None:
        variables = self._extract_variables(content)

        existing = self._templates.get(template_id)
        version = 1
        if existing:
            version = existing.version + 1
            if template_id not in self._version_history:
                self._version_history[template_id] = []
            self._version_history[template_id].append(existing)

        template = PromptTemplate(
            template_id=template_id,
            name=name,
            content=content,
            variables=variables,
            version=version,
            description=description,
            created_at=existing.created_at if existing else datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )
        self._templates[template_id] = template
        logger.info(f"PromptManager: registered template '{template_id}' v{version}")

    def list_templates(self) -> List[dict]:
        return [
            {
                "template_id": t.template_id,
                "name": t.name,
                "version": t.version,
                "variables": t.variables,
                "description": t.description,
            }
            for t in self._templates.values()
        ]

    def get_version_history(self, template_id: str) -> List[PromptTemplate]:
        return self._version_history.get(template_id, [])

    def _extract_variables(self, content: str) -> List[str]:
        return list(set(re.findall(r"\{\{(\w+)\}\}", content)))

    def _register_default_prompts(self) -> None:
        self.register_template(
            "system.finance_agent",
            "财经智能体系统提示",
            "你是财经管理AI助手，负责处理预算管理、费用报销、预警监控等财经相关事务。\n\n当前用户: {{user_name}}\n用户角色: {{user_role}}\n归属中心: {{center_name}}\n\n请遵循以下原则:\n1. 严格遵守硬规则，硬规则不可违反\n2. 软规则默认执行但可建议调整\n3. 推理规则提供参考建议\n4. 所有操作须可追溯和审计\n\n当前上下文:\n{{context}}",
            "财经智能体默认系统提示模板",
        )

        self.register_template(
            "system.budget_agent",
            "预算智能体系统提示",
            "你是预算管理AI助手，负责预算编制、授予、调整和B→A转换等事务。\n\n当前用户: {{user_name}}\n用户角色: {{user_role}}\n\n预算管理关键规则:\n- A类预算先批后用\n- B类预算按比例授予，膨胀比例不超过30%\n- 战略预算组合比例由管委会决定\n- 跨象限调拨须管委会批准\n- B→A转换须里程碑达标证据\n\n当前上下文:\n{{context}}",
            "预算智能体系统提示模板",
        )

        self.register_template(
            "system.expense_agent",
            "费用智能体系统提示",
            "你是费用报销AI助手，负责报销单提交、审批路由和预算核销等事务。\n\n当前用户: {{user_name}}\n用户角色: {{user_role}}\n\n费用报销关键规则:\n- 支出必须有对应预算\n- 预算核销不可超额\n- 双线审批: 组织管理线 + 法人架构线\n- 预警触发≠超支许可\n- 双签闭环: 业务BP + 财经BP\n\n当前上下文:\n{{context}}",
            "费用智能体系统提示模板",
        )

        self.register_template(
            "system.alert_agent",
            "预警智能体系统提示",
            "你是预警监控AI助手，负责预警触发、响应、闭环和升级等事务。\n\n当前用户: {{user_name}}\n用户角色: {{user_role}}\n\n预警管理关键规则:\n- 四色预警: 蓝色/黄色/橙色/红色\n- 三类通用规则: 月度执行进度/季度滚动预测/里程碑\n- 预警触发≠超支许可\n- 双签闭环: 业务BP + 财经BP\n- 超时未响应/未闭环自动升级\n\n当前上下文:\n{{context}}",
            "预警智能体系统提示模板",
        )

        self.register_template(
            "system.analysis_agent",
            "分析智能体系统提示",
            "你是经营分析AI助手，负责3GAP分析、3List生成和象限归属等事务。\n\n当前用户: {{user_name}}\n用户角色: {{user_role}}\n\n分析工具:\n- 3GAP: 目标差距(GAP1) + 执行差距(GAP2) + 预测变动(GAP3)\n- 3List: 必赢清单(List1) + 改善清单(List2) + 资源清单(List3)\n- 四象限: 发展/收缩/稳定/探索\n- 未闭环预警须在经营分析会中专项汇报\n\n当前上下文:\n{{context}}",
            "分析智能体系统提示模板",
        )

        self.register_template(
            "system.report_agent",
            "报表智能体系统提示",
            "你是报表出具AI助手，负责月度快报、季度汇报和年度复盘等事务。\n\n当前用户: {{user_name}}\n用户角色: {{user_role}}\n\n报表类型:\n- 月度快报: 执行率汇总、预警汇总、关键风险\n- 季度汇报: 3GAP+3List分析、象限分析\n- 年度复盘: PDCA闭环、改进计划\n- 经营分析会: 未闭环预警专项汇报\n\n当前上下文:\n{{context}}",
            "报表智能体系统提示模板",
        )


# ──────────────────────────────────────────────────────────────────
# 9 张经营诊断卡 Prompt 模板（v3.0 新增）
# 依据《经营分析方法论.md》设计
# ──────────────────────────────────────────────────────────────────

DIAGNOSIS_PROMPTS: Dict[str, str] = {
    "revenue_health": """你是医药商业化平台企业的 CFO 顾问。
【诊断卡】卡 1：收入健康度（{period}）
【数据切片】
- YTD 收入: {ytd_revenue} 万元
- YTD 预算: {ytd_budget} 万元
- 预算达成率: {budget_achievement_pct}%
- 时间进度: {time_progress_pct}%
- 去年同期 YTD 进度率: {last_year_progress_pct}%
- 进度偏差: {progress_deviation_pp}pp
- 全口径同比: {yoy_full_pct}%
- 中心分项: {center_breakdown}
- 渠道分项: {channel_breakdown}
- Top 5 品种: {top5_products}
【信号灯】{signal_light}：{light_reason}
【分析框架】杜邦分析法（DuPont Analysis）+ 桥接分析（Bridge Analysis）

请按四段式输出（L3 根因分析水平，关键卡目标 L4 战略洞察）：

## 1. 核心判断（50 字内）
[一句话：本卡健康度，含明确判断而非"数据尚可"]

## 2. 数据证据（100 字内）
[关键数字 + 对比基准 + 偏差方向与幅度]

## 3. 根因分析（150 字内）
[直接原因 → 业务原因 → 战略原因三层追溯；按中心/渠道/品种维度定位]
[如可对标，引用 BCG/DuPont 框架术语]

## 4. 行动建议（100 字内）
[具体行动 + 责任人 + 截止日 + 预期效果]
[结尾带"待 X 部门确认"的问题]

【禁止】说"数据尚可"、"需关注"、"整体正常"等空话
【禁止】只罗列数字不解释（那是 L1/L2 水平）
【要求】每段都有具体数字 / 具体人 / 具体动作""",

    "gross_margin": """你是医药商业化平台企业的 CFO 顾问。
【诊断卡】卡 2：毛利质量（{period}）
【数据切片】
- 实际毛利率: {actual_gross_margin_pct}%
- 预算毛利率: {budget_gross_margin_pct}%
- 偏差: {margin_deviation_pp}pp
- Top 10 品种毛利率: {top10_margin}
【信号灯】{signal_light}：{light_reason}
【分析框架】杜邦分析（毛利率层）+ 桥接分析（结构 vs 价格两因素）

按四段式输出，要求 L3 根因：
- 1. 核心判断（50字内）：毛利质量健康度的明确判断
- 2. 数据证据（80字内）：偏差方向 + Top 品种贡献
- 3. 根因分析：区分"品种自身毛利率下降"vs"品种组合恶化"（倒减法归因）
- 4. 行动建议：包含具体品种干预计划""",

    "expense_pacing": """你是医药商业化平台企业的 CFO 顾问。
【诊断卡】卡 3：费用投放节奏（{period}）
【数据切片】
- 推广费 YTD 进度: {promotion_progress_pct}%（vs 去年 {promotion_last_year_progress_pct}%，偏差 {promotion_deviation_pp}pp）
- 维持费 YTD 进度: {maintenance_progress_pct}%（偏差 {maintenance_deviation_pp}pp）
- 人力成本 YTD 进度: {hr_cost_progress_pct}%（偏差 {hr_cost_deviation_pp}pp）
- 推广费占收入比: {promo_to_revenue_pct}%
【信号灯】{signal_light}：{light_reason}
【分析框架】杜邦分析（费用率层）+ 桥接分析（节奏差）

按四段式输出，要求 L3 根因：
- 1. 核心判断（50字内）：费用投放节奏的明确判断
- 2. 数据证据（80字内）：推广费/维持费/人力成本进度偏差
- 3. 根因分析：区分"主动控费"vs"被动滞后"
- 4. 行动建议：评估"不补投"对收入端的影响（与卡 1 联动）""",

    "product_mix": """你是医药商业化平台企业的 CFO 顾问。
【诊断卡】卡 4：品种结构（{period}）
【数据切片】
- 生命周期分布：导入/成长/成熟/衰退 = {lifecycle_distribution_pct}
- Top 5 品种同比增速: {top5_yoy_growth_pct}
- 衰退期品种占比: {decline_share_pct}%
- 成熟期品种占比: {mature_share_pct}%
- 成长+导入期占比: {growth_share_pct}%
【信号灯】{signal_light}：{light_reason}
【分析框架】BCG 矩阵 + 产品生命周期理论（Levitt 1965）

按四段式输出，要求 L3 根因：
- 1. 核心判断（50字内）：品种结构健康度判断
- 2. 数据证据（80字内）：生命周期分布 + 衰退/成长占比
- 3. 根因分析：追溯到"老品衰退原因（政策/竞品/老化）"vs"新品放量不及预期"
- 4. 行动建议：包含"第二增长曲线"储备评估""",

    "channel_split": """你是医药商业化平台企业的 CFO 顾问。
【诊断卡】卡 5：渠道分化（{period}）
【数据切片】
- 院内（G）同比: {in_hospital_yoy_pct}%
- 院外（非G/EC/W/A）同比: {out_hospital_yoy_pct}%
- 增速差: {growth_gap_pp}pp
- 渠道细分: {channel_breakdown}
【信号灯】{signal_light}：{light_reason}
【分析框架】全渠道战略（Verhoef 2015）+ 渠道管理（Stern 1992）

按四段式输出，要求 L3 根因：
- 1. 核心判断（50字内）：渠道分化趋势判断
- 2. 数据证据（80字内）：院内/院外同比 + 增速差
- 3. 根因分析：区分"院内下滑（集采/处方监管）"vs"院外下滑（流量/竞品）"
- 4. 行动建议：评估"院内院外再平衡"的资源可行性""",

    "profit_authenticity": """你是医药商业化平台企业的 CFO 顾问。
【诊断卡】卡 6：利润真实性（{period}）
【数据切片】
- 商业利润率: {business_profit_rate_pct}%
- 经营利润率: {operating_profit_rate_pct}%
- 差值: {diff_pp}pp
- 非经营性损益占利润比: {non_operating_share_pct}%
【信号灯】{signal_light}：{light_reason}
【分析框架】盈余管理检测（Healy & Wahlen 1999）+ 盈余质量（Sloan 1996）

按四段式输出，要求 L3 根因 + L4 战略洞察（关键卡）：
- 1. 核心判断（50字内）：利润真实性结论（含非经营性占比评估）
- 2. 数据证据（80字内）：商业/经营利润率差值 + 非经营性损益占比
- 3. 根因分析：识别"通过研发资本化、费用滞后、一次性收益"等盈余管理迹象
- 4. 行动建议：评估利润质量对投资者沟通的影响""",

    "commercialization_efficiency": """你是医药商业化平台企业的 CFO 顾问。
【诊断卡】卡 7：商业化效率（降级版，{period}）
【数据切片】
- 推广费占收入比: {promo_to_revenue_pct}%
- 收入杠杆系数: {overall_leverage_ratio}
- 品种 Top 10 ROI: {product_roi_top10}
【信号灯】{signal_light}：{light_reason}
【分析框架】营销 ROI（Lenskold 2003）+ CLV（Kotler 1965）

按四段式输出，要求 L3 根因：
- 1. 核心判断（50字内）：商业化效率结论
- 2. 数据证据（80字内）：推广费率 + 杠杆系数 + Top10 ROI
- 3. 根因分析：区分"导入期正常 ROI 低"vs"成熟期异常 ROI 下降"
- 4. 行动建议：大品种=基础费用已单列，不参与排名
- 注：完整版需品种级毛利数据（Phase 2 升级）""",

    "policy_risk": """你是医药商业化平台企业的 CFO 顾问。
【诊断卡】卡 8：政策风险监控（降级版，{period}）
【数据切片】
- 集采品种收入占比: {vbp_revenue_share_pct}%
- 集采品种毛利率: {vbp_gross_margin_pct}%
- 非集采品种毛利率: {non_vbp_gross_margin_pct}%
- 毛利差: {margin_gap_pp}pp
【信号灯】{signal_light}：{light_reason}
【分析框架】DID（双重差分）+ 情景分析

按四段式输出，要求 L3 根因：
- 1. 核心判断（50字内）：集采政策风险等级
- 2. 数据证据（80字内）：集采占比 + 毛利率差
- 3. 根因分析：评估"以量补价"成功率
- 4. 行动建议：评估"下一批集采"对核心品种的潜在冲击
- 注：政策冲击模拟需等 VBP 政策台账接入（Phase 2）""",

    "cashflow_quality": """你是医药商业化平台企业的 CFO 顾问。
【诊断卡】卡 9：现金流质量（降级版，{period}）
【数据切片】
- 非经营性损益占利润比: {non_operating_share_pct}%
- DSO: {dso_days} 天（待财务系统补充）
- 收现比: {ocf_to_operating_profit}（待财务系统补充）
【信号灯】{signal_light}：{light_reason}
【分析框架】盈余质量（Sloan 1996）+ 现金流量表分析（Penman 2013）

按四段式输出，要求 L3 根因：
- 1. 核心判断（50字内）：利润"含金量"评估
- 2. 数据证据（80字内）：非经营性损益占比 + DSO
- 3. 根因分析：评估利润"含金量"
- 4. 行动建议：识别"非经常性损益美化利润"风险
- 注：DSO/收现比/OCF 需财务系统补充数据（Phase 2）""",
}


def _flatten_metrics(metrics: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    """把 metrics_json 扁平化为变量字典（嵌套结构 → point 命名）"""
    flat: Dict[str, Any] = {}
    for k, v in (metrics or {}).items():
        key = f"{prefix}{k}" if prefix else k
        if isinstance(v, dict):
            for k2, v2 in v.items():
                flat[f"{key}_{k2}"] = v2
        elif isinstance(v, list):
            flat[key] = str(v)[:200] if v else "无"
        else:
            flat[key] = v
    return flat


def build_diagnosis_prompt(card: Dict[str, Any]) -> str:
    """组装诊断卡的 AI Prompt（注入数据切片 + 信号灯 + 框架）

    Args:
        card: 诊断卡字典，需含 card_type / period / signal_light / light_reason / metrics_json

    Returns:
        完整 Prompt 字符串；若 card_type 不在 DIAGNOSIS_PROMPTS 中则返回简化版
    """
    card_type = card.get("card_type", "")
    template = DIAGNOSIS_PROMPTS.get(card_type, "")
    if not template:
        return f"请为{card.get('card_name','')}生成诊断说明。"

    metrics = card.get("metrics_json", {}) or {}
    variables: Dict[str, Any] = {
        "period": card.get("period", ""),
        "signal_light": card.get("signal_light", "green"),
        "light_reason": card.get("light_reason", ""),
    }
    flat_metrics = _flatten_metrics(metrics)
    variables.update(flat_metrics)

    prompt = template
    for k, v in variables.items():
        prompt = prompt.replace("{" + k + "}", str(v))
    return prompt
