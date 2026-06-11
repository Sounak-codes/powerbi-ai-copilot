"""
Executive summary generator.

Produces high-level summaries of report performance suitable
for executive audiences — highlighting key metrics, trends,
concerns, and recommended actions.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from llm.providers.provider_factory import ProviderFactory
from config import get_logger

logger = get_logger(__name__)


@dataclass
class ExecutiveSummaryResult:
    """Structured executive summary."""
    period: str
    headline: str
    key_metrics: List[Dict[str, Any]]
    highlights: List[str]
    concerns: List[str]
    recommendations: List[str]
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "period": self.period,
            "headline": self.headline,
            "key_metrics": self.key_metrics,
            "highlights": self.highlights,
            "concerns": self.concerns,
            "recommendations": self.recommendations,
            "generated_at": self.generated_at,
        }


class ExecutiveSummaryGenerator:
    """
    Generate executive summaries from analytics data.

    Combines KPI data, trend analysis, and anomaly detection
    into a concise executive-level overview.
    """

    SYSTEM_PROMPT = """You are a Chief Analytics Officer preparing an executive summary.
Be concise and impactful. Use business language. Structure as:
1. One-sentence headline
2. 3-5 key metric highlights (with numbers)
3. 2-3 areas of concern
4. 2-3 recommended actions

Respond in JSON with keys: headline, highlights (array), concerns (array), recommendations (array)."""

    def __init__(self):
        self.llm_provider = ProviderFactory.get_default_provider()

    async def generate(
        self,
        kpi_data: List[Dict[str, Any]],
        period: str = "Current Period",
        trends: Optional[List[Dict[str, Any]]] = None,
        anomalies: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExecutiveSummaryResult:
        """
        Generate an executive summary.

        Args:
            kpi_data: List of KPI results with name, value, target, trend.
            period: Time period being summarized.
            trends: Trend analysis results.
            anomalies: Detected anomalies.
            context: Additional context (report name, filters, etc.).

        Returns:
            ExecutiveSummaryResult with structured summary.
        """
        prompt = self._build_prompt(kpi_data, period, trends, anomalies, context)

        try:
            response = await self.llm_provider.generate_with_structured_output(
                prompt=prompt,
                system=self.SYSTEM_PROMPT,
                temperature=0.5,
                max_tokens=1000,
            )

            return ExecutiveSummaryResult(
                period=period,
                headline=response.get("headline", "Performance Summary"),
                key_metrics=self._format_key_metrics(kpi_data),
                highlights=response.get("highlights", []),
                concerns=response.get("concerns", []),
                recommendations=response.get("recommendations", []),
            )

        except Exception as e:
            logger.error(f"Executive summary generation failed: {e}")
            return self._fallback_summary(kpi_data, period, trends, anomalies)

    def _build_prompt(
        self,
        kpi_data: List[Dict[str, Any]],
        period: str,
        trends: Optional[List[Dict[str, Any]]],
        anomalies: Optional[List[Dict[str, Any]]],
        context: Optional[Dict[str, Any]],
    ) -> str:
        """Build the prompt for executive summary generation."""
        prompt = f"Generate an executive summary for: {period}\n\n"

        prompt += "KPI Performance:\n"
        for kpi in kpi_data[:10]:
            name = kpi.get("name", kpi.get("kpi_name", "Unknown"))
            value = kpi.get("current_value", kpi.get("value", 0))
            target = kpi.get("target_value", kpi.get("target"))
            trend = kpi.get("trend", "stable")

            line = f"- {name}: {value}"
            if target:
                pct = (value / target * 100) if target != 0 else 0
                line += f" (target: {target}, {pct:.0f}% achieved)"
            line += f" [trend: {trend}]"
            prompt += line + "\n"

        if trends:
            prompt += "\nKey Trends:\n"
            for t in trends[:5]:
                prompt += f"- {t.get('description', str(t))}\n"

        if anomalies:
            prompt += f"\nAnomalies Detected: {len(anomalies)}\n"
            for a in anomalies[:3]:
                prompt += f"- {a.get('description', str(a))}\n"

        if context:
            prompt += f"\nContext: {context}\n"

        return prompt

    def _format_key_metrics(self, kpi_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format KPI data into consistent key metrics list."""
        metrics = []
        for kpi in kpi_data[:8]:
            metrics.append({
                "name": kpi.get("name", kpi.get("kpi_name", "Unknown")),
                "value": kpi.get("current_value", kpi.get("value", 0)),
                "target": kpi.get("target_value", kpi.get("target")),
                "trend": kpi.get("trend", "stable"),
                "status": kpi.get("status", "unknown"),
            })
        return metrics

    def _fallback_summary(
        self,
        kpi_data: List[Dict[str, Any]],
        period: str,
        trends: Optional[List[Dict[str, Any]]],
        anomalies: Optional[List[Dict[str, Any]]],
    ) -> ExecutiveSummaryResult:
        """Generate a summary without LLM as fallback."""
        # Simple heuristic summary
        on_track = sum(1 for k in kpi_data if k.get("status") in ("on_track", "healthy", "excellent"))
        total = len(kpi_data)

        headline = f"{on_track}/{total} KPIs are on track for {period}."

        highlights = []
        concerns = []
        for kpi in kpi_data[:5]:
            name = kpi.get("name", kpi.get("kpi_name", ""))
            trend = kpi.get("trend", "stable")
            if trend == "improving":
                highlights.append(f"{name} is improving.")
            elif trend == "declining":
                concerns.append(f"{name} is declining and needs attention.")

        recommendations = ["Review underperforming KPIs and identify root causes."]
        if anomalies:
            recommendations.append(f"Investigate {len(anomalies)} detected anomalies.")

        return ExecutiveSummaryResult(
            period=period,
            headline=headline,
            key_metrics=self._format_key_metrics(kpi_data),
            highlights=highlights or ["Overall performance is stable."],
            concerns=concerns or ["No critical concerns identified."],
            recommendations=recommendations,
        )
