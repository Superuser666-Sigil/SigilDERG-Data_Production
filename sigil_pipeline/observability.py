"""
Observability infrastructure for enterprise-grade monitoring.

Provides structured logging, metrics collection, and tracing capabilities
for production-grade monitoring and debugging.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.6.0
"""

import json
import logging
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

# Try to import structlog for structured logging
try:
    import structlog
    from structlog.stdlib import BoundLogger as _BoundLogger

    STRUCTLOG_AVAILABLE = True
    BoundLogger = _BoundLogger  # type: ignore[misc]
except ImportError:
    STRUCTLOG_AVAILABLE = False
    BoundLogger = None  # type: ignore[assignment, misc]

logger = logging.getLogger(__name__)


def configure_structured_logging(
    log_level: str = "INFO",
    json_output: bool = False,
    log_file: Path | None = None,
) -> None:
    """
    Configure structured logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        json_output: Whether to output logs as JSON (for production)
        log_file: Optional path to write logs to file
    """
    if not STRUCTLOG_AVAILABLE:
        # Fallback to standard logging
        logging.basicConfig(
            level=getattr(logging, log_level.upper(), logging.INFO),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        logger.info("structlog not available, using standard logging")
        return

    # Configure processors based on output format
    shared_processors: list[Any] = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.contextvars.merge_contextvars,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if json_output:
        # JSON output for production/log aggregation
        shared_processors.append(structlog.processors.JSONRenderer())
    else:
        # Human-readable output for development
        shared_processors.append(
            structlog.dev.ConsoleRenderer(
                colors=True, exception_formatter=structlog.dev.plain_traceback
            )
        )

    structlog.configure(
        processors=shared_processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging to work with structlog
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(message)s",
        handlers=[logging.StreamHandler()],
    )

    # Add file handler if requested
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        logging.getLogger().addHandler(file_handler)


def get_logger(name: str) -> Any:
    """
    Get a structured logger with context binding.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Structured logger if structlog available, otherwise standard logger
    """
    if STRUCTLOG_AVAILABLE:
        return structlog.get_logger(name)
    return logging.getLogger(name)


@dataclass
class MetricSample:
    """A single metric sample with timestamp and labels."""

    name: str
    value: float
    timestamp: float
    labels: dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """
    Collects and exports pipeline metrics in Prometheus-compatible format.

    Thread-safe implementation for concurrent metric collection.
    """

    def __init__(self) -> None:
        """Initialize the metrics collector."""
        self._lock = threading.Lock()
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}
        self._metadata: dict[str, dict[str, str]] = {}

    def increment(
        self,
        name: str,
        value: float = 1.0,
        labels: dict[str, str] | None = None,
        help_text: str | None = None,
    ) -> None:
        """
        Increment a counter metric.

        Args:
            name: Metric name
            value: Value to add (default: 1)
            labels: Optional labels for the metric
            help_text: Optional help text for the metric
        """
        key = self._make_key(name, labels)
        with self._lock:
            self._counters[key] = self._counters.get(key, 0.0) + value
            if help_text:
                self._metadata[name] = {"type": "counter", "help": help_text}

    def gauge(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
        help_text: str | None = None,
    ) -> None:
        """
        Set a gauge metric.

        Args:
            name: Metric name
            value: Current value
            labels: Optional labels for the metric
            help_text: Optional help text for the metric
        """
        key = self._make_key(name, labels)
        with self._lock:
            self._gauges[key] = value
            if help_text:
                self._metadata[name] = {"type": "gauge", "help": help_text}

    def histogram(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
        help_text: str | None = None,
    ) -> None:
        """
        Record a histogram observation.

        Args:
            name: Metric name
            value: Observed value
            labels: Optional labels for the metric
            help_text: Optional help text for the metric
        """
        key = self._make_key(name, labels)
        with self._lock:
            if key not in self._histograms:
                self._histograms[key] = []
            self._histograms[key].append(value)
            if help_text:
                self._metadata[name] = {"type": "histogram", "help": help_text}

    @staticmethod
    def _make_key(name: str, labels: dict[str, str] | None) -> str:
        """Create a unique key for a metric with labels."""
        if labels:
            label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
            return f"{name}{{{label_str}}}"
        return name

    def get_counter(self, name: str, labels: dict[str, str] | None = None) -> float:
        """Get the current value of a counter."""
        key = self._make_key(name, labels)
        with self._lock:
            return self._counters.get(key, 0.0)

    def get_gauge(self, name: str, labels: dict[str, str] | None = None) -> float:
        """Get the current value of a gauge."""
        key = self._make_key(name, labels)
        with self._lock:
            return self._gauges.get(key, 0.0)

    def get_histogram_stats(
        self, name: str, labels: dict[str, str] | None = None
    ) -> dict[str, float]:
        """Get statistics for a histogram."""
        key = self._make_key(name, labels)
        with self._lock:
            values = self._histograms.get(key, [])
            if not values:
                return {"count": 0, "sum": 0.0, "min": 0.0, "max": 0.0, "avg": 0.0}
            return {
                "count": len(values),
                "sum": sum(values),
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values),
            }

    def export_prometheus(self) -> str:
        """
        Export metrics in Prometheus text format.

        Returns:
            Prometheus-formatted metrics string
        """
        lines: list[str] = []

        with self._lock:
            # Export counters
            for key, value in sorted(self._counters.items()):
                name = key.split("{")[0] if "{" in key else key
                meta = self._metadata.get(name, {})
                if meta.get("help"):
                    lines.append(f"# HELP sigil_{name} {meta['help']}")
                lines.append(f"# TYPE sigil_{name} counter")
                lines.append(f"sigil_{key} {value}")

            # Export gauges
            for key, value in sorted(self._gauges.items()):
                name = key.split("{")[0] if "{" in key else key
                meta = self._metadata.get(name, {})
                if meta.get("help"):
                    lines.append(f"# HELP sigil_{name} {meta['help']}")
                lines.append(f"# TYPE sigil_{name} gauge")
                lines.append(f"sigil_{key} {value}")

            # Export histograms
            for key, values in sorted(self._histograms.items()):
                name = key.split("{")[0] if "{" in key else key
                meta = self._metadata.get(name, {})
                if meta.get("help"):
                    lines.append(f"# HELP sigil_{name} {meta['help']}")
                lines.append(f"# TYPE sigil_{name} histogram")
                lines.append(f"sigil_{key}_count {len(values)}")
                lines.append(f"sigil_{key}_sum {sum(values)}")

        return "\n".join(lines)

    def export_json(self, path: Path) -> None:
        """
        Export metrics to a JSON file.

        Args:
            path: Path to write JSON metrics
        """
        with self._lock:
            data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {
                    key: self.get_histogram_stats(key.split("{")[0])
                    for key in self._histograms
                },
                "metadata": dict(self._metadata),
            }

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def reset(self) -> None:
        """Reset all metrics to initial state."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()


# Global metrics collector instance
_metrics: MetricsCollector | None = None
_metrics_lock = threading.Lock()


def get_metrics() -> MetricsCollector:
    """
    Get the global metrics collector instance.

    Returns:
        MetricsCollector singleton instance
    """
    global _metrics
    with _metrics_lock:
        if _metrics is None:
            _metrics = MetricsCollector()
        return _metrics


@contextmanager
def timed_operation(
    name: str,
    log: Any = None,
    labels: dict[str, str] | None = None,
) -> Iterator[None]:
    """
    Context manager for timing operations with logging and metrics.

    Args:
        name: Operation name for logging and metrics
        log: Optional logger to use (defaults to module logger)
        labels: Optional labels for the metric

    Yields:
        None

    Example:
        with timed_operation("fetch_crate", log=logger, labels={"crate": "serde"}):
            await fetch_crate("serde")
    """
    if log is None:
        log = logger

    metrics = get_metrics()
    start_time = time.perf_counter()

    # Log start
    if STRUCTLOG_AVAILABLE and hasattr(log, "bind"):
        bound_log = log.bind(operation=name)
        bound_log.info(f"{name}_started")
    else:
        log.info(f"{name} started")

    try:
        yield
        duration = time.perf_counter() - start_time

        # Record success metrics
        metrics.histogram(
            f"{name}_duration_seconds",
            duration,
            labels=labels,
            help_text=f"Duration of {name} operations in seconds",
        )
        metrics.increment(
            f"{name}_total",
            labels=labels,
            help_text=f"Total number of {name} operations",
        )

        # Log success
        if STRUCTLOG_AVAILABLE and hasattr(log, "bind"):
            bound_log = log.bind(operation=name, duration_seconds=round(duration, 4))
            bound_log.info(f"{name}_completed")
        else:
            log.info(f"{name} completed in {duration:.4f}s")

    except Exception as e:
        duration = time.perf_counter() - start_time

        # Record error metrics
        error_labels = dict(labels) if labels else {}
        error_labels["error_type"] = type(e).__name__
        metrics.increment(
            f"{name}_errors_total",
            labels=error_labels,
            help_text=f"Total number of {name} errors",
        )

        # Log error
        if STRUCTLOG_AVAILABLE and hasattr(log, "bind"):
            bound_log = log.bind(
                operation=name,
                duration_seconds=round(duration, 4),
                error=str(e),
                error_type=type(e).__name__,
            )
            bound_log.error(f"{name}_failed")
        else:
            log.error(f"{name} failed after {duration:.4f}s: {e}")

        raise


class OperationTracker:
    """
    Track long-running operations with progress reporting.

    Useful for pipeline runs that process many items.
    """

    def __init__(
        self,
        operation_name: str,
        total_items: int,
        log: Any = None,
    ) -> None:
        """
        Initialize the operation tracker.

        Args:
            operation_name: Name of the operation being tracked
            total_items: Total number of items to process
            log: Optional logger to use
        """
        self.operation_name = operation_name
        self.total_items = total_items
        self.log = log or logger
        self.processed = 0
        self.succeeded = 0
        self.failed = 0
        self.start_time = time.perf_counter()
        self._lock = threading.Lock()

    def record_success(self) -> None:
        """Record a successful item processing."""
        with self._lock:
            self.processed += 1
            self.succeeded += 1
            self._log_progress()

    def record_failure(self, error: str | None = None) -> None:
        """Record a failed item processing."""
        with self._lock:
            self.processed += 1
            self.failed += 1
            if error:
                self.log.warning(
                    f"{self.operation_name} item failed: {error}",
                    extra={"processed": self.processed, "total": self.total_items},
                )
            self._log_progress()

    def _log_progress(self) -> None:
        """Log progress at regular intervals."""
        if (
            self.processed % max(1, self.total_items // 10) == 0
            or self.processed == self.total_items
        ):
            elapsed = time.perf_counter() - self.start_time
            rate = self.processed / elapsed if elapsed > 0 else 0
            eta = (self.total_items - self.processed) / rate if rate > 0 else 0

            self.log.info(
                f"{self.operation_name} progress: {self.processed}/{self.total_items} "
                f"({100 * self.processed / self.total_items:.1f}%) - "
                f"{self.succeeded} succeeded, {self.failed} failed - "
                f"ETA: {eta:.0f}s"
            )

    def summary(self) -> dict[str, Any]:
        """Get a summary of the operation."""
        elapsed = time.perf_counter() - self.start_time
        return {
            "operation": self.operation_name,
            "total_items": self.total_items,
            "processed": self.processed,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "success_rate": self.succeeded / max(1, self.processed),
            "elapsed_seconds": round(elapsed, 2),
            "items_per_second": round(self.processed / max(0.001, elapsed), 2),
        }
