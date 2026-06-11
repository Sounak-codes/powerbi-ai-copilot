"""
Insights API routes.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from datetime import datetime

from models import InsightRequestModel
from analytics_engine.insight_generator import InsightGenerator
from app import get_orchestrator
from orchestration.orchestrator import Orchestrator
from config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/insights", tags=["insights"])

# Global insight generator
_insight_generator: Optional[InsightGenerator] = None


async def get_insight_generator() -> InsightGenerator:
    """Get insight generator instance."""
    global _insight_generator
    if _insight_generator is None:
        _insight_generator = InsightGenerator()
    return _insight_generator


@router.post("/generate")
async def generate_insights(
    request: InsightRequestModel,
    generator: InsightGenerator = Depends(get_insight_generator),
):
    """Generate insights for a report/page/visual."""
    try:
        insights = await generator.generate_insights(
            data={"report_id": request.report_id},
            depth=request.depth,
        )

        return {
            "status": "success",
            "insights": [insight.dict() for insight in insights],
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error generating insights: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate insights")


@router.get("/report/{report_id}")
async def get_report_insights(
    report_id: str,
    generator: InsightGenerator = Depends(get_insight_generator),
):
    """Get insights for a specific report."""
    try:
        # Mock data for demonstration
        insights = await generator.generate_insights(
            data={"report_id": report_id},
        )

        return {
            "report_id": report_id,
            "insights": [insight.dict() for insight in insights],
            "count": len(insights),
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error fetching report insights: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch insights")
