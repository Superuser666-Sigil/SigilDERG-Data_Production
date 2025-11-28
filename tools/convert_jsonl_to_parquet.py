"""
Convert JSONL dataset to Parquet format for HuggingFace upload.

Supports both training-ready (metadata stripped) and provenance/analysis
(metadata preserved) variants as documented in DATASET_SCHEMA.md.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.0.0
"""

import json
import sys
from pathlib import Path
from typing import Any, Iterator

try:
    from datasets import Dataset
except ImportError:
    print(
        "Error: Required libraries not installed. Install with: "
        "pip install pyarrow datasets"
    )
    sys.exit(1)


def _sample_generator(
    jsonl_files: list[Path],
    variant: str,
    max_samples: int | None = None,
) -> Iterator[dict[str, Any]]:
    """
    Generator that yields samples from JSONL files one at a time.

    This avoids loading all samples into memory at once, enabling
    streaming processing of large datasets.
    """
    count = 0

    for jsonl_file_path in jsonl_files:
        with open(jsonl_file_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    sample = json.loads(line)
                except json.JSONDecodeError as e:
                    print(
                        f"Warning: Invalid JSON on line {line_num} of {jsonl_file_path}: {e}"
                    )
                    continue

                # Validate required fields
                if "prompt" not in sample or "gen" not in sample:
                    print(
                        f"Warning: Skipping sample on line {line_num} - missing prompt/gen"
                    )
                    continue

                if variant == "training":
                    # Training-ready: only prompt, gen, and split
                    clean_sample: dict[str, Any] = {
                        "prompt": str(sample["prompt"]),
                        "gen": str(sample["gen"]),
                    }
                    if "split" in sample:
                        clean_sample["split"] = str(sample["split"])
                    yield clean_sample
                else:
                    # Provenance: preserve all fields
                    yield sample

                count += 1
                if count % 10000 == 0:
                    print(f"Processed {count} samples...")

                if max_samples is not None and count >= max_samples:
                    return


def convert_jsonl_to_parquet(
    jsonl_path: str,
    output_path: str,
    variant: str = "training",
    max_samples: int | None = None,
) -> None:
    """
    Convert JSONL dataset to Parquet format using streaming processing.
    """
    jsonl_file = Path(jsonl_path)
    if not jsonl_file.exists():
        print(f"Error: File not found: {jsonl_path}")
        sys.exit(1)

    if variant not in ("training", "provenance"):
        print(f"Error: variant must be 'training' or 'provenance', got '{variant}'")
        sys.exit(1)

    print(f"Reading JSONL from {jsonl_path}...")
    print(f"Output variant: {variant}")

    # Handle single file or directory
    if jsonl_file.is_file():
        jsonl_files: list[Path] = [jsonl_file]
    else:
        jsonl_files = sorted(jsonl_file.glob("*.jsonl"))
        if not jsonl_files:
            print(f"Error: No JSONL files found in {jsonl_path}")
            sys.exit(1)
        print(f"Found {len(jsonl_files)} JSONL files")

    # Build an IterableDataset from the generator
    def generator_fn():
        return _sample_generator(jsonl_files, variant, max_samples)

    print("Creating Parquet file (streaming mode)...")
    try:
        dataset = Dataset.from_generator(generator_fn)

        # Get column names (schema) for printing
        # Note: IterableDataset.column_names is available at runtime but type checker doesn't recognize it
        try:
            column_names = list(dataset.column_names)  # type: ignore[attr-defined]
        except AttributeError:
            sample_gen = _sample_generator(jsonl_files, variant, 1)
            first_sample = next(sample_gen, None)
            column_names = list(first_sample.keys()) if first_sample else []

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # IterableDataset.to_parquet() works at runtime despite type checker warnings
        dataset.to_parquet(output_path)  # type: ignore[attr-defined]
        print(f"Successfully wrote dataset to {output_path}")

        # Print summary
        if variant == "training":
            print("\nTraining-ready Parquet created with columns:")
            print("  - prompt (string)")
            print("  - gen (string)")
            if "split" in column_names:
                print("  - split (string)")
        else:
            print("\nProvenance Parquet created with columns:")
            for col in column_names:
                print(f"  - {col}")

    except Exception as e:
        print(f"Error creating Parquet file: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert JSONL dataset to Parquet format for HuggingFace"
    )
    parser.add_argument(
        "jsonl_path",
        help="Input JSONL file or directory containing JSONL files",
    )
    parser.add_argument(
        "output_path",
        help=(
            "Output Parquet file path "
            "(e.g., datasets/train_training.parquet or datasets/train_provenance.parquet)"
        ),
    )
    parser.add_argument(
        "--variant",
        choices=["training", "provenance"],
        default="training",
        help="Output variant: 'training' (metadata stripped) or 'provenance' (all fields)",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        help="Maximum number of samples to convert",
    )

    args = parser.parse_args()
    convert_jsonl_to_parquet(
        args.jsonl_path, args.output_path, args.variant, args.max_samples
    )
