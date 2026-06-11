"""
Planner Agent — decomposes complex requests into agent execution plans.

Acts as the orchestration brain: determines whether a request is simple
(route directly) or complex (build a multi-step plan), and coordinates
execution across specialized agents.
"""
from typing import Any, Dict, Optional, List
from llm.providers.provider_factory import ProviderFactory
from agents.base_agent import BaseAgent
from agents.planner_agent.prompts import (
    PLANNER_SYSTEM_PROMPT,
    PLAN_REFINEMENT_PROMPT,
    COMPLEXITY_ASSESSMENT_PROMPT,
)
from memory.session_manager import Session
from memory.conversation_memory import ConversationMemory
from intent_engine.intent_schema import Intent
from config import get_logger

logger = get_logger(__name__)


class PlannerAgent(BaseAgent):
    """
    Plans and coordinates multi-step agent workflows.

    For simple requests, routes directly to the appropriate agent.
    For complex requests, builds a step-by-step execution plan.
    """

    def __init__(self):
        super().__init__("PlannerAgent")
        self.llm_provider = ProviderFactory.get_default_provider()

    async def execute(
        self,
        message: str,
        session: Session,
        conversation: ConversationMemory,
        context: Optional[Dict[str, Any]] = None,
        intent: Optional[Intent] = None,
    ) -> Dict[str, Any]:
        """Execute the planner agent."""
        try:
            self._log_execution("START", f"Planning for: {message[:50]}...")

            # Assess complexity
            complexity = await self._assess_complexity(message, context)
            self._log_execution("ASSESSMENT", f"Complexity: {complexity.get('complexity')}")

            if not complexity.get("needs_planning", False):
                # Simple — produce a helpful response directly
                return await self._handle_simple(message, context, intent)

            # Complex — build a plan
            plan = await self._build_plan(message, context, conversation)
            self._log_execution("PLAN", f"Created {len(plan.get('plan', []))} step plan")

            return await self._get_response_message(
                self._format_plan_response(plan, message),
                metadata={
                    "agent": "planner",
                    "plan": plan,
                    "complexity": complexity.get("complexity"),
                },
            )

        except Exception as e:
            logger.error(f"PlannerAgent error: {e}")
            return await self._get_response_message(
                "I'll help you with that. Let me analyze your request and provide a response.",
                metadata={"agent": "planner", "fallback": True},
            )

    async def _assess_complexity(
        self, message: str, context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Assess whether the request needs multi-step planning."""
        prompt = COMPLEXITY_ASSESSMENT_PROMPT.format(
            message=message,
            context=str(context)[:500] if context else "None",
        )

        try:
            result = await self.llm_provider.generate_with_structured_output(
                prompt=prompt,
                system="You assess request complexity. Respond in JSON only.",
                temperature=0.2,
                max_tokens=200,
            )
            return result
        except Exception:
            # Default to simple
            return {"complexity": "simple", "needs_planning": False}

    async def _build_plan(
        self,
        message: str,
        context: Optional[Dict[str, Any]],
        conversation: ConversationMemory,
    ) -> Dict[str, Any]:
        """Build a multi-step execution plan."""
        history = conversation.get_recent_context(num_turns=3)

        prompt = f"""User request: {message}

Conversation history:
{history}

Report context: {str(context)[:1000] if context else 'None'}

Create an execution plan to fulfill this request."""

        try:
            result = await self.llm_provider.generate_with_structured_output(
                prompt=prompt,
                system=PLANNER_SYSTEM_PROMPT,
                temperature=0.4,
                max_tokens=800,
            )
            return result if isinstance(result, dict) else {"plan": [], "reasoning": str(result)}
        except Exception as e:
            logger.error(f"Plan generation failed: {e}")
            return {
                "plan": [{"step": 1, "agent": "rag_agent", "action": "Answer directly"}],
                "reasoning": "Fallback plan due to generation error.",
            }

    async def _handle_simple(
        self,
        message: str,
        context: Optional[Dict[str, Any]],
        intent: Optional[Intent],
    ) -> Dict[str, Any]:
        """Handle a simple request with a direct response."""
        prompt = f"User question: {message}"
        if context:
            prompt += f"\n\nContext: {str(context)[:500]}"

        response = await self.llm_provider.generate(
            prompt=prompt,
            system=(
                "You are a helpful Power BI analytics assistant. "
                "Provide a clear, concise answer."
            ),
            temperature=0.5,
            max_tokens=600,
        )

        return await self._get_response_message(
            response,
            metadata={"agent": "planner", "mode": "direct"},
        )

    def _format_plan_response(self, plan: Dict[str, Any], message: str) -> str:
        """Format the plan into a user-friendly response."""
        steps = plan.get("plan", [])
        reasoning = plan.get("reasoning", "")

        if not steps:
            return f"I'll help you with: {message}"

        response = f"To answer your request, I'll:\n\n"
        for step in steps:
            action = step.get("action", step.get("description", "Process"))
            response += f"  {step.get('step', '•')}. {action}\n"

        if reasoning:
            response += f"\n{reasoning}"

        return response
