"""
Format validator for ensuring Phase 2 samples match Phase 1 format exactly.

Validates JSONL structure, field names, prompt style, and code formatting.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.6.0
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class FormatValidator:
    """Validates Phase-2 dataset format and structure."""

    def __init__(self):
        """
        Initialize format validator for Phase-2 instruct mode.
        """

    def validate_sample(
        self,
        sample: dict[str, Any],
        max_lines: int | None = None,
        max_chars: int | None = None,
    ) -> tuple[bool, list[str]]:
        """
        Validate a single sample against format specification.

        Args:
            sample: Sample dictionary with structured schema
            max_lines: Maximum lines for input code field
            max_chars: Maximum characters for input code field

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        if not isinstance(sample, dict):
            return False, ["Sample must be a dict"]

        has_legacy = "input_data" in sample or "output_data" in sample
        has_prompt_gen = "prompt" in sample or "gen" in sample

        if has_prompt_gen and not has_legacy:
            prompt_value = sample.get("prompt")
            gen_value = sample.get("gen")

            if not isinstance(prompt_value, str):
                errors.append("Field 'prompt' must be a string")
                prompt_value = ""
            if not isinstance(gen_value, str):
                errors.append("Field 'gen' must be a string")
                gen_value = ""

            if prompt_value.strip() == "":
                errors.append("Field 'prompt' must not be empty")
            if gen_value.strip() == "":
                errors.append("Field 'gen' must not be empty")

            if max_lines and prompt_value:
                prompt_lines = prompt_value.count("\n") + 1
                if prompt_lines > max_lines:
                    errors.append(
                        f"prompt exceeds max_lines limit: {prompt_lines} > {max_lines}"
                    )
            if max_chars and prompt_value:
                prompt_chars = len(prompt_value)
                if prompt_chars > max_chars:
                    errors.append(
                        f"prompt exceeds max_chars limit: {prompt_chars} > {max_chars}"
                    )

            if max_lines and gen_value:
                gen_lines = gen_value.count("\n") + 1
                if gen_lines > max_lines:
                    errors.append(
                        f"gen exceeds max_lines limit: {gen_lines} > {max_lines}"
                    )
            if max_chars and gen_value:
                gen_chars = len(gen_value)
                if gen_chars > max_chars:
                    errors.append(
                        f"gen exceeds max_chars limit: {gen_chars} > {max_chars}"
                    )
        else:
            if "input_data" not in sample:
                errors.append("Missing required field: 'input_data'")
            if "output_data" not in sample:
                errors.append("Missing required field: 'output_data'")

            if errors:
                return False, errors

            input_data = sample.get("input_data")
            output_data = sample.get("output_data")

            if not isinstance(input_data, dict):
                errors.append("Field 'input_data' must be a dict")
                input_data = {}
            if not isinstance(output_data, dict):
                errors.append("Field 'output_data' must be a dict")
                output_data = {}

            prompt_value = input_data.get("prompt")
            code_value = input_data.get("code")

            if not isinstance(prompt_value, str):
                errors.append("Field 'input_data.prompt' must be a string")
                prompt_value = ""
            if not isinstance(code_value, str):
                errors.append("Field 'input_data.code' must be a string")
                code_value = ""

            if prompt_value.strip() == "":
                errors.append("Field 'input_data.prompt' must not be empty")
            if code_value.strip() == "":
                errors.append("Field 'input_data.code' must not be empty")
            if not output_data:
                errors.append("Field 'output_data' must not be empty")

            if max_lines and code_value:
                code_lines = code_value.count("\n") + 1
                if code_lines > max_lines:
                    errors.append(
                        f"input_data.code exceeds max_lines limit: {code_lines} > {max_lines}"
                    )

            if max_chars and code_value:
                code_chars = len(code_value)
                if code_chars > max_chars:
                    errors.append(
                        f"input_data.code exceeds max_chars limit: {code_chars} > {max_chars}"
                    )

        is_valid = len(errors) == 0
        return is_valid, errors

    def validate_jsonl_file(
        self, file_path: Path, max_samples: int = 100
    ) -> dict[str, Any]:
        """
        Validate a JSONL file against Phase 2 format.

        Args:
            file_path: Path to JSONL file to validate
            max_samples: Maximum number of samples to validate (for performance)

        Returns:
            Validation report dictionary
        """
        report = {
            "file_path": str(file_path),
            "total_samples": 0,
            "valid_samples": 0,
            "invalid_samples": 0,
            "errors": [],
            "warnings": [],
        }

        if not file_path.exists():
            report["errors"].append(f"File not found: {file_path}")
            return report

        logger.info(f"Validating {file_path}...")

        with open(file_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                if line_num > max_samples:
                    break

                line = line.strip()
                if not line:
                    continue

                report["total_samples"] += 1

                try:
                    sample = json.loads(line)
                    is_valid, errors = self.validate_sample(sample)

                    if is_valid:
                        report["valid_samples"] += 1
                    else:
                        report["invalid_samples"] += 1
                        report["errors"].append(
                            {
                                "line": line_num,
                                "errors": errors,
                            }
                        )

                except json.JSONDecodeError as e:
                    report["invalid_samples"] += 1
                    report["errors"].append(
                        {
                            "line": line_num,
                            "errors": [f"Invalid JSON: {e}"],
                        }
                    )

        if report["total_samples"] > 0:
            report["validation_rate"] = (
                report["valid_samples"] / report["total_samples"]
            )
        else:
            report["validation_rate"] = 0.0

        logger.info(
            f"Validation complete: {report['valid_samples']}/{report['total_samples']} "
            f"valid ({report['validation_rate']*100:.1f}%)"
        )

        return report

    def compare_formats(
        self, phase1_file: Path, phase2_file: Path, max_samples: int = 50
    ) -> dict[str, Any]:
        """
        Compare Phase 1 and Phase 2 format side-by-side.

        Args:
            phase1_file: Path to Phase 1 samples JSONL
            phase2_file: Path to Phase 2 samples JSONL
            max_samples: Maximum samples to compare

        Returns:
            Comparison report dictionary
        """
        comparison = {
            "phase1_file": str(phase1_file),
            "phase2_file": str(phase2_file),
            "samples_compared": 0,
            "format_matches": 0,
            "differences": [],
        }

        if not phase1_file.exists():
            comparison["differences"].append(f"Phase 1 file not found: {phase1_file}")
            return comparison

        if not phase2_file.exists():
            comparison["differences"].append(f"Phase 2 file not found: {phase2_file}")
            return comparison

        logger.info(f"Comparing formats: {phase1_file} vs {phase2_file}")

        phase1_samples = []
        phase2_samples = []

        with open(phase1_file, "r", encoding="utf-8") as f1:
            for i, line in enumerate(f1):
                if i >= max_samples:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    phase1_samples.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        with open(phase2_file, "r", encoding="utf-8") as f2:
            for i, line in enumerate(f2):
                if i >= max_samples:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    phase2_samples.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        for p1, p2 in zip(phase1_samples, phase2_samples):
            comparison["samples_compared"] += 1

            p1_prompt = p1.get("prompt")
            if not p1_prompt and isinstance(p1.get("input_data"), dict):
                p1_prompt = p1["input_data"].get("prompt")

            p2_prompt = p2.get("prompt")
            if not p2_prompt and isinstance(p2.get("input_data"), dict):
                p2_prompt = p2["input_data"].get("prompt")

            if isinstance(p1_prompt, str) and isinstance(p2_prompt, str):
                comparison["format_matches"] += 1
            else:
                comparison["differences"].append(
                    {
                        "type": "prompt_style",
                        "issue": "Sample missing prompt field",
                    }
                )

        return comparison
