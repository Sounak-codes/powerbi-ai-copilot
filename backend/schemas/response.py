"""
Pydantic models for API response structures.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel
from enum import Enum


class ResponseStatus(str, Enum):
    """Response status codes."""
    SUCCESS = "success"
    PARTIAL = "partial"
    ERROR = "error"
    PENDING = "pending"


class ErrorDetail(BaseModel):
    """Error detail information."""
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class APIResponse(BaseModel):
    """Standard API response wrapper."""
    status: ResponseStatus
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    error: Optional[ErrorDetail] = None
    timestamp: datetime
    request_id: Optional[str] = None


class PaginatedResponse(BaseModel):
    """Paginated response."""
    status: ResponseStatus
    data: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int
    total_pages: int
    timestamp: datetime


class AsyncResponse(BaseModel):
    """Response for async operations."""
    status: ResponseStatus
    task_id: str
    message: str
    estimate_completion: Optional[datetime] = None
    timestamp: datetime


class HealthCheckResponse(BaseModel):
    """Health check response."""
    status: str  # "healthy", "degraded", "unhealthy"
    services: Dict[str, str]
    timestamp: datetime
