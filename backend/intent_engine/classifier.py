"""
Intent classifier for routing user messages.
"""
from typing import Dict, List, Optional
from llm.providers.provider_factory import ProviderFactory
from intent_engine.intent_schema import Intent, IntentCategory
from config import get_logger

logger = get_logger(__name__)


class IntentClassifier:
    """Classify user intents using LLM."""

    SYSTEM_PROMPT = """You are an intent classifier for a Power BI AI Copilot assistant.
Classify user messages into one of these categories:
- question: User is asking a question
- analysis: User wants data analysis
- insight: User wants insights or recommendations
- explanation: User wants explanation of metrics/data
- recommendation: User wants recommendations
- dax: User wants DAX code or measures
- report: User wants to work with reports
- unknown: Unable to classify

Respond with JSON: {"category": "...", "confidence": 0.0-1.0, "entities": [...]}
"""

    def __init__(self):
        self.llm_provider = ProviderFactory.get_default_provider()

    async def classify(self, text: str) -> Intent:
        """Classify user intent."""
        try:
            response = await self.llm_provider.generate_with_structured_output(
                prompt=text,
                system=self.SYSTEM_PROMPT,
                temperature=0.3,
                max_tokens=200,
            )

            category = IntentCategory(response.get("category", "unknown"))
            confidence = response.get("confidence", 0.5)
            entities = response.get("entities", [])

            intent = Intent(
                category=category,
                confidence=confidence,
                entities=entities,
                metadata={"raw_response": response},
            )

            logger.debug(f"Classified intent: {intent.to_dict()}")
            return intent

        except Exception as e:
            logger.error(f"Intent classification failed: {e}")
            return Intent(IntentCategory.UNKNOWN, 0.0)

    async def classify_batch(self, texts: List[str]) -> List[Intent]:
        """Classify multiple intents."""
        return [await self.classify(text) for text in texts]
