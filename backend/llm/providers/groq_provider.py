"""
Groq LLM provider.
"""
from typing import Optional
import os
import json

try:
    from groq import Groq, AsyncGroq
except ImportError:
    Groq = None
    AsyncGroq = None

from config import get_logger
from llm.providers.openai_provider import LLMProvider

logger = get_logger(__name__)


class GroqProvider(LLMProvider):
    """Groq LLM provider."""

    def __init__(self, api_key: Optional[str] = None, model: str = "mixtral-8x7b-32768"):
        """Initialize Groq provider."""
        if Groq is None:
            raise ImportError("groq package is required. Install with: pip install groq")

        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.model = model
        self.client = Groq(api_key=self.api_key)

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate text using Groq."""
        messages = []

        if system:
            messages.append({"role": "system", "content": system})

        messages.append({"role": "user", "content": prompt})

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens or 1024,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Groq generation failed: {e}")
            raise

    async def generate_with_structured_output(
        self,
        prompt: str,
        system: Optional[str] = None,
        response_format: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> dict:
        """Generate structured output from Groq."""
        messages = []

        if system:
            messages.append({"role": "system", "content": system})

        messages.append({"role": "user", "content": prompt})

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens or 1024,
            )

            result = response.choices[0].message.content
            return json.loads(result) if isinstance(result, str) else result
        except Exception as e:
            logger.error(f"Groq structured generation failed: {e}")
            raise
