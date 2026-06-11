"""
Report parser for ingesting Power BI report metadata into RAG.

Extracts structured information from Power BI report definitions,
including measures, columns, relationships, and page structure.
"""
from typing import Dict, Any, List, Optional
from config import get_logger

logger = get_logger(__name__)


class ReportParser:
    """
    Parse Power BI report metadata into documents for RAG indexing.

    Converts report structure (pages, visuals, measures) into
    text documents that can be embedded and retrieved.
    """

    def parse_report(self, report_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse a report into indexable documents.

        Args:
            report_data: Report definition dict with pages, dataset, etc.

        Returns:
            List of documents ready for chunking and embedding.
        """
        documents = []

        report_name = report_data.get("name", "Unknown Report")
        report_id = report_data.get("id", "unknown")

        # Report overview document
        overview = self._parse_overview(report_data)
        if overview:
            documents.append({
                "id": f"{report_id}_overview",
                "text": overview,
                "metadata": {
                    "source_type": "report_overview",
                    "report_id": report_id,
                    "report_name": report_name,
                },
            })

        # Parse each page
        for page in report_data.get("pages", []):
            page_docs = self._parse_page(page, report_id, report_name)
            documents.extend(page_docs)

        # Parse dataset/data model
        dataset = report_data.get("dataset", {})
        if dataset:
            model_docs = self._parse_data_model(dataset, report_id, report_name)
            documents.extend(model_docs)

        logger.info(f"Parsed report '{report_name}': {len(documents)} documents")
        return documents

    def _parse_overview(self, report_data: Dict[str, Any]) -> str:
        """Create an overview document for the report."""
        name = report_data.get("name", "Unknown")
        pages = report_data.get("pages", [])
        page_names = [p.get("name", p.get("displayName", "")) for p in pages]

        text = f"Report: {name}\n"
        text += f"Pages ({len(pages)}): {', '.join(page_names)}\n"

        if report_data.get("description"):
            text += f"Description: {report_data['description']}\n"

        return text

    def _parse_page(
        self, page: Dict[str, Any], report_id: str, report_name: str
    ) -> List[Dict[str, Any]]:
        """Parse a page into documents."""
        documents = []
        page_name = page.get("name", page.get("displayName", "Unknown Page"))
        page_id = page.get("id", "unknown")

        visuals = page.get("visuals", [])
        text = f"Page: {page_name}\n"
        text += f"Visuals ({len(visuals)}):\n"

        for visual in visuals:
            v_type = visual.get("type", "unknown")
            v_title = visual.get("title", visual.get("name", ""))
            v_fields = visual.get("fields", [])

            text += f"- {v_title or v_type} ({v_type})"
            if v_fields:
                text += f": {', '.join(v_fields[:5])}"
            text += "\n"

        documents.append({
            "id": f"{report_id}_page_{page_id}",
            "text": text,
            "metadata": {
                "source_type": "report_page",
                "report_id": report_id,
                "report_name": report_name,
                "page_name": page_name,
                "visual_count": len(visuals),
            },
        })

        return documents

    def _parse_data_model(
        self, dataset: Dict[str, Any], report_id: str, report_name: str
    ) -> List[Dict[str, Any]]:
        """Parse the data model into documents."""
        documents = []

        for table in dataset.get("tables", []):
            if not isinstance(table, dict):
                continue

            table_name = table.get("name", "Unknown")
            columns = table.get("columns", [])
            measures = table.get("measures", [])

            text = f"Table: {table_name}\n"

            if columns:
                col_names = [
                    c.get("name", c) if isinstance(c, dict) else str(c)
                    for c in columns
                ]
                text += f"Columns: {', '.join(col_names)}\n"

            if measures:
                text += "Measures:\n"
                for m in measures:
                    if isinstance(m, dict):
                        m_name = m.get("name", "")
                        m_expr = m.get("expression", "")
                        text += f"  - {m_name}"
                        if m_expr:
                            text += f" = {m_expr}"
                        text += "\n"
                    else:
                        text += f"  - {m}\n"

            documents.append({
                "id": f"{report_id}_table_{table_name}",
                "text": text,
                "metadata": {
                    "source_type": "data_model",
                    "report_id": report_id,
                    "report_name": report_name,
                    "table_name": table_name,
                    "column_count": len(columns),
                    "measure_count": len(measures),
                },
            })

        return documents
