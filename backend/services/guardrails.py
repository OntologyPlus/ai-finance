from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from loguru import logger


_SENSITIVE_PATTERNS = [
    (r"\b\d{16,19}\b", "bank_account", "银行卡号"),
    (r"\b\d{6}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b", "id_card", "身份证号"),
    (r"\b1[3-9]\d{9}\b", "phone_number", "手机号"),
    (r"(?:password|密码|passwd|pwd)\s*[:=]\s*\S+", "password", "密码"),
    (r"(?:secret|密钥|token|key)\s*[:=]\s*\S+", "secret_key", "密钥"),
    (r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b", "email", "邮箱地址"),
]

_BLOCKED_KEYWORDS = [
    "绕过审批",
    "跳过审核",
    "伪造",
    "篡改数据",
    "删除审计日志",
    "提权",
    "越权",
]


# ── 间接 Prompt 注入模式 ──
# 业务自由文本字段（报销事由/预警响应说明等）被攻击者嵌入恶意指令，
# 后续 LLM 上下文拼接时会被模型执行。这是对抗"直接对话输入"之外的第二道防线。
# 模式选择原则：宁可漏报也不要错杀（severity=high 命中即阻断），因此只列高度可疑模式。
_INJECTION_PATTERNS: List[Tuple[str, str, str]] = [
    # 1. 显式覆盖/忽略系统指令
    (r"(?:ignore|disregard|forget|忽略|无视|不要\s*理会)\s*(?:the\s*)?(?:above|previous|all|prior|system|上面|之前|此前|系统|所有|前面|前述).*?(?:instructions?|rules?|prompts?|指令|规则|提示)", "instruction_override", "尝试覆盖/忽略系统指令"),
    (r"(?:忽略|无视|不要\s*理会|overlook).*?(?:hr[-_]?\d+|HR-\d+|规则\s*\d+|硬规则|合规|审计)", "rule_override", "尝试绕过硬规则/合规检查"),
    # 2. 越权诱导
    (r"(?:you\s*are\s*now|你现在是|从现在起你是|切换为|act\s*as).*?(?:admin|root|system|owner|管理员|超管|上帝)", "role_hijack", "尝试切换为高权限角色"),
    (r"(?:bypass|绕过|跳过|disable|关闭|turn\s*off).*?(?:approval|review|check|guard|审批|审核|检查|守卫)", "bypass_attempt", "尝试绕过审批/审查"),
    (r"(?:auto[-_]?approve|直接\s*通过|force\s*approve|强制\s*批准|approve\s*all|全部\s*批准)", "force_approval", "尝试强制通过审批"),
    # 3. 提示注入元标记（Anthropic/OpenAI/ChatML 标记伪造）
    (r"<\|im_start\|>|<\|im_end\|>|<<SYS>>|<</SYS>>|\\[INST\\]|\\[/INST\\]|\[SYSTEM\]|\[/SYSTEM\]", "prompt_marker", "伪造模型控制标记"),
    (r"\bSYSTEM\s*[:：]|\bASSISTANT\s*[:：]|\bUSER\s*[:：]\s*$", "role_marker", "伪造角色标记"),
    # 4. 输出/数据逃逸
    (r"(?:reveal|show|print|leak|expose|泄露|暴露|输出|显示).*?(?:system|hidden|secret|prompt|系统|隐藏|秘密|提示)", "data_exfil", "尝试获取系统/隐藏信息"),
    (r"(?:execute|run|eval|执行|运行)\s*(?:shell|command|bash|cmd|系统|命令)", "exec_attempt", "尝试执行系统命令"),
]


_PII_MASKS = {
    "bank_account": lambda m: m.group()[:4] + "****" + m.group()[-4:],
    "id_card": lambda m: m.group()[:3] + "***********" + m.group()[-4:],
    "phone_number": lambda m: m.group()[:3] + "****" + m.group()[-4:],
    "password": lambda m: re.sub(r"[:=]\s*\S+", ": ****", m.group()),
    "secret_key": lambda m: re.sub(r"[:=]\s*\S+", ": ****", m.group()),
    "email": lambda m: m.group()[0] + "****@" + m.group().split("@")[1],
}


class Guardrails:
    def __init__(self) -> None:
        self._compiled_patterns = [
            (re.compile(p, re.IGNORECASE), name, desc)
            for p, name, desc in _SENSITIVE_PATTERNS
        ]
        self._blocked_keywords = _BLOCKED_KEYWORDS
        self._compiled_injection = [
            (re.compile(p, re.IGNORECASE), name, desc)
            for p, name, desc in _INJECTION_PATTERNS
        ]

    def check(self, text: str) -> Tuple[bool, str, List[Dict[str, Any]]]:
        violations: List[Dict[str, Any]] = []
        masked_text = text

        for keyword in self._blocked_keywords:
            if keyword in text:
                violations.append({
                    "type": "blocked_keyword",
                    "keyword": keyword,
                    "severity": "high",
                    "message": f"包含被禁止的关键词：{keyword}",
                })

        for pattern, name, desc in self._compiled_patterns:
            matches = pattern.finditer(text)
            for match in matches:
                violations.append({
                    "type": "sensitive_info",
                    "category": name,
                    "description": desc,
                    "severity": "medium",
                    "position": match.start(),
                    "message": f"检测到敏感信息：{desc}",
                })
                if name in _PII_MASKS:
                    masked_text = masked_text[:match.start()] + _PII_MASKS[name](match) + masked_text[match.end():]

        safe = not any(v["severity"] == "high" for v in violations)

        if violations:
            logger.warning(f"Guardrails: detected {len(violations)} violations")

        return (safe, masked_text, violations)

    def check_injection(self, text: str) -> Tuple[bool, List[Dict[str, Any]]]:
        """检测间接 Prompt 注入。

        与 check() 的区别：
        - check_injection 不做 PII 脱敏（业务文本原本就要送入 LLM 上下文）
        - 只关心"是否携带注入攻击载荷"，命中即视为不安全

        用法：在把业务自由文本（如报销事由 description、预警响应说明 response）
        送入 LLM 上下文前先过这一道，避免攻击者通过业务字段劫持后续推理。
        """
        violations: List[Dict[str, Any]] = []
        for pattern, name, desc in self._compiled_injection:
            for match in pattern.finditer(text):
                violations.append({
                    "type": "prompt_injection",
                    "category": name,
                    "description": desc,
                    "severity": "high",
                    "position": match.start(),
                    "matched": match.group()[:80],
                    "message": f"检测到 Prompt 注入攻击：{desc}（片段：{match.group()[:40]!r}）",
                })

        safe = not violations
        if not safe:
            logger.warning(
                f"Guardrails.check_injection: detected {len(violations)} injection patterns"
            )
        return (safe, violations)
