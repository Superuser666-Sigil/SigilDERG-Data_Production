# SigilDERG Ecosystem Integration Guide

## Overview

The SigilDERG ecosystem consists of three integrated PyPI packages that work together to provide a complete workflow for Rust code model training:

1. **sigil-pipeline** - Dataset generation from Rust crates
2. **sigilderg-finetuner** - QLoRA fine-tuning for Rust code models
3. **human-eval-rust** - Evaluation harness for Rust code generation

This guide explains how to use these packages together for a complete workflow: **generate → fine-tune → evaluate**.

## Installation

### Install All Packages

Install the complete ecosystem with optional dependencies:

```bash
pip install sigil-pipeline[ecosystem]
```

This installs:
- `sigil-pipeline>=2.3.0`
- `sigilderg-finetuner>=3.0.0`
- `human-eval-rust>=2.3.0`

### Install Individual Packages

You can also install packages individually:

```bash
# Dataset generation
pip install sigil-pipeline

# Fine-tuning
pip install sigilderg-finetuner

# Evaluation
pip install human-eval-rust
```

### Install with Specific Integrations

Install only the integrations you need:

```bash
# Pipeline + Finetuner
pip install sigil-pipeline[finetuning]

# Pipeline + Evaluation
pip install sigil-pipeline[evaluation]

# Finetuner + Evaluation
pip install sigilderg-finetuner[evaluation]
```

## Complete Workflow

### Step 1: Generate Dataset

Generate a training dataset from Rust crates:

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

This creates:
- `datasets/phase2_full.jsonl` - Training dataset with `{"prompt": "...", "gen": "..."}` format
- Train/val split is created automatically (samples include `"split": "train"` or `"split": "val"`)

### Step 2: Fine-tune Model

Fine-tune a model using the generated dataset. The finetuner can now load JSONL files directly:

**Option A: Use JSONL directly (recommended)**

Create a config file `configs/llama8b-phase2.yml`:

```yaml
model_name: "meta-llama/Meta-Llama-3.1-8B-Instruct"
max_seq_len: 4096
pack: true

dataset:
  names:
    - local:datasets/phase2_full.jsonl  # Load pipeline JSONL directly
  use_cache: true
  min_length: 64
  max_length: 200_000

train:
  micro_batch_size: 8
  gradient_accumulation: 6
  num_steps: 12000
  lr: 1.0e-4
  # ... other training config
```

Then run:

```bash
sigilderg-train configs/llama8b-phase2.yml
```

**Option B: Convert to Parquet first**

If you prefer to use Parquet format (e.g., for HuggingFace Hub upload):

```bash
# Convert to Parquet (training-ready variant)
python tools/convert_jsonl_to_parquet.py \
    datasets/phase2_full.jsonl \
    datasets/phase2_training.parquet \
    --variant training

# Use in config
dataset:
  names:
    - parquet:datasets/phase2_training.parquet
```

**Option C: Mix HuggingFace and local datasets**

You can mix HuggingFace datasets with local JSONL/Parquet files:

```yaml
dataset:
  names:
    - ammarnasr/the-stack-rust-clean  # HuggingFace dataset
    - local:datasets/phase2_full.jsonl  # Pipeline output
  interleave_mode: "weighted"
  dataset_weights:
    "ammarnasr/the-stack-rust-clean": 0.3
    "local:datasets/phase2_full.jsonl": 0.7
```

### Step 3: Evaluate Model

Evaluate the fine-tuned model using the evaluation harness:

**Option A: Use finetuner's built-in evaluation**

```bash
sigilderg-eval samples.jsonl --use-human-eval
```

This runs both the standard Rust compilation/clippy evaluation and human-eval-rust functional correctness tests.

**Option B: Use human-eval-rust directly**

First, convert pipeline samples to evaluation format:

```python
from sigil_pipeline.converters import prompt_gen_to_eval_format

prompt_gen_to_eval_format(
    jsonl_path="samples.jsonl",
    output_path="samples_eval.jsonl",
    task_id_prefix="rust_task"
)
```

Then run evaluation:

```bash
evaluate_functional_correctness samples_eval.jsonl
```

## Format Compatibility

### Pipeline Output Format

Pipeline generates JSONL with this format:

```json
{
  "prompt": "Write a Rust function that...",
  "gen": "pub fn example() -> i32 { ... }",
  "split": "train",
  "_source_crate": "example-crate",
  "_source_file": "src/lib.rs",
  "_task_type": "code_generation",
  "_source": "phase2"
}
```

### Finetuner Input Format

The finetuner expects datasets with a `"text"` field for training. When loading `local:` JSONL files, the finetuner automatically:

1. Reads `prompt` and `gen` fields
2. Combines them into `text` field: `f"{prompt}\n\n{gen}"`
3. Optionally applies chat template formatting

### Evaluation Format

human-eval-rust expects:

```json
{
  "task_id": "task_123",
  "completion": "pub fn example() -> i32 { ... }"
}
```

Use `prompt_gen_to_eval_format()` to convert pipeline samples.

## Unified CLI Orchestrator

Use the unified CLI to run the complete workflow:

```bash
sigil-ecosystem \
    --crate-list data/crate_list.txt \
    --dataset-path datasets/phase2_full.jsonl \
    --config-path configs/llama8b-phase2.yml \
    --output-dir out/llama8b-rust-qlora
```

Options:
- `--no-generate-dataset` - Skip dataset generation
- `--no-fine-tune` - Skip fine-tuning
- `--no-evaluate` - Skip evaluation

## Configuration Examples

### Basic Phase-2 Training

```yaml
model_name: "meta-llama/Meta-Llama-3.1-8B-Instruct"
max_seq_len: 4096

dataset:
  names:
    - local:datasets/phase2_full.jsonl
  use_cache: true

train:
  micro_batch_size: 8
  gradient_accumulation: 6
  num_steps: 12000
  lr: 1.0e-4
```

### Mixed Dataset Training

```yaml
dataset:
  names:
    - ammarnasr/the-stack-rust-clean
    - local:datasets/phase2_full.jsonl
  interleave_mode: "weighted"
  dataset_weights:
    "ammarnasr/the-stack-rust-clean": 0.2
    "local:datasets/phase2_full.jsonl": 0.8
```

### Parquet-based Training

```yaml
dataset:
  names:
    - parquet:datasets/phase2_training.parquet
  use_cache: true
```

## Troubleshooting

### "Local JSONL file not found"

Ensure the path in your config is correct. Use absolute paths or paths relative to where you run the training command.

### "human-eval-rust not available"

Install the evaluation package:

```bash
pip install human-eval-rust
```

Or install the full ecosystem:

```bash
pip install sigil-pipeline[ecosystem]
```

### Format Conversion Issues

Use the existing conversion tools:

- `tools/convert_jsonl_to_parquet.py` - Convert JSONL to Parquet
- `tools/convert_parquet_to_jsonl.py` - Convert Parquet back to JSONL
- `sigil_pipeline.converters.prompt_gen_to_eval_format()` - Convert to evaluation format

### Dataset Loading Errors

Check that:
1. JSONL files have `prompt` and `gen` fields
2. File paths in config are correct (use `local:` prefix for JSONL, `parquet:` for Parquet)
3. Files are readable and not corrupted

## Related Documentation

- [Dataset Schema Documentation](DATASET_SCHEMA.md) - Complete schema reference
- [SigilDERG-Finetuner README](../SigilDERG-Finetuner/README.md) - Finetuner documentation
- [human-eval-Rust README](../human-eval-Rust/README.md) - Evaluation documentation

## Project Links

- **Pipeline**: https://github.com/Superuser666-Sigil/SigilDERG-Data_Production
- **Finetuner**: https://github.com/Superuser666-Sigil/SigilDERG-Finetuner
- **Evaluation**: https://github.com/Superuser666-Sigil/human-eval-Rust

