"""
Metrics collector.

Tracks application metrics including counters (requests, errors),
histograms (latency distributions), and gauges (active sessions).
Thread-safe in-memory implementation.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import threading
import math

from config import get_logger
from llm.providers.provider_factory import ProviderFactory

logger = get_logger(__name__)


@dataclass
class CounterMetric:
    """A monotonically increasing counter."""

    name: str
    value: int = 0
    labels: Dict[str, str] = field(default_factory=dict)
    last_updated: str = ""


@dataclass
class HistogramMetric:
    """A histogram tracking value distribution."""

    name: str
    values: List[float] = field(default_factory=list)
    count: int = 0
    total: float = 0.0
    min_value: float = float("inf")
    max_value: float = float("-inf")
    labels: Dict[str, str] = field(default_factory=dict)

    @property
    def mean(self) -> float:
        """Calculate mean of recorded values."""
        return self.total / self.count if self.count > 0 else 0.0

    @property
    def p50(self) -> float:
        """Calculate 50th percentile."""
        return self._percentile(50)

    @property
    def p95(self) -> float:
        """Calculate 95th percentile."""
        return self._percentile(95)

    @property
    def p99(self) -> float:
        """Calculate 99th percentile."""
        return self._percentile(99)

    def _percentile(self, pct: float) -> float:
        """Calculate a percentile from recorded values."""
        if not self.values:
            return 0.0
        sorted_vals = sorted(self.values)
        idx = math.ceil(len(sorted_vals) * pct / 100) - 1
        idx = max(0, min(idx, len(sorted_vals) - 1))
        return sorted_vals[idx]


@dataclass
class GaugeMetric:
    """A gauge that can go up or down."""

    name: str
    value: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)
    last_updated: str = ""


@dataclass
class MetricsSummary:
    """Summary of all collected metrics."""

    counters: Dict[str, int] = field(default_factory=dict)
    histograms: Dict[str, Dict[str, float]] = field(default_factory=dict)
    gauges: Dict[str, float] = field(default_factory=dict)
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "counters": self.counters,
            "histograms": self.histograms,
            "gauges": self.gauges,
            "timestamp": self.timestamp,
        }


class MetricsCollector:
    """
    Collects application metrics: counters, histograms, and gauges.

    Thread-safe in-memory metrics store with support for labeled metrics,
    percentile calculations, and aggregation.
    """

    def __init__(self, histogram_max_values: int = 5000):
        """
        Initialize the metrics collector.

        Args:
            histogram_max_values: Max values to retain per histogram for percentile calculations.
        """
        self._counters: Dict[str, CounterMetric] = {}
        self._histograms: Dict[str, HistogramMetric] = {}
        self._gauges: Dict[str, GaugeMetric] = {}
        self._histogram_max_values = histogram_max_values
        self._lock = threading.Lock()
        logger.info("MetricsCollector initialized")

    def _make_key(self, name: str, labels: Optional[Dict[str, str]] = None) -> str:
        """Create a unique key for a metric with labels."""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def increment(
        self,
        name: str,
        value: int = 1,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Increment a counter metric.

        Args:
            name: Counter name (e.g., "requests_total", "errors_total").
            value: Amount to increment by.
            labels: Optional labels for metric dimensions.
        """
        key = self._make_key(name, labels)
        now = datetime.utcnow().isoformat() + "Z"

        with self._lock:
            if key not in self._counters:
                self._counters[key] = CounterMetric(
                    name=name, labels=labels or {}
                )
            self._counters[key].value += value
            self._counters[key].last_updated = now

    def record_duration(
        self,
        name: str,
        duration_ms: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Record a duration value in a histogram.

        Args:
            name: Histogram name (e.g., "request_latency_ms", "llm_call_duration_ms").
            duration_ms: Duration in milliseconds.
            labels: Optional labels for metric dimensions.
        """
        key = self._make_key(name, labels)

        with self._lock:
            if key not in self._histograms:
                self._histograms[key] = HistogramMetric(
                    name=name, labels=labels or {}
                )

            hist = self._histograms[key]
            hist.values.append(duration_ms)
            hist.count += 1
            hist.total += duration_ms
            hist.min_value = min(hist.min_value, duration_ms)
            hist.max_value = max(hist.max_value, duration_ms)

            # Trim values if exceeding max
            if len(hist.values) > self._histogram_max_values:
                hist.values = hist.values[-self._histogram_max_values:]

    def set_gauge(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Set a gauge metric value.

        Args:
            name: Gauge name (e.g., "active_sessions", "queue_depth").
            value: Current value.
            labels: Optional labels for metric dimensions.
        """
        key = self._make_key(name, labels)
        now = datetime.utcnow().isoformat() + "Z"

        with self._lock:
            if key not in self._gauges:
                self._gauges[key] = GaugeMetric(name=name, labels=labels or {})
            self._gauges[key].value = value
            self._gauges[key].last_updated = now

    def increment_gauge(
        self,
        name: str,
        value: float = 1.0,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Increment a gauge value."""
        key = self._make_key(name, labels)
        now = datetime.utcnow().isoformat() + "Z"

        with self._lock:
            if key not in self._gauges:
                self._gauges[key] = GaugeMetric(name=name, labels=labels or {})
            self._gauges[key].value += value
            self._gauges[key].last_updated = now

    def decrement_gauge(
        self,
        name: str,
        value: float = 1.0,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Decrement a gauge value."""
        key = self._make_key(name, labels)
        now = datetime.utcnow().isoformat() + "Z"

        with self._lock:
            if key not in self._gauges:
                self._gauges[key] = GaugeMetric(name=name, labels=labels or {})
            self._gauges[key].value -= value
            self._gauges[key].last_updated = now

    def get_counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> int:
        """Get the current value of a counter."""
        key = self._make_key(name, labels)
        with self._lock:
            counter = self._counters.get(key)
        return counter.value if counter else 0

    def get_histogram_stats(
        self, name: str, labels: Optional[Dict[str, str]] = None
    ) -> Dict[str, float]:
        """Get statistics for a histogram."""
        key = self._make_key(name, labels)
        with self._lock:
            hist = self._histograms.get(key)

        if hist is None or hist.count == 0:
            return {"count": 0, "mean": 0.0, "min": 0.0, "max": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0}

        return {
            "count": hist.count,
            "mean": round(hist.mean, 2),
            "min": round(hist.min_value, 2),
            "max": round(hist.max_value, 2),
            "p50": round(hist.p50, 2),
            "p95": round(hist.p95, 2),
            "p99": round(hist.p99, 2),
        }

    def get_gauge(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """Get the current value of a gauge."""
        key = self._make_key(name, labels)
        with self._lock:
            gauge = self._gauges.get(key)
        return gauge.value if gauge else 0.0

    def get_all_metrics(self) -> MetricsSummary:
        """
        Get a summary of all collected metrics.

        Returns:
            MetricsSummary with all counters, histograms, and gauges.
        """
        with self._lock:
            counters = {key: c.value for key, c in self._counters.items()}
            histograms = {}
            for key, h in self._histograms.items():
                if h.count > 0:
                    histograms[key] = {
                        "count": h.count,
                        "mean": round(h.mean, 2),
                        "min": round(h.min_value, 2),
                        "max": round(h.max_value, 2),
                        "p50": round(h.p50, 2),
                        "p95": round(h.p95, 2),
                        "p99": round(h.p99, 2),
                    }
            gauges = {key: g.value for key, g in self._gauges.items()}

        return MetricsSummary(
            counters=counters,
            histograms=histograms,
            gauges=gauges,
            timestamp=datetime.utcnow().isoformat() + "Z",
        )

    def reset(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._counters.clear()
            self._histograms.clear()
            self._gauges.clear()
        logger.info("All metrics reset")
