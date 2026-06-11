"""
DAX debugger.

Takes broken DAX code with an error message and suggests fixes.
Includes common error pattern detection and LLM-assisted resolution.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from config import get_logger
from llm.providers.provider_factory import ProviderFactory

logger = get_logger(__name__)


# Common DAX error patterns and their typical solutions
COMMON_ERROR_PATTERNS: List[Dict[str, Any]] = [
    {
        "pattern": "a single value for column",
        "error_type": "multiple_values",
        "description": "Expression expects a single value but the column has multiple values in the current context.",
        "common_causes": [
            "Missing aggregation function (SUM, MAX, MIN, etc.)",
            "RELATED used on wrong side of relationship",
            "Filter context not narrowed to a single row",
        ],
        "solutions": [
            "Wrap the column reference in an aggregation function: SUM(Table[Column])",
            "Use CALCULATE to establish proper filter context",
            "Check if RELATED vs RELATEDTABLE is appropriate for the relationship direction",
        ],
    },
    {
        "pattern": "circular dependency",
        "error_type": "circular_dependency",
        "description": "A measure references itself directly or indirectly through other measures.",
        "common_causes": [
            "Measure A references Measure B which references Measure A",
            "Calculated column referencing a measure that depends on the same table",
        ],
        "solutions": [
            "Break the circular chain by inlining one of the dependent expressions",
            "Restructure using VAR to capture intermediate values",
            "Consider if a calculated column should be used instead of a measure",
        ],
    },
    {
        "pattern": "cannot find table",
        "error_type": "missing_table",
        "description": "Referenced table does not exist in the data model.",
        "common_causes": [
            "Table name misspelled",
            "Table was renamed or removed",
            "Missing single quotes around table names with spaces",
        ],
        "solutions": [
            "Verify table name matches exactly (case-sensitive in some contexts)",
            "Enclose table names with spaces in single quotes: 'Sales Data'",
            "Check if the table was renamed in the model",
        ],
    },
    {
        "pattern": "cannot find column",
        "error_type": "missing_column",
        "description": "Referenced column does not exist in the specified table.",
        "common_causes": [
            "Column name misspelled",
            "Column belongs to a different table",
            "Column was renamed or removed",
        ],
        "solutions": [
            "Verify column name and table reference",
            "Check if the column exists with a different name",
            "Ensure the table reference is correct: Table[Column]",
        ],
    },
    {
        "pattern": "cannot be used in this context",
        "error_type": "context_error",
        "description": "A function or expression is used in an incompatible context.",
        "common_causes": [
            "Using a measure where a column is expected",
            "Using RELATED in a measure without row context",
            "Iterator function used where scalar is expected",
        ],
        "solutions": [
            "Check if an iterator (SUMX, MAXX) is needed to create row context",
            "Verify RELATED is used within an iterator or calculated column",
            "Wrap the expression in CALCULATE if filter context manipulation is needed",
        ],
    },
    {
        "pattern": "second argument.*boolean",
        "error_type": "type_mismatch",
        "description": "CALCULATE/CALCULATETABLE filter argument must be a Boolean expression or table.",
        "common_causes": [
            "Using a column name without comparison in CALCULATE filter",
            "Missing = TRUE() for Boolean columns",
            "Passing a measure reference as a filter",
        ],
        "solutions": [
            "Add explicit comparison: Table[Column] = \"value\"",
            "Use FILTER(Table, condition) for complex filters",
            "Ensure filter arguments evaluate to TRUE/FALSE or return a table",
        ],
    },
    {
        "pattern": "not supported.*directquery",
        "error_type": "directquery_limitation",
        "description": "Function or pattern not supported in DirectQuery mode.",
        "common_causes": [
            "Using TOPN, RANKX, or complex iterators in DirectQuery",
            "Certain time intelligence functions incompatible with DirectQuery",
        ],
        "solutions": [
            "Simplify the expression to use DirectQuery-compatible functions",
            "Consider switching to Import mode for the required table",
            "Use alternative DAX patterns that push down to the data source",
        ],
    },
    {
        "pattern": "syntax error",
        "error_type": "syntax_error",
        "description": "The DAX expression has a syntax error.",
        "common_causes": [
            "Missing or extra parentheses",
            "Missing comma between arguments",
            "Incorrect string quoting (use double quotes for strings)",
        ],
        "solutions": [
            "Count opening and closing parentheses to ensure they match",
            "Check comma placement between function arguments",
            "Use double quotes for string literals, single quotes for table names",
        ],
    },
]


@dataclass
class DebugSuggestion:
    """A single debug suggestion for fixing DAX code."""

    issue: str
    explanation: str
    fix: str
    confidence: float = 0.0


@dataclass
class DAXDebugResult:
    """Result of DAX debugging analysis."""

    original_code: str
    error_message: str
    error_type: str
    root_cause: str
    suggestions: List[DebugSuggestion] = field(default_factory=list)
    fixed_code: str = ""
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_code": self.original_code,
            "error_message": self.error_message,
            "error_type": self.error_type,
            "root_cause": self.root_cause,
            "suggestions": [
                {
                    "issue": s.issue,
                    "explanation": s.explanation,
                    "fix": s.fix,
                    "confidence": round(s.confidence, 2),
                }
                for s in self.suggestions
            ],
            "fixed_code": self.fixed_code,
            "explanation": self.explanation,
        }


class DAXDebugger:
    """
    Debugs broken DAX code by analyzing error messages and suggesting fixes.

    Combines pattern matching for common errors with LLM-assisted
    diagnosis for complex issues.
    """

    SYSTEM_PROMPT = (
        "You are a DAX debugging expert. Given broken DAX code and an error message, "
        "diagnose the issue and provide a fix.\n\n"
        "Respond in this format:\n"
        "ERROR_TYPE: <type of error>\n"
        "ROOT_CAUSE: <explanation of what's wrong>\n"
        "FIXED_CODE:\n<corrected DAX code>\n"
        "EXPLANATION: <step-by-step explanation of the fix>\n"
        "SUGGESTIONS:\n"
        "- ISSUE: <issue> | FIX: <fix> | CONFIDENCE: <0.0-1.0>\n"
    )

    def __init__(self):
        self._provider = ProviderFactory.get_default_provider()

    def _match_error_pattern(self, error_message: str) -> Optional[Dict[str, Any]]:
        """Match error message against known patterns."""
        error_lower = error_message.lower()

        for pattern_info in COMMON_ERROR_PATTERNS:
            if pattern_info["pattern"] in error_lower:
                return pattern_info

        return None

    async def debug(
        self,
        dax_code: str,
        error_message: str,
        context: Optional[str] = None,
    ) -> DAXDebugResult:
        """
        Debug broken DAX code and suggest fixes.

        Args:
            dax_code: The DAX code that produces an error.
            error_message: The error message from Power BI.
            context: Optional context about the data model.

        Returns:
            DAXDebugResult with diagnosis and suggested fixes.
        """
        logger.info(f"Debugging DAX error: {error_message[:100]}")

        # Check known patterns first
        matched_pattern = self._match_error_pattern(error_message)

        # Build LLM prompt
        prompt_parts = [
            f"DAX Code with error:\n```dax\n{dax_code}\n```\n",
            f"Error Message: {error_message}",
        ]

        if matched_pattern:
            prompt_parts.append(
                f"\nKnown pattern match: {matched_pattern['error_type']}\n"
                f"Common causes: {', '.join(matched_pattern['common_causes'])}"
            )

        if context:
            prompt_parts.append(f"\nData Model Context: {context}")

        prompt = "\n".join(prompt_parts)

        try:
            response = await self._provider.generate(
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT,
            )

            result = self._parse_response(response, dax_code, error_message, matched_pattern)
            logger.info(f"Debug complete: {result.error_type} - {len(result.suggestions)} suggestions")
            return result

        except Exception as e:
            logger.error(f"DAX debugging failed: {e}")
            # Fall back to pattern-based response
            return self._build_pattern_result(dax_code, error_message, matched_pattern)

    def _parse_response(
        self,
        response: str,
        dax_code: str,
        error_message: str,
        matched_pattern: Optional[Dict[str, Any]],
    ) -> DAXDebugResult:
        """Parse LLM debug response."""
        error_type = matched_pattern["error_type"] if matched_pattern else "unknown"
        root_cause = ""
        fixed_code = ""
        explanation = ""
        suggestions: List[DebugSuggestion] = []

        lines = response.strip().split("\n")
        current_section = None
        code_lines: List[str] = []

        for line in lines:
            stripped = line.strip()

            if stripped.startswith("ERROR_TYPE:"):
                error_type = stripped.replace("ERROR_TYPE:", "").strip()
                current_section = "error_type"
            elif stripped.startswith("ROOT_CAUSE:"):
                root_cause = stripped.replace("ROOT_CAUSE:", "").strip()
                current_section = "root_cause"
            elif stripped.startswith("FIXED_CODE:"):
                current_section = "code"
            elif stripped.startswith("EXPLANATION:"):
                explanation = stripped.replace("EXPLANATION:", "").strip()
                current_section = "explanation"
            elif stripped.startswith("SUGGESTIONS:"):
                current_section = "suggestions"
            elif current_section == "code":
                if stripped != "```" and stripped != "```dax":
                    code_lines.append(line)
            elif current_section == "root_cause" and stripped and not stripped.startswith(("FIXED", "EXPLAN", "SUGGEST")):
                root_cause += " " + stripped
            elif current_section == "explanation" and stripped and not stripped.startswith(("SUGGEST",)):
                explanation += " " + stripped
            elif current_section == "suggestions" and "ISSUE:" in stripped:
                suggestion = self._parse_suggestion_line(stripped)
                if suggestion:
                    suggestions.append(suggestion)

        fixed_code = "\n".join(code_lines).strip()

        # Add pattern-based suggestions if available
        if matched_pattern and not suggestions:
            for i, solution in enumerate(matched_pattern["solutions"]):
                suggestions.append(DebugSuggestion(
                    issue=matched_pattern["common_causes"][i] if i < len(matched_pattern["common_causes"]) else "Issue",
                    explanation=matched_pattern["description"],
                    fix=solution,
                    confidence=0.7,
                ))

        return DAXDebugResult(
            original_code=dax_code,
            error_message=error_message,
            error_type=error_type,
            root_cause=root_cause or "Unable to determine root cause.",
            suggestions=suggestions,
            fixed_code=fixed_code,
            explanation=explanation,
        )

    def _parse_suggestion_line(self, line: str) -> Optional[DebugSuggestion]:
        """Parse a single suggestion line from LLM response."""
        try:
            parts = line.split("|")
            issue = ""
            fix = ""
            confidence = 0.7

            for part in parts:
                part = part.strip().lstrip("- ")
                if part.startswith("ISSUE:"):
                    issue = part.replace("ISSUE:", "").strip()
                elif part.startswith("FIX:"):
                    fix = part.replace("FIX:", "").strip()
                elif part.startswith("CONFIDENCE:"):
                    try:
                        confidence = float(part.replace("CONFIDENCE:", "").strip())
                    except ValueError:
                        pass

            if issue or fix:
                return DebugSuggestion(
                    issue=issue,
                    explanation="",
                    fix=fix,
                    confidence=confidence,
                )
        except Exception:
            pass

        return None

    def _build_pattern_result(
        self,
        dax_code: str,
        error_message: str,
        matched_pattern: Optional[Dict[str, Any]],
    ) -> DAXDebugResult:
        """Build result from pattern matching only (LLM fallback)."""
        if matched_pattern:
            suggestions = [
                DebugSuggestion(
                    issue=cause,
                    explanation=matched_pattern["description"],
                    fix=matched_pattern["solutions"][i] if i < len(matched_pattern["solutions"]) else "",
                    confidence=0.6,
                )
                for i, cause in enumerate(matched_pattern["common_causes"])
            ]

            return DAXDebugResult(
                original_code=dax_code,
                error_message=error_message,
                error_type=matched_pattern["error_type"],
                root_cause=matched_pattern["description"],
                suggestions=suggestions,
                fixed_code="",
                explanation="Based on pattern matching. LLM-assisted fix unavailable.",
            )

        return DAXDebugResult(
            original_code=dax_code,
            error_message=error_message,
            error_type="unknown",
            root_cause="Unable to determine root cause from error message.",
            suggestions=[],
            fixed_code="",
            explanation="No matching error pattern found and LLM assistance unavailable.",
        )

    def get_common_errors(self) -> List[Dict[str, Any]]:
        """Return reference list of common DAX errors and solutions."""
        return [
            {
                "error_type": p["error_type"],
                "description": p["description"],
                "common_causes": p["common_causes"],
                "solutions": p["solutions"],
            }
            for p in COMMON_ERROR_PATTERNS
        ]
