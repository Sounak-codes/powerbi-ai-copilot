"""
Driver analysis for identifying key factors behind metric behavior.

Uses statistical methods to determine which dimensions have the
strongest influence on a target metric, ranking them by impact.
"""
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
import numpy as np
from config import get_logger

logger = get_logger(__name__)


@dataclass
class Driver:
    """A dimension identified as a driver of metric behavior."""
    dimension: str
    impact_score: float  # 0-1 normalized importance
    correlation: float  # Correlation with target metric
    direction: str  # "positive" or "negative"
    segments_count: int
    top_segments: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension,
            "impact_score": round(self.impact_score, 4),
            "correlation": round(self.correlation, 4),
            "direction": self.direction,
            "segments_count": self.segments_count,
            "top_segments": self.top_segments,
        }


@dataclass
class DriverAnalysisResult:
    """Result of driver analysis."""
    target_metric: str
    drivers: List[Driver]
    total_variance_explained: float
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_metric": self.target_metric,
            "drivers": [d.to_dict() for d in self.drivers],
            "total_variance_explained": round(self.total_variance_explained, 4),
            "description": self.description,
        }


class DriverAnalyzer:
    """
    Identifies which dimensions drive variation in a target metric.

    Uses variance decomposition and correlation analysis to rank
    dimensions by their explanatory power.
    """

    def analyze(
        self,
        target_metric: str,
        target_values: List[float],
        dimensions: Dict[str, List[str]],
        top_n: int = 5,
    ) -> DriverAnalysisResult:
        """
        Identify key drivers of a metric.

        Args:
            target_metric: Name of the metric to explain.
            target_values: Values of the target metric (one per observation).
            dimensions: Dict[dimension_name -> list of category labels per observation].
            top_n: Number of top drivers to return.

        Returns:
            DriverAnalysisResult with ranked drivers.
        """
        if not target_values or not dimensions:
            return DriverAnalysisResult(
                target_metric=target_metric,
                drivers=[],
                total_variance_explained=0.0,
                description="Insufficient data for driver analysis.",
            )

        target_arr = np.array(target_values, dtype=float)
        total_variance = np.var(target_arr)

        if total_variance == 0:
            return DriverAnalysisResult(
                target_metric=target_metric,
                drivers=[],
                total_variance_explained=0.0,
                description="No variance in target metric — cannot identify drivers.",
            )

        drivers = []

        for dim_name, dim_labels in dimensions.items():
            if len(dim_labels) != len(target_values):
                logger.warning(f"Dimension '{dim_name}' length mismatch, skipping")
                continue

            impact_score, top_segments = self._calculate_dimension_impact(
                target_arr, dim_labels, total_variance
            )

            # Calculate correlation using one-hot encoding average
            correlation = self._dimension_correlation(target_arr, dim_labels)

            drivers.append(Driver(
                dimension=dim_name,
                impact_score=impact_score,
                correlation=correlation,
                direction="positive" if correlation > 0 else "negative",
                segments_count=len(set(dim_labels)),
                top_segments=top_segments[:3],
            ))

        # Sort by impact score
        drivers.sort(key=lambda d: d.impact_score, reverse=True)
        top_drivers = drivers[:top_n]

        total_explained = sum(d.impact_score for d in top_drivers)

        description = self._build_description(target_metric, top_drivers)

        return DriverAnalysisResult(
            target_metric=target_metric,
            drivers=top_drivers,
            total_variance_explained=min(1.0, total_explained),
            description=description,
        )

    def _calculate_dimension_impact(
        self,
        target: np.ndarray,
        labels: List[str],
        total_variance: float,
    ) -> Tuple[float, List[Dict[str, Any]]]:
        """
        Calculate how much variance a dimension explains (eta-squared / ANOVA).

        Returns (impact_score, top_segments_info).
        """
        unique_labels = list(set(labels))
        labels_arr = np.array(labels)

        # Calculate between-group variance (SSB)
        grand_mean = np.mean(target)
        ssb = 0.0
        segment_info = []

        for label in unique_labels:
            mask = labels_arr == label
            group = target[mask]
            group_mean = np.mean(group)
            n_group = len(group)
            ssb += n_group * (group_mean - grand_mean) ** 2

            segment_info.append({
                "segment": label,
                "mean": round(float(group_mean), 2),
                "count": int(n_group),
                "deviation_from_mean": round(float(group_mean - grand_mean), 2),
            })

        # Eta-squared: proportion of variance explained
        sst = total_variance * len(target)
        impact_score = float(ssb / sst) if sst > 0 else 0.0

        # Sort segments by absolute deviation from grand mean
        segment_info.sort(
            key=lambda s: abs(s["deviation_from_mean"]), reverse=True
        )

        return impact_score, segment_info

    def _dimension_correlation(
        self, target: np.ndarray, labels: List[str]
    ) -> float:
        """
        Calculate a pseudo-correlation between dimension and target.

        Uses the correlation ratio (eta) with direction from
        the highest-mean group vs lowest-mean group.
        """
        unique_labels = list(set(labels))
        labels_arr = np.array(labels)

        group_means = {}
        for label in unique_labels:
            mask = labels_arr == label
            group_means[label] = float(np.mean(target[mask]))

        if not group_means:
            return 0.0

        # Direction: positive if the largest groups have higher means
        sorted_groups = sorted(group_means.items(), key=lambda x: x[1])
        max_mean = sorted_groups[-1][1]
        min_mean = sorted_groups[0][1]
        grand_mean = float(np.mean(target))

        # Positive if high-value groups are larger
        direction = 1.0 if (max_mean - grand_mean) > (grand_mean - min_mean) else -1.0

        # Magnitude from eta-squared
        total_var = np.var(target) * len(target)
        ssb = sum(
            np.sum(labels_arr == label) * (mean - grand_mean) ** 2
            for label, mean in group_means.items()
        )
        eta = np.sqrt(ssb / total_var) if total_var > 0 else 0.0

        return float(direction * eta)

    def _build_description(
        self, target_metric: str, drivers: List[Driver]
    ) -> str:
        """Build natural language description of drivers."""
        if not drivers:
            return f"No significant drivers identified for {target_metric}."

        top = drivers[0]
        desc = (
            f"The strongest driver of {target_metric} is '{top.dimension}' "
            f"(impact score: {top.impact_score:.2f}), "
            f"explaining ~{top.impact_score * 100:.0f}% of the variation."
        )

        if len(drivers) > 1:
            others = ", ".join(f"'{d.dimension}'" for d in drivers[1:3])
            desc += f" Other notable drivers: {others}."

        return desc
