# ADR-012: Inline Test Detection Threshold

## Status

Accepted

## Context

The pipeline's `looks_like_test()` function was filtering out legitimate library code that contained inline unit tests. Specifically, the `scopeguard` crate was being rejected with "0/1 files passed filters" because its `lib.rs` contained:

```rust
#[cfg(test)]
mod tests {
    fn test_defer() { ... }
    fn test_defer_success_1() { ... }
    // ...more tests
}
```

The previous implementation used simple substring matching:
```python
if "#[cfg(test)]" in content or "fn test" in content:
    return True
```

This was **too aggressive** because:
1. Rust idiomatically includes unit tests inline with library code using `#[cfg(test)]`
2. The Rust standard library and most major crates follow this pattern
3. Filtering files that simply *contain* tests discards valuable production code

For scopeguard specifically:
- 596 total lines
- 104 lines in test module (17.4%)
- 492 lines of production code (82.6%)

The previous filter rejected this entire file despite 82.6% being high-quality, documented library code.

## Decision

Implement a **test ratio threshold** for content-based filtering:

1. **Path-based filtering** (unchanged): Files in `/tests/`, `/benches/`, `/test/`, or with `_test.rs`/`_tests.rs` suffixes are always filtered. These are dedicated test files.

2. **Content-based filtering** (changed): Files containing `#[cfg(test)]` or `fn test` are only filtered if **more than 50% of their lines** are test code.

The implementation:
- Counts lines inside `#[cfg(test)]` modules
- Counts explicit `#[test]` or `fn test` declarations
- Only filters if `test_lines / total_lines > 0.5`

## Consequences

### Positive

- Correctly processes crates with inline tests (scopeguard, etc.)
- Preserves idiomatic Rust code patterns
- More production code available for training
- scopeguard now passes: `1/1 files passed filters`

### Negative

- Slightly more complex filtering logic
- Small performance cost for line counting (negligible)
- Test code within the 50% threshold may appear in output (but this is acceptable - tests are valid Rust code)

### Neutral

- 50% threshold is somewhat arbitrary but errs on the side of inclusion
- Files that are primarily tests (>50%) are still filtered correctly
- Path-based filtering remains unchanged and deterministic

## Alternatives Considered

### Alternative 1: Remove Content-Based Test Detection Entirely

Only use path-based filtering (`/tests/`, `_test.rs`, etc.).

**Rejected because:**
- Some repositories have test files in non-standard locations
- Would include files that are 100% test code without the standard naming

### Alternative 2: Detect and Strip Test Modules

Parse the AST to identify `#[cfg(test)]` modules and remove them from output.

**Rejected because:**
- Significant implementation complexity
- Would require modifying source code content
- Test code is still valid, idiomatic Rust - no need to strip it

### Alternative 3: Lower Threshold (e.g., 30%)

Use a more aggressive threshold to filter files with even small test sections.

**Rejected because:**
- Would still filter many legitimate library files
- Rust's inline test pattern is common enough that 30% test code is normal

## Related

- [ADR-008: Fast Pre-Filtering](ADR-008-fast-pre-filtering.md) - Original filtering strategy
- [Rust Book: How to Write Tests](https://doc.rust-lang.org/book/ch11-01-writing-tests.html) - Documents inline test pattern
