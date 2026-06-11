"""
KPI scoring engine.

Calculates composite KPI scores that combine multiple metrics
into a single health/performance index.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import numpy as np
from config import get_logger

logger = get_logger(__name__)


@dataclass
class ScoringWeight:
    """Weight configuration for a metric in a composite score."""
    metric_name: str
    weight: float  # 0.0 to 1.0
    normalization: str = "minmax"  # "minmax", "zscore", "percentage"
    higher_is_better: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "weight": self.weight,
            "normalization": self.normalization,
            "higher_is_better": self.higher_is_better,
        }


@dataclass
class CompositeScore:
    """A composite KPI score."""
    score_name: str
    value: float  # 0-100
    components: List[Dict[str, Any]]
    grade: str  # "A", "B", "C", "D", "F"
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score_name": self.score_name,
            "value": round(self.value, 1),
            "components": self.components,
            "grade": self.grade,
            "description": self.description,
        }


class KPIScorer:
    """
    Calculate composite KPI scores from multiple metrics.

    Supports weighted scoring, multiple normalization methods,
    and letter grading.
    """

    GRADE_BOUNDARIES = {"A": 90, "B": 75, "C": 60, "D": 45, "F": 0}

    def calculate_composite_score(
        self,
        score_name: str,
        metrics: Dict[str, float],
        weights: List[ScoringWeight],
        historical_data: Optional[Dict[str, List[float]]] = None,
    ) -> CompositeScore:
        """
        Calculate a weighted composite score.

        Args:
            score_name: Name for this composite score.
            metrics: Current values for each metric.
            weights: Scoring configuration for each metric.
            historical_data: Historical values for normalization.

        Returns:
            CompositeScore with value, grade, and component breakdown.
        """
        if not weights:
            return CompositeScore(
                score_name=score_name,
                value=0.0,
                components=[],
                grade="F",
                description="No scoring weights configured.",
            )

        # Normalize weights to sum to 1
        total_weight = sum(w.weight for w in weights)
        if total_weight == 0:
            total_weight = 1.0

        components = []
        weighted_sum = 0.0

        for w in weights:
            raw_value = metrics.get(w.metric_name, 0.0)
            history = (
                historical_data.get(w.metric_name, [])
                if historical_data
                else []
            )

            # Normalize to 0-100 scale
            normalized = self._normalize(
                raw_value, w.normalization, history, w.higher_is_better
            )

            effective_weight = w.weight / total_weight
            contribution = normalized * effective_weight
            weighted_sum += contribution

            components.append({
                "metric": w.metric_name,
                "raw_value": round(raw_value, 2),
                "normalized_score": round(normalized, 1),
                "weight": round(effective_weight, 3),
                "contribution": round(contribution, 1),
            })

        grade = self._assign_grade(weighted_sum)

        return CompositeScore(
            score_name=score_name,
            value=float(np.clip(weighted_sum, 0, 100)),
            components=components,
            grade=grade,
            description=f"{score_name}: {weighted_sum:.1f}/100 (Grade: {grade})",
        )

    def rank_metrics(
        self,
        data: Dict[str, float],
        higher_is_better: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Rank metrics from best to worst performing.

        Returns ordered list with rank, percentile, and status.
        """
        items = sorted(
            data.items(),
            key=lambda x: x[1],
            reverse=higher_is_better,
        )

        n = len(items)
        rankings = []

        for rank, (name, value) in enumerate(items, 1):
            percentile = ((n - rank) / n) * 100 if n > 1 else 50.0
            rankings.append({
                "metric": name,
                "value": round(value, 2),
                "rank": rank,
                "percentile": round(percentile, 1),
                "tier": "top" if percentile >= 75 else "middle" if percentile >= 25 else "bottom",
            })

        return rankings

    def _normalize(
        self,
        value: float,
        method: str,
        history: List[float],
        higher_is_better: bool,
    ) -> float:
        """Normalize a value to 0-100 scale."""
        if method == "percentage":
            score = value * 100  # Already a ratio (0-1)
        elif method == "zscore" and history:
            arr = np.array(history)
            mean = np.mean(arr)
            std = np.std(arr)
            if std > 0:
                z = (value - mean) / std
                # Convert z-score to 0-100 (±3σ maps to 0-100)
                score = (z + 3) / 6 * 100
            else:
                score = 50.0
        elif method == "minmax" and history:
            arr = np.array(history)
            min_val = np.min(arr)
            max_val = np.max(arr)
            if max_val > min_val:
                score = ((value - min_val) / (max_val - min_val)) * 100
            else:
                score = 50.0
        else:
            # Default: treat as percentage of 100
            score = min(value, 100.0)

        if not higher_is_better:
            score = 100 - score

        return float(np.clip(score, 0, 100))

    def _assign_grade(self, score: float) -> str:
        """Assign letter grade based on score."""
        for grade, boundary in self.GRADE_BOUNDARIES.items():
            if score >= boundary:
                return grade
        return "F"
