# ADR-011: Non-Standard Cargo Source Path Detection

## Status

Accepted

## Context

The pipeline was rejecting legitimate crates like `tree-sitter` with "no documentation found" despite them having extensive public API documentation. Investigation revealed:

1. `tree-sitter`'s Rust source code is located in `binding_rust/lib.rs`, not the standard `src/lib.rs`
2. The Cargo.toml specifies: `[lib] path = "binding_rust/lib.rs"`
3. The pipeline hardcoded `src/` as the only source directory to scan for:
   - Documentation checks (`run_doc_check`)
   - File collection for processing
   - Cache hash computation

This is a valid Cargo configuration - the [Cargo Book](https://doc.rust-lang.org/cargo/reference/manifest.html#the-lib-section) documents that `[lib].path`, `[[bin]].path`, and similar sections allow customizing source locations.

## Decision

Parse `Cargo.toml` to discover actual source directories instead of assuming `src/`:

1. **New function `get_crate_source_paths(crate_dir)`** in `analyzer.py`:
   - Uses Python 3.11+'s built-in `tomllib` (no new dependencies)
   - Extracts paths from `[lib].path` and `[[bin]].path` sections
   - Also checks `[[example]]`, `[[test]]`, `[[bench]]` sections
   - Only includes directories where the specified source file actually exists
   - Always includes `src/` if it exists (standard layout)
   - Falls back gracefully on parse errors or missing Cargo.toml

2. **Updated `run_doc_check()`** to iterate over all discovered source directories

3. **Updated `compute_crate_hash()`** in `analysis_cache.py` to hash files from all source directories

4. **Updated `main.py`** file collection to scan all source directories

## Consequences

### Positive

- Correctly processes crates with non-standard layouts (tree-sitter, etc.)
- No new dependencies (uses stdlib `tomllib`)
- Minimal overhead - single Cargo.toml read per crate, cached
- Backward compatible - standard `src/` layout still works unchanged
- More accurate cache invalidation (hashes actual source files)
- Output increased from 138 to 196 samples on test_crates.txt

### Negative

- Additional Cargo.toml parsing adds small overhead (~1ms per crate)
- Slightly more complex code path for source discovery
- Duplicated logic in analyzer.py and analysis_cache.py (to avoid circular imports)

### Neutral

- Workspace-level Cargo.toml files (without `[package]`) fall back to `src/`
- Virtual workspaces must be processed at the member level

## Alternatives Considered

### Alternative 1: Run `cargo metadata` for Source Paths

Could shell out to `cargo metadata --format-version=1` which provides complete package information including resolved source paths.

**Rejected because:**
- Significant overhead (~500ms per invocation)
- Requires Cargo installed and working
- May fail on incomplete/broken crates
- Over-engineered for this specific need

### Alternative 2: Hardcode Known Non-Standard Paths

Maintain a list of known crates with non-standard layouts: `{"tree-sitter": "binding_rust"}`.

**Rejected because:**
- Doesn't scale to unknown crates
- Requires maintenance as new crates are added
- Doesn't solve the general problem

### Alternative 3: Recursively Scan for .rs Files

Walk the entire crate directory looking for any `.rs` files.

**Rejected because:**
- Would include test fixtures, generated code, vendored dependencies
- No way to distinguish library code from auxiliary files
- Could significantly inflate processing time on large crates
- High risk of false positives

## Related

- [ADR-002: Category-Based Clippy Filtering](ADR-002-category-based-clippy-filtering.md) - Also parses crate metadata
- [Cargo Book: Package Layout](https://doc.rust-lang.org/cargo/guide/project-layout.html) - Documents standard vs custom layouts
- [Cargo Book: The lib Section](https://doc.rust-lang.org/cargo/reference/manifest.html#the-lib-section) - Documents path configuration
