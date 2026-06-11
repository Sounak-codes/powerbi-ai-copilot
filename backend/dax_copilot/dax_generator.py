"""
DAX measure generator.

Takes a natural language request and data model context,
then uses an LLM to generate DAX code with appropriate patterns.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from config import get_logger
from llm.providers.provider_factory import ProviderFactory

logger = get_logger(__name__)


# Common DAX pattern templates for reference during generation
DAX_PATTERN_TEMPLATES: Dict[str, str] = {
    "time_intelligence_ytd": (
        "{measure_name} YTD = \n"
        "TOTALYTD(\n"
        "    [{measure_name}],\n"
        "    '{date_table}'[Date]\n"
        ")"
    ),
    "time_intelligence_mom": (
        "{measure_name} MoM % = \n"
        "VAR CurrentMonth = [{measure_name}]\n"
        "VAR PreviousMonth = CALCULATE(\n"
        "    [{measure_name}],\n"
        "    DATEADD('{date_table}'[Date], -1, MONTH)\n"
        ")\n"
        "RETURN\n"
        "    DIVIDE(CurrentMonth - PreviousMonth, PreviousMonth)"
    ),
    "time_intelligence_yoy": (
        "{measure_name} YoY % = \n"
        "VAR CurrentPeriod = [{measure_name}]\n"
        "VAR PreviousPeriod = CALCULATE(\n"
        "    [{measure_name}],\n"
        "    SAMEPERIODLASTYEAR('{date_table}'[Date])\n"
        ")\n"
        "RETURN\n"
        "    DIVIDE(CurrentPeriod - PreviousPeriod, PreviousPeriod)"
    ),
    "running_total": (
        "{measure_name} Running Total = \n"
        "CALCULATE(\n"
        "    [{measure_name}],\n"
        "    FILTER(\n"
        "        ALL('{date_table}'[Date]),\n"
        "        '{date_table}'[Date] <= MAX('{date_table}'[Date])\n"
        "    )\n"
        ")"
    ),
    "moving_average": (
        "{measure_name} {period}D MA = \n"
        "AVERAGEX(\n"
        "    DATESINPERIOD(\n"
        "        '{date_table}'[Date],\n"
        "        MAX('{date_table}'[Date]),\n"
        "        -{period},\n"
        "        DAY\n"
        "    ),\n"
        "    [{measure_name}]\n"
        ")"
    ),
    "percentage_of_total": (
        "{measure_name} % of Total = \n"
        "DIVIDE(\n"
        "    [{measure_name}],\n"
        "    CALCULATE(\n"
        "        [{measure_name}],\n"
        "        ALL('{table_name}')\n"
        "    )\n"
        ")"
    ),
    "rank": (
        "{measure_name} Rank = \n"
        "RANKX(\n"
        "    ALL('{table_name}'[{column_name}]),\n"
        "    [{measure_name}],\n"
        "    ,\n"
        "    DESC,\n"
        "    DENSE\n"
        ")"
    ),
    "conditional_aggregation": (
        "{measure_name} = \n"
        "CALCULATE(\n"
        "    {aggregation}('{table_name}'[{column_name}]),\n"
        "    '{table_name}'[{filter_column}] = \"{filter_value}\"\n"
        ")"
    ),
}


@dataclass
class DataModelContext:
    """Context about the Power BI data model for DAX generation."""

    tables: List[Dict[str, Any]] = field(default_factory=list)
    relationships: List[Dict[str, Any]] = field(default_factory=list)
    existing_measures: List[Dict[str, str]] = field(default_factory=list)
    date_table: Optional[str] = None

    def to_prompt_context(self) -> str:
        """Format data model context for LLM prompt inclusion."""
        parts = []

        if self.tables:
            parts.append("Tables and Columns:")
            for table in self.tables:
                name = table.get("name", "Unknown")
                columns = table.get("columns", [])
                col_str = ", ".join(columns) if columns else "no columns listed"
                parts.append(f"  - {name}: [{col_str}]")

        if self.relationships:
            parts.append("\nRelationships:")
            for rel in self.relationships:
                from_t = rel.get("from_table", "?")
                from_c = rel.get("from_column", "?")
                to_t = rel.get("to_table", "?")
                to_c = rel.get("to_column", "?")
                parts.append(f"  - {from_t}[{from_c}] -> {to_t}[{to_c}]")

        if self.existing_measures:
            parts.append("\nExisting Measures:")
            for m in self.existing_measures[:20]:  # Limit to avoid prompt bloat
                parts.append(f"  - {m.get('name', '?')}: {m.get('expression', '?')[:80]}")

        if self.date_table:
            parts.append(f"\nDate Table: {self.date_table}")

        return "\n".join(parts)


@dataclass
class DAXGenerationResult:
    """Result of DAX code generation."""

    dax_code: str
    measure_name: str
    explanation: str
    pattern_used: Optional[str] = None
    confidence: float = 0.0
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dax_code": self.dax_code,
            "measure_name": self.measure_name,
            "explanation": self.explanation,
            "pattern_used": self.pattern_used,
            "confidence": self.confidence,
            "suggestions": self.suggestions,
        }


class DAXGenerator:
    """
    Generates DAX measures from natural language requests.

    Uses an LLM with data model context and common DAX pattern
    templates to produce accurate and performant DAX code.
    """

    SYSTEM_PROMPT = (
        "You are a DAX (Data Analysis Expressions) expert for Power BI. "
        "Generate correct, performant DAX measures based on user requests. "
        "Always use best practices:\n"
        "- Use variables (VAR/RETURN) for readability and performance\n"
        "- Prefer DIVIDE() over division operator for safe division\n"
        "- Use CALCULATE with proper filter context manipulation\n"
        "- Prefer SUMX/AVERAGEX only when row-level computation is needed\n"
        "- Use time intelligence functions with a proper date table\n\n"
        "Return your response in this format:\n"
        "MEASURE_NAME: <name>\n"
        "DAX_CODE:\n<the DAX code>\n"
        "EXPLANATION: <brief explanation of what the measure does>\n"
        "PATTERN: <pattern name if applicable, otherwise 'custom'>\n"
    )

    def __init__(self):
        self._provider = ProviderFactory.get_default_provider()

    def _detect_pattern(self, request: str) -> Optional[str]:
        """Detect if the request matches a known DAX pattern."""
        request_lower = request.lower()

        pattern_keywords = {
            "time_intelligence_ytd": ["year to date", "ytd", "cumulative year"],
            "time_intelligence_mom": ["month over month", "mom", "monthly change"],
            "time_intelligence_yoy": ["year over year", "yoy", "annual change"],
            "running_total": ["running total", "cumulative", "running sum"],
            "moving_average": ["moving average", "rolling average", "ma "],
            "percentage_of_total": ["percent of total", "% of total", "share of"],
            "rank": ["rank", "top n", "ranking"],
            "conditional_aggregation": ["sum where", "count where", "total for"],
        }

        for pattern, keywords in pattern_keywords.items():
            if any(kw in request_lower for kw in keywords):
                return pattern

        return None

    async def generate(
        self,
        request: str,
        data_model: Optional[DataModelContext] = None,
        additional_context: Optional[str] = None,
    ) -> DAXGenerationResult:
        """
        Generate a DAX measure from a natural language request.

        Args:
            request: Natural language description of the desired measure.
            data_model: Context about the data model (tables, relationships).
            additional_context: Any extra context (e.g., business rules).

        Returns:
            DAXGenerationResult containing the generated code and metadata.
        """
        logger.info(f"Generating DAX for request: {request[:100]}")

        detected_pattern = self._detect_pattern(request)

        # Build prompt
        prompt_parts = [f"User Request: {request}"]

        if data_model:
            prompt_parts.append(f"\nData Model:\n{data_model.to_prompt_context()}")

        if detected_pattern:
            template = DAX_PATTERN_TEMPLATES.get(detected_pattern, "")
            prompt_parts.append(
                f"\nRelevant Pattern Template ({detected_pattern}):\n{template}"
            )

        if additional_context:
            prompt_parts.append(f"\nAdditional Context: {additional_context}")

        user_prompt = "\n".join(prompt_parts)

        try:
            response = await self._provider.generate(
                prompt=user_prompt,
                system_prompt=self.SYSTEM_PROMPT,
            )

            result = self._parse_response(response, detected_pattern)
            logger.info(f"DAX generated: {result.measure_name}")
            return result

        except Exception as e:
            logger.error(f"DAX generation failed: {e}")
            return DAXGenerationResult(
                dax_code="",
                measure_name="",
                explanation=f"Generation failed: {str(e)}",
                confidence=0.0,
            )

    def _parse_response(
        self, response: str, pattern: Optional[str]
    ) -> DAXGenerationResult:
        """Parse LLM response into structured DAX result."""
        measure_name = ""
        dax_code = ""
        explanation = ""
        detected_pattern = pattern or "custom"

        lines = response.strip().split("\n")
        current_section = None
        dax_lines: List[str] = []

        for line in lines:
            if line.startswith("MEASURE_NAME:"):
                measure_name = line.replace("MEASURE_NAME:", "").strip()
                current_section = "name"
            elif line.startswith("DAX_CODE:"):
                current_section = "dax"
            elif line.startswith("EXPLANATION:"):
                explanation = line.replace("EXPLANATION:", "").strip()
                current_section = "explanation"
            elif line.startswith("PATTERN:"):
                p = line.replace("PATTERN:", "").strip()
                if p and p != "custom":
                    detected_pattern = p
                current_section = "pattern"
            elif current_section == "dax":
                dax_lines.append(line)
            elif current_section == "explanation":
                explanation += " " + line.strip()

        dax_code = "\n".join(dax_lines).strip()

        # Fallback: if parsing failed, use the entire response as DAX
        if not dax_code:
            dax_code = response.strip()
            explanation = "Auto-generated DAX measure."

        confidence = 0.85 if pattern else 0.70

        return DAXGenerationResult(
            dax_code=dax_code,
            measure_name=measure_name or "Generated Measure",
            explanation=explanation,
            pattern_used=detected_pattern,
            confidence=confidence,
            suggestions=self._generate_suggestions(dax_code),
        )

    def _generate_suggestions(self, dax_code: str) -> List[str]:
        """Generate improvement suggestions for the DAX code."""
        suggestions = []
        code_upper = dax_code.upper()

        if "/" in dax_code and "DIVIDE(" not in code_upper:
            suggestions.append(
                "Consider using DIVIDE() instead of / for safe division."
            )

        if "VAR" not in code_upper and len(dax_code.split("\n")) > 3:
            suggestions.append(
                "Consider using VAR/RETURN for complex expressions to improve readability."
            )

        if "FILTER(" in code_upper and "ALL(" in code_upper:
            suggestions.append(
                "Check if FILTER(ALL(...)) can be replaced with a simpler CALCULATE filter."
            )

        return suggestions

    def get_pattern_template(
        self, pattern_name: str, **kwargs: str
    ) -> Optional[str]:
        """
        Get a DAX pattern template with placeholders filled.

        Args:
            pattern_name: Name of the pattern template.
            **kwargs: Values to fill in the template placeholders.

        Returns:
            Formatted template string or None if pattern not found.
        """
        template = DAX_PATTERN_TEMPLATES.get(pattern_name)
        if template and kwargs:
            try:
                return template.format(**kwargs)
            except KeyError:
                return template
        return template

    def list_patterns(self) -> List[str]:
        """Return list of available DAX pattern names."""
        return list(DAX_PATTERN_TEMPLATES.keys())
