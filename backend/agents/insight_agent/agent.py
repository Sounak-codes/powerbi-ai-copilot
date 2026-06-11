"""
Insight Agent — generates actionable business insights from data.

Combines analytics results (trends, anomalies, KPIs) with LLM
reasoning to produce prioritized, actionable insights.
"""
from typing import Any, Dict, Optional, List
from llm.providers.provider_factory import ProviderFactory
from agents.base_agent import BaseAgent
from agents.insight_agent.prompts import (
    INSIGHT_SYSTEM_PROMPT,
    INSIGHT_GENERATION_PROMPT,
)
from analytics_engine.insight_generator import InsightGenerator
from memory.session_manager import Session
from memory.conversation_memory import ConversationMemory
from intent_engine.intent_schema import Intent
from config import get_logger

logger = get_logger(__name__)


class InsightAgent(BaseAgent):
    """
    Generates prioritized business insights from analytics data.

    Orchestrates the InsightGenerator and adds LLM-powered reasoning
    for richer, more contextual insight generation.
    """

    def __init__(self):
        super().__init__("InsightAgent")
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
        """Generate insights based on available data and context."""
        try:
            self._log_execution("START", "Generating insights")

            data = context or {}
            metrics = data.get("metrics", {})
            trends = data.get("trends", [])
            anomalies = data.get("anomalies", [])

            # Generate structured insights
            insights = await self._generate_insights(
                message, metrics, trends, anomalies, data
            )

            # Build response
            if insights:
                response_text = self._format_insights(insights, message)
            else:
                response_text = await self._generate_llm_insights(message, data)

            self._log_execution("COMPLETE", f"Generated {len(insights)} insights")

            return await self._get_response_message(
                response_text,
                metadata={
                    "agent": "insight",
                    "insight_count": len(insights),
                    "insights": insights[:5],
                },
            )

        except Exception as e:
            logger.error(f"InsightAgent error: {e}")
            return await self._get_response_message(
                "I wasn't able to generate insights with the available data. "
                "Could you provide more context about what you'd like to analyze?"
            )

    async def _generate_insights(
        self,
        message: str,
        metrics: Dict[str, Any],
        trends: List[Dict[str, Any]],
        anomalies: List[Dict[str, Any]],
        full_context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Generate insights from available analytics data."""
        prompt = INSIGHT_GENERATION_PROMPT.format(
            metrics=str(metrics)[:500],
            trends=str(trends)[:500],
            anomalies=str(anomalies)[:500],
            context=str(full_context)[:500],
            focus_areas=message,
        )

        try:
            result = await self.llm_provider.generate_with_structured_output(
                prompt=prompt,
                system=INSIGHT_SYSTEM_PROMPT,
                temperature=0.5,
                max_tokens=1500,
            )

            insights = result.get("insights", []) if isinstance(result, dict) else []
            return insights

        except Exception as e:
            logger.warning(f"Structured insight generation failed: {e}")
            return []

    async def _generate_llm_insights(
        self, message: str, context: Dict[str, Any]
    ) -> str:
        """Fallback: generate insights purely from LLM."""
        prompt = f"User request: {message}\n\nAvailable data: {str(context)[:1000]}"

        response = await self.llm_provider.generate(
            prompt=prompt,
            system=(
                "You are a business analytics expert. Provide 3-5 actionable insights "
                "based on the available data. Be specific and quantitative where possible."
            ),
            temperature=0.5,
            max_tokens=800,
        )
        return response

    def _format_insights(self, insights: List[Dict[str, Any]], question: str) -> str:
        """Format insights into a readable response."""
        response = f"Here are the key insights based on your request:\n\n"

        for i, insight in enumerate(insights[:5], 1):
            title = insight.get("title", "Insight")
            desc = insight.get("description", "")
            severity = insight.get("severity", "")
            confidence = insight.get("confidence", 0)

            severity_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(severity, "•")

            response += f"{severity_icon} **{title}**\n"
            response += f"   {desc}\n"

            recs = insight.get("recommendations", [])
            if recs:
                response += f"   → Action: {recs[0]}\n"
            response += "\n"

        return response
