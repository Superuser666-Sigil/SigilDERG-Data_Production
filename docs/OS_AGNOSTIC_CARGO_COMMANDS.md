# OS-Agnostic Cargo Command Construction

## Overview

This document explains how the pipeline ensures cargo commands work correctly across Windows, Linux, and macOS without hardcoding platform-specific executables.

---

## Problem

On Windows, cargo is typically available as `cargo.exe`, while on Unix-like systems (Linux, macOS), it's `cargo`. Hardcoding either can cause failures:

```python
# ❌ BAD: Hardcoded for Unix
cmd = ["cargo", "build"]

# ❌ BAD: Hardcoded for Windows
cmd = ["cargo.exe", "build"]
```

---

## Solution: `utils` Module

The `sigil_pipeline/utils.py` module provides OS-agnostic functions for constructing cargo commands.

### Functions

#### `get_cargo_command() -> str`
Returns the appropriate cargo executable name for the current platform:
- Windows: `"cargo.exe"` (if available) or `"cargo"`
- Linux/macOS: `"cargo"`

**Example**:
```python
from sigil_pipeline.utils import get_cargo_command

cargo_cmd = get_cargo_command()
# On Windows: "cargo.exe"
# On Linux/macOS: "cargo"
```

#### `build_cargo_command(subcommand: str, *args: str) -> List[str]`
Builds a cargo command list with OS-agnostic cargo executable.

**Example**:
```python
from sigil_pipeline.utils import build_cargo_command

# Build cargo build command
cmd = build_cargo_command("build", "--release")
# On Windows: ["cargo.exe", "build", "--release"]
# On Linux/macOS: ["cargo", "build", "--release"]

# Build cargo clippy command with flags
cmd = build_cargo_command("clippy", "--message-format=json", "--", "-W", "clippy::all")
# On Windows: ["cargo.exe", "clippy", "--message-format=json", "--", "-W", "clippy::all"]
```

#### `build_cargo_subcommand_command(subcommand: str, *args: str) -> List[str]`
Builds a cargo subcommand command (e.g., `cargo audit`, `cargo geiger`).

**Example**:
```python
from sigil_pipeline.utils import build_cargo_subcommand_command

# Build cargo audit command
cmd = build_cargo_subcommand_command("audit", "--json")
# On Windows: ["cargo.exe", "audit", "--json"]
# On Linux/macOS: ["cargo", "audit", "--json"]

# Build cargo geiger command
cmd = build_cargo_subcommand_command("geiger", "--format", "json")
# On Windows: ["cargo.exe", "geiger", "--format", "json"]
```

#### `check_cargo_available() -> bool`
Checks if cargo is available in the system PATH.

**Example**:
```python
from sigil_pipeline.utils import check_cargo_available

if not check_cargo_available():
    raise RuntimeError("cargo not found in PATH")
```

---

## Usage Examples

### Before (Platform-Specific)
```python
# ❌ Hardcoded for Unix
cmd = ["cargo", "build", "--release"]

# ❌ Hardcoded for Windows
if platform.system() == "Windows":
    cmd = ["cargo.exe", "build", "--release"]
else:
    cmd = ["cargo", "build", "--release"]
```

### After (OS-Agnostic)
```python
# ✅ OS-agnostic
from sigil_pipeline.utils import build_cargo_command

cmd = build_cargo_command("build", "--release")
# Works on all platforms
```

---

## Migration Guide

### Step 1: Import the utility
```python
from sigil_pipeline.utils import (
    build_cargo_command,
    build_cargo_subcommand_command,
)
```

### Step 2: Replace hardcoded commands

**Cargo commands** (build, test, check, clippy, fmt, doc):
```python
# Before
cmd = ["cargo", "build"]

# After
cmd = build_cargo_command("build")
```

**Cargo subcommands** (audit, geiger, outdated, tree):
```python
# Before
cmd = ["cargo", "audit", "--json"]

# After
cmd = build_cargo_subcommand_command("audit", "--json")
```

**Commands with toolchain specifiers**:
```python
# Before
cmd = ["cargo", "+stable", "check"]

# After
cmd = build_cargo_command("+stable", "check")
```

---

## Current Usage

The `sigil_pipeline` package uses OS-agnostic cargo commands throughout:

1. **`sigil_pipeline/analyzer.py`**
   - Uses `build_cargo_command()` and `build_cargo_subcommand_command()` for all cargo tool invocations
   - Handles Clippy, Geiger, outdated, license, and deny commands

2. **`sigil_pipeline/utils.py`**
   - Contains all cargo utility functions
   - Provides `get_cargo_command()`, `build_cargo_command()`, `build_cargo_subcommand_command()`, and `check_cargo_available()`

---

## Testing

### Manual Testing

Test on different platforms:

**Windows**:
```powershell
python -c "from sigil_pipeline.utils import get_cargo_command; print(get_cargo_command())"
# Expected: cargo.exe
```

**Linux/macOS**:
```bash
python -c "from sigil_pipeline.utils import get_cargo_command; print(get_cargo_command())"
# Expected: cargo
```

### Automated Testing

Add tests to verify OS-agnostic behavior:

```python
def test_get_cargo_command():
    cmd = get_cargo_command()
    assert cmd in ["cargo", "cargo.exe"]
    
def test_build_cargo_command():
    cmd = build_cargo_command("build", "--release")
    assert cmd[0] in ["cargo", "cargo.exe"]
    assert cmd[1] == "build"
    assert cmd[2] == "--release"
```

---

## Benefits

1. **Cross-Platform Compatibility**: Works on Windows, Linux, and macOS without modification
2. **Maintainability**: Single source of truth for cargo command construction
3. **Reliability**: Automatically handles platform differences
4. **Consistency**: All cargo commands use the same approach

---

## Edge Cases

### Cargo Not in PATH

If cargo is not in PATH, `get_cargo_command()` will still return a default:
- Windows: `"cargo.exe"` (Windows convention)
- Unix: `"cargo"` (Unix convention)

The subprocess call will fail with a clear error message, which is better than silently using the wrong executable.

### Custom Cargo Installations

If cargo is installed in a custom location, ensure it's in PATH or set `CARGO_HOME` environment variable. The `_get_env_with_cargo_path()` function in `subprocess_utils.py` handles adding cargo bin to PATH automatically.

---

## Related Documentation

- `docs/SETUP.md` - Setup guide for Rust toolchain and cargo subcommands
- `sigil_pipeline/utils.py` - Implementation of cargo command utilities

