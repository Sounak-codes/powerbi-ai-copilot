"""
Embedding model configurations.
"""
from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class EmbeddingModelConfig:
    """Configuration for an embedding model."""
    name: str
    dimension: int
    max_tokens: int
    provider: str  # "openai", "local"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "dimension": self.dimension,
            "max_tokens": self.max_tokens,
            "provider": self.provider,
        }


# Available embedding models
EMBEDDING_MODELS = {
    "text-embedding-3-small": EmbeddingModelConfig(
        name="text-embedding-3-small",
        dimension=1536,
        max_tokens=8191,
        provider="openai",
    ),
    "text-embedding-3-large": EmbeddingModelConfig(
        name="text-embedding-3-large",
        dimension=3072,
        max_tokens=8191,
        provider="openai",
    ),
    "text-embedding-ada-002": EmbeddingModelConfig(
        name="text-embedding-ada-002",
        dimension=1536,
        max_tokens=8191,
        provider="openai",
    ),
}


def get_model_config(model_name: str) -> EmbeddingModelConfig:
    """Get configuration for an embedding model."""
    if model_name in EMBEDDING_MODELS:
        return EMBEDDING_MODELS[model_name]
    # Default
    return EMBEDDING_MODELS["text-embedding-3-small"]
