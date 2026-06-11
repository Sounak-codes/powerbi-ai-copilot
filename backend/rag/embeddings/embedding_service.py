"""
Embedding service for generating text embeddings.

Supports OpenAI embeddings with a local cache to avoid
redundant API calls for previously embedded content.
"""
from typing import Dict, Any, List, Optional
import hashlib
import numpy as np
from config import get_settings, get_logger

settings = get_settings()
logger = get_logger(__name__)


class EmbeddingService:
    """
    Generate embeddings for text content.

    Supports OpenAI text-embedding models with a local LRU cache
    to minimize API costs for repeated embeddings.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        dimension: Optional[int] = None,
    ):
        self.model = model or settings.embedding_model
        self.dimension = dimension or settings.embedding_dimension
        self._client = None
        self._cache: Dict[str, List[float]] = {}
        self._max_cache_size = 10000

    def _get_client(self):
        """Lazy-initialize the OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=settings.openai_api_key)
            except ImportError:
                raise ImportError("openai package required for embeddings: pip install openai")
        return self._client

    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text content to embed.

        Returns:
            Embedding vector as list of floats.
        """
        # Check cache
        cache_key = self._cache_key(text)
        if cache_key in self._cache:
            return self._cache[cache_key]

        embedding = await self._call_api([text])
        vector = embedding[0]

        # Update cache
        self._cache_put(cache_key, vector)
        return vector

    async def embed_batch(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts.

        Handles batching to stay within API limits and uses cache
        for previously embedded texts.

        Args:
            texts: List of texts to embed.
            batch_size: Maximum texts per API call.

        Returns:
            List of embedding vectors.
        """
        results = [None] * len(texts)
        uncached_indices = []
        uncached_texts = []

        # Check cache first
        for i, text in enumerate(texts):
            cache_key = self._cache_key(text)
            if cache_key in self._cache:
                results[i] = self._cache[cache_key]
            else:
                uncached_indices.append(i)
                uncached_texts.append(text)

        # Embed uncached texts in batches
        if uncached_texts:
            logger.debug(f"Embedding {len(uncached_texts)} texts ({len(texts) - len(uncached_texts)} cached)")

            for start in range(0, len(uncached_texts), batch_size):
                batch = uncached_texts[start : start + batch_size]
                embeddings = await self._call_api(batch)

                for j, embedding in enumerate(embeddings):
                    idx = uncached_indices[start + j]
                    results[idx] = embedding
                    self._cache_put(self._cache_key(batch[j]), embedding)

        return results

    async def _call_api(self, texts: List[str]) -> List[List[float]]:
        """Call the embedding API."""
        try:
            client = self._get_client()
            response = client.embeddings.create(
                model=self.model,
                input=texts,
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"Embedding API call failed: {e}")
            # Return zero vectors as fallback
            return [[0.0] * self.dimension for _ in texts]

    def cosine_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        a = np.array(vec_a)
        b = np.array(vec_b)

        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))

    def _cache_key(self, text: str) -> str:
        """Generate cache key from text."""
        return hashlib.md5(text.encode()).hexdigest()

    def _cache_put(self, key: str, value: List[float]):
        """Add to cache, evicting old entries if full."""
        if len(self._cache) >= self._max_cache_size:
            # Evict oldest 10%
            keys_to_remove = list(self._cache.keys())[: self._max_cache_size // 10]
            for k in keys_to_remove:
                del self._cache[k]
        self._cache[key] = value

    def clear_cache(self):
        """Clear the embedding cache."""
        self._cache.clear()
        logger.debug("Embedding cache cleared")
