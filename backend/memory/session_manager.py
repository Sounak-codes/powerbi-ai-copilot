"""
Session manager for handling user sessions.
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from config import get_settings, get_logger

settings = get_settings()
logger = get_logger(__name__)


class Session:
    """User session."""

    def __init__(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        report_id: Optional[str] = None,
    ):
        self.session_id = session_id or str(uuid.uuid4())
        self.user_id = user_id
        self.report_id = report_id
        self.created_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self.expired_at = self.created_at + timedelta(
            seconds=settings.session_timeout
        )
        self.metadata: Dict[str, Any] = {}

    def is_expired(self) -> bool:
        """Check if session is expired."""
        return datetime.utcnow() > self.expired_at

    def refresh(self):
        """Refresh session timeout."""
        self.last_activity = datetime.utcnow()
        self.expired_at = self.last_activity + timedelta(
            seconds=settings.session_timeout
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "report_id": self.report_id,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "expired_at": self.expired_at.isoformat(),
            "is_expired": self.is_expired(),
        }


class SessionManager:
    """Manage user sessions."""

    def __init__(self):
        self.sessions: Dict[str, Session] = {}

    def create_session(
        self, user_id: str, report_id: Optional[str] = None
    ) -> Session:
        """Create a new session."""
        session = Session(user_id, report_id=report_id)
        self.sessions[session.session_id] = session
        logger.info(f"Created session {session.session_id} for user {user_id}")
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        session = self.sessions.get(session_id)

        if session and session.is_expired():
            self.delete_session(session_id)
            return None

        if session:
            session.refresh()

        return session

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Deleted session {session_id}")
            return True
        return False

    def cleanup_expired_sessions(self):
        """Remove all expired sessions."""
        expired_ids = [
            sid for sid, s in self.sessions.items() if s.is_expired()
        ]
        for sid in expired_ids:
            self.delete_session(sid)
        logger.info(f"Cleaned up {len(expired_ids)} expired sessions")

    def get_active_sessions_count(self) -> int:
        """Get count of active sessions."""
        self.cleanup_expired_sessions()
        return len(self.sessions)
