"""
Filter context extraction for Power BI reports.

Extracts active filters, slicers, and cross-filter state
to provide the LLM with awareness of the current data scope.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from config import get_logger

logger = get_logger(__name__)


@dataclass
class FilterState:
    """Represents an active filter on the report."""

    target_table: str
    target_column: str
    operator: str  # "In", "NotIn", "GreaterThan", "LessThan", "Between", "Contains"
    values: List[Any] = field(default_factory=list)
    filter_type: str = "basic"  # "basic", "advanced", "relative_date", "top_n"
    is_slicer: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_table": self.target_table,
            "target_column": self.target_column,
            "operator": self.operator,
            "values": self.values,
            "filter_type": self.filter_type,
            "is_slicer": self.is_slicer,
        }

    def to_natural_language(self) -> str:
        """Convert filter to a human-readable description."""
        col = f"{self.target_table}.{self.target_column}"
        if self.operator == "In":
            values_str = ", ".join(str(v) for v in self.values[:5])
            suffix = f" and {len(self.values) - 5} more" if len(self.values) > 5 else ""
            return f"{col} is one of [{values_str}{suffix}]"
        if self.operator == "NotIn":
            return f"{col} is not in [{', '.join(str(v) for v in self.values[:3])}]"
        if self.operator == "Between":
            return f"{col} is between {self.values[0]} and {self.values[1]}"
        if self.operator in ("GreaterThan", "LessThan"):
            op_word = "greater than" if self.operator == "GreaterThan" else "less than"
            return f"{col} is {op_word} {self.values[0]}"
        if self.operator == "Contains":
            return f"{col} contains '{self.values[0]}'"
        return f"{col} {self.operator} {self.values}"


class FilterContextExtractor:
    """Extract and manage filter context from Power BI reports."""

    def extract(self, filters_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Extract filter context from raw filter data.

        Args:
            filters_data: List of filter objects from Power BI JS API.

        Returns:
            Structured filter context with natural language summary.
        """
        if not filters_data:
            return {
                "active_filters": [],
                "filter_summary": "No filters are currently applied.",
                "data_scope": "full",
                "filtered_tables": [],
            }

        filters = self._parse_filters(filters_data)

        logger.debug(f"Extracted {len(filters)} active filters")

        return {
            "active_filters": [f.to_dict() for f in filters],
            "filter_summary": self._build_summary(filters),
            "data_scope": "filtered" if filters else "full",
            "filtered_tables": list(set(f.target_table for f in filters)),
            "filter_count": len(filters),
        }

    def _parse_filters(self, filters_data: List[Dict[str, Any]]) -> List[FilterState]:
        """Parse raw Power BI filter data into FilterState objects."""
        filters = []

        for raw in filters_data:
            try:
                target = raw.get("target", {})
                table = target.get("table", "")
                column = target.get("column", "")
                operator = raw.get("operator", "In")
                values = raw.get("values", [])
                filter_type = raw.get("filterType", "basic")

                if not table or not column:
                    continue

                filter_state = FilterState(
                    target_table=table,
                    target_column=column,
                    operator=operator,
                    values=values,
                    filter_type=filter_type,
                    is_slicer=raw.get("isSlicer", False),
                )
                filters.append(filter_state)

            except Exception as e:
                logger.warning(f"Failed to parse filter: {e}")
                continue

        return filters

    def _build_summary(self, filters: List[FilterState]) -> str:
        """Build a natural language summary of all active filters."""
        if not filters:
            return "No filters are currently applied."

        descriptions = [f.to_natural_language() for f in filters]

        if len(descriptions) == 1:
            return f"Data is filtered where {descriptions[0]}."

        return "Data is filtered where: " + "; ".join(descriptions) + "."

    def get_effective_scope(
        self, filters: List[FilterState], available_tables: List[str]
    ) -> Dict[str, Any]:
        """
        Determine what data is in scope given the active filters.

        Returns information about which tables/columns are filtered
        and which are unfiltered.
        """
        filtered_tables = set(f.target_table for f in filters)
        unfiltered_tables = set(available_tables) - filtered_tables

        return {
            "filtered_tables": list(filtered_tables),
            "unfiltered_tables": list(unfiltered_tables),
            "total_filter_count": len(filters),
            "has_date_filter": any(
                "date" in f.target_column.lower() for f in filters
            ),
            "has_category_filter": any(
                f.filter_type == "basic" and f.operator == "In" for f in filters
            ),
        }
