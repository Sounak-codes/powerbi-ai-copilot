"""
Regression testing for LLM outputs.

Compares current LLM outputs against saved baselines to detect
quality regressions from prompt changes, model updates, or
configuration changes.
"""
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import time

from config import get_logger
from llm.providers.provider_factory import ProviderFactory

logger = get_logger(__name__)


@dataclass
class BaselineEntry:
    """A saved baseline output for regression comparison."""

    entry_id: str
    prompt: str
    baseline_output: str
    created_at: str
    model: str = ""
    tags: List[str] = field(default_factory=list)
    quality_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RegressionFinding:
    """A finding from regression comparison."""

    entry_id: str
    status: str  # "pass", "regression", "improvement", "changed"
    similarity_score: float = 0.0
    quality_delta: float = 0.0  # positive = improvement, negative = regression
    baseline_preview: str = ""
    current_preview: str = ""
    details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "status": self.status,
            "similarity_score": round(self.similarity_score, 4),
            "quality_delta": round(self.quality_delta, 4),
            "baseline_preview": self.baseline_preview[:150],
            "current_preview": self.current_preview[:150],
            "details": self.details,
        }


@dataclass
class RegressionReport:
    """Complete regression test report."""

    run_id: str
    timestamp: str
    total_tests: int
    passed: int
    regressions: int
    improvements: int
    avg_similarity: float
    findings: List[RegressionFinding] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def has_regressions(self) -> bool:
        return self.regressions > 0

    @property
    def regression_rate(self) -> float:
        return self.regressions / self.total_tests if self.total_tests > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "total_tests": self.total_tests,
            "passed": self.passed,
            "regressions": self.regressions,
            "improvements": self.improvements,
            "has_regressions": self.has_regressions,
            "regression_rate": round(self.regression_rate, 4),
            "avg_similarity": round(self.avg_similarity, 4),
            "findings": [f.to_dict() for f in self.findings],
            "metadata": self.metadata,
        }


class RegressionTester:
    """
    Compares current LLM outputs against baseline to detect regressions.

    Maintains a set of baseline outputs and re-runs prompts to check
    if quality has degraded. Uses text similarity and quality scoring
    to classify changes as regressions or improvements.
    """

    def __init__(
        self,
        similarity_threshold: float = 0.7,
        regression_threshold: float = -0.15,
    ):
        """
        Initialize the regression tester.

        Args:
            similarity_threshold: Minimum similarity score to consider output "same".
            regression_threshold: Quality delta below which a change is a regression.
        """
        self._provider = ProviderFactory.get_default_provider()
        self._baselines: List[BaselineEntry] = []
        self._similarity_threshold = similarity_threshold
        self._regression_threshold = regression_threshold
        self._run_count = 0

    def add_baseline(self, entry: BaselineEntry) -> None:
        """
        Add a baseline entry for regression testing.

        Args:
            entry: The baseline entry to add.
        """
        self._baselines.append(entry)
        logger.debug(f"Baseline added: {entry.entry_id}")

    def add_baselines(self, entries: List[BaselineEntry]) -> None:
        """Add multiple baseline entries."""
        self._baselines.extend(entries)
        logger.debug(f"Added {len(entries)} baselines (total: {len(self._baselines)})")

    def create_baseline(
        self,
        entry_id: str,
        prompt: str,
        output: str,
        model: str = "",
        tags: Optional[List[str]] = None,
        quality_score: float = 0.8,
    ) -> BaselineEntry:
        """
        Create and register a new baseline entry.

        Args:
            entry_id: Unique identifier for this baseline.
            prompt: The prompt used to generate the output.
            output: The baseline output to save.
            model: Model used to generate the baseline.
            tags: Optional tags for filtering.
            quality_score: Quality score of the baseline (0.0-1.0).

        Returns:
            The created BaselineEntry.
        """
        entry = BaselineEntry(
            entry_id=entry_id,
            prompt=prompt,
            baseline_output=output,
            created_at=datetime.utcnow().isoformat() + "Z",
            model=model,
            tags=tags or [],
            quality_score=quality_score,
        )
        self.add_baseline(entry)
        return entry

    def _compute_similarity(self, text_a: str, text_b: str) -> float:
        """
        Compute text similarity between two outputs.

        Uses word overlap (Jaccard similarity) as a simple metric.
        """
        if not text_a or not text_b:
            return 0.0

        words_a = set(text_a.lower().split())
        words_b = set(text_b.lower().split())

        if not words_a or not words_b:
            return 0.0

        intersection = words_a & words_b
        union = words_a | words_b

        return len(intersection) / len(union)

    def _compute_quality_score(self, text: str) -> float:
        """Compute a quality score for generated text."""
        if not text.strip():
            return 0.0

        score = 0.0

        # Length check (not too short, not too long)
        words = text.split()
        if 10 <= len(words) <= 500:
            score += 0.3
        elif len(words) > 5:
            score += 0.15

        # Structure (has sentences)
        sentences = [s.strip() for s in text.split(".") if len(s.strip()) > 5]
        if sentences:
            score += 0.3

        # Completeness (ends properly)
        if text.strip()[-1:] in ".!?)":
            score += 0.2

        # Coherence (reasonable word diversity)
        unique_words = set(text.lower().split())
        diversity = len(unique_words) / len(words) if words else 0
        if diversity > 0.3:
            score += 0.2

        return min(1.0, score)

    def _classify_change(
        self,
        similarity: float,
        quality_delta: float,
    ) -> str:
        """Classify a change as pass, regression, improvement, or changed."""
        if similarity >= self._similarity_threshold:
            return "pass"
        elif quality_delta < self._regression_threshold:
            return "regression"
        elif quality_delta > abs(self._regression_threshold):
            return "improvement"
        else:
            return "changed"

    async def run_regression(
        self,
        tags: Optional[List[str]] = None,
        system_prompt: Optional[str] = None,
    ) -> RegressionReport:
        """
        Run regression tests against all baselines.

        Args:
            tags: Optional filter to run only baselines with specific tags.
            system_prompt: Optional system prompt to use for re-generation.

        Returns:
            RegressionReport with findings and statistics.
        """
        self._run_count += 1
        run_id = f"reg_{self._run_count}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"Starting regression run: {run_id} ({len(self._baselines)} baselines)")

        # Filter baselines
        baselines = self._baselines
        if tags:
            baselines = [b for b in baselines if any(t in b.tags for t in tags)]

        findings: List[RegressionFinding] = []

        for baseline in baselines:
            finding = await self._test_baseline(baseline, system_prompt)
            findings.append(finding)

        # Aggregate results
        passed = sum(1 for f in findings if f.status == "pass")
        regressions = sum(1 for f in findings if f.status == "regression")
        improvements = sum(1 for f in findings if f.status == "improvement")
        similarities = [f.similarity_score for f in findings]

        report = RegressionReport(
            run_id=run_id,
            timestamp=datetime.utcnow().isoformat() + "Z",
            total_tests=len(findings),
            passed=passed,
            regressions=regressions,
            improvements=improvements,
            avg_similarity=sum(similarities) / len(similarities) if similarities else 0.0,
            findings=findings,
            metadata={
                "tags_filter": tags,
                "similarity_threshold": self._similarity_threshold,
                "regression_threshold": self._regression_threshold,
            },
        )

        logger.info(
            f"Regression run complete: {run_id} - "
            f"{passed} passed, {regressions} regressions, {improvements} improvements"
        )

        if regressions > 0:
            logger.warning(f"REGRESSIONS DETECTED: {regressions} tests regressed")

        return report

    async def _test_baseline(
        self,
        baseline: BaselineEntry,
        system_prompt: Optional[str],
    ) -> RegressionFinding:
        """Test a single baseline entry."""
        try:
            kwargs: Dict[str, Any] = {"prompt": baseline.prompt}
            if system_prompt:
                kwargs["system_prompt"] = system_prompt

            current_output = await self._provider.generate(**kwargs)

            # Compute metrics
            similarity = self._compute_similarity(baseline.baseline_output, current_output)
            current_quality = self._compute_quality_score(current_output)
            quality_delta = current_quality - baseline.quality_score

            # Classify
            status = self._classify_change(similarity, quality_delta)

            details = ""
            if status == "regression":
                details = f"Quality dropped by {abs(quality_delta):.3f}. Similarity: {similarity:.3f}"
            elif status == "improvement":
                details = f"Quality improved by {quality_delta:.3f}. Similarity: {similarity:.3f}"

            return RegressionFinding(
                entry_id=baseline.entry_id,
                status=status,
                similarity_score=similarity,
                quality_delta=quality_delta,
                baseline_preview=baseline.baseline_output[:150],
                current_preview=current_output[:150],
                details=details,
            )

        except Exception as e:
            logger.error(f"Regression test failed for {baseline.entry_id}: {e}")
            return RegressionFinding(
                entry_id=baseline.entry_id,
                status="regression",
                similarity_score=0.0,
                quality_delta=-1.0,
                baseline_preview=baseline.baseline_output[:150],
                current_preview="",
                details=f"Execution failed: {str(e)}",
            )

    def get_baselines(self, tags: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Get all baselines, optionally filtered by tags."""
        baselines = self._baselines
        if tags:
            baselines = [b for b in baselines if any(t in b.tags for t in tags)]

        return [
            {
                "entry_id": b.entry_id,
                "prompt_preview": b.prompt[:100],
                "created_at": b.created_at,
                "model": b.model,
                "tags": b.tags,
                "quality_score": b.quality_score,
            }
            for b in baselines
        ]

    def clear_baselines(self) -> None:
        """Clear all registered baselines."""
        self._baselines.clear()
        logger.info("All baselines cleared")
