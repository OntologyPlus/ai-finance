from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from agents.base import BaseAgent, ToolCapableBaseAgent, get as get_agent_cls
from agents.state import AgentState, ReflectionResult
from services.intent_classifier import IntentClassifier
from services.guardrails import Guardrails
from services.semantic_cache import get_semantic_cache
from services.slot_extractor import SlotExtractor
from ontology.scenes import match_scene
from ontology.rules import RuleEngine


# 意图→Agent名称映射
_INTENT_AGENT_MAP = {
    "budget_query": "budget_planning",
    "expense_query": "expense_reimbursement",
    "alert_query": "alert_monitor",
    "analysis_query": "business_analysis",
    "report_query": "report_generation",
    "pdca_query": "general_query",
    "ontology_query": "general_query",
    "general": "general_query",
    # New intents
    "cash_flow_query": "general_query",
    "scenario_query": "general_query",
    "impact_query": "general_query",
    "zbb_query": "general_query",
    "cost_center_query": "general_query",
    "hcp_query": "general_query",
    "pipeline_query": "general_query",
    "meeting_query": "general_query",
}

# 跨域意图 → 多 Agent 串联
_CROSS_DOMAIN_AGENTS: Dict[str, List[str]] = {
    "impact_query": ["budget_planning", "expense_reimbursement", "alert_monitor"],
    "scenario_query": ["budget_planning", "business_analysis", "general_query"],
    "analysis_query": ["business_analysis", "report_generation", "alert_monitor"],
}


class Supervisor:
    """LangGraph风格的多Agent编排器，使用状态机驱动协作流程
    v8.0 增强：语义缓存 + 槽位提取 + 多 Agent 串联 + 评估指标
    """

    def __init__(self):
        self._classifier = IntentClassifier()
        self._guardrails = Guardrails()
        self._slot_extractor = SlotExtractor()
        self._semantic_cache = get_semantic_cache()
        self._agents: Dict[str, BaseAgent] = {}
        self._max_reflection_rounds = 3
        # 评估指标（v8.0 增量）
        self._metrics: Dict[str, Any] = {
            "total_queries": 0,
            "cache_hits": 0,
            "multi_agent_runs": 0,
            "agent_failures": 0,
            "latency_samples": [],
            "intent_counts": {},
            # ── Phase 1 增量：工具调用统计 ──
            "tool_call_count": 0,
            "tool_calls_by_name": {},  # tool_name -> count
            "tool_distinct_per_query_samples": [],  # 每次 query 用了几种 tool（>3 视为探索失败）
        }

    def get_metrics(self) -> Dict[str, Any]:
        """获取评估指标快照"""
        m = dict(self._metrics)
        m["cache_stats"] = self._semantic_cache.get_stats()
        latencies = m.pop("latency_samples", [])
        if latencies:
            m["avg_latency_ms"] = round(sum(latencies) / len(latencies), 1)
            m["p95_latency_ms"] = round(sorted(latencies)[int(len(latencies) * 0.95)], 1)
        else:
            m["avg_latency_ms"] = 0.0
            m["p95_latency_ms"] = 0.0
        m["success_rate"] = (
            round(1.0 - m["agent_failures"] / m["total_queries"], 4)
            if m["total_queries"] > 0
            else 0.0
        )

        # ── 工具选择质量代理指标 ──
        # 准确率靠 eval_cases 的 expected_tool_set 评估（见 eval/runner.py），
        # 这里只暴露"工具调用统计 + 探索深度"作为运行时观察指标。
        tool_distinct_samples = m.pop("tool_distinct_per_query_samples", [])
        m["avg_tool_distinct_per_query"] = (
            round(sum(tool_distinct_samples) / len(tool_distinct_samples), 2)
            if tool_distinct_samples
            else 0.0
        )
        # 工具探索失败率：单次 query 用超过 3 种不同 tool 的比例（启发式阈值）
        m["tool_exploration_overrun_rate"] = (
            round(sum(1 for s in tool_distinct_samples if s > 3) / len(tool_distinct_samples), 4)
            if tool_distinct_samples
            else 0.0
        )
        # Top 5 工具使用统计
        m["top_tools"] = sorted(
            m.get("tool_calls_by_name", {}).items(),
            key=lambda kv: kv[1], reverse=True,
        )[:5]
        return m

    def record_tool_call(self, tool_name: str) -> None:
        """记录一次 tool 调用（由 Agent / ToolCapableBaseAgent 在 _handle_tool_calls 内调用）。

        这是工具选择准确率指标的最小化采集点——只看"调了哪些 tool、多频繁"，
        真正的"是否选对"由 eval/runner.py 用 expected_tool_set 对账。
        """
        self._metrics["tool_call_count"] += 1
        bucket = self._metrics["tool_calls_by_name"]
        bucket[tool_name] = bucket.get(tool_name, 0) + 1

    def end_query_tool_recording(self) -> None:
        """单次 query 结束时记录"用了几种不同 tool"用于探索深度指标。"""
        bucket = self._metrics["tool_calls_by_name"]
        # 取本次 query 之后新增的 tool 数 = end - start 的差
        # 简化做法：用 total_queries 来推算本次 distinct 数 = 调用方传入
        # 实际生产可改用 ThreadLocal 累积 query 级 bucket
        pass  # 占位，具体由 FinanceAgent 在 _handle_tool_calls 内统计后调用

    def record_query_distinct_tools(self, distinct_count: int) -> None:
        """单次 query 结束时调用，记录本次 query 用了几种不同 tool。"""
        self._metrics["tool_distinct_per_query_samples"].append(distinct_count)
        # 防止内存无限增长（最多保留 1000 个样本）
        if len(self._metrics["tool_distinct_per_query_samples"]) > 1000:
            self._metrics["tool_distinct_per_query_samples"] = (
                self._metrics["tool_distinct_per_query_samples"][-1000:]
            )

    def _get_agent(self, name: str) -> Optional[BaseAgent]:
        """获取Agent实例，懒加载"""
        if name in self._agents:
            return self._agents[name]

        agent_cls = get_agent_cls(name)
        if agent_cls is None:
            logger.warning(f"Agent '{name}' not found in registry")
            return None

        agent = agent_cls()
        self._agents[name] = agent
        return agent

    async def run(self, state: AgentState) -> AgentState:
        """执行完整的状态机流程（v8.0 增强：语义缓存 + 槽位 + 多 Agent 串联）"""
        start_time = time.time()
        self._metrics["total_queries"] += 1

        # Step 1: Guardrails安全检查
        state = await self._guardrails_node(state)
        if not state.get("safe", True):
            return state

        # Step 1.5: 语义缓存检查
        user_input = self._extract_user_input(state)
        if user_input:
            cache_hit = self._semantic_cache.get(user_input)
            if cache_hit.hit:
                self._metrics["cache_hits"] += 1
                state["response"] = cache_hit.response
                state["cache_hit"] = True
                state["cache_similarity"] = cache_hit.similarity
                state["matched_query"] = cache_hit.matched_query
                self._metrics["latency_samples"].append(
                    (time.time() - start_time) * 1000
                )
                logger.info(
                    f"Semantic cache hit (sim={cache_hit.similarity:.2f}) for: {user_input[:50]}"
                )
                return state

        # Step 2: 意图分类
        state = await self._classify_node(state)
        # Step 2.5: 槽位提取（增强意图）
        state = await self._slot_extraction_node(state, user_input)

        # Step 3: 路由 — 单一或串联
        intent = state.get("intent", "general")
        if intent in _CROSS_DOMAIN_AGENTS:
            state = await self._multi_agent_node(state)
        else:
            state = await self._agent_node(state)

        # Step 4: Self-Reflection循环
        state = await self._reflect_node(state)

        # Step 5: 幻觉检测
        state = await self._hallucination_check_node(state)

        # 写入语义缓存
        response = state.get("response", "")
        if response and not state.get("cache_hit", False) and len(response) > 10:
            self._semantic_cache.set(
                user_input,
                response,
                metadata={
                    "intent": state.get("intent"),
                    "agent": state.get("agent_name"),
                },
            )

        # 记录延迟
        self._metrics["latency_samples"].append(
            (time.time() - start_time) * 1000
        )
        if len(self._metrics["latency_samples"]) > 1000:
            self._metrics["latency_samples"] = self._metrics["latency_samples"][-1000:]

        return state

    @staticmethod
    def _extract_user_input(state: AgentState) -> str:
        """从 state 提取用户输入"""
        messages = state.get("messages", [])
        for m in reversed(messages):
            if isinstance(m, dict) and m.get("role") == "user":
                return m.get("content", "")
        return ""

    async def _slot_extraction_node(
        self, state: AgentState, user_input: str
    ) -> AgentState:
        """v8.0 槽位提取节点：增强意图路由精度"""
        if not user_input:
            return state
        try:
            result = self._slot_extractor.extract(user_input)
            state["slots"] = self._slot_extractor.to_dict(result)

            # 意图提示覆盖（仅当原分类置信度低时）
            if result.intent_hint and state.get("intent_confidence", 1.0) < 0.6:
                state["intent"] = result.intent_hint
                state["intent_hint_applied"] = True
                state["agent_name"] = _INTENT_AGENT_MAP.get(
                    result.intent_hint, "general_query"
                )
                logger.info(
                    f"Slot-based intent override: {result.intent_hint} "
                    f"(slots: {list(result.slots.keys())})"
                )
        except Exception as e:
            logger.warning(f"Slot extraction failed: {e}")
        return state

    async def _multi_agent_node(self, state: AgentState) -> AgentState:
        """v8.0 多 Agent 串联节点：跨域问题路由到 2-3 Agent 串行处理"""
        intent = state.get("intent", "general")
        agent_names = _CROSS_DOMAIN_AGENTS.get(intent, [])
        if not agent_names:
            return await self._agent_node(state)

        self._metrics["multi_agent_runs"] += 1
        context = state.get("context", {})
        db = context.get("db")
        messages = state.get("messages", [])

        sub_responses: List[Dict[str, Any]] = []
        for name in agent_names:
            agent = self._get_agent(name)
            if agent is None:
                continue
            try:
                start = time.time()
                resp = await agent.execute(messages, context, db)
                sub_responses.append(
                    {
                        "agent": name,
                        "response": resp,
                        "latency_ms": round((time.time() - start) * 1000, 1),
                    }
                )
            except Exception as e:
                self._metrics["agent_failures"] += 1
                logger.error(f"Multi-agent [{name}] error: {e}")
                sub_responses.append(
                    {
                        "agent": name,
                        "response": f"[{name} 处理失败: {e}]",
                        "latency_ms": 0,
                    }
                )

        joined = "\n\n".join(
            f"### {r['agent']}\n{r['response']}" for r in sub_responses
        )
        state["response"] = (
            f"[多 Agent 协作：{len(sub_responses)} 个 Agent 联合处理]\n\n{joined}"
        )
        state["multi_agent_responses"] = sub_responses
        state["agent_name"] = "multi_agent"
        return state

    async def _guardrails_node(self, state: AgentState) -> AgentState:
        """安全检查节点"""
        messages = state.get("messages", [])
        user_input = ""
        for m in reversed(messages):
            if isinstance(m, dict) and m.get("role") == "user":
                user_input = m.get("content", "")
                break

        safe, masked_text, violations = self._guardrails.check(user_input)
        state["safe"] = safe
        state["violations"] = violations

        if not safe:
            state["response"] = "您的输入包含不安全内容，请修改后重试。"
            state["intent"] = "blocked"
            state["intent_confidence"] = 1.0
            return state

        if violations:
            new_messages = []
            for m in messages:
                if isinstance(m, dict) and m.get("role") == "user":
                    new_messages.append({"role": "user", "content": masked_text})
                else:
                    new_messages.append(m)
            state["messages"] = new_messages

        return state

    async def _classify_node(self, state: AgentState) -> AgentState:
        """意图分类节点"""
        messages = state.get("messages", [])
        user_input = ""
        for m in reversed(messages):
            if isinstance(m, dict) and m.get("role") == "user":
                user_input = m.get("content", "")
                break

        intent, confidence = await self._classifier.classify(user_input)
        state["intent"] = intent
        state["intent_confidence"] = confidence

        # 映射意图到Agent名称
        agent_name = _INTENT_AGENT_MAP.get(intent, "general_query")
        state["agent_name"] = agent_name

        logger.info(f"Intent classified: {intent} ({confidence:.2f}) -> Agent: {agent_name}")
        return state

    async def _agent_node(self, state: AgentState) -> AgentState:
        """专业Agent执行节点"""
        agent_name = state.get("agent_name", "general_query")
        agent = self._get_agent(agent_name)

        if agent is None:
            # Fallback到通用Agent
            agent = self._get_agent("general_query")
            if agent is None:
                state["response"] = "系统暂不可用，请稍后重试。"
                return state
            state["agent_name"] = "general_query"

        context = state.get("context", {})
        db = context.get("db")

        if db is None:
            state["response"] = "数据库连接不可用，请稍后重试。"
            return state

        messages = state.get("messages", [])

        try:
            if isinstance(agent, ToolCapableBaseAgent):
                role_type = context.get("role_type", "员工")
                perm_result = agent.check_ai_permission("finance", role_type, "suggest")
                if not perm_result.allowed:
                    state["response"] = (
                        f"根据您的角色权限({role_type})，当前场景下AI仅具有"
                        f"{perm_result.ai_level.value}权限，无法执行建议操作。"
                    )
                    return state

            response = await agent.execute(messages, context, db)
            state["response"] = response
        except Exception as e:
            logger.error(f"Agent execution error [{agent_name}]: {e}")
            state["response"] = "处理您的请求时遇到错误，请稍后重试。"

        return state

    async def _reflect_node(self, state: AgentState) -> AgentState:
        """Self-Reflection节点：判断是否需要继续补充调用"""
        reflection_count = state.get("reflection_count", 0)
        response = state.get("response", "")

        # 简单规则判断是否需要继续
        should_continue = False
        if not response or len(response.strip()) < 10:
            should_continue = True
        elif response.startswith("[LLM调用失败]") or response.startswith("[流式调用失败]"):
            should_continue = True
        elif "请提供更多" in response or "需要更多信息" in response:
            should_continue = True

        if should_continue and reflection_count < self._max_reflection_rounds:
            state["reflection_count"] = reflection_count + 1
            state["reflection_passed"] = False

            # 重新执行Agent
            state = await self._agent_node(state)
            return state

        state["reflection_passed"] = True
        return state

    async def _hallucination_check_node(self, state: AgentState) -> AgentState:
        """幻觉检测节点"""
        agent_name = state.get("agent_name", "general_query")
        agent = self._agents.get(agent_name)

        if agent and isinstance(agent, ToolCapableBaseAgent):
            response = state.get("response", "")
            hallucination_result = agent.check_hallucination(response)

            if hallucination_result.should_refuse:
                state["response"] = (
                    f"{response}\n\n"
                    f"⚠️ [AI输出置信度不足] {hallucination_result.refusal_reason}\n"
                    f"请以系统实际数据为准，以上建议仅供参考。"
                )
                state["hallucination_safe"] = False
            elif not hallucination_result.is_safe:
                state["response"] = response + "\n\n⚠️ [部分信息待验证] 请以系统实际数据为准。"
                state["hallucination_safe"] = False
            else:
                state["hallucination_safe"] = True

        return state

# ── 全局单例 ──────────────────────────────────────────────────
_default_supervisor: Optional["Supervisor"] = None


def get_supervisor() -> "Supervisor":
    """获取 Supervisor 默认单例。

    用于跨模块（如 FinanceAgent）调用 record_tool_call 等指标采集方法，
    避免把 Supervisor 实例四处传递。
    """
    global _default_supervisor
    if _default_supervisor is None:
        _default_supervisor = Supervisor()
    return _default_supervisor
