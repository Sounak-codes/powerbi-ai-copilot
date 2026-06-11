"""
Context builder - orchestrates all context extractors into a unified context object.

This is the main entry point for the context engine. It combines visual, filter,
selection, slicer, page, and report context into a single enriched context
that can be passed to the orchestrator and downstream agents.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from config import get_logger
from context_engine.visual_context import VisualContextExtractor
from context_engine.filter_context import FilterContextExtractor
from context_engine.selection_context import SelectionContextExtractor
from context_engine.page_context import PageContextExtractor
from context_engine.report_context import ReportContextExtractor
from context_engine.slicer_context import SlicerContextExtractor

logger = get_logger(__name__)


class ContextBuilder:
    """
    Builds a unified context object from Power BI report state.

    Combines output from all context extractors into a single
    enriched context that downstream agents can consume.
    """

    def __init__(self):
        self.visual_extractor = VisualContextExtractor()
        self.filter_extractor = FilterContextExtractor()
        self.selection_extractor = SelectionContextExtractor()
        self.page_extractor = PageContextExtractor()
        self.report_extractor = ReportContextExtractor()
        self.slicer_extractor = SlicerContextExtractor()

    def build(self, raw_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build unified context from raw Power BI report state.

        Args:
            raw_context: Dictionary containing report state from the frontend,
                including report data, page data, visual data, filters,
                selections, and slicers.

        Returns:
            Unified context object with all extracted and enriched context.
        """
        logger.info("Building unified report context")

        # Extract each context layer
        report_ctx = self._extract_report_context(raw_context)
        page_ctx = self._extract_page_context(raw_context)
        visual_ctx = self._extract_visual_context(raw_context)
        filter_ctx = self._extract_filter_context(raw_context)
        selection_ctx = self._extract_selection_context(raw_context)
        slicer_ctx = self._extract_slicer_context(raw_context)

        # Build unified context
        unified = {
            "timestamp": datetime.utcnow().isoformat(),
            "report": report_ctx,
            "page": page_ctx,
            "visuals": visual_ctx,
            "filters": filter_ctx,
            "selection": selection_ctx,
            "slicers": slicer_ctx,
            "summary": self._build_overall_summary(
                report_ctx, page_ctx, filter_ctx, selection_ctx, slicer_ctx
            ),
        }

        logger.debug("Unified context built successfully")
        return unified

    def build_for_prompt(self, raw_context: Dict[str, Any]) -> str:
        """
        Build a concise text representation of context for LLM prompts.

        This produces a compact string suitable for including in system
        or user prompts to give the LLM awareness of the current state.
        """
        ctx = self.build(raw_context)
        parts = []

        # Report info
        report_meta = ctx.get("report", {}).get("metadata", {})
        if report_meta.get("report_name"):
            parts.append(f"Report: {report_meta['report_name']}")

        # Page info
        page_meta = ctx.get("page", {}).get("metadata", {})
        if page_meta.get("display_name"):
            parts.append(f"Current page: {page_meta['display_name']}")

        # Filter summary
        filter_summary = ctx.get("filters", {}).get("filter_summary", "")
        if filter_summary and "No filters" not in filter_summary:
            parts.append(f"Filters: {filter_summary}")

        # Slicer summary
        slicer_summary = ctx.get("slicers", {}).get("slicer_summary", "")
        if slicer_summary and "No slicers" not in slicer_summary and "default" not in slicer_summary:
            parts.append(f"Slicers: {slicer_summary}")

        # Selection
        selection_summary = ctx.get("selection", {}).get("selection_summary", "")
        if selection_summary and "No data points" not in selection_summary:
            parts.append(f"Selection: {selection_summary}")

        return "\n".join(parts) if parts else "No report context available."

    def _extract_report_context(self, raw_context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract report-level context."""
        report_data = raw_context.get("report", {})
        if not report_data:
            return {}
        return self.report_extractor.extract(report_data)

    def _extract_page_context(self, raw_context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract page-level context."""
        page_data = raw_context.get("page", raw_context.get("currentPage", {}))
        if not page_data:
            return {}
        return self.page_extractor.extract(page_data)

    def _extract_visual_context(self, raw_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract context for all visuals (or the focused visual)."""
        # If a specific visual is focused
        focused_visual = raw_context.get("focusedVisual")
        if focused_visual:
            return [self.visual_extractor.extract(focused_visual)]

        # Otherwise extract from all visuals on the page
        visuals = raw_context.get("visuals", [])
        page_data = raw_context.get("page", raw_context.get("currentPage", {}))
        if not visuals and page_data:
            visuals = page_data.get("visuals", [])

        return [self.visual_extractor.extract(v) for v in visuals]

    def _extract_filter_context(self, raw_context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract filter context."""
        filters = raw_context.get("filters", [])
        if isinstance(filters, dict):
            # Already processed or nested — try to get the raw list
            filters = filters.get("active_filters", [])
        return self.filter_extractor.extract(filters)

    def _extract_selection_context(self, raw_context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract selection context."""
        selection = raw_context.get("selection")
        return self.selection_extractor.extract(selection)

    def _extract_slicer_context(self, raw_context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract slicer context."""
        slicers = raw_context.get("slicers", [])
        return self.slicer_extractor.extract(slicers)

    def _build_overall_summary(
        self,
        report_ctx: Dict[str, Any],
        page_ctx: Dict[str, Any],
        filter_ctx: Dict[str, Any],
        selection_ctx: Dict[str, Any],
        slicer_ctx: Dict[str, Any],
    ) -> str:
        """Build a one-paragraph overall context summary."""
        parts = []

        report_summary = report_ctx.get("report_summary", "")
        if report_summary:
            parts.append(report_summary)

        page_summary = page_ctx.get("page_summary", "")
        if page_summary:
            parts.append(page_summary)

        filter_summary = filter_ctx.get("filter_summary", "")
        if filter_summary and "No filters" not in filter_summary:
            parts.append(filter_summary)

        slicer_summary = slicer_ctx.get("slicer_summary", "")
        if slicer_summary and "No slicers" not in slicer_summary and "default" not in slicer_summary:
            parts.append(slicer_summary)

        selection_summary = selection_ctx.get("selection_summary", "")
        if selection_summary and "No data points" not in selection_summary:
            parts.append(selection_summary)

        return " ".join(parts) if parts else "No context available."
