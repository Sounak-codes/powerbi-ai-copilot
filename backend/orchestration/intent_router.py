"""
Intent router — higher-level routing logic that combines intent classification,
confidence thresholds, multi-intent detection, and fallback strategies.

Sits between the raw IntentClassifier and the Orchestrator to provide
more intelligent routing decisions.
"""
from typing import Dict, Any, List, Optional, Tuple
from intent_engine.classifier import IntentClassifier
from intent_engine.intent_schema import Intent, IntentCategory
from intent_engine.routing_rules import RoutingRuleSet
from config import get_logger

logger = get_logger(__name__)


class IntentRouter:
    """
    Advanced intent routing with confidence thresholds,
    multi-intent support, and fallback strategies.
    """

    # Minimum confidence to route without clarification
    HIGH_CONFIDENCE_THRESHOLD = 0.75
    # Below this, ask for clarification
    LOW_CONFIDENCE_THRESHOLD = 0.4

    def __init__(self):
        self.classifier = IntentClassifier()
        self.routing_rules = RoutingRuleSet()

    async def route(
        self,
        message: str,
        conversation_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Route a user message to the appropriate agent(s).

        Handles:
        - High confidence: direct routing
        - Medium confidence: route with advisory flag
        - Low confidence: suggest clarification
        - Multi-intent: route to primary, note secondary

        Args:
            message: The user's message.
            conversation_context: Prior conversation context for disambiguation.

        Returns:
            Routing decision with agent name, confidence, and any advisories.
        """
        intent = await self.classifier.classify(message)

        logger.info(
            f"Intent: {intent.category.value} (confidence={intent.confidence:.2f})"
        )

        # High confidence — route directly
        if intent.confidence >= self.HIGH_CONFIDENCE_THRESHOLD:
            agent_name = self.routing_rules.get_agent_for_intent(intent)
            return {
                "decision": "route",
                "agent": agent_name,
                "intent": intent.to_dict(),
                "confidence_level": "high",
                "needs_clarification": False,
            }

        # Low confidence — request clarification
        if intent.confidence < self.LOW_CONFIDENCE_THRESHOLD:
            clarification_questions = self._generate_clarification(
                message, intent, conversation_context
            )
            return {
                "decision": "clarify",
                "intent": intent.to_dict(),
                "confidence_level": "low",
                "needs_clarification": True,
                "clarification_questions": clarification_questions,
                "fallback_agent": "planner_agent",
            }

        # Medium confidence — route but flag uncertainty
        agent_name = self.routing_rules.get_agent_for_intent(intent)

        # Check if conversation context can disambiguate
        boosted_intent = self._apply_context_boost(
            intent, conversation_context
        )
        if boosted_intent:
            agent_name = self.routing_rules.get_agent_for_intent(boosted_intent)
            return {
                "decision": "route",
                "agent": agent_name,
                "intent": boosted_intent.to_dict(),
                "confidence_level": "medium_boosted",
                "needs_clarification": False,
                "context_boosted": True,
            }

        return {
            "decision": "route",
            "agent": agent_name,
            "intent": intent.to_dict(),
            "confidence_level": "medium",
            "needs_clarification": False,
            "advisory": "Confidence is moderate — response may need refinement.",
        }

    async def detect_multi_intent(self, message: str) -> List[Dict[str, Any]]:
        """
        Detect if a message contains multiple intents.

        For example: "Show me the trend and also generate a DAX measure for it"
        contains both analysis and dax_generation intents.
        """
        # Split on conjunctions that typically separate intents
        separators = [" and also ", " and then ", " also ", " additionally "]
        sub_messages = [message]

        for sep in separators:
            new_parts = []
            for part in sub_messages:
                new_parts.extend(part.split(sep))
            sub_messages = new_parts

        # If no split happened, return single intent
        if len(sub_messages) <= 1:
            intent = await self.classifier.classify(message)
            return [intent.to_dict()]

        # Classify each sub-message
        intents = []
        for sub_msg in sub_messages:
            sub_msg = sub_msg.strip()
            if len(sub_msg) > 5:  # Skip very short fragments
                intent = await self.classifier.classify(sub_msg)
                intents.append(intent.to_dict())

        return intents

    def _generate_clarification(
        self,
        message: str,
        intent: Intent,
        context: Optional[Dict[str, Any]],
    ) -> List[str]:
        """Generate clarification questions based on ambiguous intent."""
        questions = []

        if intent.category == IntentCategory.UNKNOWN:
            questions.append(
                "Could you clarify what you'd like me to help with? "
                "I can analyze trends, detect anomalies, explain metrics, "
                "or generate DAX measures."
            )
        elif intent.category == IntentCategory.ANALYSIS:
            questions.append(
                "What type of analysis would you like? "
                "Options include: trend analysis, anomaly detection, "
                "root cause analysis, or correlation analysis."
            )
        elif intent.category == IntentCategory.QUESTION:
            questions.append(
                "Could you provide more detail about what you'd like to know? "
                "Are you asking about a specific metric, visual, or concept?"
            )
        else:
            questions.append(
                f"I think you're asking about {intent.category.value}, "
                "but I'm not fully confident. Could you rephrase or provide more detail?"
            )

        return questions

    def _apply_context_boost(
        self,
        intent: Intent,
        context: Optional[Dict[str, Any]],
    ) -> Optional[Intent]:
        """
        Boost confidence using conversation context.

        If the previous turn was about analysis and the current message
        looks like a follow-up, we can boost the analysis intent confidence.
        """
        if not context:
            return None

        previous_intent = context.get("last_intent_category")
        if not previous_intent:
            return None

        # If user seems to be continuing the same topic, boost confidence
        if intent.category.value == previous_intent:
            boosted = Intent(
                category=intent.category,
                confidence=min(intent.confidence + 0.2, 1.0),
                entities=intent.entities,
                metadata={**intent.metadata, "context_boosted": True},
            )
            logger.debug(
                f"Boosted intent confidence from {intent.confidence:.2f} "
                f"to {boosted.confidence:.2f} based on conversation context"
            )
            return boosted

        return None
