"""
Lineage builder.

Builds data lineage showing Table → Column → Measure → Visual
relationships as a graph structure.
"""
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
import re

from config import get_logger
from llm.providers.provider_factory import ProviderFactory

logger = get_logger(__name__)


@dataclass
class LineageNode:
    """A node in the data lineage graph."""

    id: str
    name: str
    node_type: str  # "table", "column", "measure", "visual"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "node_type": self.node_type,
            "metadata": self.metadata,
        }


@dataclass
class LineageEdge:
    """An edge in the data lineage graph."""

    source_id: str
    target_id: str
    relationship: str  # "contains", "references", "uses", "feeds"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relationship": self.relationship,
        }


@dataclass
class LineageGraph:
    """Complete data lineage graph."""

    nodes: List[LineageNode] = field(default_factory=list)
    edges: List[LineageEdge] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "summary": {
                "total_nodes": len(self.nodes),
                "total_edges": len(self.edges),
                "tables": sum(1 for n in self.nodes if n.node_type == "table"),
                "columns": sum(1 for n in self.nodes if n.node_type == "column"),
                "measures": sum(1 for n in self.nodes if n.node_type == "measure"),
                "visuals": sum(1 for n in self.nodes if n.node_type == "visual"),
            },
        }

    def get_upstream(self, node_id: str) -> List[LineageNode]:
        """Get all upstream nodes (sources that feed into this node)."""
        upstream_ids = {e.source_id for e in self.edges if e.target_id == node_id}
        return [n for n in self.nodes if n.id in upstream_ids]

    def get_downstream(self, node_id: str) -> List[LineageNode]:
        """Get all downstream nodes (targets fed by this node)."""
        downstream_ids = {e.target_id for e in self.edges if e.source_id == node_id}
        return [n for n in self.nodes if n.id in downstream_ids]

    def get_full_lineage(self, node_id: str) -> Dict[str, List[LineageNode]]:
        """Get complete upstream and downstream lineage for a node."""
        upstream: List[LineageNode] = []
        downstream: List[LineageNode] = []

        # Walk upstream
        visited: Set[str] = set()
        queue = [node_id]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            parents = self.get_upstream(current)
            for p in parents:
                if p.id != node_id:
                    upstream.append(p)
                queue.append(p.id)

        # Walk downstream
        visited = set()
        queue = [node_id]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            children = self.get_downstream(current)
            for c in children:
                if c.id != node_id:
                    downstream.append(c)
                queue.append(c.id)

        return {"upstream": upstream, "downstream": downstream}


class LineageBuilder:
    """
    Builds data lineage graphs showing the flow from
    Table → Column → Measure → Visual.

    Parses the data model, DAX expressions, and visual definitions
    to construct a complete lineage graph.
    """

    def __init__(self):
        self._provider = ProviderFactory.get_default_provider()
        self._nodes: Dict[str, LineageNode] = {}
        self._edges: List[LineageEdge] = []

    def _make_id(self, node_type: str, *parts: str) -> str:
        """Create a unique node ID."""
        clean_parts = [p.replace(" ", "_").replace("'", "") for p in parts]
        return f"{node_type}::{'.'.join(clean_parts)}"

    def _add_node(self, node: LineageNode) -> None:
        """Add a node if it doesn't already exist."""
        if node.id not in self._nodes:
            self._nodes[node.id] = node

    def _add_edge(self, source_id: str, target_id: str, relationship: str) -> None:
        """Add an edge to the graph."""
        # Avoid duplicates
        for e in self._edges:
            if e.source_id == source_id and e.target_id == target_id:
                return
        self._edges.append(LineageEdge(
            source_id=source_id,
            target_id=target_id,
            relationship=relationship,
        ))

    def _process_tables(self, tables: List[Dict[str, Any]]) -> None:
        """Process tables and columns into nodes."""
        for table in tables:
            table_name = table.get("name", "Unknown")
            table_id = self._make_id("table", table_name)

            self._add_node(LineageNode(
                id=table_id,
                name=table_name,
                node_type="table",
                metadata={"row_count": table.get("row_count", 0)},
            ))

            # Add columns
            for column in table.get("columns", []):
                col_name = column if isinstance(column, str) else column.get("name", "")
                col_id = self._make_id("column", table_name, col_name)

                self._add_node(LineageNode(
                    id=col_id,
                    name=col_name,
                    node_type="column",
                    metadata={"table": table_name},
                ))

                # Table contains column
                self._add_edge(table_id, col_id, "contains")

    def _process_measures(
        self, measures: List[Dict[str, Any]]
    ) -> None:
        """Process measures and link to their column dependencies."""
        for measure in measures:
            measure_name = measure.get("name", "Unknown")
            measure_table = measure.get("table", "")
            expression = measure.get("expression", "")
            measure_id = self._make_id("measure", measure_name)

            self._add_node(LineageNode(
                id=measure_id,
                name=measure_name,
                node_type="measure",
                metadata={
                    "table": measure_table,
                    "expression": expression[:200],
                },
            ))

            # Parse dependencies from expression
            # Column references: Table[Column] or 'Table Name'[Column]
            col_refs = re.findall(r"'?([^'\[\]\n]+)'?\[([^\]]+)\]", expression)
            for ref_table, ref_col in col_refs:
                ref_table = ref_table.strip()
                col_id = self._make_id("column", ref_table, ref_col)
                # Column feeds into measure
                self._add_edge(col_id, measure_id, "feeds")

            # Measure references: [MeasureName] (standalone)
            measure_refs = re.findall(r"\[([^\]]+)\]", expression)
            known_measure_names = {m.get("name", "") for m in measures}
            for ref in measure_refs:
                if ref in known_measure_names and ref != measure_name:
                    ref_id = self._make_id("measure", ref)
                    self._add_edge(ref_id, measure_id, "references")

    def _process_visuals(self, visuals: List[Dict[str, Any]]) -> None:
        """Process visuals and link to their field/measure usage."""
        for visual in visuals:
            visual_id_raw = visual.get("id", visual.get("title", "unknown"))
            visual_name = visual.get("title", visual.get("type", "Visual"))
            visual_id = self._make_id("visual", visual_id_raw)

            self._add_node(LineageNode(
                id=visual_id,
                name=visual_name,
                node_type="visual",
                metadata={
                    "type": visual.get("type", "unknown"),
                    "page": visual.get("page", ""),
                },
            ))

            # Link fields (columns) to visual
            for field_ref in visual.get("fields", []):
                # Try to match Table[Column] format
                match = re.match(r"'?([^'\[\]]+)'?\[([^\]]+)\]", field_ref)
                if match:
                    table, col = match.group(1).strip(), match.group(2)
                    col_id = self._make_id("column", table, col)
                    self._add_edge(col_id, visual_id, "uses")
                else:
                    # Might be just a column name
                    col_id = self._make_id("column", "unknown", field_ref)
                    self._add_edge(col_id, visual_id, "uses")

            # Link measures to visual
            for measure_ref in visual.get("measures", []):
                measure_id = self._make_id("measure", measure_ref)
                self._add_edge(measure_id, visual_id, "uses")

    def build_lineage(
        self,
        tables: List[Dict[str, Any]],
        measures: List[Dict[str, Any]],
        visuals: List[Dict[str, Any]],
    ) -> LineageGraph:
        """
        Build a complete data lineage graph.

        Args:
            tables: List of table definitions with 'name' and 'columns' keys.
            measures: List of measure definitions with 'name', 'table', 'expression' keys.
            visuals: List of visual definitions with 'id', 'fields', 'measures' keys.

        Returns:
            LineageGraph with nodes and edges representing the data flow.
        """
        logger.info(
            f"Building lineage: {len(tables)} tables, "
            f"{len(measures)} measures, {len(visuals)} visuals"
        )

        # Reset state for fresh build
        self._nodes = {}
        self._edges = []

        # Process each layer
        self._process_tables(tables)
        self._process_measures(measures)
        self._process_visuals(visuals)

        graph = LineageGraph(
            nodes=list(self._nodes.values()),
            edges=self._edges,
        )

        summary = graph.to_dict()["summary"]
        logger.info(
            f"Lineage built: {summary['total_nodes']} nodes, "
            f"{summary['total_edges']} edges"
        )

        return graph

    def get_measure_lineage(
        self,
        measure_name: str,
        graph: LineageGraph,
    ) -> Dict[str, Any]:
        """
        Get the complete lineage for a specific measure.

        Args:
            measure_name: Name of the measure to trace.
            graph: The lineage graph to search.

        Returns:
            Dict with upstream sources and downstream consumers.
        """
        measure_id = self._make_id("measure", measure_name)
        lineage = graph.get_full_lineage(measure_id)

        return {
            "measure": measure_name,
            "sources": [
                {"name": n.name, "type": n.node_type}
                for n in lineage["upstream"]
            ],
            "consumers": [
                {"name": n.name, "type": n.node_type}
                for n in lineage["downstream"]
            ],
        }

    def get_impact_analysis(
        self,
        column_name: str,
        table_name: str,
        graph: LineageGraph,
    ) -> Dict[str, Any]:
        """
        Analyze the impact of changing a column.

        Args:
            column_name: Name of the column.
            table_name: Table the column belongs to.
            graph: The lineage graph.

        Returns:
            Dict listing all measures and visuals affected by this column.
        """
        col_id = self._make_id("column", table_name, column_name)
        downstream = graph.get_full_lineage(col_id)["downstream"]

        affected_measures = [n for n in downstream if n.node_type == "measure"]
        affected_visuals = [n for n in downstream if n.node_type == "visual"]

        return {
            "column": f"{table_name}[{column_name}]",
            "affected_measures": [
                {"name": m.name, "table": m.metadata.get("table", "")}
                for m in affected_measures
            ],
            "affected_visuals": [
                {"name": v.name, "type": v.metadata.get("type", "")}
                for v in affected_visuals
            ],
            "total_impact": len(affected_measures) + len(affected_visuals),
        }
