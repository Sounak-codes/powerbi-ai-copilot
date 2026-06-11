"""
Z-Score based anomaly detection.

Simple, fast, and interpretable method that identifies data points
significantly deviating from the statistical mean.
"""
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
import numpy as np
from config import get_logger

logger = get_logger(__name__)


@dataclass
class ZScoreAnomaly:
    """An anomaly detected via Z-Score."""
    index: int
    value: float
    zscore: float
    direction: str  # "above" or "below"
    severity: str   # "low", "medium", "high"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "value": round(self.value, 4),
            "zscore": round(self.zscore, 3),
            "direction": self.direction,
            "severity": self.severity,
        }


@dataclass
class ZScoreResult:
    """Result of Z-Score anomaly detection."""
    anomalies: List[ZScoreAnomaly]
    mean: float
    std: float
    threshold: float
    total_points: int
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "anomalies": [a.to_dict() for a in self.anomalies],
            "mean": round(self.mean, 4),
            "std": round(self.std, 4),
            "threshold": self.threshold,
            "total_points": self.total_points,
            "anomaly_count": len(self.anomalies),
            "description": self.description,
        }


class ZScoreDetector:
    """
    Z-Score based anomaly detector.

    Flags data points that are more than N standard deviations
    from the mean. Supports both static and rolling window methods.
    """

    def __init__(self, threshold: float = 3.0):
        """
        Args:
            threshold: Z-score threshold for anomaly detection.
                Common values: 2.0 (5% expected), 2.5 (1%), 3.0 (0.3%).
        """
        self.threshold = threshold

    def detect(self, values: List[float]) -> ZScoreResult:
        """
        Detect anomalies using global Z-Score.

        Args:
            values: Numeric values to analyze.

        Returns:
            ZScoreResult with detected anomalies and statistics.
        """
        if len(values) < 3:
            return ZScoreResult(
                anomalies=[],
                mean=0.0,
                std=0.0,
                threshold=self.threshold,
                total_points=len(values),
                description="Insufficient data for Z-score detection.",
            )

        arr = np.array(values, dtype=float)
        mean = float(np.mean(arr))
        std = float(np.std(arr))

        if std == 0:
            return ZScoreResult(
                anomalies=[],
                mean=mean,
                std=0.0,
                threshold=self.threshold,
                total_points=len(values),
                description="No variance in data — all values are identical.",
            )

        anomalies = []
        for i, val in enumerate(values):
            zscore = (val - mean) / std
            if abs(zscore) > self.threshold:
                anomalies.append(ZScoreAnomaly(
                    index=i,
                    value=val,
                    zscore=float(zscore),
                    direction="above" if zscore > 0 else "below",
                    severity=self._classify_severity(abs(zscore)),
                ))

        # Sort by absolute Z-score descending
        anomalies.sort(key=lambda a: abs(a.zscore), reverse=True)

        description = self._build_description(anomalies, len(values), mean, std)

        return ZScoreResult(
            anomalies=anomalies,
            mean=mean,
            std=std,
            threshold=self.threshold,
            total_points=len(values),
            description=description,
        )

    def detect_rolling(
        self,
        values: List[float],
        window_size: int = 20,
    ) -> ZScoreResult:
        """
        Detect anomalies using a rolling window Z-Score.

        Better for data with shifting baselines where a global mean
        is not representative. Each point is compared to its local window.

        Args:
            values: Numeric values to analyze.
            window_size: Number of preceding points for the rolling window.

        Returns:
            ZScoreResult with detected anomalies.
        """
        n = len(values)
        if n < window_size + 1:
            return self.detect(values)

        arr = np.array(values, dtype=float)
        anomalies = []

        for i in range(window_size, n):
            window = arr[i - window_size : i]
            local_mean = np.mean(window)
            local_std = np.std(window)

            if local_std == 0:
                continue

            zscore = (arr[i] - local_mean) / local_std

            if abs(zscore) > self.threshold:
                anomalies.append(ZScoreAnomaly(
                    index=i,
                    value=float(arr[i]),
                    zscore=float(zscore),
                    direction="above" if zscore > 0 else "below",
                    severity=self._classify_severity(abs(zscore)),
                ))

        anomalies.sort(key=lambda a: abs(a.zscore), reverse=True)
        global_mean = float(np.mean(arr))
        global_std = float(np.std(arr))

        return ZScoreResult(
            anomalies=anomalies,
            mean=global_mean,
            std=global_std,
            threshold=self.threshold,
            total_points=n,
            description=f"Rolling Z-score (window={window_size}): {len(anomalies)} anomalies detected.",
        )

    def get_expected_range(self, values: List[float]) -> Tuple[float, float]:
        """
        Calculate the expected normal range for the data.

        Returns (lower_bound, upper_bound) based on mean ± threshold*std.
        """
        arr = np.array(values, dtype=float)
        mean = float(np.mean(arr))
        std = float(np.std(arr))
        return (mean - self.threshold * std, mean + self.threshold * std)

    def _classify_severity(self, abs_zscore: float) -> str:
        """Classify anomaly severity based on Z-score magnitude."""
        if abs_zscore > 4.0:
            return "high"
        if abs_zscore > 3.0:
            return "medium"
        return "low"

    def _build_description(
        self,
        anomalies: List[ZScoreAnomaly],
        total: int,
        mean: float,
        std: float,
    ) -> str:
        """Build description of Z-score results."""
        if not anomalies:
            return (
                f"No anomalies detected (threshold={self.threshold}σ). "
                f"Data: mean={mean:.2f}, std={std:.2f}."
            )

        above = sum(1 for a in anomalies if a.direction == "above")
        below = len(anomalies) - above

        parts = [f"{len(anomalies)} anomalies detected in {total} points"]
        if above and below:
            parts.append(f" ({above} above, {below} below)")
        elif above:
            parts.append(f" (all above mean)")
        else:
            parts.append(f" (all below mean)")

        return "".join(parts) + f". Threshold: {self.threshold}σ."
