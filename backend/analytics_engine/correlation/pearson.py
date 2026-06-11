"""
Pearson correlation analysis.

Measures the linear relationship between two numeric variables.
Suitable when both variables are approximately normally distributed.
"""
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
import numpy as np
from config import get_logger

logger = get_logger(__name__)


@dataclass
class PearsonResult:
    """Result of Pearson correlation analysis."""
    metric_a: str
    metric_b: str
    coefficient: float  # -1 to 1
    p_value: float  # Statistical significance
    strength: str  # "strong", "moderate", "weak", "negligible"
    direction: str  # "positive", "negative", "none"
    n_observations: int
    is_significant: bool  # p_value < 0.05
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_a": self.metric_a,
            "metric_b": self.metric_b,
            "coefficient": round(self.coefficient, 4),
            "p_value": round(self.p_value, 6),
            "strength": self.strength,
            "direction": self.direction,
            "n_observations": self.n_observations,
            "is_significant": self.is_significant,
            "description": self.description,
        }


class PearsonCorrelation:
    """
    Compute Pearson correlation coefficient between variables.

    Measures linear relationship strength. Assumes:
    - Both variables are continuous
    - Approximately normally distributed
    - Linear relationship
    """

    SIGNIFICANCE_LEVEL = 0.05

    def compute(
        self,
        values_a: List[float],
        values_b: List[float],
        metric_a: str = "Metric A",
        metric_b: str = "Metric B",
    ) -> PearsonResult:
        """
        Compute Pearson correlation between two variables.

        Args:
            values_a: Values of first metric.
            values_b: Values of second metric (same length).
            metric_a: Name of first metric.
            metric_b: Name of second metric.

        Returns:
            PearsonResult with coefficient, significance, and interpretation.
        """
        if len(values_a) != len(values_b):
            min_len = min(len(values_a), len(values_b))
            values_a = values_a[:min_len]
            values_b = values_b[:min_len]

        n = len(values_a)

        if n < 3:
            return PearsonResult(
                metric_a=metric_a,
                metric_b=metric_b,
                coefficient=0.0,
                p_value=1.0,
                strength="negligible",
                direction="none",
                n_observations=n,
                is_significant=False,
                description="Insufficient data for correlation analysis (need at least 3 points).",
            )

        arr_a = np.array(values_a, dtype=float)
        arr_b = np.array(values_b, dtype=float)

        # Remove NaN pairs
        valid_mask = ~(np.isnan(arr_a) | np.isnan(arr_b))
        arr_a = arr_a[valid_mask]
        arr_b = arr_b[valid_mask]
        n = len(arr_a)

        if n < 3:
            return PearsonResult(
                metric_a=metric_a, metric_b=metric_b,
                coefficient=0.0, p_value=1.0,
                strength="negligible", direction="none",
                n_observations=n, is_significant=False,
                description="Not enough valid data points after removing nulls.",
            )

        # Compute Pearson r
        coefficient = self._pearson_r(arr_a, arr_b)

        # Compute p-value using t-distribution approximation
        p_value = self._p_value(coefficient, n)

        # Classify
        strength = self._classify_strength(abs(coefficient))
        direction = "positive" if coefficient > 0.05 else "negative" if coefficient < -0.05 else "none"
        is_significant = p_value < self.SIGNIFICANCE_LEVEL

        description = self._build_description(
            metric_a, metric_b, coefficient, strength, direction, is_significant
        )

        return PearsonResult(
            metric_a=metric_a,
            metric_b=metric_b,
            coefficient=float(coefficient),
            p_value=float(p_value),
            strength=strength,
            direction=direction,
            n_observations=n,
            is_significant=is_significant,
            description=description,
        )

    def compute_matrix(
        self,
        data: Dict[str, List[float]],
    ) -> Dict[str, Any]:
        """
        Compute a correlation matrix for multiple metrics.

        Args:
            data: Dict mapping metric names to their value lists.

        Returns:
            Dictionary with matrix, significant pairs, and metadata.
        """
        metric_names = list(data.keys())
        n_metrics = len(metric_names)

        matrix = np.zeros((n_metrics, n_metrics))
        significant_pairs = []

        for i in range(n_metrics):
            for j in range(i, n_metrics):
                if i == j:
                    matrix[i][j] = 1.0
                    continue

                result = self.compute(
                    data[metric_names[i]],
                    data[metric_names[j]],
                    metric_names[i],
                    metric_names[j],
                )

                matrix[i][j] = result.coefficient
                matrix[j][i] = result.coefficient

                if result.is_significant and result.strength in ("strong", "moderate"):
                    significant_pairs.append({
                        "metric_a": metric_names[i],
                        "metric_b": metric_names[j],
                        "coefficient": result.coefficient,
                        "strength": result.strength,
                    })

        # Sort significant pairs by absolute correlation
        significant_pairs.sort(key=lambda p: abs(p["coefficient"]), reverse=True)

        return {
            "metric_names": metric_names,
            "matrix": [[round(float(v), 4) for v in row] for row in matrix],
            "significant_pairs": significant_pairs,
            "total_pairs_tested": n_metrics * (n_metrics - 1) // 2,
            "significant_count": len(significant_pairs),
        }

    def _pearson_r(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compute Pearson correlation coefficient."""
        a_mean = np.mean(a)
        b_mean = np.mean(b)

        numerator = np.sum((a - a_mean) * (b - b_mean))
        denom_a = np.sqrt(np.sum((a - a_mean) ** 2))
        denom_b = np.sqrt(np.sum((b - b_mean) ** 2))

        denominator = denom_a * denom_b

        if denominator == 0:
            return 0.0

        return float(numerator / denominator)

    def _p_value(self, r: float, n: int) -> float:
        """Approximate p-value using t-distribution."""
        if abs(r) >= 1.0 or n <= 2:
            return 0.0 if abs(r) >= 1.0 else 1.0

        # t-statistic
        t_stat = r * np.sqrt((n - 2) / (1 - r ** 2))

        # Approximate p-value using normal approximation for large n
        # For small n this is an approximation
        from math import erfc, sqrt
        p = erfc(abs(t_stat) / sqrt(2))

        return float(p)

    def _classify_strength(self, abs_r: float) -> str:
        """Classify correlation strength."""
        if abs_r >= 0.7:
            return "strong"
        if abs_r >= 0.4:
            return "moderate"
        if abs_r >= 0.2:
            return "weak"
        return "negligible"

    def _build_description(
        self,
        metric_a: str,
        metric_b: str,
        coefficient: float,
        strength: str,
        direction: str,
        is_significant: bool,
    ) -> str:
        """Build natural language description."""
        if strength == "negligible":
            return f"No meaningful linear relationship between {metric_a} and {metric_b} (r={coefficient:.3f})."

        sig_text = "statistically significant" if is_significant else "not statistically significant"

        return (
            f"There is a {strength} {direction} linear relationship between "
            f"{metric_a} and {metric_b} (r={coefficient:.3f}, {sig_text})."
        )
