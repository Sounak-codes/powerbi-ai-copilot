"""
Narrative builder for generating data-driven stories.

Converts raw analytics results into coherent, readable narratives
that explain what happened, why, and what to do about it.
"""
from typing import Dict, Any, List, Optional
from config import get_logger

logger = get_logger(__name__)


class NarrativeBuilder:
    """
    Build narratives from analytics data.

    Creates structured, readable text that tells the story behind
    the numbers — suitable for reports, emails, or chat responses.
    """

    def build_trend_narrative(
        self,
        metric_name: str,
        direction: str,
        magnitude: float,
        period_count: int,
        change_points: Optional[List[int]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Build a narrative for a trend analysis result.

        Args:
            metric_name: Name of the metric.
            direction: Trend direction.
            magnitude: Magnitude of change (as fraction).
            period_count: Number of periods analyzed.
            change_points: Indices where trend shifted.
            context: Additional context.

        Returns:
            Natural language narrative.
        """
        parts = []

        # Opening
        if direction == "increasing":
            if magnitude > 0.2:
                parts.append(f"{metric_name} has shown strong growth")
            else:
                parts.append(f"{metric_name} has been trending upward")
        elif direction == "decreasing":
            if magnitude > 0.2:
                parts.append(f"{metric_name} has declined significantly")
            else:
                parts.append(f"{metric_name} has been gradually declining")
        elif direction == "volatile":
            parts.append(f"{metric_name} has been fluctuating significantly")
        else:
            parts.append(f"{metric_name} has remained relatively stable")

        parts.append(f" over the past {period_count} periods")
        parts.append(f" ({magnitude:.1%} total change).")

        # Change points
        if change_points:
            parts.append(
                f" There {'was' if len(change_points) == 1 else 'were'} "
                f"{len(change_points)} notable shift{'s' if len(change_points) > 1 else ''} "
                f"in the trend during this period."
            )

        return "".join(parts)

    def build_anomaly_narrative(
        self,
        metric_name: str,
        anomaly_count: int,
        severity_breakdown: Dict[str, int],
        top_anomalies: List[Dict[str, Any]],
    ) -> str:
        """Build a narrative for anomaly detection results."""
        if anomaly_count == 0:
            return f"No anomalies were detected in {metric_name}. Values are within expected ranges."

        parts = []

        # Opening
        if anomaly_count == 1:
            parts.append(f"One anomalous data point was detected in {metric_name}.")
        else:
            parts.append(f"{anomaly_count} anomalous data points were detected in {metric_name}.")

        # Severity
        high = severity_breakdown.get("high", 0)
        medium = severity_breakdown.get("medium", 0)
        if high:
            parts.append(f" {high} of these are high-severity and require attention.")
        elif medium:
            parts.append(f" {medium} are of medium severity.")

        # Top anomaly details
        if top_anomalies:
            top = top_anomalies[0]
            value = top.get("value", 0)
            parts.append(f" The most significant anomaly had a value of {value:.2f}.")

        return "".join(parts)

    def build_contribution_narrative(
        self,
        metric_name: str,
        total_change: float,
        total_change_pct: float,
        top_contributors: List[Dict[str, Any]],
        dimension: str,
    ) -> str:
        """Build a narrative for contribution analysis results."""
        direction = "increase" if total_change > 0 else "decrease"

        parts = [
            f"{metric_name} {direction}d by {abs(total_change_pct):.1f}%. "
        ]

        if not top_contributors:
            parts.append("No clear individual contributors were identified.")
            return "".join(parts)

        # Top contributor
        top = top_contributors[0]
        segment = top.get("segment", "Unknown")
        contribution_pct = top.get("contribution_pct", 0)

        parts.append(
            f"The primary driver was '{segment}' in the {dimension} dimension, "
            f"accounting for {abs(contribution_pct):.0f}% of the total change."
        )

        # Secondary contributors
        if len(top_contributors) > 1:
            others = [c.get("segment", "") for c in top_contributors[1:3]]
            parts.append(f" Other notable contributors: {', '.join(others)}.")

        return "".join(parts)

    def build_correlation_narrative(
        self,
        relationships: List[Dict[str, Any]],
        target_metric: Optional[str] = None,
    ) -> str:
        """Build a narrative for correlation analysis results."""
        if not relationships:
            return "No significant correlations were found between the analyzed metrics."

        parts = []

        strong = [r for r in relationships if r.get("strength") == "strong"]
        moderate = [r for r in relationships if r.get("strength") == "moderate"]

        if target_metric:
            parts.append(f"Analyzing relationships with {target_metric}: ")
        else:
            parts.append("Cross-metric analysis reveals: ")

        if strong:
            r = strong[0]
            direction = "positive" if r.get("coefficient", 0) > 0 else "negative"
            parts.append(
                f"a strong {direction} correlation between "
                f"{r.get('metric_a', '')} and {r.get('metric_b', '')} "
                f"(r={r.get('coefficient', 0):.3f})"
            )
            if len(strong) > 1:
                parts.append(f" and {len(strong) - 1} other strong relationship(s)")
            parts.append(".")
        elif moderate:
            parts.append(
                f"{len(moderate)} moderate correlation(s) detected, "
                f"the strongest between {moderate[0].get('metric_a', '')} "
                f"and {moderate[0].get('metric_b', '')}."
            )
        else:
            parts.append("only weak relationships detected.")

        return "".join(parts)

    def build_composite_narrative(
        self,
        sections: List[Dict[str, Any]],
    ) -> str:
        """
        Build a multi-section narrative combining multiple analyses.

        Args:
            sections: List of dicts with keys "title" and "content".

        Returns:
            Combined narrative with section headers.
        """
        parts = []

        for section in sections:
            title = section.get("title", "")
            content = section.get("content", "")
            if title:
                parts.append(f"**{title}**\n{content}")
            else:
                parts.append(content)

        return "\n\n".join(parts)
