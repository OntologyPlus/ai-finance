import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from ontology.rules.hard_rules import HardRuleEngine, RuleResult
from ontology.rules.reasoning_rules import ReasoningRuleEngine
from ontology.rules.soft_rules import SoftRuleEngine
from ontology.scenes import get_scene


class ReasoningStep(BaseModel):
    step: int
    rule_id: str
    rule_type: Literal["hard", "soft", "reasoning"]
    rule_desc: str
    reasoning: str
    output: str
    confidence: float


class ReasoningTrace(BaseModel):
    trace_id: str
    timestamp: str
    scene: str
    input: dict
    reasoning_chain: list[ReasoningStep] = Field(default_factory=list)
    conclusion: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)


_TRACE_STORE: list[ReasoningTrace] = []


class RuleEngine:
    def __init__(self, yaml_path: str | None = None) -> None:
        self.hard_engine = HardRuleEngine()
        self.soft_engine = SoftRuleEngine()
        self.reasoning_engine = ReasoningRuleEngine()
        if yaml_path:
            self.soft_engine.load_params(yaml_path)

    def execute_scene(self, scene_id: str, context: dict) -> ReasoningTrace:
        scene = get_scene(scene_id)
        if scene is None:
            return ReasoningTrace(
                trace_id=str(uuid.uuid4()),
                timestamp=datetime.now().isoformat(),
                scene=scene_id,
                input=context,
                reasoning_chain=[],
                conclusion={"error": f"场景{scene_id}不存在"},
                metadata={},
            )

        reasoning_chain: list[ReasoningStep] = []
        step = 1
        any_blocked = False

        for rule_id in scene.activated_rules:
            result = self._execute_single_rule(rule_id, context)
            if result is None:
                continue

            reasoning_chain.append(ReasoningStep(
                step=step,
                rule_id=result.rule_id,
                rule_type=result.rule_type,
                rule_desc=result.rule_desc,
                reasoning=result.reasoning,
                output=result.output,
                confidence=result.confidence,
            ))
            step += 1

            if result.output == "BLOCK":
                any_blocked = True

        conclusion = {
            "scene": scene.name,
            "total_rules_checked": len(reasoning_chain),
            "blocked": any_blocked,
            "hard_rules_passed": sum(1 for s in reasoning_chain if s.rule_type == "hard" and s.output == "PASS"),
            "hard_rules_blocked": sum(1 for s in reasoning_chain if s.rule_type == "hard" and s.output == "BLOCK"),
            "soft_rules_flagged": sum(1 for s in reasoning_chain if s.rule_type == "soft" and not s.output == "PASS"),
            "reasoning_rules_applied": sum(1 for s in reasoning_chain if s.rule_type == "reasoning"),
            "min_confidence": min((s.confidence for s in reasoning_chain), default=1.0),
        }

        trace = ReasoningTrace(
            trace_id=str(uuid.uuid4()),
            timestamp=datetime.now().isoformat(),
            scene=scene_id,
            input=context,
            reasoning_chain=reasoning_chain,
            conclusion=conclusion,
            metadata={"scene_name": scene.name, "stage": scene.stage},
        )

        self.record_trace(trace)
        return trace

    def execute_rule(self, rule_id: str, context: dict) -> Optional[RuleResult]:
        return self._execute_single_rule(rule_id, context)

    def get_rules_for_scene(self, scene_id: str) -> list[str]:
        scene = get_scene(scene_id)
        if scene is None:
            return []
        return scene.activated_rules.copy()

    def record_trace(self, trace: ReasoningTrace) -> None:
        _TRACE_STORE.append(trace)

    def get_traces(self, scene_id: str | None = None, limit: int = 100) -> list[ReasoningTrace]:
        if scene_id:
            filtered = [t for t in _TRACE_STORE if t.scene == scene_id]
        else:
            filtered = _TRACE_STORE
        return filtered[-limit:]

    def _execute_single_rule(self, rule_id: str, context: dict) -> Optional[RuleResult]:
        if rule_id.startswith("HR-"):
            return self.hard_engine.execute(rule_id, context)
        elif rule_id.startswith("SR-"):
            return self.soft_engine.execute(rule_id, context)
        elif rule_id.startswith("RR-"):
            return self.reasoning_engine.execute(rule_id, context)
        return None
