# Setup Guide for SigilDERG Rust Data Pipeline

This guide covers setting up the Rust toolchain and required dependencies for running the pipeline.

## Prerequisites

### Rust Toolchain Requirements

The pipeline requires Rust with support for:
- **Rust Edition 2021**: Requires Rust 1.56.0 or later
- **Rust Edition 2024**: Requires Rust 1.72.0 or later (recommended)

#### Installing Rust

**Windows:**
1. Download and run the installer from [rustup.rs](https://rustup.rs/)
2. Follow the installation wizard
3. Ensure `cargo` is added to your PATH
4. Open a new terminal/PowerShell window to verify:
   ```powershell
   rustc --version
   cargo --version
   ```

**Linux/macOS:**
```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env
rustc --version
cargo --version
```

### Multi-Version Toolchain Support

The pipeline can work with multiple Rust toolchain versions. To enable this:

```bash
# Install multiple toolchain versions
rustup install 1.76.0
rustup install 1.75.0
rustup install stable

# List installed toolchains
rustup toolchain list

# The pipeline will automatically select the best matching toolchain
# for each crate based on its requirements
```

The pipeline includes functions to:
- Discover installed toolchains: `get_installed_toolchains()`
- Select best matching version: `find_best_toolchain(requested, installed)`

These functions automatically handle version matching and fallback to stable if needed.

### C Compiler Requirements

Some cargo subcommands (like `cargo-audit`) require a C compiler:

**Windows:**
- Install [Visual Studio Build Tools](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022)
- Or install [MinGW-w64](https://www.mingw-w64.org/downloads/)
- Ensure the compiler is in your PATH

**Linux:**
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install build-essential

# Fedora
sudo dnf install gcc
```

**macOS:**
```bash
xcode-select --install
```

## Required Cargo Subcommands

The pipeline uses several cargo subcommands for static analysis. Install them with:

```bash
cargo install cargo-clippy  # Usually pre-installed with Rust
cargo install cargo-geiger
cargo install cargo-outdated
cargo install cargo-license
cargo install cargo-deny
```

### Verification

Verify all tools are installed:

```bash
cargo clippy --version
cargo geiger --version
cargo outdated --version
cargo license --version
cargo deny --version
```

### API Evolution Tracking (Optional)

To enable API evolution tracking across Rust versions:

1. Clone the Rust repository:

   ```bash
   git clone https://github.com/rust-lang/rust.git rust-repo
   cd rust-repo
   ```

1. Install additional dependency:

   ```bash
   pip install gitpython
   ```

1. The API tracker will automatically checkout versions as needed.

Usage:

```python
from sigil_pipeline.api_tracker import APIChangeDetector
from pathlib import Path

detector = APIChangeDetector(Path("./rust-repo"))
changes = detector.detect_changes("1.76.0", "1.77.0")
```

See [API Evolution Tracking](API_EVOLUTION_TRACKING.md) for detailed documentation.

## Python Environment Setup

### Virtual Environment

Create and activate a virtual environment:

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Linux/macOS:**
```bash
python -m venv .venv
source .venv/bin/activate
```

### Install Dependencies

Install the project with optional dependencies:

```bash
# Basic installation
pip install -e .

# With observability features (structured logging, OpenTelemetry)
pip install -e ".[observability]"

# With all optional dependencies
pip install -e ".[datasets,web,ai,ml,observability]"

# Enterprise bundle (observability + advanced testing)
pip install -e ".[enterprise]"
```

### Observability Configuration

The pipeline supports enterprise-grade observability. Key options in `PipelineConfig`:

| Option | Default | Description |
|--------|---------|-------------|
| `enable_structured_logging` | `True` | Use structlog for JSON logging |
| `json_logs` | `False` | Output logs as JSON (for production) |
| `log_file` | `None` | Path to log file |
| `enable_prometheus_output` | `False` | Export Prometheus metrics |
| `capture_environment` | `True` | Capture toolchain fingerprint |

The pipeline automatically writes reproducibility artifacts:
- `output/metrics.json` - Run statistics and config
- `output/environment.json` - Toolchain fingerprint (rustc, cargo versions, etc.)
- `output/metrics.prom` - Prometheus metrics (if enabled)

## Automated Setup

You can use the setup scripts in `scripts/setup/` to install Rust analysis tools:

```bash
# Install Rust analysis tools
python scripts/setup/setup_rust_analysis_tools.py
```

This will:
- Check if Rust toolchain is installed
- Verify required cargo subcommands
- Install missing tools (with user confirmation)
- Display setup status

## Troubleshooting

### Common Issues

**Issue: `cargo: command not found`**
- **Solution**: Ensure Rust is installed and `cargo` is in your PATH
- On Windows, restart your terminal after installation
- Verify with: `cargo --version`

**Issue: `cargo-geiger` fails to install**
- **Solution**: Ensure you have a C compiler installed (see C Compiler Requirements above)
- On Windows, install Visual Studio Build Tools or MinGW-w64

**Issue: `cargo-deny` installation fails**
- **Solution**: `cargo-deny` requires OpenSSL on some platforms
- On Windows, you may need to install OpenSSL or use pre-built binaries
- On Linux: `sudo apt-get install libssl-dev` (Ubuntu/Debian)

**Issue: Platform-specific crate compilation failures**
- **Solution**: This is expected for crates with OS-specific dependencies
- The pipeline automatically skips incompatible crates
- See platform compatibility documentation for details

**Issue: HuggingFace datasets library not found**
- **Solution**: Install with `pip install datasets` or `pip install -e ".[datasets]"`
- The pipeline will gracefully fall back to local directory mode if not available

### Version Compatibility

- **Python**: 3.12 or later
- **Rust**: 1.56.0+ (for 2021 edition), 1.72.0+ (for 2024 edition)
- **Cargo subcommands**: Latest stable versions recommended

### Platform-Specific Notes

**Windows:**
- Use PowerShell or Command Prompt (not Git Bash for cargo commands)
- Ensure `cargo.exe` is accessible in PATH
- Some tools may require Visual Studio Build Tools for C compilation

**Linux:**
- Most tools install cleanly via `cargo install`
- May need `libssl-dev` for some tools
- Ensure `~/.cargo/bin` is in your PATH

**macOS:**
- Requires Xcode Command Line Tools
- Some tools may need Homebrew-installed dependencies
- Ensure `~/.cargo/bin` is in your PATH

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage


### Parquet Format

If your Phase 1 dataset is in parquet format (e.g., from HuggingFace), you'll need to convert it first:
```python
import pandas as pd
from pathlib import Path

# Read parquet files
df = pd.read_parquet("datasets/data/train-*.parquet")

# Convert to JSONL
with open("datasets/phase1.jsonl", "w") as f:
    for _, row in df.iterrows():
        # Adjust field names as needed
        sample = {
            "prompt": row.get("prompt") or row.get("instruction", ""),
            "gen": row.get("gen") or row.get("output") or row.get("content", "")
        }
        f.write(json.dumps(sample) + "\n")
```

Or use the HuggingFace datasets library:
```python
from datasets import load_dataset

dataset = load_dataset("your-dataset-name", split="train")
dataset.to_json("datasets/phase1.jsonl")
```

## Next Steps

After setup is complete:

1. Verify installation: Check that all cargo subcommands are available
2. Run a test: `python -m sigil_pipeline.main --crates serde --limit 1`
3. Check the output in the `output/` directory

For more information, see:
- [Dataset Schema](DATASET_SCHEMA.md) for output format details
- [OS-Agnostic Cargo Commands](OS_AGNOSTIC_CARGO_COMMANDS.md) for cross-platform usage

