# Power BI AI Copilot

An AI-powered analytics copilot for Power BI that provides intelligent insights, DAX generation, anomaly detection, and natural language querying.

## Overview

The Power BI AI Copilot is a comprehensive system designed to enhance Power BI user experience with:

- **Natural Language Chat**: Ask questions about your data in plain English
- **Intelligent Insights**: Automatic anomaly detection, trend analysis, and recommendations
- **DAX Code Generation**: Generate and explain DAX formulas
- **Context-Aware Analysis**: Understands Power BI context (pages, visuals, filters, selections)
- **RAG (Retrieval-Augmented Generation)**: Answers questions using your report documentation
- **Executive Summaries**: Generate automated business summaries

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Power BI Desktop                      │
│                   (Custom Visual)                       │
└────────────┬────────────────────────────────────────────┘
             │ Runtime Context
             ▼
┌─────────────────────────────────────────────────────────┐
│              API Gateway (Nginx)                        │
└─────┬───────────────────────────────────────┬───────────┘
      │                                       │
      ▼                                       ▼
┌──────────────────────────┐      ┌─────────────────────┐
│   Backend (FastAPI)      │      │  Frontend (React)   │
│  • Orchestrator          │      │  • Chat Interface   │
│  • Agents                │      │  • Insights View    │
│  • Analytics Engine      │      │  • Context Display  │
│  • RAG System            │      └─────────────────────┘
└──────────┬───────────────┘
           │
    ┌──────┴──────┬──────────┬─────────────┐
    ▼             ▼          ▼             ▼
┌────────┐  ┌─────────┐ ┌──────────┐ ┌─────────┐
│  LLMs  │  │ Database │ │ Cache    │ │ Vector  │
│        │  │(Postgres)│ │  (Redis) │ │ Store   │
└────────┘  └─────────┘ └──────────┘ └─────────┘
```

## Project Structure

```
powerbi-ai-copilot/
├── backend/
│   ├── agents/               # AI Agents (RAG, Analytics, DAX, etc.)
│   ├── analytics_engine/     # Analytics algorithms
│   ├── api/                  # API routes and middleware
│   ├── config/               # Configuration and settings
│   ├── context_engine/       # Power BI context extraction
│   ├── database/             # Database models and migrations
│   ├── intent_engine/        # Intent classification and routing
│   ├── llm/                  # LLM providers (OpenAI, Groq)
│   ├── memory/               # Session and conversation memory
│   ├── models/               # Request/response models
│   ├── orchestration/        # Workflow orchestration
│   ├── rag/                  # RAG system components
│   ├── schemas/              # Pydantic schemas
│   ├── app.py                # FastAPI application
│   └── main.py               # Entry point
│
├── frontend/
│   └── pbiviz/
│       ├── src/
│       │   ├── components/   # React components
│       │   ├── hooks/        # Custom React hooks
│       │   ├── services/     # API/WebSocket services
│       │   ├── types/        # TypeScript types
│       │   └── App.tsx       # Root component
│       └── package.json
│
├── infrastructure/
│   ├── docker/               # Docker configurations
│   ├── kubernetes/           # K8s manifests
│   └── terraform/            # IaC for cloud resources
│
├── docs/                      # Documentation
├── tests/                     # Test suites
├── docker-compose.yml         # Local development stack
├── requirement.txt            # Python dependencies
└── README.md                  # This file
```

## Features

### 1. Intelligent Chat Interface
- Ask questions about your Power BI reports
- Natural language processing with intent classification
- Multi-turn conversations with context memory
- Real-time responses with follow-up suggestions

### 2. Analytics Engine
- **Trend Detection**: Identify temporal patterns in data
- **Anomaly Detection**: Multiple algorithms (Z-score, IQR, Isolation Forest)
- **Root Cause Analysis**: Decomposition and contribution analysis
- **Correlation Analysis**: Find relationships between metrics
- **Recommendations**: Actionable insights based on data patterns

### 3. DAX Copilot
- Generate DAX formulas from natural language descriptions
- Explain existing DAX formulas
- Optimize DAX performance
- Debug DAX errors

### 4. Context Engine
- Extracts Power BI report structure
- Tracks page and visual context
- Manages filters and slicers
- Remembers user selections

### 5. RAG System
- Vector search over report documentation
- Hybrid search (semantic + BM25)
- Relevance reranking
- Citation tracking

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker and Docker Compose (optional)
- PostgreSQL 13+ (or use Docker)
- Redis (or use Docker)

### Option 1: Local Development

```bash
# Clone and setup
git clone <repo-url>
cd powerbi-ai-copilot

# Create Python environment
conda create -n copilot python=3.11
conda activate copilot

# Install dependencies
pip install -r requirement.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

#### Start Backend
```bash
cd backend
python main.py
```

Visit `http://localhost:8000/docs` for API documentation.

#### Start Frontend
```bash
cd frontend/pbiviz
npm install
npm start
```

### Option 2: Docker Compose

```bash
# Start all services
docker-compose up -d

# Check services
docker-compose ps

# View logs
docker-compose logs -f backend
```

Services will be available at:
- Backend API: `http://localhost:8000`
- Frontend: `http://localhost:3000`
- API Docs: `http://localhost:8000/docs`

### Option 3: Kubernetes

```bash
# Create namespace and deploy
kubectl apply -f infrastructure/kubernetes/

# Check deployment
kubectl get pods -n powerbi-copilot

# Port forward to access
kubectl port-forward -n powerbi-copilot svc/backend-service 8000:80
```

## Configuration

### Environment Variables

```env
# API Configuration
DEBUG=False
HOST=0.0.0.0
PORT=8000

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/powerbi_copilot
REDIS_URL=redis://localhost:6379/0

# LLM Configuration
LLM_PROVIDER=openai  # or 'groq'
OPENAI_API_KEY=your_key
OPENAI_MODEL=gpt-4
GROQ_API_KEY=your_key
GROQ_MODEL=mixtral-8x7b-32768

# Embeddings
EMBEDDING_MODEL=text-embedding-3-small

# Memory
MEMORY_MAX_TURNS=10
SESSION_TIMEOUT=3600

# Logging
LOG_LEVEL=INFO
```

## API Examples

### Create Session
```bash
curl -X POST "http://localhost:8000/api/chat/session?user_id=user123&report_id=report456"
```

### Send Message
```bash
curl -X POST "http://localhost:8000/api/chat/message" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are the top trends in sales?",
    "sessionId": "session-id",
    "context": {}
  }'
```

### Generate Insights
```bash
curl -X POST "http://localhost:8000/api/insights/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "reportId": "report123",
    "pageId": "page1",
    "depth": "standard"
  }'
```

## Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_main.py -v

# Run with coverage
pytest --cov=backend
```

## Development

### Code Style
```bash
# Format code
black backend/

# Lint
flake8 backend/

# Type checking
mypy backend/
```

### Adding New Agents

1. Extend `BaseAgent` class
2. Implement `execute` method
3. Register in `main.py`
4. Add routing rules in `intent_engine/routing_rules.py`

### Database Migrations

```bash
# Create migration
alembic revision --autogenerate -m "Add new table"

# Apply migration
alembic upgrade head
```

## Performance Optimization

- Implement caching for frequently asked questions
- Use connection pooling for database
- Redis for session and conversation caching
- Vector index compression for RAG

## Security

- JWT token authentication for API
- Rate limiting on endpoints
- Input validation on all endpoints
- Secure credential management
- CORS configuration for frontend

## Monitoring and Observability

- Prometheus metrics exposed at `/metrics`
- OpenTelemetry tracing support
- Structured logging with JSON format
- Health check endpoints

## Troubleshooting

### Backend won't start
```bash
# Check dependencies
pip install -r requirement.txt --upgrade

# Check database connection
python -c "import sqlalchemy; sqlalchemy.create_engine('postgresql://...')"
```

### LLM API errors
- Verify API keys in `.env`
- Check API quotas and rate limits
- Ensure network connectivity

### Frontend build errors
```bash
cd frontend/pbiviz
rm -rf node_modules package-lock.json
npm install
npm start
```

## Documentation

- [API Documentation](docs/api.md)
- [Architecture Overview](docs/architecture.md)
- [Setup Guide](docs/setup_guide.md)
- [Deployment Guide](docs/deployment.md)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit changes
4. Push and create a Pull Request

## License

MIT License - See LICENSE file for details

## Support

For issues, questions, or suggestions:
- Open an GitHub issue
- Check existing documentation
- Review the troubleshooting guide

## Roadmap

- [ ] Azure OpenAI integration
- [ ] Advanced DAX debugger
- [ ] Custom metric definitions
- [ ] Power BI service cloud integration
- [ ] Mobile app support
- [ ] Advanced visualization generation
- [ ] Collaborative features
```

Swagger API:

```text
http://127.0.0.1:8000/docs
```

### 4. Run Custom Visual

Install Node.js LTS first, then:

```powershell
cd frontend/custom_visual
npm install
npm run start
```

The developer visual runs at:

```text
https://localhost:8080/
```

### 5. Use In Power BI Desktop

1. Open any PBIX file.
2. Enable Power BI custom visual developer mode.
3. Add the Developer Visual.
4. Drag relevant columns/measures into the Copilot visual's Fields well.
5. Ask a question in the Copilot panel.

The visual can work with any dataset, but it can only analyze fields/data passed into the Copilot visual.

## Packaging

To create a `.pbiviz` package:

```powershell
cd frontend/custom_visual
npm run package
```

The package is generated in:

```text
frontend/custom_visual/dist/
```

## Runtime Context

The current custom visual sends:

- visual type and title
- selected fields/measures from the Copilot visual's Fields well
- up to 50 visible data points
- viewport metadata and row count

The API schema also supports these future/advanced context fields:

- report and page name
- visual id
- report/page/visual filters
- slicer selections
- selected data points
- optional dataset schema or semantic model metadata

Those advanced fields are not fully populated by the current Power BI custom visual yet.

## Notes

- `.env` is ignored by Git and should not be committed.
- The custom visual currently sends up to 50 visible data rows for fast local testing.
- Backend API base URL for local testing is `http://127.0.0.1:8000`.
