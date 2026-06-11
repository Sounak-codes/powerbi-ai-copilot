"""
DAX code explainer.

Provides step-by-step explanations of DAX expressions and
individual DAX function documentation using LLM.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from config import get_logger
from llm.providers.provider_factory import ProviderFactory

logger = get_logger(__name__)


# Reference for common DAX functions with brief descriptions
DAX_FUNCTION_REFERENCE: Dict[str, Dict[str, str]] = {
    "CALCULATE": {
        "category": "Filter",
        "description": "Evaluates an expression in a modified filter context.",
        "syntax": "CALCULATE(<expression>, <filter1>, <filter2>, ...)",
    },
    "SUMX": {
        "category": "Iterator",
        "description": "Iterates over a table and sums the expression evaluated for each row.",
        "syntax": "SUMX(<table>, <expression>)",
    },
    "DIVIDE": {
        "category": "Math",
        "description": "Safe division that returns alternate result on division by zero.",
        "syntax": "DIVIDE(<numerator>, <denominator>, [<alternate_result>])",
    },
    "FILTER": {
        "category": "Filter",
        "description": "Returns a filtered table based on a Boolean expression.",
        "syntax": "FILTER(<table>, <filter_expression>)",
    },
    "ALL": {
        "category": "Filter",
        "description": "Removes all filters from a table or columns.",
        "syntax": "ALL(<table_or_column>, [<column1>], ...)",
    },
    "TOTALYTD": {
        "category": "Time Intelligence",
        "description": "Evaluates year-to-date value of an expression.",
        "syntax": "TOTALYTD(<expression>, <dates>, [<filter>], [<year_end_date>])",
    },
    "SAMEPERIODLASTYEAR": {
        "category": "Time Intelligence",
        "description": "Returns a set of dates shifted one year back.",
        "syntax": "SAMEPERIODLASTYEAR(<dates>)",
    },
    "DATEADD": {
        "category": "Time Intelligence",
        "description": "Returns a date shifted by a specified interval.",
        "syntax": "DATEADD(<dates>, <number_of_intervals>, <interval>)",
    },
    "RANKX": {
        "category": "Statistical",
        "description": "Returns the rank of an expression in a table.",
        "syntax": "RANKX(<table>, <expression>, [<value>], [<order>], [<ties>])",
    },
    "SWITCH": {
        "category": "Logical",
        "description": "Evaluates an expression against a list of values and returns one of multiple results.",
        "syntax": "SWITCH(<expression>, <value1>, <result1>, ..., [<else>])",
    },
    "VAR": {
        "category": "Syntax",
        "description": "Defines a variable that stores the result of an expression.",
        "syntax": "VAR <name> = <expression> RETURN <result_expression>",
    },
    "AVERAGEX": {
        "category": "Iterator",
        "description": "Iterates over a table and averages the expression evaluated for each row.",
        "syntax": "AVERAGEX(<table>, <expression>)",
    },
    "COUNTROWS": {
        "category": "Aggregation",
        "description": "Counts the number of rows in a table.",
        "syntax": "COUNTROWS(<table>)",
    },
    "DISTINCTCOUNT": {
        "category": "Aggregation",
        "description": "Counts distinct values in a column.",
        "syntax": "DISTINCTCOUNT(<column>)",
    },
    "RELATED": {
        "category": "Relationship",
        "description": "Returns a related value from another table using an existing relationship.",
        "syntax": "RELATED(<column>)",
    },
}


@dataclass
class ExplanationStep:
    """A single step in a DAX explanation."""

    step_number: int
    component: str
    explanation: str
    context: str = ""


@dataclass
class DAXExplanation:
    """Complete explanation of a DAX expression."""

    original_code: str
    summary: str
    steps: List[ExplanationStep] = field(default_factory=list)
    functions_used: List[str] = field(default_factory=list)
    complexity_level: str = "simple"  # simple, moderate, complex
    filter_context_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_code": self.original_code,
            "summary": self.summary,
            "steps": [
                {
                    "step": s.step_number,
                    "component": s.component,
                    "explanation": s.explanation,
                    "context": s.context,
                }
                for s in self.steps
            ],
            "functions_used": self.functions_used,
            "complexity_level": self.complexity_level,
            "filter_context_notes": self.filter_context_notes,
        }


@dataclass
class FunctionExplanation:
    """Explanation of a single DAX function."""

    function_name: str
    category: str
    description: str
    syntax: str
    detailed_explanation: str
    examples: List[str] = field(default_factory=list)
    common_pitfalls: List[str] = field(default_factory=list)
    related_functions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "function_name": self.function_name,
            "category": self.category,
            "description": self.description,
            "syntax": self.syntax,
            "detailed_explanation": self.detailed_explanation,
            "examples": self.examples,
            "common_pitfalls": self.common_pitfalls,
            "related_functions": self.related_functions,
        }


class DAXExplainer:
    """
    Explains DAX expressions step by step using LLM.

    Breaks down complex DAX code into understandable components,
    explains evaluation context, and identifies functions used.
    """

    EXPLAIN_SYSTEM_PROMPT = (
        "You are a DAX expert educator. Explain DAX code step by step in a way "
        "that's clear for business analysts and intermediate DAX users.\n\n"
        "For each explanation, provide:\n"
        "1. SUMMARY: One-sentence summary of what the measure does\n"
        "2. COMPLEXITY: simple, moderate, or complex\n"
        "3. STEPS: Numbered steps breaking down the logic\n"
        "   Format each step as: STEP N | <component> | <explanation>\n"
        "4. FILTER_CONTEXT: How this measure interacts with filter context\n"
        "5. FUNCTIONS: Comma-separated list of DAX functions used\n"
    )

    FUNCTION_SYSTEM_PROMPT = (
        "You are a DAX function reference expert. Provide detailed explanations "
        "of DAX functions including usage patterns, examples, and common pitfalls.\n\n"
        "Format your response as:\n"
        "EXPLANATION: <detailed explanation>\n"
        "EXAMPLES:\n- <example 1>\n- <example 2>\n"
        "PITFALLS:\n- <pitfall 1>\n- <pitfall 2>\n"
        "RELATED: <comma-separated related functions>\n"
    )

    def __init__(self):
        self._provider = ProviderFactory.get_default_provider()

    def _extract_functions(self, dax_code: str) -> List[str]:
        """Extract DAX function names from code."""
        found = []
        code_upper = dax_code.upper()
        for func_name in DAX_FUNCTION_REFERENCE:
            if func_name in code_upper:
                found.append(func_name)
        return found

    def _assess_complexity(self, dax_code: str) -> str:
        """Assess the complexity level of DAX code."""
        functions = self._extract_functions(dax_code)
        lines = len(dax_code.strip().split("\n"))
        nested_count = dax_code.count("(") - dax_code.count(")")

        if lines <= 3 and len(functions) <= 2:
            return "simple"
        elif lines <= 10 and len(functions) <= 5:
            return "moderate"
        else:
            return "complex"

    async def explain(
        self,
        dax_code: str,
        audience: str = "intermediate",
    ) -> DAXExplanation:
        """
        Explain a DAX expression step by step.

        Args:
            dax_code: The DAX code to explain.
            audience: Target audience level (beginner, intermediate, advanced).

        Returns:
            DAXExplanation with structured breakdown.
        """
        logger.info(f"Explaining DAX code ({len(dax_code)} chars)")

        functions_used = self._extract_functions(dax_code)
        complexity = self._assess_complexity(dax_code)

        prompt = (
            f"Explain the following DAX code for a {audience} audience:\n\n"
            f"```dax\n{dax_code}\n```\n\n"
            f"Functions detected: {', '.join(functions_used)}\n"
            f"Complexity: {complexity}"
        )

        try:
            response = await self._provider.generate(
                prompt=prompt,
                system_prompt=self.EXPLAIN_SYSTEM_PROMPT,
            )

            result = self._parse_explanation(response, dax_code, functions_used, complexity)
            logger.info(f"Explanation generated: {complexity} complexity, {len(result.steps)} steps")
            return result

        except Exception as e:
            logger.error(f"DAX explanation failed: {e}")
            return DAXExplanation(
                original_code=dax_code,
                summary=f"Explanation failed: {str(e)}",
                functions_used=functions_used,
                complexity_level=complexity,
            )

    def _parse_explanation(
        self,
        response: str,
        dax_code: str,
        functions_used: List[str],
        complexity: str,
    ) -> DAXExplanation:
        """Parse LLM response into structured explanation."""
        summary = ""
        steps: List[ExplanationStep] = []
        filter_context = ""
        parsed_complexity = complexity

        lines = response.strip().split("\n")
        current_section = None

        for line in lines:
            stripped = line.strip()

            if stripped.startswith("SUMMARY:"):
                summary = stripped.replace("SUMMARY:", "").strip()
                current_section = "summary"
            elif stripped.startswith("COMPLEXITY:"):
                parsed_complexity = stripped.replace("COMPLEXITY:", "").strip()
                current_section = "complexity"
            elif stripped.startswith("STEP") and "|" in stripped:
                parts = stripped.split("|")
                if len(parts) >= 3:
                    step_num = len(steps) + 1
                    component = parts[1].strip()
                    explanation = parts[2].strip()
                    steps.append(ExplanationStep(
                        step_number=step_num,
                        component=component,
                        explanation=explanation,
                    ))
                current_section = "steps"
            elif stripped.startswith("FILTER_CONTEXT:"):
                filter_context = stripped.replace("FILTER_CONTEXT:", "").strip()
                current_section = "filter_context"
            elif stripped.startswith("FUNCTIONS:"):
                current_section = "functions"
            elif current_section == "filter_context" and stripped:
                filter_context += " " + stripped

        # Fallback if parsing produced no summary
        if not summary:
            summary = response.split("\n")[0][:200] if response else "No explanation available."

        return DAXExplanation(
            original_code=dax_code,
            summary=summary,
            steps=steps,
            functions_used=functions_used,
            complexity_level=parsed_complexity if parsed_complexity in ("simple", "moderate", "complex") else complexity,
            filter_context_notes=filter_context,
        )

    async def explain_function(
        self,
        function_name: str,
    ) -> FunctionExplanation:
        """
        Explain a single DAX function in detail.

        Args:
            function_name: The DAX function name (e.g., 'CALCULATE', 'SUMX').

        Returns:
            FunctionExplanation with detailed information.
        """
        func_upper = function_name.upper()
        logger.info(f"Explaining DAX function: {func_upper}")

        # Start with known reference data
        ref = DAX_FUNCTION_REFERENCE.get(func_upper, {})
        category = ref.get("category", "Unknown")
        description = ref.get("description", "")
        syntax = ref.get("syntax", f"{func_upper}(...)")

        prompt = (
            f"Explain the DAX function {func_upper} in detail.\n"
            f"Category: {category}\n"
            f"Syntax: {syntax}\n"
            f"Brief: {description}\n\n"
            "Provide a thorough explanation with practical examples and common mistakes."
        )

        try:
            response = await self._provider.generate(
                prompt=prompt,
                system_prompt=self.FUNCTION_SYSTEM_PROMPT,
            )

            return self._parse_function_explanation(
                response, func_upper, category, description, syntax
            )

        except Exception as e:
            logger.error(f"Function explanation failed: {e}")
            return FunctionExplanation(
                function_name=func_upper,
                category=category,
                description=description,
                syntax=syntax,
                detailed_explanation=f"Explanation unavailable: {str(e)}",
            )

    def _parse_function_explanation(
        self,
        response: str,
        function_name: str,
        category: str,
        description: str,
        syntax: str,
    ) -> FunctionExplanation:
        """Parse LLM response into function explanation."""
        detailed = ""
        examples: List[str] = []
        pitfalls: List[str] = []
        related: List[str] = []

        lines = response.strip().split("\n")
        current_section = None

        for line in lines:
            stripped = line.strip()

            if stripped.startswith("EXPLANATION:"):
                detailed = stripped.replace("EXPLANATION:", "").strip()
                current_section = "explanation"
            elif stripped.startswith("EXAMPLES:"):
                current_section = "examples"
            elif stripped.startswith("PITFALLS:"):
                current_section = "pitfalls"
            elif stripped.startswith("RELATED:"):
                related_str = stripped.replace("RELATED:", "").strip()
                related = [r.strip() for r in related_str.split(",") if r.strip()]
                current_section = "related"
            elif current_section == "explanation" and stripped:
                detailed += " " + stripped
            elif current_section == "examples" and stripped.startswith("-"):
                examples.append(stripped.lstrip("- "))
            elif current_section == "pitfalls" and stripped.startswith("-"):
                pitfalls.append(stripped.lstrip("- "))

        if not detailed:
            detailed = response.strip()

        return FunctionExplanation(
            function_name=function_name,
            category=category,
            description=description,
            syntax=syntax,
            detailed_explanation=detailed,
            examples=examples,
            common_pitfalls=pitfalls,
            related_functions=related,
        )

    def list_known_functions(self) -> List[Dict[str, str]]:
        """Return list of known DAX functions with categories."""
        return [
            {"name": name, "category": info["category"], "description": info["description"]}
            for name, info in DAX_FUNCTION_REFERENCE.items()
        ]
