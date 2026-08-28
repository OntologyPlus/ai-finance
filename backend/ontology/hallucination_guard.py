from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from ontology.objects import get_object, get_all_objects
from ontology.relations import get_all_relations


class VerificationResult(BaseModel):
    passed: bool
    strategy: str
    detail: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class HallucinationCheckResult(BaseModel):
    is_safe: bool
    checks: List[VerificationResult] = Field(default_factory=list)
    overall_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    should_refuse: bool = False
    refusal_reason: Optional[str] = None


class OntologyHallucinationGuard:
    def __init__(self, min_confidence: float = 0.6):
        self.min_confidence = min_confidence
        self._object_ids = set()
        self._relation_ids = set()
        self._object_names = {}
        self._relation_names = {}
        self._refresh_cache()

    def _refresh_cache(self) -> None:
        for obj_id, obj in get_all_objects().items():
            self._object_ids.add(obj_id)
            self._object_names[obj.name] = obj_id
        for rel_id, rel in get_all_relations().items():
            self._relation_ids.add(rel_id)
            self._relation_names[rel.name] = rel_id

    def verify_fact_anchoring(
        self, ai_output: str
    ) -> VerificationResult:
        source_pattern = r'(obj_\w+|rel_\w+|HR-\d+|SR-\d+|RR-\d+)'
        found_sources = re.findall(source_pattern, ai_output)

        if not found_sources:
            return VerificationResult(
                passed=False,
                strategy="fact_anchoring",
                detail="AI输出未标注任何Ontology来源标识，无法验证事实锚定",
                confidence=0.3,
            )

        valid_sources = []
        for src in found_sources:
            if src in self._object_ids or src in self._relation_ids:
                valid_sources.append(src)

        if not valid_sources:
            return VerificationResult(
                passed=False,
                strategy="fact_anchoring",
                detail=f"AI输出引用的来源{found_sources}在Ontology中不存在",
                confidence=0.2,
            )

        ratio = len(valid_sources) / len(found_sources) if found_sources else 0
        return VerificationResult(
            passed=ratio >= 0.8,
            strategy="fact_anchoring",
            detail=f"事实锚定率{ratio:.0%}({len(valid_sources)}/{len(found_sources)}来源有效)",
            confidence=ratio,
        )

    def verify_numerical_claims(
        self, ai_output: str, ontology_data: Dict[str, Any]
    ) -> VerificationResult:
        # Extract numerical claims with surrounding context keywords
        claim_pattern = r'([\u4e00-\u9fff\w]*)\s*(\d+\.?\d*)\s*(万|元|%|万元)'
        claims = re.findall(claim_pattern, ai_output)

        if not claims:
            return VerificationResult(
                passed=True,
                strategy="numerical_verification",
                detail="AI输出未包含可验证的数值声明",
                confidence=1.0,
            )

        verified = 0
        unverified = 0
        total = len(claims)
        for context_word, value_str, unit in claims:
            try:
                value = float(value_str)
                matched = False

                # Try to find a matching field by context keyword
                for field_name, field_value in ontology_data.items():
                    if not isinstance(field_value, (int, float)):
                        continue

                    # Check if context keyword matches field name
                    context_lower = context_word.lower()
                    field_lower = field_name.lower()
                    keyword_match = (
                        context_lower and (
                            context_lower in field_lower
                            or field_lower in context_lower
                            or any(kw in field_lower for kw in context_lower.split() if len(kw) > 1)
                        )
                    )

                    if keyword_match or not context_lower:
                        if unit == "万" or unit == "万元":
                            compare_value = field_value / 10000
                        elif unit == "%":
                            compare_value = field_value * 100
                        else:
                            compare_value = field_value

                        # Tighter tolerance: 5% for keyword-matched, 2% for no context
                        tolerance = 0.05 if keyword_match else 0.02
                        if abs(value - compare_value) / max(abs(compare_value), 1) < tolerance:
                            verified += 1
                            matched = True
                            break

                if not matched:
                    unverified += 1
            except (ValueError, ZeroDivisionError):
                unverified += 1

        ratio = verified / total if total > 0 else 1.0
        detail = f"数值验证率{ratio:.0%}({verified}/{total}个数值可验证"
        if unverified > 0:
            detail += f", {unverified}个无法验证"
        detail += ")"

        return VerificationResult(
            passed=ratio >= 0.7,
            strategy="numerical_verification",
            detail=detail,
            confidence=ratio,
        )

    def verify_relation_claims(
        self, ai_output: str
    ) -> VerificationResult:
        relation_claims = []
        for rel_name, rel_id in self._relation_names.items():
            if rel_name in ai_output:
                relation_claims.append(rel_name)

        if not relation_claims:
            return VerificationResult(
                passed=True,
                strategy="relation_verification",
                detail="AI输出未声称任何Ontology关系",
                confidence=1.0,
            )

        all_valid = True
        for claim in relation_claims:
            if claim not in self._relation_names:
                all_valid = False
                break

        return VerificationResult(
            passed=all_valid,
            strategy="relation_verification",
            detail=f"关系验证{'通过' if all_valid else '失败'}: {', '.join(relation_claims)}",
            confidence=1.0 if all_valid else 0.3,
        )

    def check_context_sufficiency(
        self,
        ai_output: str,
        context_blocks: int,
        truncated_hard_rules: Optional[List[str]] = None,
    ) -> VerificationResult:
        truncated_hard_rules = truncated_hard_rules or []
        if truncated_hard_rules:
            return VerificationResult(
                passed=False,
                strategy="context_sufficiency",
                detail=(
                    f"上下文窗口裁剪导致 {len(truncated_hard_rules)} 条硬规则(HR-*)未注入: "
                    f"{', '.join(truncated_hard_rules)}。合规底线被静默漏检风险，AI 输出需重新走完整上下文。"
                ),
                confidence=0.3,
            )

        if context_blocks == 0:
            return VerificationResult(
                passed=False,
                strategy="context_sufficiency",
                detail="无Ontology上下文注入，AI输出缺乏事实基础",
                confidence=0.1,
            )

        if context_blocks < 2:
            return VerificationResult(
                passed=True,
                strategy="context_sufficiency",
                detail=f"上下文注入不足({context_blocks}块)，建议补充更多Ontology上下文",
                confidence=0.5,
            )

        return VerificationResult(
            passed=True,
            strategy="context_sufficiency",
            detail=f"上下文注入充分({context_blocks}块)",
            confidence=0.9,
        )

    def check(
        self,
        ai_output: str,
        ontology_data: Optional[Dict[str, Any]] = None,
        context_blocks: int = 0,
        truncated_hard_rules: Optional[List[str]] = None,
    ) -> HallucinationCheckResult:
        checks = []

        checks.append(self.verify_fact_anchoring(ai_output))

        if ontology_data:
            checks.append(self.verify_numerical_claims(ai_output, ontology_data))

        checks.append(self.verify_relation_claims(ai_output))

        checks.append(
            self.check_context_sufficiency(ai_output, context_blocks, truncated_hard_rules)
        )

        all_passed = all(c.passed for c in checks)
        avg_confidence = sum(c.confidence for c in checks) / len(checks) if checks else 0.0

        # 硬规则被裁：合规底线被突破，整体视为不安全（即使其他检查通过）
        hard_rule_truncated = bool(truncated_hard_rules)

        should_refuse = False
        refusal_reason = None
        if avg_confidence < self.min_confidence:
            should_refuse = True
            failed_checks = [c for c in checks if not c.passed]
            refusal_reason = f"AI输出置信度不足({avg_confidence:.0%}<{self.min_confidence:.0%})，失败项: {', '.join(c.strategy for c in failed_checks)}"
        elif hard_rule_truncated:
            should_refuse = True
            refusal_reason = (
                f"合规风险：上下文裁剪导致 {len(truncated_hard_rules)} 条硬规则(HR-*)未注入 "
                f"({', '.join(truncated_hard_rules)})，AI 输出可能在合规底线（HR-*）外推理，"
                f"请重新发起请求或精简目标对象后再试。"
            )

        return HallucinationCheckResult(
            is_safe=all_passed and not should_refuse,
            checks=checks,
            overall_confidence=avg_confidence,
            should_refuse=should_refuse,
            refusal_reason=refusal_reason,
        )
