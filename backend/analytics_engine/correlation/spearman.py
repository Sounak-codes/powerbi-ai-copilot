"""
Spearman rank correlation analysis.

Measures monotonic (not necessarily linear) relationships.
More robust to outliers and non-normal distributions than Pearson.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import numpy as np
from config import get_logger

logger = get_logger(__name__)


@dataclass
class SpearmanResult:
    """Result of Spearman rank correlation."""
    metric_a: str
    metric_b: str
    coefficient: float  # -1 to 1 (rank correlation)
    strength: str
    direction: str
    n_observations: int
    tied_count: int  # Number of tied ranks
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_a": self.metric_a,
            "metric_b": self.metric_b,
            "coefficient": round(self.coefficient, 4),
            "strength": self.strength,
            "direction": self.direction,
            "n_observations": self.n_observations,
            "tied_count": self.tied_count,
            "description": self.description,
        }


class SpearmanCorrelation:
    """
    Compute Spearman rank correlation.

    Assesses monotonic relationships (both linear and non-linear).
    Better choice when:
    - Data is ordinal
    - Outliers are present
    - Relationship is monotonic but not linear
    """

    def compute(
        self,
        values_a: List[float],
        values_b: List[float],
        metric_a: str = "Metric A",
        metric_b: str = "Metric B",
    ) -> SpearmanResult:
        """
        Compute Spearman rank correlation.

        Args:
            values_a: Values of first metric.
            values_b: Values of second metric (same length).
            metric_a: Name of first metric.
            metric_b: Name of second metric.

        Returns:
            SpearmanResult with coefficient and interpretation.
        """
        min_len = min(len(values_a), len(values_b))
        values_a = values_a[:min_len]
        values_b = values_b[:min_len]
        n = min_len

        if n < 3:
            return SpearmanResult(
                metric_a=metric_a, metric_b=metric_b,
                coefficient=0.0, strength="negligible", direction="none",
                n_observations=n, tied_count=0,
                description="Insufficient data for Spearman correlation.",
            )

        # Compute ranks
        ranks_a, ties_a = self._rank(values_a)
        ranks_b, ties_b = self._rank(values_b)
        tied_count = ties_a + ties_b

        # Spearman rho = Pearson r of the ranks
        coefficient = self._pearson_of_ranks(ranks_a, ranks_b)

        strength = self._classify_strength(abs(coefficient))
        direction = "positive" if coefficient > 0.05 else "negative" if coefficient < -0.05 else "none"

        description = self._build_description(
            metric_a, metric_b, coefficient, strength, direction
        )

        return SpearmanResult(
            metric_a=metric_a,
            metric_b=metric_b,
            coefficient=float(coefficient),
            strength=strength,
            direction=direction,
            n_observations=n,
            tied_count=tied_count,
            description=description,
        )

    def compare_with_pearson(
        self,
        values_a: List[float],
        values_b: List[float],
        metric_a: str = "Metric A",
        metric_b: str = "Metric B",
    ) -> Dict[str, Any]:
        """
        Compare Spearman and Pearson correlations.

        If Spearman >> Pearson, the relationship is monotonic but non-linear.
        If Pearson >> Spearman, outliers may be inflating Pearson.
        """
        spearman = self.compute(values_a, values_b, metric_a, metric_b)

        from analytics_engine.correlation.pearson import PearsonCorrelation
        pearson_analyzer = PearsonCorrelation()
        pearson = pearson_analyzer.compute(values_a, values_b, metric_a, metric_b)

        diff = abs(spearman.coefficient) - abs(pearson.coefficient)

        if diff > 0.15:
            interpretation = (
                "Spearman is notably higher than Pearson, suggesting a "
                "monotonic but non-linear relationship."
            )
        elif diff < -0.15:
            interpretation = (
                "Pearson is notably higher than Spearman, which may indicate "
                "outliers inflating the linear correlation."
            )
        else:
            interpretation = (
                "Spearman and Pearson are similar, suggesting a "
                "approximately linear monotonic relationship."
            )

        return {
            "spearman": spearman.to_dict(),
            "pearson": pearson.to_dict(),
            "difference": round(diff, 4),
            "interpretation": interpretation,
        }

    def _rank(self, values: List[float]) -> tuple:
        """
        Assign ranks with average ranking for ties.

        Returns (ranks_array, number_of_ties).
        """
        arr = np.array(values, dtype=float)
        n = len(arr)

        # Sort indices
        order = arr.argsort()
        ranks = np.empty(n, dtype=float)

        i = 0
        ties = 0
        while i < n:
            # Find ties
            j = i
            while j < n - 1 and arr[order[j]] == arr[order[j + 1]]:
                j += 1

            # Average rank for all tied values
            avg_rank = (i + j) / 2 + 1  # 1-indexed
            for k in range(i, j + 1):
                ranks[order[k]] = avg_rank

            if j > i:
                ties += j - i

            i = j + 1

        return ranks, ties

    def _pearson_of_ranks(
        self, ranks_a: np.ndarray, ranks_b: np.ndarray
    ) -> float:
        """Compute Pearson correlation of ranks."""
        a_mean = np.mean(ranks_a)
        b_mean = np.mean(ranks_b)

        numerator = np.sum((ranks_a - a_mean) * (ranks_b - b_mean))
        denom = np.sqrt(
            np.sum((ranks_a - a_mean) ** 2) * np.sum((ranks_b - b_mean) ** 2)
        )

        if denom == 0:
            return 0.0

        return float(numerator / denom)

    def _classify_strength(self, abs_rho: float) -> str:
        """Classify correlation strength."""
        if abs_rho >= 0.7:
            return "strong"
        if abs_rho >= 0.4:
            return "moderate"
        if abs_rho >= 0.2:
            return "weak"
        return "negligible"

    def _build_description(
        self,
        metric_a: str,
        metric_b: str,
        coefficient: float,
        strength: str,
        direction: str,
    ) -> str:
        """Build natural language description."""
        if strength == "negligible":
            return f"No meaningful monotonic relationship between {metric_a} and {metric_b}."

        return (
            f"There is a {strength} {direction} monotonic relationship between "
            f"{metric_a} and {metric_b} (ρ={coefficient:.3f})."
        )
