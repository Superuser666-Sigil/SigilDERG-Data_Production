"""
exporter
========

Minimal exporter for writing instruction/response pairs to disk.

This exporter writes each sample on its own line in JSON Lines (JSONL)
format. Samples must contain ``prompt`` and ``gen`` keys. Metadata keys
(those starting with an underscore) are removed by default since they
should not be exposed to the training process.
"""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Any, AsyncIterable, Callable, Dict, Iterable, Optional, Sequence

logger = logging.getLogger(__name__)


def _normalize_sample(
    sample: Dict[str, Any],
    *,
    remove_metadata: bool,
) -> Dict[str, Any] | None:
    if not isinstance(sample, dict):
        return None

    prompt = sample.get("prompt")
    gen = sample.get("gen")

    if not (isinstance(prompt, str) and prompt.strip()):
        input_data = sample.get("input_data")
        if isinstance(input_data, dict):
            prompt = input_data.get("prompt")

    if not (isinstance(gen, str) and gen.strip()):
        output_data = sample.get("output_data")
        if isinstance(output_data, dict):
            gen = output_data.get("gen")

    if not (
        isinstance(prompt, str)
        and prompt.strip() != ""
        and isinstance(gen, str)
        and gen.strip() != ""
    ):
        return None

    normalized = {"prompt": prompt, "gen": gen}
    if not remove_metadata:
        for key, value in sample.items():
            if key.startswith("_"):
                normalized[key] = value
    return normalized


def write_jsonl(
    samples: Iterable[Dict[str, Any]],
    path: str,
    *,
    remove_metadata: bool = True,
) -> int:
    """Write an iterable of samples to ``path`` in JSONL format.

    Parameters
    ----------
    samples:
        An iterable of dictionaries. Each dictionary should have
        ``prompt`` and ``gen`` keys.
    path:
        File system path to the output file. Parent directories are created if needed.
    remove_metadata:
        If ``True``, keys starting with ``'_'`` are dropped from each
        sample before writing.
    """
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with output_path.open("w", encoding="utf-8") as f:
        for sample in samples:
            normalized = _normalize_sample(sample, remove_metadata=remove_metadata)
            if normalized is None:
                continue
            f.write(json.dumps(normalized, ensure_ascii=False) + "\n")
            count += 1
    return count


async def write_jsonl_async(
    samples: AsyncIterable[Dict[str, Any]],
    path: str,
    *,
    remove_metadata: bool = True,
    flush_every: int = 1,
) -> int:
    """Write an async iterable of samples to ``path`` in JSONL format."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with output_path.open("w", encoding="utf-8") as f:
        async for sample in samples:
            normalized = _normalize_sample(sample, remove_metadata=remove_metadata)
            if normalized is None:
                continue
            f.write(json.dumps(normalized, ensure_ascii=False) + "\n")
            count += 1
            if flush_every > 0 and count % flush_every == 0:
                f.flush()
    return count


def _repeat_count(weight: float) -> int:
    if weight <= 0:
        return 0
    if weight < 1:
        return 1 if random.random() < weight else 0
    return max(1, int(round(weight)))


def merge_jsonl_files(
    input_paths: Sequence[str],
    output_path: str,
    *,
    shuffle: bool = False,
    weights: Optional[Sequence[float]] = None,
) -> int:
    """Merge multiple JSONL files into a single output file.

    Args:
        input_paths: List of input JSONL file paths.
        output_path: Path to the merged JSONL file.
        shuffle: Whether to shuffle lines before writing.
        weights: Optional per-file weights for repetition or downsampling.

    Returns:
        Number of samples written.
    """
    if weights is not None and len(weights) != len(input_paths):
        raise ValueError("weights must match input_paths length")

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    if shuffle:
        lines: list[str] = []
        for idx, input_path in enumerate(input_paths):
            path = Path(input_path)
            if not path.exists():
                logger.warning(f"Skipping missing JSONL file: {input_path}")
                continue
            weight = weights[idx] if weights is not None else 1.0
            repeat = _repeat_count(weight)
            if repeat == 0:
                continue
            with path.open("r", encoding="utf-8") as f:
                file_lines = [line for line in f if line.strip()]
            lines.extend(file_lines * repeat)
        random.shuffle(lines)
        with output_file.open("w", encoding="utf-8") as out:
            for line in lines:
                out.write(line.rstrip("\n") + "\n")
        return len(lines)

    count = 0
    with output_file.open("w", encoding="utf-8") as out:
        for idx, input_path in enumerate(input_paths):
            path = Path(input_path)
            if not path.exists():
                logger.warning(f"Skipping missing JSONL file: {input_path}")
                continue
            weight = weights[idx] if weights is not None else 1.0
            repeat = _repeat_count(weight)
            if repeat == 0:
                continue
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    for _ in range(repeat):
                        out.write(line.rstrip("\n") + "\n")
                        count += 1
    return count


def merge_phase2_shards(
    primary_path: str,
    extra_paths: Sequence[str],
    *,
    validate_sample: Callable[[Dict[str, Any]], tuple[bool, list[str]]] | None = None,
    strict: bool = False,
    deduplicate_prompts: bool = False,
    seen_prompts: set[str] | None = None,
) -> tuple[int, dict[str, int]]:
    """Append additional Phase-2 shards to the primary JSONL file."""
    primary_file = Path(primary_path)
    primary_file.parent.mkdir(parents=True, exist_ok=True)

    added = 0
    per_file_counts: dict[str, int] = {}
    with primary_file.open("a", encoding="utf-8") as out:
        for extra_path in extra_paths:
            path = Path(extra_path)
            if not path.exists():
                logger.warning(f"Skipping missing shard: {extra_path}")
                continue
            count = 0
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    if validate_sample or deduplicate_prompts or strict:
                        try:
                            sample = json.loads(line)
                        except json.JSONDecodeError as exc:
                            message = f"Invalid JSON in shard {path}: {exc}"
                            if strict:
                                raise ValueError(message) from exc
                            logger.warning(message)
                            continue
                        if validate_sample:
                            ok, errors = validate_sample(sample)
                            if not ok:
                                message = (
                                    f"Invalid sample in shard {path}: {', '.join(errors)}"
                                )
                                if strict:
                                    raise ValueError(message)
                                logger.warning(message)
                                continue
                        if deduplicate_prompts:
                            prompt = sample.get("prompt")
                            if not isinstance(prompt, str) or not prompt.strip():
                                message = f"Missing prompt in shard {path}"
                                if strict:
                                    raise ValueError(message)
                                logger.warning(message)
                                continue
                            if seen_prompts is None:
                                seen_prompts = set()
                            prompt_key = prompt.strip()
                            if prompt_key in seen_prompts:
                                message = f"Duplicate prompt in shard {path}"
                                if strict:
                                    raise ValueError(message)
                                logger.warning(message)
                                continue
                            seen_prompts.add(prompt_key)
                    out.write(line.rstrip("\n") + "\n")
                    count += 1
            per_file_counts[str(path)] = count
            added += count

    return added, per_file_counts


def write_metrics(metrics: Dict[str, Any], path: str) -> None:
    """Write metrics JSON to disk."""
    metrics_path = Path(path)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
        f.write("\n")


__all__ = [
    "write_jsonl",
    "write_jsonl_async",
    "merge_jsonl_files",
    "merge_phase2_shards",
    "write_metrics",
]
