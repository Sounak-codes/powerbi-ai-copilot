"""API routes package."""
from fastapi import APIRouter

from api.schemas import CopilotRequest, CopilotResponse
from api.routes.health import router as health_router
from services.analytics_service import build_analytics_response

# Create main router
router = APIRouter()

router.include_router(health_router)


@router.post("/ask", response_model=CopilotResponse)
def ask_copilot(request: CopilotRequest):
    """Answer a Power BI custom visual question."""
    return build_analytics_response(request)

__all__ = ["router"]
