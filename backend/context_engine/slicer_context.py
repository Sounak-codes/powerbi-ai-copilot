"""
Slicer context extraction for Power BI reports.

Extracts the state of slicer visuals (dropdown, range slider, date pickers)
which directly affect data scope and are critical for accurate analysis context.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from config import get_logger

logger = get_logger(__name__)


@dataclass
class SlicerState:
    """State of a single slicer visual."""

    slicer_id: str
    target_table: str
    target_column: str
    slicer_type: str  # "list", "dropdown", "range", "date", "relative_date"
    selected_values: List[Any] = field(default_factory=list)
    range_start: Optional[Any] = None
    range_end: Optional[Any] = None
    is_inverted: bool = False  # "select all except"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "slicer_id": self.slicer_id,
            "target_table": self.target_table,
            "target_column": self.target_column,
            "slicer_type": self.slicer_type,
            "selected_values": self.selected_values,
            "range_start": self.range_start,
            "range_end": self.range_end,
            "is_inverted": self.is_inverted,
        }

    def to_natural_language(self) -> str:
        """Convert slicer state to human-readable description."""
        col = f"{self.target_table}.{self.target_column}"

        if self.slicer_type in ("range", "date"):
            if self.range_start and self.range_end:
                return f"{col} between {self.range_start} and {self.range_end}"
            if self.range_start:
                return f"{col} from {self.range_start} onwards"
            if self.range_end:
                return f"{col} up to {self.range_end}"

        if self.selected_values:
            if self.is_inverted:
                vals = ", ".join(str(v) for v in self.selected_values[:3])
                return f"{col} excludes [{vals}]"
            vals = ", ".join(str(v) for v in self.selected_values[:5])
            suffix = f" +{len(self.selected_values) - 5} more" if len(self.selected_values) > 5 else ""
            return f"{col} = [{vals}{suffix}]"

        return f"{col} (no selection)"

    @property
    def has_selection(self) -> bool:
        return bool(self.selected_values) or self.range_start is not None or self.range_end is not None


class SlicerContextExtractor:
    """Extract slicer state and build slicer context."""

    def extract(self, slicers_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Extract slicer context from raw slicer state data.

        Args:
            slicers_data: List of slicer state objects from Power BI.

        Returns:
            Structured slicer context with natural language summary.
        """
        if not slicers_data:
            return {
                "slicers": [],
                "active_slicers": [],
                "slicer_summary": "No slicers are configured on this page.",
                "data_scope_impact": [],
            }

        all_slicers = self._parse_slicers(slicers_data)
        active_slicers = [s for s in all_slicers if s.has_selection]

        logger.debug(
            f"Extracted {len(all_slicers)} slicers, {len(active_slicers)} active"
        )

        return {
            "slicers": [s.to_dict() for s in all_slicers],
            "active_slicers": [s.to_dict() for s in active_slicers],
            "slicer_summary": self._build_summary(active_slicers),
            "data_scope_impact": self._assess_scope_impact(active_slicers),
            "slicer_count": len(all_slicers),
            "active_count": len(active_slicers),
        }

    def _parse_slicers(self, slicers_data: List[Dict[str, Any]]) -> List[SlicerState]:
        """Parse raw slicer data into SlicerState objects."""
        slicers = []

        for raw in slicers_data:
            try:
                target = raw.get("target", {})
                slicer = SlicerState(
                    slicer_id=raw.get("id", raw.get("visualId", "")),
                    target_table=target.get("table", ""),
                    target_column=target.get("column", ""),
                    slicer_type=self._detect_slicer_type(raw),
                    selected_values=raw.get("selectedValues", raw.get("values", [])),
                    range_start=raw.get("rangeStart", raw.get("min")),
                    range_end=raw.get("rangeEnd", raw.get("max")),
                    is_inverted=raw.get("isInverted", False),
                )
                slicers.append(slicer)
            except Exception as e:
                logger.warning(f"Failed to parse slicer: {e}")
                continue

        return slicers

    def _detect_slicer_type(self, raw: Dict[str, Any]) -> str:
        """Detect the slicer type from raw data."""
        explicit_type = raw.get("slicerType", raw.get("type", ""))
        if explicit_type:
            return explicit_type

        # Heuristic: if it has range fields, it's a range slicer
        if raw.get("rangeStart") is not None or raw.get("min") is not None:
            # Check if it looks like a date
            col = raw.get("target", {}).get("column", "").lower()
            if any(kw in col for kw in ("date", "time", "month", "year")):
                return "date"
            return "range"

        return "list"

    def _build_summary(self, active_slicers: List[SlicerState]) -> str:
        """Build natural language summary of active slicer selections."""
        if not active_slicers:
            return "All slicers are in their default state (no active selections)."

        descriptions = [s.to_natural_language() for s in active_slicers]

        if len(descriptions) == 1:
            return f"Active slicer: {descriptions[0]}."

        return "Active slicers: " + "; ".join(descriptions) + "."

    def _assess_scope_impact(self, active_slicers: List[SlicerState]) -> List[Dict[str, Any]]:
        """Assess how slicers impact the data scope for analysis."""
        impacts = []

        for slicer in active_slicers:
            impact = {
                "table": slicer.target_table,
                "column": slicer.target_column,
                "restriction_type": slicer.slicer_type,
            }

            if slicer.slicer_type == "date":
                impact["narrows_time_window"] = True
            elif slicer.slicer_type == "range":
                impact["narrows_numeric_range"] = True
            else:
                impact["narrows_categories"] = True
                impact["selected_count"] = len(slicer.selected_values)

            impacts.append(impact)

        return impacts
