# ADR-009: API Evolution Tracking

## Status

Accepted

## Context

The pipeline needs to track API changes across Rust versions to understand how APIs evolve, stabilize, get deprecated, or change signatures. This is essential for generating training data that reflects real-world API evolution patterns.

## Decision

Implement a comprehensive API evolution tracking module that:

1. Extracts API entities (functions, structs, enums, traits) from Rust source code
2. Tracks changes between versions (stabilized, deprecated, signature changes, implicit changes)
3. Uses AST-based parsing for accurate extraction
4. Provides structured change reports

## Consequences

### Positive

- Enables tracking of API evolution patterns
- Supports generation of evolution-aware training data
- Provides insights into Rust standard library changes

### Negative

- Requires git repository access for version checkout
- Computationally expensive for large version ranges
- Requires maintenance as Rust evolves

### Neutral

- Can be run as separate analysis pass
- Results can be cached for reuse

## Alternatives Considered

### Alternative 1: Use Existing Rust Documentation

Parse rustdoc output instead of source code.

**Rejected because:** Less accurate, doesn't capture implementation changes.

### Alternative 2: LLM-Based Change Detection

Use LLM to identify changes between versions.

**Rejected because:** Expensive, non-deterministic, requires API keys.

## Related

- `sigil_pipeline/api_tracker.py`
- `sigil_pipeline/ast_patterns.py`
