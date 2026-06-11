"""
Pydantic models for analytics data structures.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel


class Metric(BaseModel):
    """A data metric."""
    name: str
    value: float
    unit: Optional[str] = None
    timestamp: datetime


class DataPoint(BaseModel):
    """A single data point in a time series."""
    timestamp: datetime
    value: float
    labels: Optional[Dict[str, str]] = None


class TimeSeries(BaseModel):
    """A time series dataset."""
    name: str
    data_points: List[DataPoint]
    metrics: Optional[Dict[str, float]] = None


class Trend(BaseModel):
    """A trend analysis result."""
    direction: str  # "increasing", "decreasing", "stable"
    magnitude: float
    confidence: float
    start_date: datetime
    end_date: datetime
    description: str


class Anomaly(BaseModel):
    """An anomaly detection result."""
    timestamp: datetime
    value: float
    expected_range: tuple
    severity: str  # "low", "medium", "high"
    description: str


class Correlation(BaseModel):
    """A correlation analysis result."""
    metric1: str
    metric2: str
    coefficient: float
    significance: float
    description: str


class AnalyticsResult(BaseModel):
    """Result of an analytics operation."""
    type: str
    data: Dict[str, Any]
    summary: str
    confidence: float
    timestamp: datetime
