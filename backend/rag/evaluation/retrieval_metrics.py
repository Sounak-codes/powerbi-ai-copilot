"""Comprehensive retrieval evaluation metrics."""
from typing import Dict, Any, List, Set
from rag.evaluation.recall_at_k import recall_at_k
from rag.evaluation.mrr import mean_reciprocal_rank


def precision_at_k(
    retrieved_ids: List[str], relevant_ids: Set[str], k: int = 5
) -> float:
    """Precision@K: fraction of retrieved docs that are relevant."""
    top_k = retrieved_ids[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for doc_id in top_k if doc_id in relevant_ids)
    return hits / len(top_k)


def f1_at_k(
    retrieved_ids: List[str], relevant_ids: Set[str], k: int = 5
) -> float:
    """F1@K: harmonic mean of Precision@K and Recall@K."""
    p = precision_at_k(retrieved_ids, relevant_ids, k)
    r = recall_at_k(retrieved_ids, relevant_ids, k)
    if p + r == 0:
        return 0.0
    return 2 * (p * r) / (p + r)


def evaluate_retrieval(
    retrieved_ids: List[str],
    relevant_ids: Set[str],
    k_values: List[int] = None,
) -> Dict[str, Any]:
    """
    Run all retrieval metrics.

    Args:
        retrieved_ids: Ordered retrieved document IDs.
        relevant_ids: Set of relevant document IDs.
        k_values: List of K values to evaluate at.

    Returns:
        Dictionary with all metrics.
    """
    if k_values is None:
        k_values = [1, 3, 5, 10]

    results = {"mrr": mean_reciprocal_rank(retrieved_ids, relevant_ids)}

    for k in k_values:
        results[f"recall@{k}"] = recall_at_k(retrieved_ids, relevant_ids, k)
        results[f"precision@{k}"] = precision_at_k(retrieved_ids, relevant_ids, k)
        results[f"f1@{k}"] = f1_at_k(retrieved_ids, relevant_ids, k)

    return results
