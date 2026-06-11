"""
Metric dependency analysis for cross-visual reasoning.

Maps how metrics depend on each other across visuals, enabling
the system to understand impact chains (if metric A changes,
what other metrics/visuals are affected).
"""
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from config import get_logger

logger = get_logger(__name__)


@dataclass
class MetricDependency:
    """A dependency between two metrics."""
    source_metric: str
    dependent_metric: str
    dependency_type: str  # "calculated_from", "derived", "correlated", "filtered_by"
    strength: float = 0.0
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_metric": self.source_metric,
            "dependent_metric": self.dependent_metric,
            "dependency_type": self.dependency_type,
            "strength": round(self.strength, 3),
            "description": self.description,
        }


class MetricDependencyAnalyzer:
    """
    Analyze dependencies between metrics across a report.

    Builds a dependency graph showing which metrics influence
    which others, enabling impact analysis.
    """

    def analyze(
        self,
        measures: List[Dict[str, Any]],
        visuals: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze metric dependencies.

        Args:
            measures: DAX measures with "name" and "expression".
            visuals: Optional visuals metadata for usage context.

        Returns:
            Dependency analysis results.
        """
        dependencies = self._extract_from_measures(measures)

        if visuals:
            visual_deps = self._extract_from_visuals(visuals)
            dependencies.extend(visual_deps)

        # Build graph
        graph = self._build_graph(dependencies)

        return {
            "dependencies": [d.to_dict() for d in dependencies],
            "graph": graph,
            "root_metrics": self._find_roots(dependencies),
            "leaf_metrics": self._find_leaves(dependencies, measures),
            "impact_chains": self._find_impact_chains(dependencies),
        }

    def get_impact_of(
        self, metric_name: str, dependencies: List[MetricDependency]
    ) -> List[str]:
        """Get all metrics impacted if a given metric changes."""
        impacted = set()
        queue = [metric_name]

        while queue:
            current = queue.pop(0)
            for dep in dependencies:
                if dep.source_metric == current and dep.dependent_metric not in impacted:
                    impacted.add(dep.dependent_metric)
                    queue.append(dep.dependent_metric)

        return sorted(impacted)

    def get_drivers_of(
        self, metric_name: str, dependencies: List[MetricDependency]
    ) -> List[str]:
        """Get all metrics that drive/influence a given metric."""
        drivers = set()
        queue = [metric_name]

        while queue:
            current = queue.pop(0)
            for dep in dependencies:
                if dep.dependent_metric == current and dep.source_metric not in drivers:
                    drivers.add(dep.source_metric)
                    queue.append(dep.source_metric)

        return sorted(drivers)

    def _extract_from_measures(
        self, measures: List[Dict[str, Any]]
    ) -> List[MetricDependency]:
        """Extract dependencies from DAX measure expressions."""
        import re
        dependencies = []
        measure_names = {m.get("name", "") for m in measures}

        for measure in measures:
            name = measure.get("name", "")
            expression = measure.get("expression", "")

            if not expression:
                continue

            # Find references to other measures [MeasureName]
            refs = re.findall(r"\[([^\]]+)\]", expression)
            for ref in refs:
                if ref in measure_names and ref != name:
                    dependencies.append(MetricDependency(
                        source_metric=ref,
                        dependent_metric=name,
                        dependency_type="calculated_from",
                        strength=0.9,
                        description=f"{name} is calculated from {ref}",
                    ))

        return dependencies

    def _extract_from_visuals(
        self, visuals: List[Dict[str, Any]]
    ) -> List[MetricDependency]:
        """Extract co-occurrence dependencies from visuals."""
        dependencies = []
        metric_visuals: Dict[str, List[str]] = {}

        for visual in visuals:
            vid = visual.get("id", "")
            for field_name in visual.get("fields", []):
                if field_name not in metric_visuals:
                    metric_visuals[field_name] = []
                metric_visuals[field_name].append(vid)

        # Metrics that always appear together have a dependency
        metrics = list(metric_visuals.keys())
        for i in range(len(metrics)):
            for j in range(i + 1, len(metrics)):
                shared_visuals = set(metric_visuals[metrics[i]]) & set(metric_visuals[metrics[j]])
                if len(shared_visuals) >= 2:
                    dependencies.append(MetricDependency(
                        source_metric=metrics[i],
                        dependent_metric=metrics[j],
                        dependency_type="correlated",
                        strength=len(shared_visuals) / max(
                            len(metric_visuals[metrics[i]]),
                            len(metric_visuals[metrics[j]]),
                        ),
                        description=f"Frequently appear together in {len(shared_visuals)} visuals",
                    ))

        return dependencies

    def _build_graph(self, dependencies: List[MetricDependency]) -> Dict[str, List[str]]:
        """Build adjacency list representation."""
        graph: Dict[str, List[str]] = {}
        for dep in dependencies:
            if dep.source_metric not in graph:
                graph[dep.source_metric] = []
            graph[dep.source_metric].append(dep.dependent_metric)
        return graph

    def _find_roots(self, dependencies: List[MetricDependency]) -> List[str]:
        """Find root metrics (no dependencies on other metrics)."""
        all_sources = {d.source_metric for d in dependencies}
        all_targets = {d.dependent_metric for d in dependencies}
        return sorted(all_sources - all_targets)

    def _find_leaves(
        self, dependencies: List[MetricDependency], measures: List[Dict[str, Any]]
    ) -> List[str]:
        """Find leaf metrics (nothing depends on them)."""
        all_sources = {d.source_metric for d in dependencies}
        all_targets = {d.dependent_metric for d in dependencies}
        all_metrics = {m.get("name", "") for m in measures}
        return sorted((all_targets | all_metrics) - all_sources)

    def _find_impact_chains(
        self, dependencies: List[MetricDependency]
    ) -> List[Dict[str, Any]]:
        """Find the longest impact chains."""
        graph = self._build_graph(dependencies)
        chains = []

        for root in self._find_roots(dependencies):
            chain = self._dfs_chain(root, graph, set())
            if len(chain) > 2:
                chains.append({"chain": chain, "length": len(chain)})

        chains.sort(key=lambda c: c["length"], reverse=True)
        return chains[:5]

    def _dfs_chain(
        self, node: str, graph: Dict[str, List[str]], visited: Set[str]
    ) -> List[str]:
        """DFS to find the longest chain from a node."""
        if node in visited or node not in graph:
            return [node]

        visited.add(node)
        longest = [node]

        for neighbor in graph.get(node, []):
            chain = [node] + self._dfs_chain(neighbor, graph, visited.copy())
            if len(chain) > len(longest):
                longest = chain

        return longest
