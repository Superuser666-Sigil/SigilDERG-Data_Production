"""
Downsample prompt/gen datasets to match a desired task_type distribution.

Usage example:

    python tools/rebalance_task_mix.py \
        --input datasets/phase2_full.jsonl \
        --output datasets/phase2_balanced.jsonl \
        --target-mix code_generation=0.4,error_fixing=0.3,transformations=0.2,explanations=0.1

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.5.0
"""

from __future__ import annotations

import argparse
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path


def parse_mix(mix_arg: str) -> dict[str, float]:
    result: dict[str, float] = {}
    for part in mix_arg.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise ValueError(f"Invalid target mix component: '{part}'")
        key, value = part.split("=", 1)
        result[key.strip()] = float(value.strip())

    total = sum(result.values())
    if not result or total <= 0:
        raise ValueError("target mix must contain positive weights")

    return {task: weight / total for task, weight in result.items()}


def determine_total_samples(
    buckets: dict[str, list[str]],
    target_mix: dict[str, float],
    requested_total: int | None,
) -> int:
    if requested_total:
        return requested_total

    ceilings = []
    for task, ratio in target_mix.items():
        if ratio <= 0:
            continue
        available = len(buckets.get(task, []))
        if available == 0:
            raise ValueError(f"No samples available for task '{task}'.")
        ceilings.append(available / ratio)

    if not ceilings:
        raise ValueError("Could not determine total samples from target mix.")

    return max(1, math.floor(min(ceilings)))


def compute_target_counts(
    buckets: dict[str, list[str]],
    target_mix: dict[str, float],
    total_samples: int,
) -> dict[str, int]:
    raw_targets = {
        task: target_mix.get(task, 0.0) * total_samples for task in target_mix
    }
    floored = {task: math.floor(value) for task, value in raw_targets.items()}
    remainder = total_samples - sum(floored.values())

    if remainder > 0:
        fractions = sorted(
            ((raw_targets[task] - floored[task], task) for task in floored),
            reverse=True,
        )
        for _, task in fractions:
            if remainder == 0:
                break
            floored[task] += 1
            remainder -= 1

    for task, target in floored.items():
        available = len(buckets.get(task, []))
        if target > available:
            raise ValueError(
                f"Need {target} samples for '{task}' but only {available} available."
            )

    return floored


def rebalance_dataset(
    input_path: Path,
    output_path: Path,
    target_mix: dict[str, float],
    total_samples: int | None,
    seed: int,
) -> dict[str, int]:
    rng = random.Random(seed)
    buckets: dict[str, list[str]] = defaultdict(list)

    with input_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                sample = json.loads(line)
            except json.JSONDecodeError:
                continue
            task_type = sample.get("_task_type", "code_generation")
            buckets[task_type].append(json.dumps(sample))

    total_target = determine_total_samples(buckets, target_mix, total_samples)
    target_counts = compute_target_counts(buckets, target_mix, total_target)

    selected = []
    for task, goal in target_counts.items():
        items = buckets.get(task, [])
        if goal >= len(items):
            selected.extend(items)
        else:
            selected.extend(rng.sample(items, goal))

    rng.shuffle(selected)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as out_handle:
        for entry in selected:
            out_handle.write(entry)
            out_handle.write("\n")

    final_counter = Counter()
    for entry in selected:
        sample = json.loads(entry)
        final_counter[sample.get("_task_type", "code_generation")] += 1

    summary_path = output_path.with_suffix(output_path.suffix + ".summary.json")
    with summary_path.open("w", encoding="utf-8") as summary_handle:
        total_selected = sum(final_counter.values())
        ratios = {task: count / total_selected for task, count in final_counter.items()}
        json.dump(
            {
                "input": str(input_path),
                "output": str(output_path),
                "target_mix": target_mix,
                "actual_counts": dict(final_counter),
                "actual_ratios": ratios,
                "total_samples": total_selected,
            },
            summary_handle,
            indent=2,
        )

    return dict(final_counter)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rebalance prompt/gen dataset by task_type."
    )
    parser.add_argument("--input", required=True, help="Input JSONL path")
    parser.add_argument("--output", required=True, help="Output JSONL path")
    parser.add_argument(
        "--target-mix",
        required=True,
        help="Comma-separated mix, e.g. code_generation=0.5,error_fixing=0.2,...",
    )
    parser.add_argument(
        "--total-samples",
        type=int,
        default=None,
        help="Optional explicit total sample count. Defaults to the largest value allowed by available data.",
    )
    parser.add_argument("--seed", type=int, default=1234, help="Sampling seed")

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    target_mix = parse_mix(args.target_mix)

    counts = rebalance_dataset(
        input_path=input_path,
        output_path=output_path,
        target_mix=target_mix,
        total_samples=args.total_samples,
        seed=args.seed,
    )

    total = sum(counts.values())
    ratios = {task: count / total for task, count in counts.items()}
    print(f"Wrote {total} samples to {output_path}")
    print("Final task mix:")
    for task, ratio in ratios.items():
        print(f"  {task}: {counts[task]} ({ratio:.2%})")


if __name__ == "__main__":
    main()
