"""
Main entry point for the Power BI AI Copilot backend.
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from config import get_settings, setup_logging, get_logger
from api.routes import router as api_router
from orchestration.orchestrator import Orchestrator
from agents.rag_agent.agent import RAGAgent
from agents.analytics_agent.agent import AnalyticsAgent

# Setup logging
setup_logging()
logger = get_logger(__name__)

settings = get_settings()

# Global orchestrator
_orchestrator: Orchestrator = None


def get_orchestrator() -> Orchestrator:
    """Get the global orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    logger.info("=" * 60)
    logger.info("Power BI AI Copilot - Starting Up")
    logger.info("=" * 60)
    
    # Initialize orchestrator and agents
    orchestrator = get_orchestrator()
    
    # Register agents
    logger.info("Registering agents...")
    orchestrator.register_agent("rag_agent", RAGAgent())
    orchestrator.register_agent("analytics_agent", AnalyticsAgent())
    
    logger.info("Orchestrator initialized with agents")
    logger.info(f"API running on {settings.host}:{settings.port}")
    
    yield
    
    logger.info("=" * 60)
    logger.info("Power BI AI Copilot - Shutting Down")
    logger.info("=" * 60)


# Create FastAPI app
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="AI-powered analytics copilot for Power BI",
    debug=settings.debug,
    lifespan=lifespan,
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "*.example.com"],
)

# Include API routes
app.include_router(api_router, prefix="/api")


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.api_title,
        "version": settings.api_version,
        "status": "running",
        "docs": "/docs",
    }


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.api_title,
    }


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting {settings.api_title} v{settings.api_version}")
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        workers=settings.workers,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
