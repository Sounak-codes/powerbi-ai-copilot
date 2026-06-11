"""
Pydantic models for chat data structures.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class Message(BaseModel):
    """A single message in a conversation."""
    id: str
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None


class ChatRequest(BaseModel):
    """Request for chat endpoint."""
    message: str
    session_id: str
    context: Optional[Dict[str, Any]] = None
    conversation_history: Optional[List[Message]] = None


class ChatResponse(BaseModel):
    """Response from chat endpoint."""
    message: str
    session_id: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None
    follow_up_questions: Optional[List[str]] = None


class Conversation(BaseModel):
    """A complete conversation."""
    id: str
    user_id: str
    session_id: str
    messages: List[Message]
    created_at: datetime
    updated_at: datetime
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "id": "conv_123",
                "user_id": "user_456",
                "session_id": "sess_789",
                "messages": [],
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
            }
        }
