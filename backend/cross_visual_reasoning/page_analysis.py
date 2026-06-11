"""
Page-level analysis for cross-visual reasoning.

Analyzes all visuals on a page together to derive page-level insights
that can't be seen from any single visual alone.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from cross_visual_reasoning.visual_relationships import VisualRelationshipDetector
from config import get_logger

logger = get_logger(__name__)


@dataclass
class PageInsight:
    """An insight derived from cross-visual analysis of a page."""
    insight_type: str  # "contradiction", "reinforcement", "gap", "opportunity"
    description: str
    involved_visuals: List[str]
    confidence: float = 0.7

    def to_dict(self) -> Dict[str, Any]:
        return {
            "insight_type": self.insight_type,
            "description": self.description,
            "involved_visuals": self.involved_visuals,
            "confidence": round(self.confidence, 3),
        }


class PageAnalyzer:
    """
    Analyze a page holistically by looking across all visuals.

    Identifies:
    - Contradictions between visuals
    - Reinforcing patterns
    - Missing information gaps
    - Cross-visual opportunities
    """

    def __init__(self):
        self.relationship_detector = VisualRelationshipDetector()

    def analyze_page(
        self,
        page_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Perform cross-visual analysis of a page.

        Args:
            page_data: Page dict with "visuals", "name", "filters", etc.

        Returns:
            Analysis results with relationships, insights, and narrative.
        """
        visuals = page_data.get("visuals", [])
        page_name = page_data.get("name", "Unknown Page")

        if not visuals:
            return {"page_name": page_name, "insights": [], "summary": "No visuals to analyze."}

        # Detect relationships
        relationships = self.relationship_detector.detect_relationships(visuals)
        graph = self.relationship_detector.build_relationship_graph(visuals)

        # Generate insights
        insights = []
        insights.extend(self._detect_contradictions(visuals))
        insights.extend(self._detect_reinforcements(visuals))
        insights.extend(self._detect_gaps(visuals, page_data))
        insights.extend(self._detect_data_story(visuals, relationships))

        # Build summary
        summary = self._build_page_narrative(page_name, visuals, relationships, insights)

        return {
            "page_name": page_name,
            "visual_count": len(visuals),
            "relationship_graph": graph,
            "insights": [i.to_dict() for i in insights],
            "summary": summary,
            "coverage": self._assess_coverage(visuals),
        }

    def _detect_contradictions(self, visuals: List[Dict[str, Any]]) -> List[PageInsight]:
        """Detect contradictions between visuals showing same metric differently."""
        insights = []
        metric_visuals: Dict[str, List[Dict[str, Any]]] = {}

        for visual in visuals:
            for field_name in visual.get("fields", []):
                if field_name not in metric_visuals:
                    metric_visuals[field_name] = []
                metric_visuals[field_name].append(visual)

        # Check for same metric with conflicting trends
        for metric, vis_list in metric_visuals.items():
            if len(vis_list) < 2:
                continue

            trends = set()
            for v in vis_list:
                data = v.get("data", [])
                if len(data) >= 2:
                    values = [row.get(metric, 0) for row in data if metric in row]
                    if len(values) >= 2:
                        trend = "up" if values[-1] > values[0] else "down"
                        trends.add(trend)

            if len(trends) > 1:
                involved = [v.get("id", "") for v in vis_list]
                insights.append(PageInsight(
                    insight_type="contradiction",
                    description=f"'{metric}' shows conflicting trends across visuals — verify filters and time ranges.",
                    involved_visuals=involved,
                    confidence=0.6,
                ))

        return insights

    def _detect_reinforcements(self, visuals: List[Dict[str, Any]]) -> List[PageInsight]:
        """Detect when multiple visuals reinforce the same story."""
        insights = []
        # Group visuals by the story they tell (simplified: same trend direction)
        trending_up = []
        trending_down = []

        for visual in visuals:
            data = visual.get("data", [])
            if len(data) >= 2:
                # Check if numeric values are generally increasing
                numeric_fields = [
                    f for f in visual.get("fields", [])
                    if isinstance(data[0].get(f), (int, float))
                ] if data else []

                for field_name in numeric_fields:
                    values = [row.get(field_name, 0) for row in data if field_name in row]
                    if values and values[-1] > values[0]:
                        trending_up.append(visual.get("id", ""))
                    elif values and values[-1] < values[0]:
                        trending_down.append(visual.get("id", ""))

        if len(trending_up) >= 3:
            insights.append(PageInsight(
                insight_type="reinforcement",
                description=f"{len(trending_up)} visuals show upward trends — consistent positive performance signal.",
                involved_visuals=trending_up[:5],
                confidence=0.75,
            ))

        if len(trending_down) >= 3:
            insights.append(PageInsight(
                insight_type="reinforcement",
                description=f"{len(trending_down)} visuals show downward trends — consistent concern signal.",
                involved_visuals=trending_down[:5],
                confidence=0.75,
            ))

        return insights

    def _detect_gaps(
        self, visuals: List[Dict[str, Any]], page_data: Dict[str, Any]
    ) -> List[PageInsight]:
        """Detect missing visualizations that would complete the page story."""
        insights = []
        visual_types = set(v.get("type", "") for v in visuals)
        all_fields = set()
        for v in visuals:
            all_fields.update(v.get("fields", []))

        # If there are trends but no KPI cards
        has_time_series = bool(visual_types & {"lineChart", "areaChart"})
        has_kpi = bool(visual_types & {"card", "kpi", "gauge"})

        if has_time_series and not has_kpi:
            insights.append(PageInsight(
                insight_type="gap",
                description="Page has trend visuals but no KPI cards — consider adding headline metrics.",
                involved_visuals=[],
                confidence=0.5,
            ))

        # If there are comparisons but no totals
        has_categorical = bool(visual_types & {"barChart", "columnChart", "pieChart"})
        if has_categorical and not has_kpi:
            insights.append(PageInsight(
                insight_type="gap",
                description="Page shows breakdowns but no overall totals — readers may miss the big picture.",
                involved_visuals=[],
                confidence=0.5,
            ))

        return insights

    def _detect_data_story(
        self,
        visuals: List[Dict[str, Any]],
        relationships: List,
    ) -> List[PageInsight]:
        """Detect the overall data story the page is telling."""
        insights = []

        # Strong inter-connection suggests a coherent story
        if len(relationships) > len(visuals):
            insights.append(PageInsight(
                insight_type="opportunity",
                description="Visuals are highly interconnected — cross-filtering will be effective for exploration.",
                involved_visuals=[v.get("id", "") for v in visuals[:5]],
                confidence=0.7,
            ))

        return insights

    def _assess_coverage(self, visuals: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Assess what types of analysis the page covers."""
        types = [v.get("type", "") for v in visuals]
        return {
            "has_trends": any(t in types for t in ("lineChart", "areaChart")),
            "has_comparisons": any(t in types for t in ("barChart", "columnChart")),
            "has_distributions": any(t in types for t in ("pieChart", "donutChart", "treemap")),
            "has_kpis": any(t in types for t in ("card", "kpi", "gauge")),
            "has_tables": any(t in types for t in ("table", "matrix")),
            "has_maps": any(t in types for t in ("map", "filledMap")),
        }

    def _build_page_narrative(
        self,
        page_name: str,
        visuals: List[Dict[str, Any]],
        relationships: List,
        insights: List[PageInsight],
    ) -> str:
        """Build a narrative summary of the page analysis."""
        parts = [f"Page '{page_name}' contains {len(visuals)} visuals with {len(relationships)} relationships."]

        contradictions = [i for i in insights if i.insight_type == "contradiction"]
        reinforcements = [i for i in insights if i.insight_type == "reinforcement"]

        if contradictions:
            parts.append(f" ⚠️ {len(contradictions)} potential contradiction(s) detected.")
        if reinforcements:
            parts.append(f" ✓ Consistent patterns observed across multiple visuals.")

        return "".join(parts)
