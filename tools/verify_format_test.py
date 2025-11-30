"""
Quick script to verify generated samples match Phase 1 format.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.4.0
"""

import argparse
import json
import sys
from pathlib import Path

from sigil_pipeline.format_validator import FormatValidator


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify generated samples match Phase 1 format"
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("output/sigil_phase2_dataset.jsonl"),
        help="Path to dataset JSONL file (default: output/sigil_phase2_dataset.jsonl)",
    )
    parser.add_argument(
        "--spec",
        type=Path,
        default=Path("docs/phase1_format_spec.json"),
        help="Path to format spec JSON file (default: docs/phase1_format_spec.json)",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="Maximum number of samples to validate (default: all)",
    )
    parser.add_argument(
        "--show-invalid",
        type=int,
        default=5,
        help="Number of invalid samples to show (default: 5)",
    )
    args = parser.parse_args()

    dataset_path = args.dataset
    spec_path = args.spec

    if not dataset_path.exists():
        print(f"Error: Dataset not found: {dataset_path}")
        return 1

    # Load validator
    validator = FormatValidator(spec_path)
    print(f"Format spec loaded: {validator.phase1_spec is not None}\n")

    # Check samples
    samples = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    samples.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            if args.max_samples and len(samples) >= args.max_samples:
                break

    print(f"Total samples: {len(samples)}\n")

    if not samples:
        print("No samples to validate!")
        return 1

    # Validate each sample
    valid_count = 0
    invalid_count = 0
    invalid_samples = []

    for i, sample in enumerate(samples):
        is_valid, errors = validator.validate_sample(sample)
        if is_valid:
            valid_count += 1
        else:
            invalid_count += 1
            invalid_samples.append((i, sample, errors))

    print("Validation Results:")
    print(f"  Valid: {valid_count}")
    print(f"  Invalid: {invalid_count}")
    print(f"  Success rate: {valid_count/len(samples)*100:.1f}%\n")

    # Check first few samples
    print("First 5 samples:")
    for i, sample in enumerate(samples[:5]):
        prompt = sample.get("prompt", "")
        gen = sample.get("gen", "")
        print(f"\nSample {i+1}:")
        print(f'  Prompt: "{prompt[:100]}{"..." if len(prompt) > 100 else ""}"')
        print(f"  Prompt length: {len(prompt)} chars")
        print(
            f"  Matches Phase 1 format: {prompt == 'Write a Rust code snippet. Output only the code.'}"
        )
        print(f"  Gen length: {len(gen)} chars")
        print(f"  Has backticks: {'```' in gen}")
        is_valid, errors = validator.validate_sample(sample)
        print(f"  Valid: {is_valid}")
        if errors:
            print(f"  Errors: {errors}")

    # Show invalid samples if any
    if invalid_samples and args.show_invalid > 0:
        print(
            f"\nInvalid samples ({len(invalid_samples)} total, showing {min(args.show_invalid, len(invalid_samples))}):"
        )
        for idx, sample, errors in invalid_samples[: args.show_invalid]:
            print(f"\n  Sample {idx+1}:")
            prompt = sample.get("prompt", "")[:100]
            print(
                f'    Prompt: "{prompt}{"..." if len(sample.get("prompt", "")) > 100 else ""}"'
            )
            print(f"    Errors: {errors}")

    return 0 if invalid_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
