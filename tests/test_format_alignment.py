"""
Tests for Phase 2 format alignment with Phase 1.

Validates that Phase 2 samples match Phase 1 format exactly.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
"""

import json
import tempfile
from pathlib import Path

import pytest

from sigil_pipeline.dataset_builder import build_dataset_entries, format_code_for_gen
from sigil_pipeline.format_validator import FormatValidator


def test_sample_structure():
    """Test that samples have correct structure (prompt and gen fields)."""
    files = [
        {
            "path": "test.rs",
            "code": 'fn main() {\n    println!("Hello");\n}',
            "crate_name": "test_crate",
        }
    ]

    # build_dataset_entries returns a generator; consume it into a list
    samples = list(build_dataset_entries(files, validate_format=False))

    assert len(samples) == 1
    sample = samples[0]

    assert "prompt" in sample
    assert "gen" in sample
    assert isinstance(sample["prompt"], str)
    assert isinstance(sample["gen"], str)


def test_format_validator():
    """Test format validator with valid and invalid samples."""
    validator = FormatValidator()

    # Valid sample
    valid_sample = {
        "prompt": "Write a Rust program",
        "gen": "fn main() {}",
    }
    is_valid, errors = validator.validate_sample(valid_sample)
    assert is_valid
    assert len(errors) == 0

    # Invalid sample (missing gen)
    invalid_sample = {
        "prompt": "Write a Rust program",
    }
    is_valid, errors = validator.validate_sample(invalid_sample)
    assert not is_valid
    assert len(errors) > 0


def test_code_formatting():
    """Test code formatting matches Phase 1 (no backticks if Phase 1 didn't use them)."""
    code_with_backticks = "```rust\nfn main() {}\n```"

    # Format without Phase 1 spec (should preserve backticks)
    formatted1 = format_code_for_gen(code_with_backticks, None)
    assert "```" in formatted1

    # Format with Phase 1 spec that doesn't use backticks
    phase1_spec_no_backticks = {
        "format_requirements": {
            "code_formatting": {
                "has_backticks": False,
            }
        }
    }
    formatted2 = format_code_for_gen(code_with_backticks, phase1_spec_no_backticks)
    assert "```" not in formatted2
    assert "fn main() {}" in formatted2


def test_jsonl_file_validation():
    """Test validation of a JSONL file."""
    validator = FormatValidator()

    # Create temporary JSONL file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        # Write valid sample
        json.dump({"prompt": "Write code", "gen": "fn main() {}"}, f)
        f.write("\n")
        # Write invalid sample (missing gen)
        json.dump({"prompt": "Write code"}, f)
        f.write("\n")
        temp_path = Path(f.name)

    try:
        report = validator.validate_jsonl_file(temp_path, max_samples=10)

        assert report["total_samples"] == 2
        assert report["valid_samples"] == 1
        assert report["invalid_samples"] == 1
        assert len(report["errors"]) > 0
    finally:
        temp_path.unlink()


def test_prompt_generation_style():
    """Test that prompts match Phase 1 style (direct instruction)."""
    from sigil_pipeline.dataset_builder import generate_prompt_for_code

    code = 'fn main() {\n    println!("Hello");\n}'
    prompt = generate_prompt_for_code(code)

    # Should start with instruction verb
    assert prompt.startswith(("Write", "Create", "Implement", "Demonstrate"))
    # Should not have personal tone
    assert "you" not in prompt.lower() or "your" not in prompt.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
