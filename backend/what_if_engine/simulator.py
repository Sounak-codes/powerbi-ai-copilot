"""
What-if scenario simulator.

Allows users to modify metric values and see projected impact
on dependent metrics using linear models and defined relationships.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import numpy as np
from config import get_logger

logger = get_logger(__name__)


@dataclass
class SimulationResult:
    """Result of a what-if simulation."""
    scenario_name: str
    modified_metrics: Dict[str, float]
    projected_impacts: Dict[str, float]
    confidence: float
    assumptions: List[str]
    narrative: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "modified_metrics": {k: round(v, 2) for k, v in self.modified_metrics.items()},
            "projected_impacts": {k: round(v, 2) for k, v in self.projected_impacts.items()},
            "confidence": round(self.confidence, 3),
            "assumptions": self.assumptions,
            "narrative": self.narrative,
        }


class WhatIfSimulator:
    """
    Simulate what-if scenarios by propagating metric changes
    through a dependency model.
    """

    def __init__(self):
        self._relationships: Dict[str, List[Dict[str, Any]]] = {}

    def register_relationship(
        self,
        source_metric: str,
        target_metric: str,
        coefficient: float,
        relationship_type: str = "linear",
    ):
        """
        Register a relationship between metrics.

        Args:
            source_metric: The metric being changed.
            target_metric: The metric that's impacted.
            coefficient: How much target changes per unit change in source.
            relationship_type: Type of relationship ("linear", "multiplicative").
        """
        if source_metric not in self._relationships:
            self._relationships[source_metric] = []
        self._relationships[source_metric].append({
            "target": target_metric,
            "coefficient": coefficient,
            "type": relationship_type,
        })

    def simulate(
        self,
        scenario_name: str,
        changes: Dict[str, float],
        current_values: Dict[str, float],
    ) -> SimulationResult:
        """
        Run a what-if simulation.

        Args:
            scenario_name: Name for this scenario.
            changes: Dict mapping metric names to their new values.
            current_values: Current values of all metrics.

        Returns:
            SimulationResult with projected impacts.
        """
        if not changes:
            return SimulationResult(
                scenario_name=scenario_name,
                modified_metrics={},
                projected_impacts={},
                confidence=0.0,
                assumptions=["No changes specified."],
            )

        # Calculate deltas
        deltas = {}
        for metric, new_value in changes.items():
            current = current_values.get(metric, 0)
            deltas[metric] = new_value - current

        # Propagate through relationships
        impacts = self._propagate(deltas, current_values)

        # Build assumptions
        assumptions = self._build_assumptions(changes, current_values)

        # Calculate confidence (decreases with chain length)
        confidence = self._calculate_confidence(changes, impacts)

        # Build narrative
        narrative = self._build_narrative(scenario_name, changes, impacts, current_values)

        return SimulationResult(
            scenario_name=scenario_name,
            modified_metrics=changes,
            projected_impacts=impacts,
            confidence=confidence,
            assumptions=assumptions,
            narrative=narrative,
        )

    def _propagate(
        self, deltas: Dict[str, float], current_values: Dict[str, float]
    ) -> Dict[str, float]:
        """Propagate changes through the relationship graph."""
        impacts: Dict[str, float] = {}
        visited = set()
        queue = list(deltas.items())

        while queue:
            metric, delta = queue.pop(0)
            if metric in visited:
                continue
            visited.add(metric)

            # Find downstream impacts
            relationships = self._relationships.get(metric, [])
            for rel in relationships:
                target = rel["target"]
                coeff = rel["coefficient"]
                rel_type = rel["type"]

                if rel_type == "multiplicative":
                    current = current_values.get(target, 0)
                    change_pct = delta / current_values.get(metric, 1) if current_values.get(metric, 0) != 0 else 0
                    target_delta = current * change_pct * coeff
                else:
                    target_delta = delta * coeff

                if target not in impacts:
                    impacts[target] = 0
                impacts[target] += target_delta

                # Continue propagation
                if target not in visited:
                    queue.append((target, target_delta))

        return impacts

    def _calculate_confidence(
        self, changes: Dict[str, float], impacts: Dict[str, float]
    ) -> float:
        """Estimate confidence based on relationship complexity."""
        if not impacts:
            return 0.0

        # More direct relationships = higher confidence
        direct_targets = set()
        for src in changes:
            for rel in self._relationships.get(src, []):
                direct_targets.add(rel.get("target", ""))

        direct_impacts = sum(1 for m in impacts if m in direct_targets)

        ratio = direct_impacts / len(impacts) if impacts else 0
        return min(0.95, 0.5 + ratio * 0.45)

    def _build_assumptions(
        self, changes: Dict[str, float], current_values: Dict[str, float]
    ) -> List[str]:
        """Build the list of assumptions for the simulation."""
        assumptions = [
            "Relationships are approximately linear within the change range.",
            "External factors remain constant.",
            "No feedback loops or saturating effects.",
        ]
        for metric, value in changes.items():
            current = current_values.get(metric, 0)
            pct = ((value - current) / abs(current) * 100) if current != 0 else 0
            assumptions.append(f"{metric}: {current:.2f} → {value:.2f} ({pct:+.1f}%)")
        return assumptions

    def _build_narrative(
        self,
        name: str,
        changes: Dict[str, float],
        impacts: Dict[str, float],
        current: Dict[str, float],
    ) -> str:
        """Build a narrative description of the simulation."""
        parts = [f"Scenario '{name}': "]

        change_descs = []
        for metric, value in changes.items():
            curr = current.get(metric, 0)
            pct = ((value - curr) / abs(curr) * 100) if curr != 0 else 0
            change_descs.append(f"{metric} changes by {pct:+.1f}%")
        parts.append(", ".join(change_descs) + ".")

        if impacts:
            sorted_impacts = sorted(impacts.items(), key=lambda x: abs(x[1]), reverse=True)
            top = sorted_impacts[0]
            curr_val = current.get(top[0], 0)
            pct = (top[1] / abs(curr_val) * 100) if curr_val != 0 else 0
            parts.append(f" Largest projected impact: {top[0]} ({pct:+.1f}%).")

        return "".join(parts)
