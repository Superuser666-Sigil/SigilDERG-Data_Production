"""
Exporter module for writing JSONL datasets and metrics.

Handles streaming JSONL output and merging multiple dataset files.
Supports Phase 1/Phase 2 merging with shuffle and weighting options.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.4.0
"""

import json
import logging
import random
from pathlib import Path
from typing import Any, Iterator

logger = logging.getLogger(__name__)

# Optional HuggingFace datasets library
try:
    from datasets import load_dataset  # type: ignore[import-untyped]

    HF_DATASETS_AVAILABLE = True
except ImportError:
    HF_DATASETS_AVAILABLE = False
    load_dataset = None  # type: ignore[assignment]


def write_jsonl(
    samples: Iterator[dict], output_path: str, remove_metadata: bool = True
) -> int:
    """
    Write dataset samples to a JSONL file in streaming fashion.

    Args:
        samples: Iterator of sample dicts with 'prompt' and 'gen' keys
        output_path: Path to output JSONL file
        remove_metadata: Whether to remove internal metadata keys (starting with _)

    Returns:
        Number of samples written
    """
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with open(output_file, "w", encoding="utf-8") as f:
        for sample in samples:
            try:
                # Validate sample structure
                if "prompt" not in sample or "gen" not in sample:
                    logger.warning(f"Skipping invalid sample: {sample.keys()}")
                    continue

                # Remove metadata keys if requested
                if remove_metadata:
                    clean_sample = {
                        k: v for k, v in sample.items() if not k.startswith("_")
                    }
                else:
                    clean_sample = sample

                # Write as JSON line
                json_line = json.dumps(clean_sample, ensure_ascii=False)
                f.write(json_line + "\n")
                count += 1

                if count % 1000 == 0:
                    logger.info(f"Written {count} samples...")

            except Exception as e:
                logger.error(f"Failed to write sample: {e}")
                continue

    logger.info(f"Wrote {count} samples to {output_path}")
    return count


def merge_phase2_shards(
    primary_path: str,
    extra_paths: list[str],
    output_path: str | None = None,
) -> tuple[int, dict[str, int]]:
    """
    Append additional Phase-2 style JSONL shards onto the primary dataset.

    Args:
        primary_path: Path to the freshly generated Phase-2 JSONL file.
        extra_paths: List of extra JSONL files to append (order preserved).
        output_path: Optional output path. Defaults to overwriting the primary file.

    Returns:
        Tuple of (total_new_samples, per_file_counts) where per_file_counts maps
        each appended shard path to the number of samples that were added.
    """
    base_path = Path(primary_path)
    if not base_path.exists():
        logger.error(f"Primary Phase-2 dataset not found: {primary_path}")
        return 0, {}

    valid_extra_paths: list[Path] = []
    for extra in extra_paths:
        extra_path = Path(extra)
        if not extra_path.exists():
            logger.warning(f"Extra Phase-2 shard missing, skipping: {extra}")
            continue
        valid_extra_paths.append(extra_path)

    if not valid_extra_paths:
        logger.info("No valid extra Phase-2 shards found; skipping append.")
        return 0, {}

    destination_path = Path(output_path) if output_path else base_path
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    # When overwriting the original file, write to a temporary sibling first.
    if destination_path == base_path:
        temp_path = destination_path.with_suffix(destination_path.suffix + ".tmp")
    else:
        temp_path = destination_path

    added_counts: dict[str, int] = {}

    def copy_file(
        src_path: Path, track: bool = False, infer_source: bool = False
    ) -> int:
        count = 0
        # Infer source identifier from filename if needed
        source_id = None
        if infer_source:
            if "upscaled" in src_path.name.lower():
                source_id = "phase1_upscaled"
            else:
                # Use filename stem as source identifier
                source_id = src_path.stem.replace("_", "-")

        with (
            open(src_path, "r", encoding="utf-8") as src_f,
            open(temp_path, "a", encoding="utf-8") as dest_f,
        ):
            for line in src_f:
                stripped = line.strip()
                if not stripped:
                    continue

                # If inferring source and source_id is set, add/update _source field
                if infer_source and source_id:
                    try:
                        sample = json.loads(stripped)
                        if "_source" not in sample:
                            sample["_source"] = source_id
                        stripped = json.dumps(sample, ensure_ascii=False)
                    except json.JSONDecodeError:
                        # If JSON parsing fails, write as-is
                        pass

                dest_f.write(stripped + "\n")
                count += 1

        if track:
            added_counts[str(src_path)] = count
        return count

    # Start fresh temp file to avoid stale contents.
    temp_path.unlink(missing_ok=True)

    logger.info("Appending extra Phase-2 shards...")
    copy_file(base_path, track=False)
    for extra_path in valid_extra_paths:
        copy_file(extra_path, track=True, infer_source=True)
        logger.info(
            f"  Added {added_counts[str(extra_path)]} samples from {extra_path}"
        )

    # Replace the original file if needed.
    if temp_path != destination_path:
        temp_path.replace(destination_path)

    total_added = sum(added_counts.values())
    logger.info(
        f"Appended {total_added} samples from {len(added_counts)} extra shard(s) "
        f"into {destination_path}"
    )
    return total_added, added_counts


def load_phase1_dataset(
    dataset_path: str, max_samples: int | None = None
) -> Iterator[dict[str, Any]]:
    """
    Load Phase 1 dataset from HuggingFace or local file.

    Args:
        dataset_path: HuggingFace dataset name or local file path
        max_samples: Maximum number of samples to load (None for all)

    Yields:
        Sample dictionaries with 'prompt' and 'gen' keys
    """
    # Check if it's a HuggingFace dataset name
    if (
        "/" in dataset_path
        and "\\" not in dataset_path
        and not Path(dataset_path).exists()
    ):
        # Likely a HuggingFace dataset
        if HF_DATASETS_AVAILABLE and load_dataset is not None:
            try:
                logger.info(f"Loading Phase 1 dataset from HuggingFace: {dataset_path}")
                dataset = load_dataset(dataset_path, split="train", streaming=True)

                count = 0
                for item in dataset:
                    # Dataset items are dictionaries
                    if not isinstance(item, dict):
                        continue

                    # Handle different dataset structures
                    if "prompt" in item and "gen" in item:
                        yield {"prompt": item["prompt"], "gen": item["gen"]}
                    elif "instruction" in item and "output" in item:
                        # Alternative field names
                        yield {"prompt": item["instruction"], "gen": item["output"]}
                    else:
                        logger.warning(
                            f"Unexpected Phase 1 dataset structure: {list(item.keys())}"
                        )
                        continue

                    count += 1
                    if max_samples and count >= max_samples:
                        break

            except Exception as e:
                logger.error(f"Failed to load HuggingFace dataset: {e}")
                return
        else:
            logger.error("HuggingFace datasets library not available")
            return

    # Treat as local file
    local_path = Path(dataset_path)
    if not local_path.exists():
        logger.error(f"Phase 1 dataset file not found: {dataset_path}")
        return

    logger.info(f"Loading Phase 1 dataset from local file: {dataset_path}")
    count = 0
    with open(local_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                sample = json.loads(line)
                if "prompt" in sample and "gen" in sample:
                    yield sample
                    count += 1
                    if max_samples and count >= max_samples:
                        break
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON in Phase 1 dataset: {e}")
                continue


def merge_jsonl_files(
    input_files: list[str],
    output_path: str,
    shuffle: bool = True,
    weights: list[float] | None = None,
) -> int:
    """
    Merge multiple JSONL files into a single file.

    Args:
        input_files: List of input JSONL file paths
        output_path: Path to output merged JSONL file
        shuffle: Whether to shuffle the merged dataset (default: True)
        weights: Optional list of weights for each file (for weighted sampling)

    Returns:
        Total number of samples merged
    """
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Collect all samples first (needed for shuffling/weighting)
    all_samples = []
    file_counts = []

    for input_file in input_files:
        input_path = Path(input_file)
        if not input_path.exists():
            logger.warning(f"Input file not found: {input_file}")
            continue

        logger.info(f"Loading {input_file}...")
        file_count = 0

        with open(input_path, "r", encoding="utf-8") as in_f:
            for line in in_f:
                line = line.strip()
                if not line:
                    continue

                try:
                    # Validate JSON
                    sample = json.loads(line)
                    if "prompt" not in sample or "gen" not in sample:
                        logger.warning(f"Invalid sample in {input_file}")
                        continue

                    all_samples.append(sample)
                    file_count += 1

                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON in {input_file}: {e}")
                    continue

        file_counts.append(file_count)
        logger.info(f"  Loaded {file_count} samples from {input_file}")

    # Apply weighting if specified
    if weights and len(weights) == len(input_files):
        weighted_samples = []
        for i, (samples_from_file, weight) in enumerate(zip(all_samples, weights)):
            # Repeat samples based on weight
            repeat_count = max(1, int(weight))
            for _ in range(repeat_count):
                weighted_samples.extend(samples_from_file)
        all_samples = weighted_samples
        logger.info(
            f"Applied weights: {weights}, total samples after weighting: {len(all_samples)}"
        )

    # Shuffle if requested
    if shuffle:
        logger.info("Shuffling merged dataset...")
        random.shuffle(all_samples)

    # Write merged dataset
    total_count = 0
    with open(output_file, "w", encoding="utf-8") as out_f:
        for sample in all_samples:
            json_line = json.dumps(sample, ensure_ascii=False)
            out_f.write(json_line + "\n")
            total_count += 1

    logger.info(f"Merged {total_count} total samples to {output_path}")
    return total_count


def merge_phase1_phase2(
    phase1_path: str,
    phase2_path: str,
    output_path: str,
    shuffle: bool = True,
    phase2_weight: float = 1.0,
    phase1_phase2_ratio: float | None = None,
    auto_upsample_phase2: bool = True,
) -> int:
    """
    Merge Phase 1 and Phase 2 datasets with optional weighting and ratio control.

    Args:
        phase1_path: Path to Phase 1 dataset (HuggingFace name or local file)
        phase2_path: Path to Phase 2 dataset JSONL file
        output_path: Path to output merged JSONL file
        shuffle: Whether to shuffle the merged dataset (default: True)
        phase2_weight: Weight for Phase 2 samples (1.0 = equal to Phase 1)
        phase1_phase2_ratio: Target ratio of Phase-1:Phase-2 (e.g., 10.0 = 10:1). None = use phase2_weight
        auto_upsample_phase2: Automatically up-sample Phase-2 if small relative to Phase-1

    Returns:
        Total number of samples merged
    """
    logger.info(f"Merging Phase 1 ({phase1_path}) and Phase 2 ({phase2_path})...")

    # Load Phase 1 samples
    phase1_samples = list(load_phase1_dataset(phase1_path))
    logger.info(f"Loaded {len(phase1_samples)} samples from Phase 1")

    # Load Phase 2 samples
    phase2_samples = []
    phase2_file = Path(phase2_path)
    if not phase2_file.exists():
        logger.error(f"Phase 2 file not found: {phase2_path}")
        return 0

    with open(phase2_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    sample = json.loads(line)
                    if "prompt" in sample and "gen" in sample:
                        phase2_samples.append(sample)
                except json.JSONDecodeError:
                    continue

    logger.info(f"Loaded {len(phase2_samples)} samples from Phase 2")

    # Add source metadata to Phase-1 samples for splitting
    phase1_samples_with_metadata = []
    # Derive source identifier from path (e.g., "phase1_upscaled" from filename)
    phase1_source = "phase1"
    phase1_path_obj = Path(phase1_path)
    if phase1_path_obj.exists() and "upscaled" in phase1_path_obj.name.lower():
        phase1_source = "phase1_upscaled"
    elif "/" in phase1_path or "\\" in phase1_path:
        # Try to extract meaningful identifier from HuggingFace dataset name
        if "upscaled" in phase1_path.lower():
            phase1_source = "phase1_upscaled"

    for sample in phase1_samples:
        sample_copy = sample.copy()
        sample_copy["_source_crate"] = "phase1"  # Mark as Phase-1 source
        # Preserve existing _source if present, otherwise set based on path
        if "_source" not in sample_copy:
            sample_copy["_source"] = phase1_source
        phase1_samples_with_metadata.append(sample_copy)
    phase1_samples = phase1_samples_with_metadata

    # Calculate target ratio and up-sampling
    if phase1_phase2_ratio is not None:
        # Use ratio-based approach
        target_phase2_count = int(len(phase1_samples) / phase1_phase2_ratio)
        current_phase2_count = len(phase2_samples)

        if target_phase2_count > current_phase2_count:
            # Need to up-sample Phase-2
            upsample_factor = target_phase2_count / current_phase2_count
            phase2_samples = phase2_samples * int(upsample_factor)
            # Add remaining samples randomly
            remaining = target_phase2_count - len(phase2_samples)
            if remaining > 0:
                phase2_samples.extend(random.choices(phase2_samples, k=remaining))
            logger.info(
                f"Target ratio {phase1_phase2_ratio}:1, up-sampled Phase-2 from "
                f"{current_phase2_count} to {len(phase2_samples)} samples"
            )
        elif auto_upsample_phase2 and current_phase2_count < len(phase1_samples) * 0.1:
            # Phase-2 is very small (<10% of Phase-1), auto up-sample to at least 10%
            min_phase2_count = int(len(phase1_samples) * 0.1)
            upsample_factor = min_phase2_count / current_phase2_count
            phase2_samples = phase2_samples * int(upsample_factor)
            remaining = min_phase2_count - len(phase2_samples)
            if remaining > 0:
                phase2_samples.extend(random.choices(phase2_samples, k=remaining))
            logger.info(
                f"Auto up-sampled Phase-2 from {current_phase2_count} to {len(phase2_samples)} "
                f"samples (ensures at least 10% of Phase-1 size)"
            )
        else:
            # Phase-2 is large enough, use as-is or down-sample if needed
            if len(phase2_samples) > target_phase2_count:
                phase2_samples = random.sample(phase2_samples, target_phase2_count)
                logger.info(f"Down-sampled Phase-2 to {len(phase2_samples)} samples")
    elif phase2_weight != 1.0:
        # Use weight-based approach (legacy)
        phase2_repeat = max(1, int(phase2_weight))
        original_count = len(phase2_samples)
        phase2_samples = phase2_samples * phase2_repeat
        logger.info(
            f"Applied Phase 2 weight {phase2_weight}, up-sampled from {original_count} to {len(phase2_samples)} samples"
        )

        # Check if auto up-sampling should apply additional up-sampling
        if auto_upsample_phase2 and len(phase2_samples) < len(phase1_samples) * 0.1:
            min_phase2_count = int(len(phase1_samples) * 0.1)
            if len(phase2_samples) < min_phase2_count:
                additional_factor = min_phase2_count / len(phase2_samples)
                phase2_samples = phase2_samples * int(additional_factor)
                remaining = min_phase2_count - len(phase2_samples)
                if remaining > 0:
                    phase2_samples.extend(random.choices(phase2_samples, k=remaining))
                logger.info(
                    f"Additional auto up-sampling: {len(phase2_samples)} samples "
                    f"(ensures at least 10% of Phase-1 size)"
                )
    elif auto_upsample_phase2 and len(phase2_samples) < len(phase1_samples) * 0.1:
        # Auto up-sample if Phase-2 is very small (when no ratio/weight specified)
        min_phase2_count = int(len(phase1_samples) * 0.1)
        upsample_factor = min_phase2_count / len(phase2_samples)
        original_count = len(phase2_samples)
        phase2_samples = phase2_samples * int(upsample_factor)
        remaining = min_phase2_count - len(phase2_samples)
        if remaining > 0:
            phase2_samples.extend(random.choices(phase2_samples, k=remaining))
        logger.info(
            f"Auto up-sampled Phase-2 from {original_count} to {len(phase2_samples)} "
            f"samples (ensures at least 10% of Phase-1 size)"
        )

    # Combine samples
    all_samples = phase1_samples + phase2_samples

    # Shuffle if requested
    if shuffle:
        logger.info("Shuffling merged dataset...")
        random.shuffle(all_samples)

    # Write merged dataset
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    total_count = 0
    with open(output_file, "w", encoding="utf-8") as out_f:
        for sample in all_samples:
            json_line = json.dumps(sample, ensure_ascii=False)
            out_f.write(json_line + "\n")
            total_count += 1

    logger.info(
        f"Merged dataset: {len(phase1_samples)} Phase 1 + {len(phase2_samples)} Phase 2 = "
        f"{total_count} total samples"
    )
    logger.info(f"Saved to: {output_path}")

    return total_count


def write_metrics(metrics: dict, output_path: str) -> None:
    """
    Write pipeline metrics to a JSON file.

    Args:
        metrics: Dictionary of metrics
        output_path: Path to output JSON file
    """
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)

    logger.info(f"Wrote metrics to {output_path}")
