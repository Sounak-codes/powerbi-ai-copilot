"""
Report documenter.

Generates comprehensive markdown documentation for a full Power BI
report including overview, pages, data model, and measures.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from config import get_logger
from llm.providers.provider_factory import ProviderFactory

logger = get_logger(__name__)


@dataclass
class ReportMetadata:
    """Metadata about a Power BI report."""

    report_name: str
    report_id: str = ""
    workspace: str = ""
    created_date: Optional[str] = None
    modified_date: Optional[str] = None
    author: str = ""
    description: str = ""
    pages: List[Dict[str, Any]] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    measures: List[Dict[str, Any]] = field(default_factory=list)
    relationships: List[Dict[str, Any]] = field(default_factory=list)
    data_sources: List[str] = field(default_factory=list)


@dataclass
class ReportDocumentation:
    """Complete documentation for a Power BI report."""

    report_name: str
    generated_at: str
    overview: str
    page_summaries: List[Dict[str, str]] = field(default_factory=list)
    data_model_description: str = ""
    measure_documentation: List[Dict[str, str]] = field(default_factory=list)
    relationship_map: str = ""
    data_source_notes: str = ""
    markdown: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_name": self.report_name,
            "generated_at": self.generated_at,
            "overview": self.overview,
            "page_summaries": self.page_summaries,
            "data_model_description": self.data_model_description,
            "measure_documentation": self.measure_documentation,
            "relationship_map": self.relationship_map,
            "data_source_notes": self.data_source_notes,
            "markdown": self.markdown,
        }


class ReportDocumenter:
    """
    Generates comprehensive markdown documentation for Power BI reports.

    Produces a full documentation package including report overview,
    page descriptions, data model summary, and measure explanations.
    """

    SYSTEM_PROMPT = (
        "You are a Power BI documentation expert. Generate clear, professional "
        "documentation for Power BI reports that helps business users and developers "
        "understand the report's purpose, structure, and data model.\n\n"
        "Write in a clear, concise style suitable for technical documentation. "
        "Use bullet points for lists and keep descriptions focused on practical value."
    )

    def __init__(self):
        self._provider = ProviderFactory.get_default_provider()

    async def document_report(
        self,
        report_metadata: ReportMetadata,
        include_measures: bool = True,
        include_lineage: bool = False,
    ) -> ReportDocumentation:
        """
        Generate comprehensive documentation for a Power BI report.

        Args:
            report_metadata: Metadata about the report structure.
            include_measures: Whether to document individual measures.
            include_lineage: Whether to include data lineage information.

        Returns:
            ReportDocumentation with full markdown documentation.
        """
        logger.info(f"Documenting report: {report_metadata.report_name}")

        generated_at = datetime.utcnow().isoformat() + "Z"

        # Generate overview
        overview = await self._generate_overview(report_metadata)

        # Generate page summaries
        page_summaries = await self._generate_page_summaries(report_metadata.pages)

        # Generate data model description
        data_model_desc = self._generate_data_model_description(report_metadata)

        # Generate measure documentation
        measure_docs: List[Dict[str, str]] = []
        if include_measures and report_metadata.measures:
            measure_docs = self._generate_measure_list(report_metadata.measures)

        # Generate relationship map
        relationship_map = self._generate_relationship_map(report_metadata.relationships)

        # Data source notes
        data_source_notes = self._format_data_sources(report_metadata.data_sources)

        # Assemble full markdown
        markdown = self._assemble_markdown(
            report_name=report_metadata.report_name,
            generated_at=generated_at,
            overview=overview,
            page_summaries=page_summaries,
            data_model_desc=data_model_desc,
            measure_docs=measure_docs,
            relationship_map=relationship_map,
            data_source_notes=data_source_notes,
        )

        result = ReportDocumentation(
            report_name=report_metadata.report_name,
            generated_at=generated_at,
            overview=overview,
            page_summaries=page_summaries,
            data_model_description=data_model_desc,
            measure_documentation=measure_docs,
            relationship_map=relationship_map,
            data_source_notes=data_source_notes,
            markdown=markdown,
        )

        logger.info(f"Report documentation generated: {len(markdown)} chars")
        return result

    async def _generate_overview(self, metadata: ReportMetadata) -> str:
        """Generate a report overview using LLM."""
        prompt = (
            f"Generate a brief overview (2-3 paragraphs) for a Power BI report with these details:\n"
            f"- Name: {metadata.report_name}\n"
            f"- Description: {metadata.description or 'Not provided'}\n"
            f"- Pages: {len(metadata.pages)}\n"
            f"- Tables: {len(metadata.tables)}\n"
            f"- Measures: {len(metadata.measures)}\n"
            f"- Data Sources: {', '.join(metadata.data_sources) if metadata.data_sources else 'Not specified'}\n"
            f"- Page names: {', '.join(p.get('name', '') for p in metadata.pages[:10])}\n\n"
            "Write a professional overview describing the report's likely purpose and scope."
        )

        try:
            response = await self._provider.generate(
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT,
            )
            return response.strip()
        except Exception as e:
            logger.error(f"Overview generation failed: {e}")
            return (
                f"{metadata.report_name} is a Power BI report containing "
                f"{len(metadata.pages)} pages with {len(metadata.measures)} measures "
                f"across {len(metadata.tables)} tables."
            )

    async def _generate_page_summaries(
        self, pages: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Generate brief summaries for each page."""
        summaries = []

        for page in pages:
            name = page.get("name", "Unnamed Page")
            visuals = page.get("visuals", [])
            visual_types = [v.get("type", "unknown") for v in visuals]

            summary = {
                "name": name,
                "visual_count": str(len(visuals)),
                "visual_types": ", ".join(set(visual_types)) if visual_types else "none",
                "description": page.get("description", f"Page with {len(visuals)} visuals."),
            }
            summaries.append(summary)

        return summaries

    def _generate_data_model_description(self, metadata: ReportMetadata) -> str:
        """Generate data model description from metadata."""
        parts = []
        parts.append(f"The data model contains {len(metadata.tables)} tables:\n")

        for table in metadata.tables:
            name = table.get("name", "Unknown")
            columns = table.get("columns", [])
            row_count = table.get("row_count", "unknown")
            parts.append(f"- **{name}**: {len(columns)} columns, {row_count} rows")

        if metadata.relationships:
            parts.append(f"\n{len(metadata.relationships)} relationships connect the tables.")

        return "\n".join(parts)

    def _generate_measure_list(
        self, measures: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Generate documentation entries for measures."""
        docs = []
        for measure in measures:
            docs.append({
                "name": measure.get("name", "Unknown"),
                "table": measure.get("table", ""),
                "expression": measure.get("expression", ""),
                "description": measure.get("description", ""),
            })
        return docs

    def _generate_relationship_map(
        self, relationships: List[Dict[str, Any]]
    ) -> str:
        """Generate a text-based relationship map."""
        if not relationships:
            return "No relationships defined."

        lines = ["| From | To | Cardinality | Active |", "|------|-----|-------------|--------|"]

        for rel in relationships:
            from_ref = f"{rel.get('from_table', '?')}[{rel.get('from_column', '?')}]"
            to_ref = f"{rel.get('to_table', '?')}[{rel.get('to_column', '?')}]"
            cardinality = rel.get("cardinality", "unknown")
            active = "Yes" if rel.get("active", True) else "No"
            lines.append(f"| {from_ref} | {to_ref} | {cardinality} | {active} |")

        return "\n".join(lines)

    def _format_data_sources(self, data_sources: List[str]) -> str:
        """Format data source information."""
        if not data_sources:
            return "No data source information available."
        return "\n".join(f"- {ds}" for ds in data_sources)

    def _assemble_markdown(
        self,
        report_name: str,
        generated_at: str,
        overview: str,
        page_summaries: List[Dict[str, str]],
        data_model_desc: str,
        measure_docs: List[Dict[str, str]],
        relationship_map: str,
        data_source_notes: str,
    ) -> str:
        """Assemble all sections into a single markdown document."""
        sections = []

        # Header
        sections.append(f"# {report_name} - Documentation\n")
        sections.append(f"*Generated: {generated_at}*\n")

        # Overview
        sections.append("## Overview\n")
        sections.append(f"{overview}\n")

        # Pages
        sections.append("## Pages\n")
        for page in page_summaries:
            sections.append(f"### {page['name']}\n")
            sections.append(f"- **Visuals**: {page['visual_count']}")
            sections.append(f"- **Visual Types**: {page['visual_types']}")
            sections.append(f"- **Description**: {page['description']}\n")

        # Data Model
        sections.append("## Data Model\n")
        sections.append(f"{data_model_desc}\n")

        # Relationships
        sections.append("### Relationships\n")
        sections.append(f"{relationship_map}\n")

        # Data Sources
        sections.append("## Data Sources\n")
        sections.append(f"{data_source_notes}\n")

        # Measures
        if measure_docs:
            sections.append("## Measures\n")
            for m in measure_docs:
                sections.append(f"### {m['name']}\n")
                if m.get("table"):
                    sections.append(f"- **Table**: {m['table']}")
                if m.get("description"):
                    sections.append(f"- **Description**: {m['description']}")
                if m.get("expression"):
                    sections.append(f"\n```dax\n{m['expression']}\n```\n")

        return "\n".join(sections)
