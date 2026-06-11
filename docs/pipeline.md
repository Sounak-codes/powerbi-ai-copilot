# Pipeline Documentation — Power BI AI Copilot

This document provides a detailed explanation of how the entire AI copilot pipeline works, from a user's question in the Power BI visual to the final response rendered in the chat UI.

---

## Table of Contents

1. [High-Level Architecture](#high-level-architecture)
2. [Request Lifecycle](#request-lifecycle)
3. [Phase 1 — Core Architecture](#phase-1--core-architecture)
4. [Phase 2 — Analytics Engine](#phase-2--analytics-engine)
5. [Phase 3 — Agents & RAG](#phase-3--agents--rag)
6. [Phase 4 — Advanced Features](#phase-4--advanced-features)
7. [Data Flow Diagram](#data-flow-diagram)
8. [Configuration & Environment](#configuration--environment)
9. [Extending the Pipeline](#extending-the-pipeline)

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Power BI Report                              │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Custom Visual (Chat UI)                                  │  │
│  │  - User types a question                                  │  │
│  │  - Visual sends report context + message via REST/WS      │  │
│  └──────────────────────────┬────────────────────────────────┘  │
└─────────────────────────────┼───────────────────────────────────┘
                              │ HTTP POST /api/chat
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                             │
│                                                                 │
│  ┌──────────┐  ┌──────────────┐  ┌──────────┐  ┌───────────┐  │
│  │  Intent  │→ │ Orchestrator │→ │  Agents  │→ │ Response  │  │
│  │  Engine  │  │              │  │          │  │  Builder  │  │
│  └──────────┘  └──────────────┘  └──────────┘  └───────────┘  │
│       │              │                 │              │          │
│       ▼              ▼                 ▼              ▼          │
│  ┌──────────┐  ┌──────────────┐  ┌──────────┐  ┌───────────┐  │
│  │ Context  │  │    Memory    │  │Analytics │  │    RAG    │  │
│  │  Engine  │  │   (Session)  │  │  Engine  │  │ (Retrieval│  │
│  └──────────┘  └──────────────┘  └──────────┘  └───────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  LLM Provider Layer (Groq / OpenAI)                      │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Request Lifecycle

Every user interaction follows this path:

### Step 1: Frontend sends request

The Power BI custom visual collects:
- **User message** — the question or command
- **Report context** — active page, visible visuals, applied filters, slicer states, selected data points
- **Session ID** — for conversation continuity

This is sent as a `POST /api/chat` request:

```json
{
  "message": "Why did revenue drop last month?",
  "session_id": "sess_abc123",
  "context": {
    "report": { "id": "r1", "name": "Sales Dashboard" },
    "page": { "name": "Overview", "visuals": [...] },
    "filters": [...],
    "slicers": [...],
    "selection": { "visualId": "v3", "dataPoints": [...] }
  }
}
```

### Step 2: Context Engine enriches the raw context

The `ContextBuilder` processes the raw frontend payload into a structured, enriched context:

```
Raw Context → ContextBuilder
  ├── ReportContextExtractor  → report metadata, data model, tables
  ├── PageContextExtractor    → visual inventory, relationships
  ├── VisualContextExtractor  → data summaries, analysis hints
  ├── FilterContextExtractor  → active filters with NL descriptions
  ├── SlicerContextExtractor  → slicer states, scope impact
  └── SelectionContextExtractor → user focus, intent hints
```

The output is a unified context object plus a `build_for_prompt()` text string suitable for LLM prompts.

### Step 3: Session & Memory management

The `SessionManager` validates/creates the session, and `ConversationMemory` retrieves prior turns:

- Sessions have TTL-based expiry (default: 1 hour)
- Conversation history is trimmed to the last N turns (default: 10)
- The `ContextWindowManager` packs history + context into a token budget

### Step 4: Intent Classification

The `IntentClassifier` uses the LLM to classify the user's message into one of 8 categories:

| Category | Example |
|----------|---------|
| `question` | "What is the average order value?" |
| `analysis` | "Analyze revenue trends for Q4" |
| `insight` | "Give me key insights from this page" |
| `explanation` | "Explain why margin dropped" |
| `recommendation` | "What should I do about declining NPS?" |
| `dax` | "Create a YTD revenue measure" |
| `report` | "Document this page" |
| `unknown` | Ambiguous/unclear messages |

The `IntentRouter` adds confidence thresholds:
- **High confidence (≥0.75)**: Route directly
- **Medium confidence (0.4–0.75)**: Route with advisory; attempt context-boost from conversation history
- **Low confidence (<0.4)**: Request clarification from user

### Step 5: Routing to Agent

The `RoutingRuleSet` maps intents to agents:

```
question     → rag_agent
analysis     → analytics_agent
insight      → insight_agent
explanation  → rag_agent
recommendation → insight_agent
dax          → dax_agent
report       → analytics_agent
unknown      → planner_agent
```

### Step 6: Agent Execution

The selected agent executes its logic (described in detail below). Each agent:
1. Receives the message, session, conversation memory, enriched context, and classified intent
2. Calls the LLM and/or internal analytics engines
3. Returns a structured response dict with `message` and `metadata`

### Step 7: Response Building

The `ResponseBuilder` takes the raw agent output and:
- Formats it for presentation
- Generates follow-up question suggestions
- Attaches metadata (confidence, source agent, intent)
- Enriches with context-aware follow-ups

### Step 8: Memory Update

The conversation turn (user + assistant) is stored in `ConversationMemory` and optionally persisted via `PersistentMemoryStore` (Redis or in-memory fallback).

### Step 9: Response returned to frontend

```json
{
  "id": "resp_xyz",
  "message": "Revenue dropped 12% last month primarily due to...",
  "session_id": "sess_abc123",
  "status": "success",
  "agent": "analytics_agent",
  "intent": { "category": "analysis", "confidence": 0.87 },
  "follow_up_questions": [
    "What's driving this trend?",
    "How does this compare to last year?",
    "Can you break this down by region?"
  ],
  "timestamp": "2026-06-11T10:30:00Z"
}
```

---

## Phase 1 — Core Architecture

### Intent Engine (`backend/intent_engine/`)

**Purpose**: Classify user messages and route them to the right agent.

| Module | Role |
|--------|------|
| `classifier.py` | LLM-based classification into 8 intent categories |
| `intent_schema.py` | `IntentCategory` enum + `Intent` dataclass |
| `routing_rules.py` | Rule-based mapping from intent → agent name |

The classifier sends the user message to the LLM with a system prompt requesting JSON classification. It returns confidence scores that determine routing behavior.

### Orchestration (`backend/orchestration/`)

**Purpose**: Coordinate the end-to-end request flow.

| Module | Role |
|--------|------|
| `orchestrator.py` | Central coordinator: session → memory → classify → route → execute → respond |
| `intent_router.py` | Advanced routing: confidence thresholds, context boosting, multi-intent detection |
| `workflow_manager.py` | Multi-step workflow engine with templates (analysis, insight, question, dax) |
| `state_manager.py` | Conversation state machine tracking phase transitions |
| `response_builder.py` | Formats agent outputs into user-facing responses with follow-ups |

**Workflow Templates** define step sequences:

```
"analysis" workflow:
  1. classify_intent → planner_agent
  2. gather_context → context_builder
  3. run_analysis → analytics_agent
  4. generate_response → response_agent
```

### Context Engine (`backend/context_engine/`)

**Purpose**: Extract and enrich Power BI report state for LLM consumption.

| Module | Role |
|--------|------|
| `context_builder.py` | Orchestrates all extractors → unified context + LLM-ready text |
| `visual_context.py` | Visual metadata, data summaries, analysis hints per visual type |
| `filter_context.py` | Active filters → natural language descriptions |
| `slicer_context.py` | Slicer states, range/date selections, scope impact |
| `selection_context.py` | User click/highlight → focus intent (drilling, comparing, exploring) |
| `page_context.py` | Page visual inventory, cross-visual field relationships |
| `report_context.py` | Report metadata, data model (tables, columns, measures) |

**Key method**: `ContextBuilder.build_for_prompt(raw_context)` produces a compact text like:

```
Report: Sales Dashboard
Current page: Revenue Overview
Filters: Data is filtered where Sales.Region is one of [West, East].
Active slicers: Date.Year = [2025, 2026]
Selection: User selected a data point (Region=West, Revenue=5000) in visual 'v3'.
```

### Memory (`backend/memory/`)

**Purpose**: Maintain conversation state across turns and sessions.

| Module | Role |
|--------|------|
| `session_manager.py` | Session creation, TTL-based expiry, refresh on activity |
| `conversation_memory.py` | Per-session turn storage with automatic trimming |
| `memory_store.py` | Redis-backed persistent store with TTL (fallback: in-memory) |
| `context_window.py` | Token budget manager for LLM prompts (packs history + context + retrieved docs) |

**Context Window** ensures we never exceed model limits:
- System instructions: priority 100
- User message: priority 95
- Report context: priority 80
- Conversation history: priority 70
- Retrieved documents: priority 60

Lower-priority blocks are dropped first when the budget is tight.

---

## Phase 2 — Analytics Engine

### Overview (`backend/analytics_engine/`)

The analytics engine provides statistical analysis capabilities without requiring the LLM for computation. It uses NumPy for math and produces structured results that the LLM then narrates.

### Trend Detection (`trend_detection/`)

```
Input: time series values
  ├── TrendDetector.detect()
  │     → direction, slope, R², change points
  │     → segment-wise trend detection
  │     → period-over-period comparison
  │
  ├── SeasonalityDetector.detect()
  │     → autocorrelation analysis
  │     → seasonal period identification
  │     → seasonal decomposition
  │
  └── Forecaster.forecast()
        → linear extrapolation
        → Holt's exponential smoothing
        → seasonal naive method
        → confidence intervals
```

### Anomaly Detection (`anomaly_detection/`)

Three complementary methods:

| Method | Best For | Approach |
|--------|----------|----------|
| `ZScoreDetector` | Normal distributions | Points > N standard deviations from mean |
| `IQRDetector` | Skewed data, outliers | Points outside Q1-1.5×IQR to Q3+1.5×IQR |
| `IsolationForestDetector` | Complex patterns | Tree-based isolation (sklearn) |

Each returns severity-scored anomalies with natural language descriptions.

### Root Cause Analysis (`root_cause/`)

```
"Why did revenue drop 15%?"

ContributionAnalyzer.analyze()
  → Per-segment contribution to total change
  → Waterfall decomposition for visualization
  → Multi-dimension analysis (Region × Product × Time)

DriverAnalyzer.analyze()
  → Variance decomposition (eta-squared / ANOVA)
  → Ranks dimensions by explanatory power
  → Identifies top segments within each dimension

MetricDecomposer.decompose_rate_mix()
  → Rate effect: performance changed within segments
  → Mix effect: composition shifted between segments
  → Interaction effect: both changed simultaneously
```

### Correlation (`correlation/`)

```
RelationshipAnalyzer.analyze_all_pairs()
  ├── PearsonCorrelation (linear relationships)
  ├── SpearmanCorrelation (monotonic, non-linear)
  ├── Auto-selects best method per pair
  ├── Lead-lag detection for potential causality
  └── Correlation matrix with significant pairs highlighted
```

### KPI Analysis (`kpi/`)

```
KPIHealthAssessor.assess()
  → Score against target (0-100)
  → Trend assessment (improving/declining/stable)
  → Time-to-target estimation
  → Alert generation for critical/warning states

KPIScorer.calculate_composite_score()
  → Weighted multi-metric scores
  → Normalization (min-max, z-score, percentage)
  → Letter grading (A through F)
```

### Recommendations (`recommendations/`)

```
RecommendationEngine.generate()
  Inputs: KPI health + trends + anomalies + correlations
  ├── Prioritized recommendations (critical → low)
  ├── Typed: investigate, monitor, alert, optimize, strategic
  └── De-duplicated across sources

ActionGenerator.generate_actions()
  → Concrete next steps with owners, deadlines, effort estimates
  → Categories: analysis, communication, process_change, monitoring
```

### Executive Summary (`executive_summary/`)

```
ExecutiveSummaryGenerator.generate()
  → LLM-powered headline generation
  → Key metric highlights
  → Concerns and recommendations
  → Fallback to heuristic summary when LLM unavailable

NarrativeBuilder
  → Templates for trend, anomaly, contribution, correlation narratives
  → Composable multi-section narratives
```

---

## Phase 3 — Agents & RAG

### Agent Architecture

All agents inherit from `BaseAgent` and implement:

```python
async def execute(
    self, message, session, conversation, context, intent
) -> Dict[str, Any]:
    return {"message": "...", "metadata": {...}}
```

### Agent Catalog

| Agent | When Used | What It Does |
|-------|-----------|--------------|
| **PlannerAgent** | Unknown/complex intents | Assesses complexity, builds multi-step plans, routes simple requests directly |
| **AnalyticsAgent** | Analysis requests | Runs analytics engine, generates insights, creates analysis narratives |
| **RAGAgent** | Questions, explanations | Retrieves relevant documents, generates grounded answers |
| **DAXAgent** | DAX requests | Generates, explains, optimizes, or debugs DAX based on sub-action detection |
| **InsightAgent** | Insight/recommendation requests | Combines analytics results with LLM reasoning for prioritized insights |
| **ResponseAgent** | Final formatting | Polishes raw outputs, adds follow-ups, adjusts tone |

### RAG Pipeline (`backend/rag/`)

The RAG (Retrieval-Augmented Generation) pipeline enables knowledge-grounded responses:

```
Document Ingestion (offline):
  ┌─────────────┐     ┌──────────┐     ┌───────────┐     ┌────────┐
  │ ReportParser │ ──→ │ Chunker  │ ──→ │ Embeddings│ ──→ │ FAISS  │
  │ DAXParser    │     │(sentence)│     │ (OpenAI)  │     │ Store  │
  │ MetadataExt  │     └──────────┘     └───────────┘     └────────┘
  └─────────────┘

Query-time Retrieval:
  ┌──────────────────────────────────────────────────────────┐
  │                   HybridSearch                            │
  │                                                          │
  │  Query ──┬──→ VectorSearch (semantic) ──┐                │
  │          │                              ├──→ RRF Fusion  │
  │          └──→ BM25Search (keyword) ────┘     │           │
  │                                              ▼           │
  │                                     MetadataFilter       │
  │                                              │           │
  │                                              ▼           │
  │                                         Reranker         │
  │                                        (LLM-based)       │
  └──────────────────────────────────────────────────────────┘
                              │
                              ▼
                    Top-K relevant documents
                              │
                              ▼
                    RAGAgent + LLM → Grounded answer
```

**Key design decisions:**

1. **Hybrid search** combines semantic (vector) and lexical (BM25) for best recall
2. **Reciprocal Rank Fusion (RRF)** merges both rankings without score normalization issues
3. **Reranker** uses the LLM as a cross-encoder to improve precision of final top-k
4. **Metadata filtering** pre/post-filters by source type, report, date range
5. **Chunking** uses sentence-boundary splitting with configurable overlap

### RAG Evaluation (`rag/evaluation/`)

Metrics for measuring retrieval quality:
- **Recall@K**: Were all relevant docs retrieved?
- **Precision@K**: Were retrieved docs actually relevant?
- **MRR**: How high was the first relevant result ranked?
- **F1@K**: Harmonic mean of precision and recall

---

## Phase 4 — Advanced Features

### Cross-Visual Reasoning (`backend/cross_visual_reasoning/`)

**Purpose**: Understand how visuals on a page relate to each other and derive insights that no single visual can show alone.

```
VisualRelationshipDetector
  → Shared dimensions, measures, tables
  → Detail-of relationships (card → table)
  → Filter target relationships

MetricDependencyAnalyzer
  → DAX expression parsing for measure→measure dependencies
  → Co-occurrence analysis from visual usage
  → Impact chain detection (if A changes, what else is affected?)

PageAnalyzer
  → Contradiction detection (same metric showing conflicting trends)
  → Reinforcement patterns (multiple visuals confirming same story)
  → Gap detection (missing KPI cards, no trend visuals)
  → Page coherence assessment

ReportAnalyzer
  → Cross-page theme identification
  → Visual redundancy detection
  → Report completeness scoring
  → Navigation flow suggestions
```

### What-If Engine (`backend/what_if_engine/`)

**Purpose**: Let users simulate metric changes and see projected downstream impacts.

```
User: "What if revenue grows 10%?"

ScenarioBuilder.build_percentage_change()
  → Scenario: revenue 1000 → 1100

WhatIfSimulator.simulate()
  → Propagates through registered relationships
  → revenue +10% → profit +15% (coefficient 0.3)
  → revenue +10% → market_share +3.3% (coefficient 0.05)

ImpactAnalyzer.assess_impact()
  → Financial impact: +$135
  → Risk level: low (change < 30%)
  → Feasibility: moderate
  → Sensitivity analysis (elasticity per relationship)
  → Time to realize: short_term
```

### DAX Copilot (`backend/dax_copilot/`)

**Purpose**: Full AI-powered DAX development assistance.

| Module | Capability |
|--------|-----------|
| `dax_generator.py` | Generate measures from natural language + data model |
| `dax_explainer.py` | Step-by-step explanation of DAX code |
| `dax_optimizer.py` | Anti-pattern detection, performance scoring, optimized rewrites |
| `dax_debugger.py` | Error pattern matching, root cause identification, fix suggestions |

### Report Documentation (`backend/report_documentation/`)

**Purpose**: Auto-generate comprehensive documentation for Power BI reports.

```
ReportDocumenter.document_report()
  ├── Report overview (name, description, page list)
  ├── Per-page documentation (PageDocumenter)
  │     ├── Visual inventory (type, fields, purpose)
  │     └── Page narrative
  ├── Measure catalog (MeasureDocumenter)
  │     ├── Each measure: what, how, dependencies, category
  │     └── Complexity classification
  └── Data lineage (LineageBuilder)
        └── Table → Column → Measure → Visual graph
```

### Observability (`backend/observability/`)

**Purpose**: Monitor system health, performance, and LLM usage.

| Module | Tracks |
|--------|--------|
| `telemetry.py` | Events: agent executions, LLM calls, user interactions |
| `tracing.py` | Distributed traces: request → intent → agent → LLM → response |
| `metrics.py` | Counters (requests, errors), histograms (latency), gauges (active sessions) |
| `prompt_monitoring.py` | Token usage, LLM latency, success rates, prompt version tracking |

### Evaluations (`backend/evaluations/`)

**Purpose**: Test and validate LLM output quality.

| Module | What It Tests |
|--------|---------------|
| `benchmark_suite/` | End-to-end benchmarks with custom evaluators |
| `hallucination_tests/` | Fact-based verification of LLM claims |
| `prompt_tests/` | Prompt template quality (keyword presence, length, structure) |
| `regression_tests/` | Baseline comparison to detect quality regressions |

---

## Data Flow Diagram

### Complete request flow with timing

```
T+0ms    │ Frontend sends POST /api/chat
         ▼
T+5ms    │ SessionManager validates session
         │ ConversationMemory loads history
         ▼
T+10ms   │ ContextBuilder enriches report context
         │ (filter, slicer, visual, selection extraction)
         ▼
T+50ms   │ IntentClassifier → LLM call (~40ms)
         │ Returns: category + confidence
         ▼
T+55ms   │ IntentRouter evaluates confidence
         │ RoutingRuleSet selects agent
         ▼
T+60ms   │ Agent.execute() begins
         │ ├── RAG retrieval (if needed): ~100ms
         │ ├── Analytics computation: ~20ms
         │ └── LLM generation: ~500-2000ms
         ▼
T+800ms  │ ResponseBuilder formats output
         │ Generates follow-up suggestions
         ▼
T+810ms  │ ConversationMemory stores turn
         │ TelemetryCollector records event
         ▼
T+815ms  │ JSON response returned to frontend
```

### Observability throughout

Every step is instrumented:
- `Tracer` creates spans for each phase
- `MetricsCollector` records latency and counts
- `PromptMonitor` tracks every LLM call
- `TelemetryCollector` logs structured events

---

## Configuration & Environment

### Required Environment Variables

```env
# LLM Provider (choose one)
LLM_PROVIDER=groq          # or "openai"
GROQ_API_KEY=gsk_...       # if using Groq
OPENAI_API_KEY=sk-...      # if using OpenAI

# Models
GROQ_MODEL=llama-3.3-70b-versatile
OPENAI_MODEL=gpt-4
EMBEDDING_MODEL=text-embedding-3-small

# Infrastructure
DATABASE_URL=postgresql://user:password@localhost:5432/powerbi_copilot
REDIS_URL=redis://localhost:6379/0

# Memory
MEMORY_MAX_TURNS=10
SESSION_TIMEOUT=3600

# RAG
RAG_CHUNK_SIZE=512
RAG_CHUNK_OVERLAP=50
RAG_TOP_K=5
```

### Running the backend

```bash
cd backend
pip install -r ../requirements.txt
python main.py
```

The API will be available at `http://localhost:8000` with docs at `/docs`.

---

## Extending the Pipeline

### Adding a new agent

1. Create `backend/agents/my_agent/agent.py` inheriting from `BaseAgent`
2. Create `backend/agents/my_agent/prompts.py` with system/user prompts
3. Register in `main.py` lifespan: `orchestrator.register_agent("my_agent", MyAgent())`
4. Add routing rule in `routing_rules.py`

### Adding a new analytics module

1. Create module in `backend/analytics_engine/my_module/`
2. Return structured dataclass results with `.to_dict()` method
3. Add NL description generation
4. Wire into `InsightGenerator` or `AnalyticsAgent`

### Adding a new context extractor

1. Create `backend/context_engine/my_context.py` with extractor class
2. Add to `ContextBuilder.__init__()` and `build()` method
3. Include in the `build_for_prompt()` output

### Adding new document types to RAG

1. Create parser in `backend/rag/ingestion/my_parser.py`
2. Parse into `{"id", "text", "metadata"}` format
3. Feed through `DocumentChunker` → `EmbeddingService` → `FAISSStore`
