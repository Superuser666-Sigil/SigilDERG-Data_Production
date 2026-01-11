"""
OpenTelemetry distributed tracing support.

Provides span-based tracing for observability across the pipeline.
Gracefully degrades when OpenTelemetry is not installed.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.6.0
"""

import functools
import logging
from contextlib import contextmanager
from typing import Any, Callable, Iterator, TypeVar

# Try to import OpenTelemetry
try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.trace import Span, Status, StatusCode

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    trace = None  # type: ignore[assignment]
    Span = None  # type: ignore[assignment, misc]

    class _DummyStatus:
        """Dummy Status class when OpenTelemetry not available."""

        def __init__(self, code: Any, desc: str = "") -> None:
            pass

    class _DummyStatusCode:
        """Dummy StatusCode class when OpenTelemetry not available."""

        OK = None
        ERROR = None

    Status = _DummyStatus  # type: ignore[assignment, misc]
    StatusCode = _DummyStatusCode  # type: ignore[assignment, misc]

logger = logging.getLogger(__name__)

# Type variable for generic function decoration
F = TypeVar("F", bound=Callable[..., Any])


def configure_telemetry(
    service_name: str = "sigil-pipeline",
    endpoint: str | None = None,
    console_export: bool = False,
) -> None:
    """
    Configure OpenTelemetry tracing for the pipeline.

    Args:
        service_name: Name of the service for tracing
        endpoint: OTLP endpoint URL (optional, for remote collectors)
        console_export: If True, also export spans to console (for debugging)
    """
    if not OTEL_AVAILABLE:
        logger.warning("OpenTelemetry not installed, tracing disabled")
        return

    # Create resource with service information
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": "2.2.0",
        }
    )

    # Create tracer provider
    provider = TracerProvider(resource=resource)

    # Add console exporter for debugging
    if console_export:
        console_processor = BatchSpanProcessor(ConsoleSpanExporter())
        provider.add_span_processor(console_processor)

    # Add OTLP exporter if endpoint provided
    if endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            otlp_exporter = OTLPSpanExporter(endpoint=endpoint)
            otlp_processor = BatchSpanProcessor(otlp_exporter)
            provider.add_span_processor(otlp_processor)
        except ImportError:
            logger.warning("OTLP exporter not available, skipping remote export")

    # Set as global tracer provider
    if trace is not None:
        trace.set_tracer_provider(provider)
    logger.info(f"Telemetry configured for service: {service_name}")


def get_tracer(name: str = "sigil_pipeline") -> Any:
    """
    Get a tracer instance for creating spans.

    Args:
        name: Tracer name (usually module name)

    Returns:
        Tracer instance if OpenTelemetry available, else a no-op tracer
    """
    if not OTEL_AVAILABLE or trace is None:
        return _NoOpTracer()

    return trace.get_tracer(name)


class _NoOpTracer:
    """No-op tracer for when OpenTelemetry is not available."""

    @contextmanager
    def start_as_current_span(self, name: str, **kwargs: Any) -> Iterator["_NoOpSpan"]:
        """Return a no-op span context manager."""
        yield _NoOpSpan()

    def start_span(self, name: str, **kwargs: Any) -> "_NoOpSpan":
        """Return a no-op span."""
        return _NoOpSpan()


class _NoOpSpan:
    """No-op span for when OpenTelemetry is not available."""

    def set_attribute(self, key: str, value: Any) -> None:
        """No-op."""
        pass

    def set_status(self, status: Any) -> None:
        """No-op."""
        pass

    def record_exception(self, exception: Exception) -> None:
        """No-op."""
        pass

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        """No-op."""
        pass

    def end(self) -> None:
        """No-op."""
        pass

    def __enter__(self) -> "_NoOpSpan":
        return self

    def __exit__(self, *args: Any) -> None:
        pass


@contextmanager
def traced_operation(
    name: str,
    attributes: dict[str, Any] | None = None,
) -> Iterator[Any]:
    """
    Context manager for tracing an operation.

    Args:
        name: Name of the operation
        attributes: Optional attributes to add to the span

    Yields:
        The current span (or no-op span if tracing disabled)

    Example:
        with traced_operation("fetch_crate", {"crate": "serde"}) as span:
            result = fetch_crate("serde")
            span.set_attribute("result.size", len(result))
    """
    tracer = get_tracer()

    with tracer.start_as_current_span(name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)

        try:
            yield span
            if OTEL_AVAILABLE:
                span.set_status(Status(StatusCode.OK))
        except Exception as e:
            if OTEL_AVAILABLE:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
            raise


def traced(
    name: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> Callable[[F], F]:
    """
    Decorator for tracing a function.

    Args:
        name: Optional span name (defaults to function name)
        attributes: Optional static attributes

    Returns:
        Decorated function with tracing

    Example:
        @traced(attributes={"component": "crawler"})
        async def fetch_crate(name: str) -> bytes:
            ...
    """

    def decorator(func: F) -> F:
        span_name = name or func.__name__

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            with traced_operation(span_name, attributes):
                return func(*args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            with traced_operation(span_name, attributes):
                return await func(*args, **kwargs)

        # Return appropriate wrapper based on function type
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper  # type: ignore[return-value]

    return decorator


class TracingContext:
    """
    Context for managing trace context across async operations.

    Useful for propagating trace context in async pipelines.
    """

    def __init__(self, parent_span: Any = None) -> None:
        """
        Initialize tracing context.

        Args:
            parent_span: Optional parent span to link to
        """
        self.parent_span = parent_span
        self._span_stack: list[Any] = []

    def push_span(self, name: str, attributes: dict[str, Any] | None = None) -> Any:
        """
        Create and push a new span.

        Args:
            name: Span name
            attributes: Optional span attributes

        Returns:
            The created span
        """
        tracer = get_tracer()
        span = tracer.start_span(name)

        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)

        self._span_stack.append(span)
        return span

    def pop_span(self, error: Exception | None = None) -> None:
        """
        End and pop the current span.

        Args:
            error: Optional error to record
        """
        if self._span_stack:
            span = self._span_stack.pop()

            if error and OTEL_AVAILABLE:
                span.set_status(Status(StatusCode.ERROR, str(error)))
                span.record_exception(error)
            elif OTEL_AVAILABLE:
                span.set_status(Status(StatusCode.OK))

            span.end()

    @property
    def current_span(self) -> Any:
        """Get the current span or no-op span."""
        if self._span_stack:
            return self._span_stack[-1]
        return _NoOpSpan()
