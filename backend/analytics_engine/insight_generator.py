"""
Insight generator for producing actionable insights.
"""
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from llm.providers.provider_factory import ProviderFactory
from schemas.insight import Insight, InsightType, InsightSeverity
from config import get_logger

logger = get_logger(__name__)


class InsightGenerator:
    """Generate insights from data."""

    SYSTEM_PROMPT = """You are an insight generation expert for Power BI data analysis.
Generate clear, actionable insights from the provided data.
Focus on trends, anomalies, patterns, and business recommendations.
Respond with JSON array of insights with fields: type, title, description, confidence (0-1), severity."""

    def __init__(self):
        self.llm_provider = ProviderFactory.get_default_provider()

    async def generate_insights(
        self,
        data: Dict[str, Any],
        metrics: Optional[List[str]] = None,
        depth: str = "standard",
    ) -> List[Insight]:
        """Generate insights from data."""
        try:
            prompt = self._build_prompt(data, metrics, depth)

            response = await self.llm_provider.generate_with_structured_output(
                prompt=prompt,
                system=self.SYSTEM_PROMPT,
                temperature=0.5,
                max_tokens=2000,
            )

            insights = []

            if isinstance(response, dict):
                response_data = response.get("insights", [])
            else:
                response_data = response

            for item in response_data:
                insight = Insight(
                    id=str(uuid.uuid4()),
                    type=InsightType(item.get("type", "pattern")),
                    title=item.get("title", "Insight"),
                    description=item.get("description", ""),
                    metrics=item.get("metrics", {}),
                    confidence=item.get("confidence", 0.5),
                    severity=InsightSeverity(
                        item.get("severity", "medium")
                    ) if item.get("severity") else None,
                    recommendations=item.get("recommendations"),
                    timestamp=datetime.utcnow(),
                )
                insights.append(insight)

            logger.debug(f"Generated {len(insights)} insights")
            return insights

        except Exception as e:
            logger.error(f"Insight generation failed: {e}")
            return []

    def _build_prompt(
        self,
        data: Dict[str, Any],
        metrics: Optional[List[str]],
        depth: str,
    ) -> str:
        """Build prompt for insight generation."""
        prompt = f"Analyze this data and generate insights:\n"
        prompt += f"Depth: {depth}\n"

        if metrics:
            prompt += f"Focus on these metrics: {', '.join(metrics)}\n"

        prompt += f"Data: {str(data)[:2000]}\n"

        return prompt

    async def generate_trend_insight(
        self, metric_name: str, values: List[float], dates: List[str]
    ) -> Optional[Insight]:
        """Generate trend insight from time series."""
        try:
            prompt = f"""Analyze this time series for trends:
Metric: {metric_name}
Dates: {dates[-5:]}  # Last 5 dates
Values: {values[-5:]}  # Last 5 values

Describe the trend direction, magnitude, and business implications."""

            response = await self.llm_provider.generate(
                prompt=prompt,
                system="You are a data analyst. Provide a concise trend analysis.",
                temperature=0.3,
                max_tokens=300,
            )

            return Insight(
                id=str(uuid.uuid4()),
                type=InsightType.TREND,
                title=f"{metric_name} Trend Analysis",
                description=response,
                metrics={metric_name: values[-1] if values else 0},
                confidence=0.8,
                timestamp=datetime.utcnow(),
            )

        except Exception as e:
            logger.error(f"Trend insight generation failed: {e}")
            return None
