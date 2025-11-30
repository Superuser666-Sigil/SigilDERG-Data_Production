# Toolchain Management

The Sigil Pipeline includes utilities for managing and selecting Rust toolchains when analyzing crates that require specific Rust versions.

## Overview

The pipeline can work with multiple installed Rust toolchain versions. When a crate requires a specific Rust version, the pipeline automatically selects the best matching installed toolchain.

## Functions

### `get_installed_toolchains()`

Lists all Rust toolchains installed on the system via rustup.

**Returns:** List of toolchain identifiers (e.g., `["stable", "1.76.0-x86_64-pc-windows-msvc"]`)

**Example:**
```python
from sigil_pipeline.utils import get_installed_toolchains

toolchains = get_installed_toolchains()
print(toolchains)
# ['stable', '1.76.0-x86_64-pc-windows-msvc', 'nightly-2024-01-15']
```

### `find_best_toolchain(requested_version, installed_toolchains)`

Finds the best matching toolchain for a requested version with intelligent fallback.

**Parameters:**
- `requested_version`: Version string (e.g., "1.76.0", "stable", "nightly")
- `installed_toolchains`: List from `get_installed_toolchains()`

**Returns:** Best matching toolchain identifier, or "stable" as fallback

**Matching Logic:**
1. Exact match if requested version is installed
2. Prefix matching for "stable", "nightly", "beta"
3. Semantic version matching (finds closest version)
4. Fallback to stable if no match

**Example:**
```python
from sigil_pipeline.utils import get_installed_toolchains, find_best_toolchain

installed = get_installed_toolchains()
best = find_best_toolchain("1.76.0", installed)
# Returns: "1.76.0-x86_64-pc-windows-msvc" if installed
# Or closest version if exact match not found
```

## Integration with Environment Fingerprinting

Toolchain management complements the existing environment fingerprinting system:

- **`capture_toolchain_info()`**: Records toolchain versions for reproducibility
- **`get_installed_toolchains()`**: Discovers available toolchains for selection
- **`find_best_toolchain()`**: Selects appropriate toolchain for analysis

Both systems work together to ensure reproducible analysis with appropriate toolchain selection.

## Usage in Pipeline

The pipeline automatically uses toolchain management when:

1. Crates specify required Rust versions in metadata
2. Multi-version analysis is enabled
3. Fallback to stable is needed

No manual configuration required - the pipeline handles toolchain selection automatically.
