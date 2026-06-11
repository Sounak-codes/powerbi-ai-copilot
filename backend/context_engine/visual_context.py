"""
Visual context extraction for Power BI visuals.

Extracts and enriches context from individual visuals including
data summaries, field metadata, and visual type information.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from config import get_logger

logger = get_logger(__name__)


@dataclass
class VisualMetadata:
    """Metadata about a Power BI visual."""

    visual_id: str
    visual_type: str
    title: Optional[str] = None
    fields: List[str] = field(default_factory=list)
    measures: List[str] = field(default_factory=list)
    dimensions: List[str] = field(default_factory=list)
    aggregations: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "visual_id": self.visual_id,
            "visual_type": self.visual_type,
            "title": self.title,
            "fields": self.fields,
            "measures": self.measures,
            "dimensions": self.dimensions,
            "aggregations": self.aggregations,
        }


@dataclass
class VisualDataSummary:
    """Statistical summary of data in a visual."""

    row_count: int = 0
    column_count: int = 0
    numeric_stats: Dict[str, Dict[str, float]] = field(default_factory=dict)
    categorical_counts: Dict[str, Dict[str, int]] = field(default_factory=dict)
    date_range: Optional[Dict[str, str]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "row_count": self.row_count,
            "column_count": self.column_count,
            "numeric_stats": self.numeric_stats,
            "categorical_counts": self.categorical_counts,
            "date_range": self.date_range,
        }


class VisualContextExtractor:
    """Extract context from Power BI visuals."""

    # Visual types that typically contain time-series data
    TIME_SERIES_VISUALS = {"lineChart", "areaChart", "lineClusteredColumnComboChart"}

    # Visual types that show categorical comparisons
    CATEGORICAL_VISUALS = {"barChart", "clusteredBarChart", "columnChart", "pieChart", "donutChart"}

    # Visual types that show single KPI values
    KPI_VISUALS = {"card", "multiRowCard", "kpi", "gauge"}

    def extract(self, visual_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract context from a visual's raw data.

        Args:
            visual_data: Raw visual data from Power BI including type, fields, and data rows.

        Returns:
            Enriched visual context dictionary.
        """
        visual_id = visual_data.get("id", "unknown")
        visual_type = visual_data.get("type", "unknown")
        title = visual_data.get("title") or visual_data.get("name", "")
        fields = visual_data.get("fields", [])
        data_rows = visual_data.get("data", [])

        logger.debug(f"Extracting context for visual {visual_id} ({visual_type})")

        metadata = VisualMetadata(
            visual_id=visual_id,
            visual_type=visual_type,
            title=title,
            fields=fields,
            measures=self._extract_measures(fields, visual_data),
            dimensions=self._extract_dimensions(fields, visual_data),
            aggregations=visual_data.get("aggregations", {}),
        )

        data_summary = self._summarize_data(data_rows, fields)

        context = {
            "metadata": metadata.to_dict(),
            "data_summary": data_summary.to_dict(),
            "visual_category": self._categorize_visual(visual_type),
            "analysis_hints": self._get_analysis_hints(visual_type, metadata, data_summary),
        }

        return context

    def _extract_measures(
        self, fields: List[str], visual_data: Dict[str, Any]
    ) -> List[str]:
        """Extract measure fields (numeric/aggregated)."""
        measures = visual_data.get("measures", [])
        if measures:
            return measures
        # Heuristic: fields with aggregation keywords
        return [f for f in fields if any(kw in f.lower() for kw in ("sum", "avg", "count", "total", "amount", "revenue", "profit"))]

    def _extract_dimensions(
        self, fields: List[str], visual_data: Dict[str, Any]
    ) -> List[str]:
        """Extract dimension fields (categorical/grouping)."""
        dimensions = visual_data.get("dimensions", [])
        if dimensions:
            return dimensions
        # Heuristic: fields with category keywords
        return [f for f in fields if any(kw in f.lower() for kw in ("name", "category", "region", "product", "date", "month", "year"))]

    def _summarize_data(
        self, data_rows: List[Dict[str, Any]], fields: List[str]
    ) -> VisualDataSummary:
        """Generate a statistical summary of the visual's data."""
        if not data_rows:
            return VisualDataSummary()

        summary = VisualDataSummary(
            row_count=len(data_rows),
            column_count=len(fields),
        )

        for field_name in fields:
            values = [row.get(field_name) for row in data_rows if row.get(field_name) is not None]
            if not values:
                continue

            # Numeric fields
            if all(isinstance(v, (int, float)) for v in values):
                numeric_values = [float(v) for v in values]
                summary.numeric_stats[field_name] = {
                    "min": min(numeric_values),
                    "max": max(numeric_values),
                    "mean": sum(numeric_values) / len(numeric_values),
                    "count": len(numeric_values),
                }
            else:
                # Categorical fields — top 5 value counts
                from collections import Counter

                counts = Counter(str(v) for v in values)
                summary.categorical_counts[field_name] = dict(counts.most_common(5))

        return summary

    def _categorize_visual(self, visual_type: str) -> str:
        """Categorize a visual type for analysis routing."""
        if visual_type in self.TIME_SERIES_VISUALS:
            return "time_series"
        if visual_type in self.CATEGORICAL_VISUALS:
            return "categorical"
        if visual_type in self.KPI_VISUALS:
            return "kpi"
        return "general"

    def _get_analysis_hints(
        self,
        visual_type: str,
        metadata: VisualMetadata,
        data_summary: VisualDataSummary,
    ) -> List[str]:
        """Suggest relevant analysis types based on visual context."""
        hints = []
        category = self._categorize_visual(visual_type)

        if category == "time_series":
            hints.append("trend_analysis")
            hints.append("anomaly_detection")
            if data_summary.row_count > 20:
                hints.append("forecasting")

        if category == "categorical":
            hints.append("comparison")
            hints.append("contribution_analysis")

        if category == "kpi":
            hints.append("kpi_health")
            hints.append("target_variance")

        if len(metadata.measures) >= 2:
            hints.append("correlation")

        return hints
