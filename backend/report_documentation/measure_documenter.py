"""
Measure documenter.

Documents DAX measures including what they calculate,
their dependencies, and where they are used in the report.
"""
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
import re

from config import get_logger
from llm.providers.provider_factory import ProviderFactory

logger = get_logger(__name__)


@dataclass
class MeasureDependency:
    """A dependency of a DAX measure."""

    name: str
    type: str  # "measure", "column", "table"
    table: str = ""


@dataclass
class MeasureDocumentation:
    """Documentation for a single DAX measure."""

    measure_name: str
    table: str
    expression: str
    description: str
    dependencies: List[MeasureDependency] = field(default_factory=list)
    used_in_visuals: List[str] = field(default_factory=list)
    category: str = ""  # e.g., "Time Intelligence", "Aggregation", etc.
    complexity: str = "simple"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "measure_name": self.measure_name,
            "table": self.table,
            "expression": self.expression,
            "description": self.description,
            "dependencies": [
                {"name": d.name, "type": d.type, "table": d.table}
                for d in self.dependencies
            ],
            "used_in_visuals": self.used_in_visuals,
            "category": self.category,
            "complexity": self.complexity,
        }


@dataclass
class MeasureCatalog:
    """Complete catalog of all documented measures."""

    measures: List[MeasureDocumentation] = field(default_factory=list)
    categories: Dict[str, List[str]] = field(default_factory=dict)
    dependency_graph: Dict[str, List[str]] = field(default_factory=dict)
    markdown: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "measures": [m.to_dict() for m in self.measures],
            "categories": self.categories,
            "dependency_graph": self.dependency_graph,
            "markdown": self.markdown,
        }


class MeasureDocumenter:
    """
    Documents DAX measures with descriptions, dependencies, and usage.

    Analyzes DAX expressions to extract dependencies, categorize measures,
    and generate human-readable documentation using LLM.
    """

    SYSTEM_PROMPT = (
        "You are a DAX documentation expert. Given a DAX measure expression, "
        "provide a clear one-sentence business description of what it calculates. "
        "Focus on the business meaning, not the technical implementation.\n\n"
        "Respond with ONLY the description, no extra formatting."
    )

    # Patterns for categorizing measures
    CATEGORY_PATTERNS: Dict[str, List[str]] = {
        "Time Intelligence": [
            "TOTALYTD", "TOTALQTD", "TOTALMTD", "SAMEPERIODLASTYEAR",
            "DATEADD", "DATESYTD", "DATESINPERIOD", "PREVIOUSMONTH",
            "PREVIOUSQUARTER", "PREVIOUSYEAR",
        ],
        "Aggregation": ["SUM", "AVERAGE", "COUNT", "COUNTROWS", "MIN", "MAX"],
        "Ratio/Percentage": ["DIVIDE", "PERCENTAGE"],
        "Ranking": ["RANKX", "TOPN"],
        "Conditional": ["SWITCH", "IF"],
        "Iterator": ["SUMX", "AVERAGEX", "COUNTX", "MAXX", "MINX"],
        "Filter Modification": ["CALCULATE", "CALCULATETABLE", "ALL", "ALLEXCEPT"],
    }

    def __init__(self):
        self._provider = ProviderFactory.get_default_provider()

    def _extract_dependencies(
        self,
        expression: str,
        all_measure_names: Optional[Set[str]] = None,
    ) -> List[MeasureDependency]:
        """Extract measure and column dependencies from a DAX expression."""
        dependencies: List[MeasureDependency] = []
        seen: Set[str] = set()

        # Find column references: Table[Column] or 'Table Name'[Column]
        column_refs = re.findall(r"'?([^'\[\]]+)'?\[([^\]]+)\]", expression)
        for table, column in column_refs:
            table = table.strip()
            key = f"{table}.{column}"
            if key not in seen:
                seen.add(key)
                dependencies.append(MeasureDependency(
                    name=column,
                    type="column",
                    table=table,
                ))

        # Find measure references: [Measure Name]
        measure_refs = re.findall(r"\[([^\]]+)\]", expression)
        for ref in measure_refs:
            # Skip if it's already captured as a column reference
            if any(d.name == ref and d.type == "column" for d in dependencies):
                continue
            # If we have a list of known measures, only include those
            if all_measure_names and ref in all_measure_names:
                if ref not in seen:
                    seen.add(ref)
                    dependencies.append(MeasureDependency(
                        name=ref,
                        type="measure",
                        table="",
                    ))
            elif not all_measure_names and ref not in seen:
                # Without known measures, treat standalone bracket refs as measures
                seen.add(ref)
                dependencies.append(MeasureDependency(
                    name=ref,
                    type="measure",
                    table="",
                ))

        return dependencies

    def _categorize_measure(self, expression: str) -> str:
        """Categorize a measure based on DAX functions used."""
        expression_upper = expression.upper()

        for category, functions in self.CATEGORY_PATTERNS.items():
            if any(func in expression_upper for func in functions):
                return category

        return "General"

    def _assess_complexity(self, expression: str) -> str:
        """Assess measure complexity."""
        lines = len(expression.strip().split("\n"))
        nesting = expression.count("(")

        if lines <= 2 and nesting <= 2:
            return "simple"
        elif lines <= 8 and nesting <= 5:
            return "moderate"
        else:
            return "complex"

    async def document_measure(
        self,
        measure_name: str,
        table: str,
        expression: str,
        used_in_visuals: Optional[List[str]] = None,
        all_measure_names: Optional[Set[str]] = None,
    ) -> MeasureDocumentation:
        """
        Document a single DAX measure.

        Args:
            measure_name: Name of the measure.
            table: Table the measure belongs to.
            expression: DAX expression of the measure.
            used_in_visuals: List of visual IDs/names using this measure.
            all_measure_names: Set of all measure names for dependency resolution.

        Returns:
            MeasureDocumentation with description, dependencies, and category.
        """
        logger.info(f"Documenting measure: {measure_name}")

        # Extract dependencies
        dependencies = self._extract_dependencies(expression, all_measure_names)

        # Categorize
        category = self._categorize_measure(expression)

        # Assess complexity
        complexity = self._assess_complexity(expression)

        # Generate description using LLM
        description = await self._generate_description(measure_name, expression)

        return MeasureDocumentation(
            measure_name=measure_name,
            table=table,
            expression=expression,
            description=description,
            dependencies=dependencies,
            used_in_visuals=used_in_visuals or [],
            category=category,
            complexity=complexity,
        )

    async def _generate_description(self, measure_name: str, expression: str) -> str:
        """Generate a business description for a measure using LLM."""
        prompt = (
            f"Measure Name: {measure_name}\n"
            f"DAX Expression:\n{expression}\n\n"
            "Describe what this measure calculates in one clear sentence."
        )

        try:
            response = await self._provider.generate(
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT,
            )
            return response.strip()
        except Exception as e:
            logger.error(f"Description generation failed for {measure_name}: {e}")
            return f"Calculates {measure_name} using {self._categorize_measure(expression)} logic."

    async def document_all_measures(
        self,
        measures: List[Dict[str, Any]],
        visual_usage: Optional[Dict[str, List[str]]] = None,
    ) -> MeasureCatalog:
        """
        Document all measures in a report.

        Args:
            measures: List of measure definitions with 'name', 'table', 'expression' keys.
            visual_usage: Optional mapping of measure names to visual IDs using them.

        Returns:
            MeasureCatalog with all documented measures and category groupings.
        """
        logger.info(f"Documenting {len(measures)} measures")

        all_measure_names = {m.get("name", "") for m in measures}
        documented: List[MeasureDocumentation] = []
        categories: Dict[str, List[str]] = {}
        dependency_graph: Dict[str, List[str]] = {}

        for measure_data in measures:
            name = measure_data.get("name", "Unknown")
            table = measure_data.get("table", "")
            expression = measure_data.get("expression", "")
            visuals = (visual_usage or {}).get(name, [])

            doc = await self.document_measure(
                measure_name=name,
                table=table,
                expression=expression,
                used_in_visuals=visuals,
                all_measure_names=all_measure_names,
            )
            documented.append(doc)

            # Build category index
            if doc.category not in categories:
                categories[doc.category] = []
            categories[doc.category].append(name)

            # Build dependency graph
            measure_deps = [
                d.name for d in doc.dependencies if d.type == "measure"
            ]
            if measure_deps:
                dependency_graph[name] = measure_deps

        # Generate catalog markdown
        markdown = self._generate_catalog_markdown(documented, categories)

        result = MeasureCatalog(
            measures=documented,
            categories=categories,
            dependency_graph=dependency_graph,
            markdown=markdown,
        )

        logger.info(f"Measure catalog complete: {len(documented)} measures in {len(categories)} categories")
        return result

    def _generate_catalog_markdown(
        self,
        measures: List[MeasureDocumentation],
        categories: Dict[str, List[str]],
    ) -> str:
        """Generate markdown for the complete measure catalog."""
        sections = []
        sections.append("# Measure Catalog\n")
        sections.append(f"Total measures: {len(measures)}\n")

        # Category summary
        sections.append("## Categories\n")
        for category, measure_names in sorted(categories.items()):
            sections.append(f"- **{category}** ({len(measure_names)}): {', '.join(measure_names[:5])}")
            if len(measure_names) > 5:
                sections.append(f"  ... and {len(measure_names) - 5} more")

        # Detailed measures
        sections.append("\n## Measure Details\n")
        for m in measures:
            sections.append(f"### {m.measure_name}\n")
            sections.append(f"- **Table**: {m.table}")
            sections.append(f"- **Category**: {m.category}")
            sections.append(f"- **Complexity**: {m.complexity}")
            sections.append(f"- **Description**: {m.description}")

            if m.dependencies:
                dep_str = ", ".join(f"{d.name} ({d.type})" for d in m.dependencies[:5])
                sections.append(f"- **Dependencies**: {dep_str}")

            if m.used_in_visuals:
                sections.append(f"- **Used in**: {', '.join(m.used_in_visuals[:5])}")

            sections.append(f"\n```dax\n{m.expression}\n```\n")

        return "\n".join(sections)
