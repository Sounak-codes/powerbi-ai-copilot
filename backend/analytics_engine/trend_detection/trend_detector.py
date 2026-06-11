"""
Trend detection engine for time-series data.

Identifies trends (upward, downward, stable), calculates slope,
detects change points, and provides confidence-scored trend descriptions.
"""
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import numpy as np
from config import get_logger

logger = get_logger(__name__)


class TrendDirection(str, Enum):
    """Direction of a detected trend."""
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"
    VOLATILE = "volatile"


@dataclass
class TrendResult:
    """Result of trend detection analysis."""
    direction: TrendDirection
    slope: float  # Normalized slope (% change per period)
    magnitude: float  # Absolute magnitude of change
    confidence: float  # 0-1 confidence score
    start_index: int
    end_index: int
    r_squared: float  # Goodness of fit
    description: str = ""
    change_points: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "direction": self.direction.value,
            "slope": round(self.slope, 4),
            "magnitude": round(self.magnitude, 4),
            "confidence": round(self.confidence, 3),
            "start_index": self.start_index,
            "end_index": self.end_index,
            "r_squared": round(self.r_squared, 4),
            "description": self.description,
            "change_points": self.change_points,
        }


class TrendDetector:
    """
    Detect and characterize trends in time-series data.

    Uses linear regression for overall trend, and segmented regression
    for detecting multiple trends within a series.
    """

    # Slope threshold — below this the trend is considered stable
    STABLE_THRESHOLD = 0.005  # 0.5% per period
    # R² threshold — below this the linear fit isn't reliable
    FIT_THRESHOLD = 0.3
    # Minimum data points needed for reliable trend detection
    MIN_DATA_POINTS = 5

    def detect(
        self,
        values: List[float],
        timestamps: Optional[List[str]] = None,
    ) -> TrendResult:
        """
        Detect the overall trend in a time series.

        Args:
            values: Numeric values ordered by time.
            timestamps: Optional timestamp labels for reporting.

        Returns:
            TrendResult with direction, slope, confidence, etc.
        """
        if not values or len(values) < self.MIN_DATA_POINTS:
            return TrendResult(
                direction=TrendDirection.STABLE,
                slope=0.0,
                magnitude=0.0,
                confidence=0.0,
                start_index=0,
                end_index=max(0, len(values) - 1),
                r_squared=0.0,
                description="Insufficient data for trend detection.",
            )

        arr = np.array(values, dtype=float)
        n = len(arr)
        x = np.arange(n)

        # Linear regression
        slope, intercept, r_squared = self._linear_regression(x, arr)

        # Normalize slope as percentage of mean
        mean_val = np.mean(arr)
        normalized_slope = slope / mean_val if mean_val != 0 else 0.0

        # Determine direction
        direction = self._classify_direction(normalized_slope, r_squared)

        # Calculate magnitude (total change)
        magnitude = abs(arr[-1] - arr[0]) / abs(mean_val) if mean_val != 0 else 0.0

        # Confidence is based on R² and data quantity
        confidence = self._calculate_confidence(r_squared, n, normalized_slope)

        # Detect change points
        change_points = self._detect_change_points(arr)

        # Build description
        description = self._build_description(
            direction, normalized_slope, magnitude, n, change_points
        )

        result = TrendResult(
            direction=direction,
            slope=normalized_slope,
            magnitude=magnitude,
            confidence=confidence,
            start_index=0,
            end_index=n - 1,
            r_squared=r_squared,
            description=description,
            change_points=change_points,
        )

        logger.debug(f"Trend detected: {direction.value} (slope={normalized_slope:.4f}, R²={r_squared:.3f})")
        return result

    def detect_segments(
        self,
        values: List[float],
        min_segment_length: int = 5,
    ) -> List[TrendResult]:
        """
        Detect multiple trend segments in a time series.

        Uses change point detection to split the series into
        segments, then analyzes each segment independently.

        Args:
            values: Numeric values ordered by time.
            min_segment_length: Minimum points in a segment.

        Returns:
            List of TrendResults, one per detected segment.
        """
        if len(values) < min_segment_length * 2:
            return [self.detect(values)]

        arr = np.array(values, dtype=float)
        change_points = self._detect_change_points(arr)

        if not change_points:
            return [self.detect(values)]

        # Split at change points
        boundaries = [0] + change_points + [len(arr)]
        segments = []

        for i in range(len(boundaries) - 1):
            start = boundaries[i]
            end = boundaries[i + 1]

            if end - start >= min_segment_length:
                segment_values = values[start:end]
                result = self.detect(segment_values)
                result.start_index = start
                result.end_index = end - 1
                segments.append(result)

        return segments if segments else [self.detect(values)]

    def calculate_period_over_period(
        self,
        current_values: List[float],
        previous_values: List[float],
    ) -> Dict[str, Any]:
        """
        Calculate period-over-period comparison.

        Args:
            current_values: Current period values.
            previous_values: Previous period values for comparison.

        Returns:
            Dictionary with comparison metrics.
        """
        if not current_values or not previous_values:
            return {"change_pct": 0.0, "direction": "stable", "confidence": 0.0}

        current_sum = sum(current_values)
        previous_sum = sum(previous_values)

        if previous_sum == 0:
            change_pct = 100.0 if current_sum > 0 else 0.0
        else:
            change_pct = ((current_sum - previous_sum) / abs(previous_sum)) * 100

        current_avg = np.mean(current_values)
        previous_avg = np.mean(previous_values)

        return {
            "current_total": round(current_sum, 2),
            "previous_total": round(previous_sum, 2),
            "change_pct": round(change_pct, 2),
            "current_avg": round(float(current_avg), 2),
            "previous_avg": round(float(previous_avg), 2),
            "direction": "increasing" if change_pct > 1 else "decreasing" if change_pct < -1 else "stable",
            "confidence": min(1.0, abs(change_pct) / 50),
        }

    def _linear_regression(
        self, x: np.ndarray, y: np.ndarray
    ) -> Tuple[float, float, float]:
        """Perform simple linear regression. Returns (slope, intercept, r_squared)."""
        n = len(x)
        x_mean = np.mean(x)
        y_mean = np.mean(y)

        # Slope and intercept
        numerator = np.sum((x - x_mean) * (y - y_mean))
        denominator = np.sum((x - x_mean) ** 2)

        if denominator == 0:
            return 0.0, float(y_mean), 0.0

        slope = float(numerator / denominator)
        intercept = float(y_mean - slope * x_mean)

        # R-squared
        y_pred = slope * x + intercept
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - y_mean) ** 2)

        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        r_squared = max(0.0, r_squared)

        return slope, intercept, r_squared

    def _classify_direction(self, normalized_slope: float, r_squared: float) -> TrendDirection:
        """Classify trend direction based on slope and fit quality."""
        if r_squared < self.FIT_THRESHOLD:
            return TrendDirection.VOLATILE

        if abs(normalized_slope) < self.STABLE_THRESHOLD:
            return TrendDirection.STABLE
        elif normalized_slope > 0:
            return TrendDirection.INCREASING
        else:
            return TrendDirection.DECREASING

    def _calculate_confidence(
        self, r_squared: float, n: int, normalized_slope: float
    ) -> float:
        """Calculate confidence score for the trend."""
        # Base confidence from R²
        fit_confidence = r_squared

        # Boost for more data points (diminishing returns)
        data_confidence = min(1.0, n / 30)

        # Boost for stronger trends
        strength_confidence = min(1.0, abs(normalized_slope) / 0.05)

        # Weighted combination
        confidence = (
            fit_confidence * 0.5
            + data_confidence * 0.25
            + strength_confidence * 0.25
        )

        return min(1.0, max(0.0, confidence))

    def _detect_change_points(self, arr: np.ndarray, min_segment: int = 5) -> List[int]:
        """
        Detect change points using a simple CUSUM-inspired approach.

        Finds points where the trend direction meaningfully shifts.
        """
        n = len(arr)
        if n < min_segment * 2:
            return []

        change_points = []

        # Calculate rolling slopes
        window = max(min_segment, n // 5)
        slopes = []

        for i in range(n - window + 1):
            segment = arr[i : i + window]
            x = np.arange(window)
            slope, _, _ = self._linear_regression(x, segment)
            slopes.append(slope)

        if not slopes:
            return []

        # Detect sign changes in slope that persist
        slopes_arr = np.array(slopes)
        signs = np.sign(slopes_arr)

        for i in range(1, len(signs)):
            if signs[i] != signs[i - 1] and signs[i] != 0:
                # Change point at the offset position
                cp = i + window // 2
                if cp > min_segment and cp < n - min_segment:
                    # Avoid too-close change points
                    if not change_points or cp - change_points[-1] >= min_segment:
                        change_points.append(cp)

        return change_points

    def _build_description(
        self,
        direction: TrendDirection,
        slope: float,
        magnitude: float,
        n: int,
        change_points: List[int],
    ) -> str:
        """Build a natural language trend description."""
        if direction == TrendDirection.STABLE:
            return f"The metric is relatively stable over {n} periods with minimal change ({magnitude:.1%})."

        if direction == TrendDirection.VOLATILE:
            return f"The metric shows high volatility over {n} periods, making trend detection unreliable."

        dir_word = "increasing" if direction == TrendDirection.INCREASING else "decreasing"
        rate = abs(slope)

        if rate > 0.05:
            intensity = "strongly"
        elif rate > 0.02:
            intensity = "moderately"
        else:
            intensity = "gradually"

        desc = f"The metric is {intensity} {dir_word} at {rate:.1%} per period over {n} data points (total change: {magnitude:.1%})."

        if change_points:
            desc += f" {len(change_points)} trend shift(s) detected."

        return desc
