"""
Intent schema definitions.
"""
from enum import Enum
from typing import List, Optional


class IntentCategory(str, Enum):
    """Intent categories."""
    QUESTION = "question"
    ANALYSIS = "analysis"
    INSIGHT = "insight"
    EXPLANATION = "explanation"
    RECOMMENDATION = "recommendation"
    DAX = "dax"
    REPORT = "report"
    UNKNOWN = "unknown"


class Intent:
    """Classified user intent."""

    def __init__(
        self,
        category: IntentCategory,
        confidence: float,
        entities: Optional[List[str]] = None,
        metadata: Optional[dict] = None,
    ):
        self.category = category
        self.confidence = confidence
        self.entities = entities or []
        self.metadata = metadata or {}

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "category": self.category.value,
            "confidence": self.confidence,
            "entities": self.entities,
            "metadata": self.metadata,
        }
