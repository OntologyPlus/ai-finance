from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from loguru import logger

from ontology.rules.rule_engine import RuleEngine


@dataclass
class EvalResult:
    case_id: str
    category: str
    description: str
    passed: bool
    expected: Any
    actual: Any
    rule_id: str = ""
    reasoning: str = ""
    execution_time_ms: float = 0.0
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "category": self.category,
            "description": self.description,
            "passed": self.passed,
            "expected": str(self.expected),
            "actual": str(self.actual),
            "rule_id": self.rule_id,
            "reasoning": self.reasoning,
            "execution_time_ms": self.execution_time_ms,
            "error": self.error,
        }


@dataclass
class EvalReport:
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    total_cases: int = 0
    passed_cases: int = 0
    failed_cases: int = 0
    error_cases: int = 0
    pass_rate: float = 0.0
    results: List[EvalResult] = field(default_factory=list)
    category_summary: Dict[str, Dict[str, int]] = field(default_factory=dict)

    def add_result(self, result: EvalResult) -> None:
        self.results.append(result)
        self.total_cases += 1
        if result.error:
            self.error_cases += 1
        elif result.passed:
            self.passed_cases += 1
        else:
            self.failed_cases += 1
        self.pass_rate = (self.passed_cases / self.total_cases * 100) if self.total_cases > 0 else 0.0

        cat = result.category
        if cat not in self.category_summary:
            self.category_summary[cat] = {"total": 0, "passed": 0, "failed": 0, "errors": 0}
        self.category_summary[cat]["total"] += 1
        if result.error:
            self.category_summary[cat]["errors"] += 1
        elif result.passed:
            self.category_summary[cat]["passed"] += 1
        else:
            self.category_summary[cat]["failed"] += 1

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "failed_cases": self.failed_cases,
            "error_cases": self.error_cases,
            "pass_rate": round(self.pass_rate, 2),
            "category_summary": self.category_summary,
            "results": [r.to_dict() for r in self.results],
        }

    def to_json(self, path: str | Path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    def print_summary(self) -> None:
        logger.info("=" * 60)
        logger.info(f"Eval Report - {self.timestamp}")
        logger.info(f"Total: {self.total_cases} | Passed: {self.passed_cases} | Failed: {self.failed_cases} | Errors: {self.error_cases}")
        logger.info(f"Pass Rate: {self.pass_rate:.1f}%")
        logger.info("-" * 60)
        for cat, summary in self.category_summary.items():
            rate = (summary["passed"] / summary["total"] * 100) if summary["total"] > 0 else 0
            logger.info(f"  {cat}: {summary['passed']}/{summary['total']} ({rate:.1f}%)")
        logger.info("=" * 60)


class EvalRunner:
    def __init__(self, yaml_path: str | Path | None = None) -> None:
        self._rule_engine = RuleEngine()
        self._cases: List[dict] = []
        self._baseline: dict = {}
        if yaml_path:
            self.load_cases(yaml_path)
        else:
            default_path = Path(__file__).parent / "eval_cases.yaml"
            if default_path.exists():
                self.load_cases(default_path)

    def load_cases(self, path: str | Path) -> None:
        path = Path(path)
        if not path.exists():
            logger.warning(f"Eval cases file not found: {path}")
            return
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        self._cases = data.get("cases", [])
        logger.info(f"Loaded {len(self._cases)} eval cases from {path}")

    def load_baseline(self, path: str | Path | None = None) -> dict:
        if path is None:
            path = Path(__file__).parent / "baseline.json"
        path = Path(path)
        if not path.exists():
            logger.warning(f"Baseline file not found: {path}")
            return {}
        with open(path, "r", encoding="utf-8") as f:
            self._baseline = json.load(f)
        return self._baseline

    def run_case(self, case_id: str) -> EvalResult:
        import time

        case = None
        for c in self._cases:
            if c.get("case_id") == case_id:
                case = c
                break

        if case is None:
            return EvalResult(
                case_id=case_id,
                category="unknown",
                description="Case not found",
                passed=False,
                expected=None,
                actual=None,
                error=f"Case {case_id} not found",
            )

        start = time.time()
        try:
            context = case.get("context", {})
            rule_id = case.get("rule_id", "")
            expected_output = case.get("expected", {})
            category = case.get("category", "general")

            if rule_id:
                result = self._rule_engine.execute_rule(rule_id, context)
                if result is None:
                    actual = {"output": "RULE_NOT_FOUND"}
                else:
                    actual = {
                        "passed": result.passed,
                        "output": result.output,
                        "reasoning": result.reasoning,
                        "confidence": result.confidence,
                    }
            else:
                scene_id = case.get("scene_id", "")
                if scene_id:
                    trace = self._rule_engine.execute_scene(scene_id, context)
                    actual = {
                        "conclusion": trace.conclusion,
                        "blocked": trace.conclusion.get("blocked", False),
                    }
                else:
                    actual = {"output": "NO_RULE_OR_SCENE"}

            passed = self._check_expected(actual, expected_output)
            elapsed = (time.time() - start) * 1000

            return EvalResult(
                case_id=case_id,
                category=category,
                description=case.get("description", ""),
                passed=passed,
                expected=expected_output,
                actual=actual,
                rule_id=rule_id,
                reasoning=str(actual.get("reasoning", "")),
                execution_time_ms=elapsed,
            )
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return EvalResult(
                case_id=case_id,
                category=case.get("category", "unknown"),
                description=case.get("description", ""),
                passed=False,
                expected=case.get("expected", {}),
                actual=None,
                rule_id=case.get("rule_id", ""),
                error=str(e),
                execution_time_ms=elapsed,
            )

    def run_all(self, category: str | None = None) -> EvalReport:
        report = EvalReport()

        cases_to_run = self._cases
        if category:
            cases_to_run = [c for c in self._cases if c.get("category") == category]

        logger.info(f"Running {len(cases_to_run)} eval cases" + (f" (category: {category})" if category else ""))

        for case in cases_to_run:
            case_id = case.get("case_id", "")
            result = self.run_case(case_id)
            report.add_result(result)

            status = "PASS" if result.passed else "FAIL"
            if result.error:
                status = "ERROR"
            logger.debug(f"  [{status}] {case_id}: {result.description}")

        report.print_summary()
        return report

    def check_regression(self, report: EvalReport) -> bool:
        if not self._baseline:
            logger.warning("No baseline loaded, cannot check regression")
            return False

        baseline_rate = self._baseline.get("pass_rate", 0)
        has_regression = report.pass_rate < baseline_rate

        if has_regression:
            logger.warning(
                f"Regression detected! Current pass rate {report.pass_rate:.1f}% < baseline {baseline_rate:.1f}%"
            )
            for result in report.results:
                if not result.passed:
                    baseline_result = self._baseline.get("results", {}).get(result.case_id)
                    if baseline_result and baseline_result.get("passed"):
                        logger.warning(f"  Regressed case: {result.case_id}")
        else:
            logger.info(f"No regression. Current {report.pass_rate:.1f}% >= baseline {baseline_rate:.1f}%")

        return has_regression

    def save_baseline(self, report: EvalReport, path: str | Path | None = None) -> None:
        if path is None:
            path = Path(__file__).parent / "baseline.json"
        baseline = {
            "timestamp": report.timestamp,
            "pass_rate": round(report.pass_rate, 2),
            "total_cases": report.total_cases,
            "results": {r.case_id: {"passed": r.passed} for r in report.results},
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(baseline, f, ensure_ascii=False, indent=2)
        logger.info(f"Baseline saved to {path}")

    def _check_expected(self, actual: dict, expected: dict) -> bool:
        for key, expected_val in expected.items():
            actual_val = actual.get(key)
            if isinstance(expected_val, dict) and isinstance(actual_val, dict):
                if not self._check_expected(actual_val, expected_val):
                    return False
            elif actual_val != expected_val:
                return False
        return True
