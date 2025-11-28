# ADR-004: Observability Infrastructure

## Status

Accepted

## Context

Production deployments require comprehensive observability:

1. **Debugging**: Need to trace issues through the pipeline
2. **Monitoring**: Track progress, success rates, performance metrics
3. **Alerting**: Detect anomalies and failures quickly
4. **Capacity Planning**: Understand resource usage patterns

The initial implementation used basic Python logging, which was insufficient for:
- Structured log aggregation (ELK, CloudWatch, etc.)
- Metrics export (Prometheus, Grafana)
- Distributed tracing (for future multi-node deployment)

## Decision

Implement a comprehensive observability stack:

1. **Structured Logging** (structlog)
   - JSON output for production environments
   - Human-readable output for development
   - Contextual fields automatically included
   - Graceful fallback to standard logging

2. **Metrics Collection** (Prometheus-compatible)
   - Counters for operations and errors
   - Gauges for current state
   - Histograms for latency distributions
   - Labels for dimensional analysis

3. **Operation Tracking**
   - `timed_operation` context manager
   - Automatic duration metrics
   - Success/failure tracking
   - Progress reporting for long operations

4. **Future: Distributed Tracing** (OpenTelemetry)
   - Span-based tracing
   - Cross-service correlation
   - Performance profiling

All observability is opt-in and gracefully degrades if dependencies aren't installed.

## Consequences

### Positive

- Enterprise-ready logging suitable for log aggregation
- Prometheus-compatible metrics for standard monitoring stacks
- Easy debugging with structured, contextual logs
- Foundation for future distributed deployment

### Negative

- Additional dependencies (structlog optional)
- Slight performance overhead from metric collection
- Learning curve for structured logging patterns

### Neutral

- Existing code continues to work with standard logging
- Metrics are thread-safe with locking overhead
- JSON output is more verbose than plain text

## Alternatives Considered

### Alternative 1: Keep Standard Logging

Continue using Python's logging module with formatting improvements.

**Rejected because:**
- No native support for structured/JSON output
- Context propagation requires manual effort
- No metrics capability

### Alternative 2: OpenTelemetry Only

Use OpenTelemetry for all observability needs.

**Rejected because:**
- Heavier dependency
- Overkill for single-process pipeline
- structlog better suited for Python logging patterns

## Related

- structlog documentation: https://www.structlog.org/
- Prometheus exposition format: https://prometheus.io/docs/instrumenting/exposition_formats/
- `sigil_pipeline/observability.py`


