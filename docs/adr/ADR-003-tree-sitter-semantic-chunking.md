# ADR-003: Tree-Sitter for Semantic Chunking

## Status

Accepted

## Context

Phase-2 instruct mode requires splitting large Rust files into appropriately-sized chunks for training. Simple approaches had issues:

1. **Line-based splitting**: Breaks code mid-function, creating invalid snippets
2. **Regex-based splitting**: Fragile, misses nested structures, false positives
3. **Character-based splitting**: Ignores code structure entirely

We needed chunking that:
- Respects semantic boundaries (functions, impl blocks, modules)
- Produces valid, self-contained code snippets
- Handles edge cases (nested structures, macros, attributes)
- Is maintainable and accurate

## Decision

Use tree-sitter-rust for semantic code parsing with regex fallback:

1. **Primary**: tree-sitter-rust parser
   - Accurate AST-based parsing
   - Handles all Rust syntax correctly
   - Identifies function_item, impl_item, struct_item, etc.
   
2. **Fallback**: Regex-based parsing
   - For environments where tree-sitter isn't installed
   - Less accurate but functional
   - Covers main patterns (functions, structs, impls)

Chunking rules:
- Functions: Extract as individual chunks if within size limits
- Impl blocks: Include whole block if ≤5 methods, otherwise extract methods individually
- Structs/Enums/Traits: Extract as individual chunks
- Modules: Include whole module if ≤10 items, otherwise recurse

## Consequences

### Positive

- Semantically valid chunks that make sense as training examples
- Accurate parsing handles edge cases (macros, attributes, generics)
- Graceful degradation when tree-sitter unavailable
- Clear size limits prevent overly long snippets

### Negative

- tree-sitter dependency adds installation complexity
- Regex fallback is less accurate
- Complex nested structures may still produce suboptimal chunks

### Neutral

- tree-sitter is optional (installed via `pip install sigil-pipeline[parsing]`)
- Chunk types are tracked for metrics/debugging

## Alternatives Considered

### Alternative 1: Pure Regex Parsing

Use only regex patterns for all chunking.

**Rejected because:**
- Regex can't handle nested braces correctly
- False positives with string literals containing patterns
- Maintenance burden as Rust syntax evolves

### Alternative 2: Rust Analyzer Integration

Use rust-analyzer's parsing capabilities.

**Rejected because:**
- Heavy dependency for simple chunking needs
- Requires full Rust project context
- Overkill for syntax-only parsing

### Alternative 3: Custom Parser

Write a custom Rust parser in Python.

**Rejected because:**
- Significant development effort
- Rust syntax is complex (macros, proc-macros, etc.)
- tree-sitter already solves this well

## Related

- tree-sitter documentation: https://tree-sitter.github.io/tree-sitter/
- tree-sitter-rust: https://github.com/tree-sitter/tree-sitter-rust
- `sigil_pipeline/chunker.py`





