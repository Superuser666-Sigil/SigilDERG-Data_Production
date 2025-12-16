# Dataset Schema Documentation

## Overview

The Sigil Pipeline generates JSONL (JSON Lines) datasets where each line is a JSON object representing a training sample. The pipeline now exclusively uses Phase-2 instruct mode for generating high-quality instruction-following datasets.

**Note:** Phase-1 compatible mode is deprecated and no longer supported. All references to Phase-1 in this document are for historical context only.

## Core Schema

### Required Fields

All samples must have these two fields:

- **`prompt`** (string): The instruction or prompt for the model
- **`gen`** (string): The expected code output/completion

### Split Field

When train/val splits are created, samples include an explicit `split` field:

- **`split`** (string, optional): Either `"train"` or `"val"` indicating the dataset split

**Why it's useful:**
- Enables filtering in HuggingFace: `dataset.filter(lambda x: x["split"] == "train")`
- Supports cross-validation workflows
- Simplifies merging multiple shards/versions while preserving split information
- Allows shipping single Parquet files per version instead of separate train/val files

### Metadata Fields (Optional)

Metadata fields start with `_` and are used for:
- Source tracking
- Train/val splitting
- Dataset merging
- Analysis/debugging

These fields are **removed** when `remove_metadata=True` (default for final datasets).

#### Standard Metadata Fields

- **`_source_crate`** (string, optional): Name of the crate the code came from
- **`_source_file`** (string, optional): Path to the source file within the crate
- **`_task_type`** (string, optional): Task type for Phase-2 samples (see Task Type Enum below)
- **`_source`** (string, optional): Source identifier for merged datasets (e.g., "phase1_upscaled")
- **`_prompt_seed`** (integer, optional): RNG seed used for prompt template randomization (for reproducibility)
- **`_async_runtime`** (string, optional): Detected async runtime from code imports (tokio, async-std, smol, embassy, futures). Used for metadata/analysis only; prompts use runtime-agnostic phrasing to avoid model bias.

#### Task Type Enum

The `_task_type` field is an enum with the following values:

- **`"code_generation"`** (~70%): Standard code generation tasks
- **`"transformations"`** (~15%): Code transformation tasks (sync→async, match→?, etc.)
- **`"error_fixing"`** (~10%): Fix compilation errors
- **`"explanations"`** (~5%): Explain code or generate documentation

**Normalization Rule:** Any fallback or ambiguous cases MUST be normalized to `"code_generation"`. This ensures downstream consumers won't encounter surprise values like `"transform"` vs `"transformations"`.

## Phase-1 Compatible Mode (DEPRECATED)

**⚠️ This mode is deprecated and no longer supported. The information below is for historical reference only.**

**Prompt Format:**
- Fixed prompt: `"Write a Rust code snippet. Output only the code."`
- All samples use this exact prompt (100% consistency)

**Example:**
```json
{
  "prompt": "Write a Rust code snippet. Output only the code.",
  "gen": "pub fn add(a: i32, b: i32) -> i32 {\n    a + b\n}",
  "_source_crate": "example",
  "_source_file": "src/lib.rs"
}
```

**Characteristics:**
- Library-sized modules (can be very large, up to ~1MB per sample)
- Consistent prompt format
- Code may include backticks (8.5% of samples)
- Average gen length: ~12,279 characters
- Median gen length: ~3,671 characters

## Phase-2 Instruct Mode

**Prompt Format:**
- Natural language instructions based on:
  - Doc comments
  - Function signatures (extracted via tree-sitter AST, handles nested generics)
  - Code patterns detected via AST analysis (async, serde, error handling, iterators)
  - Task type (code generation, transformations, error fixing, explanations)
  - Template randomization with seeded RNG for reproducible prompt diversity

**Example (Code Generation):**
```json
{
  "prompt": "Write a Rust function parse_config(path: &str) -> Result<Config, Error> that reads a configuration file.",
  "gen": "pub fn parse_config(path: &str) -> Result<Config, Error> {\n    // ... code ...\n}",
  "_source_crate": "example",
  "_source_file": "src/config.rs",
  "_task_type": "code_generation"
}
```

**Example (Transformation):**
```json
{
  "prompt": "Convert this synchronous function fetch_data into an async version using Tokio.",
  "gen": "pub async fn fetch_data() -> Result<String> {\n    // ... async code ...\n}",
  "_source_crate": "example",
  "_source_file": "src/api.rs",
  "_task_type": "transformations"
}
```

**Example (Error Fixing):**
```json
{
  "prompt": "This Rust code fails with error E0507: cannot move out of borrowed content. Fix it.",
  "gen": "// ... corrected code ...",
  "_source_crate": "example",
  "_source_file": "src/lib.rs",
  "_task_type": "error_fixing"
}
```

**Example (Explanation):**
```json
{
  "prompt": "Explain this Rust function in simple terms: [code]",
  "gen": "This function calculates the factorial of a number using recursion...",
  "_source_crate": "example",
  "_source_file": "src/math.rs",
  "_task_type": "explanations"
}
```

**Note:** All Phase-2 samples include `_task_type` to identify the task category. See Task Type Enum section above for details.

**Characteristics:**
- Concise snippets (max 200 lines, 8000 chars by default)
- Diverse, natural language prompts
- Task type diversity
- Semantic chunking (functions, impl blocks, modules)

## Merged Datasets (DEPRECATED)

**⚠️ Phase-1/Phase-2 merging is no longer supported. This section is for historical reference only.**

When merging Phase-1 and Phase-2 datasets, additional metadata was preserved:

**Phase-1 Samples:**
```json
{
  "prompt": "Write a Rust code snippet. Output only the code.",
  "gen": "...",
  "_source_crate": "phase1",
  "_source": "phase1_upscaled"
}
```

**Phase-2 Samples:**
```json
{
  "prompt": "Write a Rust function...",
  "gen": "...",
  "_source_crate": "example",
  "_source_file": "src/lib.rs",
  "_task_type": "code_generation"
}
```

## Train/Val Split Metadata

When `--create-train-val-split` is enabled:

- `_source_crate` is used to group samples by crate for splitting
- Entire crates are kept together (no mixing train/val)
- Ensures no data leakage between train and validation sets
- Each sample is tagged with explicit `split` field (`"train"` or `"val"`)
- The `split` field is **preserved** even when metadata is removed (it's not a `_`-prefixed field)

## Field Types

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `prompt` | string | ✅ Yes | Instruction/prompt text |
| `gen` | string | ✅ Yes | Code output/completion |
| `split` | string | ❌ No | Dataset split: `"train"` or `"val"`; may be omitted if split not created |
| `_source_crate` | string | ❌ No | Source crate name |
| `_source_file` | string | ❌ No | Source file path |
| `_task_type` | string | ❌ No | Task type enum (Phase-2 only, see Task Type Enum) |
| `_source` | string | ❌ No | Dataset source identifier |
| `_prompt_seed` | integer | ❌ No | RNG seed for prompt template randomization (for reproducibility) |

## Validation

The pipeline validates samples against:
- Required fields (`prompt`, `gen`)
- Field types (both must be strings)
- Size limits (for Phase-2: `max_sft_lines`, `max_sft_chars`)
- Format consistency (Phase-1 mode enforces exact prompt format)

## File Format

- **Format**: JSONL (JSON Lines)
- **Encoding**: UTF-8
- **Line Endings**: Platform-specific (LF on Unix, CRLF on Windows)
- **One sample per line**: Each line is a complete, valid JSON object

## Example Files

- **Phase-2**: `datasets/test_phase2_100crates.jsonl`
- **Phase-2 (production)**: `datasets/sigil_phase2_dataset.jsonl`

## Training Format

**Prompt and Gen Format:**
- `prompt` and `gen` are stored as **raw text** without chat wrappers or special tokens
- No instruction templates (e.g., `[INST]`, `[/INST]`) are baked into the dataset
- No BOS/EOS markers are included in `gen`
- The model's chat/instruction template is applied **at training time** (e.g., in Finetuner), not in the dataset

**Example:**
```json
{
  "prompt": "Write a Rust function that adds two numbers.",
  "gen": "pub fn add(a: i32, b: i32) -> i32 {\n    a + b\n}"
}
```

The training framework will wrap this appropriately:
```
[INST] Write a Rust function that adds two numbers. [/INST]
pub fn add(a: i32, b: i32) -> i32 {
    a + b
}
```

## Usage in Training

The dataset is designed for supervised fine-tuning (SFT) where:
- `prompt` is the input to the model
- `gen` is the expected output/completion
- Metadata fields can be used for filtering, analysis, or splitting

For training, metadata fields are typically removed:
```python
# Remove metadata before training (split is preserved automatically since it doesn't start with "_")
clean_sample = {
    k: v for k, v in sample.items() 
    if not k.startswith("_")
}
```

## Parquet Variants for HuggingFace

When converting to Parquet for HuggingFace upload, two variants are recommended:

### Training-Ready Parquet

**Columns:**
- `prompt` (string)
- `gen` (string)
- `split` (string, optional: `"train"` or `"val"`)

**No metadata:** All `_source_*`, `_task_type`, and `_source` fields are removed.

**Use case:** Direct training, no provenance tracking needed.

### Provenance/Analysis Parquet

**Columns:**
- `prompt` (string)
- `gen` (string)
- `split` (string, optional)
- `_source_crate` (string, optional)
- `_source_file` (string, optional)
- `_task_type` (string, optional)
- `_source` (string, optional)

**All metadata preserved:** Full provenance information for analysis, governance, and paper writing.

**Note:** Consider dropping the `_` prefix on metadata fields in the analysis variant for better ergonomics in Polars/Arrow (e.g., `task_type` instead of `_task_type`), but this is optional.

## Accompanying Output Files

In addition to the dataset JSONL, the pipeline generates these files for governance and reproducibility:

### metrics.json

Contains run statistics and configuration:

```json
{
  "total_samples": 12345,
  "crates_processed": 100,
  "crates_skipped": 25,
  "filter_breakdown": {
    "edition": 5,
    "clippy": 10,
    "license": 3,
    "unsafe": 7
  },
  "environment": { ... },
  "config": { ... }
}
```

### environment.json

Environment fingerprint for reproducibility audits:

```json
{
  "timestamp": "2025-01-15T10:30:00Z",
  "toolchain": {
    "rustc_version": "rustc 1.75.0 (82e1608df 2023-12-21)",
    "cargo_version": "cargo 1.75.0 (1d8b05cdd 2023-11-20)",
    "clippy_version": "clippy 0.1.75 (82e1608 2023-12-21)"
  },
  "platform": {
    "os": "Linux",
    "architecture": "x86_64",
    "python_version": "3.12.0"
  },
  "dependencies": {
    "tree_sitter": "0.20.4",
    "tree_sitter_rust": "0.20.4"
  }
}
```

### metrics.prom (optional)

Prometheus-format metrics for monitoring dashboards. Enabled via `enable_prometheus_output: true`.

## Schema Evolution

**Schema Version: 2.3**

Version history:
- **v1.0** (Phase-1): Fixed prompt format, library-sized modules **[DEPRECATED]**
- **v2.0** (Phase-2): Instruct-style prompts, task diversity, semantic chunking
- **v2.1**: Added `_task_type`, `_source` metadata fields, and explicit `split` field
- **v2.2**: Added `_async_runtime` metadata, environment fingerprinting, Prometheus metrics
- **v2.3** (Current): Phase-2 instruct is now the only supported mode; Phase-1 compatibility removed

**Note:** When shipping datasets to HuggingFace, include `schema_version: "2.3"` in the dataset card or README.md, referencing this documentation.

