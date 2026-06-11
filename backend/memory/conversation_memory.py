"""
Conversation memory management.
"""
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict
from config import get_settings, get_logger

settings = get_settings()
logger = get_logger(__name__)


@dataclass
class ConversationTurn:
    """A single turn in a conversation."""

    turn_id: str
    role: str  # "user", "assistant"
    content: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["timestamp"] = data["timestamp"].isoformat()
        return data


class ConversationMemory:
    """Store and manage conversation history."""

    def __init__(self, conversation_id: str, max_turns: int = None):
        self.conversation_id = conversation_id
        self.max_turns = max_turns or settings.memory_max_turns
        self.turns: List[ConversationTurn] = []
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def add_turn(
        self,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConversationTurn:
        """Add a turn to the conversation."""
        turn = ConversationTurn(
            turn_id=str(uuid.uuid4()),
            role=role,
            content=content,
            timestamp=datetime.utcnow(),
            metadata=metadata,
        )

        self.turns.append(turn)
        self.updated_at = datetime.utcnow()

        # Keep only the most recent turns
        if len(self.turns) > self.max_turns * 2:  # Buffer before trimming
            self.turns = self.turns[-self.max_turns :]
            logger.debug(
                f"Trimmed conversation {self.conversation_id} to {self.max_turns} turns"
            )

        return turn

    def get_history(self, limit: Optional[int] = None) -> List[ConversationTurn]:
        """Get conversation history."""
        if limit:
            return self.turns[-limit:]
        return self.turns

    def get_recent_context(self, num_turns: int = 3) -> str:
        """Get recent context as formatted string."""
        recent = self.turns[-num_turns:]
        context = []

        for turn in recent:
            context.append(f"{turn.role.upper()}: {turn.content}")

        return "\n".join(context)

    def clear(self):
        """Clear conversation history."""
        self.turns.clear()
        self.updated_at = datetime.utcnow()
        logger.debug(f"Cleared conversation {self.conversation_id}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "conversation_id": self.conversation_id,
            "turns": [turn.to_dict() for turn in self.turns],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "turn_count": len(self.turns),
        }


class MemoryStore:
    """Store multiple conversations."""

    def __init__(self):
        self.conversations: Dict[str, ConversationMemory] = {}

    def get_or_create_conversation(self, conversation_id: str) -> ConversationMemory:
        """Get or create a conversation."""
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = ConversationMemory(
                conversation_id
            )
            logger.debug(f"Created conversation {conversation_id}")

        return self.conversations[conversation_id]

    def get_conversation(self, conversation_id: str) -> Optional[ConversationMemory]:
        """Get a conversation."""
        return self.conversations.get(conversation_id)

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation."""
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]
            logger.debug(f"Deleted conversation {conversation_id}")
            return True
        return False

    def get_all_conversations(self) -> Dict[str, ConversationMemory]:
        """Get all conversations."""
        return self.conversations.copy()
