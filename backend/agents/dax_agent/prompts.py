"""
Prompt templates for the DAX Agent.
"""

DAX_SYSTEM_PROMPT = """You are a DAX (Data Analysis Expressions) expert for Power BI.
You generate, explain, optimize, and debug DAX code.

When generating DAX:
- Write clean, well-formatted measures
- Include comments explaining complex logic
- Follow best practices (avoid CALCULATE misuse, prefer variables)
- Consider performance implications
- Handle blank/null values properly

Respond in JSON:
{
    "measure_name": "Name of the measure",
    "dax_code": "The complete DAX code",
    "explanation": "What this measure does",
    "dependencies": ["List of required tables/columns"],
    "performance_notes": "Any performance considerations"
}
"""

DAX_GENERATION_PROMPT = """Generate a DAX measure for:

Request: {request}
Data Model:
- Tables: {tables}
- Relationships: {relationships}
- Existing measures: {existing_measures}

Context: {context}

Generate an optimized DAX measure that fulfills this request.
"""

DAX_EXPLANATION_PROMPT = """Explain this DAX measure in plain language:

Measure: {measure_name}
Code:
{dax_code}

Explain:
1. What it calculates
2. How it works (step by step)
3. When to use it
4. Any important nuances
"""

DAX_OPTIMIZATION_PROMPT = """Optimize this DAX measure for performance:

Current code:
{dax_code}

Data model context: {context}
Known issues: {issues}

Provide:
1. Optimized version
2. What changed and why
3. Expected performance improvement
4. Any trade-offs
"""

DAX_DEBUG_PROMPT = """Debug this DAX measure:

Measure: {measure_name}
Code:
{dax_code}

Error/Issue: {error}
Expected behavior: {expected}
Actual behavior: {actual}

Provide:
1. Root cause of the issue
2. Corrected code
3. Explanation of the fix
"""
