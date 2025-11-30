# API Evolution Tracking

## Overview

The SigilDERG pipeline includes an API evolution tracking system that monitors how Rust library APIs change between versions. This enables generation of training data that teaches models about API migrations, deprecations, and version-specific patterns.

## Components

### api_tracker.py

The `APITracker` class compares API entities between crate versions:

```python
from sigil_pipeline.api_tracker import APITracker, compare_versions

# Initialize tracker
tracker = APITracker()

# Compare versions
changes = compare_versions(
    old_entities=old_api_entities,
    new_entities=new_api_entities,
    old_version="1.0.0",
    new_version="2.0.0"
)

# Access changes
for change in changes:
    print(f"{change.change_type}: {change.entity_name}")
    print(f"  Old signature: {change.old_signature}")
    print(f"  New signature: {change.new_signature}")
```

### usage_analyzer.py

Static analysis module for detecting API usage patterns:

```python
from sigil_pipeline.usage_analyzer import (
    UsageAnalyzer,
    StaticUsageAnalyzer,
    analyze_api_usage
)

# Analyze API usage in code
analyzer = StaticUsageAnalyzer()
usages = analyzer.analyze(source_code)

# Check for deprecated APIs
deprecated = [u for u in usages if u.is_deprecated]
```

### ast_patterns.py Extensions

The AST patterns module was extended with API entity extraction:

```python
from sigil_pipeline.ast_patterns import (
    APIEntity,
    extract_all_api_entities,
    check_function_in_code
)

# Extract all API entities from source
entities = extract_all_api_entities(rust_source_code)

for entity in entities:
    print(f"{entity.kind}: {entity.name}")
    print(f"  Signature: {entity.signature}")
    print(f"  Public: {entity.is_public}")
    print(f"  Location: lines {entity.start_line}-{entity.end_line}")

# Check if a function exists in code
exists = check_function_in_code("my_function", rust_source_code)
```

## API Entity Types

The system tracks the following entity kinds:

| Kind | Description |
|------|-------------|
| `function` | Free functions (`fn foo()`) |
| `method` | Impl block methods (`impl T { fn bar() }`) |
| `struct` | Struct definitions |
| `enum` | Enum definitions |
| `trait` | Trait definitions |
| `const` | Constant definitions |
| `type` | Type aliases |
| `macro` | Macro definitions |

## Change Types

API changes are classified as:

| Change Type | Description |
|-------------|-------------|
| `added` | New API entity in newer version |
| `removed` | API entity no longer exists |
| `modified` | Signature or attributes changed |
| `deprecated` | Entity marked as deprecated |
| `renamed` | Entity name changed |

## Usage Examples

### Generating Migration Training Data

```python
from sigil_pipeline.api_tracker import compare_versions
from sigil_pipeline.ast_patterns import extract_all_api_entities

# Load crate sources at different versions
old_src = load_crate_source("serde", "1.0.0")
new_src = load_crate_source("serde", "1.0.200")

# Extract APIs
old_entities = extract_all_api_entities(old_src)
new_entities = extract_all_api_entities(new_src)

# Find changes
changes = compare_versions(old_entities, new_entities, "1.0.0", "1.0.200")

# Generate training prompts
for change in changes:
    if change.change_type == "modified":
        prompt = f"Update code using {change.entity_name} from v{change.old_version} to v{change.new_version}"
        # Generate completion showing migration
```

### Detecting Usage of Deprecated APIs

```python
from sigil_pipeline.usage_analyzer import StaticUsageAnalyzer

analyzer = StaticUsageAnalyzer()

user_code = '''
use serde::Serialize;

#[derive(Serialize)]
struct MyData {
    field: String,
}
'''

usages = analyzer.analyze(user_code)
for usage in usages:
    if usage.is_deprecated:
        print(f"Warning: {usage.api_name} is deprecated since {usage.deprecated_since}")
```

## Testing

The API tracking components have comprehensive test coverage:

```bash
# Test API tracker
pytest tests/test_api_tracker.py -v

# Test usage analyzer
pytest tests/test_usage_analyzer.py -v

# Test AST pattern extensions
pytest tests/test_ast_patterns.py -v -k "api_entity or check_function"
```

## Configuration

API tracking settings in configuration:

```yaml
# config.yaml
api_tracking:
  enabled: true
  track_private: false  # Only track public APIs
  compare_signatures: true
  detect_renames: true
  similarity_threshold: 0.8  # For rename detection
```

## Related Documentation

- [ADR-009: API Evolution Tracking](adr/ADR-009-api-evolution-tracking.md) - Architecture decision
- [ADR-010: Comprehensive Test Coverage](adr/ADR-010-comprehensive-test-coverage.md) - Testing strategy
- [ADVANCED_ENHANCEMENTS.md](../ADVANCED_ENHANCEMENTS.md) - Implementation roadmap

## Limitations

1. **Tree-sitter based**: Parsing relies on tree-sitter-rust, which may not handle all edge cases
2. **No semantic analysis**: Type inference and trait resolution not performed
3. **Local analysis only**: Cross-crate dependencies not tracked
4. **Signature comparison**: Uses string-based comparison, not semantic equivalence
