# ADR-013: Dataset Hardening Mode for Rust 2024

## Status

Accepted

## Context

The sigil-pipeline generates high-quality Rust code datasets for LLM fine-tuning. While the existing filtering (Clippy checks, edition requirements, documentation coverage) produces good quality data, there is demand for an even stricter "benchmark-quality" dataset tier that adheres to the Rust 2024 edition standards.

The Rust 2024 edition introduces stricter defaults and best practices. For benchmark datasets used in rigorous LLM evaluation or training on gold-standard Rust code, we need:

1. **Strict Clippy analysis** - pedantic and nursery lint groups, plus denial of common anti-patterns (`unwrap`, `expect`, `panic`)
2. **Consistent formatting** - rustfmt with Edition 2024 style defaults
3. **Unsafe-free code** - no `unsafe { }` blocks for memory-safe benchmarks
4. **Edition 2024 only** - target modern Rust idioms

This mode should be optional to avoid breaking existing workflows while providing a path to higher-quality datasets for users who want them.

## Decision

Implement an opt-in `--dataset-hardening` CLI flag that enables strict Rust 2024 quality enforcement:

### Configuration Options

```python
@dataclass
class PipelineConfig:
    # ... existing fields ...
    dataset_hardening: bool = False
    hardening_min_edition: str = "2024"
    hardening_strict_clippy: bool = True
    hardening_deny_antipatterns: bool = True
    hardening_require_rustfmt: bool = True
    hardening_reject_unsafe: bool = True
```

### Quality Gates

When `--dataset-hardening` is enabled:

1. **Toolchain Validation** - Pipeline exits early if rustc < 1.85 (Edition 2024 support)
2. **Strict Clippy** - Runs `cargo clippy` with:
   - `-W clippy::pedantic`
   - `-W clippy::nursery`
   - `-D clippy::unwrap_used`
   - `-D clippy::expect_used`
   - `-D clippy::panic`
3. **Rustfmt Check** - Runs `cargo fmt --check` with Edition 2024 style
4. **Unsafe Detection** - Tree-sitter based detection of `unsafe { }` blocks

### Filtering Behavior

- Crates failing strict clippy → rejected at crate level
- Crates failing rustfmt check → rejected at crate level
- Individual files with unsafe blocks → filtered at sample level

### Override Flags

Users can disable specific checks while keeping hardening enabled:
- `--no-hardening-strict-clippy` - Skip pedantic/nursery clippy
- `--no-hardening-rustfmt` - Skip rustfmt validation
- `--no-hardening-reject-unsafe` - Allow unsafe code

### Metadata Enrichment

When hardening is enabled, samples include additional metadata:
- `_hardening_enabled: true`
- `_hardening_edition: "2024"`
- `_clippy_strict_passed: true/false`
- `_rustfmt_passed: true/false`

### Caching

Hardening check results (strict clippy, rustfmt) are cached in the crate analysis report and serialized to disk. This means:
- Crate-level checks run once per crate, not per file
- Subsequent pipeline runs with unchanged configs reuse cached results
- Cache invalidation follows existing analysis cache behavior

## Consequences

### Positive

- **Higher quality datasets** - Benchmark-tier data for rigorous LLM evaluation
- **Modern Rust idioms** - Edition 2024 code patterns only
- **Memory safety** - No unsafe code in hardened datasets
- **Consistent style** - Uniform formatting across all samples
- **Metadata transparency** - Clear quality indicators in output
- **Backward compatible** - Opt-in only, existing workflows unchanged

### Negative

- **Performance overhead** - Strict clippy adds ~2-5x analysis time per crate
- **Reduced yield** - Many existing crates won't pass strict criteria
- **Toolchain requirement** - Requires Rust 1.85+ (not yet stable as of early 2025)
- **False positives** - Some valid code patterns trigger pedantic lints

### Neutral

- Additional CLI flags to document and maintain
- More complex crate rejection reasons to track

## Performance Mitigations

To address the performance overhead:

1. **Hardware recommendations**: Fast NVMe storage, 8+ CPU cores
2. **Selective checks**: Use override flags to disable slower checks
3. **Checkpoint files**: Enable `--checkpoint-dir` for incremental runs
4. **Parallel processing**: Tune `--max-threads` for your hardware
5. **Cache reuse**: Hardening results are cached in analysis reports

## Alternatives Considered

### Alternative 1: Post-processing Filter

Run standard pipeline, then filter output with a separate hardening tool.

**Rejected**: Would require re-running clippy/rustfmt on already-processed samples without crate context. Less efficient and loses crate-level metadata.

### Alternative 2: Separate Pipeline Mode

Create a completely separate pipeline binary/module for hardened datasets.

**Rejected**: Code duplication, maintenance burden. A flag-based approach integrates cleanly with existing architecture.

### Alternative 3: Always-on Strict Mode

Make strict checks the default for all pipeline runs.

**Rejected**: Would break existing workflows, dramatically increase runtime, and reduce dataset size. Not suitable for all use cases.

## Related

- [ADR-002: Category-based Clippy Filtering](./ADR-002-category-based-clippy-filtering.md) - Existing clippy filtering approach
- [ADR-012: Inline Test Detection Threshold](./ADR-012-inline-test-detection-threshold.md) - Quality-related filtering
- [Runbook: Rust 2024 Toolchain Setup](../runbooks/RUST_2024_TOOLCHAIN_SETUP.md) - Installation instructions
- [Rust Edition Guide](https://doc.rust-lang.org/edition-guide/) - Official edition documentation

## Implementation Files

- `sigil_pipeline/config.py` - Hardening configuration fields
- `sigil_pipeline/main.py` - CLI flags and orchestration
- `sigil_pipeline/environment.py` - Toolchain validation
- `sigil_pipeline/analyzer.py` - `run_clippy_strict()`, `run_rustfmt_check()`
- `sigil_pipeline/filter.py` - `detect_unsafe_blocks()`, hardening rejection logic
- `sigil_pipeline/dataset_builder.py` - Metadata enrichment
