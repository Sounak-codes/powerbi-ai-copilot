"""
KPI health assessment.

Evaluates the health of key performance indicators based on
current values, targets, trends, and thresholds.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
from config import get_logger

logger = get_logger(__name__)


class HealthStatus(str, Enum):
    """KPI health status levels."""
    CRITICAL = "critical"
    WARNING = "warning"
    HEALTHY = "healthy"
    EXCELLENT = "excellent"
    UNKNOWN = "unknown"


@dataclass
class KPIHealth:
    """Health assessment for a single KPI."""
    kpi_name: str
    current_value: float
    target_value: Optional[float] = None
    previous_value: Optional[float] = None
    status: HealthStatus = HealthStatus.UNKNOWN
    score: float = 0.0  # 0-100
    trend: str = "stable"  # "improving", "declining", "stable"
    gap_to_target: Optional[float] = None
    time_to_target: Optional[int] = None  # Estimated periods to reach target
    alerts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kpi_name": self.kpi_name,
            "current_value": round(self.current_value, 2),
            "target_value": self.target_value,
            "previous_value": self.previous_value,
            "status": self.status.value,
            "score": round(self.score, 1),
            "trend": self.trend,
            "gap_to_target": round(self.gap_to_target, 2) if self.gap_to_target is not None else None,
            "time_to_target": self.time_to_target,
            "alerts": self.alerts,
        }


@dataclass
class KPIHealthReport:
    """Aggregate KPI health report."""
    kpis: List[KPIHealth]
    overall_health: HealthStatus
    overall_score: float
    critical_count: int
    warning_count: int
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kpis": [k.to_dict() for k in self.kpis],
            "overall_health": self.overall_health.value,
            "overall_score": round(self.overall_score, 1),
            "critical_count": self.critical_count,
            "warning_count": self.warning_count,
            "summary": self.summary,
        }


class KPIHealthAssessor:
    """
    Assess the health of KPIs based on current performance,
    targets, and historical trends.
    """

    def assess(
        self,
        kpi_name: str,
        current_value: float,
        target_value: Optional[float] = None,
        previous_value: Optional[float] = None,
        historical_values: Optional[List[float]] = None,
        higher_is_better: bool = True,
        thresholds: Optional[Dict[str, float]] = None,
    ) -> KPIHealth:
        """
        Assess health of a single KPI.

        Args:
            kpi_name: Name of the KPI.
            current_value: Current KPI value.
            target_value: Target/goal value (optional).
            previous_value: Previous period value (optional).
            historical_values: Time series of historical values.
            higher_is_better: Whether higher values are better.
            thresholds: Custom thresholds dict with keys "critical", "warning", "excellent".

        Returns:
            KPIHealth assessment.
        """
        health = KPIHealth(
            kpi_name=kpi_name,
            current_value=current_value,
            target_value=target_value,
            previous_value=previous_value,
        )

        # Determine trend
        if historical_values and len(historical_values) >= 3:
            health.trend = self._assess_trend(historical_values, higher_is_better)
        elif previous_value is not None:
            if higher_is_better:
                health.trend = "improving" if current_value > previous_value else "declining" if current_value < previous_value else "stable"
            else:
                health.trend = "improving" if current_value < previous_value else "declining" if current_value > previous_value else "stable"

        # Calculate score and status
        if target_value is not None:
            health.score = self._score_against_target(
                current_value, target_value, higher_is_better
            )
            health.gap_to_target = target_value - current_value if higher_is_better else current_value - target_value
        elif thresholds:
            health.score = self._score_with_thresholds(
                current_value, thresholds, higher_is_better
            )
        elif historical_values:
            health.score = self._score_relative_to_history(
                current_value, historical_values, higher_is_better
            )
        else:
            health.score = 50.0  # Unknown baseline

        health.status = self._status_from_score(health.score)

        # Estimate time to target
        if target_value is not None and historical_values and len(historical_values) >= 3:
            health.time_to_target = self._estimate_time_to_target(
                historical_values, target_value, higher_is_better
            )

        # Generate alerts
        health.alerts = self._generate_alerts(health, higher_is_better)

        return health

    def assess_multiple(
        self,
        kpi_configs: List[Dict[str, Any]],
    ) -> KPIHealthReport:
        """
        Assess health of multiple KPIs and produce an aggregate report.

        Args:
            kpi_configs: List of config dicts, each passed to assess().

        Returns:
            KPIHealthReport with individual and aggregate assessments.
        """
        assessments = [self.assess(**config) for config in kpi_configs]

        scores = [a.score for a in assessments]
        overall_score = float(np.mean(scores)) if scores else 0.0

        critical = sum(1 for a in assessments if a.status == HealthStatus.CRITICAL)
        warning = sum(1 for a in assessments if a.status == HealthStatus.WARNING)

        if critical > 0:
            overall = HealthStatus.CRITICAL
        elif warning > len(assessments) * 0.3:
            overall = HealthStatus.WARNING
        elif overall_score >= 80:
            overall = HealthStatus.EXCELLENT
        else:
            overall = HealthStatus.HEALTHY

        summary = self._build_report_summary(assessments, overall_score, critical, warning)

        return KPIHealthReport(
            kpis=assessments,
            overall_health=overall,
            overall_score=overall_score,
            critical_count=critical,
            warning_count=warning,
            summary=summary,
        )

    def _score_against_target(
        self, current: float, target: float, higher_is_better: bool
    ) -> float:
        """Score KPI as percentage of target achieved."""
        if target == 0:
            return 50.0

        if higher_is_better:
            ratio = current / target
        else:
            ratio = target / current if current != 0 else 0

        # Scale: 100% of target = score 80, 120% = 100, <50% = 20
        score = ratio * 80
        return float(np.clip(score, 0, 100))

    def _score_with_thresholds(
        self, current: float, thresholds: Dict[str, float], higher_is_better: bool
    ) -> float:
        """Score using custom thresholds."""
        critical = thresholds.get("critical", 0)
        warning = thresholds.get("warning", 0)
        excellent = thresholds.get("excellent", 100)

        if higher_is_better:
            if current >= excellent:
                return 95.0
            if current >= warning:
                return 70.0
            if current >= critical:
                return 40.0
            return 15.0
        else:
            if current <= excellent:
                return 95.0
            if current <= warning:
                return 70.0
            if current <= critical:
                return 40.0
            return 15.0

    def _score_relative_to_history(
        self, current: float, history: List[float], higher_is_better: bool
    ) -> float:
        """Score relative to historical performance."""
        arr = np.array(history)
        percentile = float(np.sum(arr <= current) / len(arr) * 100)

        if not higher_is_better:
            percentile = 100 - percentile

        return percentile

    def _assess_trend(self, values: List[float], higher_is_better: bool) -> str:
        """Assess trend from recent values."""
        if len(values) < 3:
            return "stable"

        recent = values[-5:]
        x = np.arange(len(recent))
        slope = np.polyfit(x, recent, 1)[0]

        # Normalize by mean
        mean = np.mean(recent)
        normalized_slope = slope / abs(mean) if mean != 0 else 0

        threshold = 0.01

        if higher_is_better:
            if normalized_slope > threshold:
                return "improving"
            if normalized_slope < -threshold:
                return "declining"
        else:
            if normalized_slope < -threshold:
                return "improving"
            if normalized_slope > threshold:
                return "declining"

        return "stable"

    def _estimate_time_to_target(
        self, history: List[float], target: float, higher_is_better: bool
    ) -> Optional[int]:
        """Estimate periods needed to reach target at current rate."""
        recent = history[-5:]
        if len(recent) < 2:
            return None

        x = np.arange(len(recent))
        slope = np.polyfit(x, recent, 1)[0]

        current = recent[-1]
        gap = target - current if higher_is_better else current - target

        if gap <= 0:
            return 0  # Already at/past target

        if higher_is_better and slope <= 0:
            return None  # Moving away from target
        if not higher_is_better and slope >= 0:
            return None

        effective_slope = abs(slope)
        if effective_slope == 0:
            return None

        periods = int(np.ceil(gap / effective_slope))
        return periods if periods < 365 else None

    def _status_from_score(self, score: float) -> HealthStatus:
        """Convert numeric score to health status."""
        if score >= 80:
            return HealthStatus.EXCELLENT
        if score >= 60:
            return HealthStatus.HEALTHY
        if score >= 35:
            return HealthStatus.WARNING
        return HealthStatus.CRITICAL

    def _generate_alerts(self, health: KPIHealth, higher_is_better: bool) -> List[str]:
        """Generate contextual alerts for the KPI."""
        alerts = []

        if health.status == HealthStatus.CRITICAL:
            alerts.append(f"CRITICAL: {health.kpi_name} requires immediate attention.")

        if health.trend == "declining":
            alerts.append(f"{health.kpi_name} has been declining — investigate root cause.")

        if health.gap_to_target is not None and health.gap_to_target > 0:
            pct = (health.gap_to_target / health.target_value * 100) if health.target_value else 0
            if pct > 20:
                alerts.append(f"{health.kpi_name} is {pct:.0f}% below target.")

        if health.time_to_target is None and health.gap_to_target and health.gap_to_target > 0:
            alerts.append(f"{health.kpi_name} is not trending toward target.")

        return alerts

    def _build_report_summary(
        self,
        assessments: List[KPIHealth],
        overall_score: float,
        critical: int,
        warning: int,
    ) -> str:
        """Build aggregate summary."""
        total = len(assessments)
        healthy = total - critical - warning

        parts = [f"KPI Health Report: {total} KPIs assessed (score: {overall_score:.0f}/100)."]

        if critical:
            names = [a.kpi_name for a in assessments if a.status == HealthStatus.CRITICAL]
            parts.append(f" {critical} CRITICAL: {', '.join(names)}.")

        if warning:
            parts.append(f" {warning} in WARNING state.")

        if healthy == total:
            parts.append(" All KPIs are healthy.")

        return "".join(parts)
