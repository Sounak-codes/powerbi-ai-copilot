"""
Routing rules for intent-based agent selection.
"""
from typing import Dict, Callable, Optional, List
from intent_engine.intent_schema import Intent, IntentCategory


class RoutingRule:
    """A routing rule that maps intents to agents."""

    def __init__(
        self,
        intent_category: IntentCategory,
        agent_name: str,
        min_confidence: float = 0.5,
    ):
        self.intent_category = intent_category
        self.agent_name = agent_name
        self.min_confidence = min_confidence

    def matches(self, intent: Intent) -> bool:
        """Check if intent matches this rule."""
        return (
            intent.category == self.intent_category
            and intent.confidence >= self.min_confidence
        )


class RoutingRuleSet:
    """Set of routing rules."""

    DEFAULT_RULES = [
        RoutingRule(IntentCategory.QUESTION, "rag_agent"),
        RoutingRule(IntentCategory.ANALYSIS, "analytics_agent"),
        RoutingRule(IntentCategory.INSIGHT, "insight_agent"),
        RoutingRule(IntentCategory.EXPLANATION, "rag_agent"),
        RoutingRule(IntentCategory.RECOMMENDATION, "insight_agent"),
        RoutingRule(IntentCategory.DAX, "dax_agent"),
        RoutingRule(IntentCategory.REPORT, "analytics_agent"),
        RoutingRule(IntentCategory.UNKNOWN, "planner_agent"),
    ]

    def __init__(self, rules: Optional[List[RoutingRule]] = None):
        self.rules = rules or self.DEFAULT_RULES

    def get_agent_for_intent(self, intent: Intent) -> str:
        """Get the agent that should handle this intent."""
        for rule in self.rules:
            if rule.matches(intent):
                return rule.agent_name

        # Fallback to planner agent
        return "planner_agent"

    def add_rule(self, rule: RoutingRule):
        """Add a routing rule."""
        self.rules.append(rule)

    def clear_rules(self):
        """Clear all rules."""
        self.rules.clear()

    def reset_to_defaults(self):
        """Reset to default rules."""
        self.rules = self.DEFAULT_RULES.copy()
