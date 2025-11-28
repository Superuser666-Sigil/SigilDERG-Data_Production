# ADR-002: Category-Based Clippy Filtering

## Status

Accepted

## Context

Initial Clippy filtering used a simple threshold on total warning count (`max_clippy_warnings`). This approach had problems:

1. **Over-filtering**: Style/documentation warnings (e.g., `doc_markdown`, `too_many_lines`) caused rejection of otherwise high-quality code
2. **Under-filtering**: Critical warnings (e.g., `unwrap_used`, `indexing_slicing`) could be drowned out by many style warnings
3. **Poor signal-to-noise**: Total count didn't distinguish between "cosmetic issues" and "actual problems"

We needed filtering that:
- Blocks code with actual quality/safety issues
- Ignores stylistic preferences that don't affect training quality
- Provides transparency into why crates are rejected

## Decision

Implement category-based Clippy warning classification:

1. **safe_to_ignore**: Style/documentation warnings that don't indicate code problems
   - `doc_markdown`, `too_many_lines`, `cognitive_complexity`
   - Cast warnings, naming conventions, import style
   
2. **bad_code**: Warnings indicating actual problems that should cause rejection
   - `unwrap_used`, `expect_used`, `panic`
   - `indexing_slicing`, `transmute`, unsafe operations
   - Unused variables/imports, unimplemented code
   
3. **questionable**: May indicate issues but often false positives
   - Treated as neutral for filtering purposes

Add `max_bad_code_warnings` configuration (default: 0) that only counts `bad_code` category warnings. Retain `max_clippy_warnings` for backward compatibility.

## Consequences

### Positive

- Higher quality filtering: rejects code with real issues, accepts stylistically diverse code
- Better training data: includes code with varying style but consistent quality
- Transparency: rejection logs show category breakdown
- Flexibility: can adjust category definitions as understanding improves

### Negative

- More complex categorization logic to maintain
- Some subjective decisions about category boundaries
- May need periodic review as Clippy adds new lints

### Neutral

- Existing `max_clippy_warnings` still works for total-count filtering
- Category definitions can be adjusted via code updates

## Alternatives Considered

### Alternative 1: Whitelist/Blacklist Specific Lints

Maintain explicit lists of lint codes to allow or block.

**Rejected because:**
- Hundreds of Clippy lints exist
- New lints added regularly
- Pattern-based matching is more maintainable

### Alternative 2: Severity-Based Filtering

Use Clippy's severity levels (allow, warn, deny, forbid).

**Rejected because:**
- Clippy severity doesn't map to "training data quality"
- Many important lints are just "warn" level
- Our categories are more domain-specific

## Related

- Clippy Lints Reference: https://rust-lang.github.io/rust-clippy/
- `sigil_pipeline/analyzer.py::categorize_clippy_warning()`
- `docs/CLIPPY_CATEGORY_FILTERING.md`

