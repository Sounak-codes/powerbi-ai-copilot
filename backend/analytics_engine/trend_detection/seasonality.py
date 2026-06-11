"""
Seasonality detection for time-series data.

Identifies seasonal patterns (weekly, monthly, quarterly, annual)
and measures their strength to support better forecasting and
anomaly detection.
"""
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
from config import get_logger

logger = get_logger(__name__)


class SeasonalityPeriod(str, Enum):
    """Common seasonality periods."""
    WEEKLY = "weekly"       # 7 periods
    MONTHLY = "monthly"     # ~30 periods
    QUARTERLY = "quarterly" # ~90 periods
    ANNUAL = "annual"       # ~365 or 12 periods
    CUSTOM = "custom"


@dataclass
class SeasonalityResult:
    """Result of seasonality detection."""
    is_seasonal: bool
    period: Optional[SeasonalityPeriod] = None
    period_length: int = 0
    strength: float = 0.0  # 0 = no seasonality, 1 = perfect seasonality
    seasonal_component: List[float] = field(default_factory=list)
    residuals: List[float] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_seasonal": self.is_seasonal,
            "period": self.period.value if self.period else None,
            "period_length": self.period_length,
            "strength": round(self.strength, 3),
            "seasonal_component": [round(v, 4) for v in self.seasonal_component[:20]],
            "description": self.description,
        }


class SeasonalityDetector:
    """
    Detect and measure seasonality in time-series data.

    Uses autocorrelation analysis and seasonal decomposition
    to identify periodic patterns.
    """

    # Minimum strength to consider a pattern seasonal
    STRENGTH_THRESHOLD = 0.3
    # Common periods to test
    CANDIDATE_PERIODS = [7, 12, 14, 24, 28, 30, 52, 90, 365]

    def detect(
        self,
        values: List[float],
        known_frequency: Optional[str] = None,
    ) -> SeasonalityResult:
        """
        Detect seasonality in time-series data.

        Args:
            values: Numeric values ordered by time.
            known_frequency: If known, the data frequency ("daily", "weekly", "monthly").

        Returns:
            SeasonalityResult with period, strength, and components.
        """
        if len(values) < 14:
            return SeasonalityResult(
                is_seasonal=False,
                description="Insufficient data for seasonality detection (need at least 14 points).",
            )

        arr = np.array(values, dtype=float)

        # If frequency is known, test specific periods
        if known_frequency:
            candidate_periods = self._get_periods_for_frequency(known_frequency)
        else:
            # Filter candidates to those that make sense for the data length
            candidate_periods = [p for p in self.CANDIDATE_PERIODS if p < len(arr) // 2]

        if not candidate_periods:
            return SeasonalityResult(
                is_seasonal=False,
                description="Data length too short for any candidate seasonal period.",
            )

        # Find the best period using autocorrelation
        best_period, best_strength = self._find_best_period(arr, candidate_periods)

        if best_strength < self.STRENGTH_THRESHOLD:
            return SeasonalityResult(
                is_seasonal=False,
                strength=best_strength,
                description=f"No significant seasonality detected (max strength={best_strength:.2f}).",
            )

        # Decompose to get seasonal component
        seasonal_component, residuals = self._decompose(arr, best_period)

        # Classify the period
        period_type = self._classify_period(best_period, known_frequency)

        description = (
            f"Detected {period_type.value} seasonality with period={best_period} "
            f"and strength={best_strength:.2f}."
        )

        logger.debug(description)

        return SeasonalityResult(
            is_seasonal=True,
            period=period_type,
            period_length=best_period,
            strength=best_strength,
            seasonal_component=seasonal_component.tolist(),
            residuals=residuals.tolist(),
            description=description,
        )

    def get_seasonal_indices(
        self, values: List[float], period: int
    ) -> List[float]:
        """
        Calculate seasonal indices for each position in the period.

        Returns a list of length `period` where each value represents
        the average deviation at that position.
        """
        arr = np.array(values, dtype=float)
        n = len(arr)

        if n < period:
            return [1.0] * period

        # Calculate mean for each position
        indices = []
        overall_mean = np.mean(arr)

        for pos in range(period):
            position_values = arr[pos::period]
            pos_mean = np.mean(position_values)
            index = pos_mean / overall_mean if overall_mean != 0 else 1.0
            indices.append(float(index))

        return indices

    def deseasonalize(
        self, values: List[float], period: int
    ) -> List[float]:
        """
        Remove seasonal component from data.

        Useful for identifying underlying trends without seasonal noise.
        """
        indices = self.get_seasonal_indices(values, period)
        arr = np.array(values, dtype=float)

        deseasonalized = []
        for i, val in enumerate(arr):
            idx = indices[i % period]
            deseasonalized.append(float(val / idx) if idx != 0 else float(val))

        return deseasonalized

    def _find_best_period(
        self, arr: np.ndarray, candidate_periods: List[int]
    ) -> Tuple[int, float]:
        """Find the period with the strongest autocorrelation."""
        best_period = candidate_periods[0]
        best_strength = 0.0

        for period in candidate_periods:
            strength = self._autocorrelation_at_lag(arr, period)
            if strength > best_strength:
                best_strength = strength
                best_period = period

        return best_period, best_strength

    def _autocorrelation_at_lag(self, arr: np.ndarray, lag: int) -> float:
        """Calculate autocorrelation at a specific lag."""
        n = len(arr)
        if lag >= n:
            return 0.0

        mean = np.mean(arr)
        denominator = np.sum((arr - mean) ** 2)

        if denominator == 0:
            return 0.0

        numerator = np.sum((arr[:n - lag] - mean) * (arr[lag:] - mean))
        return float(max(0.0, numerator / denominator))

    def _decompose(
        self, arr: np.ndarray, period: int
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Simple additive seasonal decomposition.

        Returns (seasonal_component, residuals).
        """
        n = len(arr)

        # Calculate trend using moving average
        if period % 2 == 0:
            # Even period — use centered moving average
            kernel = np.ones(period) / period
            trend = np.convolve(arr, kernel, mode="same")
        else:
            kernel = np.ones(period) / period
            trend = np.convolve(arr, kernel, mode="same")

        # Detrended = original - trend
        detrended = arr - trend

        # Average seasonal pattern
        seasonal_pattern = np.zeros(period)
        counts = np.zeros(period)

        for i in range(n):
            pos = i % period
            seasonal_pattern[pos] += detrended[i]
            counts[pos] += 1

        seasonal_pattern = seasonal_pattern / np.maximum(counts, 1)

        # Center the seasonal pattern (zero mean)
        seasonal_pattern -= np.mean(seasonal_pattern)

        # Build full seasonal component
        seasonal = np.array([seasonal_pattern[i % period] for i in range(n)])

        # Residuals
        residuals = arr - trend - seasonal

        return seasonal, residuals

    def _classify_period(
        self, period_length: int, known_frequency: Optional[str]
    ) -> SeasonalityPeriod:
        """Classify a period length into a named seasonality type."""
        if known_frequency == "daily":
            if period_length == 7:
                return SeasonalityPeriod.WEEKLY
            if 28 <= period_length <= 31:
                return SeasonalityPeriod.MONTHLY
            if 89 <= period_length <= 92:
                return SeasonalityPeriod.QUARTERLY
            if 360 <= period_length <= 370:
                return SeasonalityPeriod.ANNUAL
        elif known_frequency == "monthly":
            if period_length == 12:
                return SeasonalityPeriod.ANNUAL
            if period_length == 3:
                return SeasonalityPeriod.QUARTERLY
        elif known_frequency == "weekly":
            if period_length == 52:
                return SeasonalityPeriod.ANNUAL
            if period_length == 4:
                return SeasonalityPeriod.MONTHLY

        # Heuristic classification
        if period_length <= 7:
            return SeasonalityPeriod.WEEKLY
        if period_length <= 31:
            return SeasonalityPeriod.MONTHLY
        if period_length <= 92:
            return SeasonalityPeriod.QUARTERLY
        return SeasonalityPeriod.ANNUAL

    def _get_periods_for_frequency(self, frequency: str) -> List[int]:
        """Get candidate periods for a known data frequency."""
        mapping = {
            "daily": [7, 30, 90, 365],
            "weekly": [4, 12, 13, 52],
            "monthly": [3, 4, 6, 12],
            "quarterly": [4],
            "hourly": [24, 168],  # day, week
        }
        return mapping.get(frequency, self.CANDIDATE_PERIODS)
