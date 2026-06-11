"""
Visual relationship detection for cross-visual reasoning.

Identifies relationships between visuals on a report page based on
shared dimensions, measures, filters, and data model connections.
"""
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from config import get_logger

logger = get_logger(__name__)


class RelationshipType(str, Enum):
    """Types of relationships between visuals."""
    SHARED_DIMENSION = "shared_dimension"
    SHARED_MEASURE = "shared_measure"
    DRILL_DOWN = "drill_down"
    DETAIL_OF = "detail_of"
    COMPLEMENT = "complement"
    FILTER_TARGET = "filter_target"
    SAME_TABLE = "same_table"


@dataclass
class VisualRelationship:
    """A detected relationship between two visuals."""
    visual_a_id: str
    visual_b_id: str
    relationship_type: RelationshipType
    shared_fields: List[str] = field(default_factory=list)
    strength: float = 0.0  # 0-1
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "visual_a_id": self.visual_a_id,
            "visual_b_id": self.visual_b_id,
            "relationship_type": self.relationship_type.value,
            "shared_fields": self.shared_fields,
            "strength": round(self.strength, 3),
            "description": self.description,
        }


class VisualRelationshipDetector:
    """
    Detect relationships between visuals on a Power BI page.

    Analyzes field overlaps, data model connections, and visual types
    to determine how visuals relate to each other for cross-visual reasoning.
    """

    def detect_relationships(
        self, visuals: List[Dict[str, Any]]
    ) -> List[VisualRelationship]:
        """
        Detect all pairwise relationships between visuals.

        Args:
            visuals: List of visual metadata dicts with "id", "type", "fields", etc.

        Returns:
            List of detected VisualRelationships.
        """
        relationships = []

        for i in range(len(visuals)):
            for j in range(i + 1, len(visuals)):
                rels = self._analyze_pair(visuals[i], visuals[j])
                relationships.extend(rels)

        logger.debug(f"Detected {len(relationships)} visual relationships from {len(visuals)} visuals")
        return relationships

    def get_related_visuals(
        self,
        visual_id: str,
        visuals: List[Dict[str, Any]],
        relationship_types: Optional[List[RelationshipType]] = None,
    ) -> List[Dict[str, Any]]:
        """Get all visuals related to a specific visual."""
        all_rels = self.detect_relationships(visuals)
        related = []

        for rel in all_rels:
            if relationship_types and rel.relationship_type not in relationship_types:
                continue

            if rel.visual_a_id == visual_id:
                related.append({"visual_id": rel.visual_b_id, "relationship": rel.to_dict()})
            elif rel.visual_b_id == visual_id:
                related.append({"visual_id": rel.visual_a_id, "relationship": rel.to_dict()})

        return related

    def build_relationship_graph(
        self, visuals: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build a graph representation of all visual relationships."""
        relationships = self.detect_relationships(visuals)

        nodes = [{"id": v.get("id", ""), "type": v.get("type", ""), "title": v.get("title", "")} for v in visuals]
        edges = [r.to_dict() for r in relationships]

        return {
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
        }

    def _analyze_pair(
        self, visual_a: Dict[str, Any], visual_b: Dict[str, Any]
    ) -> List[VisualRelationship]:
        """Analyze the relationship between two visuals."""
        relationships = []
        id_a = visual_a.get("id", "")
        id_b = visual_b.get("id", "")

        fields_a = set(visual_a.get("fields", []))
        fields_b = set(visual_b.get("fields", []))

        # Shared fields
        shared = fields_a & fields_b
        if shared:
            # Determine if shared fields are dimensions or measures
            dims_shared = [f for f in shared if self._is_dimension(f)]
            measures_shared = [f for f in shared if not self._is_dimension(f)]

            if dims_shared:
                relationships.append(VisualRelationship(
                    visual_a_id=id_a,
                    visual_b_id=id_b,
                    relationship_type=RelationshipType.SHARED_DIMENSION,
                    shared_fields=dims_shared,
                    strength=len(dims_shared) / max(len(fields_a | fields_b), 1),
                    description=f"Share dimension(s): {', '.join(dims_shared)}",
                ))

            if measures_shared:
                relationships.append(VisualRelationship(
                    visual_a_id=id_a,
                    visual_b_id=id_b,
                    relationship_type=RelationshipType.SHARED_MEASURE,
                    shared_fields=measures_shared,
                    strength=len(measures_shared) / max(len(fields_a | fields_b), 1),
                    description=f"Share measure(s): {', '.join(measures_shared)}",
                ))

        # Same table
        table_a = self._extract_tables(fields_a)
        table_b = self._extract_tables(fields_b)
        shared_tables = table_a & table_b
        if shared_tables and not shared:
            relationships.append(VisualRelationship(
                visual_a_id=id_a,
                visual_b_id=id_b,
                relationship_type=RelationshipType.SAME_TABLE,
                shared_fields=list(shared_tables),
                strength=0.3,
                description=f"Use same table(s): {', '.join(shared_tables)}",
            ))

        # Detail relationship (one is a summary, other has more detail)
        type_a = visual_a.get("type", "")
        type_b = visual_b.get("type", "")
        if self._is_summary_visual(type_a) and self._is_detail_visual(type_b) and shared:
            relationships.append(VisualRelationship(
                visual_a_id=id_a,
                visual_b_id=id_b,
                relationship_type=RelationshipType.DETAIL_OF,
                shared_fields=list(shared),
                strength=0.7,
                description=f"{type_b} provides detail for {type_a}",
            ))

        return relationships

    def _is_dimension(self, field_name: str) -> bool:
        """Heuristic to determine if a field is a dimension."""
        dim_keywords = ("name", "category", "region", "product", "date", "month", "year", "id", "type", "status")
        return any(kw in field_name.lower() for kw in dim_keywords)

    def _extract_tables(self, fields: set) -> set:
        """Extract table names from Table.Column formatted fields."""
        tables = set()
        for f in fields:
            if "." in f:
                tables.add(f.split(".")[0])
        return tables

    def _is_summary_visual(self, visual_type: str) -> bool:
        return visual_type in ("card", "kpi", "gauge", "multiRowCard")

    def _is_detail_visual(self, visual_type: str) -> bool:
        return visual_type in ("table", "matrix", "lineChart", "barChart", "columnChart")
