"""
Convert Phase 1 parquet dataset to JSONL format for pipeline processing.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.6.0
"""

import json
import sys
from pathlib import Path

try:
    from datasets import Dataset, load_dataset
except ImportError:
    print("Error: datasets library not installed. Install with: pip install datasets")
    sys.exit(1)


def convert_parquet_to_jsonl(
    parquet_dir: str, output_path: str, max_samples: int | None = None
) -> None:
    """
    Convert parquet files to JSONL format.

    Args:
        parquet_dir: Directory containing parquet files
        output_path: Output JSONL file path
        max_samples: Maximum number of samples to convert (None for all)
    """
    parquet_path = Path(parquet_dir)
    if not parquet_path.exists():
        print(f"Error: Directory not found: {parquet_dir}")
        sys.exit(1)

    # Find all parquet files
    parquet_files = list(parquet_path.glob("*.parquet"))
    if not parquet_files:
        print(f"Error: No parquet files found in {parquet_dir}")
        sys.exit(1)

    print(f"Found {len(parquet_files)} parquet files")

    # Load dataset using HuggingFace datasets library
    data_files = [str(f) for f in parquet_files]
    print(f"Loading dataset from {len(data_files)} files...")

    try:
        dataset = load_dataset("parquet", data_files=data_files, split="train")
        if not isinstance(dataset, Dataset):
            print("Error: Expected Dataset type, got iterable dataset")
            sys.exit(1)
        print(f"Loaded {len(dataset)} samples")
        column_names = dataset.column_names
        if column_names is None:
            print("Error: Could not determine column names")
            sys.exit(1)
        print(f"Columns: {column_names}")
    except Exception as e:
        print(f"Error loading dataset: {e}")
        sys.exit(1)

    # Determine field mapping
    # Check what fields are available
    if len(dataset) > 0:
        sample = dataset[0]
        if isinstance(sample, dict):
            print(f"Sample keys: {list(sample.keys())}")
        else:
            print(f"Sample type: {type(sample)}")

    # Map fields to prompt/gen
    prompt_field: str | None = None
    gen_field: str | None = None

    column_names = dataset.column_names
    if column_names is None:
        print("Error: Could not determine column names")
        sys.exit(1)

    # Try common field names
    if "prompt" in column_names:
        prompt_field = "prompt"
    elif "instruction" in column_names:
        prompt_field = "instruction"
    elif "text" in column_names:
        prompt_field = "text"

    if "gen" in column_names:
        gen_field = "gen"
    elif "output" in column_names:
        gen_field = "output"
    elif "content" in column_names:
        gen_field = "content"
    elif "code" in column_names:
        gen_field = "code"

    # If we only have content/code, generate simple prompts
    if not prompt_field and gen_field:
        print("Note: Only code content found, will generate simple prompts")
        prompt_field = None  # Will generate prompts

    if not gen_field:
        column_names = dataset.column_names
        available = column_names if column_names else "unknown"
        print(f"Error: Could not determine code field. Available fields: {available}")
        print("Expected fields: 'gen'/'output'/'content'/'code'")
        sys.exit(1)

    if prompt_field:
        print(f"Using fields: prompt='{prompt_field}', gen='{gen_field}'")
    else:
        print(f"Using field: gen='{gen_field}' (will generate prompts)")

    # Convert to JSONL
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with open(output_file, "w", encoding="utf-8") as f:
        for item in dataset:
            # Type guard: ensure item is a dict-like object
            if not isinstance(item, dict):
                continue

            gen = item.get(gen_field, "") if gen_field else ""
            if not gen:
                continue

            # Get prompt if available, otherwise generate simple one
            if prompt_field:
                prompt = item.get(prompt_field, "")
            else:
                # Generate simple prompt for raw code
                prompt = "Write a Rust code snippet. Output only the code."

            sample = {"prompt": str(prompt), "gen": str(gen)}
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")
            count += 1

            if max_samples and count >= max_samples:
                break

            if count % 10000 == 0:
                print(f"Converted {count} samples...")

    print(f"Converted {count} samples to {output_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert parquet dataset to JSONL format"
    )
    parser.add_argument(
        "parquet_dir", help="Directory containing parquet files (e.g., datasets/data)"
    )
    parser.add_argument(
        "output_path", help="Output JSONL file path (e.g., datasets/phase1.jsonl)"
    )
    parser.add_argument(
        "--max-samples", type=int, help="Maximum number of samples to convert"
    )

    args = parser.parse_args()
    convert_parquet_to_jsonl(args.parquet_dir, args.output_path, args.max_samples)
