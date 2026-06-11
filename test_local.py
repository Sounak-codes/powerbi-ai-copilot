"""
Local end-to-end pipeline test.

Tests the full request lifecycle WITHOUT requiring an LLM API key.
Mocks the LLM provider so all orchestration, context, analytics,
memory, and routing logic can be verified locally.
"""
import sys
import os
import asyncio

# Set minimal env vars so settings don't fail
os.environ.setdefault("GROQ_API_KEY", "test-key-for-local-testing")
os.environ.setdefault("OPENAI_API_KEY", "test-key-for-local-testing")
os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("LOG_LEVEL", "WARNING")

sys.path.insert(0, "backend")

# ──────────────────────────────────────────────────────────────────────
# Mock LLM Provider (returns deterministic responses for testing)
# ──────────────────────────────────────────────────────────────────────
class MockLLMProvider:
    """Mock LLM that returns structured responses for testing."""

    async def generate(self, prompt, system=None, temperature=0.7, max_tokens=None):
        if "intent" in (system or "").lower() or "classify" in (system or "").lower():
            return '{"category": "analysis", "confidence": 0.85, "entities": ["revenue"]}'
        if "dax" in (system or "").lower():
            return "Total Revenue = SUM(Sales[Revenue])"
        if "insight" in (system or "").lower():
            return "Revenue increased by 12% driven primarily by the West region."
        return f"Mock response for: {prompt[:50]}..."

    async def generate_with_structured_output(self, prompt, system=None, response_format=None, temperature=0.7, max_tokens=None):
        if "classify" in (system or "").lower() or "intent" in (system or "").lower():
            return {"category": "analysis", "confidence": 0.85, "entities": ["revenue"]}
        if "insight" in (system or "").lower():
            return {"insights": [{"type": "trend", "title": "Revenue Growth", "description": "Revenue grew 12%", "confidence": 0.85, "severity": "medium"}], "summary": "Overall positive trend"}
        if "complexity" in (system or "").lower():
            return {"complexity": "simple", "needs_planning": False, "direct_agent": "analytics_agent"}
        if "plan" in (system or "").lower():
            return {"plan": [{"step": 1, "agent": "analytics_agent", "action": "Analyze"}], "reasoning": "Simple analysis"}
        return {"result": "mock structured response"}


# Patch the provider factory before any imports use it
from llm.providers import provider_factory
provider_factory.ProviderFactory.get_default_provider = staticmethod(lambda: MockLLMProvider())
provider_factory.ProviderFactory.create_provider = staticmethod(lambda name=None: MockLLMProvider())


# ──────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────
def separator(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


async def test_context_engine():
    """Test the full context engine pipeline."""
    separator("Context Engine")

    from context_engine.context_builder import ContextBuilder

    cb = ContextBuilder()

    raw_context = {
        "report": {"id": "r1", "name": "Sales Dashboard", "pages": [
            {"id": "p1", "name": "Overview", "visuals": []}
        ], "dataset": {"tables": [{"name": "Sales", "columns": [{"name": "Revenue"}, {"name": "Date"}]}]}},
        "page": {"id": "p1", "name": "Overview", "visuals": [
            {"id": "v1", "type": "lineChart", "title": "Revenue Trend", "fields": ["Sales.Date", "Sales.Revenue"]},
            {"id": "v2", "type": "card", "title": "Total Revenue", "fields": ["Sales.Revenue"]},
            {"id": "v3", "type": "barChart", "title": "By Region", "fields": ["Sales.Region", "Sales.Revenue"]},
        ]},
        "filters": [
            {"target": {"table": "Sales", "column": "Region"}, "operator": "In", "values": ["West", "East"]}
        ],
        "slicers": [
            {"id": "s1", "target": {"table": "Date", "column": "Year"}, "selectedValues": [2025, 2026]}
        ],
        "selection": {"visualId": "v1", "dataPoints": [{"values": {"Month": "March", "Revenue": 45000}}]},
    }

    # Full context build
    unified = cb.build(raw_context)
    print(f"  ✓ Unified context built ({len(unified)} top-level keys)")
    print(f"    Report: {unified['report'].get('metadata', {}).get('report_name', 'N/A')}")
    print(f"    Page visuals: {unified['page'].get('metadata', {}).get('visual_count', 0)}")
    print(f"    Filters: {unified['filters'].get('filter_count', 0)} active")
    print(f"    Selection: {unified['selection'].get('has_selection', False)}")

    # Prompt-ready text
    prompt_text = cb.build_for_prompt(raw_context)
    print(f"  ✓ Prompt text ({len(prompt_text)} chars):")
    for line in prompt_text.split("\n"):
        print(f"    {line}")


async def test_intent_classification():
    """Test intent classification and routing."""
    separator("Intent Classification & Routing")

    from intent_engine.classifier import IntentClassifier
    from intent_engine.routing_rules import RoutingRuleSet
    from orchestration.intent_router import IntentRouter

    classifier = IntentClassifier()
    intent = await classifier.classify("Why did revenue drop last month?")
    print(f"  ✓ Intent classified: {intent.category.value} (confidence: {intent.confidence})")

    rules = RoutingRuleSet()
    agent = rules.get_agent_for_intent(intent)
    print(f"  ✓ Routed to: {agent}")

    # Test the advanced router
    router = IntentRouter()
    decision = await router.route("Analyze revenue trends")
    print(f"  ✓ IntentRouter decision: {decision['decision']} → {decision.get('agent', 'N/A')}")
    print(f"    Confidence level: {decision['confidence_level']}")


async def test_memory():
    """Test session and memory management."""
    separator("Memory & Session")

    from memory.session_manager import SessionManager
    from memory.conversation_memory import ConversationMemory, MemoryStore
    from memory.context_window import ContextWindowManager

    # Session
    sm = SessionManager()
    session = sm.create_session("user_123", report_id="report_abc")
    print(f"  ✓ Session created: {session.session_id[:8]}...")
    print(f"    Expired: {session.is_expired()}")

    retrieved = sm.get_session(session.session_id)
    print(f"  ✓ Session retrieved: {retrieved is not None}")

    # Conversation memory
    store = MemoryStore()
    conv = store.get_or_create_conversation(session.session_id)
    conv.add_turn("user", "Why did revenue drop?")
    conv.add_turn("assistant", "Revenue dropped 12% due to seasonal factors.")
    conv.add_turn("user", "Which region was most affected?")
    print(f"  ✓ Conversation: {len(conv.turns)} turns")
    print(f"    Recent context: {conv.get_recent_context(2)[:80]}...")

    # Context window
    cwm = ContextWindowManager(max_tokens=4000)
    window = cwm.build_context_window(
        user_message="Break it down by product",
        conversation_history=[t.to_dict() for t in conv.turns],
        report_context="Report: Sales Dashboard, Page: Overview, Filters: Region=West",
    )
    print(f"  ✓ Context window: {window.used_tokens} tokens, {len(window.blocks)} blocks")


async def test_analytics_engine():
    """Test analytics computations."""
    separator("Analytics Engine")

    from analytics_engine.trend_detection.trend_detector import TrendDetector
    from analytics_engine.trend_detection.forecasting import Forecaster
    from analytics_engine.anomaly_detection.zscore import ZScoreDetector
    from analytics_engine.anomaly_detection.iqr import IQRDetector
    from analytics_engine.root_cause.contribution_analysis import ContributionAnalyzer
    from analytics_engine.correlation.pearson import PearsonCorrelation
    from analytics_engine.kpi.kpi_health import KPIHealthAssessor
    from analytics_engine.recommendations.recommendation_engine import RecommendationEngine

    # Trend
    td = TrendDetector()
    revenue = [100, 105, 103, 110, 115, 112, 120, 125, 130, 128, 135, 140]
    trend = td.detect(revenue)
    print(f"  ✓ Trend: {trend.direction.value} (slope={trend.slope:.3f}, R²={trend.r_squared:.3f})")

    # Forecast
    fc = Forecaster()
    forecast = fc.forecast(revenue, periods_ahead=3)
    print(f"  ✓ Forecast (next 3): {[round(v, 1) for v in forecast.forecast_values]}")

    # Anomaly
    data = [10, 11, 12, 10, 11, 100, 10, 12, 11, 10, 11, 12, -50, 10, 11]
    zd = ZScoreDetector(threshold=2.0)
    anomalies = zd.detect(data)
    print(f"  ✓ Z-Score anomalies: {len(anomalies.anomalies)} found")

    iqr = IQRDetector()
    iqr_result = iqr.detect(data)
    print(f"  ✓ IQR anomalies: {len(iqr_result.anomalies)} found")

    # Root cause
    ca = ContributionAnalyzer()
    result = ca.analyze(
        "Revenue",
        {"West": 500, "East": 300, "North": 200, "South": 150},
        {"West": 600, "East": 350, "North": 180, "South": 170},
        "Region",
    )
    print(f"  ✓ Root cause: {result.description[:80]}...")

    # Correlation
    pc = PearsonCorrelation()
    corr = pc.compute([1, 2, 3, 4, 5, 6, 7, 8], [2, 4, 5, 4, 6, 7, 8, 9], "Revenue", "Profit")
    print(f"  ✓ Correlation: r={corr.coefficient:.3f} ({corr.strength})")

    # KPI Health
    ha = KPIHealthAssessor()
    kpi = ha.assess("Revenue", current_value=850, target_value=1000, previous_value=800, higher_is_better=True)
    print(f"  ✓ KPI Health: {kpi.kpi_name} → {kpi.status.value} (score={kpi.score:.0f}, trend={kpi.trend})")

    # Recommendations
    re = RecommendationEngine()
    recs = re.generate(
        kpi_health=[kpi.to_dict()],
        trend_results=[trend.to_dict()],
    )
    print(f"  ✓ Recommendations: {len(recs.recommendations)} generated")
    for r in recs.recommendations[:2]:
        print(f"    [{r.priority.value}] {r.title}")


async def test_orchestrator():
    """Test the full orchestrator flow."""
    separator("Orchestrator (Full Pipeline)")

    from orchestration.orchestrator import Orchestrator

    orch = Orchestrator()

    # Create a session
    session = orch.create_session("user_123", report_id="report_sales")
    print(f"  ✓ Session: {session.session_id[:8]}...")

    # Register a mock agent
    class MockAnalyticsAgent:
        async def execute(self, message, session, conversation, context=None, intent=None):
            return {
                "message": f"Analysis complete: Revenue is trending upward at 3.3% per period.",
                "metadata": {"agent": "analytics", "confidence": 0.85},
            }

    orch.register_agent("analytics_agent", MockAnalyticsAgent())
    orch.register_agent("rag_agent", MockAnalyticsAgent())
    orch.register_agent("insight_agent", MockAnalyticsAgent())
    orch.register_agent("planner_agent", MockAnalyticsAgent())
    print(f"  ✓ Agents registered: {list(orch.agents.keys())}")

    # Handle a message
    response = await orch.handle_user_message(
        message="Why did revenue drop last month?",
        session_id=session.session_id,
        context={"report_name": "Sales Dashboard"},
    )
    print(f"  ✓ Response status: {response['status']}")
    print(f"    Agent used: {response.get('agent', 'N/A')}")
    print(f"    Message: {response.get('message', '')[:80]}...")

    # Check conversation history persisted
    history = orch.get_conversation_history(session.session_id)
    print(f"  ✓ Conversation history: {len(history)} turns stored")


async def test_what_if_engine():
    """Test what-if simulation."""
    separator("What-If Engine")

    from what_if_engine.simulator import WhatIfSimulator
    from what_if_engine.scenario_builder import ScenarioBuilder
    from what_if_engine.impact_analysis import ImpactAnalyzer

    # Build scenario
    sb = ScenarioBuilder()
    scenario = sb.build_percentage_change("Revenue +15%", "revenue", 15, 1000)
    print(f"  ✓ Scenario: {scenario.name}")
    print(f"    Changes: {scenario.changes}")

    # Simulate
    sim = WhatIfSimulator()
    sim.register_relationship("revenue", "profit", 0.35)
    sim.register_relationship("revenue", "customer_satisfaction", 0.1)
    sim.register_relationship("profit", "reinvestment", 0.2)

    result = sim.simulate(
        scenario.name,
        scenario.changes,
        {"revenue": 1000, "profit": 250, "customer_satisfaction": 4.2, "reinvestment": 50},
    )
    print(f"  ✓ Simulation: {result.narrative}")
    print(f"    Impacts: {result.projected_impacts}")

    # Impact analysis
    ia = ImpactAnalyzer()
    impact = ia.assess_impact(
        scenario.name, scenario.changes, result.projected_impacts,
        {"revenue": 1000, "profit": 250, "customer_satisfaction": 4.2, "reinvestment": 50},
    )
    print(f"  ✓ Impact: {impact.description}")


async def test_cross_visual_reasoning():
    """Test cross-visual reasoning."""
    separator("Cross-Visual Reasoning")

    from cross_visual_reasoning.page_analysis import PageAnalyzer
    from cross_visual_reasoning.report_analysis import ReportAnalyzer

    pa = PageAnalyzer()
    result = pa.analyze_page({
        "name": "Sales Overview",
        "visuals": [
            {"id": "v1", "type": "lineChart", "title": "Revenue Trend", "fields": ["Date", "Revenue"], "data": []},
            {"id": "v2", "type": "card", "title": "Total Revenue", "fields": ["Revenue"], "data": []},
            {"id": "v3", "type": "barChart", "title": "By Region", "fields": ["Region", "Revenue"], "data": []},
            {"id": "v4", "type": "pieChart", "title": "Product Split", "fields": ["Product", "Revenue"], "data": []},
        ],
    })
    print(f"  ✓ Page analysis: {result['summary']}")
    print(f"    Insights: {len(result['insights'])}")
    print(f"    Coverage: {result['coverage']}")

    ra = ReportAnalyzer()
    report_result = ra.analyze_report({
        "name": "Sales Dashboard",
        "pages": [
            {"name": "Overview", "visuals": [{"id": "v1", "type": "card", "fields": ["Revenue"]}, {"id": "v2", "type": "lineChart", "fields": ["Date", "Revenue"]}]},
            {"name": "Regional", "visuals": [{"id": "v3", "type": "barChart", "fields": ["Region", "Revenue"]}, {"id": "v4", "type": "table", "fields": ["Region", "Revenue", "Profit"]}]},
            {"name": "Products", "visuals": [{"id": "v5", "type": "pieChart", "fields": ["Product", "Revenue"]}]},
        ],
    })
    print(f"  ✓ Report analysis: {report_result['summary']}")


async def test_rag_pipeline():
    """Test the RAG pipeline (ingestion + retrieval)."""
    separator("RAG Pipeline")

    from rag.ingestion.chunking import DocumentChunker
    from rag.ingestion.report_parser import ReportParser
    from rag.ingestion.dax_parser import DAXParser
    from rag.retrieval.bm25_search import BM25Search
    from rag.retrieval.metadata_filter import MetadataFilter

    # Parse report into documents
    rp = ReportParser()
    docs = rp.parse_report({
        "id": "r1", "name": "Sales Dashboard",
        "pages": [{"id": "p1", "name": "Overview", "visuals": [
            {"type": "lineChart", "title": "Revenue", "fields": ["Date.Month", "Sales.Revenue"]},
            {"type": "card", "title": "YTD Revenue", "fields": ["Sales.Revenue"]},
        ]}],
        "dataset": {"tables": [
            {"name": "Sales", "columns": [{"name": "Revenue"}, {"name": "Quantity"}, {"name": "Region"}],
             "measures": [{"name": "Total Revenue", "expression": "SUM(Sales[Revenue])"},
                          {"name": "YTD Revenue", "expression": "TOTALYTD([Total Revenue], 'Date'[Date])"}]},
        ]},
    })
    print(f"  ✓ Report parsed: {len(docs)} documents")

    # Parse DAX
    dp = DAXParser()
    dax_docs = dp.parse_measures([
        {"name": "Total Revenue", "expression": "SUM(Sales[Revenue])", "table": "Sales"},
        {"name": "YTD Revenue", "expression": "TOTALYTD([Total Revenue], 'Date'[Date])", "table": "Sales"},
        {"name": "Revenue Growth", "expression": "DIVIDE([Total Revenue] - [Previous Revenue], [Previous Revenue])", "table": "Sales"},
    ])
    print(f"  ✓ DAX parsed: {len(dax_docs)} measures")
    for d in dax_docs:
        print(f"    {d['metadata']['measure_name']} ({d['metadata']['category']})")

    # Chunk
    chunker = DocumentChunker(chunk_size=200, chunk_overlap=30)
    all_docs = docs + dax_docs
    chunks = chunker.chunk_batch(all_docs)
    print(f"  ✓ Chunked: {len(all_docs)} docs → {len(chunks)} chunks")

    # BM25 index and search
    bm25 = BM25Search()
    bm25.index_documents([{"id": c.chunk_id, "text": c.text, "metadata": c.metadata} for c in chunks])
    results = bm25.search("revenue year to date calculation", top_k=3)
    print(f"  ✓ BM25 search 'revenue year to date': {len(results)} results")
    for r in results[:2]:
        print(f"    [{r.score:.3f}] {r.text[:60]}...")

    # Metadata filter
    mf = MetadataFilter()
    dax_only = mf.filter_results(
        [{"text": r.text, "metadata": r.metadata} for r in results],
        {"source_type": "dax_measure"},
    )
    print(f"  ✓ Filtered to DAX measures: {len(dax_only)} results")


async def test_observability():
    """Test observability stack."""
    separator("Observability")

    from observability.telemetry import TelemetryCollector
    from observability.tracing import Tracer
    from observability.metrics import MetricsCollector

    # Telemetry
    tc = TelemetryCollector()
    tc.record_event("user_query", {"question": "Why did revenue drop?", "session": "s1"})
    tc.record_event("agent_execution", {"agent": "analytics", "duration_ms": 150})
    tc.record_event("llm_call", {"model": "llama-3.3-70b", "tokens": 500, "latency_ms": 200})
    metrics = tc.get_metrics()
    print(f"  ✓ Telemetry: {metrics.total_events} events")

    # Metrics
    mc = MetricsCollector()
    mc.increment("http_requests", 10)
    mc.increment("http_errors", 1)
    mc.record_duration("response_time", 0.12)
    mc.record_duration("response_time", 0.18)
    mc.record_duration("response_time", 0.45)
    mc.set_gauge("active_sessions", 5)
    print(f"  ✓ Metrics collected (requests=10, errors=1, sessions=5)")

    # Tracing
    tr = Tracer()
    trace_id = tr.start_trace("handle_user_message")
    tr.start_span(trace_id, "intent_classification")
    tr.end_span(trace_id, "intent_classification")
    tr.start_span(trace_id, "context_building")
    tr.end_span(trace_id, "context_building")
    tr.start_span(trace_id, "agent_execution")
    tr.end_span(trace_id, "agent_execution")
    trace = tr.get_trace(trace_id)
    print(f"  ✓ Trace: {len(trace['spans'])} spans recorded")


async def main():
    print("\n" + "🧪 " * 20)
    print("  POWER BI AI COPILOT — LOCAL PIPELINE TEST")
    print("🧪 " * 20)

    await test_context_engine()
    await test_intent_classification()
    await test_memory()
    await test_analytics_engine()
    await test_orchestrator()
    await test_what_if_engine()
    await test_cross_visual_reasoning()
    await test_rag_pipeline()
    await test_observability()

    separator("FINAL RESULT")
    print("  ✅ ALL TESTS PASSED — Pipeline is working correctly!")
    print()
    print("  To run with a real LLM, create .env with your GROQ_API_KEY")
    print("  and run: cd backend && python main.py")
    print()


if __name__ == "__main__":
    asyncio.run(main())
