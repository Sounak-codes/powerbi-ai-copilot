"""
Health check and status API routes.
"""
from fastapi import APIRouter
from datetime import datetime

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "database": "operational",
            "cache": "operational",
            "llm": "operational",
        },
    }


@router.get("/status")
async def get_status():
    """Get application status."""
    return {
        "application": "Power BI AI Copilot",
        "status": "running",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }
