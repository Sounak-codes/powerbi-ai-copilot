"""
Chat API routes.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
import uuid
from datetime import datetime

from models import ChatRequestModel, ChatResponseModel
from schemas import ChatRequest, ChatResponse
from orchestration.orchestrator import Orchestrator
from app import get_orchestrator
from config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: ChatRequestModel,
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    """Send a chat message and get a response."""
    try:
        # Ensure session exists
        session = orchestrator.get_session(request.session_id)
        if not session:
            # Create new session if it doesn't exist
            session = orchestrator.create_session(
                user_id="default_user",
                report_id=None,
            )

        # Handle message through orchestrator
        result = await orchestrator.handle_user_message(
            message=request.message,
            session_id=request.session_id,
            context=request.context,
        )

        if result["status"] == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))

        return ChatResponse(
            message=result.get("message", ""),
            session_id=request.session_id,
            timestamp=datetime.utcnow(),
            metadata={
                "agent": result.get("agent"),
                "intent": result.get("intent"),
            },
            follow_up_questions=result.get("follow_up_questions"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/session")
async def create_session(
    user_id: str = Query(...),
    report_id: Optional[str] = Query(None),
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    """Create a new chat session."""
    try:
        session = orchestrator.create_session(user_id, report_id)
        return {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "created_at": session.created_at.isoformat(),
            "expires_at": session.expired_at.isoformat(),
        }
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise HTTPException(status_code=500, detail="Failed to create session")


@router.get("/session/{session_id}")
async def get_session(
    session_id: str,
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    """Get session information."""
    try:
        session = orchestrator.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        return session.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/history/{session_id}")
async def get_conversation_history(
    session_id: str,
    limit: Optional[int] = Query(None),
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    """Get conversation history for a session."""
    try:
        history = orchestrator.get_conversation_history(session_id, limit)
        return {
            "session_id": session_id,
            "messages": history,
            "total": len(history),
        }
    except Exception as e:
        logger.error(f"Error getting conversation history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
