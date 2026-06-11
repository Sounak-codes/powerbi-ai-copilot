"""
Time-series forecasting for Power BI metrics.

Provides simple but effective forecasting methods including
linear extrapolation, exponential smoothing, and seasonal naive.
"""
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
import numpy as np
from config import get_logger

logger = get_logger(__name__)


@dataclass
class ForecastResult:
    """Result of a forecasting operation."""
    forecast_values: List[float]
    confidence_intervals: List[Tuple[float, float]]  # (lower, upper) for each period
    method: str
    periods_ahead: int
    historical_fit_error: float  # MAPE on historical data
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "forecast_values": [round(v, 2) for v in self.forecast_values],
            "confidence_intervals": [
                {"lower": round(lo, 2), "upper": round(hi, 2)}
                for lo, hi in self.confidence_intervals
            ],
            "method": self.method,
            "periods_ahead": self.periods_ahead,
            "historical_fit_error": round(self.historical_fit_error, 4),
            "description": self.description,
        }


class Forecaster:
    """
    Forecast future values using multiple methods.

    Automatically selects the best method based on data characteristics
    or allows explicit method selection.
    """

    def forecast(
        self,
        values: List[float],
        periods_ahead: int = 3,
        method: Optional[str] = None,
        seasonal_period: Optional[int] = None,
    ) -> ForecastResult:
        """
        Generate a forecast for future periods.

        Args:
            values: Historical time series values.
            periods_ahead: Number of future periods to forecast.
            method: Forecasting method ("linear", "exponential_smoothing", "seasonal_naive", "auto").
            seasonal_period: Period length if seasonality is known.

        Returns:
            ForecastResult with predictions and confidence intervals.
        """
        if len(values) < 3:
            return ForecastResult(
                forecast_values=[values[-1]] * periods_ahead if values else [0.0] * periods_ahead,
                confidence_intervals=[(0.0, 0.0)] * periods_ahead,
                method="constant",
                periods_ahead=periods_ahead,
                historical_fit_error=0.0,
                description="Insufficient data for forecasting, returning last known value.",
            )

        if method is None or method == "auto":
            method = self._select_method(values, seasonal_period)

        if method == "linear":
            return self._linear_forecast(values, periods_ahead)
        elif method == "exponential_smoothing":
            return self._exponential_smoothing_forecast(values, periods_ahead)
        elif method == "seasonal_naive":
            return self._seasonal_naive_forecast(values, periods_ahead, seasonal_period)
        else:
            return self._linear_forecast(values, periods_ahead)

    def _select_method(
        self, values: List[float], seasonal_period: Optional[int]
    ) -> str:
        """Auto-select the best forecasting method."""
        n = len(values)

        # If seasonality is known and we have enough data, use seasonal naive
        if seasonal_period and n >= seasonal_period * 2:
            return "seasonal_naive"

        # For short series, use exponential smoothing
        if n < 20:
            return "exponential_smoothing"

        # For longer series, compare methods on holdout
        return self._cross_validate_methods(values)

    def _cross_validate_methods(self, values: List[float]) -> str:
        """Compare methods using last-few-points holdout validation."""
        holdout = min(5, len(values) // 4)
        train = values[:-holdout]
        actual = values[-holdout:]

        methods = {
            "linear": self._linear_forecast,
            "exponential_smoothing": self._exponential_smoothing_forecast,
        }

        best_method = "linear"
        best_error = float("inf")

        for name, func in methods.items():
            try:
                result = func(train, holdout)
                error = self._mape(actual, result.forecast_values)
                if error < best_error:
                    best_error = error
                    best_method = name
            except Exception:
                continue

        return best_method

    def _linear_forecast(
        self, values: List[float], periods_ahead: int
    ) -> ForecastResult:
        """Forecast using linear extrapolation."""
        arr = np.array(values, dtype=float)
        n = len(arr)
        x = np.arange(n)

        # Fit linear model
        slope, intercept = np.polyfit(x, arr, 1)

        # Forecast
        future_x = np.arange(n, n + periods_ahead)
        forecast = slope * future_x + intercept

        # Confidence intervals based on residual std
        residuals = arr - (slope * x + intercept)
        std_resid = np.std(residuals)

        confidence_intervals = []
        for i in range(periods_ahead):
            # Wider intervals for further-out predictions
            width = std_resid * (1 + 0.2 * (i + 1)) * 1.96
            confidence_intervals.append(
                (float(forecast[i] - width), float(forecast[i] + width))
            )

        # Historical MAPE
        fitted = slope * x + intercept
        mape = self._mape(values, fitted.tolist())

        return ForecastResult(
            forecast_values=forecast.tolist(),
            confidence_intervals=confidence_intervals,
            method="linear",
            periods_ahead=periods_ahead,
            historical_fit_error=mape,
            description=f"Linear forecast: slope={slope:.2f} per period.",
        )

    def _exponential_smoothing_forecast(
        self,
        values: List[float],
        periods_ahead: int,
        alpha: float = 0.3,
        beta: float = 0.1,
    ) -> ForecastResult:
        """
        Forecast using Holt's double exponential smoothing.

        Captures both level and trend.
        """
        arr = np.array(values, dtype=float)
        n = len(arr)

        # Initialize
        level = arr[0]
        trend = arr[1] - arr[0] if n > 1 else 0.0

        # Smooth
        levels = [level]
        trends = [trend]
        fitted = [level]

        for i in range(1, n):
            new_level = alpha * arr[i] + (1 - alpha) * (level + trend)
            new_trend = beta * (new_level - level) + (1 - beta) * trend
            level = new_level
            trend = new_trend
            levels.append(level)
            trends.append(trend)
            fitted.append(level)

        # Forecast
        forecast = []
        for h in range(1, periods_ahead + 1):
            forecast.append(level + h * trend)

        # Confidence intervals
        residuals = arr - np.array(fitted)
        std_resid = np.std(residuals)

        confidence_intervals = []
        for i in range(periods_ahead):
            width = std_resid * (1 + 0.3 * (i + 1)) * 1.96
            confidence_intervals.append(
                (forecast[i] - width, forecast[i] + width)
            )

        mape = self._mape(values, fitted)

        return ForecastResult(
            forecast_values=forecast,
            confidence_intervals=confidence_intervals,
            method="exponential_smoothing",
            periods_ahead=periods_ahead,
            historical_fit_error=mape,
            description=f"Holt exponential smoothing (α={alpha}, β={beta}).",
        )

    def _seasonal_naive_forecast(
        self,
        values: List[float],
        periods_ahead: int,
        seasonal_period: Optional[int] = None,
    ) -> ForecastResult:
        """
        Forecast using seasonal naive method.

        Repeats the last complete season's values.
        """
        if not seasonal_period:
            seasonal_period = 12  # Default to monthly

        arr = np.array(values, dtype=float)
        n = len(arr)

        # Get last season's values
        last_season = arr[-seasonal_period:]

        # Forecast by cycling through the seasonal pattern
        forecast = []
        for i in range(periods_ahead):
            forecast.append(float(last_season[i % seasonal_period]))

        # Confidence intervals based on inter-season variability
        if n >= seasonal_period * 2:
            season_diffs = []
            for i in range(seasonal_period, n):
                diff = arr[i] - arr[i - seasonal_period]
                season_diffs.append(diff)
            std_seasonal = np.std(season_diffs)
        else:
            std_seasonal = np.std(arr) * 0.5

        confidence_intervals = []
        for i in range(periods_ahead):
            width = std_seasonal * 1.96
            confidence_intervals.append(
                (forecast[i] - width, forecast[i] + width)
            )

        # MAPE on one-season-ahead prediction
        if n > seasonal_period:
            actual_last = values[-seasonal_period:]
            predicted_last = values[-2 * seasonal_period : -seasonal_period]
            mape = self._mape(actual_last, predicted_last)
        else:
            mape = 0.0

        return ForecastResult(
            forecast_values=forecast,
            confidence_intervals=confidence_intervals,
            method="seasonal_naive",
            periods_ahead=periods_ahead,
            historical_fit_error=mape,
            description=f"Seasonal naive forecast with period={seasonal_period}.",
        )

    def _mape(self, actual: List[float], predicted: List[float]) -> float:
        """Calculate Mean Absolute Percentage Error."""
        actual_arr = np.array(actual, dtype=float)
        predicted_arr = np.array(predicted[: len(actual)], dtype=float)

        # Avoid division by zero
        mask = actual_arr != 0
        if not np.any(mask):
            return 0.0

        ape = np.abs((actual_arr[mask] - predicted_arr[mask]) / actual_arr[mask])
        return float(np.mean(ape))
