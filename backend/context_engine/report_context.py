"""
Report-level context extraction for Power BI reports.

Builds the full report context including all pages, data model info,
and report-wide metadata.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from config import get_logger

logger = get_logger(__name__)


@dataclass
class ReportMetadata:
    """Metadata about a Power BI report."""

    report_id: str
    report_name: str
    page_count: int = 0
    dataset_id: Optional[str] = None
    workspace_id: Optional[str] = None
    tables: List[str] = field(default_factory=list)
    measures: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "report_name": self.report_name,
            "page_count": self.page_count,
            "dataset_id": self.dataset_id,
            "workspace_id": self.workspace_id,
            "tables": self.tables,
            "measures": self.measures,
        }


class ReportContextExtractor:
    """Extract report-level context from Power BI."""

    def extract(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract report-level context.

        Args:
            report_data: Raw report data including pages, dataset info, and metadata.

        Returns:
            Structured report context.
        """
        report_id = report_data.get("id", "unknown")
        report_name = report_data.get("name", "")
        pages = report_data.get("pages", [])
        dataset = report_data.get("dataset", {})

        logger.debug(f"Extracting context for report '{report_name}' ({len(pages)} pages)")

        metadata = ReportMetadata(
            report_id=report_id,
            report_name=report_name,
            page_count=len(pages),
            dataset_id=dataset.get("id"),
            workspace_id=report_data.get("workspaceId"),
            tables=self._extract_tables(dataset),
            measures=self._extract_measures(dataset),
        )

        return {
            "metadata": metadata.to_dict(),
            "pages": self._summarize_pages(pages),
            "data_model": self._extract_data_model(dataset),
            "report_summary": self._build_report_summary(metadata, pages),
        }

    def _extract_tables(self, dataset: Dict[str, Any]) -> List[str]:
        """Extract table names from the dataset."""
        tables = dataset.get("tables", [])
        if isinstance(tables, list):
            return [t.get("name", t) if isinstance(t, dict) else str(t) for t in tables]
        return []

    def _extract_measures(self, dataset: Dict[str, Any]) -> List[str]:
        """Extract measure names from the dataset."""
        measures = []
        tables = dataset.get("tables", [])

        for table in tables:
            if isinstance(table, dict):
                table_measures = table.get("measures", [])
                for m in table_measures:
                    name = m.get("name", m) if isinstance(m, dict) else str(m)
                    measures.append(name)

        return measures

    def _extract_data_model(self, dataset: Dict[str, Any]) -> Dict[str, Any]:
        """Extract a summary of the data model."""
        if not dataset:
            return {"tables": [], "relationships": []}

        tables_info = []
        for table in dataset.get("tables", []):
            if isinstance(table, dict):
                tables_info.append({
                    "name": table.get("name", ""),
                    "columns": [
                        c.get("name", c) if isinstance(c, dict) else str(c)
                        for c in table.get("columns", [])
                    ],
                    "measures": [
                        m.get("name", m) if isinstance(m, dict) else str(m)
                        for m in table.get("measures", [])
                    ],
                })

        return {
            "tables": tables_info,
            "relationships": dataset.get("relationships", []),
            "table_count": len(tables_info),
        }

    def _summarize_pages(self, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create a concise summary of all pages."""
        summaries = []

        for page in pages:
            summaries.append({
                "id": page.get("id", ""),
                "name": page.get("name", page.get("displayName", "")),
                "visual_count": len(page.get("visuals", [])),
                "is_active": page.get("isActive", False),
            })

        return summaries

    def _build_report_summary(
        self, metadata: ReportMetadata, pages: List[Dict[str, Any]]
    ) -> str:
        """Build a natural language report summary."""
        parts = [
            f"Report '{metadata.report_name}' has {metadata.page_count} pages",
        ]

        if metadata.tables:
            parts.append(f", uses {len(metadata.tables)} tables ({', '.join(metadata.tables[:5])})")

        if metadata.measures:
            parts.append(f", and {len(metadata.measures)} measures")

        return "".join(parts) + "."
