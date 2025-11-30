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
    """Validates Phase 2 dataset format against Phase 1 specification."""

    def __init__(
        self,
        phase1_spec_path: Path | None = None,
        prompt_mode: str = "phase1_compat",
    ):
        """
        Initialize format validator.

        Args:
            phase1_spec_path: Path to Phase 1 format specification JSON file
            prompt_mode: Validation mode ('phase1_compat' or 'instruct')
        """
        self.prompt_mode = prompt_mode
        self.phase1_spec: dict[str, Any] | None = None
        if phase1_spec_path and phase1_spec_path.exists():
            self.load_phase1_spec(phase1_spec_path)
        else:
            # Use default spec if available
            default_spec = Path("docs/phase1_format_spec.json")
            if default_spec.exists():
                self.load_phase1_spec(default_spec)
            else:
                logger.warning(
                    "No Phase 1 format spec found. Using basic validation only."
                )

    def load_phase1_spec(self, spec_path: Path) -> None:
        """Load Phase 1 format specification from JSON file."""
        try:
            with open(spec_path, "r", encoding="utf-8") as f:
                self.phase1_spec = json.load(f)
            logger.info(f"Loaded Phase 1 format spec from {spec_path}")
        except Exception as e:
            logger.error(f"Failed to load Phase 1 spec: {e}")
            self.phase1_spec = None

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

        # Phase-2 specific validation (snippet size limits)
        if self.prompt_mode == "instruct":
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

        # Phase-1 validation (only if in phase1_compat mode)
        if self.prompt_mode == "phase1_compat":
            # Check for extra fields (Phase 1 might only have prompt and gen)
            if self.phase1_spec:
                required_fields = self.phase1_spec.get("format_requirements", {}).get(
                    "required_fields", ["prompt", "gen"]
                )
                allowed_fields = set(required_fields)
                # Allow metadata fields for debugging but warn
                extra_fields = set(sample.keys()) - allowed_fields
                if extra_fields:
                    logger.debug(
                        f"Sample has extra fields (will be ignored): {extra_fields}"
                    )

            # Validate prompt style (if spec available) - only for Phase-1 mode
            prompt_characteristics: dict[str, Any] = {}
            if self.phase1_spec and "prompt" in sample:
                prompt = prompt_value
                prompt_characteristics = self.phase1_spec.get(
                    "prompt_characteristics", {}
                )

                # Check for required prompt patterns (Phase 1 uses "Write a Rust code snippet. Output only the code.")
                common_patterns = prompt_characteristics.get("common_patterns", {})
                if common_patterns:
                    # Check if prompt contains expected patterns
                    has_write_rust = "Write a Rust" in prompt
                    has_output_only = "Output only" in prompt

                    # If Phase 1 had these patterns in 100% of samples, we should enforce them
                    write_rust_ratio = common_patterns.get("Write a Rust", 0) / max(
                        prompt_characteristics.get("total_prompts", 1), 1
                    )
                    if write_rust_ratio > 0.9 and not has_write_rust:
                        errors.append(
                            "Prompt missing 'Write a Rust' pattern (required in Phase 1 format)"
                        )
                    if write_rust_ratio > 0.9 and not has_output_only:
                        errors.append(
                            "Prompt missing 'Output only' pattern (required in Phase 1 format)"
                        )

            # Check prompt length (warn if very different)
            length_stats = prompt_characteristics.get("length_stats", {})
            if length_stats:
                avg_length = length_stats.get("avg", 0)
                if avg_length > 0:
                    current_length = len(prompt)
                    # Warn if more than 2x or less than 0.5x average
                    if current_length > avg_length * 2:
                        logger.debug(
                            f"Prompt length {current_length} is much longer than Phase 1 average {avg_length}"
                        )
                    elif current_length < avg_length * 0.5:
                        logger.debug(
                            f"Prompt length {current_length} is much shorter than Phase 1 average {avg_length}"
                        )

        # Validate code formatting (backticks are optional in Phase 1 - 6.7% had them)
        if self.phase1_spec and "gen" in sample:
            gen = sample["gen"]
            code_formatting = self.phase1_spec.get("format_requirements", {}).get(
                "code_formatting", {}
            )
            backticks_ratio = code_formatting.get("backticks_ratio", 0.0)
            has_backticks_current = "```" in gen

            # Phase 1 allows backticks (6.7% of samples had them), so both are valid
            # Only warn if backticks are present but Phase 1 had very few (suggests format drift)
            if has_backticks_current and backticks_ratio < 0.05:
                logger.debug(
                    f"Code contains backticks but Phase 1 had very few ({backticks_ratio*100:.1f}%)"
                )
            # Don't error on backticks - they're valid in Phase 1 format

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
