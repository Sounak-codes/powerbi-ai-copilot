"""
Action generator for producing specific next steps.

Converts high-level recommendations into concrete, time-bound
actions that can be tracked and executed.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from config import get_logger

logger = get_logger(__name__)


class ActionUrgency(str, Enum):
    """Urgency level for actions."""
    IMMEDIATE = "immediate"  # Today
    SHORT_TERM = "short_term"  # This week
    MEDIUM_TERM = "medium_term"  # This month
    LONG_TERM = "long_term"  # This quarter


class ActionCategory(str, Enum):
    """Categories of actions."""
    ANALYSIS = "analysis"
    COMMUNICATION = "communication"
    PROCESS_CHANGE = "process_change"
    MONITORING = "monitoring"
    DATA_QUALITY = "data_quality"


@dataclass
class Action:
    """A specific, actionable next step."""
    title: str
    description: str
    urgency: ActionUrgency
    category: ActionCategory
    owner_role: str  # "analyst", "manager", "executive", "engineer"
    estimated_effort: str  # "5 minutes", "1 hour", "half day", "multi-day"
    expected_outcome: str
    metric: Optional[str] = None
    deadline_days: int = 7

    def to_dict(self) -> Dict[str, Any]:
        deadline = (datetime.utcnow() + timedelta(days=self.deadline_days)).isoformat()
        return {
            "title": self.title,
            "description": self.description,
            "urgency": self.urgency.value,
            "category": self.category.value,
            "owner_role": self.owner_role,
            "estimated_effort": self.estimated_effort,
            "expected_outcome": self.expected_outcome,
            "metric": self.metric,
            "suggested_deadline": deadline,
        }


class ActionGenerator:
    """
    Generate specific actions from recommendations.

    Transforms abstract recommendations into concrete steps
    with owners, deadlines, and expected outcomes.
    """

    def generate_actions(
        self,
        recommendations: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Action]:
        """
        Generate actions from a list of recommendations.

        Args:
            recommendations: List of recommendation dicts.
            context: Report/business context for tailoring actions.

        Returns:
            List of Actions sorted by urgency.
        """
        actions = []

        for rec in recommendations:
            rec_type = rec.get("type", "")
            priority = rec.get("priority", "medium")
            metric = rec.get("metric")

            generated = self._generate_for_type(rec_type, priority, metric, rec)
            actions.extend(generated)

        # Sort by urgency
        urgency_order = {
            ActionUrgency.IMMEDIATE: 0,
            ActionUrgency.SHORT_TERM: 1,
            ActionUrgency.MEDIUM_TERM: 2,
            ActionUrgency.LONG_TERM: 3,
        }
        actions.sort(key=lambda a: urgency_order.get(a.urgency, 4))

        return actions

    def _generate_for_type(
        self,
        rec_type: str,
        priority: str,
        metric: Optional[str],
        rec: Dict[str, Any],
    ) -> List[Action]:
        """Generate actions based on recommendation type."""
        metric_name = metric or "the metric"

        if rec_type == "investigate":
            return self._investigation_actions(metric_name, priority, rec)
        elif rec_type == "monitor":
            return self._monitoring_actions(metric_name, priority)
        elif rec_type == "alert":
            return self._alert_actions(metric_name, priority)
        elif rec_type == "optimize":
            return self._optimization_actions(metric_name, priority)
        elif rec_type == "strategic":
            return self._strategic_actions(metric_name, rec)
        else:
            return [Action(
                title=f"Review {metric_name}",
                description=rec.get("description", f"Review {metric_name} status."),
                urgency=ActionUrgency.SHORT_TERM,
                category=ActionCategory.ANALYSIS,
                owner_role="analyst",
                estimated_effort="30 minutes",
                expected_outcome="Clear understanding of current status.",
                metric=metric,
            )]

    def _investigation_actions(
        self, metric: str, priority: str, rec: Dict[str, Any]
    ) -> List[Action]:
        """Generate investigation actions."""
        urgency = ActionUrgency.IMMEDIATE if priority == "critical" else ActionUrgency.SHORT_TERM

        actions = [
            Action(
                title=f"Root cause analysis for {metric}",
                description=f"Run contribution analysis to identify what's driving changes in {metric}.",
                urgency=urgency,
                category=ActionCategory.ANALYSIS,
                owner_role="analyst",
                estimated_effort="1 hour",
                expected_outcome=f"Identified top 3 drivers of {metric} change.",
                metric=metric,
                deadline_days=1 if priority == "critical" else 3,
            ),
            Action(
                title=f"Report findings on {metric}",
                description=f"Summarize investigation results and proposed next steps for {metric}.",
                urgency=ActionUrgency.SHORT_TERM,
                category=ActionCategory.COMMUNICATION,
                owner_role="analyst",
                estimated_effort="30 minutes",
                expected_outcome="Stakeholders informed with clear next steps.",
                metric=metric,
                deadline_days=3,
            ),
        ]

        return actions

    def _monitoring_actions(self, metric: str, priority: str) -> List[Action]:
        """Generate monitoring actions."""
        return [
            Action(
                title=f"Set up enhanced monitoring for {metric}",
                description=f"Configure alerts at warning/critical thresholds for {metric}.",
                urgency=ActionUrgency.SHORT_TERM,
                category=ActionCategory.MONITORING,
                owner_role="analyst",
                estimated_effort="30 minutes",
                expected_outcome="Automated alerts configured for early detection.",
                metric=metric,
                deadline_days=5,
            ),
        ]

    def _alert_actions(self, metric: str, priority: str) -> List[Action]:
        """Generate alert response actions."""
        return [
            Action(
                title=f"Validate anomalies in {metric}",
                description=f"Check if anomalies in {metric} are due to data quality issues or genuine events.",
                urgency=ActionUrgency.IMMEDIATE if priority == "critical" else ActionUrgency.SHORT_TERM,
                category=ActionCategory.DATA_QUALITY,
                owner_role="analyst",
                estimated_effort="1 hour",
                expected_outcome="Anomalies classified as data issues or real events.",
                metric=metric,
                deadline_days=2,
            ),
        ]

    def _optimization_actions(self, metric: str, priority: str) -> List[Action]:
        """Generate optimization actions."""
        return [
            Action(
                title=f"Identify optimization levers for {metric}",
                description=f"Analyze which factors can be adjusted to improve {metric}.",
                urgency=ActionUrgency.MEDIUM_TERM,
                category=ActionCategory.ANALYSIS,
                owner_role="manager",
                estimated_effort="half day",
                expected_outcome="Prioritized list of improvement levers.",
                metric=metric,
                deadline_days=14,
            ),
        ]

    def _strategic_actions(self, metric: str, rec: Dict[str, Any]) -> List[Action]:
        """Generate strategic actions."""
        return [
            Action(
                title=f"Strategic review: {rec.get('title', metric)}",
                description=rec.get("description", f"Review strategic implications for {metric}."),
                urgency=ActionUrgency.LONG_TERM,
                category=ActionCategory.PROCESS_CHANGE,
                owner_role="manager",
                estimated_effort="multi-day",
                expected_outcome="Strategic decision with documented rationale.",
                metric=metric,
                deadline_days=30,
            ),
        ]
