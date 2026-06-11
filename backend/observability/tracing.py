"""
Distributed tracing.

Provides trace/span hierarchy for tracking request flows across
the application. Each trace contains multiple spans representing
individual operations.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import uuid
import threading

from config import get_logger
from llm.providers.provider_factory import ProviderFactory

logger = get_logger(__name__)


@dataclass
class Span:
    """A single span within a trace."""

    span_id: str
    trace_id: str
    operation_name: str
    parent_span_id: Optional[str] = None
    start_time: str = ""
    end_time: Optional[str] = None
    duration_ms: float = 0.0
    status: str = "in_progress"  # "in_progress", "completed", "error"
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "operation_name": self.operation_name,
            "parent_span_id": self.parent_span_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": round(self.duration_ms, 2),
            "status": self.status,
            "attributes": self.attributes,
            "events": self.events,
        }


@dataclass
class Trace:
    """A complete trace containing multiple spans."""

    trace_id: str
    root_operation: str
    start_time: str
    end_time: Optional[str] = None
    total_duration_ms: float = 0.0
    status: str = "in_progress"
    spans: List[Span] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "root_operation": self.root_operation,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_duration_ms": round(self.total_duration_ms, 2),
            "status": self.status,
            "span_count": len(self.spans),
            "spans": [s.to_dict() for s in self.spans],
            "metadata": self.metadata,
        }


class Tracer:
    """
    Distributed tracing for request flow tracking.

    Creates trace/span hierarchies to track operations across
    the application. Thread-safe with in-memory storage.
    """

    def __init__(self, max_traces: int = 1000):
        """
        Initialize the tracer.

        Args:
            max_traces: Maximum number of completed traces to retain.
        """
        self._traces: Dict[str, Trace] = {}
        self._active_spans: Dict[str, Span] = {}
        self._max_traces = max_traces
        self._lock = threading.Lock()
        logger.info(f"Tracer initialized (max_traces={max_traces})")

    def _generate_id(self) -> str:
        """Generate a unique ID for traces and spans."""
        return uuid.uuid4().hex[:16]

    def start_trace(
        self,
        operation_name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Start a new trace.

        Args:
            operation_name: Name of the root operation.
            metadata: Optional metadata for the trace.

        Returns:
            The trace_id for the new trace.
        """
        trace_id = self._generate_id()
        now = datetime.utcnow().isoformat() + "Z"

        trace = Trace(
            trace_id=trace_id,
            root_operation=operation_name,
            start_time=now,
            metadata=metadata or {},
        )

        with self._lock:
            self._traces[trace_id] = trace

        logger.debug(f"Trace started: {trace_id} ({operation_name})")
        return trace_id

    def start_span(
        self,
        trace_id: str,
        operation_name: str,
        parent_span_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Start a new span within a trace.

        Args:
            trace_id: The trace this span belongs to.
            operation_name: Name of the operation.
            parent_span_id: Optional parent span for nesting.
            attributes: Optional span attributes.

        Returns:
            The span_id for the new span.
        """
        span_id = self._generate_id()
        now = datetime.utcnow().isoformat() + "Z"

        span = Span(
            span_id=span_id,
            trace_id=trace_id,
            operation_name=operation_name,
            parent_span_id=parent_span_id,
            start_time=now,
            attributes=attributes or {},
        )

        with self._lock:
            self._active_spans[span_id] = span
            if trace_id in self._traces:
                self._traces[trace_id].spans.append(span)

        logger.debug(f"Span started: {span_id} ({operation_name}) in trace {trace_id}")
        return span_id

    def end_span(
        self,
        span_id: str,
        status: str = "completed",
        attributes: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> Optional[Span]:
        """
        End an active span.

        Args:
            span_id: The span to end.
            status: Final status ("completed" or "error").
            attributes: Additional attributes to add.
            error: Error message if the span failed.

        Returns:
            The completed Span, or None if not found.
        """
        now = datetime.utcnow().isoformat() + "Z"

        with self._lock:
            span = self._active_spans.pop(span_id, None)

        if span is None:
            logger.warning(f"Span not found: {span_id}")
            return None

        span.end_time = now
        span.status = "error" if error else status

        if attributes:
            span.attributes.update(attributes)
        if error:
            span.attributes["error"] = error
            span.events.append({"type": "error", "message": error, "timestamp": now})

        # Calculate duration
        start = datetime.fromisoformat(span.start_time.rstrip("Z"))
        end = datetime.fromisoformat(now.rstrip("Z"))
        span.duration_ms = (end - start).total_seconds() * 1000

        logger.debug(f"Span ended: {span_id} ({span.duration_ms:.1f}ms, {span.status})")
        return span

    def end_trace(self, trace_id: str) -> Optional[Trace]:
        """
        End a trace and compute its total duration.

        Args:
            trace_id: The trace to end.

        Returns:
            The completed Trace, or None if not found.
        """
        now = datetime.utcnow().isoformat() + "Z"

        with self._lock:
            trace = self._traces.get(trace_id)

        if trace is None:
            logger.warning(f"Trace not found: {trace_id}")
            return None

        trace.end_time = now

        # End any active spans in this trace
        with self._lock:
            active_in_trace = [
                sid for sid, s in self._active_spans.items()
                if s.trace_id == trace_id
            ]

        for span_id in active_in_trace:
            self.end_span(span_id, status="completed")

        # Calculate total duration
        start = datetime.fromisoformat(trace.start_time.rstrip("Z"))
        end = datetime.fromisoformat(now.rstrip("Z"))
        trace.total_duration_ms = (end - start).total_seconds() * 1000

        # Determine status
        has_errors = any(s.status == "error" for s in trace.spans)
        trace.status = "error" if has_errors else "completed"

        # Evict old traces
        with self._lock:
            if len(self._traces) > self._max_traces:
                completed = [
                    (tid, t) for tid, t in self._traces.items()
                    if t.status != "in_progress" and tid != trace_id
                ]
                completed.sort(key=lambda x: x[1].start_time)
                for tid, _ in completed[:len(completed) // 2]:
                    del self._traces[tid]

        logger.debug(f"Trace ended: {trace_id} ({trace.total_duration_ms:.1f}ms, {trace.status})")
        return trace

    def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a trace by its ID.

        Args:
            trace_id: The trace ID to look up.

        Returns:
            Trace as dictionary, or None if not found.
        """
        with self._lock:
            trace = self._traces.get(trace_id)

        if trace is None:
            return None

        return trace.to_dict()

    def add_span_event(
        self,
        span_id: str,
        event_name: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add an event annotation to an active span.

        Args:
            span_id: The span to annotate.
            event_name: Name of the event.
            attributes: Optional event attributes.
        """
        with self._lock:
            span = self._active_spans.get(span_id)

        if span:
            span.events.append({
                "type": event_name,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                **(attributes or {}),
            })

    def get_active_traces(self) -> List[Dict[str, Any]]:
        """Get all currently active (in-progress) traces."""
        with self._lock:
            active = [
                t.to_dict() for t in self._traces.values()
                if t.status == "in_progress"
            ]
        return active

    def get_recent_traces(
        self,
        count: int = 20,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get recent traces with optional status filter.

        Args:
            count: Maximum number of traces to return.
            status: Filter by status ("completed", "error", "in_progress").

        Returns:
            List of recent traces as dictionaries.
        """
        with self._lock:
            traces = list(self._traces.values())

        if status:
            traces = [t for t in traces if t.status == status]

        # Sort by start time descending
        traces.sort(key=lambda t: t.start_time, reverse=True)

        return [t.to_dict() for t in traces[:count]]

    def get_trace_stats(self) -> Dict[str, Any]:
        """Get overall tracing statistics."""
        with self._lock:
            traces = list(self._traces.values())
            active_span_count = len(self._active_spans)

        completed = [t for t in traces if t.status == "completed"]
        errored = [t for t in traces if t.status == "error"]

        avg_duration = 0.0
        if completed:
            avg_duration = sum(t.total_duration_ms for t in completed) / len(completed)

        return {
            "total_traces": len(traces),
            "active_traces": sum(1 for t in traces if t.status == "in_progress"),
            "completed_traces": len(completed),
            "errored_traces": len(errored),
            "active_spans": active_span_count,
            "avg_trace_duration_ms": round(avg_duration, 2),
        }
