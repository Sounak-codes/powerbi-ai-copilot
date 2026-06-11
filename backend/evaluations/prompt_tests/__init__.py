"""
Prompt testing framework.

Tests prompt templates against defined test cases and evaluates
output quality using configurable scoring criteria.
"""
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
import time

from config import get_logger
from llm.providers.provider_factory import ProviderFactory

logger = get_logger(__name__)


@dataclass
class PromptTestCase:
    """A single test case for a prompt template."""

    case_id: str
    name: str
    input_variables: Dict[str, str]
    expected_content: Optional[List[str]] = None  # Keywords expected in output
    forbidden_content: Optional[List[str]] = None  # Keywords that should NOT appear
    min_length: int = 0
    max_length: int = 0  # 0 means no limit
    quality_criteria: Dict[str, float] = field(default_factory=dict)


@dataclass
class PromptTestResult:
    """Result of a single prompt test."""

    case_id: str
    name: str
    passed: bool
    score: float = 0.0
    output: str = ""
    latency_ms: float = 0.0
    checks: Dict[str, bool] = field(default_factory=dict)
    feedback: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "name": self.name,
            "passed": self.passed,
            "score": round(self.score, 4),
            "output_preview": self.output[:200] if self.output else "",
            "latency_ms": round(self.latency_ms, 2),
            "checks": self.checks,
            "feedback": self.feedback,
        }


@dataclass
class PromptTestReport:
    """Complete prompt test run report."""

    prompt_name: str
    prompt_template: str
    timestamp: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    avg_score: float
    avg_latency_ms: float
    results: List[PromptTestResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.passed_cases / self.total_cases if self.total_cases > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt_name": self.prompt_name,
            "prompt_template_preview": self.prompt_template[:200],
            "timestamp": self.timestamp,
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "failed_cases": self.failed_cases,
            "pass_rate": round(self.pass_rate, 4),
            "avg_score": round(self.avg_score, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "results": [r.to_dict() for r in self.results],
        }


class PromptTester:
    """
    Tests prompt templates against test cases and evaluates output quality.

    Supports keyword presence/absence checks, length constraints,
    and custom quality scoring functions.
    """

    def __init__(self):
        self._provider = ProviderFactory.get_default_provider()
        self._quality_scorers: Dict[str, Callable[[str], float]] = {}
        self._register_default_scorers()

    def _register_default_scorers(self) -> None:
        """Register default quality scoring functions."""
        self._quality_scorers["coherence"] = self._score_coherence
        self._quality_scorers["conciseness"] = self._score_conciseness
        self._quality_scorers["completeness"] = self._score_completeness

    def register_scorer(
        self,
        name: str,
        scorer: Callable[[str], float],
    ) -> None:
        """
        Register a custom quality scorer.

        Args:
            name: Name of the scoring criterion.
            scorer: Function that takes output text and returns 0.0-1.0 score.
        """
        self._quality_scorers[name] = scorer
        logger.debug(f"Quality scorer registered: {name}")

    async def test_prompt(
        self,
        prompt_name: str,
        prompt_template: str,
        test_cases: List[PromptTestCase],
        system_prompt: Optional[str] = None,
        pass_threshold: float = 0.6,
    ) -> PromptTestReport:
        """
        Test a prompt template against multiple test cases.

        Args:
            prompt_name: Identifier for the prompt being tested.
            prompt_template: The prompt template with {variable} placeholders.
            test_cases: List of test cases to evaluate.
            system_prompt: Optional system prompt to use.
            pass_threshold: Minimum score to consider a test passed.

        Returns:
            PromptTestReport with all results and aggregate metrics.
        """
        logger.info(f"Testing prompt '{prompt_name}' with {len(test_cases)} cases")

        results: List[PromptTestResult] = []

        for case in test_cases:
            result = await self._run_test_case(
                prompt_template, case, system_prompt, pass_threshold
            )
            results.append(result)

        # Aggregate
        passed = sum(1 for r in results if r.passed)
        scores = [r.score for r in results]
        latencies = [r.latency_ms for r in results]

        report = PromptTestReport(
            prompt_name=prompt_name,
            prompt_template=prompt_template,
            timestamp=datetime.utcnow().isoformat() + "Z",
            total_cases=len(results),
            passed_cases=passed,
            failed_cases=len(results) - passed,
            avg_score=sum(scores) / len(scores) if scores else 0.0,
            avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0.0,
            results=results,
        )

        logger.info(
            f"Prompt test complete: '{prompt_name}' - "
            f"{passed}/{len(results)} passed, avg score {report.avg_score:.3f}"
        )
        return report

    async def _run_test_case(
        self,
        prompt_template: str,
        case: PromptTestCase,
        system_prompt: Optional[str],
        pass_threshold: float,
    ) -> PromptTestResult:
        """Run a single test case."""
        start_time = time.perf_counter()
        checks: Dict[str, bool] = {}
        feedback: List[str] = []

        try:
            # Format prompt with test case variables
            prompt = prompt_template.format(**case.input_variables)

            # Generate response
            kwargs: Dict[str, Any] = {"prompt": prompt}
            if system_prompt:
                kwargs["system_prompt"] = system_prompt

            output = await self._provider.generate(**kwargs)
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            # Run checks
            score = self._evaluate_output(output, case, checks, feedback)
            passed = score >= pass_threshold

            return PromptTestResult(
                case_id=case.case_id,
                name=case.name,
                passed=passed,
                score=score,
                output=output,
                latency_ms=elapsed_ms,
                checks=checks,
                feedback=feedback,
            )

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"Test case failed: {case.case_id} - {e}")
            return PromptTestResult(
                case_id=case.case_id,
                name=case.name,
                passed=False,
                score=0.0,
                output="",
                latency_ms=elapsed_ms,
                checks={"execution": False},
                feedback=[f"Execution error: {str(e)}"],
            )

    def _evaluate_output(
        self,
        output: str,
        case: PromptTestCase,
        checks: Dict[str, bool],
        feedback: List[str],
    ) -> float:
        """Evaluate output against test case criteria."""
        scores: List[float] = []
        output_lower = output.lower()

        # Check expected content presence
        if case.expected_content:
            found = 0
            for keyword in case.expected_content:
                present = keyword.lower() in output_lower
                checks[f"contains_{keyword}"] = present
                if present:
                    found += 1
                else:
                    feedback.append(f"Missing expected content: '{keyword}'")

            content_score = found / len(case.expected_content)
            scores.append(content_score)

        # Check forbidden content absence
        if case.forbidden_content:
            violations = 0
            for keyword in case.forbidden_content:
                present = keyword.lower() in output_lower
                checks[f"excludes_{keyword}"] = not present
                if present:
                    violations += 1
                    feedback.append(f"Contains forbidden content: '{keyword}'")

            forbidden_score = 1.0 - (violations / len(case.forbidden_content))
            scores.append(forbidden_score)

        # Check length constraints
        if case.min_length > 0:
            meets_min = len(output) >= case.min_length
            checks["min_length"] = meets_min
            if not meets_min:
                feedback.append(f"Output too short: {len(output)} < {case.min_length}")
            scores.append(1.0 if meets_min else 0.3)

        if case.max_length > 0:
            meets_max = len(output) <= case.max_length
            checks["max_length"] = meets_max
            if not meets_max:
                feedback.append(f"Output too long: {len(output)} > {case.max_length}")
            scores.append(1.0 if meets_max else 0.5)

        # Run quality scorers
        for criterion, weight in case.quality_criteria.items():
            scorer = self._quality_scorers.get(criterion)
            if scorer:
                criterion_score = scorer(output)
                checks[f"quality_{criterion}"] = criterion_score >= 0.5
                scores.append(criterion_score * weight)

        # Non-empty output baseline
        if not output.strip():
            return 0.0

        return sum(scores) / len(scores) if scores else 0.5

    def _score_coherence(self, text: str) -> float:
        """Score text coherence (sentence structure and flow)."""
        sentences = text.split(".")
        valid_sentences = [s.strip() for s in sentences if len(s.strip()) > 5]

        if not valid_sentences:
            return 0.0

        # Simple heuristic: ratio of well-formed sentences
        return min(1.0, len(valid_sentences) / max(1, len(sentences) - 1))

    def _score_conciseness(self, text: str) -> float:
        """Score text conciseness (not overly verbose)."""
        words = text.split()
        if not words:
            return 0.0

        # Penalize very long or very short outputs
        word_count = len(words)
        if word_count < 10:
            return 0.5
        elif word_count > 500:
            return 0.4
        else:
            return 0.8

    def _score_completeness(self, text: str) -> float:
        """Score text completeness (appears to be a full response)."""
        if not text.strip():
            return 0.0

        # Check for trailing content that suggests completeness
        text_stripped = text.strip()
        ends_properly = text_stripped[-1] in ".!?)\"'"
        has_substance = len(text_stripped.split()) > 5

        score = 0.0
        if has_substance:
            score += 0.5
        if ends_properly:
            score += 0.5

        return score
