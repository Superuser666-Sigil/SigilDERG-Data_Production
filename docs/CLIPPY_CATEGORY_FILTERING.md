# Clippy Warning Category-Based Filtering

**Version**: 1.1.0  
**Date**: 2025-11-24

## Overview

The pipeline now uses **category-based filtering** for Clippy warnings instead of a simple integer count. This allows the pipeline to accept crates with style/documentation warnings while still rejecting crates with actual code quality problems.

## How It Works

### Warning Categories

Clippy warnings are automatically categorized into three groups:

1. **`safe_to_ignore`**: Style and documentation warnings that don't affect code quality
   - Documentation formatting (`doc_lazy_continuation`, `doc_markdown`)
   - Complexity metrics (`too_many_lines`, `cognitive_complexity`)
   - Naming preferences (`similar_names`, `module_name_repetitions`)
   - Style preferences (`manual_*`, `needless_*`, `collapsible_*`)

2. **`bad_code`**: Warnings indicating actual code quality problems
   - Unsafe operations (`unwrap_used`, `expect_used`, `panic`)
   - Memory safety (`transmute`, `mem_forget`, `invalid_*`)
   - Resource leaks (`let_underscore_drop`, `drop_copy`)
   - Logic errors (`todo`, `unimplemented`, `unreachable`)
   - Actual dead code (`unused_variables`, `unused_imports`)

3. **`questionable`**: Warnings that might indicate issues but are often false positives
   - Performance hints (`needless_pass_by_value`)
   - Control flow style (`collapsible_if`)

### Filtering Logic

The pipeline now filters based on **`bad_code` warnings only**:

```python
# Old approach (deprecated)
max_clippy_warnings = 50  # Rejects if total warnings > 50

# New approach (recommended)
max_bad_code_warnings = 0  # Only rejects if bad_code warnings > 0
```

### Configuration

**New Config Option**:
```python
max_bad_code_warnings: int = 0
"""
Maximum allowed 'bad_code' category Clippy warnings.
Style/documentation warnings are ignored.
Default: 0 (reject any bad_code warnings).
"""
```

**Backward Compatibility**:
- `max_clippy_warnings` is still supported but deprecated
- If `max_bad_code_warnings` is set, it takes precedence
- If only `max_clippy_warnings` is set, it falls back to total count filtering

## Impact

### Before (Total Count Filtering)

- **aho-corasick**: Rejected (195 total warnings)
- **tokio**: Rejected (1 total warning - style)
- **serde**: Rejected (2 total warnings - style)
- **futures**: Rejected (2 total warnings - style)

### After (Category-Based Filtering)

- **aho-corasick**: ✅ **PASSES** (195 warnings, but 0 bad_code warnings)
- **tokio**: ✅ **PASSES** (1 warning, but 0 bad_code warnings)
- **serde**: ✅ **PASSES** (2 warnings, but 0 bad_code warnings)
- **futures**: ✅ **PASSES** (2 warnings, but 0 bad_code warnings)

Only crates with actual code quality problems (unsafe code, memory safety issues, etc.) will be rejected.

## Example

### ClippyResult Structure

```python
ClippyResult(
    warning_count=195,              # Total warnings
    bad_code_warnings=0,            # Only these cause rejection
    safe_to_ignore_warnings=150,    # Ignored
    questionable_warnings=45,        # Ignored
    error_count=0
)
```

### Filter Logic

```python
# Only check bad_code_warnings
if clippy_result.bad_code_warnings > config.max_bad_code_warnings:
    reject_crate()
```

## Bad Code Warning Patterns

The following warning types will cause rejection (if `max_bad_code_warnings = 0`):

- `unwrap_used`, `expect_used` - Unsafe unwrapping
- `panic`, `panic_in_result_fn` - Panic usage
- `transmute`, `as_conversions` - Unsafe conversions
- `mem_forget`, `let_underscore_drop` - Resource leaks
- `invalid_*` - Invalid operations
- `unused_variables`, `unused_imports` - Actual dead code
- `todo`, `unimplemented` - Incomplete code
- `out_of_bounds_indexing` - Unsafe indexing

## Safe to Ignore Patterns

The following warning types are **ignored**:

- `doc_lazy_continuation` - Documentation formatting
- `too_many_lines` - File length
- `cognitive_complexity` - Complexity metrics
- `similar_names` - Variable naming
- `manual_*` - Manual implementations
- `needless_*` - Needless operations
- `cast_possible_*` - Cast warnings (often intentional)

## Migration

### For Existing Configs

If you have existing configs using `max_clippy_warnings`:

1. **Option 1**: Keep using `max_clippy_warnings` (backward compatible)
2. **Option 2**: Switch to `max_bad_code_warnings = 0` (recommended)

### Recommended Settings

```python
# Recommended: Only reject actual code quality problems
max_bad_code_warnings = 0

# Alternative: Allow some bad_code warnings (not recommended)
max_bad_code_warnings = 5  # Allows up to 5 bad_code warnings
```

## Benefits

1. ✅ **Higher Quality Dataset**: Includes high-quality crates with style warnings
2. ✅ **Better Filtering**: Only rejects actual problems, not style preferences
3. ✅ **More Inclusive**: Captures crates like `aho-corasick`, `tokio`, `serde`
4. ✅ **Maintainable**: Clear separation between style and quality issues

## Technical Details

### Categorization Function

Located in `sigil_pipeline/analyzer.py`:
- `categorize_clippy_warning(code: str) -> str`
- Returns: `"safe_to_ignore"`, `"questionable"`, `"bad_code"`, or `"unknown"`

### ClippyResult Updates

Added fields:
- `bad_code_warnings: int`
- `safe_to_ignore_warnings: int`
- `questionable_warnings: int`

### Filter Updates

`sigil_pipeline/filter.py` now checks:
- `report.clippy.bad_code_warnings > config.max_bad_code_warnings`

