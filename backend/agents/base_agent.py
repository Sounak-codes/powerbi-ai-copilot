"""
Base agent class for all agents.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from memory.session_manager import Session
from memory.conversation_memory import ConversationMemory
from intent_engine.intent_schema import Intent
from config import get_logger

logger = get_logger(__name__)


class BaseAgent(ABC):
    """Base class for all agents."""

    def __init__(self, name: str):
        self.name = name
        self.llm_provider = None  # To be set by subclasses

    @abstractmethod
    async def execute(
        self,
        message: str,
        session: Session,
        conversation: ConversationMemory,
        context: Optional[Dict[str, Any]] = None,
        intent: Optional[Intent] = None,
    ) -> Dict[str, Any]:
        """Execute the agent's logic.
        
        Returns:
            Dictionary with 'message' and optional 'metadata' keys
        """
        pass

    async def _get_response_message(
        self, content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Build a response message."""
        return {
            "message": content,
            "metadata": metadata or {},
        }

    def _log_execution(self, step: str, details: str = ""):
        """Log agent execution steps."""
        logger.info(f"[{self.name}] {step}: {details}")
