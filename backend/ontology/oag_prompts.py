from __future__ import annotations

from typing import Dict


_BUDGET_EXECUTION_ANALYSIS_PROMPT = """你是一个基于Ontology的财经分析AI。请基于以下Ontology上下文分析预算执行率。

{ontology_context}

分析要求：
1. 计算当前执行率与目标执行率的偏差
2. 识别偏差的根本原因（从Ontology对象和关系中推导）
3. 给出3GAP分析（目标差距、执行差距、预测变动）
4. 给出3List建议（必赢清单、改善清单、资源清单）

当前数据：
- L1科目: {l1_code}
- 年度预算: {annual_amount}元
- 已使用: {used_amount}元
- 目标执行率: {target_rate}%
- 实际执行率: {actual_rate}%

请确保：
- 所有结论必须标注Ontology来源（如 obj_budget_item#预算项目）
- 数值引用必须与Ontology属性一致
- 如果上下文不足以得出结论，请明确说明
"""

_ALERT_RESPONSE_SUGGESTION_PROMPT = """你是一个基于Ontology的预警响应AI。请基于以下Ontology上下文为预警响应提供建议。

{ontology_context}

预警信息：
- 预警级别: {alert_level}
- 预警类型: {alert_type}
- L1科目: {l1_code}
- 偏差率: {deviation_rate}%
- 触发值: {trigger_value}元
- 阈值: {threshold_value}元

请提供：
1. 响应建议（业务单元应采取的整改措施）
2. 根因分析（基于Ontology关系链推导）
3. 需要确认的关键问题（财经BP应确认的事项）
4. 升级条件（什么情况下应升级到上级管理层）

请确保：
- 建议必须基于Ontology中的对象和关系
- 引用相关硬规则(HR-*)和软规则(SR-*)
- 如果预警涉及红色级别，必须建议立即行动
"""

_B2A_CONVERSION_SUGGESTION_PROMPT = """你是一个基于Ontology的B→A转换建议AI。请基于以下Ontology上下文评估B→A转换的可行性。

{ontology_context}

转换信息：
- 预算项目ID: {budget_id}
- 当前类别: B类(弹性支出)
- 里程碑季度: {milestone_period}
- 里程碑达标证据: {milestone_evidence}
- 年度预算: {annual_amount}元
- 已使用: {used_amount}元

请评估：
1. 里程碑是否达标（基于Ontology中的里程碑定义）
2. 转换后的管控变化（B→A意味着从弹性管控变为先批后用）
3. 转换后的冻结额度建议
4. 是否需要向管委会提交专项报告

请确保：
- 评估必须基于硬规则HR-004(先批后用)和HR-009(里程碑延期报备)
- 引用相关Ontology对象和关系
- 明确说明转换的前置条件是否满足
"""

OAG_PROMPT_TEMPLATES: Dict[str, str] = {
    "budget_execution_analysis": _BUDGET_EXECUTION_ANALYSIS_PROMPT,
    "alert_response_suggestion": _ALERT_RESPONSE_SUGGESTION_PROMPT,
    "b2a_conversion_suggestion": _B2A_CONVERSION_SUGGESTION_PROMPT,
}


def get_oag_prompt(template_name: str) -> str:
    return OAG_PROMPT_TEMPLATES.get(template_name, "")


def format_oag_prompt(
    template_name: str, ontology_context: str, **kwargs
) -> str:
    template = get_oag_prompt(template_name)
    if not template:
        return ""

    return template.format(
        ontology_context=ontology_context,
        **kwargs,
    )
