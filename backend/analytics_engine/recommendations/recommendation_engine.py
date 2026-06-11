"""
Recommendation engine for generating actionable suggestions.

Analyzes KPI health, trends, anomalies, and correlations to
produce prioritized recommendations for business users.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from config import get_logger

logger = get_logger(__name__)


class RecommendationPriority(str, Enum):
    """Priority levels for recommendations."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RecommendationType(str, Enum):
    """Types of recommendations."""
    INVESTIGATE = "investigate"
    OPTIMIZE = "optimize"
    MONITOR = "monitor"
    ALERT = "alert"
    STRATEGIC = "strategic"


@dataclass
class Recommendation:
    """A single actionable recommendation."""
    title: str
    description: str
    priority: RecommendationPriority
    type: RecommendationType
    metric: Optional[str] = None
    confidence: float = 0.7
    supporting_evidence: List[str] = field(default_factory=list)
    suggested_actions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "priority": self.priority.value,
            "type": self.type.value,
            "metric": self.metric,
            "confidence": round(self.confidence, 2),
            "supporting_evidence": self.supporting_evidence,
            "suggested_actions": self.suggested_actions,
        }


@dataclass
class RecommendationReport:
    """Collection of recommendations."""
    recommendations: List[Recommendation]
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendations": [r.to_dict() for r in self.recommendations],
            "generated_at": self.generated_at,
            "summary": self.summary,
            "total_count": len(self.recommendations),
            "critical_count": sum(1 for r in self.recommendations if r.priority == RecommendationPriority.CRITICAL),
        }


class RecommendationEngine:
    """
    Generate prioritized recommendations from analytics results.

    Analyzes multiple signals (KPI health, trends, anomalies, etc.)
    to produce actionable suggestions.
    """

    def generate(
        self,
        kpi_health: Optional[List[Dict[str, Any]]] = None,
        trend_results: Optional[List[Dict[str, Any]]] = None,
        anomaly_results: Optional[List[Dict[str, Any]]] = None,
        correlation_results: Optional[List[Dict[str, Any]]] = None,
    ) -> RecommendationReport:
        """
        Generate recommendations from analytics results.

        Args:
            kpi_health: KPI health assessment results.
            trend_results: Trend detection results.
            anomaly_results: Anomaly detection results.
            correlation_results: Correlation analysis results.

        Returns:
            RecommendationReport with prioritized recommendations.
        """
        recommendations = []

        if kpi_health:
            recommendations.extend(self._from_kpi_health(kpi_health))

        if trend_results:
            recommendations.extend(self._from_trends(trend_results))

        if anomaly_results:
            recommendations.extend(self._from_anomalies(anomaly_results))

        if correlation_results:
            recommendations.extend(self._from_correlations(correlation_results))

        # Sort by priority
        priority_order = {
            RecommendationPriority.CRITICAL: 0,
            RecommendationPriority.HIGH: 1,
            RecommendationPriority.MEDIUM: 2,
            RecommendationPriority.LOW: 3,
        }
        recommendations.sort(key=lambda r: priority_order.get(r.priority, 4))

        # Deduplicate similar recommendations
        recommendations = self._deduplicate(recommendations)

        summary = self._build_summary(recommendations)

        return RecommendationReport(
            recommendations=recommendations,
            summary=summary,
        )

    def _from_kpi_health(self, kpi_health: List[Dict[str, Any]]) -> List[Recommendation]:
        """Generate recommendations from KPI health data."""
        recs = []

        for kpi in kpi_health:
            status = kpi.get("status", "unknown")
            name = kpi.get("kpi_name", kpi.get("name", "Unknown"))
            trend = kpi.get("trend", "stable")

            if status == "critical":
                recs.append(Recommendation(
                    title=f"Urgent: {name} is critical",
                    description=f"{name} requires immediate attention — performance is critically below expectations.",
                    priority=RecommendationPriority.CRITICAL,
                    type=RecommendationType.INVESTIGATE,
                    metric=name,
                    confidence=0.9,
                    supporting_evidence=[f"Status: {status}", f"Trend: {trend}"],
                    suggested_actions=[
                        f"Investigate root cause of {name} decline",
                        "Review recent changes that may have impacted this metric",
                        "Set up alerting if not already configured",
                    ],
                ))
            elif status == "warning" and trend == "declining":
                recs.append(Recommendation(
                    title=f"Monitor: {name} is declining",
                    description=f"{name} is in warning state and declining — could become critical if trend continues.",
                    priority=RecommendationPriority.HIGH,
                    type=RecommendationType.MONITOR,
                    metric=name,
                    confidence=0.8,
                    supporting_evidence=[f"Status: {status}", f"Trend: {trend}"],
                    suggested_actions=[
                        f"Set up enhanced monitoring for {name}",
                        "Identify if decline is due to seasonality or structural issue",
                    ],
                ))
            elif trend == "declining":
                recs.append(Recommendation(
                    title=f"Watch: {name} trending down",
                    description=f"{name} is declining — monitor closely.",
                    priority=RecommendationPriority.MEDIUM,
                    type=RecommendationType.MONITOR,
                    metric=name,
                    confidence=0.7,
                    supporting_evidence=[f"Trend: {trend}"],
                    suggested_actions=[f"Review {name} drivers weekly"],
                ))

        return recs

    def _from_trends(self, trend_results: List[Dict[str, Any]]) -> List[Recommendation]:
        """Generate recommendations from trend analysis."""
        recs = []

        for trend in trend_results:
            direction = trend.get("direction", "stable")
            metric = trend.get("metric_name", "Metric")
            magnitude = trend.get("magnitude", 0)
            change_points = trend.get("change_points", [])

            if direction == "decreasing" and magnitude > 0.15:
                recs.append(Recommendation(
                    title=f"Investigate: {metric} declining rapidly",
                    description=f"{metric} has declined {magnitude:.0%} — this pace warrants investigation.",
                    priority=RecommendationPriority.HIGH,
                    type=RecommendationType.INVESTIGATE,
                    metric=metric,
                    confidence=0.8,
                    supporting_evidence=[
                        f"Direction: {direction}",
                        f"Magnitude: {magnitude:.0%}",
                    ],
                    suggested_actions=[
                        "Run root cause analysis to identify contributing factors",
                        "Compare with same period last year for seasonal context",
                    ],
                ))

            if change_points:
                recs.append(Recommendation(
                    title=f"Trend shift detected in {metric}",
                    description=f"{metric} shows {len(change_points)} trend shift(s) — may indicate a fundamental change.",
                    priority=RecommendationPriority.MEDIUM,
                    type=RecommendationType.INVESTIGATE,
                    metric=metric,
                    confidence=0.7,
                    supporting_evidence=[f"{len(change_points)} change point(s)"],
                    suggested_actions=[
                        "Identify what events coincided with the trend shift",
                        "Update forecasting models to account for the new trajectory",
                    ],
                ))

        return recs

    def _from_anomalies(self, anomaly_results: List[Dict[str, Any]]) -> List[Recommendation]:
        """Generate recommendations from anomaly detection."""
        recs = []

        for result in anomaly_results:
            count = result.get("anomaly_count", 0)
            metric = result.get("metric_name", "Metric")

            if count == 0:
                continue

            high_severity = sum(
                1 for a in result.get("anomalies", [])
                if a.get("severity") == "high"
            )

            if high_severity > 0:
                recs.append(Recommendation(
                    title=f"High-severity anomalies in {metric}",
                    description=f"{high_severity} high-severity anomalies detected in {metric}.",
                    priority=RecommendationPriority.HIGH,
                    type=RecommendationType.ALERT,
                    metric=metric,
                    confidence=0.85,
                    supporting_evidence=[
                        f"{count} total anomalies",
                        f"{high_severity} high severity",
                    ],
                    suggested_actions=[
                        "Investigate the anomalous data points for data quality issues",
                        "Determine if anomalies represent genuine business events",
                    ],
                ))
            elif count > 3:
                recs.append(Recommendation(
                    title=f"Multiple anomalies in {metric}",
                    description=f"{count} anomalies detected — may indicate instability.",
                    priority=RecommendationPriority.MEDIUM,
                    type=RecommendationType.MONITOR,
                    metric=metric,
                    confidence=0.7,
                    supporting_evidence=[f"{count} anomalies"],
                    suggested_actions=["Monitor for patterns in anomaly occurrence"],
                ))

        return recs

    def _from_correlations(self, correlation_results: List[Dict[str, Any]]) -> List[Recommendation]:
        """Generate recommendations from correlation analysis."""
        recs = []

        for rel in correlation_results:
            strength = rel.get("strength", "")
            if strength != "strong":
                continue

            metric_a = rel.get("metric_a", "")
            metric_b = rel.get("metric_b", "")
            coefficient = rel.get("coefficient", 0)

            recs.append(Recommendation(
                title=f"Strong link: {metric_a} ↔ {metric_b}",
                description=(
                    f"Strong correlation (r={coefficient:.3f}) between {metric_a} and {metric_b}. "
                    f"Changes in one likely affect the other."
                ),
                priority=RecommendationPriority.LOW,
                type=RecommendationType.STRATEGIC,
                confidence=0.75,
                supporting_evidence=[f"Correlation: {coefficient:.3f}"],
                suggested_actions=[
                    f"Consider {metric_a} as a leading indicator for {metric_b}",
                    "Investigate potential causal mechanisms",
                ],
            ))

        return recs

    def _deduplicate(self, recs: List[Recommendation]) -> List[Recommendation]:
        """Remove duplicate recommendations about the same metric/issue."""
        seen_keys = set()
        unique = []

        for rec in recs:
            key = f"{rec.metric}:{rec.type.value}"
            if key not in seen_keys:
                seen_keys.add(key)
                unique.append(rec)

        return unique

    def _build_summary(self, recs: List[Recommendation]) -> str:
        """Build a summary of all recommendations."""
        if not recs:
            return "No recommendations at this time — all metrics are performing as expected."

        critical = sum(1 for r in recs if r.priority == RecommendationPriority.CRITICAL)
        high = sum(1 for r in recs if r.priority == RecommendationPriority.HIGH)

        parts = [f"{len(recs)} recommendations generated."]
        if critical:
            parts.append(f" {critical} require immediate action.")
        if high:
            parts.append(f" {high} are high priority.")

        return "".join(parts)
