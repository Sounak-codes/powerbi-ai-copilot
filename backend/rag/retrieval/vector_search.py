"""
Vector similarity search for RAG retrieval.

Performs semantic search against the vector store using
embedding similarity to find relevant documents.
"""
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from config import get_settings, get_logger

settings = get_settings()
logger = get_logger(__name__)


@dataclass
class SearchResult:
    """A single search result."""
    document_id: str
    text: str
    score: float  # Similarity score 0-1
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "text": self.text,
            "score": round(self.score, 4),
            "metadata": self.metadata,
        }


class VectorSearch:
    """
    Perform vector similarity search against embedded documents.

    Uses FAISS for efficient approximate nearest neighbor search.
    """

    def __init__(self, embedding_service=None):
        self._index = None
        self._documents: List[Dict[str, Any]] = []
        self._embedding_service = embedding_service

    def _get_embedding_service(self):
        """Lazy-load embedding service."""
        if self._embedding_service is None:
            from rag.embeddings.embedding_service import EmbeddingService
            self._embedding_service = EmbeddingService()
        return self._embedding_service

    async def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> List[SearchResult]:
        """
        Search for documents similar to the query.

        Args:
            query: Search query text.
            top_k: Number of results to return.
            min_score: Minimum similarity threshold.

        Returns:
            List of SearchResults ranked by similarity.
        """
        if not self._documents:
            logger.warning("No documents indexed for vector search")
            return []

        try:
            import numpy as np
        except ImportError:
            logger.error("numpy required for vector search")
            return []

        embedding_service = self._get_embedding_service()
        query_embedding = await embedding_service.embed_text(query)

        # Calculate similarities
        results = []
        for i, doc in enumerate(self._documents):
            doc_embedding = doc.get("embedding")
            if doc_embedding is None:
                continue

            score = embedding_service.cosine_similarity(query_embedding, doc_embedding)

            if score >= min_score:
                results.append(SearchResult(
                    document_id=doc.get("id", str(i)),
                    text=doc.get("text", ""),
                    score=score,
                    metadata=doc.get("metadata", {}),
                ))

        # Sort by score descending
        results.sort(key=lambda r: r.score, reverse=True)

        return results[:top_k]

    async def index_documents(self, documents: List[Dict[str, Any]]):
        """
        Index documents for search.

        Args:
            documents: List of dicts with "id", "text", and optional "metadata".
        """
        embedding_service = self._get_embedding_service()
        texts = [doc.get("text", "") for doc in documents]

        logger.info(f"Indexing {len(documents)} documents for vector search")
        embeddings = await embedding_service.embed_batch(texts)

        for doc, embedding in zip(documents, embeddings):
            doc["embedding"] = embedding

        self._documents = documents
        logger.info(f"Indexed {len(documents)} documents")

    def add_document(self, document: Dict[str, Any], embedding: List[float]):
        """Add a single pre-embedded document."""
        document["embedding"] = embedding
        self._documents.append(document)

    def clear(self):
        """Clear the index."""
        self._documents.clear()

    @property
    def document_count(self) -> int:
        return len(self._documents)
