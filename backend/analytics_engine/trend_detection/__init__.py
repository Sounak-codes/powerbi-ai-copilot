"""Trend detection sub-package."""
from analytics_engine.trend_detection.trend_detector import TrendDetector, TrendResult, TrendDirection
from analytics_engine.trend_detection.seasonality import SeasonalityDetector, SeasonalityResult
from analytics_engine.trend_detection.forecasting import Forecaster, ForecastResult

__all__ = [
    "TrendDetector",
    "TrendResult",
    "TrendDirection",
    "SeasonalityDetector",
    "SeasonalityResult",
    "Forecaster",
    "ForecastResult",
]
