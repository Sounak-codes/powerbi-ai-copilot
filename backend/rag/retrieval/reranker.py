"""
Reranker for improving retrieval quality.

Takes initial retrieval results and reranks them using a more
expensive but accurate scoring method (cross-encoder style).
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from config import get_settings, get_logger

settings = get_settings()
logger = get_logger(__name__)


@dataclass
class RerankedResult:
    """A reranked search result."""
    document_id: str
    text: str
    original_score: float
    reranked_score: float
    rank_change: int  # Positive = moved up, negative = moved down
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "text": self.text,
            "original_score": round(self.original_score, 4),
            "reranked_score": round(self.reranked_score, 4),
            "rank_change": self.rank_change,
            "metadata": self.metadata,
        }


class Reranker:
    """
    Reranks search results using LLM-based relevance scoring.

    Uses the LLM to score query-document relevance more accurately
    than embedding similarity alone. More expensive but improves
    precision for the final top-k results.
    """

    def __init__(self, use_llm: bool = True):
        """
        Args:
            use_llm: If True, uses LLM for reranking; otherwise uses heuristic.
        """
        self.use_llm = use_llm
        self._llm_provider = None

    def _get_llm(self):
        """Lazy-load LLM provider."""
        if self._llm_provider is None:
            from llm.providers.provider_factory import ProviderFactory
            self._llm_provider = ProviderFactory.get_default_provider()
        return self._llm_provider

    async def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int = 5,
    ) -> List[RerankedResult]:
        """
        Rerank search results for a query.

        Args:
            query: The original search query.
            results: List of initial results (with "document_id", "text", "score", "metadata").
            top_k: Number of results to return after reranking.

        Returns:
            List of RerankedResults sorted by new relevance score.
        """
        if not results:
            return []

        if len(results) <= top_k and not self.use_llm:
            # No need to rerank if we're keeping all results
            return [
                RerankedResult(
                    document_id=r.get("document_id", str(i)),
                    text=r.get("text", ""),
                    original_score=r.get("score", 0),
                    reranked_score=r.get("score", 0),
                    rank_change=0,
                    metadata=r.get("metadata", {}),
                )
                for i, r in enumerate(results)
            ]

        # Score each result
        if self.use_llm:
            scored = await self._llm_rerank(query, results)
        else:
            scored = self._heuristic_rerank(query, results)

        # Sort by new score
        scored.sort(key=lambda r: r.reranked_score, reverse=True)

        # Calculate rank changes
        original_order = {r.get("document_id", str(i)): i for i, r in enumerate(results)}
        for new_rank, result in enumerate(scored):
            old_rank = original_order.get(result.document_id, new_rank)
            result.rank_change = old_rank - new_rank

        return scored[:top_k]

    async def _llm_rerank(
        self, query: str, results: List[Dict[str, Any]]
    ) -> List[RerankedResult]:
        """Rerank using LLM relevance scoring."""
        llm = self._get_llm()
        scored_results = []

        for i, result in enumerate(results):
            text = result.get("text", "")[:500]

            prompt = (
                f"Rate the relevance of this document to the query on a scale of 0.0 to 1.0.\n\n"
                f"Query: {query}\n\n"
                f"Document: {text}\n\n"
                f"Respond with ONLY a number between 0.0 and 1.0."
            )

            try:
                response = await llm.generate(
                    prompt=prompt,
                    system="You are a relevance judge. Respond with only a decimal number.",
                    temperature=0.0,
                    max_tokens=10,
                )

                # Parse score
                score = float(response.strip())
                score = max(0.0, min(1.0, score))
            except (ValueError, Exception):
                score = result.get("score", 0.5)

            scored_results.append(RerankedResult(
                document_id=result.get("document_id", str(i)),
                text=result.get("text", ""),
                original_score=result.get("score", 0),
                reranked_score=score,
                rank_change=0,
                metadata=result.get("metadata", {}),
            ))

        return scored_results

    def _heuristic_rerank(
        self, query: str, results: List[Dict[str, Any]]
    ) -> List[RerankedResult]:
        """
        Heuristic reranking based on keyword overlap and freshness.

        Cheaper than LLM reranking — useful for high-volume scenarios.
        """
        query_terms = set(query.lower().split())
        scored_results = []

        for i, result in enumerate(results):
            text = result.get("text", "").lower()
            original_score = result.get("score", 0)

            # Keyword overlap bonus
            doc_terms = set(text.split())
            overlap = len(query_terms & doc_terms) / max(len(query_terms), 1)

            # Title match bonus
            title = result.get("metadata", {}).get("title", "").lower()
            title_match = 0.1 if any(t in title for t in query_terms) else 0

            # Combine: 60% original, 30% keyword overlap, 10% title
            reranked_score = 0.6 * original_score + 0.3 * overlap + title_match

            scored_results.append(RerankedResult(
                document_id=result.get("document_id", str(i)),
                text=result.get("text", ""),
                original_score=original_score,
                reranked_score=reranked_score,
                rank_change=0,
                metadata=result.get("metadata", {}),
            ))

        return scored_results
