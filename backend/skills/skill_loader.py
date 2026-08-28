from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from loguru import logger
from pydantic import BaseModel, Field


class SkillMeta(BaseModel):
    name: str
    description: str
    intent: str
    activation_condition: str = ""
    activated_objects: List[str] = Field(default_factory=list)
    activated_rules: List[str] = Field(default_factory=list)
    activated_behaviors: List[str] = Field(default_factory=list)
    skill_dir: str = ""


class Skill(BaseModel):
    meta: SkillMeta
    instructions: str = ""
    resources: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"arbitrary_types_allowed": True}


class SkillLoader:
    def __init__(self) -> None:
        self._skills: Dict[str, SkillMeta] = {}
        self._loaded_details: Dict[str, Skill] = {}

    def load_skills(self, skills_dir: str) -> List[SkillMeta]:
        if not os.path.isdir(skills_dir):
            logger.warning(f"Skills directory not found: {skills_dir}")
            return []

        loaded = []
        for entry in sorted(os.listdir(skills_dir)):
            skill_path = os.path.join(skills_dir, entry)
            if not os.path.isdir(skill_path):
                continue

            skill_md = os.path.join(skill_path, "SKILL.md")
            if not os.path.isfile(skill_md):
                continue

            try:
                meta = self._parse_l1_metadata(skill_md, skill_path)
                if meta:
                    self._skills[meta.name] = meta
                    loaded.append(meta)
                    logger.debug(f"SkillLoader: loaded L1 metadata for '{meta.name}'")
            except Exception as e:
                logger.error(f"SkillLoader: failed to parse {skill_md}: {e}")

        logger.info(f"SkillLoader: loaded {len(loaded)} skills from {skills_dir}")
        return loaded

    def load_skill_detail(self, skill_name: str) -> Optional[Skill]:
        """L2: 加载Skill完整指令（延迟加载resources）"""
        if skill_name in self._loaded_details:
            return self._loaded_details[skill_name]

        meta = self._skills.get(skill_name)
        if meta is None:
            return None

        skill_md = os.path.join(meta.skill_dir, "SKILL.md")
        if not os.path.isfile(skill_md):
            return None

        try:
            with open(skill_md, "r", encoding="utf-8") as f:
                content = f.read()

            frontmatter, body = self._split_frontmatter(content)

            # L2: 只加载指令，不预加载resources（延迟到L3）
            skill = Skill(
                meta=meta,
                instructions=body.strip(),
                resources={},  # L3按需加载
            )
            self._loaded_details[skill_name] = skill
            return skill

        except Exception as e:
            logger.error(f"SkillLoader: failed to load detail for '{skill_name}': {e}")
            return None

    def load_skill_l3_resource(self, skill_name: str, resource_name: str) -> Optional[str]:
        """L3: 按需加载Skill的references/目录中的特定资源文件"""
        meta = self._skills.get(skill_name)
        if not meta or not meta.skill_dir:
            return None

        # 先检查references/子目录
        resource_path = os.path.join(meta.skill_dir, "references", resource_name)
        if os.path.isfile(resource_path):
            try:
                with open(resource_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                logger.error(f"SkillLoader: failed to load L3 resource '{resource_name}': {e}")
                return None

        # 再检查skill根目录（兼容无references/子目录的旧结构）
        resource_path = os.path.join(meta.skill_dir, resource_name)
        if os.path.isfile(resource_path):
            try:
                with open(resource_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                pass

        return None

    def list_l3_resources(self, skill_name: str) -> List[str]:
        """列出Skill可用的L3资源文件名"""
        meta = self._skills.get(skill_name)
        if not meta or not meta.skill_dir:
            return []

        resources = []
        # 检查references/子目录
        ref_dir = os.path.join(meta.skill_dir, "references")
        if os.path.isdir(ref_dir):
            for fname in os.listdir(ref_dir):
                fpath = os.path.join(ref_dir, fname)
                if os.path.isfile(fpath):
                    resources.append(fname)

        # 兼容：检查skill根目录的非SKILL.md文件
        if not resources:
            for fname in os.listdir(meta.skill_dir):
                fpath = os.path.join(meta.skill_dir, fname)
                if os.path.isfile(fpath) and fname != "SKILL.md":
                    resources.append(fname)

        return resources

    def find_by_intent(self, intent: str) -> Optional[Skill]:
        for meta in self._skills.values():
            if meta.intent == intent:
                return self.load_skill_detail(meta.name)
        return None

    def get_all_skills(self) -> List[SkillMeta]:
        return list(self._skills.values())

    def _parse_l1_metadata(self, skill_md_path: str, skill_dir: str) -> Optional[SkillMeta]:
        with open(skill_md_path, "r", encoding="utf-8") as f:
            content = f.read()

        frontmatter, _ = self._split_frontmatter(content)
        if not frontmatter:
            return None

        meta_dict = self._parse_yaml_frontmatter(frontmatter)

        for list_key in ("activated_objects", "activated_rules", "activated_behaviors"):
            val = meta_dict.get(list_key, [])
            if isinstance(val, str):
                meta_dict[list_key] = []

        return SkillMeta(
            name=meta_dict.get("name", os.path.basename(skill_dir)),
            description=meta_dict.get("description", ""),
            intent=meta_dict.get("intent", ""),
            activation_condition=meta_dict.get("activation_condition", ""),
            activated_objects=meta_dict.get("activated_objects", []),
            activated_rules=meta_dict.get("activated_rules", []),
            activated_behaviors=meta_dict.get("activated_behaviors", []),
            skill_dir=skill_dir,
        )

    def _split_frontmatter(self, content: str) -> tuple[str, str]:
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                return parts[1].strip(), parts[2].strip()
        return "", content

    def _parse_yaml_frontmatter(self, yaml_str: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        current_key = None
        current_list: List[str] = []
        in_list = False

        for line in yaml_str.split("\n"):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            if stripped.startswith("- ") and in_list and current_key:
                current_list.append(stripped[2:].strip().strip('"').strip("'"))
                continue

            if in_list and current_key and current_list:
                result[current_key] = current_list
                current_list = []
                in_list = False

            if ":" in stripped:
                key, _, value = stripped.partition(":")
                key = key.strip()
                value = value.strip().strip('"').strip("'")

                if value:
                    result[key] = value
                    in_list = False
                else:
                    current_key = key
                    current_list = []
                    in_list = True

        if in_list and current_key and current_list:
            result[current_key] = current_list

        return result
