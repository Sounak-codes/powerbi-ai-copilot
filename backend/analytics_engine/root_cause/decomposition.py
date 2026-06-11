"""
Metric decomposition for root cause analysis.

Breaks down metric changes into constituent effects:
- Mix effect (composition change)
- Rate effect (per-segment performance change)
- Volume effect (quantity change)
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import numpy as np
from config import get_logger

logger = get_logger(__name__)


@dataclass
class DecompositionEffect:
    """A single effect in the decomposition."""
    effect_type: str  # "mix", "rate", "volume", "interaction"
    value: float
    percentage_of_total: float
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "effect_type": self.effect_type,
            "value": round(self.value, 4),
            "percentage_of_total": round(self.percentage_of_total, 2),
            "description": self.description,
        }


@dataclass
class DecompositionResult:
    """Result of metric decomposition."""
    metric_name: str
    total_change: float
    effects: List[DecompositionEffect]
    segment_details: List[Dict[str, Any]]
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "total_change": round(self.total_change, 4),
            "effects": [e.to_dict() for e in self.effects],
            "segment_details": self.segment_details,
            "description": self.description,
        }


class MetricDecomposer:
    """
    Decomposes metric changes into mix, rate, and volume effects.

    Mix/Rate decomposition (Dunn method):
    - Rate effect: What would happen if only rates changed (mix held constant)?
    - Mix effect: What would happen if only composition changed (rates held constant)?
    - Interaction: The combined effect of both changing.
    """

    def decompose_rate_mix(
        self,
        metric_name: str,
        current_segments: Dict[str, Dict[str, float]],
        previous_segments: Dict[str, Dict[str, float]],
    ) -> DecompositionResult:
        """
        Decompose change into rate and mix effects.

        Args:
            metric_name: Name of the metric.
            current_segments: Dict[segment -> {"rate": float, "volume": float}].
            previous_segments: Same structure for previous period.

        Returns:
            DecompositionResult with effects breakdown.
        """
        all_segments = set(
            list(current_segments.keys()) + list(previous_segments.keys())
        )

        # Calculate totals
        prev_total_volume = sum(
            s.get("volume", 0) for s in previous_segments.values()
        )
        curr_total_volume = sum(
            s.get("volume", 0) for s in current_segments.values()
        )

        # Previous weighted average rate
        prev_weighted_rate = (
            sum(
                s.get("rate", 0) * s.get("volume", 0)
                for s in previous_segments.values()
            )
            / prev_total_volume
            if prev_total_volume > 0
            else 0
        )

        # Current weighted average rate
        curr_weighted_rate = (
            sum(
                s.get("rate", 0) * s.get("volume", 0)
                for s in current_segments.values()
            )
            / curr_total_volume
            if curr_total_volume > 0
            else 0
        )

        total_change = curr_weighted_rate - prev_weighted_rate

        # Decompose
        rate_effect = 0.0
        mix_effect = 0.0
        segment_details = []

        for segment in all_segments:
            curr = current_segments.get(segment, {"rate": 0.0, "volume": 0.0})
            prev = previous_segments.get(segment, {"rate": 0.0, "volume": 0.0})

            curr_rate = curr.get("rate", 0.0)
            prev_rate = prev.get("rate", 0.0)
            curr_vol = curr.get("volume", 0.0)
            prev_vol = prev.get("volume", 0.0)

            # Previous mix weight
            prev_weight = prev_vol / prev_total_volume if prev_total_volume > 0 else 0
            # Current mix weight
            curr_weight = curr_vol / curr_total_volume if curr_total_volume > 0 else 0

            # Rate effect for this segment (weight held at previous)
            seg_rate_effect = prev_weight * (curr_rate - prev_rate)
            rate_effect += seg_rate_effect

            # Mix effect for this segment (rate held at previous)
            seg_mix_effect = (curr_weight - prev_weight) * (prev_rate - prev_weighted_rate)
            mix_effect += seg_mix_effect

            segment_details.append({
                "segment": segment,
                "rate_effect": round(seg_rate_effect, 4),
                "mix_effect": round(seg_mix_effect, 4),
                "prev_rate": round(prev_rate, 4),
                "curr_rate": round(curr_rate, 4),
                "prev_weight": round(prev_weight, 4),
                "curr_weight": round(curr_weight, 4),
            })

        # Interaction effect (residual)
        interaction = total_change - rate_effect - mix_effect

        # Build effects list
        effects = []
        abs_total = abs(total_change) if total_change != 0 else 1.0

        effects.append(DecompositionEffect(
            effect_type="rate",
            value=rate_effect,
            percentage_of_total=(rate_effect / abs_total) * 100,
            description=(
                f"Rate effect: {rate_effect:+.4f} — change due to performance "
                f"within segments (holding mix constant)."
            ),
        ))
        effects.append(DecompositionEffect(
            effect_type="mix",
            value=mix_effect,
            percentage_of_total=(mix_effect / abs_total) * 100,
            description=(
                f"Mix effect: {mix_effect:+.4f} — change due to composition shift "
                f"between segments (holding rates constant)."
            ),
        ))
        if abs(interaction) > 0.0001:
            effects.append(DecompositionEffect(
                effect_type="interaction",
                value=interaction,
                percentage_of_total=(interaction / abs_total) * 100,
                description=(
                    f"Interaction effect: {interaction:+.4f} — joint impact "
                    f"of rates and mix changing simultaneously."
                ),
            ))

        # Sort segment details by absolute rate effect
        segment_details.sort(
            key=lambda s: abs(s["rate_effect"]) + abs(s["mix_effect"]),
            reverse=True,
        )

        description = self._build_description(
            metric_name, total_change, rate_effect, mix_effect, interaction
        )

        return DecompositionResult(
            metric_name=metric_name,
            total_change=total_change,
            effects=effects,
            segment_details=segment_details[:10],
            description=description,
        )

    def decompose_additive(
        self,
        metric_name: str,
        current_components: Dict[str, float],
        previous_components: Dict[str, float],
    ) -> DecompositionResult:
        """
        Simple additive decomposition for metrics that sum.

        For metrics like Total Revenue = Product A + Product B + Product C.

        Args:
            metric_name: Name of the total metric.
            current_components: Dict[component -> current value].
            previous_components: Dict[component -> previous value].

        Returns:
            DecompositionResult showing each component's contribution.
        """
        all_components = set(
            list(current_components.keys()) + list(previous_components.keys())
        )

        total_current = sum(current_components.values())
        total_previous = sum(previous_components.values())
        total_change = total_current - total_previous
        abs_total = abs(total_change) if total_change != 0 else 1.0

        effects = []
        segment_details = []

        for comp in all_components:
            curr = current_components.get(comp, 0.0)
            prev = previous_components.get(comp, 0.0)
            change = curr - prev

            effects.append(DecompositionEffect(
                effect_type="component",
                value=change,
                percentage_of_total=(change / abs_total) * 100,
                description=f"{comp}: {prev:.2f} → {curr:.2f} (change: {change:+.2f})",
            ))

            segment_details.append({
                "component": comp,
                "current": round(curr, 2),
                "previous": round(prev, 2),
                "change": round(change, 2),
                "pct_of_total_change": round((change / abs_total) * 100, 1),
            })

        # Sort by absolute change
        effects.sort(key=lambda e: abs(e.value), reverse=True)
        segment_details.sort(key=lambda s: abs(s["change"]), reverse=True)

        direction = "increased" if total_change > 0 else "decreased"
        pct = abs(total_change / total_previous * 100) if total_previous != 0 else 0

        description = (
            f"{metric_name} {direction} by {abs(total_change):.2f} ({pct:.1f}%). "
            f"Largest contributor: {effects[0].description}" if effects else ""
        )

        return DecompositionResult(
            metric_name=metric_name,
            total_change=total_change,
            effects=effects,
            segment_details=segment_details,
            description=description,
        )

    def _build_description(
        self,
        metric_name: str,
        total_change: float,
        rate_effect: float,
        mix_effect: float,
        interaction: float,
    ) -> str:
        """Build natural language decomposition description."""
        if total_change == 0:
            return f"{metric_name} is unchanged."

        direction = "increased" if total_change > 0 else "decreased"
        parts = [f"{metric_name} {direction} by {abs(total_change):.4f}."]

        # Identify dominant effect
        effects = {
            "rate changes (performance)": rate_effect,
            "mix shift (composition)": mix_effect,
        }

        dominant = max(effects.items(), key=lambda x: abs(x[1]))
        pct = abs(dominant[1] / total_change * 100) if total_change != 0 else 0

        parts.append(
            f" Primarily driven by {dominant[0]} ({pct:.0f}% of change)."
        )

        return "".join(parts)
