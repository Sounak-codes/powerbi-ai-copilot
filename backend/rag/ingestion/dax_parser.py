"""
DAX parser for ingesting DAX measures into RAG.

Extracts and documents DAX measures, their dependencies,
and structure for retrieval-augmented generation.
"""
from typing import Dict, Any, List, Optional
import re
from config import get_logger

logger = get_logger(__name__)


class DAXParser:
    """
    Parse DAX measures into structured documents for RAG.

    Extracts measure logic, dependencies, and creates
    searchable documentation for each measure.
    """

    # Common DAX functions for categorization
    AGGREGATION_FUNCTIONS = {"SUM", "AVERAGE", "COUNT", "COUNTROWS", "MIN", "MAX", "DISTINCTCOUNT"}
    TIME_FUNCTIONS = {"DATEADD", "DATESYTD", "SAMEPERIODLASTYEAR", "TOTALYTD", "PARALLELPERIOD"}
    FILTER_FUNCTIONS = {"CALCULATE", "FILTER", "ALL", "ALLEXCEPT", "KEEPFILTERS", "REMOVEFILTERS"}
    TABLE_FUNCTIONS = {"SUMMARIZE", "ADDCOLUMNS", "SELECTCOLUMNS", "CROSSJOIN", "UNION"}

    def parse_measures(
        self, measures: List[Dict[str, Any]], report_id: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Parse a list of DAX measures into indexable documents.

        Args:
            measures: List of dicts with "name", "expression", "table", etc.
            report_id: Associated report ID.

        Returns:
            List of documents for RAG indexing.
        """
        documents = []

        for measure in measures:
            if not isinstance(measure, dict):
                continue

            doc = self._parse_single_measure(measure, report_id)
            if doc:
                documents.append(doc)

        logger.info(f"Parsed {len(documents)} DAX measures")
        return documents

    def _parse_single_measure(
        self, measure: Dict[str, Any], report_id: str
    ) -> Optional[Dict[str, Any]]:
        """Parse a single DAX measure."""
        name = measure.get("name", "")
        expression = measure.get("expression", "")
        table = measure.get("table", "")
        description = measure.get("description", "")

        if not name or not expression:
            return None

        # Analyze the DAX
        dependencies = self._extract_dependencies(expression)
        functions_used = self._extract_functions(expression)
        category = self._categorize_measure(functions_used)

        # Build rich text document
        text = f"DAX Measure: {name}\n"
        text += f"Table: {table}\n" if table else ""
        text += f"Category: {category}\n"
        text += f"Expression:\n{expression}\n"

        if description:
            text += f"Description: {description}\n"

        if dependencies:
            text += f"Dependencies: {', '.join(dependencies)}\n"

        if functions_used:
            text += f"Functions used: {', '.join(functions_used)}\n"

        return {
            "id": f"{report_id}_measure_{name}".replace(" ", "_"),
            "text": text,
            "metadata": {
                "source_type": "dax_measure",
                "report_id": report_id,
                "measure_name": name,
                "table": table,
                "category": category,
                "functions": functions_used,
                "dependencies": dependencies,
            },
        }

    def _extract_dependencies(self, expression: str) -> List[str]:
        """Extract table/column references from DAX expression."""
        deps = set()

        # Match Table[Column] pattern
        table_col_pattern = r"(\w+)\[(\w+)\]"
        matches = re.findall(table_col_pattern, expression)
        for table, col in matches:
            deps.add(f"{table}[{col}]")

        # Match [MeasureName] references
        measure_refs = re.findall(r"\[(\w+)\]", expression)
        for ref in measure_refs:
            if not any(ref in tc for tc in deps):
                deps.add(f"[{ref}]")

        return sorted(deps)

    def _extract_functions(self, expression: str) -> List[str]:
        """Extract DAX function names from expression."""
        # Match function calls: FUNCTION_NAME(
        pattern = r"\b([A-Z][A-Z0-9_.]+)\s*\("
        matches = re.findall(pattern, expression.upper())
        return sorted(set(matches))

    def _categorize_measure(self, functions: List[str]) -> str:
        """Categorize measure based on functions used."""
        func_set = set(functions)

        if func_set & self.TIME_FUNCTIONS:
            return "time_intelligence"
        if func_set & self.FILTER_FUNCTIONS:
            if func_set & self.AGGREGATION_FUNCTIONS:
                return "filtered_aggregation"
            return "filter_logic"
        if func_set & self.AGGREGATION_FUNCTIONS:
            return "aggregation"
        if func_set & self.TABLE_FUNCTIONS:
            return "table_manipulation"
        return "general"
