"""
State manager for tracking conversation and workflow state.

Maintains a state machine per conversation that tracks the current
phase, accumulated context, and pending actions.
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from config import get_logger

logger = get_logger(__name__)


class ConversationPhase(str, Enum):
    """Phases of a conversation turn."""

    IDLE = "idle"
    INTENT_CLASSIFICATION = "intent_classification"
    CONTEXT_GATHERING = "context_gathering"
    AGENT_EXECUTION = "agent_execution"
    RESPONSE_BUILDING = "response_building"
    AWAITING_CLARIFICATION = "awaiting_clarification"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class ConversationState:
    """State of a conversation at any point in time."""

    session_id: str
    phase: ConversationPhase = ConversationPhase.IDLE
    current_intent: Optional[Dict[str, Any]] = None
    current_context: Dict[str, Any] = field(default_factory=dict)
    pending_agent: Optional[str] = None
    accumulated_results: Dict[str, Any] = field(default_factory=dict)
    turn_count: int = 0
    last_updated: datetime = field(default_factory=datetime.utcnow)
    # Track what the user is focused on across turns
    topic_stack: List[str] = field(default_factory=list)
    # Clarification questions waiting for answers
    pending_clarifications: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "phase": self.phase.value,
            "current_intent": self.current_intent,
            "pending_agent": self.pending_agent,
            "turn_count": self.turn_count,
            "last_updated": self.last_updated.isoformat(),
            "topic_stack": self.topic_stack,
            "pending_clarifications": self.pending_clarifications,
        }


class StateManager:
    """
    Manage conversation state across turns.

    Tracks what phase each conversation is in, what agents are
    working on, and what accumulated context exists.
    """

    def __init__(self):
        self.states: Dict[str, ConversationState] = {}

    def get_or_create_state(self, session_id: str) -> ConversationState:
        """Get or create a conversation state."""
        if session_id not in self.states:
            self.states[session_id] = ConversationState(session_id=session_id)
            logger.debug(f"Created state for session {session_id}")
        return self.states[session_id]

    def get_state(self, session_id: str) -> Optional[ConversationState]:
        """Get state for a session, or None if not found."""
        return self.states.get(session_id)

    def transition(
        self,
        session_id: str,
        new_phase: ConversationPhase,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConversationState:
        """
        Transition conversation to a new phase.

        Args:
            session_id: The session to transition.
            new_phase: Target phase.
            metadata: Additional data to store with the transition.

        Returns:
            Updated ConversationState.
        """
        state = self.get_or_create_state(session_id)
        old_phase = state.phase

        state.phase = new_phase
        state.last_updated = datetime.utcnow()

        if metadata:
            state.accumulated_results.update(metadata)

        logger.debug(
            f"Session {session_id}: {old_phase.value} -> {new_phase.value}"
        )

        return state

    def set_intent(
        self, session_id: str, intent: Dict[str, Any]
    ) -> ConversationState:
        """Set the current intent for a session."""
        state = self.get_or_create_state(session_id)
        state.current_intent = intent
        state.last_updated = datetime.utcnow()

        # Track topic
        category = intent.get("category", "unknown")
        if not state.topic_stack or state.topic_stack[-1] != category:
            state.topic_stack.append(category)
            # Keep topic stack manageable
            if len(state.topic_stack) > 10:
                state.topic_stack = state.topic_stack[-10:]

        return state

    def set_pending_agent(
        self, session_id: str, agent_name: str
    ) -> ConversationState:
        """Set the agent currently working on this conversation."""
        state = self.get_or_create_state(session_id)
        state.pending_agent = agent_name
        state.last_updated = datetime.utcnow()
        return state

    def add_result(
        self, session_id: str, key: str, value: Any
    ) -> ConversationState:
        """Add a result to the accumulated results."""
        state = self.get_or_create_state(session_id)
        state.accumulated_results[key] = value
        state.last_updated = datetime.utcnow()
        return state

    def increment_turn(self, session_id: str) -> ConversationState:
        """Increment the turn counter for a session."""
        state = self.get_or_create_state(session_id)
        state.turn_count += 1
        state.last_updated = datetime.utcnow()
        return state

    def request_clarification(
        self, session_id: str, questions: List[str]
    ) -> ConversationState:
        """Set clarification questions and transition to awaiting state."""
        state = self.get_or_create_state(session_id)
        state.pending_clarifications = questions
        state.phase = ConversationPhase.AWAITING_CLARIFICATION
        state.last_updated = datetime.utcnow()
        return state

    def resolve_clarification(self, session_id: str) -> ConversationState:
        """Clear pending clarifications and resume."""
        state = self.get_or_create_state(session_id)
        state.pending_clarifications.clear()
        state.phase = ConversationPhase.INTENT_CLASSIFICATION
        state.last_updated = datetime.utcnow()
        return state

    def reset_state(self, session_id: str) -> ConversationState:
        """Reset state to idle (after a turn completes)."""
        state = self.get_or_create_state(session_id)
        state.phase = ConversationPhase.IDLE
        state.pending_agent = None
        state.current_intent = None
        state.accumulated_results.clear()
        state.last_updated = datetime.utcnow()
        return state

    def delete_state(self, session_id: str) -> bool:
        """Delete state for a session."""
        if session_id in self.states:
            del self.states[session_id]
            return True
        return False

    def get_active_sessions(self) -> List[str]:
        """Get IDs of sessions that are not idle."""
        return [
            sid
            for sid, state in self.states.items()
            if state.phase != ConversationPhase.IDLE
        ]
