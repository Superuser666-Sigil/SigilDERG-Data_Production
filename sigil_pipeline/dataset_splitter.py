"""
Dataset splitting utilities for train/val splits by source.

Splits datasets by source (crate/file) to keep whole crates/files together,
ensuring validation set tests true generalization.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.6.0
"""

import json
import logging
import random
from collections import defaultdict
from pathlib import Path

# Tuple is kept for clarity in return type annotations

logger = logging.getLogger(__name__)


def split_by_source(
    input_path: str,
    train_path: str,
    val_path: str,
    val_ratio: float = 0.1,
    source_key: str = "_source_crate",
) -> tuple[int, int]:
    """
    Split dataset by source (crate/file), keeping whole sources together.

    Args:
        input_path: Path to input JSONL file
        train_path: Path to output training JSONL file
        val_path: Path to output validation JSONL file
        val_ratio: Ratio of sources to put in validation set (default: 0.1 = 10%)
        source_key: Key in sample dict to use for source grouping (default: "_source_crate")

    Returns:
        Tuple of (train_count, val_count)
    """
    input_file = Path(input_path)
    if not input_file.exists():
        logger.error(f"Input file not found: {input_path}")
        return 0, 0

    # Group samples by source
    source_groups: dict[str, list[dict]] = defaultdict(list)
    samples_without_source = []

    logger.info(f"Loading samples from {input_path}...")
    with open(input_file, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                sample = json.loads(line)
                source = sample.get(source_key)

                if source:
                    source_groups[source].append(sample)
                else:
                    # Samples without source go to a special group
                    samples_without_source.append(sample)
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON on line {line_num}: {e}")
                continue

    logger.info(
        f"Grouped {len(source_groups)} sources, "
        f"{len(samples_without_source)} samples without source"
    )

    # Split sources (not individual samples)
    source_list = list(source_groups.keys())
    random.shuffle(source_list)  # Shuffle for random split

    # Ensure at least 1 source in train set (unless only 1 source total)
    if len(source_list) == 1:
        # With only 1 source, put it in train (can't validate on unseen source)
        logger.warning(
            "Only 1 source found. Cannot create proper train/val split. "
            "Putting all samples in train set."
        )
        val_source_count = 0
    else:
        val_source_count = max(1, int(len(source_list) * val_ratio))
        # Ensure at least 1 source remains in train
        if val_source_count >= len(source_list):
            val_source_count = len(source_list) - 1

    val_sources = set(source_list[:val_source_count])
    train_sources = set(source_list[val_source_count:])

    logger.info(
        f"Split: {len(train_sources)} sources -> train, {len(val_sources)} sources -> val"
    )

    # Write train set
    train_file = Path(train_path)
    train_file.parent.mkdir(parents=True, exist_ok=True)

    train_count = 0
    with open(train_file, "w", encoding="utf-8") as f:
        for source in train_sources:
            for sample in source_groups[source]:
                # Remove metadata keys before writing, but preserve split field
                clean_sample = _remove_metadata(sample)
                clean_sample["split"] = "train"
                json_line = json.dumps(clean_sample, ensure_ascii=False)
                f.write(json_line + "\n")
                train_count += 1

        # Add samples without source to train set
        for sample in samples_without_source:
            clean_sample = _remove_metadata(sample)
            clean_sample["split"] = "train"
            json_line = json.dumps(clean_sample, ensure_ascii=False)
            f.write(json_line + "\n")
            train_count += 1

    # Write val set
    val_file = Path(val_path)
    val_file.parent.mkdir(parents=True, exist_ok=True)

    val_count = 0
    with open(val_file, "w", encoding="utf-8") as f:
        for source in val_sources:
            for sample in source_groups[source]:
                # Remove metadata keys before writing, but preserve split field
                clean_sample = _remove_metadata(sample)
                clean_sample["split"] = "val"
                json_line = json.dumps(clean_sample, ensure_ascii=False)
                f.write(json_line + "\n")
                val_count += 1

    total_samples = train_count + val_count
    if total_samples > 0:
        val_percentage = val_count / total_samples * 100
        logger.info(
            f"Split complete: {train_count} train samples, {val_count} val samples "
            f"({val_percentage:.1f}% validation)"
        )
    else:
        logger.warning(
            "Split complete: 0 train samples, 0 val samples (no data to split)"
        )

    return train_count, val_count


def _remove_metadata(sample: dict) -> dict:
    """Remove internal metadata keys from sample."""
    clean = {k: v for k, v in sample.items() if not k.startswith("_")}
    return clean


def split_merged_dataset(
    merged_path: str,
    train_path: str,
    val_path: str,
    val_ratio: float = 0.1,
    phase1_source_key: str = "phase1",
    phase2_source_key: str = "_source_crate",
) -> tuple[int, int]:
    """
    Split merged Phase-1/Phase-2 dataset by source.

    Args:
        merged_path: Path to merged JSONL file
        train_path: Path to output training JSONL file
        val_path: Path to output validation JSONL file
        val_ratio: Ratio of sources for validation (default: 0.1)
        phase1_source_key: Source identifier for Phase-1 samples (default: "phase1")
        phase2_source_key: Key to extract source from Phase-2 samples (default: "_source_crate")

    Returns:
        Tuple of (train_count, val_count)
    """
    merged_file = Path(merged_path)
    if not merged_file.exists():
        logger.error(f"Merged file not found: {merged_path}")
        return 0, 0

    # Group samples by source
    source_groups: dict[str, list[dict]] = defaultdict(list)

    logger.info(f"Loading merged dataset from {merged_path}...")
    with open(merged_file, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                sample = json.loads(line)

                # Determine source: Phase-2 samples have _source_crate, Phase-1 don't
                source = sample.get(phase2_source_key)
                if source:
                    # Phase-2 sample
                    source_groups[source].append(sample)
                else:
                    # Phase-1 sample - group all together or by some identifier
                    source_groups[phase1_source_key].append(sample)

            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON on line {line_num}: {e}")
                continue

    logger.info(f"Grouped into {len(source_groups)} sources")

    # Split sources
    source_list = list(source_groups.keys())
    random.shuffle(source_list)

    val_source_count = max(1, int(len(source_list) * val_ratio))
    val_sources = set(source_list[:val_source_count])
    train_sources = set(source_list[val_source_count:])

    logger.info(
        f"Split: {len(train_sources)} sources -> train, {len(val_sources)} sources -> val"
    )

    # Write train set
    train_file = Path(train_path)
    train_file.parent.mkdir(parents=True, exist_ok=True)

    train_count = 0
    with open(train_file, "w", encoding="utf-8") as f:
        for source in train_sources:
            for sample in source_groups[source]:
                clean_sample = _remove_metadata(sample)
                clean_sample["split"] = "train"
                json_line = json.dumps(clean_sample, ensure_ascii=False)
                f.write(json_line + "\n")
                train_count += 1

    # Write val set
    val_file = Path(val_path)
    val_file.parent.mkdir(parents=True, exist_ok=True)

    val_count = 0
    with open(val_file, "w", encoding="utf-8") as f:
        for source in val_sources:
            for sample in source_groups[source]:
                clean_sample = _remove_metadata(sample)
                clean_sample["split"] = "val"
                json_line = json.dumps(clean_sample, ensure_ascii=False)
                f.write(json_line + "\n")
                val_count += 1

    logger.info(f"Split complete: {train_count} train samples, {val_count} val samples")

    return train_count, val_count
