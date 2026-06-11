"""
Context window manager for LLM prompt construction.

Manages the token budget for context passed to LLMs, ensuring
we include the most relevant conversation history, report context,
and retrieved information without exceeding model limits.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from config import get_settings, get_logger

settings = get_settings()
logger = get_logger(__name__)


@dataclass
class ContextBlock:
    """A block of context with priority and estimated token count."""

    name: str
    content: str
    priority: int  # Higher = more important, included first
    token_estimate: int = 0
    category: str = "general"  # "system", "conversation", "report", "retrieved", "user"

    def __post_init__(self):
        if not self.token_estimate:
            # Rough estimate: ~4 chars per token for English text
            self.token_estimate = len(self.content) // 4


@dataclass
class ContextWindow:
    """
    Manages context within a token budget.

    Prioritizes blocks by importance and trims or drops lower-priority
    content to stay within the model's context window.
    """

    max_tokens: int = 8000  # Reserve budget for system prompt + response
    blocks: List[ContextBlock] = field(default_factory=list)
    reserved_for_response: int = 1500

    @property
    def available_tokens(self) -> int:
        """Tokens available for context (excluding response reservation)."""
        return self.max_tokens - self.reserved_for_response

    @property
    def used_tokens(self) -> int:
        """Estimated tokens currently used by included blocks."""
        return sum(b.token_estimate for b in self.blocks)

    @property
    def remaining_tokens(self) -> int:
        """Tokens remaining for additional content."""
        return max(0, self.available_tokens - self.used_tokens)

    def add_block(self, block: ContextBlock) -> bool:
        """
        Add a context block if it fits within the token budget.

        Returns True if added, False if it would exceed the budget.
        """
        if block.token_estimate <= self.remaining_tokens:
            self.blocks.append(block)
            return True

        logger.debug(
            f"Context block '{block.name}' ({block.token_estimate} tokens) "
            f"exceeds remaining budget ({self.remaining_tokens} tokens)"
        )
        return False

    def build(self) -> str:
        """
        Build the final context string from all included blocks.

        Sorts blocks by priority (highest first) and concatenates.
        """
        # Sort by priority descending
        sorted_blocks = sorted(self.blocks, key=lambda b: b.priority, reverse=True)
        parts = [b.content for b in sorted_blocks if b.content.strip()]
        return "\n\n".join(parts)

    def clear(self):
        """Clear all context blocks."""
        self.blocks.clear()


class ContextWindowManager:
    """
    High-level manager for building context windows for LLM prompts.

    Takes raw inputs (conversation history, report context, retrieved docs)
    and packs them into an optimized context window.
    """

    # Token budgets for different categories (as fraction of available)
    BUDGET_ALLOCATION = {
        "system": 0.10,
        "report": 0.25,
        "conversation": 0.30,
        "retrieved": 0.25,
        "user": 0.10,
    }

    def __init__(self, max_tokens: int = 8000):
        self.max_tokens = max_tokens

    def build_context_window(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        report_context: Optional[str] = None,
        retrieved_documents: Optional[List[str]] = None,
        system_instructions: Optional[str] = None,
    ) -> ContextWindow:
        """
        Build an optimized context window.

        Args:
            user_message: The current user message.
            conversation_history: Previous turns as dicts with role/content.
            report_context: Current report context string.
            retrieved_documents: RAG-retrieved document chunks.
            system_instructions: System-level instructions.

        Returns:
            A ContextWindow ready to be rendered into a prompt.
        """
        window = ContextWindow(max_tokens=self.max_tokens)

        # System instructions (highest priority)
        if system_instructions:
            window.add_block(ContextBlock(
                name="system_instructions",
                content=system_instructions,
                priority=100,
                category="system",
            ))

        # User message (high priority — always included)
        window.add_block(ContextBlock(
            name="user_message",
            content=f"User: {user_message}",
            priority=95,
            category="user",
        ))

        # Report context (important for relevance)
        if report_context:
            window.add_block(ContextBlock(
                name="report_context",
                content=f"[Report Context]\n{report_context}",
                priority=80,
                category="report",
            ))

        # Conversation history (most recent first, higher priority)
        if conversation_history:
            history_str = self._format_conversation_history(
                conversation_history, window.remaining_tokens // 3
            )
            if history_str:
                window.add_block(ContextBlock(
                    name="conversation_history",
                    content=f"[Conversation History]\n{history_str}",
                    priority=70,
                    category="conversation",
                ))

        # Retrieved documents (for RAG)
        if retrieved_documents:
            docs_str = self._format_retrieved_docs(
                retrieved_documents, window.remaining_tokens
            )
            if docs_str:
                window.add_block(ContextBlock(
                    name="retrieved_documents",
                    content=f"[Retrieved Information]\n{docs_str}",
                    priority=60,
                    category="retrieved",
                ))

        logger.debug(
            f"Context window: {window.used_tokens}/{window.available_tokens} tokens, "
            f"{len(window.blocks)} blocks"
        )

        return window

    def _format_conversation_history(
        self, history: List[Dict[str, Any]], max_tokens: int
    ) -> str:
        """Format conversation history, most recent first, within budget."""
        if not history:
            return ""

        # Start from most recent and work backwards
        formatted_turns = []
        estimated_tokens = 0

        for turn in reversed(history):
            role = turn.get("role", "unknown").capitalize()
            content = turn.get("content", "")
            line = f"{role}: {content}"
            line_tokens = len(line) // 4

            if estimated_tokens + line_tokens > max_tokens:
                break

            formatted_turns.insert(0, line)
            estimated_tokens += line_tokens

        return "\n".join(formatted_turns)

    def _format_retrieved_docs(
        self, documents: List[str], max_tokens: int
    ) -> str:
        """Format retrieved documents within budget."""
        if not documents:
            return ""

        formatted = []
        estimated_tokens = 0

        for i, doc in enumerate(documents, 1):
            doc_tokens = len(doc) // 4
            if estimated_tokens + doc_tokens > max_tokens:
                break
            formatted.append(f"[Source {i}]\n{doc}")
            estimated_tokens += doc_tokens

        return "\n\n".join(formatted)
