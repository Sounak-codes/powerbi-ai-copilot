"""
Selection context extraction for Power BI reports.

Handles user selections (clicks, highlights) on visuals to provide
the LLM with awareness of what the user is focusing on.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from config import get_logger

logger = get_logger(__name__)


@dataclass
class DataPointSelection:
    """A single selected data point in a visual."""

    visual_id: str
    values: Dict[str, Any] = field(default_factory=dict)
    identity: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "visual_id": self.visual_id,
            "values": self.values,
            "identity": self.identity,
        }


@dataclass
class SelectionState:
    """Current selection state in the report."""

    visual_id: Optional[str] = None
    selected_points: List[DataPointSelection] = field(default_factory=list)
    is_cross_highlighting: bool = False
    source_visual: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "visual_id": self.visual_id,
            "selected_points": [p.to_dict() for p in self.selected_points],
            "is_cross_highlighting": self.is_cross_highlighting,
            "source_visual": self.source_visual,
            "point_count": len(self.selected_points),
        }

    @property
    def has_selection(self) -> bool:
        return len(self.selected_points) > 0


class SelectionContextExtractor:
    """Extract context from user selections in Power BI visuals."""

    def extract(self, selection_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Extract selection context from raw selection event data.

        Args:
            selection_data: Selection event data from Power BI JS API.

        Returns:
            Structured selection context.
        """
        if not selection_data:
            return {
                "has_selection": False,
                "selection_summary": "No data points are currently selected.",
                "focus_area": None,
            }

        state = self._parse_selection(selection_data)

        if not state.has_selection:
            return {
                "has_selection": False,
                "selection_summary": "No data points are currently selected.",
                "focus_area": None,
            }

        logger.debug(
            f"Extracted selection: {len(state.selected_points)} points from visual {state.visual_id}"
        )

        return {
            "has_selection": True,
            "selection_state": state.to_dict(),
            "selection_summary": self._build_summary(state),
            "focus_area": self._determine_focus(state),
            "cross_highlighting": state.is_cross_highlighting,
        }

    def _parse_selection(self, selection_data: Dict[str, Any]) -> SelectionState:
        """Parse raw selection data into SelectionState."""
        visual_id = selection_data.get("visual_id") or selection_data.get("visualId")
        data_points = selection_data.get("dataPoints", [])
        is_cross = selection_data.get("isCrossHighlighting", False)

        points = []
        for dp in data_points:
            point = DataPointSelection(
                visual_id=visual_id or "",
                values=dp.get("values", dp) if isinstance(dp, dict) else {"value": dp},
                identity=dp.get("identity") if isinstance(dp, dict) else None,
            )
            points.append(point)

        return SelectionState(
            visual_id=visual_id,
            selected_points=points,
            is_cross_highlighting=is_cross,
            source_visual=selection_data.get("sourceVisual"),
        )

    def _build_summary(self, state: SelectionState) -> str:
        """Build natural language summary of the selection."""
        count = len(state.selected_points)

        if count == 1:
            point = state.selected_points[0]
            values_str = ", ".join(f"{k}={v}" for k, v in point.values.items())
            return f"User selected a data point ({values_str}) in visual '{state.visual_id}'."

        return (
            f"User selected {count} data points in visual '{state.visual_id}'."
        )

    def _determine_focus(self, state: SelectionState) -> Dict[str, Any]:
        """Determine what the user is focusing on based on selection."""
        focus = {
            "visual_id": state.visual_id,
            "type": "single_point" if len(state.selected_points) == 1 else "multi_point",
        }

        # Extract common dimensions across selected points
        if state.selected_points:
            all_keys = set()
            for point in state.selected_points:
                all_keys.update(point.values.keys())
            focus["dimensions"] = list(all_keys)

        # If cross-highlighting, the user may be exploring relationships
        if state.is_cross_highlighting:
            focus["intent_hint"] = "exploring_relationships"
        elif len(state.selected_points) > 1:
            focus["intent_hint"] = "comparing_items"
        else:
            focus["intent_hint"] = "drilling_into_detail"

        return focus
