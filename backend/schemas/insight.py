"""
Pydantic models for insight data structures.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel
from enum import Enum


class InsightType(str, Enum):
    """Types of insights."""
    TREND = "trend"
    ANOMALY = "anomaly"
    PATTERN = "pattern"
    OPPORTUNITY = "opportunity"
    RISK = "risk"


class InsightSeverity(str, Enum):
    """Severity levels for insights."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Insight(BaseModel):
    """An individual insight."""
    id: str
    type: InsightType
    title: str
    description: str
    metrics: Dict[str, float]
    confidence: float
    severity: Optional[InsightSeverity] = None
    recommendations: Optional[List[str]] = None
    timestamp: datetime


class InsightCard(BaseModel):
    """A card containing insights for UI display."""
    id: str
    title: str
    insights: List[Insight]
    summary: str
    visual_reference: Optional[str] = None


class KPIMetric(BaseModel):
    """A KPI metric."""
    name: str
    current_value: float
    previous_value: Optional[float] = None
    target_value: Optional[float] = None
    trend: str  # "up", "down", "stable"
    threshold: Optional[float] = None


class ExecutiveSummary(BaseModel):
    """Executive summary of key insights."""
    period: str
    key_metrics: List[KPIMetric]
    highlights: List[str]
    concerns: List[str]
    recommendations: List[str]


class InsightResponse(BaseModel):
    """Response containing insights."""
    insights: List[Insight]
    summary: str
    next_actions: Optional[List[str]] = None
    timestamp: datetime
