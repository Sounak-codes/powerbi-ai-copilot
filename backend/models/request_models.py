"""
Request and response models for API endpoints.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ChatRequestModel(BaseModel):
    """Chat request model."""
    message: str = Field(..., description="User message")
    session_id: str = Field(..., description="Session identifier")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")


class ChatResponseModel(BaseModel):
    """Chat response model."""
    message: str
    session_id: str
    suggestions: Optional[List[str]] = None


class AnalyticsRequestModel(BaseModel):
    """Analytics request model."""
    metric_name: str
    time_range: str  # e.g., "7d", "30d", "1y"
    analysis_types: List[str]  # e.g., ["trend", "anomaly"]
    filters: Optional[Dict[str, Any]] = None


class InsightRequestModel(BaseModel):
    """Insight request model."""
    report_id: str
    page_id: Optional[str] = None
    visual_id: Optional[str] = None
    depth: str = "standard"  # "light", "standard", "deep"


class DAXGeneratorRequestModel(BaseModel):
    """DAX code generation request."""
    description: str
    context: Optional[Dict[str, Any]] = None


class FeedbackModel(BaseModel):
    """User feedback model."""
    message_id: str
    rating: int = Field(1, ge=1, le=5)
    feedback: Optional[str] = None
    helpful: bool = Field(True)


__all__ = [
    "ChatRequestModel",
    "ChatResponseModel",
    "AnalyticsRequestModel",
    "InsightRequestModel",
    "DAXGeneratorRequestModel",
    "FeedbackModel",
]
