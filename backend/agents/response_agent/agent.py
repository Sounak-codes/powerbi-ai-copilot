"""
Response Agent — formats and polishes final responses for the user.

Takes raw outputs from other agents and produces well-structured,
user-friendly responses with follow-up suggestions.
"""
from typing import Any, Dict, Optional, List
from llm.providers.provider_factory import ProviderFactory
from agents.base_agent import BaseAgent
from agents.response_agent.prompts import (
    RESPONSE_SYSTEM_PROMPT,
    FORMAT_RESPONSE_PROMPT,
)
from memory.session_manager import Session
from memory.conversation_memory import ConversationMemory
from intent_engine.intent_schema import Intent
from config import get_logger

logger = get_logger(__name__)


class ResponseAgent(BaseAgent):
    """
    Formats raw agent outputs into polished user-facing responses.

    Handles formatting, follow-up generation, tone adjustment,
    and response structure.
    """

    def __init__(self):
        super().__init__("ResponseAgent")
        self.llm_provider = ProviderFactory.get_default_provider()

    async def execute(
        self,
        message: str,
        session: Session,
        conversation: ConversationMemory,
        context: Optional[Dict[str, Any]] = None,
        intent: Optional[Intent] = None,
    ) -> Dict[str, Any]:
        """Format and deliver the final response."""
        try:
            self._log_execution("START", "Formatting response")

            raw_output = context.get("raw_output", "") if context else ""
            source_agent = context.get("source_agent", "unknown") if context else "unknown"
            intent_category = intent.category.value if intent else "question"

            # If raw_output is already well-formatted, use it directly
            if not raw_output:
                raw_output = message

            # Format the response
            formatted = await self._format_response(
                raw_output=raw_output,
                user_question=message,
                agent_name=source_agent,
                intent=intent_category,
            )

            # Generate follow-ups
            follow_ups = self._generate_follow_ups(intent_category, context)

            self._log_execution("COMPLETE", "Response formatted")

            return await self._get_response_message(
                formatted,
                metadata={
                    "agent": "response",
                    "source_agent": source_agent,
                    "follow_up_questions": follow_ups,
                },
            )

        except Exception as e:
            logger.error(f"ResponseAgent error: {e}")
            # Graceful fallback — return raw content
            raw = context.get("raw_output", message) if context else message
            return await self._get_response_message(raw)

    async def _format_response(
        self,
        raw_output: str,
        user_question: str,
        agent_name: str,
        intent: str,
    ) -> str:
        """Format raw output into a polished response."""
        # For short/clean responses, don't over-process
        if len(raw_output) < 200 and "\n" not in raw_output:
            return raw_output

        prompt = FORMAT_RESPONSE_PROMPT.format(
            agent_name=agent_name,
            raw_output=raw_output[:2000],
            user_question=user_question,
            intent=intent,
        )

        try:
            response = await self.llm_provider.generate(
                prompt=prompt,
                system=RESPONSE_SYSTEM_PROMPT,
                temperature=0.4,
                max_tokens=1000,
            )
            return response
        except Exception as e:
            logger.warning(f"Response formatting failed, using raw: {e}")
            return raw_output

    def _generate_follow_ups(
        self,
        intent_category: str,
        context: Optional[Dict[str, Any]],
    ) -> List[str]:
        """Generate contextual follow-up suggestions."""
        follow_up_map = {
            "analysis": [
                "What's driving this trend?",
                "How does this compare to last period?",
                "Can you break this down by segment?",
            ],
            "insight": [
                "What actions should I take?",
                "Which metrics are most at risk?",
                "Show me the root cause analysis.",
            ],
            "question": [
                "Can you explain in more detail?",
                "How does this relate to other metrics?",
                "What should I look at next?",
            ],
            "dax": [
                "Can you optimize this measure?",
                "Add a year-over-year comparison.",
                "How would I handle blank values?",
            ],
            "explanation": [
                "Why is this important?",
                "What factors influence this metric?",
                "Can you give me an example?",
            ],
        }
        return follow_up_map.get(intent_category, follow_up_map["question"])
