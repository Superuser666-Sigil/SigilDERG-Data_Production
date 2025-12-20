"""
Exporter module for writing JSONL datasets and metrics.

Handles streaming JSONL output and merging multiple dataset files.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.5.0
"""

import json
import logging
import random
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)


def write_jsonl(
    samples: Iterator[dict], output_path: str, remove_metadata: bool = True
) -> int:
    """
    Write dataset samples to a JSONL file in streaming fashion.

    Args:
        samples: Iterator of sample dicts with 'prompt' and 'gen' keys
        output_path: Path to output JSONL file
                    if ("prompt" in sample and "gen" in sample) or (
                        "input_data" in sample and "output_data" in sample
                    ):
                        # Filter out comment_generation samples
                        tc = sample.get("task_category") if isinstance(sample, dict) else None
                        is_comment = False
                        if isinstance(tc, str) and tc.strip().lower() == "comment_generation":
                            is_comment = True
                        else:
                            for k in ("input_data", "output_data"):
                                nested = sample.get(k)
                                if isinstance(nested, dict):
                                    if nested.get("task_category") and str(nested.get("task_category")).strip().lower() == "comment_generation":
                                        is_comment = True
                                        break
                                    if "commented_code" in nested:
                                        is_comment = True
                                        break

                        if is_comment:
                            continue

                        all_samples.append(sample)
    """
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with open(output_file, "w", encoding="utf-8") as f:
        for sample in samples:
            try:
                # Support both legacy samples (prompt/gen) and new structured schema.
                # Preferred structured schema:
                # {
                #   "crate_name": str | null,
                #   "input_data": dict,
                #   "output_data": dict,
                #   "task_category": str,
                #   "test": str
                # }

                if "prompt" in sample and "gen" in sample:
                    # Legacy sample: convert to structured schema for dataset quality
                    structured = {
                        "crate_name": sample.get("crate_name"),
                        "input_data": {"prompt": sample["prompt"]},
                        "output_data": {"assistant": sample["gen"]},
                        "task_category": sample.get("task_category", "unknown"),
                        "test": sample.get("test", ""),
                    }
                elif "input_data" in sample and "output_data" in sample:
                    structured = sample
                else:
                    logger.warning(
                        f"Skipping invalid sample (missing expected keys): {list(sample.keys())}"
                    )
                    continue

                # Defensive filter: drop any comment_generation samples (case-insensitive)
                # Also drop samples whose output_data contains legacy "commented_code" key
                def _is_comment_sample(obj: dict) -> bool:
                    try:
                        tc = obj.get("task_category") if isinstance(obj, dict) else None
                        if (
                            isinstance(tc, str)
                            and tc.strip().lower() == "comment_generation"
                        ):
                            return True
                        # Inspect nested input/output for legacy labels
                        for key in ("input_data", "output_data"):
                            nested = obj.get(key)
                            if isinstance(nested, dict):
                                if (
                                    nested.get("task_category")
                                    and str(nested.get("task_category")).strip().lower()
                                    == "comment_generation"
                                ):
                                    return True
                                if "commented_code" in nested:
                                    return True
                    except Exception:
                        return False
                    return False

                if _is_comment_sample(structured):
                    logger.info(
                        "Skipping sample with task_category=comment_generation or legacy commented_code"
                    )
                    continue

                # Remove metadata keys if requested (preserve top-level structured fields)
                if remove_metadata and isinstance(structured, dict):
                    structured = {
                        k: v
                        for k, v in structured.items()
                        if not str(k).startswith("_")
                    }

                # Write as JSON line
                json_line = json.dumps(structured, ensure_ascii=False)
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

                # Try to parse JSON so we can filter comment_generation samples
                try:
                    sample = json.loads(stripped)
                except json.JSONDecodeError:
                    # If JSON parsing fails, fall back to writing raw line
                    dest_f.write(stripped + "\n")
                    count += 1
                    continue

                # Defensive filter similar to write_jsonl()
                def _is_comment_sample_obj(obj: dict) -> bool:
                    tc = obj.get("task_category") if isinstance(obj, dict) else None
                    if (
                        isinstance(tc, str)
                        and tc.strip().lower() == "comment_generation"
                    ):
                        return True
                    for key in ("input_data", "output_data"):
                        nested = obj.get(key)
                        if isinstance(nested, dict):
                            if (
                                nested.get("task_category")
                                and str(nested.get("task_category")).strip().lower()
                                == "comment_generation"
                            ):
                                return True
                            if "commented_code" in nested:
                                return True
                    return False

                if _is_comment_sample_obj(sample):
                    # Skip writing this sample
                    continue

                # If inferring source and source_id is set, add/update _source field
                if infer_source and source_id:
                    if "_source" not in sample:
                        sample["_source"] = source_id

                dest_f.write(json.dumps(sample, ensure_ascii=False) + "\n")
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
                    # Validate JSON; accept legacy (prompt/gen) or structured schema
                    sample = json.loads(line)
                    if ("prompt" in sample and "gen" in sample) or (
                        "input_data" in sample and "output_data" in sample
                    ):
                        all_samples.append(sample)
                        file_count += 1
                    else:
                        logger.warning(
                            f"Invalid sample in {input_file}: missing expected keys"
                        )
                        continue

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
