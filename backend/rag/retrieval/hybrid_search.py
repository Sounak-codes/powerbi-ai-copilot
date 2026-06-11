"""
Hybrid search combining vector (semantic) and BM25 (keyword) retrieval.

Uses Reciprocal Rank Fusion (RRF) to merge results from both methods,
providing the best of semantic understanding and keyword precision.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from rag.retrieval.vector_search import VectorSearch, SearchResult
from rag.retrieval.bm25_search import BM25Search, BM25Result
from rag.retrieval.metadata_filter import MetadataFilter
from config import get_logger

logger = get_logger(__name__)


@dataclass
class HybridResult:
    """A result from hybrid search."""
    document_id: str
    text: str
    score: float  # Combined RRF score
    vector_score: Optional[float] = None
    bm25_score: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: str = "hybrid"  # "vector", "bm25", "hybrid"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "text": self.text,
            "score": round(self.score, 4),
            "vector_score": round(self.vector_score, 4) if self.vector_score else None,
            "bm25_score": round(self.bm25_score, 4) if self.bm25_score else None,
            "metadata": self.metadata,
            "source": self.source,
        }


class HybridSearch:
    """
    Hybrid search engine combining semantic and keyword search.

    Uses Reciprocal Rank Fusion (RRF) to combine rankings from
    both methods, with configurable weighting.
    """

    def __init__(
        self,
        vector_weight: float = 0.6,
        bm25_weight: float = 0.4,
        rrf_k: int = 60,
    ):
        """
        Args:
            vector_weight: Weight for vector search results (0-1).
            bm25_weight: Weight for BM25 results (0-1).
            rrf_k: RRF constant (higher = more uniform ranking).
        """
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight
        self.rrf_k = rrf_k
        self.vector_search = VectorSearch()
        self.bm25_search = BM25Search()
        self.metadata_filter = MetadataFilter()

    async def search(
        self,
        query: str,
        top_k: int = 5,
        metadata_filters: Optional[Dict[str, Any]] = None,
        vector_top_k: int = 20,
        bm25_top_k: int = 20,
    ) -> List[HybridResult]:
        """
        Perform hybrid search combining vector and BM25.

        Args:
            query: Search query.
            top_k: Final number of results to return.
            metadata_filters: Optional metadata filters to apply.
            vector_top_k: Number of vector results to retrieve before fusion.
            bm25_top_k: Number of BM25 results to retrieve before fusion.

        Returns:
            List of HybridResults ranked by combined score.
        """
        logger.debug(f"Hybrid search: '{query[:50]}...' (top_k={top_k})")

        # Run both searches
        vector_results = await self.vector_search.search(query, top_k=vector_top_k)
        bm25_results = self.bm25_search.search(query, top_k=bm25_top_k)

        # Apply metadata filters if provided
        if metadata_filters:
            vector_results = [
                r for r in vector_results
                if self.metadata_filter.matches(r.metadata, metadata_filters)
            ]
            bm25_results = [
                r for r in bm25_results
                if self.metadata_filter.matches(r.metadata, metadata_filters)
            ]

        # Fuse results using RRF
        fused = self._reciprocal_rank_fusion(vector_results, bm25_results)

        logger.debug(f"Hybrid search returned {len(fused[:top_k])} results")
        return fused[:top_k]

    async def index_documents(self, documents: List[Dict[str, Any]]):
        """Index documents for both vector and BM25 search."""
        await self.vector_search.index_documents(documents)
        self.bm25_search.index_documents(documents)
        logger.info(f"Hybrid search: indexed {len(documents)} documents")

    def _reciprocal_rank_fusion(
        self,
        vector_results: List[SearchResult],
        bm25_results: List[BM25Result],
    ) -> List[HybridResult]:
        """
        Combine rankings using Reciprocal Rank Fusion.

        RRF score = sum(1 / (k + rank_i)) across all ranking lists.
        """
        scores: Dict[str, Dict[str, Any]] = {}

        # Process vector results
        for rank, result in enumerate(vector_results):
            doc_id = result.document_id
            rrf_score = self.vector_weight * (1.0 / (self.rrf_k + rank + 1))

            if doc_id not in scores:
                scores[doc_id] = {
                    "text": result.text,
                    "metadata": result.metadata,
                    "rrf_score": 0.0,
                    "vector_score": result.score,
                    "bm25_score": None,
                }
            scores[doc_id]["rrf_score"] += rrf_score
            scores[doc_id]["vector_score"] = result.score

        # Process BM25 results
        for rank, result in enumerate(bm25_results):
            doc_id = result.document_id
            rrf_score = self.bm25_weight * (1.0 / (self.rrf_k + rank + 1))

            if doc_id not in scores:
                scores[doc_id] = {
                    "text": result.text,
                    "metadata": result.metadata,
                    "rrf_score": 0.0,
                    "vector_score": None,
                    "bm25_score": result.score,
                }
            scores[doc_id]["rrf_score"] += rrf_score
            scores[doc_id]["bm25_score"] = result.score

        # Build results
        results = []
        for doc_id, data in scores.items():
            # Determine source
            has_vector = data["vector_score"] is not None
            has_bm25 = data["bm25_score"] is not None
            source = "hybrid" if has_vector and has_bm25 else "vector" if has_vector else "bm25"

            results.append(HybridResult(
                document_id=doc_id,
                text=data["text"],
                score=data["rrf_score"],
                vector_score=data["vector_score"],
                bm25_score=data["bm25_score"],
                metadata=data["metadata"],
                source=source,
            ))

        # Sort by combined score
        results.sort(key=lambda r: r.score, reverse=True)
        return results

    @property
    def document_count(self) -> int:
        return self.vector_search.document_count
