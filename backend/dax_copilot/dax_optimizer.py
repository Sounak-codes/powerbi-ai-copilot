"""
DAX performance optimizer.

Analyzes DAX expressions for performance issues, detects common
anti-patterns, and suggests optimizations using LLM assistance.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import re

from config import get_logger
from llm.providers.provider_factory import ProviderFactory

logger = get_logger(__name__)


@dataclass
class AntiPattern:
    """A detected anti-pattern in DAX code."""

    name: str
    description: str
    severity: str  # "high", "medium", "low"
    line_hint: Optional[str] = None
    suggestion: str = ""


@dataclass
class OptimizationResult:
    """Result of DAX optimization analysis."""

    original_code: str
    optimized_code: str
    anti_patterns: List[AntiPattern] = field(default_factory=list)
    improvements: List[str] = field(default_factory=list)
    performance_score: float = 0.0  # 0-1, higher is better
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_code": self.original_code,
            "optimized_code": self.optimized_code,
            "anti_patterns": [
                {
                    "name": ap.name,
                    "description": ap.description,
                    "severity": ap.severity,
                    "line_hint": ap.line_hint,
                    "suggestion": ap.suggestion,
                }
                for ap in self.anti_patterns
            ],
            "improvements": self.improvements,
            "performance_score": round(self.performance_score, 2),
            "explanation": self.explanation,
        }


# Anti-pattern detection rules
ANTI_PATTERN_RULES: List[Dict[str, Any]] = [
    {
        "name": "nested_calculate",
        "description": "Nested CALCULATE calls can cause unexpected filter context interactions and hurt performance.",
        "pattern": r"CALCULATE\s*\([^)]*CALCULATE\s*\(",
        "severity": "high",
        "suggestion": "Flatten nested CALCULATE by combining filters, or use variables to separate contexts.",
    },
    {
        "name": "unnecessary_filter_all",
        "description": "FILTER(ALL(...)) used where a direct CALCULATE filter argument would suffice.",
        "pattern": r"FILTER\s*\(\s*ALL\s*\(",
        "severity": "medium",
        "suggestion": "Replace FILTER(ALL(Table), condition) with a direct filter in CALCULATE when possible.",
    },
    {
        "name": "iterator_instead_of_aggregator",
        "description": "Using SUMX/AVERAGEX where SUM/AVERAGE would work (no row context needed).",
        "pattern": r"SUMX\s*\(\s*['\w]+\s*,\s*['\w]+\s*\[[^\]]+\]\s*\)",
        "severity": "medium",
        "suggestion": "Use SUM(Table[Column]) instead of SUMX(Table, Table[Column]) for simple column aggregation.",
    },
    {
        "name": "filter_with_large_table",
        "description": "FILTER iterating over an entire table without KEEPFILTERS or limiting scope.",
        "pattern": r"FILTER\s*\(\s*['\w]+\s*,",
        "severity": "low",
        "suggestion": "Consider using CALCULATE with direct filter arguments instead of FILTER on large tables.",
    },
    {
        "name": "missing_variables",
        "description": "Repeated sub-expressions without VAR/RETURN can cause redundant evaluation.",
        "pattern": None,  # Detected via logic, not regex
        "severity": "low",
        "suggestion": "Use VAR to store intermediate results that are referenced multiple times.",
    },
    {
        "name": "division_without_divide",
        "description": "Using / operator instead of DIVIDE() risks division-by-zero errors.",
        "pattern": r"(?<![A-Z])/(?!\*)",
        "severity": "low",
        "suggestion": "Use DIVIDE(numerator, denominator, 0) for safe division handling.",
    },
    {
        "name": "countrows_filter_instead_of_calculate",
        "description": "COUNTROWS(FILTER(...)) can often be replaced with CALCULATE(COUNTROWS(...)).",
        "pattern": r"COUNTROWS\s*\(\s*FILTER\s*\(",
        "severity": "medium",
        "suggestion": "Use CALCULATE(COUNTROWS(Table), filter_condition) for better performance.",
    },
    {
        "name": "addcolumns_in_measure",
        "description": "ADDCOLUMNS in a measure context creates a row-by-row materialization.",
        "pattern": r"ADDCOLUMNS\s*\(",
        "severity": "medium",
        "suggestion": "Consider if SUMMARIZE or SUMMARIZECOLUMNS with CALCULATE can achieve the same result more efficiently.",
    },
]


class DAXOptimizer:
    """
    Analyzes DAX expressions for performance issues and suggests improvements.

    Combines rule-based pattern detection for known anti-patterns with
    LLM-assisted optimization for complex restructuring.
    """

    SYSTEM_PROMPT = (
        "You are a DAX performance optimization expert. Analyze the given DAX code "
        "and provide an optimized version.\n\n"
        "Consider these optimization strategies:\n"
        "1. Replace iterators (SUMX, AVERAGEX) with aggregators (SUM, AVERAGE) when possible\n"
        "2. Flatten nested CALCULATE by combining or reordering filters\n"
        "3. Use VAR/RETURN to avoid repeated calculations\n"
        "4. Replace FILTER(ALL(...)) with direct filter arguments in CALCULATE\n"
        "5. Use DIVIDE() for safe division\n"
        "6. Minimize row-context transitions\n"
        "7. Prefer KEEPFILTERS over FILTER when appropriate\n\n"
        "Return your response in this format:\n"
        "OPTIMIZED_CODE:\n<optimized DAX code>\n"
        "IMPROVEMENTS:\n- <improvement 1>\n- <improvement 2>\n"
        "EXPLANATION: <brief explanation of changes>\n"
        "SCORE: <performance score 0.0-1.0>\n"
    )

    def __init__(self):
        self._provider = ProviderFactory.get_default_provider()

    def detect_anti_patterns(self, dax_code: str) -> List[AntiPattern]:
        """
        Detect common DAX anti-patterns using rule-based analysis.

        Args:
            dax_code: The DAX code to analyze.

        Returns:
            List of detected anti-patterns.
        """
        detected: List[AntiPattern] = []
        code_upper = dax_code.upper()

        for rule in ANTI_PATTERN_RULES:
            pattern = rule.get("pattern")

            if pattern is None:
                # Special logic-based detection
                if rule["name"] == "missing_variables":
                    if self._detect_repeated_expressions(dax_code):
                        detected.append(AntiPattern(
                            name=rule["name"],
                            description=rule["description"],
                            severity=rule["severity"],
                            suggestion=rule["suggestion"],
                        ))
                continue

            matches = re.findall(pattern, code_upper, re.IGNORECASE | re.DOTALL)
            if matches:
                line_hint = matches[0][:50] if matches else None
                detected.append(AntiPattern(
                    name=rule["name"],
                    description=rule["description"],
                    severity=rule["severity"],
                    line_hint=line_hint,
                    suggestion=rule["suggestion"],
                ))

        return detected

    def _detect_repeated_expressions(self, dax_code: str) -> bool:
        """Check if there are repeated sub-expressions without VAR."""
        if "VAR" in dax_code.upper():
            return False

        # Look for repeated measure references or function calls
        refs = re.findall(r'\[[\w\s]+\]', dax_code)
        if len(refs) != len(set(refs)) and len(refs) > 2:
            return True

        return False

    def _calculate_base_score(self, anti_patterns: List[AntiPattern]) -> float:
        """Calculate a base performance score from detected anti-patterns."""
        score = 1.0
        severity_penalties = {"high": 0.25, "medium": 0.15, "low": 0.05}

        for ap in anti_patterns:
            score -= severity_penalties.get(ap.severity, 0.05)

        return max(0.0, min(1.0, score))

    async def optimize(
        self,
        dax_code: str,
        context: Optional[str] = None,
    ) -> OptimizationResult:
        """
        Analyze DAX code for performance issues and suggest optimizations.

        Args:
            dax_code: The DAX code to optimize.
            context: Optional context about the data model or intended use.

        Returns:
            OptimizationResult with optimized code and analysis.
        """
        logger.info(f"Optimizing DAX code ({len(dax_code)} chars)")

        # Rule-based detection first
        anti_patterns = self.detect_anti_patterns(dax_code)
        base_score = self._calculate_base_score(anti_patterns)

        # Build LLM prompt
        prompt_parts = [f"Optimize the following DAX code:\n\n```dax\n{dax_code}\n```"]

        if anti_patterns:
            ap_summary = "\n".join(
                f"- {ap.name}: {ap.description}" for ap in anti_patterns
            )
            prompt_parts.append(f"\nDetected anti-patterns:\n{ap_summary}")

        if context:
            prompt_parts.append(f"\nContext: {context}")

        prompt = "\n".join(prompt_parts)

        try:
            response = await self._provider.generate(
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT,
            )

            result = self._parse_response(response, dax_code, anti_patterns, base_score)
            logger.info(
                f"Optimization complete: {len(anti_patterns)} anti-patterns, "
                f"score {result.performance_score:.2f}"
            )
            return result

        except Exception as e:
            logger.error(f"DAX optimization failed: {e}")
            return OptimizationResult(
                original_code=dax_code,
                optimized_code=dax_code,
                anti_patterns=anti_patterns,
                performance_score=base_score,
                explanation=f"LLM optimization failed: {str(e)}. Rule-based analysis only.",
            )

    def _parse_response(
        self,
        response: str,
        original_code: str,
        anti_patterns: List[AntiPattern],
        base_score: float,
    ) -> OptimizationResult:
        """Parse LLM optimization response."""
        optimized_code = ""
        improvements: List[str] = []
        explanation = ""
        score = base_score

        lines = response.strip().split("\n")
        current_section = None
        code_lines: List[str] = []

        for line in lines:
            stripped = line.strip()

            if stripped.startswith("OPTIMIZED_CODE:"):
                current_section = "code"
            elif stripped.startswith("IMPROVEMENTS:"):
                current_section = "improvements"
            elif stripped.startswith("EXPLANATION:"):
                explanation = stripped.replace("EXPLANATION:", "").strip()
                current_section = "explanation"
            elif stripped.startswith("SCORE:"):
                try:
                    score = float(stripped.replace("SCORE:", "").strip())
                    score = max(0.0, min(1.0, score))
                except ValueError:
                    pass
                current_section = "score"
            elif current_section == "code":
                if stripped != "```" and stripped != "```dax":
                    code_lines.append(line)
            elif current_section == "improvements" and stripped.startswith("-"):
                improvements.append(stripped.lstrip("- "))
            elif current_section == "explanation" and stripped:
                explanation += " " + stripped

        optimized_code = "\n".join(code_lines).strip()

        # Fallback: if no optimized code parsed, keep original
        if not optimized_code:
            optimized_code = original_code

        return OptimizationResult(
            original_code=original_code,
            optimized_code=optimized_code,
            anti_patterns=anti_patterns,
            improvements=improvements,
            performance_score=score,
            explanation=explanation,
        )

    def quick_check(self, dax_code: str) -> Dict[str, Any]:
        """
        Quick synchronous check for anti-patterns without LLM call.

        Args:
            dax_code: The DAX code to check.

        Returns:
            Dict with anti-patterns and base score.
        """
        anti_patterns = self.detect_anti_patterns(dax_code)
        score = self._calculate_base_score(anti_patterns)

        return {
            "anti_patterns": [
                {"name": ap.name, "severity": ap.severity, "suggestion": ap.suggestion}
                for ap in anti_patterns
            ],
            "performance_score": round(score, 2),
            "has_issues": len(anti_patterns) > 0,
        }
