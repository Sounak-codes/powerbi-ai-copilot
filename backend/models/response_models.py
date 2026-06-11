"""
Response models for API endpoints.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel
from enum import Enum


class ResponseStatus(str, Enum):
    """Response status."""
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"


class CopilotResponse(BaseModel):
    """Standard copilot response."""
    status: ResponseStatus
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    error: Optional[str] = None
    timestamp: datetime


class InsightResponse(BaseModel):
    """Insight response."""
    insights: List[Dict[str, Any]]
    summary: str
    metrics: Optional[Dict[str, float]] = None
    timestamp: datetime


class AnalyticsResponse(BaseModel):
    """Analytics response."""
    analysis_type: str
    results: Dict[str, Any]
    summary: str
    timestamp: datetime


class DAXResponse(BaseModel):
    """DAX generation response."""
    dax_code: str
    explanation: str
    metrics: Optional[List[str]] = None
    timestamp: datetime


__all__ = [
    "ResponseStatus",
    "CopilotResponse",
    "InsightResponse",
    "AnalyticsResponse",
    "DAXResponse",
]
