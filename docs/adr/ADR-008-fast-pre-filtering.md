# ADR-008: Fast Pre-Filtering Before Expensive Analysis

## Status

Accepted

## Context

The pipeline runs expensive compilation-based analysis (Clippy) on all crates, even those with obviously invalid code. This wastes computational resources and slows down the pipeline. We need a way to quickly reject invalid code before running expensive analysis tools.

## Decision

Implement fast static analysis functions that validate code syntax and structure without compilation:

1. **Static syntax validation**: Check bracket matching, quote balancing, basic structure
2. **Fast signature checking**: Regex-based function signature validation before AST parsing
3. **API usage validation**: Verify required APIs are used (excluding comments)

These pre-filters run before Clippy and can reject obviously invalid code, improving pipeline performance.

## Consequences

### Positive

- Faster pipeline execution by rejecting invalid code early
- Reduced computational load on analysis infrastructure
- Better resource utilization

### Negative

- Additional code to maintain
- Potential for false positives if regex patterns are too strict

### Neutral

- Clippy remains the authoritative quality check
- Pre-filters are optional and can be disabled

## Alternatives Considered

### Alternative 1: Always Run Full Analysis

Run Clippy on all code regardless of validity.

**Rejected because:** Wastes resources on obviously invalid code.

### Alternative 2: Compile-Only Pre-Check

Run `cargo check` before Clippy to catch compilation errors.

**Rejected because:** Still expensive, doesn't provide much speedup over Clippy.

## Related

- `sigil_pipeline/filter.py::static_analysis_rust_code()`
- `sigil_pipeline/ast_patterns.py::check_function_in_code()`
