"""
FAISS vector store for efficient similarity search.

Provides a persistent vector store backed by FAISS with
support for add, search, and serialization.
"""
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import json
import numpy as np
from config import get_settings, get_logger

settings = get_settings()
logger = get_logger(__name__)


class FAISSStore:
    """
    FAISS-backed vector store for document embeddings.

    Supports:
    - Adding vectors with metadata
    - Similarity search (cosine, L2)
    - Persistence to disk
    - Incremental updates
    """

    def __init__(self, dimension: Optional[int] = None, index_path: Optional[str] = None):
        self.dimension = dimension or settings.embedding_dimension
        self.index_path = index_path or settings.redis_url  # Reuse path config
        self._index = None
        self._metadata: List[Dict[str, Any]] = []
        self._documents: List[str] = []
        self._faiss = None

    def _get_faiss(self):
        """Lazy-load FAISS."""
        if self._faiss is None:
            try:
                import faiss
                self._faiss = faiss
            except ImportError:
                raise ImportError("faiss-cpu required: pip install faiss-cpu")
        return self._faiss

    def _ensure_index(self):
        """Initialize FAISS index if not already done."""
        if self._index is None:
            faiss = self._get_faiss()
            # Use inner product (equivalent to cosine on normalized vectors)
            self._index = faiss.IndexFlatIP(self.dimension)
            logger.debug(f"Created FAISS index (dim={self.dimension})")

    def add(
        self,
        embeddings: List[List[float]],
        documents: List[str],
        metadata: Optional[List[Dict[str, Any]]] = None,
    ) -> int:
        """
        Add vectors to the store.

        Args:
            embeddings: List of embedding vectors.
            documents: List of document texts.
            metadata: Optional metadata for each document.

        Returns:
            Number of vectors added.
        """
        self._ensure_index()

        # Normalize vectors for cosine similarity
        vectors = np.array(embeddings, dtype=np.float32)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1  # Avoid division by zero
        vectors = vectors / norms

        self._index.add(vectors)
        self._documents.extend(documents)
        self._metadata.extend(metadata or [{} for _ in documents])

        logger.debug(f"Added {len(embeddings)} vectors (total: {self._index.ntotal})")
        return len(embeddings)

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors.

        Args:
            query_embedding: Query vector.
            top_k: Number of results.
            min_score: Minimum similarity threshold.

        Returns:
            List of results with document, score, and metadata.
        """
        if self._index is None or self._index.ntotal == 0:
            return []

        # Normalize query
        query = np.array([query_embedding], dtype=np.float32)
        norm = np.linalg.norm(query)
        if norm > 0:
            query = query / norm

        # Search
        k = min(top_k, self._index.ntotal)
        scores, indices = self._index.search(query, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or float(score) < min_score:
                continue

            results.append({
                "document_id": str(idx),
                "text": self._documents[idx] if idx < len(self._documents) else "",
                "score": float(score),
                "metadata": self._metadata[idx] if idx < len(self._metadata) else {},
            })

        return results

    def save(self, path: Optional[str] = None):
        """Save index and metadata to disk."""
        save_path = Path(path or self.index_path or "vectorstore")
        save_path.mkdir(parents=True, exist_ok=True)

        if self._index is not None:
            faiss = self._get_faiss()
            faiss.write_index(self._index, str(save_path / "index.faiss"))

        # Save metadata
        with open(save_path / "metadata.json", "w") as f:
            json.dump({
                "documents": self._documents,
                "metadata": self._metadata,
                "dimension": self.dimension,
            }, f)

        logger.info(f"Saved FAISS store to {save_path} ({self.total_vectors} vectors)")

    def load(self, path: Optional[str] = None) -> bool:
        """Load index and metadata from disk."""
        load_path = Path(path or self.index_path or "vectorstore")

        index_file = load_path / "index.faiss"
        meta_file = load_path / "metadata.json"

        if not index_file.exists():
            logger.warning(f"No FAISS index found at {index_file}")
            return False

        try:
            faiss = self._get_faiss()
            self._index = faiss.read_index(str(index_file))

            if meta_file.exists():
                with open(meta_file) as f:
                    data = json.load(f)
                    self._documents = data.get("documents", [])
                    self._metadata = data.get("metadata", [])
                    self.dimension = data.get("dimension", self.dimension)

            logger.info(f"Loaded FAISS store from {load_path} ({self.total_vectors} vectors)")
            return True

        except Exception as e:
            logger.error(f"Failed to load FAISS store: {e}")
            return False

    def clear(self):
        """Clear the index."""
        self._index = None
        self._documents.clear()
        self._metadata.clear()

    @property
    def total_vectors(self) -> int:
        return self._index.ntotal if self._index else 0
