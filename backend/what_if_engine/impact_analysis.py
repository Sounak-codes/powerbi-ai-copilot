"""
Impact analysis for what-if scenarios.

Quantifies the business impact of scenario changes including
financial implications, risk assessment, and sensitivity analysis.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import numpy as np
from config import get_logger

logger = get_logger(__name__)


@dataclass
class ImpactAssessment:
    """Assessment of a scenario's business impact."""
    scenario_name: str
    financial_impact: float
    risk_level: str  # "low", "medium", "high"
    feasibility: str  # "easy", "moderate", "difficult"
    time_to_impact: str  # "immediate", "short_term", "long_term"
    sensitivity_scores: Dict[str, float] = field(default_factory=dict)
    key_risks: List[str] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "financial_impact": round(self.financial_impact, 2),
            "risk_level": self.risk_level,
            "feasibility": self.feasibility,
            "time_to_impact": self.time_to_impact,
            "sensitivity_scores": {k: round(v, 4) for k, v in self.sensitivity_scores.items()},
            "key_risks": self.key_risks,
            "description": self.description,
        }


class ImpactAnalyzer:
    """
    Analyze the business impact of what-if scenarios.

    Provides:
    - Financial impact quantification
    - Sensitivity analysis
    - Risk assessment
    - Feasibility evaluation
    """

    def assess_impact(
        self,
        scenario_name: str,
        changes: Dict[str, float],
        projected_impacts: Dict[str, float],
        current_values: Dict[str, float],
        financial_weights: Optional[Dict[str, float]] = None,
    ) -> ImpactAssessment:
        """
        Assess the overall impact of a scenario.

        Args:
            scenario_name: Name of the scenario.
            changes: Direct changes applied.
            projected_impacts: Projected downstream impacts.
            current_values: Current baseline values.
            financial_weights: Optional mapping of metrics to monetary value.

        Returns:
            ImpactAssessment with comprehensive evaluation.
        """
        # Financial impact
        financial = self._calculate_financial_impact(
            changes, projected_impacts, current_values, financial_weights
        )

        # Risk level
        risk = self._assess_risk(changes, current_values)

        # Feasibility
        feasibility = self._assess_feasibility(changes, current_values)

        # Sensitivity
        sensitivity = self._sensitivity_analysis(changes, projected_impacts, current_values)

        # Key risks
        risks = self._identify_risks(changes, projected_impacts, current_values)

        # Time to impact
        time_to_impact = self._estimate_time_to_impact(changes, current_values)

        description = self._build_description(
            scenario_name, financial, risk, feasibility, time_to_impact
        )

        return ImpactAssessment(
            scenario_name=scenario_name,
            financial_impact=financial,
            risk_level=risk,
            feasibility=feasibility,
            time_to_impact=time_to_impact,
            sensitivity_scores=sensitivity,
            key_risks=risks,
            description=description,
        )

    def compare_scenarios(
        self, assessments: List[ImpactAssessment]
    ) -> Dict[str, Any]:
        """Compare multiple scenario impact assessments."""
        if not assessments:
            return {"comparison": [], "recommendation": "No scenarios to compare."}

        ranked = sorted(assessments, key=lambda a: a.financial_impact, reverse=True)

        comparison = []
        for i, assessment in enumerate(ranked, 1):
            comparison.append({
                "rank": i,
                "scenario": assessment.scenario_name,
                "financial_impact": assessment.financial_impact,
                "risk": assessment.risk_level,
                "feasibility": assessment.feasibility,
            })

        # Simple recommendation: best financial impact with acceptable risk
        acceptable = [a for a in ranked if a.risk_level != "high"]
        if acceptable:
            best = acceptable[0]
            recommendation = (
                f"Recommended: '{best.scenario_name}' — "
                f"financial impact of {best.financial_impact:+.2f} with {best.risk_level} risk."
            )
        else:
            recommendation = "All scenarios carry high risk — proceed with caution."

        return {"comparison": comparison, "recommendation": recommendation}

    def _calculate_financial_impact(
        self,
        changes: Dict[str, float],
        impacts: Dict[str, float],
        current: Dict[str, float],
        weights: Optional[Dict[str, float]],
    ) -> float:
        """Calculate total financial impact."""
        if not weights:
            # Default: sum all changes as direct financial impact
            total = 0.0
            for metric, new_val in changes.items():
                curr = current.get(metric, 0)
                total += new_val - curr
            for metric, impact in impacts.items():
                total += impact
            return total

        total = 0.0
        all_changes = {**{m: v - current.get(m, 0) for m, v in changes.items()}, **impacts}
        for metric, delta in all_changes.items():
            weight = weights.get(metric, 0)
            total += delta * weight
        return total

    def _assess_risk(self, changes: Dict[str, float], current: Dict[str, float]) -> str:
        """Assess risk level based on magnitude of changes."""
        max_pct_change = 0.0
        for metric, new_val in changes.items():
            curr = current.get(metric, 0)
            if curr != 0:
                pct = abs((new_val - curr) / curr)
                max_pct_change = max(max_pct_change, pct)

        if max_pct_change > 0.30:
            return "high"
        if max_pct_change > 0.10:
            return "medium"
        return "low"

    def _assess_feasibility(self, changes: Dict[str, float], current: Dict[str, float]) -> str:
        """Assess feasibility of achieving the changes."""
        total_change = sum(
            abs(v - current.get(m, 0)) / abs(current.get(m, 1)) * 100
            for m, v in changes.items()
            if current.get(m, 0) != 0
        )
        avg_change = total_change / max(len(changes), 1)

        if avg_change < 5:
            return "easy"
        if avg_change < 20:
            return "moderate"
        return "difficult"

    def _sensitivity_analysis(
        self,
        changes: Dict[str, float],
        impacts: Dict[str, float],
        current: Dict[str, float],
    ) -> Dict[str, float]:
        """Calculate sensitivity of outcomes to input changes."""
        sensitivities = {}

        for input_metric, new_val in changes.items():
            curr = current.get(input_metric, 0)
            input_delta = new_val - curr
            if input_delta == 0:
                continue

            for output_metric, output_delta in impacts.items():
                # Elasticity: % change output / % change input
                input_pct = input_delta / abs(curr) if curr != 0 else 0
                output_curr = current.get(output_metric, 0)
                output_pct = output_delta / abs(output_curr) if output_curr != 0 else 0

                elasticity = output_pct / input_pct if input_pct != 0 else 0
                sensitivities[f"{input_metric}->{output_metric}"] = float(elasticity)

        return sensitivities

    def _identify_risks(
        self,
        changes: Dict[str, float],
        impacts: Dict[str, float],
        current: Dict[str, float],
    ) -> List[str]:
        """Identify key risks of the scenario."""
        risks = []

        for metric, new_val in changes.items():
            curr = current.get(metric, 0)
            pct = ((new_val - curr) / abs(curr) * 100) if curr != 0 else 0
            if abs(pct) > 25:
                risks.append(f"Large change in {metric} ({pct:+.0f}%) may be difficult to sustain.")

        # Check for negative downstream impacts
        for metric, delta in impacts.items():
            curr = current.get(metric, 0)
            pct = (delta / abs(curr) * 100) if curr != 0 else 0
            if pct < -10:
                risks.append(f"Negative impact on {metric} ({pct:.0f}%).")

        return risks

    def _estimate_time_to_impact(self, changes: Dict[str, float], current: Dict[str, float]) -> str:
        """Estimate how quickly the impact would be realized."""
        avg_pct = np.mean([
            abs((v - current.get(m, 0)) / current.get(m, 1) * 100)
            for m, v in changes.items()
            if current.get(m, 0) != 0
        ]) if changes else 0

        if avg_pct < 5:
            return "immediate"
        if avg_pct < 15:
            return "short_term"
        return "long_term"

    def _build_description(
        self, name: str, financial: float, risk: str, feasibility: str, time: str
    ) -> str:
        """Build description of the impact assessment."""
        return (
            f"Scenario '{name}': Projected financial impact of {financial:+,.2f}. "
            f"Risk: {risk}. Feasibility: {feasibility}. Time to realize: {time}."
        )
