"""
Isolation Forest anomaly detection.

Provides a production-ready wrapper around scikit-learn's Isolation Forest
with support for univariate and multivariate data, automatic contamination
estimation, and enriched result metadata.
"""
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
import numpy as np
from config import get_logger

logger = get_logger(__name__)


@dataclass
class AnomalyPoint:
    """A detected anomaly with context."""
    index: int
    value: float
    anomaly_score: float  # -1 (most anomalous) to 1 (most normal)
    severity: str  # "low", "medium", "high"
    deviation: float  # How far from expected

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "value": round(self.value, 4),
            "anomaly_score": round(self.anomaly_score, 4),
            "severity": self.severity,
            "deviation": round(self.deviation, 4),
        }


@dataclass
class IsolationForestResult:
    """Result of Isolation Forest anomaly detection."""
    anomalies: List[AnomalyPoint]
    total_points: int
    anomaly_count: int
    contamination_used: float
    model_fitted: bool
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "anomalies": [a.to_dict() for a in self.anomalies],
            "total_points": self.total_points,
            "anomaly_count": self.anomaly_count,
            "contamination_used": self.contamination_used,
            "model_fitted": self.model_fitted,
            "description": self.description,
        }


class IsolationForestDetector:
    """
    Isolation Forest anomaly detector.

    Works by isolating observations — anomalies are easier to isolate
    and thus have shorter average path lengths in the tree structure.
    """

    def __init__(
        self,
        contamination: Optional[float] = None,
        n_estimators: int = 100,
        random_state: int = 42,
    ):
        """
        Args:
            contamination: Expected proportion of anomalies (0.0-0.5).
                If None, will be auto-estimated.
            n_estimators: Number of isolation trees.
            random_state: Random seed for reproducibility.
        """
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.random_state = random_state

    def detect(
        self,
        values: List[float],
        timestamps: Optional[List[str]] = None,
    ) -> IsolationForestResult:
        """
        Detect anomalies using Isolation Forest.

        Args:
            values: Numeric values to analyze.
            timestamps: Optional timestamps for context.

        Returns:
            IsolationForestResult with detected anomalies.
        """
        if len(values) < 10:
            return IsolationForestResult(
                anomalies=[],
                total_points=len(values),
                anomaly_count=0,
                contamination_used=0.0,
                model_fitted=False,
                description="Insufficient data for Isolation Forest (need at least 10 points).",
            )

        try:
            from sklearn.ensemble import IsolationForest
        except ImportError:
            logger.warning("scikit-learn not available, falling back to Z-score based detection")
            return self._fallback_zscore(values)

        arr = np.array(values, dtype=float).reshape(-1, 1)

        # Auto-estimate contamination if not provided
        contamination = self.contamination or self._estimate_contamination(values)

        # Fit model
        model = IsolationForest(
            contamination=contamination,
            n_estimators=self.n_estimators,
            random_state=self.random_state,
        )
        predictions = model.fit_predict(arr)
        scores = model.decision_function(arr)

        # Build anomaly points
        mean_val = np.mean(arr)
        std_val = np.std(arr)
        anomalies = []

        for i, (pred, score) in enumerate(zip(predictions, scores)):
            if pred == -1:  # Anomaly
                deviation = abs(values[i] - mean_val) / std_val if std_val > 0 else 0
                severity = self._score_severity(score)

                anomalies.append(AnomalyPoint(
                    index=i,
                    value=values[i],
                    anomaly_score=float(score),
                    severity=severity,
                    deviation=float(deviation),
                ))

        # Sort by severity (most anomalous first)
        anomalies.sort(key=lambda a: a.anomaly_score)

        description = self._build_description(anomalies, len(values), contamination)

        logger.debug(f"Isolation Forest: {len(anomalies)}/{len(values)} anomalies detected")

        return IsolationForestResult(
            anomalies=anomalies,
            total_points=len(values),
            anomaly_count=len(anomalies),
            contamination_used=contamination,
            model_fitted=True,
            description=description,
        )

    def detect_multivariate(
        self,
        data: List[List[float]],
        feature_names: Optional[List[str]] = None,
    ) -> IsolationForestResult:
        """
        Detect anomalies in multivariate data.

        Args:
            data: List of feature vectors (each inner list is one observation).
            feature_names: Names of features for reporting.

        Returns:
            IsolationForestResult with detected anomalies.
        """
        if len(data) < 10:
            return IsolationForestResult(
                anomalies=[],
                total_points=len(data),
                anomaly_count=0,
                contamination_used=0.0,
                model_fitted=False,
                description="Insufficient data for multivariate anomaly detection.",
            )

        try:
            from sklearn.ensemble import IsolationForest
        except ImportError:
            return IsolationForestResult(
                anomalies=[],
                total_points=len(data),
                anomaly_count=0,
                contamination_used=0.0,
                model_fitted=False,
                description="scikit-learn not available for multivariate detection.",
            )

        arr = np.array(data, dtype=float)
        contamination = self.contamination or 0.05

        model = IsolationForest(
            contamination=contamination,
            n_estimators=self.n_estimators,
            random_state=self.random_state,
        )
        predictions = model.fit_predict(arr)
        scores = model.decision_function(arr)

        # For multivariate, value is the L2 norm from center
        center = np.mean(arr, axis=0)
        anomalies = []

        for i, (pred, score) in enumerate(zip(predictions, scores)):
            if pred == -1:
                distance = float(np.linalg.norm(arr[i] - center))
                anomalies.append(AnomalyPoint(
                    index=i,
                    value=distance,
                    anomaly_score=float(score),
                    severity=self._score_severity(score),
                    deviation=distance,
                ))

        anomalies.sort(key=lambda a: a.anomaly_score)

        return IsolationForestResult(
            anomalies=anomalies,
            total_points=len(data),
            anomaly_count=len(anomalies),
            contamination_used=contamination,
            model_fitted=True,
            description=f"Multivariate detection: {len(anomalies)} anomalies in {arr.shape[1]}-dimensional data.",
        )

    def _estimate_contamination(self, values: List[float]) -> float:
        """Auto-estimate contamination rate from data."""
        arr = np.array(values)
        # Use IQR to estimate expected anomaly fraction
        q1, q3 = np.percentile(arr, [25, 75])
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr

        outlier_count = np.sum((arr < lower) | (arr > upper))
        estimated = outlier_count / len(arr)

        # Clamp between 0.01 and 0.2
        return float(np.clip(estimated, 0.01, 0.2))

    def _score_severity(self, anomaly_score: float) -> str:
        """Convert anomaly score to severity level."""
        # Scores closer to -1 are more anomalous
        if anomaly_score < -0.3:
            return "high"
        if anomaly_score < -0.1:
            return "medium"
        return "low"

    def _fallback_zscore(self, values: List[float]) -> IsolationForestResult:
        """Fallback detection using Z-scores when sklearn is unavailable."""
        arr = np.array(values, dtype=float)
        mean = np.mean(arr)
        std = np.std(arr)

        if std == 0:
            return IsolationForestResult(
                anomalies=[],
                total_points=len(values),
                anomaly_count=0,
                contamination_used=0.0,
                model_fitted=False,
                description="No variance in data.",
            )

        anomalies = []
        threshold = 2.5

        for i, val in enumerate(values):
            zscore = abs(val - mean) / std
            if zscore > threshold:
                anomalies.append(AnomalyPoint(
                    index=i,
                    value=val,
                    anomaly_score=-zscore / 10,
                    severity="high" if zscore > 4 else "medium" if zscore > 3 else "low",
                    deviation=float(zscore),
                ))

        return IsolationForestResult(
            anomalies=anomalies,
            total_points=len(values),
            anomaly_count=len(anomalies),
            contamination_used=0.0,
            model_fitted=False,
            description=f"Z-score fallback: {len(anomalies)} anomalies (threshold={threshold}).",
        )

    def _build_description(
        self, anomalies: List[AnomalyPoint], total: int, contamination: float
    ) -> str:
        """Build a description of the detection results."""
        if not anomalies:
            return f"No anomalies detected in {total} data points."

        high = sum(1 for a in anomalies if a.severity == "high")
        med = sum(1 for a in anomalies if a.severity == "medium")
        low = sum(1 for a in anomalies if a.severity == "low")

        parts = [f"Detected {len(anomalies)} anomalies in {total} data points"]
        severity_parts = []
        if high:
            severity_parts.append(f"{high} high")
        if med:
            severity_parts.append(f"{med} medium")
        if low:
            severity_parts.append(f"{low} low")

        if severity_parts:
            parts.append(f" ({', '.join(severity_parts)} severity)")

        return "".join(parts) + "."
