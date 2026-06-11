"""
Contribution analysis for root cause identification.

Decomposes a metric change into contributions from individual dimensions
(e.g., which regions, products, or segments drove revenue decline).
"""
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
import numpy as np
from config import get_logger

logger = get_logger(__name__)


@dataclass
class Contributor:
    """A single contributor to a metric change."""
    dimension: str
    segment: str
    contribution: float  # Absolute contribution
    contribution_pct: float  # Percentage of total change
    current_value: float
    previous_value: float
    change: float
    direction: str  # "positive" or "negative"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension,
            "segment": self.segment,
            "contribution": round(self.contribution, 2),
            "contribution_pct": round(self.contribution_pct, 2),
            "current_value": round(self.current_value, 2),
            "previous_value": round(self.previous_value, 2),
            "change": round(self.change, 2),
            "direction": self.direction,
        }


@dataclass
class ContributionResult:
    """Result of contribution analysis."""
    metric_name: str
    total_change: float
    total_change_pct: float
    top_contributors: List[Contributor]
    dimension_analyzed: str
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "total_change": round(self.total_change, 2),
            "total_change_pct": round(self.total_change_pct, 2),
            "top_contributors": [c.to_dict() for c in self.top_contributors],
            "dimension_analyzed": self.dimension_analyzed,
            "description": self.description,
        }


class ContributionAnalyzer:
    """
    Analyzes which segments of a dimension contributed most
    to an overall metric change.

    Answers questions like:
    - "Why did revenue drop 15%?"
    - "What's driving the increase in costs?"
    """

    def analyze(
        self,
        metric_name: str,
        current_data: Dict[str, float],
        previous_data: Dict[str, float],
        dimension_name: str = "segment",
        top_n: int = 5,
    ) -> ContributionResult:
        """
        Analyze contributions to a metric change by dimension.

        Args:
            metric_name: Name of the metric being analyzed.
            current_data: Dict mapping segment names to current values.
            previous_data: Dict mapping segment names to previous values.
            dimension_name: Name of the dimension being analyzed.
            top_n: Number of top contributors to return.

        Returns:
            ContributionResult with ranked contributors.
        """
        if not current_data and not previous_data:
            return ContributionResult(
                metric_name=metric_name,
                total_change=0.0,
                total_change_pct=0.0,
                top_contributors=[],
                dimension_analyzed=dimension_name,
                description="No data provided for analysis.",
            )

        # Calculate totals
        all_segments = set(list(current_data.keys()) + list(previous_data.keys()))
        current_total = sum(current_data.values())
        previous_total = sum(previous_data.values())
        total_change = current_total - previous_total
        total_change_pct = (
            (total_change / abs(previous_total)) * 100
            if previous_total != 0
            else 0.0
        )

        # Calculate per-segment contributions
        contributors = []
        for segment in all_segments:
            curr = current_data.get(segment, 0.0)
            prev = previous_data.get(segment, 0.0)
            change = curr - prev

            contribution_pct = (
                (change / abs(total_change)) * 100
                if total_change != 0
                else 0.0
            )

            contributors.append(Contributor(
                dimension=dimension_name,
                segment=segment,
                contribution=change,
                contribution_pct=contribution_pct,
                current_value=curr,
                previous_value=prev,
                change=change,
                direction="positive" if change > 0 else "negative",
            ))

        # Sort by absolute contribution
        contributors.sort(key=lambda c: abs(c.contribution), reverse=True)
        top_contributors = contributors[:top_n]

        description = self._build_description(
            metric_name, total_change, total_change_pct,
            top_contributors, dimension_name,
        )

        logger.debug(f"Contribution analysis: {metric_name} changed {total_change_pct:.1f}%")

        return ContributionResult(
            metric_name=metric_name,
            total_change=total_change,
            total_change_pct=total_change_pct,
            top_contributors=top_contributors,
            dimension_analyzed=dimension_name,
            description=description,
        )

    def analyze_multi_dimension(
        self,
        metric_name: str,
        current_data: Dict[str, Dict[str, float]],
        previous_data: Dict[str, Dict[str, float]],
        top_n: int = 5,
    ) -> List[ContributionResult]:
        """
        Analyze contributions across multiple dimensions.

        Args:
            metric_name: Name of the metric.
            current_data: Dict[dimension_name -> Dict[segment -> value]].
            previous_data: Same structure for previous period.
            top_n: Top contributors per dimension.

        Returns:
            List of ContributionResult, one per dimension.
        """
        results = []
        for dimension in current_data:
            curr = current_data.get(dimension, {})
            prev = previous_data.get(dimension, {})
            result = self.analyze(metric_name, curr, prev, dimension, top_n)
            results.append(result)

        # Sort dimensions by total absolute change
        results.sort(key=lambda r: abs(r.total_change), reverse=True)
        return results

    def waterfall_decomposition(
        self,
        metric_name: str,
        current_data: Dict[str, float],
        previous_data: Dict[str, float],
    ) -> List[Dict[str, Any]]:
        """
        Create a waterfall chart decomposition showing how each segment
        incrementally contributed to the total change.

        Returns ordered steps for rendering a waterfall chart.
        """
        previous_total = sum(previous_data.values())
        current_total = sum(current_data.values())
        all_segments = set(list(current_data.keys()) + list(previous_data.keys()))

        steps = [{"label": "Previous Total", "value": previous_total, "type": "start"}]

        contributions = []
        for segment in all_segments:
            curr = current_data.get(segment, 0.0)
            prev = previous_data.get(segment, 0.0)
            change = curr - prev
            if change != 0:
                contributions.append({"segment": segment, "change": change})

        # Sort: positive contributions first, then negative
        contributions.sort(key=lambda c: c["change"], reverse=True)

        running = previous_total
        for item in contributions:
            running += item["change"]
            steps.append({
                "label": item["segment"],
                "value": item["change"],
                "running_total": running,
                "type": "increase" if item["change"] > 0 else "decrease",
            })

        steps.append({"label": "Current Total", "value": current_total, "type": "end"})

        return steps

    def _build_description(
        self,
        metric_name: str,
        total_change: float,
        total_change_pct: float,
        top_contributors: List[Contributor],
        dimension: str,
    ) -> str:
        """Build natural language explanation."""
        if not top_contributors:
            return f"No significant contributors to {metric_name} change."

        direction = "increased" if total_change > 0 else "decreased"
        desc = f"{metric_name} {direction} by {abs(total_change_pct):.1f}%. "

        top = top_contributors[0]
        desc += (
            f"The largest contributor was '{top.segment}' ({dimension}) "
            f"with a change of {top.change:+.2f} ({top.contribution_pct:.1f}% of total)."
        )

        if len(top_contributors) > 1:
            second = top_contributors[1]
            desc += f" Followed by '{second.segment}' ({second.contribution_pct:.1f}%)."

        return desc
