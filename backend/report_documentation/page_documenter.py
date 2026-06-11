"""
Page documenter.

Documents a single Power BI report page including its visuals,
fields used, and inferred purpose.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from config import get_logger
from llm.providers.provider_factory import ProviderFactory

logger = get_logger(__name__)


@dataclass
class VisualInfo:
    """Information about a single visual on a page."""

    visual_id: str
    visual_type: str
    title: str = ""
    fields: List[str] = field(default_factory=list)
    measures: List[str] = field(default_factory=list)
    filters: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "visual_id": self.visual_id,
            "visual_type": self.visual_type,
            "title": self.title,
            "fields": self.fields,
            "measures": self.measures,
            "filters": self.filters,
        }


@dataclass
class PageDocumentation:
    """Documentation for a single report page."""

    page_name: str
    purpose: str
    visuals: List[VisualInfo] = field(default_factory=list)
    fields_used: List[str] = field(default_factory=list)
    measures_used: List[str] = field(default_factory=list)
    interactions: str = ""
    filters: List[str] = field(default_factory=list)
    markdown: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page_name": self.page_name,
            "purpose": self.purpose,
            "visuals": [v.to_dict() for v in self.visuals],
            "fields_used": self.fields_used,
            "measures_used": self.measures_used,
            "interactions": self.interactions,
            "filters": self.filters,
            "markdown": self.markdown,
        }


class PageDocumenter:
    """
    Documents a single Power BI report page.

    Analyzes visuals, fields, and layout to generate a comprehensive
    description of the page's purpose and content.
    """

    SYSTEM_PROMPT = (
        "You are a Power BI report documentation specialist. Given information about "
        "a report page (visuals, fields, measures), infer the page's business purpose "
        "and describe how the visuals work together to tell a story.\n\n"
        "Be concise and focus on business value. Describe what questions the page "
        "helps answer and what insights users can derive from it."
    )

    def __init__(self):
        self._provider = ProviderFactory.get_default_provider()

    def _extract_visuals(self, page_data: Dict[str, Any]) -> List[VisualInfo]:
        """Extract visual information from raw page data."""
        visuals_data = page_data.get("visuals", [])
        visuals: List[VisualInfo] = []

        for v in visuals_data:
            visual = VisualInfo(
                visual_id=v.get("id", ""),
                visual_type=v.get("type", "unknown"),
                title=v.get("title", ""),
                fields=v.get("fields", []),
                measures=v.get("measures", []),
                filters=v.get("filters", []),
            )
            visuals.append(visual)

        return visuals

    def _collect_fields(self, visuals: List[VisualInfo]) -> List[str]:
        """Collect all unique fields used across visuals."""
        fields: set = set()
        for v in visuals:
            fields.update(v.fields)
        return sorted(fields)

    def _collect_measures(self, visuals: List[VisualInfo]) -> List[str]:
        """Collect all unique measures used across visuals."""
        measures: set = set()
        for v in visuals:
            measures.update(v.measures)
        return sorted(measures)

    def _collect_filters(self, page_data: Dict[str, Any], visuals: List[VisualInfo]) -> List[str]:
        """Collect page-level and visual-level filters."""
        filters: set = set()

        # Page-level filters
        page_filters = page_data.get("filters", [])
        filters.update(page_filters)

        # Visual-level filters
        for v in visuals:
            filters.update(v.filters)

        return sorted(filters)

    async def document_page(
        self,
        page_data: Dict[str, Any],
    ) -> PageDocumentation:
        """
        Generate documentation for a single report page.

        Args:
            page_data: Dictionary containing page metadata including:
                - name: Page display name
                - visuals: List of visual definitions
                - filters: Page-level filters

        Returns:
            PageDocumentation with purpose, visual details, and markdown.
        """
        page_name = page_data.get("name", "Unnamed Page")
        logger.info(f"Documenting page: {page_name}")

        # Extract structured info
        visuals = self._extract_visuals(page_data)
        fields_used = self._collect_fields(visuals)
        measures_used = self._collect_measures(visuals)
        filters = self._collect_filters(page_data, visuals)

        # Infer page purpose using LLM
        purpose = await self._infer_purpose(page_name, visuals, fields_used, measures_used)

        # Generate interactions description
        interactions = self._describe_interactions(visuals)

        # Generate markdown
        markdown = self._generate_markdown(
            page_name, purpose, visuals, fields_used, measures_used, filters, interactions
        )

        result = PageDocumentation(
            page_name=page_name,
            purpose=purpose,
            visuals=visuals,
            fields_used=fields_used,
            measures_used=measures_used,
            interactions=interactions,
            filters=filters,
            markdown=markdown,
        )

        logger.info(f"Page documented: {page_name} ({len(visuals)} visuals)")
        return result

    async def _infer_purpose(
        self,
        page_name: str,
        visuals: List[VisualInfo],
        fields: List[str],
        measures: List[str],
    ) -> str:
        """Infer the page's business purpose using LLM."""
        visual_summary = ", ".join(
            f"{v.visual_type}({v.title or 'untitled'})" for v in visuals
        )

        prompt = (
            f"Describe the business purpose of a Power BI page with these details:\n"
            f"- Page Name: {page_name}\n"
            f"- Visuals: {visual_summary}\n"
            f"- Fields Used: {', '.join(fields[:15])}\n"
            f"- Measures Used: {', '.join(measures[:10])}\n\n"
            "Write 2-3 sentences describing what business questions this page answers."
        )

        try:
            response = await self._provider.generate(
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT,
            )
            return response.strip()
        except Exception as e:
            logger.error(f"Purpose inference failed: {e}")
            return (
                f"This page ({page_name}) contains {len(visuals)} visuals "
                f"using {len(fields)} fields and {len(measures)} measures."
            )

    def _describe_interactions(self, visuals: List[VisualInfo]) -> str:
        """Describe how visuals on the page might interact."""
        if len(visuals) <= 1:
            return "Single visual page - no cross-visual interactions."

        # Identify common fields that could enable cross-filtering
        field_counts: Dict[str, int] = {}
        for v in visuals:
            for f in v.fields:
                field_counts[f] = field_counts.get(f, 0) + 1

        shared_fields = [f for f, count in field_counts.items() if count > 1]

        if shared_fields:
            return (
                f"Visuals share {len(shared_fields)} common fields "
                f"({', '.join(shared_fields[:5])}), enabling cross-filtering interactions."
            )

        return "Visuals appear to show independent data dimensions."

    def _generate_markdown(
        self,
        page_name: str,
        purpose: str,
        visuals: List[VisualInfo],
        fields: List[str],
        measures: List[str],
        filters: List[str],
        interactions: str,
    ) -> str:
        """Generate markdown documentation for the page."""
        sections = []

        sections.append(f"## {page_name}\n")
        sections.append(f"**Purpose**: {purpose}\n")

        # Visuals table
        sections.append("### Visuals\n")
        sections.append("| # | Type | Title | Fields | Measures |")
        sections.append("|---|------|-------|--------|----------|")
        for i, v in enumerate(visuals, 1):
            fields_str = ", ".join(v.fields[:3]) + ("..." if len(v.fields) > 3 else "")
            measures_str = ", ".join(v.measures[:3]) + ("..." if len(v.measures) > 3 else "")
            sections.append(f"| {i} | {v.visual_type} | {v.title} | {fields_str} | {measures_str} |")

        # Fields
        sections.append(f"\n### Fields Used ({len(fields)})\n")
        for f in fields:
            sections.append(f"- {f}")

        # Measures
        if measures:
            sections.append(f"\n### Measures Used ({len(measures)})\n")
            for m in measures:
                sections.append(f"- {m}")

        # Filters
        if filters:
            sections.append(f"\n### Filters ({len(filters)})\n")
            for f in filters:
                sections.append(f"- {f}")

        # Interactions
        sections.append(f"\n### Interactions\n")
        sections.append(interactions)

        return "\n".join(sections)
