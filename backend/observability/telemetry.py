"""
Telemetry collector.

Collects application events (agent executions, LLM calls, user
interactions) and provides metrics aggregation. Uses in-memory storage.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import threading

from config import get_logger
from llm.providers.provider_factory import ProviderFactory

logger = get_logger(__name__)


@dataclass
class TelemetryEvent:
    """A single telemetry event."""

    event_type: str  # "agent_execution", "llm_call", "user_interaction"
    timestamp: str
    data: Dict[str, Any] = field(default_factory=dict)
    session_id: str = ""
    duration_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "data": self.data,
            "session_id": self.session_id,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "error": self.error,
        }


@dataclass
class TelemetryMetrics:
    """Aggregated telemetry metrics."""

    total_events: int = 0
    events_by_type: Dict[str, int] = field(default_factory=dict)
    success_rate: float = 0.0
    avg_duration_ms: float = 0.0
    error_count: int = 0
    active_sessions: int = 0
    events_last_hour: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_events": self.total_events,
            "events_by_type": self.events_by_type,
            "success_rate": round(self.success_rate, 4),
            "avg_duration_ms": round(self.avg_duration_ms, 2),
            "error_count": self.error_count,
            "active_sessions": self.active_sessions,
            "events_last_hour": self.events_last_hour,
        }


class TelemetryCollector:
    """
    Collects and aggregates application telemetry events.

    Thread-safe in-memory event store with metrics computation.
    Supports event types: agent_execution, llm_call, user_interaction.
    """

    VALID_EVENT_TYPES = {"agent_execution", "llm_call", "user_interaction", "error", "system"}

    def __init__(self, max_events: int = 10000):
        """
        Initialize the telemetry collector.

        Args:
            max_events: Maximum number of events to retain in memory.
        """
        self._events: List[TelemetryEvent] = []
        self._max_events = max_events
        self._lock = threading.Lock()
        self._sessions: Dict[str, datetime] = {}
        logger.info(f"TelemetryCollector initialized (max_events={max_events})")

    def record_event(
        self,
        event_type: str,
        data: Optional[Dict[str, Any]] = None,
        session_id: str = "",
        duration_ms: float = 0.0,
        success: bool = True,
        error: Optional[str] = None,
    ) -> TelemetryEvent:
        """
        Record a telemetry event.

        Args:
            event_type: Type of event (agent_execution, llm_call, user_interaction).
            data: Additional event data.
            session_id: Session identifier for the event.
            duration_ms: Duration of the operation in milliseconds.
            success: Whether the operation succeeded.
            error: Error message if the operation failed.

        Returns:
            The recorded TelemetryEvent.
        """
        if event_type not in self.VALID_EVENT_TYPES:
            logger.warning(f"Unknown event type: {event_type}, recording anyway")

        event = TelemetryEvent(
            event_type=event_type,
            timestamp=datetime.utcnow().isoformat() + "Z",
            data=data or {},
            session_id=session_id,
            duration_ms=duration_ms,
            success=success,
            error=error,
        )

        with self._lock:
            self._events.append(event)

            # Track active sessions
            if session_id:
                self._sessions[session_id] = datetime.utcnow()

            # Evict oldest events if over limit
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events:]

        logger.debug(f"Event recorded: {event_type} (session={session_id})")
        return event

    def get_metrics(self) -> TelemetryMetrics:
        """
        Compute aggregated metrics from collected events.

        Returns:
            TelemetryMetrics with counts, rates, and averages.
        """
        with self._lock:
            events = list(self._events)
            sessions = dict(self._sessions)

        if not events:
            return TelemetryMetrics()

        total = len(events)
        success_count = sum(1 for e in events if e.success)
        error_count = sum(1 for e in events if not e.success)

        # Events by type
        events_by_type: Dict[str, int] = defaultdict(int)
        for e in events:
            events_by_type[e.event_type] += 1

        # Average duration (only for events with duration > 0)
        durations = [e.duration_ms for e in events if e.duration_ms > 0]
        avg_duration = sum(durations) / len(durations) if durations else 0.0

        # Events in last hour
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        events_last_hour = sum(
            1 for e in events
            if datetime.fromisoformat(e.timestamp.rstrip("Z")) > one_hour_ago
        )

        # Active sessions (activity in last 30 minutes)
        thirty_min_ago = datetime.utcnow() - timedelta(minutes=30)
        active_sessions = sum(
            1 for last_seen in sessions.values() if last_seen > thirty_min_ago
        )

        return TelemetryMetrics(
            total_events=total,
            events_by_type=dict(events_by_type),
            success_rate=success_count / total if total > 0 else 0.0,
            avg_duration_ms=avg_duration,
            error_count=error_count,
            active_sessions=active_sessions,
            events_last_hour=events_last_hour,
        )

    def get_recent_events(
        self,
        count: int = 50,
        event_type: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get recent telemetry events with optional filtering.

        Args:
            count: Maximum number of events to return.
            event_type: Filter by event type.
            session_id: Filter by session ID.

        Returns:
            List of recent events as dictionaries.
        """
        with self._lock:
            events = list(self._events)

        # Apply filters
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if session_id:
            events = [e for e in events if e.session_id == session_id]

        # Return most recent
        recent = events[-count:]
        recent.reverse()

        return [e.to_dict() for e in recent]

    def get_error_summary(self) -> Dict[str, Any]:
        """Get a summary of recent errors."""
        with self._lock:
            errors = [e for e in self._events if not e.success]

        error_types: Dict[str, int] = defaultdict(int)
        for e in errors:
            error_msg = e.error or "unknown"
            # Group by first 50 chars of error
            key = error_msg[:50]
            error_types[key] += 1

        return {
            "total_errors": len(errors),
            "error_groups": dict(error_types),
            "recent_errors": [e.to_dict() for e in errors[-10:]],
        }

    def clear(self) -> None:
        """Clear all collected events."""
        with self._lock:
            self._events.clear()
            self._sessions.clear()
        logger.info("Telemetry data cleared")
