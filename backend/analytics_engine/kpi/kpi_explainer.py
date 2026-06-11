"""
KPI explainer — generates natural language explanations of KPI behavior.

Uses LLM to provide business-friendly explanations of what a KPI
measures, why it changed, and what it means for the business.
"""
from typing import Dict, Any, List, Optional
from llm.providers.provider_factory import ProviderFactory
from config import get_logger

logger = get_logger(__name__)


class KPIExplainer:
    """
    Generate natural language explanations for KPI behavior.

    Combines statistical context with LLM generation to produce
    business-ready explanations.
    """

    SYSTEM_PROMPT = """You are a business analytics expert explaining KPIs to executives.
Keep explanations clear, concise, and actionable. Use business language, not technical jargon.
Focus on: what the KPI measures, what the current value means, what's driving changes, and recommended actions."""

    def __init__(self):
        self.llm_provider = ProviderFactory.get_default_provider()

    async def explain_kpi(
        self,
        kpi_name: str,
        current_value: float,
        target_value: Optional[float] = None,
        previous_value: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate an explanation for a KPI's current state.

        Args:
            kpi_name: Name of the KPI.
            current_value: Current KPI value.
            target_value: Target value (optional).
            previous_value: Previous period value (optional).
            context: Additional context (trends, contributors, etc.).

        Returns:
            Dictionary with explanation, key points, and recommendations.
        """
        prompt = self._build_prompt(
            kpi_name, current_value, target_value, previous_value, context
        )

        try:
            response = await self.llm_provider.generate(
                prompt=prompt,
                system=self.SYSTEM_PROMPT,
                temperature=0.5,
                max_tokens=500,
            )

            return {
                "kpi_name": kpi_name,
                "explanation": response,
                "current_value": current_value,
                "target_value": target_value,
                "status": self._quick_status(current_value, target_value, previous_value),
            }

        except Exception as e:
            logger.error(f"KPI explanation failed: {e}")
            return {
                "kpi_name": kpi_name,
                "explanation": self._fallback_explanation(
                    kpi_name, current_value, target_value, previous_value
                ),
                "current_value": current_value,
                "target_value": target_value,
                "status": self._quick_status(current_value, target_value, previous_value),
            }

    async def explain_change(
        self,
        kpi_name: str,
        current_value: float,
        previous_value: float,
        contributors: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Generate an explanation for why a KPI changed."""
        change = current_value - previous_value
        change_pct = (change / abs(previous_value) * 100) if previous_value != 0 else 0

        prompt = f"""Explain this KPI change in 2-3 sentences:
KPI: {kpi_name}
Previous: {previous_value:.2f}
Current: {current_value:.2f}
Change: {change:+.2f} ({change_pct:+.1f}%)
"""
        if contributors:
            prompt += f"\nTop contributors to change:\n"
            for c in contributors[:5]:
                prompt += f"- {c.get('segment', 'Unknown')}: {c.get('change', 0):+.2f}\n"

        try:
            response = await self.llm_provider.generate(
                prompt=prompt,
                system=self.SYSTEM_PROMPT,
                temperature=0.4,
                max_tokens=300,
            )
            return response
        except Exception as e:
            logger.error(f"Change explanation failed: {e}")
            direction = "increased" if change > 0 else "decreased"
            return f"{kpi_name} {direction} by {abs(change_pct):.1f}% from {previous_value:.2f} to {current_value:.2f}."

    def _build_prompt(
        self,
        kpi_name: str,
        current_value: float,
        target_value: Optional[float],
        previous_value: Optional[float],
        context: Optional[Dict[str, Any]],
    ) -> str:
        """Build prompt for KPI explanation."""
        prompt = f"Explain this KPI to a business stakeholder:\n\n"
        prompt += f"KPI: {kpi_name}\n"
        prompt += f"Current Value: {current_value:.2f}\n"

        if target_value:
            achievement = (current_value / target_value * 100) if target_value != 0 else 0
            prompt += f"Target: {target_value:.2f} (Achievement: {achievement:.1f}%)\n"

        if previous_value:
            change_pct = ((current_value - previous_value) / abs(previous_value) * 100) if previous_value != 0 else 0
            prompt += f"Previous Period: {previous_value:.2f} (Change: {change_pct:+.1f}%)\n"

        if context:
            prompt += f"\nAdditional Context:\n"
            for key, val in context.items():
                prompt += f"- {key}: {val}\n"

        prompt += "\nProvide: 1) What this KPI means, 2) Current status assessment, 3) Recommended action."
        return prompt

    def _quick_status(
        self,
        current: float,
        target: Optional[float],
        previous: Optional[float],
    ) -> str:
        """Quick status assessment without LLM."""
        if target:
            ratio = current / target if target != 0 else 0
            if ratio >= 1.0:
                return "on_track"
            if ratio >= 0.8:
                return "at_risk"
            return "off_track"

        if previous:
            change = (current - previous) / abs(previous) if previous != 0 else 0
            if change > 0.05:
                return "improving"
            if change < -0.05:
                return "declining"

        return "stable"

    def _fallback_explanation(
        self,
        kpi_name: str,
        current: float,
        target: Optional[float],
        previous: Optional[float],
    ) -> str:
        """Generate explanation without LLM as fallback."""
        parts = [f"{kpi_name} is currently at {current:.2f}."]

        if target:
            pct = (current / target * 100) if target != 0 else 0
            if pct >= 100:
                parts.append(f" This meets the target of {target:.2f}.")
            else:
                parts.append(f" This is {100 - pct:.0f}% below the target of {target:.2f}.")

        if previous:
            change = current - previous
            pct = (change / abs(previous) * 100) if previous != 0 else 0
            direction = "up" if change > 0 else "down"
            parts.append(f" {direction.capitalize()} {abs(pct):.1f}% vs previous period.")

        return "".join(parts)
