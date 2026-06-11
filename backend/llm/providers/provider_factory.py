"""
LLM provider factory.
"""
from typing import Optional
from config import get_settings
from llm.providers.openai_provider import OpenAIProvider
from llm.providers.groq_provider import GroqProvider

settings = get_settings()


class ProviderFactory:
    """Factory for creating LLM providers."""

    _providers = {
        "openai": OpenAIProvider,
        "groq": GroqProvider,
    }

    @staticmethod
    def create_provider(provider_name: Optional[str] = None):
        """Create an LLM provider instance."""
        provider = provider_name or settings.llm_provider

        if provider not in ProviderFactory._providers:
            raise ValueError(f"Unknown provider: {provider}")

        provider_class = ProviderFactory._providers[provider]

        if provider == "openai":
            return provider_class(
                api_key=settings.openai_api_key, model=settings.openai_model
            )
        elif provider == "groq":
            return provider_class(
                api_key=settings.groq_api_key, model=settings.groq_model
            )

    @staticmethod
    def get_default_provider():
        """Get the default LLM provider based on settings."""
        return ProviderFactory.create_provider()
