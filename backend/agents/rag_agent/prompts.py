"""
Prompt templates for the RAG Agent.
"""

RAG_SYSTEM_PROMPT = """You are a knowledgeable Power BI assistant.
Answer questions using ONLY the provided context/documents.
If the context doesn't contain enough information, clearly state what you know
and what you're uncertain about.

Rules:
- Be accurate and concise
- Cite source documents when relevant
- Distinguish between facts from context and your own reasoning
- If context is insufficient, say "Based on available information..." 
  and note what additional context would help
"""

RAG_QA_PROMPT = """Answer the user's question based on the retrieved context.

User Question: {question}

Retrieved Context:
{context_documents}

Conversation History:
{conversation_history}

Report Context:
{report_context}

Provide a clear, accurate answer. If the context is insufficient, indicate
what information would help you provide a better answer.
"""

RAG_FOLLOW_UP_PROMPT = """The user is asking a follow-up question.
Use both the previous context and any new retrieved information.

Previous exchange:
{previous_exchange}

Follow-up question: {question}

New context (if any):
{new_context}

Answer the follow-up question, referencing the previous discussion as needed.
"""

RAG_SYNTHESIS_PROMPT = """Synthesize information from multiple sources to answer:

Question: {question}

Sources:
{sources}

Create a comprehensive answer that:
1. Combines relevant information from all sources
2. Notes any contradictions between sources
3. Provides the most accurate and complete answer possible
"""
