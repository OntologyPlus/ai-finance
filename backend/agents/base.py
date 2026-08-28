from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from ontology.context_injection import OntologyContextInjector, OAGContext
from ontology.hallucination_guard import OntologyHallucinationGuard, HallucinationCheckResult
from ontology.permissions import OntologyPermissionEngine, PermissionCheckResult
from skills.skill_loader import Skill


@dataclass
class ReflectionResult:
    """Self-Reflection结果"""
    should_continue: bool
    next_action: Optional[str] = None
    reasoning: str = ""


class BaseAgent(ABC):
    name: str = ""
    description: str = ""
    supported_intents: List[str] = []

    @abstractmethod
    async def execute(
        self,
        messages: List[Dict[str, str]],
        context: Dict[str, Any],
        db: AsyncSession,
    ) -> str:
        ...

    def get_suggestions(self) -> List[str]:
        return []


class ToolCapableBaseAgent(BaseAgent):
    system_prompt: str = ""
    skill_name: str = ""
    _skill_loader = None

    def __init__(self):
        self._context_injector = OntologyContextInjector()
        self._hallucination_guard = OntologyHallucinationGuard()
        self._permission_engine = OntologyPermissionEngine()
        self._last_oag_context: Optional[OAGContext] = None
        self._last_hallucination_check: Optional[HallucinationCheckResult] = None

    def load_skill(self) -> Optional[Skill]:
        if not self.skill_name or not self._skill_loader:
            return None
        return self._skill_loader.load_skill_detail(self.skill_name)

    def get_skill_instructions(self) -> str:
        skill = self.load_skill()
        if skill and skill.instructions:
            return skill.instructions
        return ""

    def get_skill_activated_objects(self) -> List[str]:
        skill = self.load_skill()
        if skill and skill.meta.activated_objects:
            return skill.meta.activated_objects
        return []

    def get_skill_activated_rules(self) -> List[str]:
        skill = self.load_skill()
        if skill and skill.meta.activated_rules:
            return skill.meta.activated_rules
        return []

    def get_skill_activated_behaviors(self) -> List[str]:
        skill = self.load_skill()
        if skill and skill.meta.activated_behaviors:
            return skill.meta.activated_behaviors
        return []

    def get_default_tools(self) -> List[Dict[str, Any]]:
        return []

    async def execute(
        self,
        messages: List[Dict[str, str]],
        context: Dict[str, Any],
        db: AsyncSession,
    ) -> str:
        skill_instructions = self.get_skill_instructions()
        if skill_instructions:
            base_prompt = skill_instructions
        else:
            base_prompt = self.system_prompt or f"你是 {self.name} Agent。"

        base_prompt = await self.inject_ontology_context(base_prompt, db=db)

        full_messages = [{"role": "system", "content": base_prompt}] + messages
        return await self.execute_with_tools(full_messages, context, db)

    async def execute_with_tools(
        self,
        messages: List[Dict[str, str]],
        context: Dict[str, Any],
        db: AsyncSession,
    ) -> str:
        return ""

    async def select_skills(self, user_input: str) -> List[Tuple[str, float, str]]:
        """根据用户输入动态选择匹配的Skills"""
        from ontology.scenes import match_scene_semantic
        return await match_scene_semantic(user_input, top_k=3)

    def merge_skill_contexts(self, skills: List[Optional[Skill]]) -> Tuple[List[str], List[str], List[str], str]:
        """合并多个Skill的激活项和指令"""
        all_objects: set = set()
        all_rules: set = set()
        all_behaviors: set = set()
        instructions_parts: List[str] = []
        for skill in skills:
            if skill and skill.meta:
                all_objects.update(skill.meta.activated_objects or [])
                all_rules.update(skill.meta.activated_rules or [])
                all_behaviors.update(skill.meta.activated_behaviors or [])
                if skill.instructions:
                    instructions_parts.append(f"### {skill.meta.name}\n{skill.instructions}")
        return list(all_objects), list(all_rules), list(all_behaviors), "\n\n".join(instructions_parts)

    async def inject_ontology_context(
        self,
        base_prompt: str,
        db: AsyncSession = None,
        activated_objects: Optional[List[str]] = None,
        activated_rules: Optional[List[str]] = None,
        activated_behaviors: Optional[List[str]] = None,
    ) -> str:
        # 如果传入了合并后的激活项，直接使用
        # 否则从当前Skill加载（兼容旧逻辑）
        if activated_objects is None:
            activated_objects = self.get_skill_activated_objects()
        if activated_rules is None:
            activated_rules = self.get_skill_activated_rules()
        if activated_behaviors is None:
            activated_behaviors = self.get_skill_activated_behaviors()
        if (activated_objects or activated_rules or activated_behaviors) and self._context_injector:
            context = await self._context_injector.build_context(
                target_object_ids=activated_objects or None,
                activated_rules=activated_rules or None,
                activated_behaviors=activated_behaviors or None,
                db=db,
            )
            self._last_oag_context = context
            formatted = self._context_injector.format_for_prompt(context)
            return f"{base_prompt}\n\n## 本体上下文\n{formatted}"
        elif self._context_injector:
            context = await self._context_injector.build_context(db=db)
            self._last_oag_context = context
            formatted = self._context_injector.format_for_prompt(context)
            return f"{base_prompt}\n\n## 本体上下文\n{formatted}"
        return base_prompt

    def check_hallucination(
        self,
        ai_output: str,
        ontology_data: Optional[Dict[str, Any]] = None,
    ) -> HallucinationCheckResult:
        context_blocks = len(self._last_oag_context.blocks) if self._last_oag_context else 0
        truncated_hard_rules = (
            list(self._last_oag_context.truncated_hard_rules)
            if self._last_oag_context and self._last_oag_context.truncated_hard_rules
            else None
        )
        self._last_hallucination_check = self._hallucination_guard.check(
            ai_output=ai_output,
            ontology_data=ontology_data,
            context_blocks=context_blocks,
            truncated_hard_rules=truncated_hard_rules,
        )
        return self._last_hallucination_check

    def check_ai_permission(
        self,
        scene: str,
        role_type: str,
        action_type: str,
    ) -> PermissionCheckResult:
        return self._permission_engine.check_ai_action(scene, role_type, action_type)

    def filter_response_by_permission(
        self,
        role_type: str,
        object_type: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        return self._permission_engine.filter_object_fields(role_type, object_type, data)

    async def reflect(
        self,
        tool_result: Dict[str, Any],
        original_query: str,
    ) -> ReflectionResult:
        """工具调用后自检：结果是否完整？是否需要补充调用？最多3轮。"""
        try:
            from utils.llm_client import get_llm_client
            llm = get_llm_client()
            if llm._mock_mode:
                return ReflectionResult(should_continue=False, reasoning="Mock模式跳过自检")

            import json
            prompt = (
                f"用户原始问题：{original_query}\n"
                f"工具返回结果：{json.dumps(tool_result, ensure_ascii=False, default=str)[:2000]}\n\n"
                f"请判断：\n"
                f"1) 结果是否完整回答了问题？（是/否）\n"
                f"2) 是否需要补充调用其他工具？（是/否，如需要请说明）\n"
                f"请用以下格式回答：完整|是否需要补充|补充说明"
            )
            messages = [{"role": "user", "content": prompt}]
            response = await llm.invoke(messages, temperature=0)
            content = response.content.strip()

            should_continue = False
            next_action = None
            reasoning = content

            if "否" in content[:5] or content.startswith("完整|否"):
                should_continue = False
            elif "是" in content[:5] or "需要补充" in content or "需要调用" in content:
                should_continue = True
                parts = content.split("|")
                if len(parts) >= 3:
                    next_action = parts[2].strip()

            return ReflectionResult(
                should_continue=should_continue,
                next_action=next_action,
                reasoning=reasoning,
            )
        except Exception as e:
            return ReflectionResult(should_continue=False, reasoning=f"自检异常: {e}")

    def get_last_oag_context(self) -> Optional[OAGContext]:
        return self._last_oag_context

    def get_last_hallucination_check(self) -> Optional[HallucinationCheckResult]:
        return self._last_hallucination_check


_AGENT_REGISTRY: Dict[str, type[BaseAgent]] = {}


def register(cls: type[BaseAgent]) -> type[BaseAgent]:
    _AGENT_REGISTRY[cls.name] = cls
    return cls


def get_all() -> Dict[str, type[BaseAgent]]:
    return _AGENT_REGISTRY.copy()


def get(name: str) -> Optional[type[BaseAgent]]:
    return _AGENT_REGISTRY.get(name)
