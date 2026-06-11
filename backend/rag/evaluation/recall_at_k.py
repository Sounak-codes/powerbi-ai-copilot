"""Recall@K evaluation metric for RAG retrieval."""
from typing import List, Set


def recall_at_k(
    retrieved_ids: List[str],
    relevant_ids: Set[str],
    k: int = 5,
) -> float:
    """
    Calculate Recall@K: what fraction of relevant documents were retrieved.

    Args:
        retrieved_ids: Ordered list of retrieved document IDs.
        relevant_ids: Set of truly relevant document IDs.
        k: Number of top results to consider.

    Returns:
        Recall score (0.0 to 1.0).
    """
    if not relevant_ids:
        return 0.0

    top_k = set(retrieved_ids[:k])
    hits = top_k & relevant_ids
    return len(hits) / len(relevant_ids)
