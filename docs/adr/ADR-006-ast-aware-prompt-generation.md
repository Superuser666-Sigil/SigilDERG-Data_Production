# ADR-006: AST-Aware Prompt Generation

## Status

Accepted

## Context

The dataset builder module (`dataset_builder.py`) relied heavily on Regular Expressions (Regex) to:

1. **Detect code patterns** (async, serde, error handling, iterators)
2. **Extract function signatures** (name, params, return type)
3. **Parse struct fields** (for Serde-related prompts)

This approach had significant limitations:

- **Nested generics**: Regex like `fn\s+(\w+)\s*\(([^)]*)\)` fails on `fn foo(x: HashMap<String, Vec<i32>>)` because `[^)]*` greedily captures until the first `)`, breaking on types containing `)`
- **Comments inside code**: A function parameter like `fn foo(/* ) */ x: i32)` breaks param extraction
- **String literals**: Code patterns inside string literals can trigger false positives
- **Macros**: Macro-generated functions don't match expected patterns
- **Complex types**: Lifetimes, where clauses, and trait bounds are difficult to capture reliably

The project already had tree-sitter integration in `chunker.py` for semantic code chunking (see ADR-003). However, the more critical prompt generation path still used fragile regex.

## Decision

Extend tree-sitter usage from chunking to include all code parsing for prompt generation:

1. **Make tree-sitter a required dependency** (moved from `[parsing]` optional extra to core dependencies)
2. **Create `ast_patterns.py` module** with AST-based extraction:
   - `extract_function_signature()` - extracts name, params (including nested generics), return type, lifetimes, where clauses
   - `extract_struct_fields()` - extracts field names and types, handling nested generics correctly
   - `detect_code_patterns_ast()` - AST-based pattern detection that walks the syntax tree
3. **Remove regex fallback code** from `chunker.py` (tree-sitter always available)
4. **Update `dataset_builder.py`** to use AST-based extraction

Additionally, to address concerns about prompt diversity:

5. **Implement pattern combination** - prompts now combine multiple detected patterns (e.g., "async + serde + error handling")
6. **Add seeded template randomization** - action verbs and phrases are randomized for lexical diversity, with configurable seed for reproducibility
7. **Store seed in metadata** - `_prompt_seed` field enables full reproducibility

## Consequences

### Positive

- **Robust parsing**: Correctly handles nested generics, lifetimes, macros, comments in code
- **Simpler codebase**: No fallback paths to maintain, tree-sitter is always available
- **Richer prompts**: Pattern combination produces more natural, diverse instructions
- **Reproducibility**: Seeded randomization allows exact dataset regeneration
- **Extensibility**: AST makes it easy to add new pattern detection

### Negative

- **Mandatory dependency**: tree-sitter and tree-sitter-rust are now required, adding ~5MB to installation
- **Learning curve**: Contributors need to understand tree-sitter AST structure

### Neutral

- **Performance**: Tree-sitter is fast; the overhead is negligible compared to cargo tool execution
- **API stability**: tree-sitter-rust follows the official Rust grammar, updates are infrequent

## Implementation Details

### New Configuration Options

```python
prompt_seed: int | None = None
"""RNG seed for prompt template randomization. If None, uses system random."""

enable_prompt_randomization: bool = True
"""Enable template randomization for prompt diversity."""
```

### New Metadata Fields

```json
{
  "prompt": "...",
  "gen": "...",
  "_prompt_seed": 12345
}
```

### Template Randomization

The system now uses seeded random selection for:
- Action verbs: "Write", "Implement", "Create", "Build", "Design", "Develop"
- Function phrases: "a Rust function", "a function in Rust", "Rust code for a function"
- Pattern-specific phrases for async, error handling, serde, etc.

## Alternatives Considered

### Alternative 1: Enhanced Regex Patterns

Improve existing regex to handle more cases (e.g., recursive matching for nested braces).

**Rejected because:**
- Regex fundamentally cannot parse context-free grammars
- Maintenance burden grows with language complexity
- Edge cases would always exist

### Alternative 2: Keep tree-sitter Optional

Continue with regex fallback when tree-sitter is unavailable.

**Rejected because:**
- Maintaining two code paths is expensive
- Quality disparity between paths creates inconsistency
- tree-sitter is lightweight and widely available

### Alternative 3: LLM-based Prompt Augmentation

Use an LLM to generate diverse prompts from code.

**Rejected because:**
- Expensive at scale
- Non-deterministic (reproducibility concerns)
- Governance/audit challenges
- Overkill for structured template variation

## Related

- ADR-003: Tree-Sitter for Semantic Chunking (original tree-sitter introduction)
- tree-sitter documentation: https://tree-sitter.github.io/tree-sitter/
- tree-sitter-rust: https://github.com/tree-sitter/tree-sitter-rust
- `sigil_pipeline/ast_patterns.py`
- `sigil_pipeline/prompt_templates.py`
- `sigil_pipeline/dataset_builder.py`




