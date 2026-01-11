"""
Format conversion utilities for SigilDERG ecosystem integration.

Converts between pipeline format (prompt/gen JSONL) and other formats
needed for fine-tuning and evaluation.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.6.0
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _extract_completion(sample: dict[str, Any]) -> str | None:
    if "gen" in sample:
        return str(sample["gen"])

    output_data = sample.get("output_data")
    if isinstance(output_data, dict) and output_data:
        for key in ("code", "fixed_code", "explanation", "docstring"):
            if key in output_data:
                return str(output_data[key])
        if len(output_data) == 1:
            return str(next(iter(output_data.values())))
        return json.dumps(output_data, ensure_ascii=False)

    return None


def prompt_gen_to_eval_format(
    jsonl_path: str,
    output_path: str,
    task_id_prefix: str = "task",
    max_samples: Optional[int] = None,
) -> int:
    """
    Convert pipeline samples to human-eval-rust format.

    Pipeline format: structured or legacy
    Evaluation format: {"task_id": "...", "completion": "..."}

    Args:
        jsonl_path: Path to input JSONL file
        output_path: Path to output JSONL file with task_id/completion format
        task_id_prefix: Prefix for task IDs (default: "task")
        max_samples: Maximum number of samples to convert (None for all)

    Returns:
        Number of samples converted
    """
    jsonl_file = Path(jsonl_path)
    if not jsonl_file.exists():
        raise FileNotFoundError(f"JSONL file not found: {jsonl_path}")

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Converting {jsonl_path} to evaluation format: {output_path}")

    count = 0
    with (
        open(jsonl_file, "r", encoding="utf-8") as infile,
        open(output_file, "w", encoding="utf-8") as outfile,
    ):
        for line_num, line in enumerate(infile, 1):
            line = line.strip()
            if not line:
                continue

            try:
                sample = json.loads(line)
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON on line {line_num}: {e}")
                continue

            completion = _extract_completion(sample)
            if completion is None:
                logger.warning(
                    f"Skipping sample on line {line_num} - missing completion field"
                )
                continue

            task_id = sample.get("task_id")
            if not task_id:
                prompt = sample.get("prompt")
                if not prompt and isinstance(sample.get("input_data"), dict):
                    prompt = sample["input_data"].get("prompt")
                if prompt:
                    task_id = f"{task_id_prefix}_{hash(prompt) % 1000000}"
                else:
                    task_id = f"{task_id_prefix}_{line_num}"

            eval_sample = {
                "task_id": str(task_id),
                "completion": completion,
            }

            if "_source_crate" in sample:
                eval_sample["_source_crate"] = sample["_source_crate"]
            if "_task_type" in sample:
                eval_sample["_task_type"] = sample["_task_type"]

            outfile.write(json.dumps(eval_sample, ensure_ascii=False) + "\n")
            count += 1

            if max_samples is not None and count >= max_samples:
                break

            if count % 10000 == 0:
                logger.info(f"Converted {count} samples...")

    logger.info(f"Converted {count} samples to evaluation format")
    return count


def prompt_gen_to_hf_dataset(
    jsonl_path: str,
    output_path: Optional[str] = None,
    variant: str = "training",
) -> Dict[str, Any]:
    """
    Convert pipeline JSONL to HuggingFace Dataset format.

    This is a convenience wrapper around the existing convert_jsonl_to_parquet.py tool.
    For direct conversion, use that tool instead.

    Args:
        jsonl_path: Path to input JSONL file
        output_path: Path to output Parquet file (optional, returns dict if None)
        variant: Output variant - "training" (metadata stripped) or "provenance" (all fields)

    Returns:
        Dictionary with conversion metadata, or writes to file if output_path provided
    """
    # Import the existing conversion function
    try:
        from tools.convert_jsonl_to_parquet import convert_jsonl_to_parquet
    except ImportError:
        # Fallback: try direct import
        import sys
        from pathlib import Path

        tools_path = Path(__file__).parent.parent / "tools"
        sys.path.insert(0, str(tools_path))
        from convert_jsonl_to_parquet import convert_jsonl_to_parquet

    if output_path:
        convert_jsonl_to_parquet(
            jsonl_path=jsonl_path,
            output_path=output_path,
            variant=variant,
        )
        return {"status": "success", "output_path": output_path}
    else:
        # Return metadata about what would be converted
        return {
            "status": "info",
            "message": "Use convert_jsonl_to_parquet tool for actual conversion",
            "input_path": jsonl_path,
            "variant": variant,
        }


def hf_dataset_to_prompt_gen(
    parquet_path: str,
    output_path: str,
    prompt_field: str = "prompt",
    gen_field: str = "gen",
) -> int:
    """
    Convert HuggingFace Parquet dataset back to prompt/gen JSONL format.

    This is a convenience wrapper around the existing convert_parquet_to_jsonl.py tool.

    Args:
        parquet_path: Path to input Parquet file
        output_path: Path to output JSONL file
        prompt_field: Field name for prompt in Parquet (default: "prompt")
        gen_field: Field name for gen in Parquet (default: "gen")

    Returns:
        Number of samples converted
    """
    # Import the existing conversion function
    try:
        from tools.convert_parquet_to_jsonl import convert_parquet_to_jsonl
    except ImportError:
        # Fallback: try direct import
        import sys
        from pathlib import Path

        tools_path = Path(__file__).parent.parent / "tools"
        sys.path.insert(0, str(tools_path))
        from convert_parquet_to_jsonl import convert_parquet_to_jsonl

    parquet_file = Path(parquet_path)
    if parquet_file.is_file():
        import shutil
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_parquet = Path(tmpdir) / parquet_file.name
            shutil.copy(parquet_file, tmp_parquet)
            convert_parquet_to_jsonl(
                parquet_dir=str(tmpdir),
                output_path=output_path,
                prompt_field=prompt_field,
                gen_field=gen_field,
            )
            return 1

    convert_parquet_to_jsonl(
        parquet_dir=parquet_path,
        output_path=output_path,
        prompt_field=prompt_field,
        gen_field=gen_field,
    )
    return 1
