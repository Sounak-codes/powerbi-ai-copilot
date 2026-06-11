"""
Page context extraction for Power BI report pages.

Builds context about the current page including its visuals,
layout, relationships between visuals, and page-level metadata.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from config import get_logger

logger = get_logger(__name__)


@dataclass
class PageMetadata:
    """Metadata about a Power BI report page."""

    page_id: str
    display_name: str
    is_active: bool = True
    visual_count: int = 0
    page_type: str = "standard"  # "standard", "tooltip", "drillthrough"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page_id": self.page_id,
            "display_name": self.display_name,
            "is_active": self.is_active,
            "visual_count": self.visual_count,
            "page_type": self.page_type,
        }


class PageContextExtractor:
    """Extract context from a Power BI report page."""

    def extract(self, page_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract page-level context.

        Args:
            page_data: Raw page data from Power BI including visuals list and metadata.

        Returns:
            Structured page context.
        """
        page_id = page_data.get("id", "unknown")
        display_name = page_data.get("name", page_data.get("displayName", ""))
        visuals = page_data.get("visuals", [])

        logger.debug(f"Extracting context for page '{display_name}' ({len(visuals)} visuals)")

        metadata = PageMetadata(
            page_id=page_id,
            display_name=display_name,
            is_active=page_data.get("isActive", True),
            visual_count=len(visuals),
            page_type=self._determine_page_type(page_data),
        )

        visual_inventory = self._build_visual_inventory(visuals)
        relationships = self._detect_visual_relationships(visuals)

        return {
            "metadata": metadata.to_dict(),
            "visual_inventory": visual_inventory,
            "visual_relationships": relationships,
            "page_summary": self._build_page_summary(metadata, visual_inventory),
            "data_tables_used": self._get_tables_used(visuals),
        }

    def _determine_page_type(self, page_data: Dict[str, Any]) -> str:
        """Determine the type of page (standard, tooltip, drillthrough)."""
        if page_data.get("isTooltipPage"):
            return "tooltip"
        if page_data.get("isDrillthroughPage"):
            return "drillthrough"
        return "standard"

    def _build_visual_inventory(self, visuals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build a concise inventory of all visuals on the page."""
        inventory = []

        for visual in visuals:
            entry = {
                "id": visual.get("id", ""),
                "type": visual.get("type", "unknown"),
                "title": visual.get("title", visual.get("name", "")),
                "fields": visual.get("fields", []),
            }
            inventory.append(entry)

        return inventory

    def _detect_visual_relationships(
        self, visuals: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Detect relationships between visuals based on shared fields.

        If two visuals share a dimension field, they are likely related
        and cross-filtering may be relevant.
        """
        relationships = []
        visual_fields: Dict[str, set] = {}

        for visual in visuals:
            vid = visual.get("id", "")
            fields = set(visual.get("fields", []))
            visual_fields[vid] = fields

        visual_ids = list(visual_fields.keys())
        for i in range(len(visual_ids)):
            for j in range(i + 1, len(visual_ids)):
                vid_a = visual_ids[i]
                vid_b = visual_ids[j]
                shared = visual_fields[vid_a] & visual_fields[vid_b]
                if shared:
                    relationships.append({
                        "visual_a": vid_a,
                        "visual_b": vid_b,
                        "shared_fields": list(shared),
                        "relationship_type": "shared_dimension",
                    })

        return relationships

    def _get_tables_used(self, visuals: List[Dict[str, Any]]) -> List[str]:
        """Extract all data tables referenced by visuals on this page."""
        tables = set()

        for visual in visuals:
            # Fields might be formatted as "Table.Column"
            for field_name in visual.get("fields", []):
                if "." in field_name:
                    table = field_name.split(".")[0]
                    tables.add(table)

            # Explicit table references
            if "table" in visual:
                tables.add(visual["table"])

        return sorted(tables)

    def _build_page_summary(
        self, metadata: PageMetadata, inventory: List[Dict[str, Any]]
    ) -> str:
        """Build a natural language summary of the page."""
        visual_types = [v["type"] for v in inventory]

        type_counts: Dict[str, int] = {}
        for vt in visual_types:
            type_counts[vt] = type_counts.get(vt, 0) + 1

        parts = [f"Page '{metadata.display_name}' contains {metadata.visual_count} visuals"]

        type_descriptions = [f"{count} {vtype}" for vtype, count in type_counts.items()]
        if type_descriptions:
            parts.append(f" ({', '.join(type_descriptions)})")

        return "".join(parts) + "."
