"""
Format validator for ensuring Phase 2 samples match Phase 1 format exactly.

Validates JSONL structure, field names, prompt style, and code formatting.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.5.0
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
            sample: Sample dictionary with 'prompt' and 'gen' keys
            max_lines: Maximum lines for gen field (Phase-2 validation)
            max_chars: Maximum characters for gen field (Phase-2 validation)

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Check required fields
        if "prompt" not in sample:
            errors.append("Missing required field: 'prompt'")
        if "gen" not in sample:
            errors.append("Missing required field: 'gen'")

        if errors:
            return False, errors

        # Validate field types
        prompt_value = sample.get("prompt")
        gen_value = sample.get("gen")

        if not isinstance(prompt_value, str):
            errors.append("Field 'prompt' must be a string")
            prompt_value = ""
        if not isinstance(gen_value, str):
            errors.append("Field 'gen' must be a string")
            gen_value = ""

        # Validate non-empty
        if prompt_value.strip() == "":
            errors.append("Field 'prompt' must not be empty")
        if gen_value.strip() == "":
            errors.append("Field 'gen' must not be empty")

        # Phase-2 validation (snippet size limits)
        if max_lines and sample.get("gen"):
            gen_lines = sample["gen"].count("\n") + 1
            if gen_lines > max_lines:
                errors.append(
                    f"Gen field exceeds max_lines limit: {gen_lines} > {max_lines}"
                )

        if max_chars and sample.get("gen"):
            gen_chars = len(sample["gen"])
            if gen_chars > max_chars:
                errors.append(
                    f"Gen field exceeds max_chars limit: {gen_chars} > {max_chars}"
                )

        is_valid = len(errors) == 0
        return is_valid, errors

    def validate_jsonl_file(
        self, file_path: Path, max_samples: int = 100
    ) -> dict[str, Any]:
        """
        Validate a JSONL file against Phase 1 format.

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

        # Calculate validation rate
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

        # Load samples
        phase1_samples = []
        phase2_samples = []

        with open(phase1_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        phase1_samples.append(json.loads(line))
                        if len(phase1_samples) >= max_samples:
                            break
                    except json.JSONDecodeError:
                        continue

        with open(phase2_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        phase2_samples.append(json.loads(line))
                        if len(phase2_samples) >= max_samples:
                            break
                    except json.JSONDecodeError:
                        continue

        # Compare structures
        if phase1_samples and phase2_samples:
            phase1_fields = set(phase1_samples[0].keys())
            phase2_fields = set(phase2_samples[0].keys())

            if phase1_fields != phase2_fields:
                comparison["differences"].append(
                    {
                        "type": "field_mismatch",
                        "phase1_fields": list(phase1_fields),
                        "phase2_fields": list(phase2_fields),
                        "missing_in_phase2": list(phase1_fields - phase2_fields),
                        "extra_in_phase2": list(phase2_fields - phase1_fields),
                    }
                )

            # Compare sample structures
            for i, (p1, p2) in enumerate(zip(phase1_samples[:10], phase2_samples[:10])):
                comparison["samples_compared"] += 1

                # Check field types
                for field in phase1_fields & phase2_fields:
                    p1_type = type(p1[field]).__name__
                    p2_type = type(p2[field]).__name__
                    if p1_type != p2_type:
                        comparison["differences"].append(
                            {
                                "type": "type_mismatch",
                                "sample": i,
                                "field": field,
                                "phase1_type": p1_type,
                                "phase2_type": p2_type,
                            }
                        )

                # Check prompt style similarity
                if "prompt" in p1 and "prompt" in p2:
                    p1_prompt = p1["prompt"]
                    p2_prompt = p2["prompt"]

                    # Check for common patterns
                    if "Write a Rust" in p1_prompt and "Write a Rust" not in p2_prompt:
                        comparison["differences"].append(
                            {
                                "type": "prompt_style",
                                "sample": i,
                                "issue": "Phase 2 prompt missing 'Write a Rust' pattern",
                            }
                        )

                # Check code formatting
                if "gen" in p1 and "gen" in p2:
                    p1_has_backticks = "```" in p1["gen"]
                    p2_has_backticks = "```" in p2["gen"]
                    if p1_has_backticks != p2_has_backticks:
                        comparison["differences"].append(
                            {
                                "type": "code_formatting",
                                "sample": i,
                                "issue": f"Backticks mismatch: Phase 1={p1_has_backticks}, Phase 2={p2_has_backticks}",
                            }
                        )

        comparison["format_matches"] = comparison["samples_compared"] - len(
            comparison["differences"]
        )

        return comparison
