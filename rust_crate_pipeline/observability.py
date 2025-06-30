"""
Observability module for the Rust Crate Pipeline.

Provides structured logging, metrics collection, and distributed tracing
capabilities for production monitoring and debugging.
"""

import functools
import json
import logging
import time
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, TypeVar

# Try to import OpenTelemetry components
try:
    from opentelemetry import metrics, trace
    from opentelemetry.metrics import Meter
    from opentelemetry.trace import Span, Tracer
    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False
    Tracer = Any  # type: ignore
    Span = Any  # type: ignore
    Meter = Any  # type: ignore


T = TypeVar('T')


@dataclass
class MetricTags:
    """Standard metric tags for consistency across the pipeline."""
    service: str = "rust-crate-pipeline"
    environment: str = field(default_factory=lambda: "development")
    version: str = field(default_factory=lambda: "1.0.0")
    additional: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary for metric systems."""
        base = {
            "service": self.service,
            "environment": self.environment,
            "version": self.version
        }
        base.update(self.additional)
        return base


class StructuredLogger:
    """Structured logging with consistent formatting and context."""

    def __init__(self, name: str,
                 base_context: Optional[Dict[str, Any]] = None):
        self.logger = logging.getLogger(name)
        self.base_context = base_context or {}

    def _log(self, level: str, message: str, **kwargs):
        """Internal logging method with structured context."""
        context = {**self.base_context, **kwargs}

        # Add standard fields
        context.update({
            "timestamp": time.time(),
            "logger": self.logger.name,
            "level": level,
            "message": message
        })

        # Log as JSON for machine parsing
        self.logger.log(
            getattr(logging, level.upper()),
            json.dumps(context, default=str)
        )

    def debug(self, message: str, **kwargs):
        self._log("debug", message, **kwargs)

    def info(self, message: str, **kwargs):
        self._log("info", message, **kwargs)

    def warning(self, message: str, **kwargs):
        self._log("warning", message, **kwargs)

    def error(self, message: str, error: Optional[Exception] = None, **kwargs):
        if error:
            kwargs["error_type"] = type(error).__name__
            kwargs["error_message"] = str(error)
        self._log("error", message, **kwargs)

    def with_context(self, **additional_context) -> 'StructuredLogger':
        """Create a new logger with additional context."""
        new_context = {**self.base_context, **additional_context}
        return StructuredLogger(self.logger.name, new_context)


class MetricsCollector:
    """Collects and reports metrics for monitoring."""

    def __init__(self, namespace: str = "rust_crate_pipeline"):
        self.namespace = namespace
        self.metrics: Dict[str, Any] = {}

        if OPENTELEMETRY_AVAILABLE:
            self.meter = metrics.get_meter(namespace)
            self._init_standard_metrics()
        else:
            self.meter = None

    def _init_standard_metrics(self):
        """Initialize standard metrics used across the pipeline."""
        if not self.meter:
            return

        self.metrics["requests_total"] = self.meter.create_counter(
            "requests_total",
            description="Total number of API requests"
        )

        self.metrics["request_duration"] = self.meter.create_histogram(
            "request_duration_seconds",
            description="Request duration in seconds"
        )

        self.metrics["enrichment_total"] = self.meter.create_counter(
            "enrichment_total",
            description="Total number of crate enrichments"
        )

        self.metrics["errors_total"] = self.meter.create_counter(
            "errors_total",
            description="Total number of errors"
        )

    def increment(self, metric_name: str, value: int = 1,
                  tags: Optional[Dict[str, str]] = None):
        """Increment a counter metric."""
        if self.meter and metric_name in self.metrics:
            self.metrics[metric_name].add(value, tags or {})

    def record(self, metric_name: str, value: float,
               tags: Optional[Dict[str, str]] = None):
        """Record a value for a histogram metric."""
        if self.meter and metric_name in self.metrics:
            self.metrics[metric_name].record(value, tags or {})

    @contextmanager
    def timer(self, metric_name: str, tags: Optional[Dict[str, str]] = None):
        """Context manager to time operations."""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.record(metric_name, duration, tags)


class TracingManager:
    """Manages distributed tracing for the pipeline."""

    def __init__(self, service_name: str = "rust-crate-pipeline"):
        self.service_name = service_name

        if OPENTELEMETRY_AVAILABLE:
            self.tracer = trace.get_tracer(service_name)
        else:
            self.tracer = None

    @contextmanager
    def span(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """Create a tracing span."""
        if self.tracer:
            with self.tracer.start_as_current_span(name) as span:
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, str(value))
                yield span
        else:
            yield None

    def trace(self, name: Optional[str] = None):
        """Decorator to add tracing to functions."""
        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            span_name = name or f"{func.__module__}.{func.__name__}"

            @functools.wraps(func)
            def wrapper(*args, **kwargs) -> T:
                with self.span(span_name, {"function": func.__name__}):
                    return func(*args, **kwargs)

            return wrapper
        return decorator


# Global instances for convenience
logger = StructuredLogger("rust_crate_pipeline")
metrics_collector = MetricsCollector()
tracer = TracingManager()


def observe_function(
    metric_prefix: str,
    log_args: bool = False,
    trace_enabled: bool = True
):
    """
    Decorator to add comprehensive observability to functions.

    Adds:
    - Structured logging
    - Metrics collection
    - Distributed tracing
    - Error tracking
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            func_name = f"{func.__module__}.{func.__name__}"

            # Create function-specific logger
            func_logger = logger.with_context(function=func_name)

            # Log function call
            log_context = {"function": func_name}
            if log_args:
                log_context["args"] = str(args)
                log_context["kwargs"] = str(kwargs)

            func_logger.info(f"Calling {func_name}", **log_context)

            # Start tracing span
            span_ctx = tracer.span(func_name) if trace_enabled else None

            # Time the execution
            start_time = time.time()

            try:
                with span_ctx or nullcontext():
                    with metrics_collector.timer(f"{metric_prefix}_duration", {"function": func_name}):
                        result = func(*args, **kwargs)

                        # Log success
                        duration = time.time() - start_time
                        func_logger.info(
                            f"Completed {func_name}",
                            duration=duration,
                            status="success"
                        )

                        # Record success metric
                        metrics_collector.increment(
                            f"{metric_prefix}_total",
                            tags={"function": func_name, "status": "success"}
                        )

                        return result

            except Exception as e:
                # Log error with full context
                duration = time.time() - start_time
                func_logger.error(
                    f"Failed {func_name}",
                    error=e,
                    duration=duration,
                    status="error"
                )

                # Record error metric
                metrics_collector.increment(
                    f"{metric_prefix}_total",
                    tags={
                        "function": func_name,
                        "status": "error",
                        "error_type": type(e).__name__})

                # Re-raise the exception
                raise

        return wrapper
    return decorator
