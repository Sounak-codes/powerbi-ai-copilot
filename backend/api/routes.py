from fastapi import APIRouter

from api.schemas import CopilotRequest, CopilotResponse
from services.analytics_service import build_analytics_response


router = APIRouter()


@router.post("/ask", response_model=CopilotResponse)
def ask_copilot(request: CopilotRequest):
    return build_analytics_response(request)
