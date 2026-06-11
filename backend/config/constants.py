"""
Application-wide constants and enumerations.
"""
from enum import Enum

# Intent Types
class IntentType(str, Enum):
    """Types of user intents."""
    QUESTION = "question"
    ANALYSIS = "analysis"
    INSIGHT = "insight"
    EXPLANATION = "explanation"
    RECOMMENDATION = "recommendation"
    DAX_GENERATION = "dax_generation"
    TREND_ANALYSIS = "trend_analysis"
    ANOMALY_DETECTION = "anomaly_detection"
    CORRELATION = "correlation"
    ROOT_CAUSE = "root_cause"
    REPORT_GENERATION = "report_generation"


# Analysis Types
class AnalysisType(str, Enum):
    """Types of analytics to perform."""
    TREND = "trend"
    ANOMALY = "anomaly"
    ROOT_CAUSE = "root_cause"
    CORRELATION = "correlation"
    RECOMMENDATION = "recommendation"
    KPI = "kpi"
    EXECUTIVE_SUMMARY = "executive_summary"


# Insight Types
class InsightType(str, Enum):
    """Types of insights that can be generated."""
    TREND = "trend"
    ANOMALY = "anomaly"
    PATTERN = "pattern"
    OPPORTUNITY = "opportunity"
    RISK = "risk"
    RECOMMENDATION = "recommendation"


# Response Status
class ResponseStatus(str, Enum):
    """Status codes for responses."""
    SUCCESS = "success"
    PARTIAL = "partial"
    ERROR = "error"
    PENDING = "pending"


# Agent Types
class AgentType(str, Enum):
    """Types of agents in the system."""
    PLANNER = "planner"
    ANALYTICS = "analytics"
    RAG = "rag"
    DAX = "dax"
    INSIGHT = "insight"
    RESPONSE = "response"


# Context Types
class ContextType(str, Enum):
    """Types of context information."""
    REPORT = "report"
    PAGE = "page"
    VISUAL = "visual"
    SLICER = "slicer"
    FILTER = "filter"
    SELECTION = "selection"


# Constants
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 1000
DEFAULT_TIMEOUT = 30
MAX_CONVERSATION_LENGTH = 100
MAX_SESSION_DURATION = 86400  # 24 hours

# Cache TTL (seconds)
CACHE_TTL_SHORT = 300  # 5 minutes
CACHE_TTL_MEDIUM = 3600  # 1 hour
CACHE_TTL_LONG = 86400  # 1 day

# RAG Settings
RAG_MIN_RELEVANCE_SCORE = 0.5
RAG_MAX_RESULTS = 10

# Rate Limiting
RATE_LIMIT_REQUESTS = 100
RATE_LIMIT_WINDOW = 3600  # 1 hour
