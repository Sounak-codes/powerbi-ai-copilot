"""
Prompt monitoring.

Tracks LLM prompt usage including tokens consumed, latency,
success rates, and prompt version tracking.
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
class PromptCallRecord:
    """Record of a single LLM prompt call."""

    prompt_name: str
    prompt_version: str
    timestamp: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None
    model: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt_name": self.prompt_name,
            "prompt_version": self.prompt_version,
            "timestamp": self.timestamp,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "latency_ms": round(self.latency_ms, 2),
            "success": self.success,
            "error": self.error,
            "model": self.model,
            "metadata": self.metadata,
        }


@dataclass
class PromptStats:
    """Aggregated statistics for a prompt."""

    prompt_name: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_tokens: int = 0
    avg_input_tokens: float = 0.0
    avg_output_tokens: float = 0.0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    success_rate: float = 0.0
    versions_used: List[str] = field(default_factory=list)
    last_called: str = ""
    error_types: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt_name": self.prompt_name,
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "total_tokens": self.total_tokens,
            "avg_input_tokens": round(self.avg_input_tokens, 1),
            "avg_output_tokens": round(self.avg_output_tokens, 1),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
            "success_rate": round(self.success_rate, 4),
            "versions_used": self.versions_used,
            "last_called": self.last_called,
            "error_types": self.error_types,
        }


@dataclass
class OverallPromptMetrics:
    """Overall metrics across all prompts."""

    total_calls: int = 0
    total_tokens_consumed: int = 0
    overall_success_rate: float = 0.0
    avg_latency_ms: float = 0.0
    prompts_tracked: int = 0
    calls_last_hour: int = 0
    tokens_last_hour: int = 0
    top_prompts_by_usage: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_calls": self.total_calls,
            "total_tokens_consumed": self.total_tokens_consumed,
            "overall_success_rate": round(self.overall_success_rate, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "prompts_tracked": self.prompts_tracked,
            "calls_last_hour": self.calls_last_hour,
            "tokens_last_hour": self.tokens_last_hour,
            "top_prompts_by_usage": self.top_prompts_by_usage,
        }


class PromptMonitor:
    """
    Monitors LLM prompt usage across the application.

    Tracks tokens consumed, latency, success rates, and prompt
    versions for each named prompt template. Thread-safe.
    """

    def __init__(self, max_records: int = 10000):
        """
        Initialize the prompt monitor.

        Args:
            max_records: Maximum call records to retain per prompt.
        """
        self._records: Dict[str, List[PromptCallRecord]] = defaultdict(list)
        self._max_records = max_records
        self._lock = threading.Lock()
        logger.info(f"PromptMonitor initialized (max_records={max_records})")

    def record_prompt_call(
        self,
        prompt_name: str,
        prompt_version: str = "1.0",
        input_tokens: int = 0,
        output_tokens: int = 0,
        latency_ms: float = 0.0,
        success: bool = True,
        error: Optional[str] = None,
        model: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PromptCallRecord:
        """
        Record an LLM prompt call.

        Args:
            prompt_name: Name/identifier of the prompt template.
            prompt_version: Version string of the prompt.
            input_tokens: Number of input tokens sent.
            output_tokens: Number of output tokens received.
            latency_ms: Call latency in milliseconds.
            success: Whether the call succeeded.
            error: Error message if the call failed.
            model: LLM model used.
            metadata: Additional metadata.

        Returns:
            The recorded PromptCallRecord.
        """
        record = PromptCallRecord(
            prompt_name=prompt_name,
            prompt_version=prompt_version,
            timestamp=datetime.utcnow().isoformat() + "Z",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            latency_ms=latency_ms,
            success=success,
            error=error,
            model=model,
            metadata=metadata or {},
        )

        with self._lock:
            self._records[prompt_name].append(record)

            # Trim old records
            if len(self._records[prompt_name]) > self._max_records:
                self._records[prompt_name] = self._records[prompt_name][-self._max_records:]

        logger.debug(
            f"Prompt call recorded: {prompt_name} v{prompt_version} "
            f"({record.total_tokens} tokens, {latency_ms:.0f}ms)"
        )
        return record

    def get_prompt_stats(
        self,
        prompt_name: Optional[str] = None,
    ) -> Dict[str, PromptStats]:
        """
        Get aggregated statistics for prompts.

        Args:
            prompt_name: Specific prompt to get stats for, or None for all.

        Returns:
            Dict mapping prompt names to their PromptStats.
        """
        with self._lock:
            if prompt_name:
                records_map = {prompt_name: list(self._records.get(prompt_name, []))}
            else:
                records_map = {k: list(v) for k, v in self._records.items()}

        stats: Dict[str, PromptStats] = {}

        for name, records in records_map.items():
            if not records:
                continue

            successful = [r for r in records if r.success]
            failed = [r for r in records if not r.success]
            latencies = [r.latency_ms for r in records if r.latency_ms > 0]

            # Calculate p95 latency
            p95 = 0.0
            if latencies:
                sorted_lat = sorted(latencies)
                idx = int(len(sorted_lat) * 0.95)
                idx = min(idx, len(sorted_lat) - 1)
                p95 = sorted_lat[idx]

            # Versions used
            versions = sorted(set(r.prompt_version for r in records))

            # Error types
            error_types: Dict[str, int] = defaultdict(int)
            for r in failed:
                error_key = (r.error or "unknown")[:50]
                error_types[error_key] += 1

            total_input = sum(r.input_tokens for r in records)
            total_output = sum(r.output_tokens for r in records)
            total_calls = len(records)

            stats[name] = PromptStats(
                prompt_name=name,
                total_calls=total_calls,
                successful_calls=len(successful),
                failed_calls=len(failed),
                total_tokens=sum(r.total_tokens for r in records),
                avg_input_tokens=total_input / total_calls if total_calls else 0,
                avg_output_tokens=total_output / total_calls if total_calls else 0,
                avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0,
                p95_latency_ms=p95,
                success_rate=len(successful) / total_calls if total_calls else 0,
                versions_used=versions,
                last_called=records[-1].timestamp if records else "",
                error_types=dict(error_types),
            )

        return stats

    def get_overall_metrics(self) -> OverallPromptMetrics:
        """
        Get overall metrics across all monitored prompts.

        Returns:
            OverallPromptMetrics with aggregate statistics.
        """
        with self._lock:
            all_records: List[PromptCallRecord] = []
            for records in self._records.values():
                all_records.extend(records)

        if not all_records:
            return OverallPromptMetrics()

        total_calls = len(all_records)
        successful = sum(1 for r in all_records if r.success)
        total_tokens = sum(r.total_tokens for r in all_records)
        latencies = [r.latency_ms for r in all_records if r.latency_ms > 0]

        # Calls in last hour
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent = [
            r for r in all_records
            if datetime.fromisoformat(r.timestamp.rstrip("Z")) > one_hour_ago
        ]
        calls_last_hour = len(recent)
        tokens_last_hour = sum(r.total_tokens for r in recent)

        # Top prompts by usage
        prompt_counts: Dict[str, int] = defaultdict(int)
        for r in all_records:
            prompt_counts[r.prompt_name] += 1

        top_prompts = sorted(prompt_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        return OverallPromptMetrics(
            total_calls=total_calls,
            total_tokens_consumed=total_tokens,
            overall_success_rate=successful / total_calls if total_calls else 0,
            avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0,
            prompts_tracked=len(self._records),
            calls_last_hour=calls_last_hour,
            tokens_last_hour=tokens_last_hour,
            top_prompts_by_usage=[
                {"prompt_name": name, "call_count": count}
                for name, count in top_prompts
            ],
        )

    def get_recent_calls(
        self,
        prompt_name: Optional[str] = None,
        count: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Get recent prompt calls.

        Args:
            prompt_name: Filter by prompt name, or None for all.
            count: Maximum number of records to return.

        Returns:
            List of recent call records.
        """
        with self._lock:
            if prompt_name:
                records = list(self._records.get(prompt_name, []))
            else:
                records = []
                for recs in self._records.values():
                    records.extend(recs)

        # Sort by timestamp descending
        records.sort(key=lambda r: r.timestamp, reverse=True)

        return [r.to_dict() for r in records[:count]]

    def clear(self, prompt_name: Optional[str] = None) -> None:
        """
        Clear recorded data.

        Args:
            prompt_name: Clear data for a specific prompt, or None for all.
        """
        with self._lock:
            if prompt_name:
                self._records.pop(prompt_name, None)
            else:
                self._records.clear()
        logger.info(f"Prompt monitoring data cleared: {prompt_name or 'all'}")
