from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from loguru import logger

from eval.runner import EvalRunner, EvalReport
from ontology.rules.hard_rules import HardRuleEngine
from ontology.rules.reasoning_rules import ReasoningRuleEngine
from ontology.rules.soft_rules import SoftRuleEngine


class EvolutionStatus(str, Enum):
    IDLE = "idle"
    OBSERVING = "observing"
    ANALYZING = "analyzing"
    HYPOTHESIZING = "hypothesizing"
    VERIFYING = "verifying"
    DEPLOYING = "deploying"
    ROLLING_BACK = "rolling_back"


class SafetyBoundary(str, Enum):
    HARD_RULE_IMMUTABLE = "hard_rule_immutable"
    SOFT_RULE_OUTPUT_PASS = "soft_rule_output_pass"
    REASONING_CANNOT_OVERRIDE_HARD = "reasoning_cannot_override_hard"
    CHANGE_REQUIRES_APPROVAL = "change_requires_approval"
    ALL_CHANGES_TRACEABLE = "all_changes_traceable"


@dataclass
class RuleCandidate:
    candidate_id: str
    rule_type: str
    rule_id: str
    change_type: str
    original_value: Any
    proposed_value: Any
    reasoning: str
    confidence: float
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class EvolutionSnapshot:
    snapshot_id: str
    timestamp: str
    soft_params: Dict[str, dict]
    reasoning_patterns: Dict[str, dict]
    confidence_scores: Dict[str, float]
    status: str = "active"


class EvolutionService:
    def __init__(self) -> None:
        self._status = EvolutionStatus.IDLE
        self._observations: List[dict] = []
        self._deviations: List[dict] = []
        self._candidates: List[RuleCandidate] = []
        self._snapshots: List[EvolutionSnapshot] = []
        self._deploy_log: List[dict] = []
        self._hard_engine = HardRuleEngine()
        self._soft_engine = SoftRuleEngine()
        self._reasoning_engine = ReasoningRuleEngine()
        self._eval_runner: Optional[EvalRunner] = None

    @property
    def status(self) -> EvolutionStatus:
        return self._status

    def observe(self, runtime_data: dict, user_feedback: Optional[dict] = None) -> List[dict]:
        self._status = EvolutionStatus.OBSERVING
        observations = []

        if runtime_data:
            observations.append({
                "type": "runtime_data",
                "timestamp": datetime.now().isoformat(),
                "data": runtime_data,
            })
            self._observations.append(observations[-1])

        if user_feedback:
            observations.append({
                "type": "user_feedback",
                "timestamp": datetime.now().isoformat(),
                "data": user_feedback,
            })
            self._observations.append(observations[-1])

        logger.info(f"Evolution: observed {len(observations)} data points")
        self._status = EvolutionStatus.IDLE
        return observations

    def analyze(self) -> List[dict]:
        self._status = EvolutionStatus.ANALYZING
        self._deviations = []

        for obs in self._observations[-100:]:
            data = obs.get("data", {})
            obs_type = obs.get("type", "")

            if obs_type == "runtime_data":
                execution_rate = data.get("execution_rate", 0)
                if execution_rate > 105:
                    self._deviations.append({
                        "type": "execution_rate_high",
                        "value": execution_rate,
                        "observation": obs,
                    })

                false_positive_rate = data.get("false_positive_rate", 0)
                if false_positive_rate > 0.3:
                    self._deviations.append({
                        "type": "high_false_positive",
                        "value": false_positive_rate,
                        "observation": obs,
                    })

            elif obs_type == "user_feedback":
                feedback_type = data.get("feedback_type", "")
                if feedback_type == "rule_too_sensitive":
                    self._deviations.append({
                        "type": "rule_sensitivity",
                        "rule_id": data.get("rule_id", ""),
                        "observation": obs,
                    })
                elif feedback_type == "rule_missing":
                    self._deviations.append({
                        "type": "rule_gap",
                        "description": data.get("description", ""),
                        "observation": obs,
                    })

        logger.info(f"Evolution: identified {len(self._deviations)} deviations")
        self._status = EvolutionStatus.IDLE
        return self._deviations

    def hypothesize(self) -> List[RuleCandidate]:
        self._status = EvolutionStatus.HYPOTHESIZING
        self._candidates = []
        candidate_id = 0

        for deviation in self._deviations:
            dev_type = deviation.get("type", "")

            if dev_type == "rule_sensitivity":
                rule_id = deviation.get("rule_id", "")
                if rule_id.startswith("SR-"):
                    current_params = self._soft_engine.get_all_params()
                    rule_params = current_params.get(rule_id, {})
                    threshold_key = None
                    for key in rule_params:
                        if "threshold" in key or "percentage" in key:
                            threshold_key = key
                            break

                    if threshold_key:
                        current_val = rule_params[threshold_key]
                        proposed_val = current_val * 1.05 if isinstance(current_val, (int, float)) else current_val
                        candidate_id += 1
                        self._candidates.append(RuleCandidate(
                            candidate_id=f"CAND-{candidate_id:03d}",
                            rule_type="soft",
                            rule_id=rule_id,
                            change_type="param_adjustment",
                            original_value=current_val,
                            proposed_value=proposed_val,
                            reasoning=f"规则{rule_id}误报率偏高，建议上调阈值{threshold_key}以降低灵敏度",
                            confidence=0.7,
                        ))

            elif dev_type == "execution_rate_high":
                candidate_id += 1
                self._candidates.append(RuleCandidate(
                    candidate_id=f"CAND-{candidate_id:03d}",
                    rule_type="reasoning",
                    rule_id="RR-004",
                    change_type="pattern_update",
                    original_value=None,
                    proposed_value={"s_curve_params": {"early_threshold": 0.35, "late_threshold": 0.65}},
                    reasoning="执行率持续偏高，建议调整S曲线参数以更早检测异常执行节奏",
                    confidence=0.6,
                ))

            elif dev_type == "rule_gap":
                candidate_id += 1
                self._candidates.append(RuleCandidate(
                    candidate_id=f"CAND-{candidate_id:03d}",
                    rule_type="reasoning",
                    rule_id="RR-NEW",
                    change_type="new_rule",
                    original_value=None,
                    proposed_value=deviation.get("description", ""),
                    reasoning=f"用户反馈存在规则缺口: {deviation.get('description', '')}",
                    confidence=0.5,
                ))

        logger.info(f"Evolution: generated {len(self._candidates)} candidates")
        self._status = EvolutionStatus.IDLE
        return self._candidates

    def verify(self, candidates: Optional[List[RuleCandidate]] = None) -> EvalReport:
        self._status = EvolutionStatus.VERIFYING
        targets = candidates or self._candidates

        if self._eval_runner is None:
            self._eval_runner = EvalRunner()

        report = self._eval_runner.run_all()

        for candidate in targets:
            if candidate.rule_type == "soft" and candidate.change_type == "param_adjustment":
                self._soft_engine.update_param(
                    candidate.rule_id,
                    self._find_threshold_key(candidate.rule_id),
                    candidate.proposed_value,
                    "evolution_verify",
                )
                verify_report = self._eval_runner.run_all()
                if verify_report.pass_rate < report.pass_rate:
                    self._soft_engine.update_param(
                        candidate.rule_id,
                        self._find_threshold_key(candidate.rule_id),
                        candidate.original_value,
                        "evolution_rollback_verify",
                    )
                    candidate.confidence *= 0.5

        logger.info(f"Evolution: verification complete, pass rate {report.pass_rate:.1f}%")
        self._status = EvolutionStatus.IDLE
        return report

    def deploy(self, candidates: Optional[List[RuleCandidate]] = None, gray_ratio: float = 1.0) -> bool:
        self._status = EvolutionStatus.DEPLOYING
        targets = candidates or self._candidates

        for boundary in SafetyBoundary:
            if not self._check_safety_boundary(boundary, targets):
                logger.warning(f"Evolution: safety boundary {boundary.value} violated, deployment aborted")
                self._status = EvolutionStatus.IDLE
                return False

        snapshot = self._create_snapshot()
        self._snapshots.append(snapshot)

        deployed = []
        for candidate in targets:
            if candidate.confidence < 0.5:
                logger.info(f"Evolution: skipping low-confidence candidate {candidate.candidate_id}")
                continue

            if candidate.rule_type == "soft" and candidate.change_type == "param_adjustment":
                threshold_key = self._find_threshold_key(candidate.rule_id)
                if threshold_key:
                    self._soft_engine.update_param(
                        candidate.rule_id,
                        threshold_key,
                        candidate.proposed_value,
                        f"evolution_deploy_{candidate.candidate_id}",
                    )
                    deployed.append(candidate)

            elif candidate.rule_type == "reasoning" and candidate.change_type == "pattern_update":
                self._reasoning_engine.learn_from_data(candidate.rule_id, candidate.proposed_value)
                deployed.append(candidate)

        self._deploy_log.append({
            "timestamp": datetime.now().isoformat(),
            "snapshot_id": snapshot.snapshot_id,
            "gray_ratio": gray_ratio,
            "deployed_candidates": [c.candidate_id for c in deployed],
        })

        logger.info(f"Evolution: deployed {len(deployed)} candidates (gray_ratio={gray_ratio})")
        self._status = EvolutionStatus.IDLE
        return True

    def rollback(self, snapshot_id: Optional[str] = None) -> bool:
        self._status = EvolutionStatus.ROLLING_BACK

        if not self._snapshots:
            logger.warning("Evolution: no snapshots available for rollback")
            self._status = EvolutionStatus.IDLE
            return False

        target_snapshot = None
        if snapshot_id:
            for s in self._snapshots:
                if s.snapshot_id == snapshot_id:
                    target_snapshot = s
                    break
        else:
            target_snapshot = self._snapshots[-1]

        if target_snapshot is None:
            logger.warning(f"Evolution: snapshot {snapshot_id} not found")
            self._status = EvolutionStatus.IDLE
            return False

        for rule_id, params in target_snapshot.soft_params.items():
            for param_name, param_value in params.items():
                self._soft_engine.update_param(
                    rule_id, param_name, param_value, f"evolution_rollback_{target_snapshot.snapshot_id}"
                )

        for rule_id, patterns in target_snapshot.reasoning_patterns.items():
            self._reasoning_engine.learn_from_data(rule_id, patterns)

        logger.info(f"Evolution: rolled back to snapshot {target_snapshot.snapshot_id}")
        self._status = EvolutionStatus.IDLE
        return True

    def get_snapshots(self) -> List[EvolutionSnapshot]:
        return self._snapshots.copy()

    def get_deploy_log(self) -> List[dict]:
        return self._deploy_log.copy()

    def _create_snapshot(self) -> EvolutionSnapshot:
        return EvolutionSnapshot(
            snapshot_id=f"SNAp-{len(self._snapshots) + 1:03d}",
            timestamp=datetime.now().isoformat(),
            soft_params=self._soft_engine.get_all_params(),
            reasoning_patterns={},
            confidence_scores={
                rule_id: self._reasoning_engine.get_confidence(rule_id)
                for rule_id in self._reasoning_engine.get_all_rules()
            },
        )

    def _check_safety_boundary(self, boundary: SafetyBoundary, candidates: List[RuleCandidate]) -> bool:
        if boundary == SafetyBoundary.HARD_RULE_IMMUTABLE:
            for c in candidates:
                if c.rule_type == "hard":
                    return False
        elif boundary == SafetyBoundary.SOFT_RULE_OUTPUT_PASS:
            pass
        elif boundary == SafetyBoundary.REASONING_CANNOT_OVERRIDE_HARD:
            for c in candidates:
                if c.rule_type == "reasoning" and c.change_type == "override_hard":
                    return False
        elif boundary == SafetyBoundary.CHANGE_REQUIRES_APPROVAL:
            for c in candidates:
                if c.confidence < 0.5:
                    pass
        elif boundary == SafetyBoundary.ALL_CHANGES_TRACEABLE:
            pass
        return True

    def _find_threshold_key(self, rule_id: str) -> str:
        params = self._soft_engine.get_all_params().get(rule_id, {})
        for key in params:
            if "threshold" in key or "percentage" in key or "ratio" in key:
                return key
        return ""
