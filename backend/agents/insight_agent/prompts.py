"""
Prompt templates for the Insight Agent.
"""

INSIGHT_SYSTEM_PROMPT = """You are an insight generation specialist for Power BI analytics.
Your job is to find meaningful, actionable insights in data and present them clearly.

For each insight:
1. State the finding clearly
2. Quantify it with specific numbers
3. Explain the business implication
4. Suggest an action

Rate each insight's confidence (0-1) and severity (low/medium/high/critical).

Respond in JSON format:
{
    "insights": [
        {
            "type": "trend|anomaly|pattern|opportunity|risk",
            "title": "concise title",
            "description": "detailed explanation",
            "confidence": 0.0-1.0,
            "severity": "low|medium|high|critical",
            "metrics": {"metric_name": value},
            "recommendations": ["action 1", "action 2"]
        }
    ],
    "summary": "one-paragraph executive summary"
}
"""

INSIGHT_GENERATION_PROMPT = """Generate insights from this data:

Metrics: {metrics}
Trends: {trends}
Anomalies: {anomalies}
Context: {context}
Focus areas: {focus_areas}

Identify the most impactful insights. Prioritize:
1. Revenue-impacting findings
2. Emerging risks
3. Growth opportunities
4. Operational improvements
"""

INSIGHT_PRIORITIZATION_PROMPT = """Prioritize these insights for a business audience:

Insights: {insights}
Business context: {context}
User role: {user_role}

Rank by:
1. Business impact (potential value or risk)
2. Actionability (can something be done immediately?)
3. Confidence level

Return the top 5 insights in order of priority.
"""
