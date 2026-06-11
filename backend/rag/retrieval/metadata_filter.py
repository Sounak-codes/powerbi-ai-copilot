"""
Metadata filtering for RAG retrieval.

Allows filtering search results by metadata attributes (source type,
date range, report name, etc.) before or after retrieval.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from config import get_logger

logger = get_logger(__name__)


class MetadataFilter:
    """
    Filter documents based on metadata attributes.

    Supports various filter operators: equals, in, range, contains,
    exists, and combinations via AND logic.
    """

    def matches(
        self, metadata: Dict[str, Any], filters: Dict[str, Any]
    ) -> bool:
        """
        Check if a document's metadata matches all filter criteria.

        Args:
            metadata: Document metadata to check.
            filters: Filter criteria as key-value pairs or operator dicts.

        Filter formats:
            Simple equality: {"source": "documentation"}
            Operator: {"score": {"$gte": 0.5}}
            In list: {"type": {"$in": ["report", "measure"]}}
            Contains: {"text": {"$contains": "revenue"}}
            Exists: {"author": {"$exists": True}}

        Returns:
            True if document matches all filters.
        """
        if not filters:
            return True

        for key, condition in filters.items():
            value = metadata.get(key)

            if isinstance(condition, dict):
                # Operator-based filter
                if not self._evaluate_operator(value, condition):
                    return False
            else:
                # Simple equality
                if value != condition:
                    return False

        return True

    def filter_results(
        self,
        results: List[Dict[str, Any]],
        filters: Dict[str, Any],
        metadata_key: str = "metadata",
    ) -> List[Dict[str, Any]]:
        """
        Filter a list of search results by metadata.

        Args:
            results: List of result dicts.
            filters: Filter criteria.
            metadata_key: Key in each result dict containing metadata.

        Returns:
            Filtered list of results.
        """
        if not filters:
            return results

        filtered = [
            r for r in results
            if self.matches(r.get(metadata_key, {}), filters)
        ]

        logger.debug(f"Metadata filter: {len(results)} -> {len(filtered)} results")
        return filtered

    def build_filter(
        self,
        source_type: Optional[str] = None,
        report_id: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        tags: Optional[List[str]] = None,
        min_score: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Build a filter dict from common parameters.

        Convenience method for constructing metadata filters.
        """
        filters = {}

        if source_type:
            filters["source_type"] = source_type

        if report_id:
            filters["report_id"] = report_id

        if date_from and date_to:
            filters["created_at"] = {"$gte": date_from, "$lte": date_to}
        elif date_from:
            filters["created_at"] = {"$gte": date_from}
        elif date_to:
            filters["created_at"] = {"$lte": date_to}

        if tags:
            filters["tags"] = {"$in": tags}

        if min_score is not None:
            filters["relevance_score"] = {"$gte": min_score}

        return filters

    def _evaluate_operator(
        self, value: Any, condition: Dict[str, Any]
    ) -> bool:
        """Evaluate an operator-based condition."""
        for op, target in condition.items():
            if op == "$eq":
                if value != target:
                    return False
            elif op == "$ne":
                if value == target:
                    return False
            elif op == "$gt":
                if value is None or value <= target:
                    return False
            elif op == "$gte":
                if value is None or value < target:
                    return False
            elif op == "$lt":
                if value is None or value >= target:
                    return False
            elif op == "$lte":
                if value is None or value > target:
                    return False
            elif op == "$in":
                if isinstance(value, list):
                    if not any(v in target for v in value):
                        return False
                elif value not in target:
                    return False
            elif op == "$nin":
                if isinstance(value, list):
                    if any(v in target for v in value):
                        return False
                elif value in target:
                    return False
            elif op == "$contains":
                if value is None or target.lower() not in str(value).lower():
                    return False
            elif op == "$exists":
                if target and value is None:
                    return False
                if not target and value is not None:
                    return False
            elif op == "$regex":
                import re
                if value is None or not re.search(target, str(value)):
                    return False

        return True
