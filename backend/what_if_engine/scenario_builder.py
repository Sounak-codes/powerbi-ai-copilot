"""
Scenario builder for constructing what-if scenarios.

Provides templates and helpers for building common business scenarios.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from config import get_logger

logger = get_logger(__name__)


@dataclass
class Scenario:
    """A what-if scenario definition."""
    name: str
    description: str
    changes: Dict[str, float]
    category: str = "custom"  # "growth", "cost", "risk", "optimization", "custom"
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "changes": self.changes,
            "category": self.category,
            "tags": self.tags,
        }


class ScenarioBuilder:
    """
    Build what-if scenarios from templates or custom definitions.

    Provides common scenario templates (growth, cost reduction, risk)
    and the ability to build custom scenarios from user input.
    """

    TEMPLATES = {
        "revenue_growth_10": {
            "name": "10% Revenue Growth",
            "description": "What if revenue grows by 10%?",
            "category": "growth",
            "multiplier_field": "revenue",
            "multiplier": 1.10,
        },
        "cost_reduction_15": {
            "name": "15% Cost Reduction",
            "description": "What if we cut costs by 15%?",
            "category": "cost",
            "multiplier_field": "costs",
            "multiplier": 0.85,
        },
        "volume_increase_20": {
            "name": "20% Volume Increase",
            "description": "What if transaction volume increases 20%?",
            "category": "growth",
            "multiplier_field": "volume",
            "multiplier": 1.20,
        },
        "churn_increase_5": {
            "name": "5% Churn Increase",
            "description": "What if churn rate rises by 5 percentage points?",
            "category": "risk",
            "multiplier_field": "churn_rate",
            "adder": 0.05,
        },
    }

    def from_template(
        self,
        template_name: str,
        current_values: Dict[str, float],
    ) -> Optional[Scenario]:
        """
        Build a scenario from a template.

        Args:
            template_name: Name of the template.
            current_values: Current metric values.

        Returns:
            Scenario if template exists, None otherwise.
        """
        template = self.TEMPLATES.get(template_name)
        if not template:
            logger.warning(f"Unknown scenario template: {template_name}")
            return None

        field_name = template.get("multiplier_field", "")
        current = current_values.get(field_name, 0)

        if "multiplier" in template:
            new_value = current * template["multiplier"]
        elif "adder" in template:
            new_value = current + template["adder"]
        else:
            new_value = current

        return Scenario(
            name=template["name"],
            description=template["description"],
            changes={field_name: new_value},
            category=template.get("category", "custom"),
            tags=[template_name],
        )

    def build_custom(
        self,
        name: str,
        changes: Dict[str, float],
        description: Optional[str] = None,
    ) -> Scenario:
        """Build a custom scenario."""
        if not description:
            change_descs = [f"{k} → {v}" for k, v in changes.items()]
            description = f"Custom scenario: {', '.join(change_descs)}"

        return Scenario(
            name=name,
            description=description,
            changes=changes,
            category="custom",
        )

    def build_percentage_change(
        self,
        name: str,
        metric: str,
        percentage: float,
        current_value: float,
    ) -> Scenario:
        """Build a scenario from a percentage change."""
        new_value = current_value * (1 + percentage / 100)
        direction = "increase" if percentage > 0 else "decrease"

        return Scenario(
            name=name,
            description=f"What if {metric} {direction}s by {abs(percentage)}%?",
            changes={metric: new_value},
            category="custom",
        )

    def build_comparative(
        self,
        base_scenario: Scenario,
        alternative_changes: Dict[str, float],
        alt_name: Optional[str] = None,
    ) -> List[Scenario]:
        """Build a pair of scenarios for comparison."""
        alt = Scenario(
            name=alt_name or f"{base_scenario.name} (Alternative)",
            description=f"Alternative to: {base_scenario.description}",
            changes=alternative_changes,
            category=base_scenario.category,
        )
        return [base_scenario, alt]

    def list_templates(self) -> List[Dict[str, Any]]:
        """List available scenario templates."""
        return [
            {"id": k, "name": v["name"], "description": v["description"], "category": v["category"]}
            for k, v in self.TEMPLATES.items()
        ]
