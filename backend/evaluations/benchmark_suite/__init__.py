"""
Benchmark suite for evaluating LLM and agent performance.

Runs a set of evaluation tests against defined test cases
and produces structured performance reports.
"""
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
import time

from config import get_logger
from llm.providers.provider_factory import ProviderFactory

logger = get_logger(__name__)


@dataclass
class BenchmarkCase:
    """A single benchmark test case."""

    case_id: str
    name: str
    input_data: Dict[str, Any]
    expected_output: Optional[Dict[str, Any]] = None
    tags: List[str] = field(default_factory=list)
    timeout_seconds: float = 30.0


@dataclass
class BenchmarkResult:
    """Result of a single benchmark case."""

    case_id: str
    name: str
    passed: bool
    score: float = 0.0  # 0.0 - 1.0
    latency_ms: float = 0.0
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "name": self.name,
            "passed": self.passed,
            "score": round(self.score, 4),
            "latency_ms": round(self.latency_ms, 2),
            "output": self.output,
            "error": self.error,
            "details": self.details,
        }


@dataclass
class BenchmarkReport:
    """Complete benchmark run report."""

    run_id: str
    timestamp: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    avg_score: float
    avg_latency_ms: float
    results: List[BenchmarkResult] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def pass_rate(self) -> float:
        """Calculate pass rate."""
        return self.passed_cases / self.total_cases if self.total_cases > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "failed_cases": self.failed_cases,
            "pass_rate": round(self.pass_rate, 4),
            "avg_score": round(self.avg_score, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "results": [r.to_dict() for r in self.results],
            "metadata": self.metadata,
        }


class BenchmarkSuite:
    """
    Runs evaluation benchmarks against LLM and agent outputs.

    Supports custom evaluation functions, scoring, and latency tracking.
    Produces structured reports comparing results against expected outputs.
    """

    def __init__(self):
        self._provider = ProviderFactory.get_default_provider()
        self._cases: List[BenchmarkCase] = []
        self._evaluators: Dict[str, Callable] = {}
        self._run_count = 0

    def add_case(self, case: BenchmarkCase) -> None:
        """
        Add a benchmark test case.

        Args:
            case: The benchmark case to add.
        """
        self._cases.append(case)
        logger.debug(f"Benchmark case added: {case.case_id}")

    def add_cases(self, cases: List[BenchmarkCase]) -> None:
        """Add multiple benchmark test cases."""
        self._cases.extend(cases)
        logger.debug(f"Added {len(cases)} benchmark cases")

    def register_evaluator(
        self,
        name: str,
        evaluator: Callable[[Dict[str, Any], Optional[Dict[str, Any]]], float],
    ) -> None:
        """
        Register a custom evaluation function.

        Args:
            name: Name of the evaluator.
            evaluator: Function that takes (actual_output, expected_output)
                      and returns a score between 0.0 and 1.0.
        """
        self._evaluators[name] = evaluator
        logger.debug(f"Evaluator registered: {name}")

    async def run_benchmarks(
        self,
        prompt_template: Optional[str] = None,
        evaluator_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> BenchmarkReport:
        """
        Run all benchmark cases and produce a report.

        Args:
            prompt_template: Optional prompt template to use for LLM calls.
                           Use {input} as placeholder for test input.
            evaluator_name: Name of registered evaluator to use for scoring.
            tags: Optional filter to run only cases with specific tags.

        Returns:
            BenchmarkReport with all results and aggregate metrics.
        """
        self._run_count += 1
        run_id = f"bench_{self._run_count}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"Starting benchmark run: {run_id} ({len(self._cases)} cases)")

        # Filter cases by tags
        cases = self._cases
        if tags:
            cases = [c for c in cases if any(t in c.tags for t in tags)]

        results: List[BenchmarkResult] = []

        for case in cases:
            result = await self._run_single_case(case, prompt_template, evaluator_name)
            results.append(result)

        # Aggregate metrics
        passed = sum(1 for r in results if r.passed)
        failed = len(results) - passed
        scores = [r.score for r in results]
        latencies = [r.latency_ms for r in results]

        report = BenchmarkReport(
            run_id=run_id,
            timestamp=datetime.utcnow().isoformat() + "Z",
            total_cases=len(results),
            passed_cases=passed,
            failed_cases=failed,
            avg_score=sum(scores) / len(scores) if scores else 0.0,
            avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0.0,
            results=results,
            metadata={
                "prompt_template": prompt_template,
                "evaluator": evaluator_name,
                "tags_filter": tags,
            },
        )

        logger.info(
            f"Benchmark run complete: {run_id} - "
            f"{passed}/{len(results)} passed, avg score {report.avg_score:.3f}"
        )
        return report

    async def _run_single_case(
        self,
        case: BenchmarkCase,
        prompt_template: Optional[str],
        evaluator_name: Optional[str],
    ) -> BenchmarkResult:
        """Run a single benchmark case."""
        start_time = time.perf_counter()

        try:
            # Generate output via LLM
            if prompt_template:
                prompt = prompt_template.format(input=str(case.input_data))
            else:
                prompt = str(case.input_data)

            response = await self._provider.generate(prompt=prompt)
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            output = {"response": response}

            # Score the result
            score = self._evaluate(output, case.expected_output, evaluator_name)
            passed = score >= 0.5  # Threshold for passing

            return BenchmarkResult(
                case_id=case.case_id,
                name=case.name,
                passed=passed,
                score=score,
                latency_ms=elapsed_ms,
                output=output,
            )

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"Benchmark case failed: {case.case_id} - {e}")
            return BenchmarkResult(
                case_id=case.case_id,
                name=case.name,
                passed=False,
                score=0.0,
                latency_ms=elapsed_ms,
                error=str(e),
            )

    def _evaluate(
        self,
        actual: Dict[str, Any],
        expected: Optional[Dict[str, Any]],
        evaluator_name: Optional[str],
    ) -> float:
        """Evaluate an output against expected using the specified evaluator."""
        # Use custom evaluator if specified
        if evaluator_name and evaluator_name in self._evaluators:
            try:
                score = self._evaluators[evaluator_name](actual, expected)
                return max(0.0, min(1.0, score))
            except Exception as e:
                logger.error(f"Evaluator {evaluator_name} failed: {e}")
                return 0.0

        # Default evaluation: check if expected keys are present in response
        if expected is None:
            # No expected output, just check we got a non-empty response
            response = actual.get("response", "")
            return 1.0 if response and len(response) > 10 else 0.0

        # Simple keyword matching evaluation
        response = str(actual.get("response", "")).lower()
        expected_keywords = str(expected).lower().split()

        if not expected_keywords:
            return 1.0

        matches = sum(1 for kw in expected_keywords if kw in response)
        return matches / len(expected_keywords)

    def clear_cases(self) -> None:
        """Clear all registered benchmark cases."""
        self._cases.clear()
        logger.info("Benchmark cases cleared")
