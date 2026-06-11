"""
Response builder for formatting agent outputs into user-facing responses.

Takes raw agent results and constructs structured, presentation-ready
responses with metadata, follow-up suggestions, and confidence scores.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
from config import get_logger

logger = get_logger(__name__)


class ResponseBuilder:
    """
    Build structured responses from agent outputs.

    Handles formatting, follow-up generation, and metadata attachment
    for all response types (chat, insights, analysis, DAX, etc.).
    """

    def build_chat_response(
        self,
        message: str,
        session_id: str,
        agent_name: Optional[str] = None,
        intent: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        follow_ups: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Build a standard chat response.

        Args:
            message: The response message text.
            session_id: Session identifier.
            agent_name: Name of the agent that produced the response.
            intent: Classified intent information.
            metadata: Additional metadata.
            follow_ups: Suggested follow-up questions.

        Returns:
            Structured chat response.
        """
        response = {
            "id": str(uuid.uuid4()),
            "message": message,
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "success",
        }

        if agent_name:
            response["agent"] = agent_name
        if intent:
            response["intent"] = intent
        if metadata:
            response["metadata"] = metadata
        if follow_ups:
            response["follow_up_questions"] = follow_ups

        return response

    def build_insight_response(
        self,
        insights: List[Dict[str, Any]],
        summary: str,
        session_id: str,
        confidence: float = 0.0,
        recommendations: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Build a response containing insights."""
        return {
            "id": str(uuid.uuid4()),
            "type": "insight",
            "insights": insights,
            "summary": summary,
            "session_id": session_id,
            "confidence": confidence,
            "recommendations": recommendations or [],
            "timestamp": datetime.utcnow().isoformat(),
            "status": "success",
        }

    def build_analysis_response(
        self,
        analysis_type: str,
        results: Dict[str, Any],
        summary: str,
        session_id: str,
        visualizations: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Build a response containing analysis results."""
        return {
            "id": str(uuid.uuid4()),
            "type": "analysis",
            "analysis_type": analysis_type,
            "results": results,
            "summary": summary,
            "visualizations": visualizations or [],
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "success",
        }

    def build_dax_response(
        self,
        dax_code: str,
        explanation: str,
        session_id: str,
        measure_name: Optional[str] = None,
        optimizations: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Build a response containing DAX code."""
        return {
            "id": str(uuid.uuid4()),
            "type": "dax",
            "dax_code": dax_code,
            "explanation": explanation,
            "measure_name": measure_name,
            "optimizations": optimizations or [],
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "success",
        }

    def build_error_response(
        self,
        error_message: str,
        session_id: str,
        error_code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build an error response."""
        return {
            "id": str(uuid.uuid4()),
            "status": "error",
            "error": {
                "code": error_code,
                "message": error_message,
                "details": details,
            },
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def generate_follow_up_questions(
        self,
        intent_category: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """
        Generate contextual follow-up question suggestions.

        Based on the intent type and available context, suggest
        natural next questions the user might want to ask.
        """
        suggestions: Dict[str, List[str]] = {
            "analysis": [
                "What's driving this trend?",
                "Are there any anomalies in this period?",
                "How does this compare to the previous period?",
                "Can you break this down by region?",
            ],
            "insight": [
                "What actions should I take based on this?",
                "Which metrics are most at risk?",
                "Can you provide more detail on the top finding?",
                "What's the expected impact if this continues?",
            ],
            "question": [
                "Can you explain this in more detail?",
                "What other factors should I consider?",
                "How does this relate to other metrics?",
            ],
            "dax": [
                "Can you optimize this measure?",
                "How would I add a time comparison?",
                "What about handling blanks/nulls?",
                "Can you add a year-over-year calculation?",
            ],
            "trend_analysis": [
                "What's causing this trend?",
                "Is this seasonal or structural?",
                "What's the forecast for next quarter?",
            ],
            "anomaly_detection": [
                "What happened at that anomaly point?",
                "Is this a one-time event or recurring?",
                "Which segments are most affected?",
            ],
        }

        return suggestions.get(intent_category, suggestions["question"])[:3]

    def enrich_response(
        self,
        response: Dict[str, Any],
        intent_category: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Enrich a response with follow-ups and additional metadata.

        Call this as a final step before returning to the user.
        """
        # Add follow-up questions if not already present
        if "follow_up_questions" not in response:
            response["follow_up_questions"] = self.generate_follow_up_questions(
                intent_category, context
            )

        # Add confidence indicator
        if "confidence" not in response and "intent" in response:
            response["confidence"] = response["intent"].get("confidence", 0.5)

        return response
