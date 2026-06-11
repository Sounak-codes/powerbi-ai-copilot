"""
RAG (Retrieval-Augmented Generation) Agent.
"""
from typing import Any, Dict, Optional
from llm.providers.provider_factory import ProviderFactory
from agents.base_agent import BaseAgent
from memory.session_manager import Session
from memory.conversation_memory import ConversationMemory
from intent_engine.intent_schema import Intent
from config import get_logger

logger = get_logger(__name__)


class RAGAgent(BaseAgent):
    """Agent that uses RAG for question answering and retrieval."""

    SYSTEM_PROMPT = """You are a helpful assistant for Power BI analytics.
Answer questions based on the provided context and your knowledge.
Always be accurate and cite sources when relevant.
If you don't know something, say so clearly."""

    def __init__(self):
        super().__init__("RAGAgent")
        self.llm_provider = ProviderFactory.get_default_provider()
        self.knowledge_base = {}  # Would be loaded from vectorstore

    async def execute(
        self,
        message: str,
        session: Session,
        conversation: ConversationMemory,
        context: Optional[Dict[str, Any]] = None,
        intent: Optional[Intent] = None,
    ) -> Dict[str, Any]:
        """Execute RAG agent logic."""
        try:
            self._log_execution("START", "Processing user query with RAG")

            # Step 1: Retrieve relevant context
            retrieved_context = await self._retrieve_context(message)
            self._log_execution("RETRIEVAL", f"Retrieved {len(retrieved_context)} documents")

            # Step 2: Build prompt with context
            prompt = self._build_prompt(message, retrieved_context)

            # Step 3: Generate response using LLM
            response = await self.llm_provider.generate(
                prompt=prompt,
                system=self.SYSTEM_PROMPT,
                temperature=0.3,
                max_tokens=1000,
            )

            self._log_execution("GENERATION", "Generated response successfully")

            return await self._get_response_message(
                response,
                metadata={
                    "agent": "rag",
                    "context_count": len(retrieved_context),
                    "confidence": 0.8,
                },
            )

        except Exception as e:
            logger.error(f"RAGAgent error: {e}")
            return await self._get_response_message(
                "Sorry, I encountered an error while processing your question."
            )

    async def _retrieve_context(self, query: str) -> list:
        """Retrieve relevant context from knowledge base."""
        # Mock implementation - would use actual vector store
        return [
            {
                "text": "Power BI is a business analytics tool by Microsoft.",
                "source": "documentation",
            },
            {
                "text": "DAX is the formula language used in Power BI.",
                "source": "documentation",
            },
        ]

    def _build_prompt(self, query: str, context: list) -> str:
        """Build prompt with retrieved context."""
        prompt = f"Question: {query}\n\n"
        prompt += "Context:\n"
        for i, doc in enumerate(context, 1):
            prompt += f"{i}. {doc['text']}\n"
        prompt += "\nPlease answer the question based on the provided context."
        return prompt
