# SigilDERG Ecosystem Architecture

**Version:** 2.0.0  
**Last Updated:** 2025-11-28

This document provides a comprehensive overview of how the three SigilDERG projects work together to create a complete pipeline for training and evaluating Rust code generation models.

## Overview

The SigilDERG ecosystem consists of three integrated components:

1. **SigilDERG-Data_Production** (`sigil-pipeline`) - Generates high-quality Rust code datasets
2. **SigilDERG-Finetuner** (`sigilderg-finetuner`) - Fine-tunes language models on Rust code using QLoRA
3. **human-eval-Rust** (`human-eval-rust`) - Evaluates model performance on standardized Rust programming problems

```
┌─────────────────────┐
│  Data Production    │
│  (sigil-pipeline)   │
│                     │
│  Generates JSONL    │
│  datasets from      │
│  Rust crates        │
└──────────┬──────────┘
           │
           │ JSONL files
           │ (prompt/gen format)
           ▼
┌─────────────────────┐
│     Finetuner       │
│(sigilderg-finetuner)│
│                     │
│  Trains models on   │
│  generated datasets │
│  using QLoRA        │
└──────────┬──────────┘
           │
           │ Checkpoints
           │ (HuggingFace)
           ▼
┌─────────────────────┐
│  human-eval-Rust    │
│                     │
│  Evaluates model    │
│  performance on     │
│  HumanEval problems │
└─────────────────────┘
```

---

## How to Use This Document

**If you are a Lambda engineer** → Jump to [Complete Workflow Example](#complete-workflow-example) for step-by-step commands.

**If you are a researcher** → Read [3. human-eval-Rust](#3-human-eval-rust) and [Policy Enforcement](#policy-enforcement) for evaluation methodology.

**If you are infrastructure/PM** → Skim [Hardware Requirements Summary](#hardware-requirements-summary) and [Integration Points](#integration-points) for resource planning.

---

## 1. Data Production (sigil-pipeline)

### Purpose

Generates high-quality, instruction-style Rust code datasets from real-world crates using static analysis and quality filters.

### Output: Dataset Format

**File Format:** JSONL (JSON Lines) - one sample per line, UTF-8 encoded

**Output Location:** Specified via `--output` flag (default: `output/sigil_phase2_dataset.jsonl`)

**Schema:**

```json
{
  "prompt": "Write a Rust function that parses a configuration file...",
  "gen": "pub fn parse_config(path: &str) -> Result<Config, Error> {\n    // ... code ...\n}",
  "split": "train",
  "_source_crate": "example-crate",
  "_source_file": "src/config.rs",
  "_task_type": "code_generation",
  "_source": "phase2"
}
```

**Required Fields:**
- `prompt` (string): Instruction/prompt text
- `gen` (string): Expected code output/completion

**Optional Fields:**
- `split` (string): `"train"` or `"val"` - preserved even when metadata removed
- `_source_crate` (string): Source crate name (metadata)
- `_source_file` (string): Source file path (metadata)
- `_task_type` (string): Task type enum - `"code_generation"`, `"transformations"`, `"error_fixing"`, `"explanations"` (metadata)
- `_source` (string): Dataset source identifier (metadata)

**Note:** All fields starting with `_` are metadata and are removed by default when `remove_metadata=True` (default behavior). The `split` field is preserved since it doesn't start with `_`.

### Task Types

The `_task_type` field categorizes samples:

- **`code_generation`** (~70%): Standard code generation tasks
- **`transformations`** (~15%): Code transformation tasks (sync→async, match→?, etc.)
- **`error_fixing`** (~10%): Fix compilation errors
- **`explanations`** (~5%): Explain code or generate documentation

### CLI Reference

```bash
python -m sigil_pipeline.main --help
```

**Key Arguments:**

| Argument | Default | Description |
|----------|---------|-------------|
| `--crates` | - | Specific crate names to process |
| `--crate-list` | `data/crate_list.txt` | Path to crate list file |
| `--output` | `output/sigil_phase2_dataset.jsonl` | Output JSONL path |
| `--prompt-mode` | `phase1_compat` | `phase1_compat` or `instruct` |
| `--max-sft-lines` | `200` | Max lines per snippet (Phase-2) |
| `--max-sft-chars` | `8000` | Max chars per snippet (Phase-2) |
| `--max-threads` | `4` | Parallel processing threads |
| `--limit` | - | Limit number of crates |
| `--create-train-val-split` | `false` | Create train/val split |
| `--val-ratio` | `0.1` | Validation set ratio |
| `--config` | - | Path to YAML/JSON config file |

### Output Modes

#### Phase-1 Compatible Mode

```bash
python -m sigil_pipeline.main \
    --crate-list data/crate_list.txt \
    --prompt-mode phase1_compat \
    --output datasets/phase1_full.jsonl
```

**Characteristics:**
- Fixed prompt: `"Write a Rust code snippet. Output only the code."`
- Library-sized modules (can be very large, up to ~1MB per sample)
- Average gen length: ~12,279 characters
- Median gen length: ~3,671 characters

#### Phase-2 Instruct Mode (Recommended)

```bash
python -m sigil_pipeline.main \
    --crate-list data/crate_list.txt \
    --prompt-mode instruct \
    --max-sft-lines 200 \
    --max-sft-chars 8000 \
    --output datasets/phase2_full.jsonl \
    --create-train-val-split \
    --val-ratio 0.1
```

**Characteristics:**
- Natural language instructions based on doc comments, function signatures, code patterns
- Concise snippets (max 200 lines, 8000 chars by default)
- Diverse, natural language prompts
- Task type diversity
- Semantic chunking (functions, impl blocks, modules)

### Quality Filters

The pipeline applies multiple quality filters:

| Filter | Default | Description |
|--------|---------|-------------|
| **Rust Edition** | 2021+ | Only modern Rust crates |
| **Clippy Warnings** | Category-based | Blocks unsafe/correctness issues, ignores style/doc lints |
| **Documentation** | Required | Requires doc comments on public items |
| **Test/Bench Exclusion** | Auto | Filters out test and benchmark files |
| **License Filtering** | MIT, Apache-2.0, BSD, ISC | Permissive licenses only |
| **Unsafe Code** | Optional | Threshold for maximum unsafe code items |
| **Outdated Dependencies** | Optional | Threshold for maximum outdated ratio |
| **Platform Compatibility** | Auto | Skips OS-specific crates incompatible with current platform |
| **Security Auditing** | Optional | cargo-deny integration |

### Train/Val Split

When `--create-train-val-split` is enabled:

- Samples are grouped by `_source_crate` for splitting
- Entire crates are kept together (no mixing train/val)
- Ensures no data leakage between train and validation sets
- Each sample is tagged with explicit `split` field (`"train"` or `"val"`)
- The `split` field is preserved even when metadata is removed

### Checkpointing

The pipeline supports automatic checkpointing for resumable runs:

```bash
python -m sigil_pipeline.main \
    --crate-list data/crate_list.txt \
    --checkpoint-path output/checkpoint.json \
    --checkpoint-interval 10
```

- Saves state every N crates (default: 10)
- Automatically resumes from last checkpoint
- Config hash validation ensures compatible configs

### Observability

The pipeline includes enterprise-grade observability features:

- **Structured Logging**: via `structlog` with JSON output support
- **Metrics Collection**: Prometheus-compatible metrics
- **Distributed Tracing**: OpenTelemetry integration (optional)

Install observability dependencies:

```bash
pip install sigil-pipeline[observability]
```

---

## 2. Finetuner (sigilderg-finetuner)

### Purpose

Fine-tunes large language models (e.g., Llama-3.1-8B-Instruct) on Rust code datasets using QLoRA (Quantized Low-Rank Adaptation) for efficient training with reduced memory requirements.

### How It Consumes Data

The finetuner can consume data from multiple sources:

1. **Local JSONL files** (from sigil-pipeline) - `local:path/to/file.jsonl`
2. **Parquet files** (converted from JSONL) - `parquet:path/to/file.parquet`
3. **HuggingFace datasets** - `username/dataset-name`

### Data Path Configuration

**Config File Format (YAML):**

```yaml
dataset:
  names:
    - local:datasets/phase2_full.jsonl  # Direct JSONL from pipeline
    # OR
    - parquet:datasets/phase2_training.parquet  # Converted Parquet
    # OR
    - ammarnasr/the-stack-rust-clean  # HuggingFace dataset
  use_cache: true  # Cache tokenized data for faster subsequent runs
  min_length: 64  # Minimum sequence length
  max_length: 200_000  # Maximum sequence length
  # Interleaving options
  interleave_mode: "weighted"  # "sequential", "round-robin", or "weighted"
  dataset_weights:
    "local:datasets/phase2_full.jsonl": 0.7
    "ammarnasr/the-stack-rust-clean": 0.3
  # Task type oversampling (uses _task_type field from pipeline)
  task_weights:
    "code_generation": 1.0
    "transformations": 1.5  # Oversample transformations
    "error_fixing": 1.2
    "explanations": 0.8  # Undersample explanations
```

### Data Loading Process

1. **JSONL Loading** (`local:` prefix):
   - Reads `prompt` and `gen` fields from JSONL
   - Combines them: `f"{prompt}\n\n{gen}"` or applies chat template
   - Optionally removes metadata fields (those starting with `_`)
   - Supports `_task_type`-aware oversampling via `task_weights`

2. **Parquet Loading** (`parquet:` prefix):
   - Reads Parquet files (typically converted from JSONL)
   - Same format expectations as JSONL
   - Faster loading for large datasets

3. **HuggingFace Loading**:
   - Standard HuggingFace dataset loading
   - Supports streaming for large datasets

### Config Knobs

**Dataset Configuration:**

```yaml
dataset:
  names: []  # List of dataset sources
  use_cache: true  # Cache tokenized data
  min_length: 64  # Minimum sequence length filter (in tokens, post-tokenization)
  max_length: 200_000  # Maximum sequence length filter (in tokens, post-tokenization)
  exclude_tests: true  # Exclude test files
  exclude_examples: true  # Exclude example files
  exclude_benches: true  # Exclude benchmark files
  prefer_idiomatic: true  # Quality heuristics
  prefer_documented: true  # Quality heuristics
  idiomatic_quality_ratio: 2.0  # Quality threshold
  shuffle_seed: 42  # Random seed for shuffling
  interleave_mode: "weighted"  # How to mix datasets
  dataset_weights: {}  # Per-dataset weights
  task_weights: {}  # Per-task-type oversampling weights
```

**Training Configuration:**

```yaml
train:
  micro_batch_size: 16  # Batch size per GPU
  gradient_accumulation: 4  # Effective batch = 16*4=64
  num_steps: 12000  # Training steps
  lr: 1.0e-4  # Learning rate
  warmup_steps: 100  # Warmup steps
  logging_steps: 12  # Logging frequency
  save_every: 500  # Checkpoint frequency
  bf16: true  # Use bfloat16
  grad_checkpointing: true  # Gradient checkpointing
  max_grad_norm: 1.0  # Gradient clipping
  use_flash_attention: true  # Flash Attention 2
  dataloader_num_workers: 48  # Data loading workers
  dataloader_pin_memory: true  # Faster CPU-GPU transfers
  dataloader_prefetch_factor: 4  # Prefetch batches
```

**QLoRA Configuration:**

```yaml
lora:
  r: 16  # LoRA rank
  alpha: 16  # LoRA alpha
  dropout: 0.05  # LoRA dropout
  target_modules:  # Modules to apply LoRA to
    - q_proj
    - k_proj
    - v_proj
    - o_proj
    - up_proj
    - down_proj
    - gate_proj

bnb_4bit:
  quant_type: nf4  # Quantization type
  compute_dtype: bfloat16  # Compute dtype
  use_double_quant: true  # Double quantization
```

### Hardware Assumptions

**Recommended Hardware:**
- **GPU**: H100 80GB (tested), or other CUDA-capable GPU with sufficient VRAM
- **CPU**: 26+ vCPUs for optimal data loading (configurable via `dataloader_num_workers`)
- **RAM**: 225GB+ for large datasets and multi-GPU setups
- **Storage**: Fast SSD for dataset storage and checkpointing

**H100 Optimizations:**
- Pre-tokenization for faster training
- Parallel data loading (`dataloader_num_workers: 48`)
- TF32 tensor cores
- Flash Attention 2 support
- Multi-GPU scaling (2×/4×/8× H100 nodes)

**Memory Requirements:**
- **4-bit QLoRA**: ~16-20GB VRAM for 8B models
- **8-bit QLoRA**: ~24-30GB VRAM for 8B models
- **Full fine-tuning**: ~80GB+ VRAM for 8B models

### Output: Checkpoints

**Checkpoint Location:** Specified via `misc.output_dir` in config (default: `out/`)

**Checkpoint Format:**
- LoRA adapter weights (small, ~100MB)
- Training state (optimizer, scheduler)
- Model configuration

**Checkpoint Frequency:** Controlled via `train.save_every` (default: every 500 steps)

**Checkpoint Structure:**
```
out/llama8b-rust-qlora-phase2/
├── checkpoint-500/
│   ├── adapter_config.json
│   ├── adapter_model.bin
│   └── training_state.bin
├── checkpoint-1000/
│   └── ...
└── checkpoint-12000/
    └── ...
```

**HuggingFace Upload:**
- Checkpoints can be uploaded to HuggingFace Hub
- Use `infer_export.py` to merge LoRA weights into base model
- Use `push_model_card.py` to create model cards

---

## 3. human-eval-Rust

### Purpose

Evaluates model performance on standardized Rust programming problems using the HumanEval benchmark format. Provides functional correctness testing and pass@k metrics.

### How It Evaluates Checkpoints

The evaluator can work with:

1. **HuggingFace model checkpoints** - `username/model-name` or `username/model-name/checkpoint-XXXX`
2. **Local model paths** - Path to local model directory
3. **PEFT/QLoRA checkpoints** - Fine-tuned checkpoints from sigilderg-finetuner

### What It Expects

**Input Format (JSONL):**

```json
{
  "task_id": "HumanEval/0",
  "completion": "pub fn has_close_elements(numbers: Vec<f64>, threshold: f64) -> bool {\n    // ... code ...\n}"
}
```

**Sample Generation:**

The evaluator expects samples in JSONL format with:
- `task_id` (string): Unique identifier for the problem (e.g., "HumanEval/0")
- `completion` (string): Model-generated Rust code completion

**Problem File:**

The evaluator uses the HumanEval Rust dataset (`data/HumanEval_rust.jsonl`) which contains 164 Rust programming problems. Each problem includes:
- `task_id`: Unique identifier
- `prompt`: Function signature and docstring
- `canonical_solution`: Reference implementation
- `test`: Rust test cases using `#[cfg(test)]`
- `entry_point`: Function name

### CLI Arguments

**Basic Evaluation:**

```bash
evaluate_functional_correctness rust_samples.jsonl
```

**Full Options:**

```bash
evaluate_functional_correctness \
    rust_samples.jsonl \
    --problem_file=data/HumanEval_rust.jsonl \
    --k=1,10,100 \
    --n_workers=24 \
    --timeout=10.0 \
    --sandbox-mode=firejail \
    --enforce-policy
```

**Key Arguments:**

| Argument | Default | Description |
|----------|---------|-------------|
| `sample_file` | (required) | Path to JSONL file with `task_id` and `completion` fields |
| `--k` | `"1,10,100"` | Comma-separated list of pass@k values to compute |
| `--n_workers` | `24` | Number of parallel workers for compilation/testing |
| `--timeout` | `10.0` | Per-sample timeout in seconds |
| `--problem_file` | (default dataset) | Override default HumanEval Rust dataset |
| `--sandbox-mode` | auto-detect | `"firejail"`, `"none"`, or `None` for auto |
| `--enforce-policy` | `true` | Enable pattern-based security filtering |

### Sandboxing

**Firejail Sandboxing (Recommended):**

- Uses Firejail for Linux process isolation
- Memory limit: **4GB** (optimized for H100)
- Network isolation: `--net=none`
- Private filesystem
- **Automatic completion extraction**: Removes extra `main()` functions and extracts only the target function body
- **Validation checks**: Verifies `rustc` availability before evaluation (fails fast if missing)
- Interactive installation flow if Firejail is missing

**No Sandboxing (`--sandbox-mode=none`):**

- ⚠️ **UNSAFE** - Only for local development with trusted code
- Runs code directly on host system
- No isolation or resource limits
- Requires explicit opt-in (`--allow-no-sandbox` in non-interactive mode)

### Policy Enforcement

**Pattern-Based Filtering (`--enforce-policy`, default):**

- Blocks dangerous code patterns before execution:
  - Filesystem operations (`std::fs`, `std::path`)
  - Network operations (`std::net`, `reqwest`, `tokio::net`)
  - Process operations (`std::process`, `std::env`)
  - Unsafe code (`unsafe` blocks)
  - External crate dependencies (prevents arbitrary code execution)

**Pure HumanEval Compatibility (`--no-enforce-policy`):**

- Disables pattern filtering
- Exact 1:1 comparability with original HumanEval benchmark format
- Use for research/publication mode

### Output

**Results File:** `<input>_results.jsonl`

Each result includes:
- `task_id`: Problem identifier
- `passed`: Boolean indicating if tests passed
- `result`: Execution result ("passed", "timed out", or "failed")
- `completion`: Generated code
- `tests`: Test execution details

**Metrics Output (stdout):**

```json
{
  "pass@1": 0.42,
  "pass@10": 0.68,
  "pass@100": 0.85
}
```

**H100 Optimizations:**

- **24 workers** (default): Saturates 26 vCPUs (reserving 2 for OS)
- **10.0s timeout** (default): Handles compilation latency on loaded systems
- **4GB memory limit**: Handles complex, macro-heavy Rust code compilation
- **2GB tmpfs**: Prevents "disk full" errors during build artifact generation

**Performance & Cost:**
- At 24 workers, 10s timeout, and 100 samples per problem (16,400 total samples), a full evaluation run on 1×H100 completes in approximately **3-4 hours**
- Estimated cost at Lambda Labs H100 pricing: **~$12-16 per full evaluation run**

---

## Complete Workflow Example

### Step 1: Generate Dataset

```bash
cd SigilDERG-Data_Production
python -m sigil_pipeline.main \
    --crate-list data/crate_list.txt \
    --prompt-mode instruct \
    --max-sft-lines 200 \
    --max-sft-chars 8000 \
    --output datasets/phase2_full.jsonl \
    --create-train-val-split \
    --val-ratio 0.1
```

**Output:** `datasets/phase2_full.jsonl` with `{"prompt": "...", "gen": "...", "split": "train"}` format

### Step 2: Fine-tune Model

```bash
cd SigilDERG-Finetuner
sigilderg-train configs/llama8b-phase2.yml
```

**Config (`configs/llama8b-phase2.yml`):**

```yaml
model_name: "meta-llama/Meta-Llama-3.1-8B-Instruct"

dataset:
  names:
    - local:../SigilDERG-Data_Production/datasets/phase2_full.jsonl
  use_cache: true
  min_length: 64
  max_length: 200_000

train:
  micro_batch_size: 16
  gradient_accumulation: 4
  num_steps: 12000
  lr: 1.0e-4
  save_every: 500

lora:
  r: 16
  alpha: 16
  dropout: 0.05

misc:
  output_dir: out/llama8b-rust-qlora-phase2
```

**Output:** Checkpoints in `out/llama8b-rust-qlora-phase2/checkpoint-XXXX/`

### Step 3: Evaluate Model

**Option A: Using eval_setup.sh (Recommended)**

```bash
# In human-eval-Rust directory on H100 server
bash eval_setup.sh
```

This script:
1. Sets up Python 3.12 environment
2. Installs all SigilDERG components
3. Generates samples from base and fine-tuned models
4. Evaluates both models
5. Produces comparison report and metrics JSON

**Option B: Manual Evaluation**

```bash
# Generate samples from checkpoint
python generate_samples.py \
    --checkpoint Superuser666-Sigil/Llama-3.1-8B-Instruct-Rust-QLora/checkpoint-9000 \
    --output rust_samples.jsonl

# Evaluate samples
evaluate_functional_correctness rust_samples.jsonl \
    --n_workers=24 \
    --timeout=10.0 \
    --sandbox-mode=firejail \
    --enforce-policy
```

**Output:** 
- `rust_samples.jsonl_results.jsonl` - Detailed results
- Metrics printed to stdout: `{"pass@1": 0.42, "pass@10": 0.68, "pass@100": 0.85}`

---

## Data Flow Summary

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Data Production                                          │
│                                                              │
│ Input:  Rust crates (crate_list.txt)                        │
│ Process: Static analysis → Quality filtering → Task gen     │
│ Output: datasets/phase2_full.jsonl                          │
│         Format: {"prompt": "...", "gen": "...", "split": ...}│
└───────────────────────┬─────────────────────────────────────┘
                        │
                        │ JSONL file
                        ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Finetuner                                                 │
│                                                              │
│ Input:  local:datasets/phase2_full.jsonl                    │
│ Process: Load JSONL → Apply chat template → QLoRA training  │
│ Config:  dataset.names, train.*, lora.*                     │
│ Output: out/llama8b-rust-qlora-phase2/checkpoint-XXXX/      │
│         Format: LoRA adapter weights                        │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        │ Checkpoint (HuggingFace)
                        ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. human-eval-Rust                                          │
│                                                              │
│ Input:  Checkpoint path + HumanEval problems                │
│ Process: Generate samples → Compile → Test → Metrics        │
│ Config:  --n_workers=24, --timeout=10.0, --sandbox-mode     │
│ Output: rust_samples.jsonl_results.jsonl + pass@k metrics   │
│         Format: {"task_id": "...", "passed": true, ...}     │
└─────────────────────────────────────────────────────────────┘
```

---

## Integration Points

### Format Compatibility

1. **Pipeline → Finetuner:**
   - Pipeline outputs `{"prompt": "...", "gen": "..."}`
   - Finetuner reads `local:path/to/file.jsonl` and combines into `text` field
   - Chat template applied at training time (not in dataset)

2. **Finetuner → Evaluation:**
   - Finetuner produces checkpoints (LoRA adapters)
   - Evaluation script loads checkpoint and generates completions
   - Completions formatted as `{"task_id": "...", "completion": "..."}`

3. **Task Type Oversampling:**
   - Pipeline includes `_task_type` field in samples
   - Finetuner can use `task_weights` to oversample/undersample task types
   - Enables balanced training across code generation, transformations, error fixing, explanations

### Version Compatibility

**Current Versions:**
- `sigil-pipeline>=2.0.0`
- `sigilderg-finetuner>=2.8.0`
- `human-eval-rust>=2.0.0`

**Installation:**

```bash
pip install sigil-pipeline[ecosystem]
```

This installs all three packages with compatible versions.

---

## Utilities (tools/)

The `tools/` directory contains utility scripts for dataset manipulation:

| Tool | Purpose |
|------|---------|
| `convert_jsonl_to_parquet.py` | Convert JSONL datasets to Parquet format |
| `convert_parquet_to_jsonl.py` | Convert Parquet datasets back to JSONL |
| `split_jsonl.py` | Split large JSONL files into smaller shards |
| `split_train_val.py` | Create train/validation splits |
| `analyze_failures.py` | Analyze pipeline rejection reasons |
| `rebalance_task_mix.py` | Adjust task type distribution in datasets |
| `verify_format_test.py` | Validate dataset format compliance |

---

## Hardware Requirements Summary

### Data Production

- **CPU**: Multi-core recommended for parallel crate analysis
- **RAM**: 16GB+ for large datasets
- **Storage**: Fast SSD for temporary crate downloads and dataset output
- **Network**: Internet connection for downloading crates from crates.io
- **Rust Toolchain**: Required for Clippy, Geiger, and other analysis tools

### Finetuner

- **GPU**: H100 80GB (recommended) or other CUDA-capable GPU
- **CPU**: 26+ vCPUs for optimal data loading
- **RAM**: 225GB+ for large datasets and multi-GPU setups
- **Storage**: Fast SSD for checkpoints and dataset cache

### human-eval-Rust

- **CPU**: 26+ vCPUs for parallel evaluation (24 workers + 2 reserved)
- **RAM**: 225GB+ (96GB max usage with 24 workers × 4GB)
- **Firejail**: Required for secure sandboxing (Linux)
- **Rust Toolchain**: Required for compilation testing

---

## Related Documentation

- **[Dataset Schema](docs/DATASET_SCHEMA.md)** - Complete schema reference for pipeline output
- **[Ecosystem Integration](docs/ECOSYSTEM_INTEGRATION.md)** - Detailed integration guide
- **[Clippy Category Filtering](docs/CLIPPY_CATEGORY_FILTERING.md)** - Quality filter documentation
- **[Architecture Decision Records](docs/adr/)** - Design decisions and rationale
- **[Runbooks](docs/runbooks/)** - Operational procedures

## Project Links

- **Pipeline**: https://github.com/Superuser666-Sigil/SigilDERG-Data_Production
- **Finetuner**: https://github.com/Superuser666-Sigil/SigilDERG-Finetuner
- **Evaluation**: https://github.com/Superuser666-Sigil/human-eval-Rust

---

**Copyright (c) 2025 Dave Tofflemire, SigilDERG Project**
