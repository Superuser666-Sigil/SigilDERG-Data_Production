# Sigil Pipeline v2.3.0

A static analysis pipeline for generating high-quality Rust code datasets for model fine-tuning. The pipeline analyzes Rust crates using static analysis tools and generates training datasets in JSONL format.

> 📖 **Ecosystem Architecture**: For a comprehensive overview of how this project integrates with [SigilDERG-Finetuner](https://github.com/Superuser666-Sigil/SigilDERG-Finetuner) and [human-eval-Rust](https://github.com/Superuser666-Sigil/human-eval-Rust), see [ARCHITECTURE.md](ARCHITECTURE.md).

**Version 2.3.0** includes:
- **Checkpoint/Resume System**: Automatic checkpointing allows resuming long-running pipeline executions without losing progress. Preserves temp directories and skips already-processed crates.
- **Improved Error Injection**: Enhanced error-fixing task generation with fallback to simulated errors when real compilation times out, ensuring more robust task diversity.
- **Enhanced Logging**: Geiger and License checks now always write logs, even when no issues are found, improving observability and debugging.
- **Tool Execution Tracking**: Rejection summaries now include flags indicating which analysis tools were executed or skipped.
- **Enterprise Observability**: Structured logging via structlog, Prometheus-compatible metrics, and optional OpenTelemetry tracing.
- License pre-checking from crates.io API
- Cargo-deny security auditing integration
- Streaming architecture for memory-efficient processing
- Granular filter metrics and observability
- Enhanced quality filtering (unsafe code, outdated dependencies)
- Platform compatibility detection
- Shared cargo target directory for faster builds

## Overview

Sigil Pipeline performs comprehensive static analysis on Rust crates to identify high-quality, idiomatic code suitable for training code generation models. It combines:

- **Curated Rust crates** analyzed through static analysis tools
- **The Stack Rust Clean dataset** files (from HuggingFace)
- **Format validation** to ensure consistent dataset structure

The pipeline generates JSONL datasets with prompt-generation pairs that can be used directly for fine-tuning language models.

## Features

### Static Code Analysis

- **Clippy**: Detects idiomatic code patterns and lint violations
- **Cargo Geiger**: Analyzes unsafe code usage and safety metrics
- **Cargo Outdated**: Assesses dependency maintenance status
- **Cargo License**: Checks license compliance (with centralized verification logic)
- **Cargo Deny**: Performs security and license auditing (optional, configurable)
- **License Pre-Check**: Validates licenses from crates.io API before downloading

### Quality Filtering

- **Rust Edition**: Filters to 2021+ edition crates (modern Rust)
- **Clippy Warnings**: Category-based `max_bad_code_warnings` threshold (default: 0, ignores style/doc lints but blocks unsafe or correctness issues). Legacy `max_clippy_warnings` is still available for total-count filtering.
- **Documentation**: Requires documentation comments on public items
- **Test/Bench Exclusion**: Automatically filters out test and benchmark files
- **Size/Sanity Filters**: Applies Stack dataset filtering criteria (line length, alphabetic ratio)
- **License Filtering**: Only includes permissively licensed code (MIT, Apache-2.0, BSD, etc.) with SPDX expression support
- **Unsafe Code Filtering**: Optional threshold for maximum unsafe code items (from Geiger)
- **Outdated Dependencies**: Optional threshold for maximum outdated dependency ratio
- **Platform Compatibility**: Automatically skips OS-specific crates incompatible with current platform
- **Security Auditing**: Optional cargo-deny integration for security advisories and license violations

### Dataset Generation

- **Prompt Generation**: Creates instruction prompts from code and documentation
  - **Phase 1 Compatible Mode**: Uses exact Phase 1 prompt format for backwards compatibility
  - **Instruct Mode (Phase-2)**: Generates natural language instructions based on code patterns and doc comments
- **Semantic Chunking**: Splits large files into snippet-sized chunks (functions, impl blocks, modules) for Phase-2
- **Task Type Diversity**: Generates multiple task types for Phase-2:
  - Code generation (70% default)
  - Transformations (15% default): sync→async, match→?, iterator conversions
  - Error fixing (10% default): fix compiler errors in broken code with improved fallback to simulated errors when real compilation times out
  - Explanations (5% default): explain code functionality
- **Format Validation**: Ensures consistent dataset structure matching Phase 1 format
- **Stack Dataset Integration**: Streams files from HuggingFace datasets or uses local cache
- **Dataset Merging**: Combines multiple datasets with shuffle and weighting options
  - **Phase-1:Phase-2 Ratio Control**: Set target ratio (e.g., 10:1) for QLoRA training
  - **Auto Up-sampling**: Automatically up-samples Phase-2 if small relative to Phase-1 (prioritizes instruct behavior)
- **Extra Phase-2 Shards**: Append pre-generated instruct-style shards (e.g., experimental upscales) via CLI without moving files
- **Train/Val Split by Source**: Splits datasets keeping whole crates/files together (tests true generalization)
- **Streaming Architecture**: Generator-based pipeline for memory-efficient processing of large datasets
- **Granular Metrics**: Detailed filter reason breakdown for observability

### Checkpoint/Resume System

- **Automatic Checkpointing**: Saves progress periodically (configurable interval, default: every 10 crates)
- **Resume from Interruptions**: Automatically detects and loads checkpoints on startup
- **Temp Directory Preservation**: Reuses existing temp directories when resuming, preserving downloaded crates (saves GBs of re-downloads)
- **Smart Crate Skipping**: Automatically skips already-processed crates to avoid duplicates
- **Config Compatibility Checking**: Verifies config hash to prevent incompatible resumes
- **Checkpoint Location**: Defaults to `output_dir/checkpoint.json`, customizable via `--checkpoint-path`

## Requirements

- **Python 3.12+**
- **Rust toolchain** (1.56+ for 2021 edition, 1.72+ for 2024 edition)
- **Cargo subcommands**:
  - `cargo clippy` (included with rustup)
  - `cargo geiger`
  - `cargo outdated`
  - `cargo license`
  - `cargo deny`

See [docs/SETUP.md](docs/SETUP.md) for detailed setup instructions.

## Installation

```bash
# Clone the repository
git clone https://github.com/Superuser666-Sigil/SigilDERG-Data_Production.git
cd SigilDERG-Data_Production

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[datasets,parsing]"  # Add 'parsing' for Phase-2 semantic chunking

# Install Rust analysis tools
cargo install cargo-geiger cargo-outdated cargo-license cargo-deny
rustup component add clippy
```

## Quick Start

### Command Line

```bash
# Analyze specific crates
python -m sigil_pipeline.main --crates serde tokio actix-web

# Use crate list file
python -m sigil_pipeline.main --crate-list data/crate_list.txt

# Phase-2 Instruct Mode (generates diverse task types with semantic chunking)
python -m sigil_pipeline.main \
  --prompt-mode instruct \
  --max-sft-lines 200 \
  --max-sft-chars 8000 \
  --output output/phase2_dataset.jsonl

# Custom task type distribution for Phase-2
python -m sigil_pipeline.main \
  --prompt-mode instruct \
  --task-mix '{"code_generation": 0.7, "transformations": 0.15, "error_fixing": 0.1, "explanations": 0.05}'

# Include Stack dataset (from local cache)
python -m sigil_pipeline.main \
  --include-stack-dataset \
  --stack-dataset-path "datasets/the-stack-rust-clean" \
  --output output/dataset.jsonl

# Include Stack dataset with streaming fallback
python -m sigil_pipeline.main \
  --include-stack-dataset \
  --stack-dataset-path "datasets/the-stack-rust-clean" \
  --stack-dataset-streaming \
  --output output/dataset.jsonl

# Merge with existing dataset
python -m sigil_pipeline.main \
  --merge-with-phase1 \
  --phase1-dataset-path "data/phase1.jsonl" \
  --shuffle-merged \
  --output output/merged.jsonl

# Merge with Phase-1:Phase-2 ratio control (10:1 ratio, auto up-sample Phase-2 if small)
python -m sigil_pipeline.main \
  --merge-with-phase1 \
  --phase1-dataset-path "data/phase1.jsonl" \
  --phase1-phase2-ratio 10.0 \
  --create-train-val-split \
  --val-ratio 0.1 \
  --output output/phase2.jsonl

# Append experimental / pre-generated Phase-2 shards after generation
python -m sigil_pipeline.main \
  --prompt-mode instruct \
  --crate-list data/crate_list.txt \
  --extra-phase2-shard experimental/phase1_upscaled.jsonl \
  --output datasets/phase2_full.jsonl

# Allow longer real error injection (e.g., 3 minutes for cargo check)
python -m sigil_pipeline.main \
  --prompt-mode instruct \
  --error-injection-timeout 180 \
  --output datasets/phase2_full.jsonl

# Checkpoint/Resume: Automatically saves progress and can resume from interruptions
# Checkpoint is saved to output_dir/checkpoint.json by default
python -m sigil_pipeline.main \
  --crate-list data/crate_list.txt \
  --output datasets/phase2_full.jsonl \
  --checkpoint-interval 10  # Save checkpoint every 10 crates (default)

# Resume from checkpoint (automatically detected if checkpoint.json exists)
python -m sigil_pipeline.main \
  --crate-list data/crate_list.txt \
  --output datasets/phase2_full.jsonl
# Pipeline will automatically skip already-processed crates and reuse temp directory

# Custom checkpoint path
python -m sigil_pipeline.main \
  --checkpoint-path logs/my_checkpoint.json \
  --crate-list data/crate_list.txt \
  --output datasets/phase2_full.jsonl

# Disable checkpointing
python -m sigil_pipeline.main \
  --no-checkpointing \
  --crate-list data/crate_list.txt \
  --output datasets/phase2_full.jsonl
```

### Python API

```python
import asyncio
from sigil_pipeline.config import PipelineConfig
from sigil_pipeline.main import run_pipeline

async def main():
    config = PipelineConfig(
        crates=["serde", "tokio"],
        include_stack_dataset=False,  # Opt-in when Stack is available locally
        output_path="output/dataset.jsonl",
    )
    
    await run_pipeline(config)

if __name__ == "__main__":
    asyncio.run(main())
```

## Configuration

The pipeline uses a `PipelineConfig` dataclass for all settings. Key options:

```python
from sigil_pipeline.config import PipelineConfig

config = PipelineConfig(
    # Crates to analyze
    crates=["serde", "tokio"],
    crate_list_path="data/crate_list.txt",  # Or specify individual crates
    
    # Stack dataset integration (opt-in)
    include_stack_dataset=False,
    stack_dataset_path="ammarnasr/the-stack-rust-clean",
    
    # Quality thresholds
    allow_edition_2018=False,  # Only 2021+ edition
    max_bad_code_warnings=0,  # Strict filter for critical lints (style lints ignored)
    require_docs=True,  # Require documentation
    
    # Advanced filtering
    max_unsafe_items=None,  # Optional: max unsafe code items (None = no filter)
    max_outdated_ratio=None,  # Optional: max outdated dependency ratio
    enable_deny_scan=False,  # Optional: cargo-deny security auditing
    
    # File filtering
    max_line_length=100,  # Matches Stack dataset criteria
    min_alphabetic_ratio=0.3,  # Filters minified code
    
    # Dataset merging
    merge_with_phase1=False,
    phase1_dataset_path=None,
    shuffle_merged=True,
    phase2_weight=1.0,

    # Error injection controls
    enable_error_injection=True,
    error_injection_method="both",
    error_injection_timeout=120,
    
    # Performance
    reuse_cargo_target=True,  # Share cargo target directory (output/cargo_target_cache by default)
    
    # Checkpoint/Resume
    enable_checkpointing=True,  # Enable automatic checkpointing (default: True)
    checkpoint_path=None,  # Custom checkpoint path (default: output_dir/checkpoint.json)
    checkpoint_interval=10,  # Save checkpoint every N crates (default: 10)
    
    # Output
    output_path="output/dataset.jsonl",
    max_threads=4,  # Parallel processing
)
```

Configuration can be loaded from JSON or YAML files:

```bash
python -m sigil_pipeline.main --config config.yaml
```

## Output Format

The pipeline generates JSONL files (one JSON object per line) with the following structure:

```jsonl
{"prompt": "Write a Rust program that demonstrates error handling", "gen": "use anyhow::Result;\n\nfn main() -> Result<()> {\n    // ...\n}"}
{"prompt": "Write a Rust code example that uses iterators", "gen": "fn process_data(items: &[i32]) -> Vec<i32> {\n    items.iter().map(|x| x * 2).collect()\n}"}
```

Each line contains:
- `prompt`: Instruction prompt describing what the code does
- `gen`: Generated code (plain text, UTF-8 encoded)

See [docs/DATASET_SCHEMA.md](docs/DATASET_SCHEMA.md) for detailed format specification.

## Project Structure

```
sigil_pipeline/          # Main pipeline package
├── main.py             # Pipeline orchestration and CLI entry point
├── config.py           # Configuration management
├── crawler.py          # Crate downloading and Stack dataset integration
├── analyzer.py         # Static analysis tools execution
├── filter.py           # Quality filtering heuristics
├── chunker.py          # Semantic code chunking (Phase-2)
├── task_generator.py   # Task type generation (Phase-2)
├── dataset_builder.py  # Prompt generation and dataset assembly
├── dataset_splitter.py # Train/val splitting by source
├── exporter.py         # JSONL export and dataset merging
├── format_validator.py # Format validation
├── observability.py    # Structured logging and metrics
├── telemetry.py        # OpenTelemetry tracing (optional)
└── utils.py            # Utilities (cargo commands, file I/O, etc.)

tools/                   # Dataset utilities
├── analyze_failures.py         # Analyze pipeline rejection reasons
├── convert_jsonl_to_parquet.py # Convert JSONL to Parquet
├── convert_parquet_to_jsonl.py # Convert Parquet to JSONL
├── split_jsonl.py              # Split large JSONL into chunks
├── split_train_val.py          # Create train/val splits
├── rebalance_task_mix.py       # Adjust task type distribution
└── verify_format_test.py       # Validate format compliance

scripts/                 # Setup and release scripts
├── create_release.py           # Release automation
└── setup/
    └── setup_rust_analysis_tools.py  # Install Rust tools

tests/                   # Test suite
benches/                 # Performance benchmarks
docs/                    # Documentation
```

## Tools

The repository includes utility scripts for dataset manipulation and analysis.

### Failure Analysis

`tools/analyze_failures.py`

- Parses the latest (or specified) analysis logs
- Categorizes Clippy warnings (ignores style warnings, flags unsafe/bad code)
- Detects license rejections from the main pipeline log
- Automatically removes license-rejected crates from `data/crate_list.txt` (unless `--no-cleanup`)
- Can write a full report to disk

```bash
# Auto-detect most recent analysis directory
python tools/analyze_failures.py

# Specify locations explicitly
python tools/analyze_failures.py \
  --log-dir logs/analysis_20251124_180335 \
  --log-file logs/phase2_full_run.log \
  --crate-list data/crate_list.txt \
  --output logs/failure_analysis.txt

# Skip automatic crate_list cleanup
python tools/analyze_failures.py --no-cleanup
```

### Dataset Utilities

`tools/split_train_val.py`

- Splits a dataset into train/val files while keeping whole crates/files together.

```bash
python tools/split_train_val.py \
  --input datasets/phase2_full.jsonl \
  --train output/train.jsonl \
  --val output/val.jsonl \
  --val-ratio 0.1
```

`tools/split_jsonl.py`

- Splits large JSONL files into ~11MB chunks without breaking JSON objects.

```bash
python tools/split_jsonl.py \
  --input datasets/phase2_full.jsonl \
  --output-dir datasets/chunks \
  --prefix phase2_chunk
```

`tools/convert_jsonl_to_parquet.py`

- Converts JSONL datasets to Parquet, supporting both training-ready (metadata stripped) and provenance variants.

```bash
python tools/convert_jsonl_to_parquet.py \
  --input datasets/phase2_full.jsonl \
  --output datasets/phase2_full.parquet \
  --variant training
```

`tools/convert_parquet_to_jsonl.py`

- Converts Parquet datasets back to JSONL (useful for inspection or smaller workflows).

```bash
python tools/convert_parquet_to_jsonl.py \
  --input datasets/phase2_full.parquet \
  --output datasets/phase2_roundtrip.jsonl
```

`tools/verify_format_test.py`

- Quick check to ensure a dataset matches the Phase 1 format specification.

```bash
python tools/verify_format_test.py --input datasets/phase2_full.jsonl
```

`tools/rebalance_task_mix.py`

- Downsamples (or lightly reweights) a JSONL dataset to match a desired `_task_type` distribution and writes a summary report.

```bash
python tools/rebalance_task_mix.py \
  --input datasets/phase2_full.jsonl \
  --output datasets/phase2_balanced.jsonl \
  --target-mix code_generation=0.5,error_fixing=0.25,transformations=0.15,explanations=0.10
```

## Testing

```bash
# Run all tests
pytest tests/

# Run format validation tests
pytest tests/test_format_alignment.py -v

# Run property-based tests
pytest tests/test_properties.py -v --hypothesis-show-statistics

# Run local CI checks
python test_ci_local.py
```

## SigilDERG Ecosystem Integration

This package is part of the **SigilDERG ecosystem** for Rust code model training. It integrates seamlessly with:

- **[sigilderg-finetuner](https://github.com/Superuser666-Sigil/SigilDERG-Finetuner)**: QLoRA fine-tuning for Rust code models
- **[human-eval-rust](https://github.com/Superuser666-Sigil/human-eval-Rust)**: Evaluation harness for Rust code generation

### Install Full Ecosystem

```bash
pip install sigil-pipeline[ecosystem]
```

This installs all three packages with proper version constraints.

### Complete Workflow

1. **Generate dataset** (this package):
   ```bash
   python -m sigil_pipeline.main --output datasets/phase2_full.jsonl
   ```

2. **Fine-tune model** (sigilderg-finetuner):
   ```bash
   sigilderg-train configs/llama8b-phase2.yml  # Uses local:datasets/phase2_full.jsonl
   ```

3. **Evaluate model** (human-eval-rust):
   ```bash
   sigilderg-eval samples.jsonl --use-human-eval
   ```

### Unified CLI

Use the unified orchestrator for the complete workflow:

```bash
sigil-ecosystem \
    --crate-list data/crate_list.txt \
    --dataset-path datasets/phase2_full.jsonl \
    --config-path configs/llama8b-phase2.yml
```

See **[Ecosystem Integration Guide](docs/ECOSYSTEM_INTEGRATION.md)** for detailed documentation.

## Documentation

- **[Architecture](ARCHITECTURE.md)**: Complete ecosystem architecture overview
- **[Setup Guide](docs/SETUP.md)**: Rust toolchain and cargo subcommand installation
- **[Dataset Schema](docs/DATASET_SCHEMA.md)**: Detailed dataset format specification
- **[Ecosystem Integration](docs/ECOSYSTEM_INTEGRATION.md)**: Complete workflow guide for all three packages
- **[Clippy Category Filtering](docs/CLIPPY_CATEGORY_FILTERING.md)**: Quality filter documentation
- **[OS-Agnostic Cargo Commands](docs/OS_AGNOSTIC_CARGO_COMMANDS.md)**: Cross-platform cargo usage
- **[Testing CI Locally](docs/TESTING_CI_LOCALLY.md)**: Local CI workflow testing
- **[Architecture Decision Records](docs/adr/)**: Design decisions and rationale

## Docker

The project includes Docker support for containerized execution:

```bash
# Build image
docker build -t sigil-pipeline:2.3.0 .

# Run pipeline
docker-compose up

# Interactive shell
docker run -it sigil-pipeline:2.2.0 bash

# Run with custom arguments
docker run -v $(pwd)/output:/app/output sigil-pipeline:2.2.0 \
    --crate-list /app/data/crate_list.txt \
    --output /app/output/dataset.jsonl
```

See `docker-compose.yml` and `Dockerfile` for configuration details.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- **Rust community** for excellent analysis tools (Clippy, Geiger, etc.)
- **HuggingFace** for the Stack dataset and datasets library
- **The Stack dataset** contributors for providing high-quality Rust code
- **Ammar Nasr** for producing and distributing the Stack Rust Clean Dataset (https://huggingface.co/datasets/ammarnasr/the-stack-rust-clean)

---

**Sigil Pipeline** - Generating high-quality Rust code datasets for model fine-tuning.
