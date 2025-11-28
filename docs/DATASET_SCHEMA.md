# Dataset Schema Documentation

## Overview

The Sigil Pipeline generates JSONL (JSON Lines) datasets where each line is a JSON object representing a training sample. The schema varies slightly between Phase-1 compatible mode and Phase-2 instruct mode.

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

#### Task Type Enum

The `_task_type` field is an enum with the following values:

- **`"code_generation"`** (~70%): Standard code generation tasks
- **`"transformations"`** (~15%): Code transformation tasks (sync→async, match→?, etc.)
- **`"error_fixing"`** (~10%): Fix compilation errors
- **`"explanations"`** (~5%): Explain code or generate documentation

**Normalization Rule:** Any fallback or ambiguous cases MUST be normalized to `"code_generation"`. This ensures downstream consumers won't encounter surprise values like `"transform"` vs `"transformations"`.

## Phase-1 Compatible Mode

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
  - Function signatures
  - Code patterns (async, serde, error handling, iterators)
  - Task type (code generation, transformations, error fixing, explanations)

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

## Merged Datasets

When merging Phase-1 and Phase-2 datasets, additional metadata is preserved:

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

- **Phase-1**: `datasets/phase1_full.jsonl`
- **Phase-2**: `datasets/test_phase2_100crates.jsonl`
- **Upscaled Phase-1**: `datasets/phase1_upscaled.jsonl`
- **Merged**: `datasets/merged_phase1_phase2.jsonl`

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

## Schema Evolution

**Schema Version: 2.1**

Version history:
- **v1.0** (Phase-1): Fixed prompt format, library-sized modules
- **v2.0** (Phase-2): Instruct-style prompts, task diversity, semantic chunking
- **v2.1** (Current): Added `_task_type`, `_source` metadata fields, and explicit `split` field

**Note:** When shipping datasets to HuggingFace, include `schema_version: "2.1"` in the dataset card or README.md, referencing this documentation.

