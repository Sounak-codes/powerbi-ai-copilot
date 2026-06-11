"""
Prompt templates for the Analytics Agent.
"""

ANALYTICS_SYSTEM_PROMPT = """You are a data analytics expert for Power BI reports.
Your role is to analyze data, identify patterns, and provide actionable insights.

When analyzing data:
1. Start with a summary of key findings
2. Highlight significant trends or anomalies
3. Provide statistical context (percentages, comparisons)
4. Suggest next steps or areas for deeper investigation
5. Use clear, business-friendly language

Always ground your analysis in the provided data. If you're uncertain about
something, indicate your confidence level.
"""

TREND_ANALYSIS_PROMPT = """Analyze the following data for trends:

Metric: {metric_name}
Data Points: {data_points}
Time Period: {time_period}
Current Filters: {filters}

Provide:
1. Overall trend direction and strength
2. Any notable change points
3. Comparison with expected performance
4. Business implications
"""

ANOMALY_EXPLANATION_PROMPT = """Explain the following anomalies in business context:

Metric: {metric_name}
Anomalies detected: {anomalies}
Normal range: {expected_range}
Context: {context}

Provide:
1. What each anomaly likely represents
2. Possible causes
3. Whether action is needed
4. Recommended next steps
"""

ROOT_CAUSE_PROMPT = """Perform a root cause analysis for this metric change:

Metric: {metric_name}
Change: {change_description}
Contributing factors: {contributors}
Historical context: {history}

Provide:
1. Most likely root cause(s)
2. Supporting evidence
3. Confidence level for each cause
4. Recommended actions
"""

COMPARISON_PROMPT = """Compare these metrics/periods:

Comparison type: {comparison_type}
Data A: {data_a}
Data B: {data_b}
Context: {context}

Provide:
1. Key differences
2. Similarities
3. Statistical significance
4. Business implications
"""
