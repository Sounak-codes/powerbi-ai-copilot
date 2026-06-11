"""
DAX Agent — generates, explains, optimizes, and debugs DAX measures.

Handles all DAX-related requests including measure creation,
code explanation, performance optimization, and error debugging.
"""
from typing import Any, Dict, Optional, List
from llm.providers.provider_factory import ProviderFactory
from agents.base_agent import BaseAgent
from agents.dax_agent.prompts import (
    DAX_SYSTEM_PROMPT,
    DAX_GENERATION_PROMPT,
    DAX_EXPLANATION_PROMPT,
    DAX_OPTIMIZATION_PROMPT,
    DAX_DEBUG_PROMPT,
)
from memory.session_manager import Session
from memory.conversation_memory import ConversationMemory
from intent_engine.intent_schema import Intent
from config import get_logger

logger = get_logger(__name__)


class DAXAgent(BaseAgent):
    """
    Generates, explains, optimizes, and debugs DAX measures.
    """

    def __init__(self):
        super().__init__("DAXAgent")
        self.llm_provider = ProviderFactory.get_default_provider()

    async def execute(
        self,
        message: str,
        session: Session,
        conversation: ConversationMemory,
        context: Optional[Dict[str, Any]] = None,
        intent: Optional[Intent] = None,
    ) -> Dict[str, Any]:
        """Execute DAX agent logic."""
        try:
            self._log_execution("START", f"DAX request: {message[:50]}...")

            # Determine sub-action
            action = self._determine_action(message)
            data_model = context.get("data_model", {}) if context else {}

            if action == "generate":
                result = await self._generate_dax(message, data_model, context)
            elif action == "explain":
                result = await self._explain_dax(message, context)
            elif action == "optimize":
                result = await self._optimize_dax(message, context)
            elif action == "debug":
                result = await self._debug_dax(message, context)
            else:
                result = await self._generate_dax(message, data_model, context)

            self._log_execution("COMPLETE", f"Action: {action}")
            return result

        except Exception as e:
            logger.error(f"DAXAgent error: {e}")
            return await self._get_response_message(
                "I encountered an error while working on your DAX request. "
                "Could you provide more details about what you need?"
            )

    def _determine_action(self, message: str) -> str:
        """Determine the DAX action from the message."""
        msg_lower = message.lower()

        if any(w in msg_lower for w in ("explain", "what does", "how does", "understand")):
            return "explain"
        if any(w in msg_lower for w in ("optimize", "improve", "faster", "performance", "slow")):
            return "optimize"
        if any(w in msg_lower for w in ("debug", "error", "wrong", "fix", "not working", "incorrect")):
            return "debug"
        return "generate"

    async def _generate_dax(
        self,
        message: str,
        data_model: Dict[str, Any],
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate a new DAX measure."""
        tables = data_model.get("tables", [])
        relationships = data_model.get("relationships", [])
        existing_measures = data_model.get("measures", [])

        prompt = DAX_GENERATION_PROMPT.format(
            request=message,
            tables=str(tables)[:500],
            relationships=str(relationships)[:300],
            existing_measures=str(existing_measures)[:300],
            context=str(context)[:300] if context else "None",
        )

        try:
            result = await self.llm_provider.generate_with_structured_output(
                prompt=prompt,
                system=DAX_SYSTEM_PROMPT,
                temperature=0.3,
                max_tokens=1000,
            )

            measure_name = result.get("measure_name", "NewMeasure")
            dax_code = result.get("dax_code", "")
            explanation = result.get("explanation", "")

            response_text = f"**{measure_name}**\n\n```dax\n{dax_code}\n```\n\n"
            response_text += f"**Explanation:** {explanation}\n"

            deps = result.get("dependencies", [])
            if deps:
                response_text += f"\n**Dependencies:** {', '.join(deps)}\n"

            perf = result.get("performance_notes", "")
            if perf:
                response_text += f"\n**Performance:** {perf}\n"

            return await self._get_response_message(
                response_text,
                metadata={
                    "agent": "dax",
                    "action": "generate",
                    "measure_name": measure_name,
                    "dax_code": dax_code,
                },
            )

        except Exception as e:
            logger.error(f"DAX generation failed: {e}")
            # Fallback to plain generation
            response = await self.llm_provider.generate(
                prompt=f"Generate a DAX measure for: {message}",
                system=DAX_SYSTEM_PROMPT,
                temperature=0.3,
                max_tokens=800,
            )
            return await self._get_response_message(response, metadata={"agent": "dax"})

    async def _explain_dax(
        self, message: str, context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Explain existing DAX code."""
        dax_code = ""
        if context:
            dax_code = context.get("dax_code", "")

        # Try extracting code from message
        if not dax_code and "```" in message:
            parts = message.split("```")
            if len(parts) >= 2:
                dax_code = parts[1].strip()

        prompt = DAX_EXPLANATION_PROMPT.format(
            measure_name=context.get("measure_name", "Measure") if context else "Measure",
            dax_code=dax_code or message,
        )

        response = await self.llm_provider.generate(
            prompt=prompt,
            system="You are a DAX expert. Explain code clearly for business users.",
            temperature=0.4,
            max_tokens=800,
        )

        return await self._get_response_message(
            response, metadata={"agent": "dax", "action": "explain"}
        )

    async def _optimize_dax(
        self, message: str, context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Optimize DAX code for performance."""
        dax_code = context.get("dax_code", message) if context else message

        prompt = DAX_OPTIMIZATION_PROMPT.format(
            dax_code=dax_code,
            context=str(context)[:300] if context else "None",
            issues=context.get("issues", "Performance is slow") if context else "General optimization",
        )

        response = await self.llm_provider.generate(
            prompt=prompt,
            system=DAX_SYSTEM_PROMPT,
            temperature=0.3,
            max_tokens=1000,
        )

        return await self._get_response_message(
            response, metadata={"agent": "dax", "action": "optimize"}
        )

    async def _debug_dax(
        self, message: str, context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Debug DAX code."""
        dax_code = context.get("dax_code", "") if context else ""
        error = context.get("error", message) if context else message

        prompt = DAX_DEBUG_PROMPT.format(
            measure_name=context.get("measure_name", "Measure") if context else "Measure",
            dax_code=dax_code or "Not provided",
            error=error,
            expected=context.get("expected", "Not specified") if context else "Not specified",
            actual=context.get("actual", "Not specified") if context else "Not specified",
        )

        response = await self.llm_provider.generate(
            prompt=prompt,
            system=DAX_SYSTEM_PROMPT,
            temperature=0.3,
            max_tokens=1000,
        )

        return await self._get_response_message(
            response, metadata={"agent": "dax", "action": "debug"}
        )
