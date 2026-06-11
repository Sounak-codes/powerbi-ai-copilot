"""
Relationship analysis — high-level API for finding and interpreting
correlations between metrics in a dataset.

Combines Pearson and Spearman, auto-selects the appropriate method,
and provides business-ready interpretations.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import numpy as np
from analytics_engine.correlation.pearson import PearsonCorrelation, PearsonResult
from analytics_engine.correlation.spearman import SpearmanCorrelation, SpearmanResult
from config import get_logger

logger = get_logger(__name__)


@dataclass
class Relationship:
    """A discovered relationship between two metrics."""
    metric_a: str
    metric_b: str
    pearson_r: float
    spearman_rho: float
    recommended_method: str  # "pearson" or "spearman"
    coefficient: float  # The recommended coefficient
    strength: str
    direction: str
    is_linear: bool
    interpretation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_a": self.metric_a,
            "metric_b": self.metric_b,
            "pearson_r": round(self.pearson_r, 4),
            "spearman_rho": round(self.spearman_rho, 4),
            "recommended_method": self.recommended_method,
            "coefficient": round(self.coefficient, 4),
            "strength": self.strength,
            "direction": self.direction,
            "is_linear": self.is_linear,
            "interpretation": self.interpretation,
        }


@dataclass
class RelationshipAnalysisResult:
    """Result of relationship analysis across a dataset."""
    relationships: List[Relationship]
    strong_correlations: List[Relationship]
    potential_causal: List[Dict[str, Any]]
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relationships": [r.to_dict() for r in self.relationships],
            "strong_correlations": [r.to_dict() for r in self.strong_correlations],
            "potential_causal": self.potential_causal,
            "summary": self.summary,
            "total_pairs_analyzed": len(self.relationships),
        }


class RelationshipAnalyzer:
    """
    High-level relationship analysis engine.

    Discovers correlations between metrics, selects the best method,
    and provides interpretable results.
    """

    def __init__(self):
        self.pearson = PearsonCorrelation()
        self.spearman = SpearmanCorrelation()

    def analyze_all_pairs(
        self,
        data: Dict[str, List[float]],
        min_strength: str = "moderate",
    ) -> RelationshipAnalysisResult:
        """
        Analyze relationships between all pairs of metrics.

        Args:
            data: Dict mapping metric names to value lists.
            min_strength: Minimum strength to include ("weak", "moderate", "strong").

        Returns:
            RelationshipAnalysisResult with discovered relationships.
        """
        metric_names = list(data.keys())
        n = len(metric_names)

        if n < 2:
            return RelationshipAnalysisResult(
                relationships=[],
                strong_correlations=[],
                potential_causal=[],
                summary="Need at least 2 metrics for relationship analysis.",
            )

        all_relationships = []
        strength_order = {"negligible": 0, "weak": 1, "moderate": 2, "strong": 3}
        min_level = strength_order.get(min_strength, 1)

        for i in range(n):
            for j in range(i + 1, n):
                relationship = self._analyze_pair(
                    data[metric_names[i]],
                    data[metric_names[j]],
                    metric_names[i],
                    metric_names[j],
                )

                if strength_order.get(relationship.strength, 0) >= min_level:
                    all_relationships.append(relationship)

        # Sort by absolute coefficient
        all_relationships.sort(key=lambda r: abs(r.coefficient), reverse=True)

        # Strong correlations
        strong = [r for r in all_relationships if r.strength == "strong"]

        # Potential causal relationships (strong + directional)
        potential_causal = self._identify_potential_causal(all_relationships, data)

        summary = self._build_summary(all_relationships, strong, n)

        return RelationshipAnalysisResult(
            relationships=all_relationships,
            strong_correlations=strong,
            potential_causal=potential_causal,
            summary=summary,
        )

    def analyze_pair(
        self,
        values_a: List[float],
        values_b: List[float],
        metric_a: str = "Metric A",
        metric_b: str = "Metric B",
    ) -> Relationship:
        """Analyze the relationship between two specific metrics."""
        return self._analyze_pair(values_a, values_b, metric_a, metric_b)

    def find_strongest_correlates(
        self,
        data: Dict[str, List[float]],
        target_metric: str,
        top_n: int = 5,
    ) -> List[Relationship]:
        """
        Find the metrics most correlated with a target metric.

        Args:
            data: Dict of all metric values.
            target_metric: The metric to find correlates for.
            top_n: Number of top results.

        Returns:
            List of Relationships sorted by absolute correlation.
        """
        if target_metric not in data:
            return []

        target_values = data[target_metric]
        relationships = []

        for name, values in data.items():
            if name == target_metric:
                continue
            rel = self._analyze_pair(target_values, values, target_metric, name)
            relationships.append(rel)

        relationships.sort(key=lambda r: abs(r.coefficient), reverse=True)
        return relationships[:top_n]

    def _analyze_pair(
        self,
        values_a: List[float],
        values_b: List[float],
        metric_a: str,
        metric_b: str,
    ) -> Relationship:
        """Analyze a single pair of metrics."""
        pearson_result = self.pearson.compute(values_a, values_b, metric_a, metric_b)
        spearman_result = self.spearman.compute(values_a, values_b, metric_a, metric_b)

        # Determine if relationship is linear
        diff = abs(spearman_result.coefficient) - abs(pearson_result.coefficient)
        is_linear = diff < 0.1

        # Recommend method
        if is_linear:
            recommended = "pearson"
            coefficient = pearson_result.coefficient
            strength = pearson_result.strength
        else:
            recommended = "spearman"
            coefficient = spearman_result.coefficient
            strength = spearman_result.strength

        direction = "positive" if coefficient > 0.05 else "negative" if coefficient < -0.05 else "none"

        interpretation = self._interpret(
            metric_a, metric_b, coefficient, strength, direction, is_linear
        )

        return Relationship(
            metric_a=metric_a,
            metric_b=metric_b,
            pearson_r=pearson_result.coefficient,
            spearman_rho=spearman_result.coefficient,
            recommended_method=recommended,
            coefficient=coefficient,
            strength=strength,
            direction=direction,
            is_linear=is_linear,
            interpretation=interpretation,
        )

    def _identify_potential_causal(
        self,
        relationships: List[Relationship],
        data: Dict[str, List[float]],
    ) -> List[Dict[str, Any]]:
        """
        Identify relationships that might suggest causality.

        Note: Correlation ≠ causation. This only flags relationships
        that merit further investigation.
        """
        potential = []

        for rel in relationships:
            if rel.strength not in ("strong", "moderate"):
                continue

            # Check for lead-lag relationship
            if rel.metric_a in data and rel.metric_b in data:
                lag_info = self._check_lead_lag(
                    data[rel.metric_a], data[rel.metric_b]
                )
                if lag_info["has_lead_lag"]:
                    potential.append({
                        "metric_a": rel.metric_a,
                        "metric_b": rel.metric_b,
                        "correlation": rel.coefficient,
                        "lead_metric": lag_info["leader"],
                        "lag_periods": lag_info["lag"],
                        "note": "Lead-lag relationship detected — may suggest directionality but not causation.",
                    })

        return potential

    def _check_lead_lag(
        self, values_a: List[float], values_b: List[float]
    ) -> Dict[str, Any]:
        """Check if one variable leads the other by testing lagged correlations."""
        arr_a = np.array(values_a, dtype=float)
        arr_b = np.array(values_b, dtype=float)
        n = min(len(arr_a), len(arr_b))

        if n < 10:
            return {"has_lead_lag": False}

        max_lag = min(5, n // 4)
        best_lag = 0
        best_corr = 0.0
        leader = None

        for lag in range(1, max_lag + 1):
            # A leads B
            corr_ab = abs(np.corrcoef(arr_a[:-lag], arr_b[lag:])[0, 1])
            if corr_ab > best_corr:
                best_corr = corr_ab
                best_lag = lag
                leader = "metric_a"

            # B leads A
            corr_ba = abs(np.corrcoef(arr_b[:-lag], arr_a[lag:])[0, 1])
            if corr_ba > best_corr:
                best_corr = corr_ba
                best_lag = lag
                leader = "metric_b"

        # Compare with zero-lag correlation
        zero_lag_corr = abs(np.corrcoef(arr_a[:n], arr_b[:n])[0, 1])

        # Only report lead-lag if it's meaningfully stronger than zero-lag
        if best_corr > zero_lag_corr + 0.1:
            return {
                "has_lead_lag": True,
                "leader": leader,
                "lag": best_lag,
                "lagged_correlation": float(best_corr),
            }

        return {"has_lead_lag": False}

    def _interpret(
        self,
        metric_a: str,
        metric_b: str,
        coefficient: float,
        strength: str,
        direction: str,
        is_linear: bool,
    ) -> str:
        """Build business-ready interpretation."""
        if strength == "negligible":
            return f"No meaningful relationship between {metric_a} and {metric_b}."

        linearity = "linear" if is_linear else "non-linear monotonic"

        return (
            f"{metric_a} and {metric_b} have a {strength} {direction} "
            f"{linearity} relationship (r={coefficient:.3f}). "
            f"When {metric_a} {'increases' if direction == 'positive' else 'decreases'}, "
            f"{metric_b} tends to {'increase' if direction == 'positive' else 'decrease'} as well."
        )

    def _build_summary(
        self,
        all_relationships: List[Relationship],
        strong: List[Relationship],
        n_metrics: int,
    ) -> str:
        """Build overall summary."""
        total_pairs = n_metrics * (n_metrics - 1) // 2

        if not all_relationships:
            return f"Analyzed {total_pairs} metric pairs — no notable correlations found."

        parts = [
            f"Analyzed {total_pairs} metric pairs. "
            f"Found {len(all_relationships)} notable relationships"
        ]

        if strong:
            parts.append(f" ({len(strong)} strong)")

        parts.append(".")

        if strong:
            top = strong[0]
            parts.append(
                f" Strongest: {top.metric_a} ↔ {top.metric_b} "
                f"(r={top.coefficient:.3f})."
            )

        return "".join(parts)
