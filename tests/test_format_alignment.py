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
    """Test that samples have correct structure (input_data/output_data fields)."""
    files = [
        {
            "path": "test.rs",
            "code": 'fn main() {\n    println!("Hello");\n}',
            "crate_name": "test_crate",
        }
    ]

    samples = list(build_dataset_entries(files, validate_format=False))

    assert len(samples) == 1
    sample = samples[0]

    assert "input_data" in sample
    assert "output_data" in sample
    assert isinstance(sample["input_data"], dict)
    assert isinstance(sample["output_data"], dict)


def test_format_validator():
    """Test format validator with valid and invalid samples."""
    validator = FormatValidator()

    valid_sample = {
        "input_data": {"prompt": "Write a Rust program", "code": "fn main() {}"},
        "output_data": {"code": "fn main() {}"},
    }
    is_valid, errors = validator.validate_sample(valid_sample)
    assert is_valid
    assert len(errors) == 0

    invalid_sample = {
        "input_data": {"prompt": "Write a Rust program"},
    }
    is_valid, errors = validator.validate_sample(invalid_sample)
    assert not is_valid
    assert len(errors) > 0


def test_code_formatting():
    """Test code formatting removes backticks."""
    code_with_backticks = "```rust\nfn main() {}\n```"

    formatted = format_code_for_gen(code_with_backticks)
    assert "```" not in formatted


def test_jsonl_file_validation():
    """Test validation of a JSONL file."""
    validator = FormatValidator()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        json.dump(
            {
                "input_data": {"prompt": "Write code", "code": "fn main() {}"},
                "output_data": {"code": "fn main() {}"},
            },
            f,
        )
        f.write("\n")
        json.dump({"input_data": {"prompt": "Write code"}}, f)
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
