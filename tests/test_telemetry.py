"""
Tests for sigil_pipeline.telemetry module.

Tests OpenTelemetry integration including no-op behavior when
OpenTelemetry is not available.
"""

import pytest

from sigil_pipeline.telemetry import (
    OTEL_AVAILABLE,
    TracingContext,
    _NoOpSpan,
    _NoOpTracer,
    configure_telemetry,
    get_tracer,
    traced,
    traced_operation,
)


class TestNoOpTracer:
    """Test _NoOpTracer class."""

    def test_start_as_current_span_returns_noop_span(self):
        """Test that start_as_current_span returns a no-op span."""
        tracer = _NoOpTracer()
        with tracer.start_as_current_span("test") as span:
            assert isinstance(span, _NoOpSpan)

    def test_start_span_returns_noop_span(self):
        """Test that start_span returns a no-op span."""
        tracer = _NoOpTracer()
        span = tracer.start_span("test")
        assert isinstance(span, _NoOpSpan)

    def test_start_as_current_span_with_kwargs(self):
        """Test start_as_current_span ignores kwargs."""
        tracer = _NoOpTracer()
        with tracer.start_as_current_span("test", kind="internal") as span:
            assert isinstance(span, _NoOpSpan)


class TestNoOpSpan:
    """Test _NoOpSpan class."""

    def test_set_attribute_noop(self):
        """Test set_attribute is a no-op."""
        span = _NoOpSpan()
        # Should not raise
        span.set_attribute("key", "value")
        span.set_attribute("count", 42)
        span.set_attribute("enabled", True)

    def test_set_status_noop(self):
        """Test set_status is a no-op."""
        span = _NoOpSpan()
        span.set_status(None)
        span.set_status("ok")

    def test_record_exception_noop(self):
        """Test record_exception is a no-op."""
        span = _NoOpSpan()
        span.record_exception(ValueError("test error"))

    def test_add_event_noop(self):
        """Test add_event is a no-op."""
        span = _NoOpSpan()
        span.add_event("event_name")
        span.add_event("event_name", {"attr": "value"})

    def test_end_noop(self):
        """Test end is a no-op."""
        span = _NoOpSpan()
        span.end()

    def test_context_manager(self):
        """Test span works as context manager."""
        span = _NoOpSpan()
        with span as s:
            assert s is span


class TestGetTracer:
    """Test get_tracer function."""

    def test_get_tracer_default_name(self):
        """Test get_tracer with default name."""
        tracer = get_tracer()
        # Should return either real tracer or no-op
        assert tracer is not None

    def test_get_tracer_custom_name(self):
        """Test get_tracer with custom name."""
        tracer = get_tracer("custom_module")
        assert tracer is not None

    def test_get_tracer_returns_noop_when_unavailable(self):
        """Test that get_tracer returns no-op when OTEL not available."""
        # If OTEL is not available, should get NoOpTracer
        if not OTEL_AVAILABLE:
            tracer = get_tracer()
            assert isinstance(tracer, _NoOpTracer)


class TestTracedOperation:
    """Test traced_operation context manager."""

    def test_basic_operation(self):
        """Test basic traced operation."""
        with traced_operation("test_op") as span:
            assert span is not None

    def test_operation_with_attributes(self):
        """Test traced operation with attributes."""
        attrs = {"crate": "serde", "version": "1.0"}
        with traced_operation("fetch", attrs) as span:
            assert span is not None

    def test_operation_success(self):
        """Test traced operation that succeeds."""
        result = None
        with traced_operation("compute"):
            result = 42
        assert result == 42

    def test_operation_with_exception(self):
        """Test traced operation that raises exception."""
        with pytest.raises(ValueError, match="test error"):
            with traced_operation("failing_op"):
                raise ValueError("test error")

    def test_span_attributes_can_be_set(self):
        """Test setting attributes on span within context."""
        with traced_operation("dynamic_attrs") as span:
            span.set_attribute("dynamic_key", "dynamic_value")
            span.set_attribute("count", 100)


class TestTracedDecorator:
    """Test traced decorator."""

    def test_traced_sync_function(self):
        """Test tracing a synchronous function."""

        @traced()
        def sync_function(x: int) -> int:
            return x * 2

        result = sync_function(21)
        assert result == 42

    def test_traced_with_custom_name(self):
        """Test traced decorator with custom span name."""

        @traced(name="custom_span_name")
        def my_func() -> str:
            return "result"

        result = my_func()
        assert result == "result"

    def test_traced_with_attributes(self):
        """Test traced decorator with static attributes."""

        @traced(attributes={"component": "parser"})
        def parse_code(code: str) -> dict:
            return {"parsed": True}

        result = parse_code("fn main() {}")
        assert result == {"parsed": True}

    def test_traced_function_preserves_name(self):
        """Test that traced decorator preserves function name."""

        @traced()
        def original_name():
            pass

        assert original_name.__name__ == "original_name"

    def test_traced_function_preserves_docstring(self):
        """Test that traced decorator preserves docstring."""

        @traced()
        def documented_func():
            """This is documentation."""
            pass

        assert documented_func.__doc__ == """This is documentation."""

    def test_traced_function_with_exception(self):
        """Test traced function that raises exception."""

        @traced()
        def failing_func():
            raise RuntimeError("failure")

        with pytest.raises(RuntimeError, match="failure"):
            failing_func()

    def test_traced_function_with_args_and_kwargs(self):
        """Test traced function with various arguments."""

        @traced()
        def complex_func(a: int, b: int, *, c: int = 0) -> int:
            return a + b + c

        result = complex_func(1, 2, c=3)
        assert result == 6


class TestTracedAsyncDecorator:
    """Test traced decorator with async functions."""

    @pytest.mark.asyncio
    async def test_traced_async_function(self):
        """Test tracing an async function."""

        @traced()
        async def async_function(x: int) -> int:
            return x * 2

        result = await async_function(21)
        assert result == 42

    @pytest.mark.asyncio
    async def test_traced_async_with_attributes(self):
        """Test traced async function with attributes."""

        @traced(name="async_op", attributes={"async": True})
        async def async_op() -> str:
            return "done"

        result = await async_op()
        assert result == "done"

    @pytest.mark.asyncio
    async def test_traced_async_with_exception(self):
        """Test traced async function that raises exception."""

        @traced()
        async def failing_async():
            raise ValueError("async failure")

        with pytest.raises(ValueError, match="async failure"):
            await failing_async()


class TestTracingContext:
    """Test TracingContext class."""

    def test_create_context(self):
        """Test creating a tracing context."""
        ctx = TracingContext()
        assert ctx.parent_span is None
        assert ctx._span_stack == []

    def test_create_context_with_parent(self):
        """Test creating a tracing context with parent span."""
        parent = _NoOpSpan()
        ctx = TracingContext(parent_span=parent)
        assert ctx.parent_span is parent

    def test_push_span(self):
        """Test pushing a span onto the stack."""
        ctx = TracingContext()
        span = ctx.push_span("test_span")
        assert span is not None
        assert len(ctx._span_stack) == 1

    def test_push_span_with_attributes(self):
        """Test pushing a span with attributes."""
        ctx = TracingContext()
        span = ctx.push_span("attributed_span", {"key": "value"})
        assert span is not None
        assert len(ctx._span_stack) == 1

    def test_pop_span(self):
        """Test popping a span from the stack."""
        ctx = TracingContext()
        ctx.push_span("test_span")
        assert len(ctx._span_stack) == 1
        ctx.pop_span()
        assert len(ctx._span_stack) == 0

    def test_pop_span_with_error(self):
        """Test popping a span with an error."""
        ctx = TracingContext()
        ctx.push_span("error_span")
        ctx.pop_span(error=ValueError("test error"))
        assert len(ctx._span_stack) == 0

    def test_pop_empty_stack(self):
        """Test popping from empty stack is safe."""
        ctx = TracingContext()
        # Should not raise
        ctx.pop_span()

    def test_current_span_empty_stack(self):
        """Test current_span returns no-op when stack empty."""
        ctx = TracingContext()
        span = ctx.current_span
        assert isinstance(span, _NoOpSpan)

    def test_current_span_with_spans(self):
        """Test current_span returns top of stack."""
        ctx = TracingContext()
        span1 = ctx.push_span("span1")
        span2 = ctx.push_span("span2")
        assert ctx.current_span is span2

        ctx.pop_span()
        assert ctx.current_span is span1

    def test_nested_spans(self):
        """Test nested span operations."""
        ctx = TracingContext()

        ctx.push_span("outer")
        assert len(ctx._span_stack) == 1

        ctx.push_span("inner")
        assert len(ctx._span_stack) == 2

        ctx.pop_span()
        assert len(ctx._span_stack) == 1

        ctx.pop_span()
        assert len(ctx._span_stack) == 0


class TestConfigureTelemetry:
    """Test configure_telemetry function."""

    def test_configure_default(self):
        """Test configure with default parameters."""
        # Should not raise regardless of OTEL availability
        configure_telemetry()

    def test_configure_custom_service_name(self):
        """Test configure with custom service name."""
        configure_telemetry(service_name="test-service")

    def test_configure_with_console_export(self):
        """Test configure with console export enabled."""
        configure_telemetry(console_export=True)

    def test_configure_with_endpoint(self):
        """Test configure with OTLP endpoint."""
        # This may warn if OTLP exporter not available
        configure_telemetry(endpoint="http://localhost:4317")


class TestOTELAvailability:
    """Test OTEL_AVAILABLE flag behavior."""

    def test_otel_available_is_bool(self):
        """Test that OTEL_AVAILABLE is a boolean."""
        assert isinstance(OTEL_AVAILABLE, bool)

    def test_functionality_works_regardless_of_otel(self):
        """Test that all functions work regardless of OTEL status."""
        # These should all work without raising
        _ = get_tracer()
        with traced_operation("test"):
            pass

        @traced()
        def test_func():
            return 42

        result = test_func()
        assert result == 42

        ctx = TracingContext()
        ctx.push_span("span")
        ctx.pop_span()
