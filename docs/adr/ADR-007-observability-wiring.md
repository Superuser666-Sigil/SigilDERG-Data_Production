# ADR-007: Observability Infrastructure Integration

## Status

Accepted (extends ADR-004)

## Context

ADR-004 established the observability infrastructure (`observability.py`) with `MetricsCollector`, 
`configure_structured_logging`, `timed_operation`, and `OperationTracker`. However, this 
infrastructure was not wired into the main pipeline—`main.py` continued to use basic 
`utils.setup_logging()` and plain dict-based metrics.

This created a disconnect between the documented observability capabilities and actual pipeline 
behavior, making it difficult to:

1. **Audit runs for reproducibility**: No environment fingerprint (rustc/cargo versions, OS, etc.)
2. **Monitor in production**: No Prometheus-compatible metrics export
3. **Debug failures**: Basic logging without structured context
4. **Track per-crate performance**: No histograms for processing times

## Decision

Wire the existing observability infrastructure into the main pipeline:

### 1. Structured Logging Integration

Replace `utils.setup_logging()` with `observability.configure_structured_logging()`:

```python
if cfg.enable_structured_logging:
    configure_structured_logging(
        log_level=cfg.log_level,
        json_output=cfg.json_logs,
        log_file=log_file_path,
    )
else:
    utils.setup_logging(cfg.log_level)  # Fallback
```

### 2. MetricsCollector Usage

Use the global `MetricsCollector` for tracking:

- `crates_accepted_total` (counter)
- `crates_rejected_total{reason="..."}` (counter with labels)
- `crate_file_count` (histogram)
- `pipeline_samples_total` (gauge)

Export both JSON (existing) and Prometheus text format (new, optional).

### 3. Environment Fingerprinting

Create `sigil_pipeline/environment.py` to capture:

```python
@dataclass
class EnvironmentFingerprint:
    timestamp: str
    toolchain: ToolchainInfo  # rustc, cargo, clippy versions
    cargo_tools: CargoToolAvailability  # geiger, deny, audit, etc.
    platform: PlatformInfo  # OS, arch, Python version
    dependencies: DependencyVersions  # tree-sitter, etc.
```

Log at startup and include in `metrics.json` + standalone `environment.json`.

### 4. New Configuration Options

Add to `PipelineConfig`:

```python
enable_structured_logging: bool = True
log_file: str | None = None
json_logs: bool = False
enable_prometheus_output: bool = False
prometheus_output_path: str | None = None
capture_environment: bool = True
```

## Consequences

### Positive

- **Reproducibility**: "Same inputs, same toolchain" can now be verified via `environment.json`
- **Production monitoring**: Prometheus metrics enable Grafana dashboards, alerting
- **Debugging**: Structured logs with context make root-cause analysis faster
- **Governance story**: Aligns with SigilDERG's "enterprise-grade" positioning
- **Backward compatible**: Defaults preserve existing behavior; new features are opt-in

### Negative

- **Slight startup overhead**: Environment capture runs version commands (~1-2s)
- **Additional output files**: `environment.json`, optional `metrics.prom`
- **Dependency on structlog**: Falls back gracefully if unavailable

### Neutral

- Config complexity increases slightly (6 new options)
- MetricsCollector is thread-safe but adds minor memory overhead

## Implementation Notes

1. The `timed_operation` context manager is available but not yet wired to individual crate 
   processing—this can be added in a follow-up for per-crate latency histograms.

2. OTEL tracing spans can be added later by wrapping key operations; the infrastructure 
   supports this via optional `[observability]` dependencies.

## Related ADRs

- [ADR-004](ADR-004-observability-infrastructure.md): Defines the observability infrastructure
- [ADR-006](ADR-006-ast-aware-prompt-generation.md): AST-based extraction (uses same patterns)




