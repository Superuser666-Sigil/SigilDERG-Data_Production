# API Evolution Tracking

The Sigil Pipeline includes comprehensive API evolution tracking capabilities to detect changes in Rust APIs across versions.

## Overview

The API tracker module extracts API entities from Rust source code and detects changes between versions, including:

- **Stabilized APIs**: New APIs that became stable
- **Deprecated APIs**: APIs marked as deprecated
- **Signature Changes**: APIs with changed function signatures
- **Implicit Changes**: APIs with same signature but changed behavior

## Usage

```python
from sigil_pipeline.api_tracker import APIChangeDetector
from pathlib import Path

detector = APIChangeDetector(Path("./rust-repo"))
changes = detector.detect_changes("1.76.0", "1.77.0")

for change in changes:
    print(f"{change.change_type}: {change.api.name}")
    print(f"  {change.details}")
```

## Components

### APIEntity

Represents a Rust API entity with:

- `name`: Entity name
- `module`: Module path (e.g., 'std::fs')
- `entity_type`: function, struct, enum, trait, method, macro
- `signature`: Full signature string
- `documentation`: Documentation comments
- `examples`: Example code blocks
- `attributes`: Rust attributes (#[stable], #[deprecated], etc.)
- `version`: Rust version where found

### APIChange

Represents a detected API change:

- `api`: The changed API entity
- `change_type`: stabilized, deprecated, signature, implicit
- `from_version`: Source version
- `to_version`: Target version
- `details`: Human-readable description

### RustASTParser

Tree-sitter based parser that extracts public API entities from Rust files.

### APIChangeDetector

Main class for detecting changes between versions:

- Extracts APIs from each version
- Compares signatures and attributes
- Detects stabilization and deprecation
- Identifies implicit behavioral changes

## Requirements

- Git repository of Rust source code
- Tree-sitter-rust for parsing
- Sufficient disk space for version checkouts
- Optional: gitpython for version checkout automation

## Static Usage Analysis

The pipeline also includes static API usage analysis via `usage_analyzer.py`:

```python
from sigil_pipeline.usage_analyzer import APIUsageAnalyzer

analyzer = APIUsageAnalyzer()
result = analyzer.analyze_usage(code, "File", "std::fs")

print(f"Confidence: {result.confidence}")
print(f"Usage type: {result.usage_type}")
print(f"Locations: {result.usage_locations}")
```

### UsageAnalysis

Results include:

- `api_name`: Name of the API analyzed
- `module_path`: Expected module path
- `confidence`: Score from 0.0 to 1.0
- `usage_type`: direct_call, qualified_call, import_only, struct_init, method_call
- `import_statement`: Import statement if found
- `usage_locations`: List of (line, column) tuples

## Related Documentation

- [ADR-009: API Evolution Tracking](adr/ADR-009-api-evolution-tracking.md)
- [AST Patterns](../sigil_pipeline/ast_patterns.py)
