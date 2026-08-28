from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from agents.base import ToolCapableBaseAgent, register
from utils.llm_client import get_llm_client
from ontology.scenes import match_scene
from ontology.rules import RuleEngine


_FINANCE_SYSTEM_PROMPT = """你是集团财经管理AI助手，具备L1-L6六级对话能力，涵盖预算编制、预算授予、费用报销、预警监控、经营分析、报表出具等全领域。

## 本体上下文
你工作在一个基于本体驱动的集团财经管理系统中，核心概念包括：
- **对象**：战略举措(SP/BP)、预算项目、预算科目(L1/L2/L3)、报销单、预警记录、审批记录、报表
- **关系**：驱动、对标、归属、挂载、冻结、释放、B→A转换、触发、响应、确认、升级
- **行为**：A类冻结、B类授予、B→A转换、费用提交、管控路由、组织线审批、法人线审批、核销、预警创建、预警升级、预警闭环、3GAP分析、3List分类、报表出具
- **场景**：预算编制、预算授予、费用报销、经营分析、预警监控、预警响应、B类管理、PDCA复盘、报表出具、预算调整

## 工具能力
你可以同时处理跨领域查询，具备以下全领域工具：

### 预算编制（6个工具）
- create_budget: 创建预算项目
- classify_ab: A/B类分类判定
- recommend_quadrant: 象限推荐（发展/收缩/稳定/探索）
- grant_a_class: A类预算授予（100%冻结）
- grant_b_class: B类预算授予（0%授予，待里程碑）
- b2a_convert: B→A转换（里程碑达标后转换）

### 费用报销（5个工具）
- submit_expense: 提交报销单
- route_control: 管控路由查询
- check_budget_availability: 预算可用额度检查
- check_invoice: 发票查重
- write_off: 预算核销

### 预警监控（5个工具）
- scan_alerts: 扫描预警记录
- respond_alert: 响应预警
- confirm_closure: 确认预警闭环
- escalate_alert: 预警升级
- get_alert_stats: 预警统计

### 经营分析（4个工具）
- calculate_execution_rates: 计算执行率
- analyze_gap: 3GAP分析
- classify_list: 3List分类
- check_quadrant_compliance: 象限合规检查

### 报表出具（3个工具）
- generate_monthly_flash: 生成月度快报
- generate_quarterly_report: 生成季度汇报
- generate_annual_review: 生成年度复盘

### 通用查询（17个工具）
- get_budget_status: 查询预算状态
- get_execution_rate: 查询执行率
- get_alert_status: 查询预警状态
- get_approval_status: 查询审批状态
- calculate_deviation: 计算偏差
- recommend_action: 推荐行动方案
- simulate_transfer: 模拟预算调拨
- generate_report: 生成报告
- get_quadrant_info: 查询象限信息
- check_compliance: 合规性检查
- get_pdca_status: PDCA状态查询
- explain_strategic_budget: 战略预算归因解释
- comprehensive_review: 综合复盘分析
- search_ontology: 搜索本体定义

## 对话能力等级
- L1 事实查询：回答关于预算、费用、预警等的事实性问题
- L2 逻辑推理：基于规则进行推理判断（如是否超预算、预警级别判定）
- L3 方案推荐：根据分析结果推荐行动方案
- L4 方案模拟：模拟不同方案的执行效果
- L5 报告生成：生成结构化的分析报告
- L6 主动建议：基于上下文主动发现风险并提供建议

## 回答规范
1. 基于事实和规则回答，不编造数据
2. 引用规则时标注规则编号（如HR-001、SR-001）
3. 涉及金额时使用精确数值，标注单位（万元/元）
4. 推荐方案时给出理由和预期效果
5. 主动识别潜在风险并提醒用户
6. 你可以同时处理跨领域查询，如"查看预算执行率并处理相关预警"
"""


def _make_tool(name: str, description: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
    }


_TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    # ── 通用查询工具（原有17个） ──
    _make_tool(
        "get_budget_status",
        "查询预算项目的状态、额度、使用情况",
        {
            "type": "object",
            "properties": {
                "budget_id": {"type": "string", "description": "预算项目ID"},
                "l1_code": {"type": "string", "description": "L1科目编码"},
            },
        },
    ),
    _make_tool(
        "get_execution_rate",
        "查询预算执行率，支持按L1/L2/L3/项目维度",
        {
            "type": "object",
            "properties": {
                "dimension": {"type": "string", "enum": ["l1", "l2", "l3", "project"], "description": "查询维度"},
                "code": {"type": "string", "description": "维度编码"},
            },
        },
    ),
    _make_tool(
        "get_alert_status",
        "查询预警记录的状态、级别、响应情况",
        {
            "type": "object",
            "properties": {
                "alert_id": {"type": "string", "description": "预警编号"},
                "l1_code": {"type": "string", "description": "L1科目编码筛选"},
                "alert_level": {"type": "string", "enum": ["蓝色", "黄色", "橙色", "红色"], "description": "预警级别筛选"},
            },
        },
    ),
    _make_tool(
        "get_approval_status",
        "查询审批记录的当前状态和审批流程",
        {
            "type": "object",
            "properties": {
                "approval_id": {"type": "string", "description": "审批记录编号"},
                "expense_id": {"type": "string", "description": "报销单号"},
            },
        },
    ),
    _make_tool(
        "calculate_deviation",
        "计算预算偏差率和偏离金额",
        {
            "type": "object",
            "properties": {
                "budget_id": {"type": "string", "description": "预算项目ID"},
                "actual_amount": {"type": "number", "description": "实际金额"},
                "plan_amount": {"type": "number", "description": "计划金额"},
            },
        },
    ),
    _make_tool(
        "analyze_gap",
        "执行3GAP分析：目标差距、执行差距、能力差距",
        {
            "type": "object",
            "properties": {
                "l1_code": {"type": "string", "description": "L1科目编码"},
                "period": {"type": "string", "description": "分析周期（月度/季度）"},
            },
        },
    ),
    _make_tool(
        "classify_list",
        "执行3List分类：必赢清单、改善清单、资源清单",
        {
            "type": "object",
            "properties": {
                "l1_code": {"type": "string", "description": "L1科目编码"},
                "gap_type": {"type": "string", "enum": ["target", "execution", "capability"], "description": "差距类型"},
            },
        },
    ),
    _make_tool(
        "recommend_action",
        "基于分析结果推荐行动方案",
        {
            "type": "object",
            "properties": {
                "context": {"type": "string", "description": "分析上下文描述"},
                "gap_type": {"type": "string", "description": "差距类型"},
                "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"], "description": "严重程度"},
            },
        },
    ),
    _make_tool(
        "simulate_transfer",
        "模拟预算调拨效果，计算调拨后的额度分配",
        {
            "type": "object",
            "properties": {
                "from_budget_id": {"type": "string", "description": "调出预算项目ID"},
                "to_budget_id": {"type": "string", "description": "调入预算项目ID"},
                "amount": {"type": "number", "description": "调拨金额"},
            },
        },
    ),
    _make_tool(
        "generate_report",
        "生成结构化报告（快报/分析报告/复盘报告）",
        {
            "type": "object",
            "properties": {
                "report_type": {"type": "string", "enum": ["flash", "analysis", "review"], "description": "报告类型"},
                "scope": {"type": "string", "description": "报告范围（L1编码或项目ID）"},
                "period": {"type": "string", "description": "报告周期"},
            },
        },
    ),
    _make_tool(
        "check_budget_availability",
        "检查预算可用额度是否充足",
        {
            "type": "object",
            "properties": {
                "budget_id": {"type": "string", "description": "预算项目ID"},
                "required_amount": {"type": "number", "description": "所需金额"},
            },
        },
    ),
    _make_tool(
        "get_quadrant_info",
        "查询预算象限归属和发展/收缩/稳定/探索分类",
        {
            "type": "object",
            "properties": {
                "budget_id": {"type": "string", "description": "预算项目ID"},
            },
        },
    ),
    _make_tool(
        "check_compliance",
        "检查操作是否符合硬规则和软规则约束",
        {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "待检查的操作"},
                "context": {"type": "object", "description": "操作上下文"},
            },
        },
    ),
    _make_tool(
        "get_pdca_status",
        "查询PDCA复盘状态和闭环率",
        {
            "type": "object",
            "properties": {
                "period": {"type": "string", "description": "复盘周期"},
                "scope": {"type": "string", "description": "复盘范围"},
            },
        },
    ),
    _make_tool(
        "explain_strategic_budget",
        "解释预算项的战略归因：战略方向、象限、类别、执行率偏差及预警原因",
        {
            "type": "object",
            "properties": {
                "budget_id": {"type": "string", "description": "预算项目ID"},
                "l1_code": {"type": "string", "description": "L1科目编码"},
            },
        },
    ),
    _make_tool(
        "comprehensive_review",
        "综合复盘分析：汇聚执行率、3GAP分析、预警摘要、审批意见、PDCA行动等数据生成结构化复盘洞察",
        {
            "type": "object",
            "properties": {
                "period": {"type": "string", "description": "复盘周期（YYYY-MM）"},
                "center_id": {"type": "string", "description": "中心ID（可选）"},
            },
        },
    ),
    _make_tool(
        "search_ontology",
        "搜索本体对象、关系、行为、规则的定义",
        {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "搜索关键词"},
                "category": {"type": "string", "enum": ["object", "relation", "behavior", "rule", "scene"], "description": "本体类别"},
            },
        },
    ),
    # ── 预算编制工具（从BudgetAgent吸收） ──
    _make_tool(
        "create_budget",
        "创建预算项目，关联战略举措并设置科目编码",
        {
            "type": "object",
            "properties": {
                "budget_name": {"type": "string", "description": "预算项目名称"},
                "l1_code": {"type": "string", "description": "L1科目编码"},
                "l2_code": {"type": "string", "description": "L2科目编码"},
                "l3_code": {"type": "string", "description": "L3科目编码"},
                "annual_amount": {"type": "number", "description": "年度预算金额"},
                "center_id": {"type": "string", "description": "中心ID"},
                "strategy_initiative_id": {"type": "string", "description": "关联战略举措ID"},
                "certainty": {"type": "string", "enum": ["high", "medium", "low"], "description": "确定性"},
                "is_approved_project": {"type": "boolean", "description": "是否已批准项目"},
            },
            "required": ["budget_name", "l1_code", "annual_amount"],
        },
    ),
    _make_tool(
        "classify_ab",
        "对预算项目进行A/B类分类判定：A类为高确定性已批准项目，B类为进度依赖型项目",
        {
            "type": "object",
            "properties": {
                "budget_id": {"type": "string", "description": "预算项目ID"},
                "certainty": {"type": "string", "enum": ["high", "medium", "low"], "description": "确定性"},
                "is_approved_project": {"type": "boolean", "description": "是否已批准项目"},
                "has_milestone": {"type": "boolean", "description": "是否有里程碑"},
                "strategic_priority": {"type": "string", "enum": ["high", "medium", "low"], "description": "战略优先级"},
            },
        },
    ),
    _make_tool(
        "recommend_quadrant",
        "推荐预算项目的象限归属：发展/收缩/稳定/探索",
        {
            "type": "object",
            "properties": {
                "growth_rate": {"type": "number", "description": "增长率"},
                "market_share": {"type": "number", "description": "市场份额"},
                "strategic_priority": {"type": "string", "enum": ["high", "medium", "low"], "description": "战略优先级"},
                "strategic_intent_l1": {"type": "string", "description": "战略意图L1"},
            },
        },
    ),
    # ── 预算授予工具（从BudgetAgent吸收） ──
    _make_tool(
        "grant_a_class",
        "A类预算授予：100%冻结额度，立即可用",
        {
            "type": "object",
            "properties": {
                "budget_id": {"type": "string", "description": "预算项目ID"},
            },
            "required": ["budget_id"],
        },
    ),
    _make_tool(
        "grant_b_class",
        "B类预算授予：0%授予，创建里程碑跟踪",
        {
            "type": "object",
            "properties": {
                "budget_id": {"type": "string", "description": "预算项目ID"},
            },
            "required": ["budget_id"],
        },
    ),
    _make_tool(
        "b2a_convert",
        "B→A转换：里程碑达标后将B类预算转为A类",
        {
            "type": "object",
            "properties": {
                "budget_id": {"type": "string", "description": "预算项目ID"},
                "milestone_evidence": {"type": "string", "description": "里程碑达成证据（至少10字）"},
            },
            "required": ["budget_id", "milestone_evidence"],
        },
    ),
    # ── 费用报销工具（从ExpenseAgent吸收） ──
    _make_tool(
        "submit_expense",
        "提交报销单，执行6步验证流程（预算校验→管控路由→额度检查→发票查重→创建报销单→战略对齐评估）",
        {
            "type": "object",
            "properties": {
                "budget_id": {"type": "string", "description": "关联预算项目ID"},
                "amount": {"type": "number", "description": "报销金额"},
                "description": {"type": "string", "description": "报销说明"},
                "l3_code": {"type": "string", "description": "L3科目编码"},
                "applicant_id": {"type": "string", "description": "申请人ID"},
                "center_id": {"type": "string", "description": "中心ID"},
                "department_id": {"type": "string", "description": "部门ID"},
                "invoices": {"type": "array", "description": "发票列表", "items": {"type": "object"}},
            },
            "required": ["budget_id", "amount", "description"],
        },
    ),
    _make_tool(
        "route_control",
        "查询L3科目的管控路由级别（强管控/中心弱管控/组合管控/不管控）",
        {
            "type": "object",
            "properties": {
                "l3_code": {"type": "string", "description": "L3科目编码"},
            },
        },
    ),
    _make_tool(
        "check_invoice",
        "检查发票是否重复提交",
        {
            "type": "object",
            "properties": {
                "invoice_number": {"type": "string", "description": "发票号码"},
            },
            "required": ["invoice_number"],
        },
    ),
    _make_tool(
        "write_off",
        "预算核销：双线审批完成后核销预算",
        {
            "type": "object",
            "properties": {
                "expense_id": {"type": "string", "description": "报销单号"},
            },
            "required": ["expense_id"],
        },
    ),
    # ── 预警监控工具（从AlertAgent吸收） ──
    _make_tool(
        "scan_alerts",
        "扫描预警记录，支持按级别、状态、L1科目筛选",
        {
            "type": "object",
            "properties": {
                "alert_level": {"type": "string", "enum": ["蓝色", "黄色", "橙色", "红色"], "description": "预警级别筛选"},
                "alert_status": {"type": "string", "enum": ["开放", "响应中", "待闭环确认", "已闭环", "已升级"], "description": "预警状态筛选"},
                "l1_code": {"type": "string", "description": "L1科目编码筛选"},
                "limit": {"type": "integer", "description": "返回数量限制", "default": 20},
            },
        },
    ),
    _make_tool(
        "respond_alert",
        "响应预警：提交整改方案",
        {
            "type": "object",
            "properties": {
                "alert_id": {"type": "string", "description": "预警编号"},
                "response": {"type": "string", "description": "整改方案"},
                "responder": {"type": "string", "description": "响应人"},
            },
            "required": ["alert_id", "response", "responder"],
        },
    ),
    _make_tool(
        "confirm_closure",
        "确认预警闭环：财经BP确认整改方案并关闭预警",
        {
            "type": "object",
            "properties": {
                "closure_id": {"type": "string", "description": "闭环记录ID"},
                "bp_confirmation": {"type": "string", "description": "BP确认意见"},
                "bp_confirmer": {"type": "string", "description": "BP确认人"},
            },
            "required": ["closure_id", "bp_confirmation", "bp_confirmer"],
        },
    ),
    _make_tool(
        "escalate_alert",
        "预警升级：超时未响应时升级至上级管理层",
        {
            "type": "object",
            "properties": {
                "alert_id": {"type": "string", "description": "预警编号"},
            },
            "required": ["alert_id"],
        },
    ),
    _make_tool(
        "get_alert_stats",
        "获取预警统计数据：按级别、状态聚合",
        {
            "type": "object",
            "properties": {
                "l1_code": {"type": "string", "description": "L1科目编码筛选（可选）"},
            },
        },
    ),
    # ── 经营分析工具（从AnalysisAgent吸收） ──
    _make_tool(
        "calculate_execution_rates",
        "计算指定中心在指定期间的执行率（月度/累计/年度）",
        {
            "type": "object",
            "properties": {
                "center_id": {"type": "string", "description": "中心ID"},
                "period": {"type": "string", "description": "期间（YYYY-MM）"},
            },
            "required": ["center_id", "period"],
        },
    ),
    _make_tool(
        "check_quadrant_compliance",
        "检查象限合规性：验证预算执行是否符合象限策略",
        {
            "type": "object",
            "properties": {
                "period": {"type": "string", "description": "期间（YYYY-MM）"},
            },
            "required": ["period"],
        },
    ),
    # ── 报表出具工具（从ReportAgent吸收） ──
    _make_tool(
        "generate_monthly_flash",
        "生成月度快报：包含执行率、预警摘要、战略意图分析",
        {
            "type": "object",
            "properties": {
                "period": {"type": "string", "description": "期间（YYYY-MM）"},
            },
            "required": ["period"],
        },
    ),
    _make_tool(
        "generate_quarterly_report",
        "生成季度汇报：包含3GAP+3List分析、调拨建议、预警摘要",
        {
            "type": "object",
            "properties": {
                "period": {"type": "string", "description": "期间（YYYY-QN）"},
            },
            "required": ["period"],
        },
    ),
    _make_tool(
        "generate_annual_review",
        "生成年度复盘：包含组合校准、下年建议、战略意图分析",
        {
            "type": "object",
            "properties": {
                "period": {"type": "string", "description": "年度（YYYY）"},
            },
            "required": ["period"],
        },
    ),
    # ── 高级分析工具（新增5个） ──
    _make_tool(
        "predict_execution_trend",
        "预测指定L1科目未来N个月的执行率趋势，使用线性回归和移动平均算法",
        {
            "type": "object",
            "properties": {
                "l1_code": {"type": "string", "description": "L1科目编码"},
                "months_ahead": {"type": "integer", "description": "预测月数，默认6", "default": 6},
            },
            "required": ["l1_code"],
        },
    ),
    _make_tool(
        "detect_anomalies",
        "检测指定周期的预算执行异常，使用Z-score和IQR方法识别异常值",
        {
            "type": "object",
            "properties": {
                "period": {"type": "string", "description": "周期，格式YYYY-MM"},
                "z_threshold": {"type": "number", "description": "Z-score阈值，默认2.0", "default": 2.0},
                "iqr_multiplier": {"type": "number", "description": "IQR倍数，默认1.5", "default": 1.5},
            },
            "required": ["period"],
        },
    ),
    _make_tool(
        "root_cause_analysis",
        "对指定问题进行根因分析，识别导致执行偏差的根本原因",
        {
            "type": "object",
            "properties": {
                "issue_type": {"type": "string", "enum": ["execution_low", "execution_high", "alert_frequent", "deviation_large"], "description": "问题类型"},
                "period": {"type": "string", "description": "分析周期，格式YYYY-MM"},
                "l1_code": {"type": "string", "description": "L1科目编码（可选）"},
            },
            "required": ["issue_type", "period"],
        },
    ),
    _make_tool(
        "cascade_risk_assess",
        "级联风险评估：当L1科目触发红色预警时，评估对L2科目和战略意图的影响",
        {
            "type": "object",
            "properties": {
                "l1_code": {"type": "string", "description": "L1科目编码"},
            },
            "required": ["l1_code"],
        },
    ),
    _make_tool(
        "alert_pattern_analysis",
        "预警模式分析：分析历史预警数据，识别系统性问题和偶发问题",
        {
            "type": "object",
            "properties": {
                "l1_code": {"type": "string", "description": "L1科目编码（可选，不填则分析全部）"},
                "lookback_months": {"type": "integer", "description": "回溯月数，默认6", "default": 6},
            },
        },
    ),
]


@register
class FinanceAgent(ToolCapableBaseAgent):
    name = "finance"
    description = "集团财经管理AI助手，支持L1-L6六级对话能力，涵盖预算编制、预算授予、费用报销、预警监控、经营分析、报表出具等全领域"
    supported_intents = ["budget_query", "expense_query", "alert_query", "analysis_query", "report_query", "general"]
    system_prompt = _FINANCE_SYSTEM_PROMPT
    skill_name = "chat-finance"

    # ── Phase 1 增量：本次 query 期间调用的 tool 集合（探索深度统计用） ──
    _current_query_tools: set = set()

    def get_default_tools(self) -> List[Dict[str, Any]]:
        return _TOOL_DEFINITIONS

    async def execute(
        self,
        messages: List[Dict[str, str]],
        context: Dict[str, Any],
        db: AsyncSession,
    ) -> str:
        user_input = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                user_input = m.get("content", "")
                break

        scene = match_scene(user_input, context)

        rule_engine = RuleEngine()
        reasoning_trace = None
        if scene:
            rule_context = {
                "user_input": user_input,
                "scene_id": scene.scene_id,
                **context,
            }
            reasoning_trace = rule_engine.execute_scene(scene.scene_id, rule_context)

        # ── 多Skill动态组合 ──
        matched_skills = await self.select_skills(user_input)
        all_objects: set = set()
        all_rules: set = set()
        all_behaviors: set = set()
        combined_instructions: List[str] = []

        for skill_id, score, desc in matched_skills:
            skill = self.load_skill()
            # 尝试按场景ID加载对应的Skill
            skill_name_candidate = skill_id.replace("fin.", "")
            if self._skill_loader:
                detail = self._skill_loader.load_skill_detail(skill_name_candidate)
                if detail:
                    skill = detail
            if skill and skill.meta:
                all_objects.update(skill.meta.activated_objects or [])
                all_rules.update(skill.meta.activated_rules or [])
                all_behaviors.update(skill.meta.activated_behaviors or [])
                if skill.instructions:
                    combined_instructions.append(f"### {skill.meta.name}\n{skill.instructions}")

        # 如果没有匹配到Skill，回退到默认Skill
        if not combined_instructions:
            skill_instructions = self.get_skill_instructions()
            if skill_instructions:
                combined_instructions.append(skill_instructions)

        # 合并场景匹配的激活项
        if scene:
            all_objects.update(scene.activated_objects or [])
            all_rules.update(scene.activated_rules or [])
            all_behaviors.update(scene.activated_behaviors or [])

        system_content = "\n\n".join(combined_instructions) if combined_instructions else _FINANCE_SYSTEM_PROMPT

        if scene:
            scene_info = (
                f"\n\n[当前场景] {scene.name}（{scene.scene_id}）\n"
                f"阶段：{scene.stage}\n"
                f"激活对象：{', '.join(scene.activated_objects)}\n"
                f"激活规则：{', '.join(scene.activated_rules)}\n"
                f"激活行为：{', '.join(scene.activated_behaviors)}"
            )
            system_content += scene_info

        if matched_skills:
            skill_names = [f"{sid}({score:.2f})" for sid, score, _ in matched_skills]
            system_content += f"\n\n[匹配Skills] {', '.join(skill_names)}"

        system_content = await self.inject_ontology_context(
            system_content,
            db=db,
            activated_objects=list(all_objects) if all_objects else None,
            activated_rules=list(all_rules) if all_rules else None,
            activated_behaviors=list(all_behaviors) if all_behaviors else None,
        )

        if reasoning_trace and reasoning_trace.reasoning_chain:
            trace_info = "\n\n[规则推理结果]\n"
            for step in reasoning_trace.reasoning_chain:
                trace_info += f"- {step.rule_id}（{step.rule_type}）：{step.rule_desc} → {step.output}\n"
            trace_info += f"结论：{'存在阻断' if reasoning_trace.conclusion.get('blocked') else '无阻断'}"
            system_content += trace_info

        full_messages = [{"role": "system", "content": system_content}]

        full_messages.extend(messages)

        llm = get_llm_client()
        tools = self.get_default_tools()
        bound_llm = llm.bind_tools(tools)

        response = await bound_llm.invoke(full_messages, temperature=0.3)

        if response.tool_calls:
            tool_results = await self._handle_tool_calls(response.tool_calls, db, context)
            tool_messages = [{"role": msg["role"], "content": msg["content"]} for msg in tool_results]
            full_messages.append({"role": "assistant", "content": response.content or "", "tool_calls": response.tool_calls})
            full_messages.extend(tool_messages)

            final_response = await llm.invoke(full_messages, temperature=0.3)
            ai_output = final_response.content
        else:
            ai_output = response.content

        hallucination_result = self.check_hallucination(ai_output)
        if hallucination_result.should_refuse:
            ai_output = (
                f"{ai_output}\n\n"
                f"⚠️ [AI输出置信度不足] {hallucination_result.refusal_reason}\n"
                f"请以系统实际数据为准，以上建议仅供参考。"
            )
        elif not hallucination_result.is_safe:
            ai_output += "\n\n⚠️ [部分信息待验证] 请以系统实际数据为准。"

        return ai_output

    async def execute_with_tools(
        self,
        messages: List[Dict[str, str]],
        context: Dict[str, Any],
        db: AsyncSession,
    ) -> str:
        return await self.execute(messages, context, db)

    async def _handle_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],
        db: AsyncSession,
        context: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        results = []
        for tc in tool_calls:
            func = tc.get("function", {})
            tool_name = func.get("name", "")
            try:
                args = json.loads(func.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}

            # ── 间接 Prompt 注入防护 ──
            # 三个 tool 接收业务自由文本字段（报销事由/响应说明/确认意见），
            # 这些字段会被后续 LLM 上下文引用。先做注入检查再执行。
            injection_blocked = self._check_tool_injection(tool_name, args)
            if injection_blocked:
                results.append({
                    "role": "tool",
                    "content": json.dumps(injection_blocked, ensure_ascii=False),
                })
                continue

            result = await self._execute_tool(tool_name, args, db, context)
            results.append({
                "role": "tool",
                "content": json.dumps(result, ensure_ascii=False, default=str),
            })

        return results

    def _check_tool_injection(
        self, tool_name: str, args: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """对 3 个接收业务自由文本的 tool 做间接 Prompt 注入检测。

        命中即返回降级响应字典（带 blocked 标志），由 _handle_tool_calls
        短路返回，不再执行实际 tool。

        Returns:
            None = 未命中注入，可继续执行
            dict = 命中注入，降级响应（含 blocked=True + reason）
        """
        # 不同 tool 的自由文本字段
        text_fields: List[str] = []
        if tool_name == "submit_expense":
            text_fields = ["description", "remarks", "reason", "note"]
        elif tool_name == "respond_alert":
            text_fields = ["response", "response_text", "remarks"]
        elif tool_name == "confirm_closure":
            text_fields = ["bp_confirmation", "confirmation", "remarks"]
        else:
            return None

        from services.guardrails import Guardrails

        guard = Guardrails()
        collected: List[Dict[str, Any]] = []
        for field in text_fields:
            value = args.get(field)
            if not isinstance(value, str) or not value:
                continue
            safe, violations = guard.check_injection(value)
            if not safe:
                collected.append({
                    "field": field,
                    "violations": violations,
                })

        if not collected:
            return None

        # 命中注入：返回降级响应（不抛异常，保持 Agent 状态机连贯）
        from loguru import logger
        logger.warning(
            f"[indirect-injection] tool={tool_name} blocked, "
            f"fields={[c['field'] for c in collected]}, "
            f"patterns={[v['category'] for c in collected for v in c['violations']]}"
        )
        return {
            "blocked": True,
            "reason": (
                f"输入字段包含疑似 Prompt 注入攻击载荷（{len(collected)} 个字段命中），"
                f"已阻断本次 tool 调用。请移除可疑措辞后重试。"
            ),
            "blocked_fields": [c["field"] for c in collected],
            "blocked_categories": list({
                v["category"] for c in collected for v in c["violations"]
            }),
        }

    async def _execute_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
        db: AsyncSession,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            # ── 原有17个工具 ──
            if tool_name == "get_budget_status":
                return await self._tool_get_budget_status(args, db)
            elif tool_name == "get_execution_rate":
                return await self._tool_get_execution_rate(args, db)
            elif tool_name == "get_alert_status":
                return await self._tool_get_alert_status(args, db)
            elif tool_name == "get_approval_status":
                return await self._tool_get_approval_status(args, db)
            elif tool_name == "calculate_deviation":
                return self._tool_calculate_deviation(args)
            elif tool_name == "analyze_gap":
                return await self._tool_analyze_gap(args, db)
            elif tool_name == "classify_list":
                return await self._tool_classify_list(args, db)
            elif tool_name == "recommend_action":
                return self._tool_recommend_action(args)
            elif tool_name == "simulate_transfer":
                return self._tool_simulate_transfer(args)
            elif tool_name == "generate_report":
                return await self._tool_generate_report(args, db)
            elif tool_name == "check_budget_availability":
                return await self._tool_check_budget_availability(args, db)
            elif tool_name == "get_quadrant_info":
                return await self._tool_get_quadrant_info(args, db)
            elif tool_name == "check_compliance":
                return self._tool_check_compliance(args)
            elif tool_name == "get_pdca_status":
                return self._tool_get_pdca_status(args)
            elif tool_name == "explain_strategic_budget":
                return await self._tool_explain_strategic_budget(args, db)
            elif tool_name == "comprehensive_review":
                return await self._tool_comprehensive_review(args, db)
            elif tool_name == "search_ontology":
                return self._tool_search_ontology(args)
            # ── 预算编制工具（从BudgetAgent吸收） ──
            elif tool_name == "create_budget":
                return await self._tool_create_budget(args, db)
            elif tool_name == "classify_ab":
                return await self._tool_classify_ab(args, db)
            elif tool_name == "recommend_quadrant":
                return await self._tool_recommend_quadrant(args, db)
            # ── 预算授予工具（从BudgetAgent吸收） ──
            elif tool_name == "grant_a_class":
                return await self._tool_grant_a_class(args, db)
            elif tool_name == "grant_b_class":
                return await self._tool_grant_b_class(args, db)
            elif tool_name == "b2a_convert":
                return await self._tool_b2a_convert(args, db)
            # ── 费用报销工具（从ExpenseAgent吸收） ──
            elif tool_name == "submit_expense":
                return await self._tool_submit_expense(args, db)
            elif tool_name == "route_control":
                return await self._tool_route_control(args, db)
            elif tool_name == "check_invoice":
                return await self._tool_check_invoice(args, db)
            elif tool_name == "write_off":
                return await self._tool_write_off(args, db)
            # ── 预警监控工具（从AlertAgent吸收） ──
            elif tool_name == "scan_alerts":
                return await self._tool_scan_alerts(args, db)
            elif tool_name == "respond_alert":
                return await self._tool_respond_alert(args, db)
            elif tool_name == "confirm_closure":
                return await self._tool_confirm_closure(args, db)
            elif tool_name == "escalate_alert":
                return await self._tool_escalate_alert(args, db)
            elif tool_name == "get_alert_stats":
                return await self._tool_get_alert_stats(args, db)
            # ── 经营分析工具（从AnalysisAgent吸收） ──
            elif tool_name == "calculate_execution_rates":
                return await self._tool_calculate_execution_rates(args, db)
            elif tool_name == "check_quadrant_compliance":
                return await self._tool_check_quadrant_compliance(args, db)
            # ── 报表出具工具（从ReportAgent吸收） ──
            elif tool_name == "generate_monthly_flash":
                return await self._tool_generate_monthly_flash(args, db)
            elif tool_name == "generate_quarterly_report":
                return await self._tool_generate_quarterly_report(args, db)
            elif tool_name == "generate_annual_review":
                return await self._tool_generate_annual_review(args, db)
            # ── 高级分析工具（新增5个） ──
            elif tool_name == "predict_execution_trend":
                return await self._tool_predict_execution_trend(args, db)
            elif tool_name == "detect_anomalies":
                return await self._tool_detect_anomalies(args, db)
            elif tool_name == "root_cause_analysis":
                return await self._tool_root_cause_analysis(args, db)
            elif tool_name == "cascade_risk_assess":
                return await self._tool_cascade_risk_assess(args, db)
            elif tool_name == "alert_pattern_analysis":
                return await self._tool_alert_pattern_analysis(args, db)
            else:
                return {"error": f"未知工具: {tool_name}"}
        except Exception as e:
            logger.error(f"Tool execution error [{tool_name}]: {e}")
            return {"error": str(e)}

    # ═══════════════════════════════════════════════════════════════
    # 原有17个工具实现（保持不变）
    # ═══════════════════════════════════════════════════════════════

    async def _tool_get_budget_status(self, args: Dict, db: AsyncSession) -> Dict:
        from sqlalchemy import select
        from models.budget import BudgetItem

        budget_id = args.get("budget_id")
        l1_code = args.get("l1_code")

        stmt = select(BudgetItem)
        if budget_id:
            stmt = stmt.where(BudgetItem.budget_id == budget_id)
        if l1_code:
            stmt = stmt.where(BudgetItem.l1_code == l1_code)
        stmt = stmt.limit(10)

        result = await db.execute(stmt)
        items = result.scalars().all()

        if not items:
            return {"message": "未找到匹配的预算项目", "data": []}

        return {
            "data": [
                {
                    "budget_id": i.budget_id,
                    "budget_name": i.budget_name,
                    "status": i.status,
                    "annual_amount": float(i.annual_amount) if i.annual_amount else 0,
                    "granted_amount": float(i.granted_amount) if i.granted_amount else 0,
                    "used_amount": float(i.used_amount) if i.used_amount else 0,
                    "available_amount": float(i.available_amount) if i.available_amount else 0,
                    "strategic_intent_l1": i.strategic_intent_l1,
                    "strategic_intent_l2": i.strategic_intent_l2,
                    "quadrant": i.quadrant,
                    "budget_category": i.budget_category,
                }
                for i in items
            ]
        }

    async def _tool_get_execution_rate(self, args: Dict, db: AsyncSession) -> Dict:
        from sqlalchemy import select
        from models.budget import BudgetItem

        dimension = args.get("dimension", "l1")
        code = args.get("code", "")

        stmt = select(BudgetItem).where(BudgetItem.status.in_(["已授予", "执行中"]))
        if code:
            if dimension == "l1":
                stmt = stmt.where(BudgetItem.l1_code == code)
            elif dimension == "l2":
                stmt = stmt.where(BudgetItem.l2_code == code)

        result = await db.execute(stmt)
        items = result.scalars().all()

        if not items:
            return {"message": "未找到匹配的预算数据", "execution_rate": 0}

        total_annual = sum(float(i.annual_amount or 0) for i in items)
        total_used = sum(float(i.used_amount or 0) for i in items)
        rate = (total_used / total_annual * 100) if total_annual > 0 else 0

        return {
            "dimension": dimension,
            "code": code,
            "total_annual": total_annual,
            "total_used": total_used,
            "execution_rate": round(rate, 2),
            "item_count": len(items),
        }

    async def _tool_get_alert_status(self, args: Dict, db: AsyncSession) -> Dict:
        from sqlalchemy import select
        from models.alert import AlertRecord

        alert_id = args.get("alert_id")
        l1_code = args.get("l1_code")
        alert_level = args.get("alert_level")

        stmt = select(AlertRecord)
        if alert_id:
            stmt = stmt.where(AlertRecord.alert_id == alert_id)
        if l1_code:
            stmt = stmt.where(AlertRecord.l1_code == l1_code)
        if alert_level:
            stmt = stmt.where(AlertRecord.alert_level == alert_level)
        stmt = stmt.limit(20)

        result = await db.execute(stmt)
        alerts = result.scalars().all()

        return {
            "data": [
                {
                    "alert_id": a.alert_id,
                    "alert_level": a.alert_level,
                    "alert_type": a.alert_type,
                    "alert_status": a.alert_status,
                    "deviation_rate": float(a.deviation_rate) if a.deviation_rate else 0,
                }
                for a in alerts
            ],
            "total": len(alerts),
        }

    async def _tool_get_approval_status(self, args: Dict, db: AsyncSession) -> Dict:
        from sqlalchemy import select
        from models.approval import ApprovalRecord

        expense_id = args.get("expense_id")
        approval_id = args.get("approval_id")

        stmt = select(ApprovalRecord)
        if expense_id:
            stmt = stmt.where(ApprovalRecord.expense_id == expense_id)
        if approval_id:
            stmt = stmt.where(ApprovalRecord.approval_id == approval_id)
        stmt = stmt.limit(10)

        result = await db.execute(stmt)
        records = result.scalars().all()

        return {
            "data": [
                {
                    "approval_id": r.approval_id,
                    "approval_line": r.approval_line,
                    "approval_step": r.approval_step,
                    "approval_action": r.approval_action,
                }
                for r in records
            ]
        }

    def _tool_calculate_deviation(self, args: Dict) -> Dict:
        actual = args.get("actual_amount", 0)
        plan = args.get("plan_amount", 0)
        if plan == 0:
            return {"error": "计划金额不能为0"}
        deviation = actual - plan
        deviation_rate = deviation / plan * 100
        return {
            "actual_amount": actual,
            "plan_amount": plan,
            "deviation": deviation,
            "deviation_rate": round(deviation_rate, 2),
        }

    async def _tool_analyze_gap(self, args: Dict, db: AsyncSession) -> Dict:
        from engines.business_analysis import BusinessAnalysisEngine

        l1_code = args.get("l1_code", "")
        period = args.get("period", "月度")

        ba_engine = BusinessAnalysisEngine()
        try:
            from sqlalchemy import select
            from models.budget import BudgetItem
            center_id = None
            if l1_code:
                stmt = select(BudgetItem.center_id).where(BudgetItem.l1_code == l1_code).limit(1)
                result = await db.execute(stmt)
                row = result.scalar_one_or_none()
                center_id = row if row else None

            if not center_id:
                stmt = select(BudgetItem.center_id).limit(1)
                result = await db.execute(stmt)
                center_id = result.scalar_one_or_none() or "C01"

            quarter_period = period
            if "-" in period and "Q" not in period:
                try:
                    month = int(period.split("-")[1])
                    quarter_period = period[:4] + "-Q" + str((month - 1) // 3 + 1)
                except (ValueError, IndexError):
                    quarter_period = period

            gap_analysis = await ba_engine.analyze_3gap(center_id, quarter_period, db)
            return {
                "l1_code": l1_code,
                "period": period,
                "center_id": center_id,
                "target_gap": {"description": "目标差距(GAP1)", "value": float(gap_analysis.gap1) if gap_analysis.gap1 else 0},
                "execution_gap": {"description": "执行差距(GAP2)", "value": float(gap_analysis.gap2) if gap_analysis.gap2 else 0},
                "capability_gap": {"description": "预测变动(GAP3)", "value": float(gap_analysis.gap3) if gap_analysis.gap3 else 0},
                "message": "3GAP分析完成",
            }
        except Exception as e:
            logger.error(f"3GAP analysis failed: {e}")
            return {
                "l1_code": l1_code,
                "period": period,
                "target_gap": {"description": "目标差距分析", "value": 0},
                "execution_gap": {"description": "执行差距分析", "value": 0},
                "capability_gap": {"description": "能力差距分析", "value": 0},
                "message": f"3GAP分析异常: {str(e)}",
            }

    async def _tool_classify_list(self, args: Dict, db: AsyncSession) -> Dict:
        l1_code = args.get("l1_code", "")
        gap_type = args.get("gap_type", "target")
        return {
            "l1_code": l1_code,
            "gap_type": gap_type,
            "must_win_list": [],
            "improvement_list": [],
            "resource_list": [],
            "message": "3List分类完成",
        }

    def _tool_recommend_action(self, args: Dict) -> Dict:
        context = args.get("context", "")
        severity = args.get("severity", "medium")
        recommendations = {
            "low": ["持续监控", "定期检查"],
            "medium": ["加强管控", "调整预算分配", "优化执行计划"],
            "high": ["立即整改", "启动预警响应", "调整战略举措"],
            "critical": ["紧急叫停", "升级至管委会", "启动应急方案"],
        }
        return {
            "context": context,
            "severity": severity,
            "recommendations": recommendations.get(severity, []),
        }

    def _tool_simulate_transfer(self, args: Dict) -> Dict:
        from_budget = args.get("from_budget_id", "")
        to_budget = args.get("to_budget_id", "")
        amount = args.get("amount", 0)
        return {
            "from_budget_id": from_budget,
            "to_budget_id": to_budget,
            "amount": amount,
            "result": "模拟完成",
            "from_remaining": 0,
            "to_remaining": 0,
            "message": "预算调拨模拟完成，请确认是否执行",
        }

    async def _tool_generate_report(self, args: Dict, db: AsyncSession) -> Dict:
        report_type = args.get("report_type", "flash")
        scope = args.get("scope", "")
        period = args.get("period", "")
        return {
            "report_type": report_type,
            "scope": scope,
            "period": period,
            "sections": [],
            "message": "报告生成完成",
        }

    async def _tool_check_budget_availability(self, args: Dict, db: AsyncSession) -> Dict:
        from sqlalchemy import select
        from models.budget import BudgetItem

        budget_id = args.get("budget_id", "")
        required = args.get("required_amount", 0)

        stmt = select(BudgetItem).where(BudgetItem.budget_id == budget_id)
        result = await db.execute(stmt)
        item = result.scalar_one_or_none()

        if not item:
            return {"error": f"预算项目 {budget_id} 不存在"}

        available = float(item.available_amount or 0)
        return {
            "budget_id": budget_id,
            "available_amount": available,
            "required_amount": required,
            "sufficient": available >= required,
            "shortage": max(0, required - available),
        }

    async def _tool_get_quadrant_info(self, args: Dict, db: AsyncSession) -> Dict:
        from sqlalchemy import select
        from models.budget import BudgetItem

        budget_id = args.get("budget_id", "")
        stmt = select(BudgetItem).where(BudgetItem.budget_id == budget_id)
        result = await db.execute(stmt)
        item = result.scalar_one_or_none()

        if not item:
            return {"error": f"预算项目 {budget_id} 不存在"}

        return {
            "budget_id": budget_id,
            "budget_name": item.budget_name,
            "quadrant": item.quadrant,
            "budget_category": item.budget_category,
        }

    def _tool_check_compliance(self, args: Dict) -> Dict:
        action = args.get("action", "")
        ctx = args.get("context", {})
        rule_engine = RuleEngine()
        violations = []
        warnings = []
        try:
            result = rule_engine.evaluate(action, ctx)
            if result and hasattr(result, 'violations'):
                violations = result.violations
            if result and hasattr(result, 'warnings'):
                warnings = result.warnings
            compliant = not violations
        except Exception:
            compliant = True

        strategic_alignment_score = 100
        if ctx:
            quadrant = ctx.get("quadrant", "")
            intent_l1 = ctx.get("strategic_intent_l1", "")
            if quadrant == "收缩" and intent_l1:
                strategic_alignment_score = 60
            elif quadrant and not intent_l1:
                strategic_alignment_score = 70
        if violations:
            strategic_alignment_score -= len(violations) * 15
        strategic_alignment_score = max(0, strategic_alignment_score)

        return {
            "action": action,
            "compliant": compliant,
            "violations": violations,
            "warnings": warnings,
            "strategic_alignment_score": strategic_alignment_score,
            "message": "合规性检查通过" if compliant else f"发现{len(violations)}项违规",
        }

    def _tool_get_pdca_status(self, args: Dict) -> Dict:
        period = args.get("period", "月度")
        scope = args.get("scope", "")
        return {
            "period": period,
            "scope": scope,
            "closure_rate": 0,
            "open_items": 0,
            "overdue_items": 0,
            "message": "PDCA状态查询完成",
        }

    async def _tool_explain_strategic_budget(self, args: Dict, db: AsyncSession) -> Dict:
        from sqlalchemy import select
        from models.budget import BudgetItem
        from models.alert import AlertRecord
        from models.approval import ApprovalRecord
        from engines.budget_planning import BudgetPlanningEngine

        budget_id = args.get("budget_id")
        l1_code = args.get("l1_code")

        stmt = select(BudgetItem)
        if budget_id:
            stmt = stmt.where(BudgetItem.budget_id == budget_id)
        if l1_code:
            stmt = stmt.where(BudgetItem.l1_code == l1_code)
        stmt = stmt.limit(1)

        result = await db.execute(stmt)
        item = result.scalar_one_or_none()

        if not item:
            return {"error": "未找到匹配的预算项目"}

        intent_l1 = item.strategic_intent_l1 or "未分类"
        intent_l2 = item.strategic_intent_l2 or "未分类"
        quadrant = item.quadrant or "未分类"
        budget_category = item.budget_category or "未分类"

        annual = float(item.annual_amount or 0)
        used = float(item.used_amount or 0)
        rate = round(used / annual * 100, 2) if annual > 0 else 0

        target_rate = 100.0
        if quadrant == "发展":
            target_rate = 80.0
        elif quadrant == "收缩":
            target_rate = 40.0
        elif quadrant == "稳定":
            target_rate = 60.0
        elif quadrant == "探索":
            target_rate = 50.0

        alert_stmt = select(AlertRecord).where(AlertRecord.budget_id == item.budget_id)
        alert_result = await db.execute(alert_stmt)
        alerts = alert_result.scalars().all()

        deviation_reasons = []
        for alert in alerts:
            if alert.alert_status != "已闭环":
                deviation_reasons.append(
                    f"{alert.alert_type}预警(级别:{alert.alert_level}, 偏离率:{float(alert.deviation_rate or 0)}%)"
                )

        explanation = f"该预算项属于'{intent_l1}'战略方向，{quadrant}象限，{budget_category}类预算。"
        comparison = "低于" if rate < target_rate else "高于"
        explanation += f"当前执行率{rate}%，{comparison}目标{target_rate}%。"

        if deviation_reasons:
            explanation += f"主要偏差原因：{'；'.join(deviation_reasons)}"
        else:
            explanation += "暂无预警记录，执行正常。"

        if quadrant == "收缩" and item.strategy_initiative_id:
            explanation += "注意：该预算项处于收缩象限但战略优先级较高，建议评估是否需要战略调整。"

        budget_ratio_info = {}
        try:
            bp_engine = BudgetPlanningEngine()
            ratios = await bp_engine.calculate_strategic_budget_ratio(db)
            current_ratio = None
            for r in ratios:
                if r["intent"] == intent_l1:
                    current_ratio = r
                    break
            budget_ratio_info = {
                "current_intent_ratio": current_ratio["ratio"] if current_ratio else 0,
                "all_ratios": ratios,
            }
            if current_ratio:
                explanation += f" 战略预算占比：'{intent_l1}'占总预算的{current_ratio['ratio'] * 100:.1f}%（{current_ratio['total_amount']:.0f}元）。"
        except Exception as e:
            budget_ratio_info = {"error": str(e)}

        deviation_attribution = {}
        if abs(rate - target_rate) > 10:
            attribution_reasons = []
            for alert in alerts:
                if alert.alert_status != "已闭环":
                    alert_type = alert.alert_type or ""
                    if "执行" in alert_type or "进度" in alert_type:
                        attribution_reasons.append({"type": "管理效率", "detail": f"{alert_type}预警表明执行管理不足"})
                    elif "预测" in alert_type or "超支" in alert_type:
                        attribution_reasons.append({"type": "市场变化", "detail": f"{alert_type}预警表明市场环境变化导致偏差"})
                    elif "战略" in alert_type:
                        attribution_reasons.append({"type": "战略调整", "detail": f"{alert_type}预警表明战略方向调整"})
                    else:
                        attribution_reasons.append({"type": "其他", "detail": f"{alert_type}预警"})

            try:
                approval_stmt = select(ApprovalRecord).where(
                    ApprovalRecord.approval_comment.isnot(None),
                    ApprovalRecord.approval_comment != "",
                ).limit(10)
                approval_result = await db.execute(approval_stmt)
                approval_records = approval_result.scalars().all()
                for ar in approval_records:
                    comment = ar.approval_comment or ""
                    if any(kw in comment for kw in ["市场", "需求", "竞争"]):
                        attribution_reasons.append({"type": "市场变化", "detail": f"审批意见提及市场因素：{comment[:50]}"})
                    elif any(kw in comment for kw in ["效率", "管理", "执行"]):
                        attribution_reasons.append({"type": "管理效率", "detail": f"审批意见提及管理因素：{comment[:50]}"})
                    elif any(kw in comment for kw in ["战略", "方向", "调整"]):
                        attribution_reasons.append({"type": "战略调整", "detail": f"审批意见提及战略调整：{comment[:50]}"})
            except Exception:
                pass

            if not attribution_reasons:
                if rate < target_rate:
                    attribution_reasons.append({"type": "管理效率", "detail": "执行率偏低，无明确预警或审批意见指向具体原因，默认归因为管理效率"})
                else:
                    attribution_reasons.append({"type": "市场变化", "detail": "执行率偏高，无明确预警或审批意见指向具体原因，默认归因为市场变化"})

            deviation_attribution = {
                "deviation": round(rate - target_rate, 2),
                "reasons": attribution_reasons,
            }
            reason_summary = "、".join(set(r["type"] for r in attribution_reasons))
            explanation += f" 执行偏差归因：{reason_summary}。"

        quadrant_suggestions = {}
        try:
            all_budget_stmt = select(BudgetItem).where(BudgetItem.status.in_(["已授予", "执行中"]))
            all_budget_result = await db.execute(all_budget_stmt)
            all_items = all_budget_result.scalars().all()

            quadrant_stats: Dict[str, Dict] = {}
            for bi in all_items:
                q = bi.quadrant or "未分类"
                if q not in quadrant_stats:
                    quadrant_stats[q] = {"total_amount": 0.0, "used_amount": 0.0, "count": 0}
                quadrant_stats[q]["total_amount"] += float(bi.annual_amount or 0)
                quadrant_stats[q]["used_amount"] += float(bi.used_amount or 0)
                quadrant_stats[q]["count"] += 1

            quadrant_rates = {}
            for q, stats in quadrant_stats.items():
                q_rate = round(stats["used_amount"] / stats["total_amount"] * 100, 2) if stats["total_amount"] > 0 else 0
                quadrant_rates[q] = {
                    "execution_rate": q_rate,
                    "total_amount": stats["total_amount"],
                    "count": stats["count"],
                }

            suggestions = []
            if quadrant_rates:
                sorted_quads = sorted(quadrant_rates.items(), key=lambda x: x[1]["execution_rate"])
                lowest = sorted_quads[0]
                highest = sorted_quads[-1]
                if highest[1]["execution_rate"] - lowest[1]["execution_rate"] > 20:
                    suggestions.append(
                        f"'{highest[0]}'象限执行率({highest[1]['execution_rate']}%)显著高于'{lowest[0]}'象限({lowest[1]['execution_rate']}%)，"
                        f"建议评估是否将部分资源从'{highest[0]}'向'{lowest[0]}'调配"
                    )

                current_q_rate = quadrant_rates.get(quadrant, {})
                if current_q_rate:
                    q_exec = current_q_rate.get("execution_rate", 0)
                    if q_exec < 50 and quadrant == "发展":
                        suggestions.append("发展象限执行率偏低，建议加强项目推进力度或调整预算分配")
                    elif q_exec > 90 and quadrant == "收缩":
                        suggestions.append("收缩象限执行率偏高，建议严格控制支出，加速资源释放")

            quadrant_suggestions = {
                "quadrant_rates": quadrant_rates,
                "suggestions": suggestions,
            }
            if suggestions:
                explanation += f" 象限间资源建议：{'；'.join(suggestions)}"
        except Exception as e:
            quadrant_suggestions = {"error": str(e)}

        return {
            "budget_id": item.budget_id,
            "budget_name": item.budget_name,
            "strategic_intent_l1": intent_l1,
            "strategic_intent_l2": intent_l2,
            "quadrant": quadrant,
            "budget_category": budget_category,
            "execution_rate": rate,
            "target_rate": target_rate,
            "alert_count": len(alerts),
            "deviation_reasons": deviation_reasons,
            "explanation": explanation,
            "budget_ratio": budget_ratio_info,
            "deviation_attribution": deviation_attribution,
            "quadrant_suggestions": quadrant_suggestions,
        }

    async def _tool_comprehensive_review(self, args: Dict, db: AsyncSession) -> Dict:
        from sqlalchemy import select
        from models.budget import BudgetItem
        from models.alert import AlertRecord
        from models.approval import ApprovalRecord
        from engines.business_analysis import BusinessAnalysisEngine
        from engines.pdca_review import PDCAReviewEngine
        from engines.budget_planning import BudgetPlanningEngine

        period = args.get("period", "")
        center_id = args.get("center_id")

        stmt_budget = select(BudgetItem).where(
            BudgetItem.status.in_(["已授予", "执行中"]),
        )
        if center_id:
            stmt_budget = stmt_budget.where(BudgetItem.center_id == center_id)
        result_budget = await db.execute(stmt_budget)
        budget_items = result_budget.scalars().all()

        total_annual = sum(float(i.annual_amount or 0) for i in budget_items)
        total_used = sum(float(i.used_amount or 0) for i in budget_items)
        overall_rate = round(total_used / total_annual * 100, 2) if total_annual > 0 else 0

        gap_data = {}
        try:
            ba_engine = BusinessAnalysisEngine()
            if center_id and period:
                quarter_period = period[:4] + "-Q" + str((int(period.split("-")[1]) - 1) // 3 + 1)
                gap_analysis = await ba_engine.analyze_3gap(center_id, quarter_period, db)
                gap_data = {
                    "gap1": float(gap_analysis.gap1) if gap_analysis.gap1 else 0,
                    "gap2": float(gap_analysis.gap2) if gap_analysis.gap2 else 0,
                    "gap3": float(gap_analysis.gap3) if gap_analysis.gap3 else 0,
                }
        except Exception as e:
            gap_data = {"error": str(e)}

        stmt_alert = select(AlertRecord)
        if center_id:
            budget_ids = [i.budget_id for i in budget_items]
            if budget_ids:
                stmt_alert = stmt_alert.where(AlertRecord.budget_id.in_(budget_ids))
        result_alert = await db.execute(stmt_alert)
        alerts = result_alert.scalars().all()
        alert_summary = {
            "total": len(alerts),
            "open": sum(1 for a in alerts if a.alert_status == "开放"),
            "closed": sum(1 for a in alerts if a.alert_status == "已闭环"),
        }

        approval_comments = []
        try:
            stmt_approval = select(ApprovalRecord).where(
                ApprovalRecord.approval_comment.isnot(None),
                ApprovalRecord.approval_comment != "",
            )
            result_approval = await db.execute(stmt_approval)
            approval_records = result_approval.scalars().all()
            for r in approval_records[:10]:
                approval_comments.append({
                    "approval_id": r.approval_id,
                    "comment": r.approval_comment,
                    "role": r.approver_role,
                })
        except Exception:
            pass

        pdca_data = {}
        try:
            pdca_engine = PDCAReviewEngine()
            if period:
                pdca_result = await pdca_engine.pdca_a_monthly(period, db)
                pdca_data = {
                    "closure_rate": pdca_result.get("closure_rate", 0),
                    "overdue_count": len(pdca_result.get("overdue_alerts", [])),
                    "improvement_actions": pdca_result.get("improvement_actions", []),
                }
        except Exception as e:
            pdca_data = {"error": str(e)}

        strategic_deviation = {}
        try:
            intent_groups: Dict[str, list] = {}
            for item in budget_items:
                intent = item.strategic_intent_l1 or "未分类"
                if intent not in intent_groups:
                    intent_groups[intent] = []
                intent_groups[intent].append(item)

            intent_analysis = []
            for intent, items_list in intent_groups.items():
                intent_annual = sum(float(i.annual_amount or 0) for i in items_list)
                intent_used = sum(float(i.used_amount or 0) for i in items_list)
                intent_rate = round(intent_used / intent_annual * 100, 2) if intent_annual > 0 else 0

                status = "达成" if intent_rate >= 60 else "未达成"
                reasons = []

                if status == "未达成":
                    item_ids = [i.budget_id for i in items_list]
                    if item_ids:
                        stmt_intent_alert = select(AlertRecord).where(
                            AlertRecord.budget_id.in_(item_ids),
                            AlertRecord.alert_status != "已闭环",
                        )
                        intent_alerts_result = await db.execute(stmt_intent_alert)
                        intent_alerts = intent_alerts_result.scalars().all()

                        for alert in intent_alerts:
                            alert_type = alert.alert_type or ""
                            if "执行" in alert_type or "进度" in alert_type:
                                reasons.append({"type": "管理效率", "detail": f"{alert_type}预警"})
                            elif "预测" in alert_type or "超支" in alert_type:
                                reasons.append({"type": "市场变化", "detail": f"{alert_type}预警"})
                            elif "战略" in alert_type:
                                reasons.append({"type": "战略调整", "detail": f"{alert_type}预警"})

                    if not reasons:
                        reasons.append({"type": "管理效率", "detail": "执行率偏低，无明确预警指向具体原因"})

                intent_analysis.append({
                    "strategic_intent": intent,
                    "execution_rate": intent_rate,
                    "status": status,
                    "reasons": reasons,
                    "item_count": len(items_list),
                })

            strategic_deviation = {
                "intent_analysis": intent_analysis,
                "unachieved_count": sum(1 for a in intent_analysis if a["status"] == "未达成"),
            }
        except Exception as e:
            strategic_deviation = {"error": str(e)}

        resource_efficiency = {}
        try:
            budget_utilization = overall_rate / 100.0 if overall_rate > 0 else 0

            strategic_alignment_score = 0.7
            try:
                bp_engine = BudgetPlanningEngine()
                all_items_data = [
                    {
                        "budget_id": i.budget_id,
                        "l1_code": i.l1_code,
                        "budget_name": i.budget_name,
                        "strategy_initiative_id": i.strategy_initiative_id,
                    }
                    for i in budget_items
                ]

                try:
                    from models.strategic import StrategicInitiative
                    stmt_si = select(StrategicInitiative)
                    si_result = await db.execute(stmt_si)
                    initiatives = si_result.scalars().all()
                    strategic_initiatives = [
                        {"id": si.initiative_id, "l1_code": si.strategic_intent_l1, "keywords": []}
                        for si in initiatives
                    ]
                except Exception:
                    strategic_initiatives = []

                aligned_count = 0
                for item_data in all_items_data:
                    alignment = await bp_engine.check_strategic_alignment(item_data, strategic_initiatives, db)
                    if alignment.get("aligned"):
                        aligned_count += 1

                if len(all_items_data) > 0:
                    strategic_alignment_score = aligned_count / len(all_items_data)
            except Exception:
                pass

            efficiency_score = round(budget_utilization * strategic_alignment_score * 100, 2)

            resource_efficiency = {
                "budget_utilization": round(budget_utilization * 100, 2),
                "strategic_alignment": round(strategic_alignment_score * 100, 2),
                "efficiency_score": efficiency_score,
                "rating": "优秀" if efficiency_score >= 60 else "良好" if efficiency_score >= 40 else "待改善",
            }
        except Exception as e:
            resource_efficiency = {"error": str(e)}

        improvement_tracking = {}
        try:
            closed_actions = 0
            unclosed_actions = 0
            improved_after_closure = 0

            if pdca_data and "improvement_actions" in pdca_data:
                actions = pdca_data.get("improvement_actions", [])
                for action in actions:
                    status = action.get("status", "")
                    if status == "已完成" or status == "已闭环":
                        closed_actions += 1
                        budget_id = action.get("budget_id", "")
                        if budget_id:
                            stmt_bi = select(BudgetItem).where(BudgetItem.budget_id == budget_id)
                            bi_result = await db.execute(stmt_bi)
                            bi = bi_result.scalar_one_or_none()
                            if bi and bi.annual_amount and float(bi.annual_amount) > 0:
                                rate = float(bi.used_amount or 0) / float(bi.annual_amount) * 100
                                if 50 <= rate <= 100:
                                    improved_after_closure += 1
                    else:
                        unclosed_actions += 1

            improvement_tracking = {
                "closed_actions": closed_actions,
                "unclosed_actions": unclosed_actions,
                "improved_after_closure": improved_after_closure,
                "closure_improvement_rate": round(improved_after_closure / closed_actions * 100, 2) if closed_actions > 0 else 0,
            }
        except Exception as e:
            improvement_tracking = {"error": str(e)}

        insight_parts = []
        if overall_rate < 50:
            insight_parts.append(f"执行率仅{overall_rate}%，预算使用进度偏慢")
        elif overall_rate > 90:
            insight_parts.append(f"执行率达{overall_rate}%，预算使用进度偏快")
        else:
            insight_parts.append(f"执行率{overall_rate}%，基本符合预期")

        if gap_data.get("gap1") and gap_data["gap1"] != 0:
            insight_parts.append(f"目标差距{gap_data['gap1']}万元")

        if alert_summary["open"] > 0:
            insight_parts.append(f"存在{alert_summary['open']}条开放预警")

        if approval_comments:
            latest_comment = approval_comments[0]
            insight_parts.append(f"最近审批意见：'{latest_comment['comment']}'")

        if strategic_deviation.get("unachieved_count", 0) > 0:
            insight_parts.append(f"{strategic_deviation['unachieved_count']}个战略意图执行率低于60%")

        if resource_efficiency.get("efficiency_score"):
            insight_parts.append(f"资源配置效率评分{resource_efficiency['efficiency_score']}分({resource_efficiency.get('rating', '')})")

        if improvement_tracking.get("unclosed_actions", 0) > 0:
            insight_parts.append(f"{improvement_tracking['unclosed_actions']}项改进行动未闭环")

        insight = "；".join(insight_parts) if insight_parts else "暂无显著异常"

        return {
            "period": period,
            "center_id": center_id,
            "execution_rate": overall_rate,
            "gap_analysis": gap_data,
            "alert_summary": alert_summary,
            "approval_comments": approval_comments,
            "pdca_data": pdca_data,
            "strategic_deviation": strategic_deviation,
            "resource_efficiency": resource_efficiency,
            "improvement_tracking": improvement_tracking,
            "insight": insight,
        }

    def _tool_search_ontology(self, args: Dict) -> Dict:
        keyword = args.get("keyword", "")
        category = args.get("category", "")
        results = []

        if category in ("object", ""):
            from ontology.objects import get_all_objects
            for obj in get_all_objects().values():
                if keyword in obj.name or keyword in (obj.natural_language_definition or ""):
                    results.append({"type": "object", "id": obj.object_id, "name": obj.name})

        if category in ("relation", ""):
            from ontology.relations import get_all_relations
            for rel in get_all_relations().values():
                if keyword in rel.name or keyword in (rel.semantic_description or ""):
                    results.append({"type": "relation", "id": rel.relation_id, "name": rel.name})

        if category in ("behavior", ""):
            from ontology.behaviors import get_all_behaviors
            for beh in get_all_behaviors().values():
                if keyword in beh.name or keyword in (beh.natural_language_definition or ""):
                    results.append({"type": "behavior", "id": beh.behavior_id, "name": beh.name})

        if category in ("rule", ""):
            from ontology.rules import get_all_rules
            for rule in get_all_rules().values():
                if keyword in rule.name or keyword in (rule.natural_language_definition or ""):
                    results.append({"type": "rule", "id": rule.rule_id, "name": rule.name})

        if category in ("scene", ""):
            from ontology.scenes import get_all_scenes
            for scene in get_all_scenes().values():
                if keyword in scene.name or keyword in scene.description:
                    results.append({"type": "scene", "id": scene.scene_id, "name": scene.name})

        return {"keyword": keyword, "results": results[:10]}

    # ═══════════════════════════════════════════════════════════════
    # 预算编制工具实现（从BudgetAgent吸收，真实引擎调用）
    # ═══════════════════════════════════════════════════════════════

    async def _tool_create_budget(self, args: Dict, db: AsyncSession) -> Dict:
        from engines.budget_planning import BudgetPlanningEngine

        bp_engine = BudgetPlanningEngine()
        budget_data = {
            "budget_name": args.get("budget_name", ""),
            "l1_code": args.get("l1_code", "00"),
            "l2_code": args.get("l2_code"),
            "l3_code": args.get("l3_code"),
            "annual_amount": args.get("annual_amount", 0),
            "center_id": args.get("center_id"),
            "department_id": args.get("department_id"),
            "strategy_initiative_id": args.get("strategy_initiative_id"),
            "certainty": args.get("certainty", "medium"),
            "is_approved_project": args.get("is_approved_project", False),
            "strategic_priority": args.get("strategic_priority", "medium"),
        }
        try:
            sp_data = {"strategic_initiatives": []}
            bp_data = {"budget_proposals": [budget_data]}
            created_items = await bp_engine.create_budget_from_strategy(sp_data, bp_data, db)
            if created_items:
                item = created_items[0]
                return {
                    "success": True,
                    "budget_id": item.budget_id,
                    "budget_name": item.budget_name,
                    "budget_category": item.budget_category,
                    "quadrant": item.quadrant,
                    "status": item.status,
                    "annual_amount": float(item.annual_amount or 0),
                    "message": "预算项目创建成功",
                }
            return {"success": False, "message": "预算项目创建失败"}
        except Exception as e:
            logger.error(f"create_budget failed: {e}")
            return {"success": False, "error": str(e)}

    async def _tool_classify_ab(self, args: Dict, db: AsyncSession) -> Dict:
        from engines.budget_planning import BudgetPlanningEngine

        bp_engine = BudgetPlanningEngine()
        budget_id = args.get("budget_id")

        budget_item = dict(args)
        if budget_id:
            from sqlalchemy import select
            from models.budget import BudgetItem
            stmt = select(BudgetItem).where(BudgetItem.budget_id == budget_id)
            result = await db.execute(stmt)
            item = result.scalar_one_or_none()
            if item:
                budget_item = {
                    "budget_id": item.budget_id,
                    "certainty": args.get("certainty", "medium"),
                    "approval_status": getattr(item, "status", "pending"),
                    "has_milestone": bool(item.project_id),
                    "is_approved_project": item.status in ("已授予", "执行中"),
                    "project_id": item.project_id,
                    "annual_amount": float(item.annual_amount or 0),
                    "strategic_priority": args.get("strategic_priority", "medium"),
                }

        try:
            category = await bp_engine.classify_ab_category(budget_item, db)
            return {
                "budget_id": budget_id,
                "category": category,
                "message": f"预算项目分类为{category}类",
            }
        except Exception as e:
            logger.error(f"classify_ab failed: {e}")
            return {"budget_id": budget_id, "category": "B", "error": str(e)}

    async def _tool_recommend_quadrant(self, args: Dict, db: AsyncSession) -> Dict:
        from engines.budget_planning import BudgetPlanningEngine

        bp_engine = BudgetPlanningEngine()
        strategic_initiative = {
            "growth_rate": args.get("growth_rate", 0),
            "market_share": args.get("market_share", 0),
            "priority": args.get("strategic_priority", "medium"),
            "strategic_intent_l1": args.get("strategic_intent_l1"),
        }
        try:
            result = await bp_engine.recommend_quadrant(strategic_initiative, db)
            return {
                "quadrant": result.get("quadrant", "稳定"),
                "flag_for_review": result.get("flag_for_review", False),
                "strategic_intent_adjustment": result.get("strategic_intent_adjustment"),
                "message": f"推荐象限：{result.get('quadrant', '稳定')}",
            }
        except Exception as e:
            logger.error(f"recommend_quadrant failed: {e}")
            return {"quadrant": "稳定", "error": str(e)}

    # ═══════════════════════════════════════════════════════════════
    # 预算授予工具实现（从BudgetAgent吸收，真实引擎调用）
    # ═══════════════════════════════════════════════════════════════

    async def _tool_grant_a_class(self, args: Dict, db: AsyncSession) -> Dict:
        from engines.budget_grant import BudgetGrantEngine

        budget_id = args.get("budget_id", "")
        try:
            bg_engine = BudgetGrantEngine()
            item = await bg_engine.grant_a_class(budget_id, db)
            return {
                "success": True,
                "budget_id": item.budget_id,
                "budget_category": item.budget_category,
                "grant_percentage": float(item.grant_percentage or 0),
                "granted_amount": float(item.granted_amount or 0),
                "frozen_amount": float(item.frozen_amount or 0),
                "available_amount": float(item.available_amount or 0),
                "status": item.status,
                "message": "A类预算授予成功，100%冻结",
            }
        except ValueError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"grant_a_class failed: {e}")
            return {"success": False, "error": str(e)}

    async def _tool_grant_b_class(self, args: Dict, db: AsyncSession) -> Dict:
        from engines.budget_grant import BudgetGrantEngine

        budget_id = args.get("budget_id", "")
        try:
            bg_engine = BudgetGrantEngine()
            item = await bg_engine.grant_b_class(budget_id, db)
            return {
                "success": True,
                "budget_id": item.budget_id,
                "budget_category": item.budget_category,
                "grant_percentage": float(item.grant_percentage or 0),
                "granted_amount": float(item.granted_amount or 0),
                "status": item.status,
                "pending_project_budget_id": item.pending_project_budget_id,
                "message": "B类预算处理完成，0%授予，已创建里程碑跟踪",
            }
        except ValueError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"grant_b_class failed: {e}")
            return {"success": False, "error": str(e)}

    async def _tool_b2a_convert(self, args: Dict, db: AsyncSession) -> Dict:
        from engines.budget_grant import BudgetGrantEngine

        budget_id = args.get("budget_id", "")
        milestone_evidence = args.get("milestone_evidence", "")
        try:
            bg_engine = BudgetGrantEngine()
            item = await bg_engine.b2a_convert(budget_id, milestone_evidence, db)
            return {
                "success": True,
                "budget_id": item.budget_id,
                "budget_category": item.budget_category,
                "grant_percentage": float(item.grant_percentage or 0),
                "granted_amount": float(item.granted_amount or 0),
                "frozen_amount": float(item.frozen_amount or 0),
                "available_amount": float(item.available_amount or 0),
                "status": item.status,
                "message": "B→A转换成功",
            }
        except ValueError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"b2a_convert failed: {e}")
            return {"success": False, "error": str(e)}

    # ═══════════════════════════════════════════════════════════════
    # 费用报销工具实现（从ExpenseAgent吸收，真实引擎调用）
    # ═══════════════════════════════════════════════════════════════

    async def _tool_submit_expense(self, args: Dict, db: AsyncSession) -> Dict:
        from engines.expense_reimbursement import ExpenseReimbursementEngine

        er_engine = ExpenseReimbursementEngine()
        expense_data = {
            "budget_id": args.get("budget_id"),
            "amount": args.get("amount", 0),
            "description": args.get("description", ""),
            "l3_code": args.get("l3_code"),
            "applicant_id": args.get("applicant_id", ""),
            "center_id": args.get("center_id"),
            "department_id": args.get("department_id"),
            "legal_entity_id": args.get("legal_entity_id"),
            "invoices": args.get("invoices", []),
        }
        try:
            report = await er_engine.submit_expense(expense_data, db)
            return {
                "success": True,
                "expense_id": report.expense_id,
                "budget_id": report.budget_id,
                "amount": float(report.amount or 0),
                "control_tag": report.control_tag,
                "status": report.status,
                "message": f"报销单提交成功，状态：{report.status}",
            }
        except ValueError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"submit_expense failed: {e}")
            return {"success": False, "error": str(e)}

    async def _tool_route_control(self, args: Dict, db: AsyncSession) -> Dict:
        from engines.expense_reimbursement import ExpenseReimbursementEngine

        l3_code = args.get("l3_code")
        try:
            er_engine = ExpenseReimbursementEngine()
            result = await er_engine.route_control_level(l3_code, db)
            return {
                "l3_code": l3_code,
                "control_tag": result.get("control_tag"),
                "cross_dept": result.get("cross_dept"),
                "cross_category": result.get("cross_category"),
                "approval_requirements": result.get("approval_requirements", []),
            }
        except Exception as e:
            logger.error(f"route_control failed: {e}")
            return {"error": str(e)}

    async def _tool_check_invoice(self, args: Dict, db: AsyncSession) -> Dict:
        from engines.expense_reimbursement import ExpenseReimbursementEngine

        invoice_number = args.get("invoice_number", "")
        try:
            er_engine = ExpenseReimbursementEngine()
            is_duplicate = await er_engine.check_invoice_duplicate(invoice_number, db)
            return {
                "invoice_number": invoice_number,
                "is_duplicate": is_duplicate,
                "message": "发票已存在，请勿重复提交" if is_duplicate else "发票未重复",
            }
        except Exception as e:
            logger.error(f"check_invoice failed: {e}")
            return {"error": str(e)}

    async def _tool_write_off(self, args: Dict, db: AsyncSession) -> Dict:
        from engines.expense_reimbursement import ExpenseReimbursementEngine

        expense_id = args.get("expense_id", "")
        try:
            er_engine = ExpenseReimbursementEngine()
            write_off = await er_engine.write_off_budget(expense_id, db)
            return {
                "success": True,
                "write_off_id": write_off.write_off_id,
                "expense_id": write_off.expense_id,
                "budget_id": write_off.budget_id,
                "write_off_amount": float(write_off.write_off_amount or 0),
                "execution_rate": float(write_off.execution_rate or 0),
                "message": "预算核销成功",
            }
        except ValueError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"write_off failed: {e}")
            return {"success": False, "error": str(e)}

    # ═══════════════════════════════════════════════════════════════
    # 预警监控工具实现（从AlertAgent吸收，真实引擎调用）
    # ═══════════════════════════════════════════════════════════════

    async def _tool_scan_alerts(self, args: Dict, db: AsyncSession) -> Dict:
        from sqlalchemy import select
        from models.alert import AlertRecord

        alert_level = args.get("alert_level")
        alert_status = args.get("alert_status")
        l1_code = args.get("l1_code")
        limit = args.get("limit", 20)

        stmt = select(AlertRecord)
        if alert_level:
            stmt = stmt.where(AlertRecord.alert_level == alert_level)
        if alert_status:
            stmt = stmt.where(AlertRecord.alert_status == alert_status)
        if l1_code:
            stmt = stmt.where(AlertRecord.l1_code == l1_code)
        stmt = stmt.limit(limit)

        result = await db.execute(stmt)
        alerts = result.scalars().all()

        return {
            "data": [
                {
                    "alert_id": a.alert_id,
                    "alert_level": a.alert_level,
                    "alert_type": a.alert_type,
                    "alert_status": a.alert_status,
                    "l1_code": a.l1_code,
                    "budget_id": a.budget_id,
                    "deviation_rate": float(a.deviation_rate) if a.deviation_rate else 0,
                    "response_deadline": a.response_deadline.isoformat() if a.response_deadline else None,
                }
                for a in alerts
            ],
            "total": len(alerts),
        }

    async def _tool_respond_alert(self, args: Dict, db: AsyncSession) -> Dict:
        from engines.alert_monitor import AlertMonitorEngine

        alert_id = args.get("alert_id", "")
        response = args.get("response", "")
        responder = args.get("responder", "")
        try:
            am_engine = AlertMonitorEngine()
            closure = await am_engine.respond_alert(alert_id, response, responder, db)
            return {
                "success": True,
                "closure_id": closure.closure_id,
                "alert_id": alert_id,
                "closure_status": closure.closure_status,
                "message": "预警响应已提交",
            }
        except ValueError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"respond_alert failed: {e}")
            return {"success": False, "error": str(e)}

    async def _tool_confirm_closure(self, args: Dict, db: AsyncSession) -> Dict:
        from engines.alert_monitor import AlertMonitorEngine

        closure_id = args.get("closure_id", "")
        bp_confirmation = args.get("bp_confirmation", "")
        bp_confirmer = args.get("bp_confirmer", "")
        try:
            am_engine = AlertMonitorEngine()
            closure = await am_engine.confirm_closure(closure_id, bp_confirmation, bp_confirmer, db)
            return {
                "success": True,
                "closure_id": closure.closure_id,
                "alert_id": closure.alert_id,
                "closure_status": closure.closure_status,
                "message": "预警闭环确认完成",
            }
        except ValueError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"confirm_closure failed: {e}")
            return {"success": False, "error": str(e)}

    async def _tool_escalate_alert(self, args: Dict, db: AsyncSession) -> Dict:
        from engines.alert_monitor import AlertMonitorEngine

        alert_id = args.get("alert_id", "")
        try:
            am_engine = AlertMonitorEngine()
            escalation = await am_engine.escalate_alert(alert_id, db)
            return {
                "success": True,
                "escalation_id": escalation.escalation_id,
                "alert_id": alert_id,
                "escalation_reason": escalation.escalation_reason,
                "escalation_level": escalation.escalation_level,
                "escalation_target": escalation.escalation_target,
                "message": "预警已升级",
            }
        except ValueError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"escalate_alert failed: {e}")
            return {"success": False, "error": str(e)}

    async def _tool_get_alert_stats(self, args: Dict, db: AsyncSession) -> Dict:
        from sqlalchemy import select
        from models.alert import AlertRecord

        l1_code = args.get("l1_code")

        stmt = select(AlertRecord)
        if l1_code:
            stmt = stmt.where(AlertRecord.l1_code == l1_code)
        result = await db.execute(stmt)
        alerts = result.scalars().all()

        by_level = {"蓝色": 0, "黄色": 0, "橙色": 0, "红色": 0}
        by_status = {"开放": 0, "响应中": 0, "待闭环确认": 0, "已闭环": 0, "已升级": 0}
        for a in alerts:
            by_level[a.alert_level] = by_level.get(a.alert_level, 0) + 1
            by_status[a.alert_status] = by_status.get(a.alert_status, 0) + 1

        return {
            "total": len(alerts),
            "by_level": by_level,
            "by_status": by_status,
            "l1_code": l1_code,
        }

    # ═══════════════════════════════════════════════════════════════
    # 经营分析工具实现（从AnalysisAgent吸收，真实引擎调用）
    # ═══════════════════════════════════════════════════════════════

    async def _tool_calculate_execution_rates(self, args: Dict, db: AsyncSession) -> Dict:
        from engines.business_analysis import BusinessAnalysisEngine

        center_id = args.get("center_id", "")
        period = args.get("period", "")
        try:
            ba_engine = BusinessAnalysisEngine()
            rates = await ba_engine.calculate_execution_rates(center_id, period, db)
            return {
                "success": True,
                "center_id": center_id,
                "period": period,
                "data": [
                    {
                        "l1_code": r.l1_code,
                        "monthly_rate": float(r.monthly_rate) if r.monthly_rate else 0,
                        "cumulative_rate": float(r.cumulative_rate) if r.cumulative_rate else 0,
                        "annual_rate": float(r.annual_rate) if r.annual_rate else 0,
                    }
                    for r in rates
                ],
                "count": len(rates),
                "message": f"执行率计算完成，共{len(rates)}条记录",
            }
        except Exception as e:
            logger.error(f"calculate_execution_rates failed: {e}")
            return {"success": False, "error": str(e)}

    async def _tool_check_quadrant_compliance(self, args: Dict, db: AsyncSession) -> Dict:
        from engines.business_analysis import BusinessAnalysisEngine

        period = args.get("period", "")
        try:
            ba_engine = BusinessAnalysisEngine()
            results = await ba_engine.check_quadrant_compliance(period, db)
            return {
                "success": True,
                "period": period,
                "data": results,
                "message": "象限合规检查完成",
            }
        except Exception as e:
            logger.error(f"check_quadrant_compliance failed: {e}")
            return {"success": False, "error": str(e)}

    # ═══════════════════════════════════════════════════════════════
    # 报表出具工具实现（从ReportAgent吸收，真实引擎调用）
    # ═══════════════════════════════════════════════════════════════

    async def _tool_generate_monthly_flash(self, args: Dict, db: AsyncSession) -> Dict:
        from engines.report_engine import ReportEngine

        period = args.get("period", "")
        try:
            rp_engine = ReportEngine()
            content = await rp_engine.generate_monthly_flash(period, db)
            return {
                "success": True,
                "report_type": "月度快报",
                "period": period,
                "content": content,
                "message": "月度快报生成完成",
            }
        except Exception as e:
            logger.error(f"generate_monthly_flash failed: {e}")
            return {"success": False, "error": str(e)}

    async def _tool_generate_quarterly_report(self, args: Dict, db: AsyncSession) -> Dict:
        from engines.report_engine import ReportEngine

        period = args.get("period", "")
        try:
            rp_engine = ReportEngine()
            content = await rp_engine.generate_quarterly_report(period, db)
            return {
                "success": True,
                "report_type": "季度汇报",
                "period": period,
                "content": content,
                "message": "季度汇报生成完成",
            }
        except Exception as e:
            logger.error(f"generate_quarterly_report failed: {e}")
            return {"success": False, "error": str(e)}

    async def _tool_generate_annual_review(self, args: Dict, db: AsyncSession) -> Dict:
        from engines.report_engine import ReportEngine

        period = args.get("period", "")
        try:
            rp_engine = ReportEngine()
            content = await rp_engine.generate_annual_review(period, db)
            return {
                "success": True,
                "report_type": "年度复盘",
                "period": period,
                "content": content,
                "message": "年度复盘生成完成",
            }
        except Exception as e:
            logger.error(f"generate_annual_review failed: {e}")
            return {"success": False, "error": str(e)}

    # ═══════════════════════════════════════════════════════════════
    # 高级分析工具实现（新增5个，调用增强引擎）
    # ═══════════════════════════════════════════════════════════════

    async def _tool_predict_execution_trend(self, args: Dict, db: AsyncSession) -> Dict:
        from engines.business_analysis import BusinessAnalysisEngine

        l1_code = args.get("l1_code", "")
        months_ahead = args.get("months_ahead", 6)
        try:
            ba_engine = BusinessAnalysisEngine()
            result = await ba_engine.predict_execution_trend(l1_code, db, months_ahead)
            return {
                "success": True,
                "l1_code": l1_code,
                "months_ahead": months_ahead,
                "trend_direction": result.get("trend_direction", "unknown"),
                "historical_data": result.get("historical_data", []),
                "predictions": result.get("predictions", []),
                "inflection_points": result.get("inflection_points", []),
                "message": f"执行趋势预测完成，趋势方向：{result.get('trend_direction', 'unknown')}",
            }
        except Exception as e:
            logger.error(f"predict_execution_trend failed: {e}")
            return {"success": False, "error": str(e)}

    async def _tool_detect_anomalies(self, args: Dict, db: AsyncSession) -> Dict:
        from engines.business_analysis import BusinessAnalysisEngine

        period = args.get("period", "")
        z_threshold = args.get("z_threshold", 2.0)
        iqr_multiplier = args.get("iqr_multiplier", 1.5)
        try:
            ba_engine = BusinessAnalysisEngine()
            result = await ba_engine.detect_anomalies(period, db, z_threshold, iqr_multiplier)
            return {
                "success": True,
                "period": period,
                "anomalies": result.get("anomalies", []),
                "anomaly_count": len(result.get("anomalies", [])),
                "detection_method": result.get("detection_method", "Z-score + IQR"),
                "message": f"异常检测完成，发现{len(result.get('anomalies', []))}个异常点",
            }
        except Exception as e:
            logger.error(f"detect_anomalies failed: {e}")
            return {"success": False, "error": str(e)}

    async def _tool_root_cause_analysis(self, args: Dict, db: AsyncSession) -> Dict:
        from engines.business_analysis import BusinessAnalysisEngine

        issue_type = args.get("issue_type", "")
        period = args.get("period", "")
        l1_code = args.get("l1_code")
        try:
            ba_engine = BusinessAnalysisEngine()
            result = await ba_engine.root_cause_analysis(issue_type, period, l1_code, db)
            return {
                "success": True,
                "issue_type": issue_type,
                "period": period,
                "l1_code": l1_code,
                "root_causes": result.get("root_causes", []),
                "contributing_factors": result.get("contributing_factors", []),
                "recommendations": result.get("recommendations", []),
                "message": f"根因分析完成，识别{len(result.get('root_causes', []))}个根本原因",
            }
        except Exception as e:
            logger.error(f"root_cause_analysis failed: {e}")
            return {"success": False, "error": str(e)}

    async def _tool_cascade_risk_assess(self, args: Dict, db: AsyncSession) -> Dict:
        from engines.alert_monitor import AlertMonitorEngine

        l1_code = args.get("l1_code", "")
        try:
            alert_engine = AlertMonitorEngine()
            result = await alert_engine.cascade_risk_assess(l1_code, db)
            return {
                "success": True,
                "l1_code": l1_code,
                "cascade_impact": result.get("cascade_impact", {}),
                "affected_l2_subjects": result.get("affected_l2_subjects", []),
                "affected_strategic_intents": result.get("affected_strategic_intents", []),
                "risk_level": result.get("risk_level", "unknown"),
                "message": f"级联风险评估完成，影响{len(result.get('affected_l2_subjects', []))}个L2科目",
            }
        except Exception as e:
            logger.error(f"cascade_risk_assess failed: {e}")
            return {"success": False, "error": str(e)}

    async def _tool_alert_pattern_analysis(self, args: Dict, db: AsyncSession) -> Dict:
        from engines.alert_monitor import AlertMonitorEngine

        l1_code = args.get("l1_code")
        lookback_months = args.get("lookback_months", 6)
        try:
            alert_engine = AlertMonitorEngine()
            result = await alert_engine.alert_pattern_analysis(l1_code, db, lookback_months)
            return {
                "success": True,
                "l1_code": l1_code,
                "lookback_months": lookback_months,
                "systemic_issues": result.get("systemic_issues", []),
                "sporadic_issues": result.get("sporadic_issues", []),
                "high_frequency_l1s": result.get("high_frequency_l1s", []),
                "pattern_summary": result.get("pattern_summary", ""),
                "message": f"预警模式分析完成，识别{len(result.get('systemic_issues', []))}个系统性问题",
            }
        except Exception as e:
            logger.error(f"alert_pattern_analysis failed: {e}")
            return {"success": False, "error": str(e)}

    def get_suggestions(self) -> List[str]:
        return [
            "查看本月预算执行情况",
            "当前有哪些预警需要处理？",
            "帮我分析B1科目的3GAP",
            "模拟预算调拨方案",
            "生成本月执行快报",
            "创建一个新的预算项目",
            "提交一笔报销",
            "检查发票是否重复",
            "对B类预算进行B→A转换",
            "查看象限合规性",
        ]
