"""
Pydantic models for context data structures.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class Filter(BaseModel):
    """A filter applied to data."""
    column: str
    operator: str
    value: Any


class Selection(BaseModel):
    """A user selection within the report."""
    visual_id: str
    data_points: List[Dict[str, Any]]


class Visual(BaseModel):
    """A Power BI visual."""
    id: str
    name: str
    type: str
    fields: List[str]
    data_summary: Optional[Dict[str, Any]] = None


class Page(BaseModel):
    """A Power BI page."""
    id: str
    name: str
    visuals: List[Visual]


class Report(BaseModel):
    """A Power BI report."""
    id: str
    name: str
    pages: List[Page]
    metadata: Optional[Dict[str, Any]] = None


class ReportContext(BaseModel):
    """Context information about the current report."""
    report: Report
    current_page: str
    filters: Optional[List[Filter]] = None
    selection: Optional[Selection] = None


class VisualContext(BaseModel):
    """Context information about a specific visual."""
    visual: Visual
    data: List[Dict[str, Any]]
    filters: Optional[List[Filter]] = None


class SessionContext(BaseModel):
    """Context for a user session."""
    session_id: str
    user_id: str
    report_context: ReportContext
    conversation_history: List[Dict[str, Any]]
    metadata: Optional[Dict[str, Any]] = None
