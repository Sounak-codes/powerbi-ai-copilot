"""
Interquartile Range (IQR) anomaly detection.

Robust non-parametric method that doesn't assume normal distribution.
Effective for skewed data and resistant to extreme outliers affecting
the detection boundary.
"""
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
import numpy as np
from config import get_logger

logger = get_logger(__name__)


@dataclass
class IQRAnomaly:
    """An anomaly detected via IQR method."""
    index: int
    value: float
    distance_from_fence: float  # How far past the IQR fence
    direction: str  # "upper" or "lower"
    severity: str   # "mild" (1.5x IQR) or "extreme" (3x IQR)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "value": round(self.value, 4),
            "distance_from_fence": round(self.distance_from_fence, 4),
            "direction": self.direction,
            "severity": self.severity,
        }


@dataclass
class IQRResult:
    """Result of IQR anomaly detection."""
    anomalies: List[IQRAnomaly]
    q1: float
    q3: float
    iqr: float
    lower_fence: float
    upper_fence: float
    lower_extreme_fence: float
    upper_extreme_fence: float
    total_points: int
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "anomalies": [a.to_dict() for a in self.anomalies],
            "q1": round(self.q1, 4),
            "q3": round(self.q3, 4),
            "iqr": round(self.iqr, 4),
            "lower_fence": round(self.lower_fence, 4),
            "upper_fence": round(self.upper_fence, 4),
            "total_points": self.total_points,
            "anomaly_count": len(self.anomalies),
            "mild_outliers": sum(1 for a in self.anomalies if a.severity == "mild"),
            "extreme_outliers": sum(1 for a in self.anomalies if a.severity == "extreme"),
            "description": self.description,
        }


class IQRDetector:
    """
    IQR-based anomaly detector.

    Uses the interquartile range to define "fences" beyond which
    data points are considered outliers. Standard fences are at
    Q1 - 1.5*IQR and Q3 + 1.5*IQR. Extreme fences at 3*IQR.
    """

    def __init__(self, multiplier: float = 1.5):
        """
        Args:
            multiplier: IQR multiplier for fence calculation.
                1.5 is standard (Tukey's rule), lower = more sensitive.
        """
        self.multiplier = multiplier
        self.extreme_multiplier = 3.0

    def detect(self, values: List[float]) -> IQRResult:
        """
        Detect anomalies using IQR method.

        Args:
            values: Numeric values to analyze.

        Returns:
            IQRResult with detected anomalies and quartile statistics.
        """
        if len(values) < 4:
            return IQRResult(
                anomalies=[],
                q1=0.0, q3=0.0, iqr=0.0,
                lower_fence=0.0, upper_fence=0.0,
                lower_extreme_fence=0.0, upper_extreme_fence=0.0,
                total_points=len(values),
                description="Insufficient data for IQR detection (need at least 4 points).",
            )

        arr = np.array(values, dtype=float)
        q1 = float(np.percentile(arr, 25))
        q3 = float(np.percentile(arr, 75))
        iqr = q3 - q1

        if iqr == 0:
            # Fallback: use a small epsilon based on data range
            data_range = float(np.max(arr) - np.min(arr))
            if data_range == 0:
                return IQRResult(
                    anomalies=[], q1=q1, q3=q3, iqr=0.0,
                    lower_fence=q1, upper_fence=q3,
                    lower_extreme_fence=q1, upper_extreme_fence=q3,
                    total_points=len(values),
                    description="IQR is zero — data has no spread in the middle 50%.",
                )
            iqr = data_range * 0.1  # Use 10% of range as proxy

        lower_fence = q1 - self.multiplier * iqr
        upper_fence = q3 + self.multiplier * iqr
        lower_extreme = q1 - self.extreme_multiplier * iqr
        upper_extreme = q3 + self.extreme_multiplier * iqr

        anomalies = []
        for i, val in enumerate(values):
            if val < lower_fence or val > upper_fence:
                # Determine direction
                if val < lower_fence:
                    direction = "lower"
                    distance = lower_fence - val
                    is_extreme = val < lower_extreme
                else:
                    direction = "upper"
                    distance = val - upper_fence
                    is_extreme = val > upper_extreme

                anomalies.append(IQRAnomaly(
                    index=i,
                    value=val,
                    distance_from_fence=float(distance),
                    direction=direction,
                    severity="extreme" if is_extreme else "mild",
                ))

        # Sort by distance from fence (most extreme first)
        anomalies.sort(key=lambda a: a.distance_from_fence, reverse=True)

        description = self._build_description(anomalies, len(values), q1, q3, iqr)

        return IQRResult(
            anomalies=anomalies,
            q1=q1,
            q3=q3,
            iqr=iqr,
            lower_fence=lower_fence,
            upper_fence=upper_fence,
            lower_extreme_fence=lower_extreme,
            upper_extreme_fence=upper_extreme,
            total_points=len(values),
            description=description,
        )

    def detect_by_group(
        self,
        values: List[float],
        groups: List[str],
    ) -> Dict[str, IQRResult]:
        """
        Detect anomalies within each group separately.

        Useful when different categories have different normal ranges.

        Args:
            values: Numeric values.
            groups: Group label for each value (same length as values).

        Returns:
            Dictionary mapping group name to IQRResult.
        """
        grouped: Dict[str, List[Tuple[int, float]]] = {}

        for i, (val, group) in enumerate(zip(values, groups)):
            if group not in grouped:
                grouped[group] = []
            grouped[group].append((i, val))

        results = {}
        for group_name, entries in grouped.items():
            group_values = [v for _, v in entries]
            result = self.detect(group_values)

            # Re-map indices to original positions
            index_map = {local_i: orig_i for local_i, (orig_i, _) in enumerate(entries)}
            for anomaly in result.anomalies:
                anomaly.index = index_map.get(anomaly.index, anomaly.index)

            results[group_name] = result

        return results

    def get_box_plot_stats(self, values: List[float]) -> Dict[str, float]:
        """
        Get full box plot statistics for visualization.

        Returns all values needed to render a box-and-whisker plot.
        """
        arr = np.array(values, dtype=float)
        q1 = float(np.percentile(arr, 25))
        q3 = float(np.percentile(arr, 75))
        iqr = q3 - q1
        median = float(np.median(arr))

        lower_fence = q1 - self.multiplier * iqr
        upper_fence = q3 + self.multiplier * iqr

        # Whiskers extend to the last non-outlier point
        lower_whisker = float(np.min(arr[arr >= lower_fence])) if np.any(arr >= lower_fence) else lower_fence
        upper_whisker = float(np.max(arr[arr <= upper_fence])) if np.any(arr <= upper_fence) else upper_fence

        return {
            "min": float(np.min(arr)),
            "lower_whisker": lower_whisker,
            "q1": q1,
            "median": median,
            "q3": q3,
            "upper_whisker": upper_whisker,
            "max": float(np.max(arr)),
            "iqr": iqr,
            "lower_fence": lower_fence,
            "upper_fence": upper_fence,
        }

    def _build_description(
        self,
        anomalies: List[IQRAnomaly],
        total: int,
        q1: float,
        q3: float,
        iqr: float,
    ) -> str:
        """Build description of IQR results."""
        if not anomalies:
            return (
                f"No outliers detected (IQR={iqr:.2f}, fences at "
                f"{q1 - self.multiplier * iqr:.2f} to {q3 + self.multiplier * iqr:.2f})."
            )

        mild = sum(1 for a in anomalies if a.severity == "mild")
        extreme = sum(1 for a in anomalies if a.severity == "extreme")
        upper = sum(1 for a in anomalies if a.direction == "upper")
        lower = len(anomalies) - upper

        parts = [f"{len(anomalies)} outliers in {total} points"]
        details = []
        if extreme:
            details.append(f"{extreme} extreme")
        if mild:
            details.append(f"{mild} mild")
        if details:
            parts.append(f" ({', '.join(details)})")

        if upper and lower:
            parts.append(f" — {upper} above, {lower} below")
        elif upper:
            parts.append(" — all above Q3")
        else:
            parts.append(" — all below Q1")

        return "".join(parts) + "."
