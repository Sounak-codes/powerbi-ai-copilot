"""
Report-level analysis for cross-visual reasoning.

Analyzes patterns across multiple pages and the entire report
to identify report-wide themes, redundancies, and opportunities.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from cross_visual_reasoning.page_analysis import PageAnalyzer
from config import get_logger

logger = get_logger(__name__)


@dataclass
class ReportTheme:
    """A theme identified across the report."""
    theme: str
    pages_involved: List[str]
    metrics: List[str]
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "theme": self.theme,
            "pages_involved": self.pages_involved,
            "metrics": self.metrics,
            "description": self.description,
        }


class ReportAnalyzer:
    """
    Analyze an entire report for cross-page patterns and themes.

    Identifies:
    - Common themes across pages
    - Metric redundancies
    - Navigation flow suggestions
    - Report completeness
    """

    def __init__(self):
        self.page_analyzer = PageAnalyzer()

    def analyze_report(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Full cross-page report analysis.

        Args:
            report_data: Complete report data with pages and metadata.

        Returns:
            Report-level analysis with themes, redundancies, and suggestions.
        """
        pages = report_data.get("pages", [])
        report_name = report_data.get("name", "Report")

        if not pages:
            return {"report_name": report_name, "summary": "No pages to analyze."}

        # Analyze each page
        page_analyses = []
        for page in pages:
            analysis = self.page_analyzer.analyze_page(page)
            page_analyses.append(analysis)

        # Cross-page analysis
        themes = self._identify_themes(pages)
        redundancies = self._find_redundancies(pages)
        completeness = self._assess_completeness(pages, page_analyses)
        flow = self._suggest_navigation_flow(pages)

        # Metric usage across pages
        metric_map = self._build_metric_page_map(pages)

        return {
            "report_name": report_name,
            "page_count": len(pages),
            "page_analyses": page_analyses,
            "themes": [t.to_dict() for t in themes],
            "redundancies": redundancies,
            "completeness": completeness,
            "navigation_flow": flow,
            "metric_usage": metric_map,
            "summary": self._build_report_summary(
                report_name, pages, themes, redundancies, completeness
            ),
        }

    def _identify_themes(self, pages: List[Dict[str, Any]]) -> List[ReportTheme]:
        """Identify common themes across pages."""
        themes = []
        page_metrics: Dict[str, List[str]] = {}

        for page in pages:
            page_name = page.get("name", "")
            metrics = set()
            for visual in page.get("visuals", []):
                metrics.update(visual.get("fields", []))
            page_metrics[page_name] = list(metrics)

        # Find metrics that appear on multiple pages
        metric_pages: Dict[str, List[str]] = {}
        for page_name, metrics in page_metrics.items():
            for metric in metrics:
                if metric not in metric_pages:
                    metric_pages[metric] = []
                metric_pages[metric].append(page_name)

        # Group into themes
        multi_page_metrics = {m: p for m, p in metric_pages.items() if len(p) >= 2}
        if multi_page_metrics:
            # Cluster metrics by pages they appear on
            page_sets: Dict[str, List[str]] = {}
            for metric, metric_page_list in multi_page_metrics.items():
                key = ",".join(sorted(metric_page_list))
                if key not in page_sets:
                    page_sets[key] = []
                page_sets[key].append(metric)

            for page_key, metrics in page_sets.items():
                page_list = page_key.split(",")
                themes.append(ReportTheme(
                    theme=f"Cross-page metrics: {', '.join(metrics[:3])}",
                    pages_involved=page_list,
                    metrics=metrics[:5],
                    description=f"{len(metrics)} metric(s) span {len(page_list)} pages — indicating a connected data story.",
                ))

        return themes

    def _find_redundancies(self, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find redundant visuals across pages."""
        redundancies = []
        visual_fingerprints: Dict[str, List[str]] = {}

        for page in pages:
            page_name = page.get("name", "")
            for visual in page.get("visuals", []):
                # Fingerprint: type + sorted fields
                fields = sorted(visual.get("fields", []))
                fingerprint = f"{visual.get('type', '')}:{','.join(fields)}"

                if fingerprint not in visual_fingerprints:
                    visual_fingerprints[fingerprint] = []
                visual_fingerprints[fingerprint].append(page_name)

        for fp, page_list in visual_fingerprints.items():
            if len(page_list) > 1:
                redundancies.append({
                    "visual_type": fp.split(":")[0],
                    "fields": fp.split(":")[1] if ":" in fp else "",
                    "pages": page_list,
                    "suggestion": "Consider consolidating or differentiating these similar visuals.",
                })

        return redundancies

    def _assess_completeness(
        self, pages: List[Dict[str, Any]], page_analyses: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Assess how complete the report is."""
        all_coverages = [a.get("coverage", {}) for a in page_analyses]

        has_any = {
            "trends": any(c.get("has_trends") for c in all_coverages),
            "comparisons": any(c.get("has_comparisons") for c in all_coverages),
            "distributions": any(c.get("has_distributions") for c in all_coverages),
            "kpis": any(c.get("has_kpis") for c in all_coverages),
            "tables": any(c.get("has_tables") for c in all_coverages),
        }

        missing = [k for k, v in has_any.items() if not v]
        score = sum(has_any.values()) / len(has_any) * 100

        return {
            "score": round(score, 0),
            "present": [k for k, v in has_any.items() if v],
            "missing": missing,
            "suggestion": f"Consider adding {', '.join(missing)} visuals." if missing else "Report covers all major visualization types.",
        }

    def _suggest_navigation_flow(self, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Suggest a logical reading order for the pages."""
        flow = []
        for i, page in enumerate(pages):
            page_name = page.get("name", f"Page {i + 1}")
            visuals = page.get("visuals", [])
            types = [v.get("type", "") for v in visuals]

            if any(t in types for t in ("card", "kpi")):
                priority = 1  # Overview pages first
            elif any(t in types for t in ("lineChart", "areaChart")):
                priority = 2  # Trend pages next
            elif any(t in types for t in ("barChart", "pieChart")):
                priority = 3  # Comparison pages
            elif any(t in types for t in ("table", "matrix")):
                priority = 4  # Detail pages last
            else:
                priority = 5

            flow.append({"page": page_name, "priority": priority, "role": self._page_role(types)})

        flow.sort(key=lambda f: f["priority"])
        return flow

    def _page_role(self, visual_types: List[str]) -> str:
        """Determine the role of a page."""
        if any(t in visual_types for t in ("card", "kpi", "gauge")):
            return "Executive Overview"
        if any(t in visual_types for t in ("lineChart", "areaChart")):
            return "Trend Analysis"
        if any(t in visual_types for t in ("barChart", "columnChart", "pieChart")):
            return "Breakdown/Comparison"
        if any(t in visual_types for t in ("table", "matrix")):
            return "Detailed Data"
        return "General"

    def _build_metric_page_map(self, pages: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Map which metrics appear on which pages."""
        metric_map: Dict[str, List[str]] = {}
        for page in pages:
            page_name = page.get("name", "")
            for visual in page.get("visuals", []):
                for field_name in visual.get("fields", []):
                    if field_name not in metric_map:
                        metric_map[field_name] = []
                    if page_name not in metric_map[field_name]:
                        metric_map[field_name].append(page_name)
        return metric_map

    def _build_report_summary(
        self, name: str, pages: List, themes: List, redundancies: List, completeness: Dict
    ) -> str:
        """Build report-level summary."""
        parts = [f"Report '{name}': {len(pages)} pages."]

        if themes:
            parts.append(f" {len(themes)} cross-page theme(s) identified.")
        if redundancies:
            parts.append(f" {len(redundancies)} potential redundancy found.")

        score = completeness.get("score", 0)
        parts.append(f" Completeness: {score:.0f}%.")

        return "".join(parts)
