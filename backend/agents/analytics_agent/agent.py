"""
Analytics Agent for data analysis and insights.
"""
from typing import Any, Dict, Optional
from llm.providers.provider_factory import ProviderFactory
from agents.base_agent import BaseAgent
from memory.session_manager import Session
from memory.conversation_memory import ConversationMemory
from intent_engine.intent_schema import Intent
from analytics_engine.insight_generator import InsightGenerator
from config import get_logger

logger = get_logger(__name__)


class AnalyticsAgent(BaseAgent):
    """Agent that performs analytics and generates insights."""

    SYSTEM_PROMPT = """You are a data analysis expert for Power BI.
Provide detailed analysis, identify trends, anomalies, and actionable insights.
Present findings clearly with supporting metrics."""

    def __init__(self):
        super().__init__("AnalyticsAgent")
        self.llm_provider = ProviderFactory.get_default_provider()
        self.insight_generator = InsightGenerator()

    async def execute(
        self,
        message: str,
        session: Session,
        conversation: ConversationMemory,
        context: Optional[Dict[str, Any]] = None,
        intent: Optional[Intent] = None,
    ) -> Dict[str, Any]:
        """Execute analytics agent logic."""
        try:
            self._log_execution("START", "Analyzing data")

            # Step 1: Generate insights
            insights = await self.insight_generator.generate_insights(
                data=context or {},
                depth="standard",
            )

            # Step 2: Create analysis narrative
            analysis_text = await self._create_analysis_narrative(message, insights)

            self._log_execution("COMPLETE", f"Generated {len(insights)} insights")

            return await self._get_response_message(
                analysis_text,
                metadata={
                    "agent": "analytics",
                    "insights_count": len(insights),
                    "confidence": 0.85,
                },
            )

        except Exception as e:
            logger.error(f"AnalyticsAgent error: {e}")
            return await self._get_response_message(
                "Unable to perform analysis at this time."
            )

    async def _create_analysis_narrative(self, query: str, insights: list) -> str:
        """Create a narrative analysis from insights."""
        if not insights:
            return f"No significant insights found for: {query}"

        narrative = f"Analysis of {query}:\n\n"
        for insight in insights:
            narrative += f"- {insight.title}: {insight.description}\n"

        return narrative
