"""
Main orchestrator for coordinating agent workflows.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid

from intent_engine.classifier import IntentClassifier
from intent_engine.routing_rules import RoutingRuleSet
from memory.session_manager import SessionManager, Session
from memory.conversation_memory import MemoryStore, ConversationMemory
from config import get_logger

logger = get_logger(__name__)


class Orchestrator:
    """Orchestrate agent workflows."""

    def __init__(self):
        self.intent_classifier = IntentClassifier()
        self.routing_rules = RoutingRuleSet()
        self.session_manager = SessionManager()
        self.memory_store = MemoryStore()
        self.agents: Dict[str, Any] = {}  # Agent instances

    async def handle_user_message(
        self,
        message: str,
        session_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Handle a user message end-to-end."""
        try:
            # Get or create session
            session = self.session_manager.get_session(session_id)
            if not session:
                logger.error(f"Session {session_id} not found or expired")
                return {
                    "status": "error",
                    "message": "Session expired. Please start a new conversation.",
                }

            # Get or create conversation memory
            conversation = self.memory_store.get_or_create_conversation(
                session_id
            )

            # Add user message to memory
            conversation.add_turn("user", message, metadata=context)

            # Classify intent
            intent = await self.intent_classifier.classify(message)
            logger.info(f"Classified intent: {intent.category} ({intent.confidence})")

            # Route to appropriate agent
            agent_name = self.routing_rules.get_agent_for_intent(intent)
            logger.info(f"Routing to agent: {agent_name}")

            # Get agent and execute
            agent = self.agents.get(agent_name)
            if not agent:
                return {
                    "status": "error",
                    "message": f"Agent {agent_name} not available",
                }

            response = await agent.execute(
                message=message,
                session=session,
                conversation=conversation,
                context=context,
                intent=intent,
            )

            # Add assistant response to memory
            conversation.add_turn(
                "assistant",
                response.get("message", ""),
                metadata={"agent": agent_name, "intent": intent.to_dict()},
            )

            return {
                "status": "success",
                "message": response.get("message", ""),
                "agent": agent_name,
                "intent": intent.to_dict(),
                "metadata": response.get("metadata"),
            }

        except Exception as e:
            logger.error(f"Error handling user message: {e}")
            return {
                "status": "error",
                "message": f"Error processing message: {str(e)}",
            }

    def create_session(
        self, user_id: str, report_id: Optional[str] = None
    ) -> Session:
        """Create a new session."""
        return self.session_manager.create_session(user_id, report_id)

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session."""
        return self.session_manager.get_session(session_id)

    def register_agent(self, name: str, agent: Any):
        """Register an agent."""
        self.agents[name] = agent
        logger.info(f"Registered agent: {name}")

    def get_conversation_history(
        self, session_id: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get conversation history."""
        conversation = self.memory_store.get_conversation(session_id)
        if not conversation:
            return []

        history = conversation.get_history(limit)
        return [turn.to_dict() for turn in history]
