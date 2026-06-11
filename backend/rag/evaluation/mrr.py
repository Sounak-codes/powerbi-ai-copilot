"""Mean Reciprocal Rank (MRR) evaluation metric for RAG retrieval."""
from typing import List, Set


def mean_reciprocal_rank(
    retrieved_ids: List[str],
    relevant_ids: Set[str],
) -> float:
    """
    Calculate Mean Reciprocal Rank.

    The reciprocal rank is 1/position of the first relevant result.

    Args:
        retrieved_ids: Ordered list of retrieved document IDs.
        relevant_ids: Set of truly relevant document IDs.

    Returns:
        Reciprocal rank (0.0 to 1.0). 0 if no relevant doc found.
    """
    for rank, doc_id in enumerate(retrieved_ids, 1):
        if doc_id in relevant_ids:
            return 1.0 / rank
    return 0.0


def mrr_batch(
    queries: List[List[str]],
    relevants: List[Set[str]],
) -> float:
    """
    Calculate MRR across multiple queries.

    Args:
        queries: List of retrieved ID lists (one per query).
        relevants: List of relevant ID sets (one per query).

    Returns:
        Average MRR across all queries.
    """
    if not queries:
        return 0.0

    total = sum(
        mean_reciprocal_rank(retrieved, relevant)
        for retrieved, relevant in zip(queries, relevants)
    )
    return total / len(queries)
