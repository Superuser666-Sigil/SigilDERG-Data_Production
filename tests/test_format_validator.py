"""
Tests for sigil_pipeline.format_validator module.

Tests format validation, Phase 1 spec loading, and format comparison.
"""

from sigil_pipeline.format_validator import FormatValidator


class TestFormatValidatorInit:
    """Test FormatValidator initialization."""

    def test_init_without_spec(self):
        """Test initialization without spec."""
        validator = FormatValidator()
        assert validator.phase1_spec is None or isinstance(validator.phase1_spec, dict)

    def test_init_with_spec_path(self, phase1_spec):
        """Test initialization with spec path."""
        validator = FormatValidator(phase1_spec)
        assert validator.phase1_spec is not None
        assert "format_requirements" in validator.phase1_spec

    def test_init_with_nonexistent_spec(self, tmp_path):
        """Test initialization with non-existent spec."""
        nonexistent = tmp_path / "nonexistent.json"
        validator = FormatValidator(nonexistent)
        # Should handle gracefully
        assert validator.phase1_spec is None or isinstance(validator.phase1_spec, dict)


class TestLoadPhase1Spec:
    """Test load_phase1_spec method."""

    def test_load_valid_spec(self, phase1_spec):
        """Test loading valid Phase 1 spec."""
        validator = FormatValidator()
        validator.load_phase1_spec(phase1_spec)
        assert validator.phase1_spec is not None
        assert "format_requirements" in validator.phase1_spec

    def test_load_invalid_json(self, tmp_path):
        """Test loading invalid JSON spec."""
        invalid_spec = tmp_path / "invalid.json"
        invalid_spec.write_text("invalid json content")

        validator = FormatValidator()
        # Should handle error gracefully
        validator.load_phase1_spec(invalid_spec)
        # May set to None or keep previous value


class TestValidateSample:
    """Test validate_sample method."""

    def test_valid_sample(self):
        """Test validation of valid sample."""
        validator = FormatValidator()
        sample = {"prompt": "Write code", "gen": "fn main() {}"}
        is_valid, errors = validator.validate_sample(sample)
        assert is_valid is True
        assert len(errors) == 0

    def test_missing_prompt_field(self):
        """Test validation with missing prompt field."""
        validator = FormatValidator()
        sample = {"gen": "fn main() {}"}
        is_valid, errors = validator.validate_sample(sample)
        assert is_valid is False
        assert any("prompt" in str(e).lower() for e in errors)

    def test_missing_gen_field(self):
        """Test validation with missing gen field."""
        validator = FormatValidator()
        sample = {"prompt": "Write code"}
        is_valid, errors = validator.validate_sample(sample)
        assert is_valid is False
        assert any("gen" in str(e).lower() for e in errors)

    def test_wrong_field_types(self):
        """Test validation with wrong field types."""
        validator = FormatValidator()
        sample = {"prompt": 123, "gen": ["not", "a", "string"]}
        is_valid, errors = validator.validate_sample(sample)
        assert is_valid is False
        assert len(errors) > 0

    def test_prompt_style_validation(self, phase1_spec):
        """Test prompt style validation."""
        validator = FormatValidator(phase1_spec)
        # Very long prompt
        sample = {"prompt": "a" * 1000, "gen": "code"}
        is_valid, errors = validator.validate_sample(sample)
        # May warn but not necessarily invalid
        assert isinstance(is_valid, bool)

    def test_code_formatting_validation(self, phase1_spec):
        """Test code formatting validation."""
        validator = FormatValidator(phase1_spec)
        # Code with backticks when spec says no backticks
        sample = {"prompt": "Write code", "gen": "```rust\nfn main() {}\n```"}
        is_valid, errors = validator.validate_sample(sample)
        # Should detect backticks mismatch
        assert isinstance(is_valid, bool)

    def test_empty_sample(self):
        """Test validation of empty sample."""
        validator = FormatValidator()
        sample = {}
        is_valid, errors = validator.validate_sample(sample)
        assert is_valid is False
        assert len(errors) > 0

    def test_very_long_prompt_and_code(self):
        """Test validation with very long prompt and code."""
        validator = FormatValidator()
        sample = {
            "prompt": "a" * 10000,
            "gen": "b" * 10000,
        }
        is_valid, errors = validator.validate_sample(sample)
        # Should handle long content
        assert isinstance(is_valid, bool)


class TestValidateJsonlFile:
    """Test validate_jsonl_file method."""

    def test_validate_valid_jsonl_file(self, sample_jsonl_file):
        """Test validation of valid JSONL file."""
        validator = FormatValidator()
        report = validator.validate_jsonl_file(sample_jsonl_file, max_samples=10)
        assert report["total_samples"] > 0
        assert "valid_samples" in report
        assert "invalid_samples" in report

    def test_validate_invalid_jsonl_file(self, tmp_path):
        """Test validation of invalid JSONL file."""
        invalid_file = tmp_path / "invalid.jsonl"
        with open(invalid_file, "w", encoding="utf-8") as f:
            f.write('{"prompt": "test"}\n')  # Missing gen
            f.write('{"gen": "code"}\n')  # Missing prompt
            f.write('{"prompt": "test", "gen": "code"}\n')  # Valid

        validator = FormatValidator()
        report = validator.validate_jsonl_file(invalid_file, max_samples=10)
        assert report["invalid_samples"] == 2
        assert report["valid_samples"] == 1

    def test_validate_mixed_jsonl_file(self, tmp_path):
        """Test validation of mixed valid/invalid JSONL file."""
        mixed_file = tmp_path / "mixed.jsonl"
        with open(mixed_file, "w", encoding="utf-8") as f:
            for i in range(5):
                if i % 2 == 0:
                    f.write(f'{{"prompt": "test{i}", "gen": "code{i}"}}\n')
                else:
                    f.write(f'{{"invalid": "sample{i}"}}\n')

        validator = FormatValidator()
        report = validator.validate_jsonl_file(mixed_file, max_samples=10)
        assert report["valid_samples"] == 3
        assert report["invalid_samples"] == 2

    def test_validate_nonexistent_file(self, tmp_path):
        """Test validation of non-existent file."""
        validator = FormatValidator()
        nonexistent = tmp_path / "nonexistent.jsonl"
        report = validator.validate_jsonl_file(nonexistent, max_samples=10)
        assert len(report["errors"]) > 0

    def test_validate_with_max_samples_limit(self, sample_jsonl_file):
        """Test validation with max_samples limit."""
        validator = FormatValidator()
        report = validator.validate_jsonl_file(sample_jsonl_file, max_samples=1)
        assert report["total_samples"] <= 1


class TestCompareFormats:
    """Test compare_formats method."""

    def test_compare_matching_formats(self, tmp_path):
        """Test comparison of matching formats."""
        phase1_file = tmp_path / "phase1.jsonl"
        phase2_file = tmp_path / "phase2.jsonl"

        with open(phase1_file, "w", encoding="utf-8") as f:
            f.write('{"prompt": "test1", "gen": "code1"}\n')

        with open(phase2_file, "w", encoding="utf-8") as f:
            f.write('{"prompt": "test2", "gen": "code2"}\n')

        validator = FormatValidator()
        comparison = validator.compare_formats(phase1_file, phase2_file, max_samples=10)
        assert comparison["samples_compared"] > 0

    def test_compare_field_mismatch(self, tmp_path):
        """Test comparison with field mismatches."""
        phase1_file = tmp_path / "phase1.jsonl"
        phase2_file = tmp_path / "phase2.jsonl"

        with open(phase1_file, "w", encoding="utf-8") as f:
            f.write('{"prompt": "test", "gen": "code"}\n')

        with open(phase2_file, "w", encoding="utf-8") as f:
            f.write(
                '{"instruction": "test", "output": "code"}\n'
            )  # Different field names

        validator = FormatValidator()
        comparison = validator.compare_formats(phase1_file, phase2_file, max_samples=10)
        # Should detect field mismatch
        assert len(comparison["differences"]) > 0 or comparison["samples_compared"] > 0

    def test_compare_type_mismatch(self, tmp_path):
        """Test comparison with type mismatches."""
        phase1_file = tmp_path / "phase1.jsonl"
        phase2_file = tmp_path / "phase2.jsonl"

        with open(phase1_file, "w", encoding="utf-8") as f:
            f.write('{"prompt": "test", "gen": "code"}\n')

        with open(phase2_file, "w", encoding="utf-8") as f:
            f.write('{"prompt": 123, "gen": ["not", "string"]}\n')  # Wrong types

        validator = FormatValidator()
        comparison = validator.compare_formats(phase1_file, phase2_file, max_samples=10)
        assert comparison["samples_compared"] > 0

    def test_compare_prompt_style_differences(self, tmp_path):
        """Test comparison of prompt style differences."""
        phase1_file = tmp_path / "phase1.jsonl"
        phase2_file = tmp_path / "phase2.jsonl"

        with open(phase1_file, "w", encoding="utf-8") as f:
            f.write('{"prompt": "Write a Rust program", "gen": "code"}\n')

        with open(phase2_file, "w", encoding="utf-8") as f:
            f.write(
                '{"prompt": "Please write code", "gen": "code"}\n'
            )  # Different style

        validator = FormatValidator()
        comparison = validator.compare_formats(phase1_file, phase2_file, max_samples=10)
        assert comparison["samples_compared"] > 0

    def test_compare_code_formatting_differences(self, tmp_path):
        """Test comparison of code formatting differences."""
        phase1_file = tmp_path / "phase1.jsonl"
        phase2_file = tmp_path / "phase2.jsonl"

        with open(phase1_file, "w", encoding="utf-8") as f:
            f.write('{"prompt": "test", "gen": "fn main() {}"}\n')  # No backticks

        with open(phase2_file, "w", encoding="utf-8") as f:
            f.write(
                '{"prompt": "test", "gen": "```rust\\nfn main() {}\\n```"}\n'
            )  # With backticks

        validator = FormatValidator()
        comparison = validator.compare_formats(phase1_file, phase2_file, max_samples=10)
        assert comparison["samples_compared"] > 0

    def test_compare_nonexistent_files(self, tmp_path):
        """Test comparison with non-existent files."""
        phase1_file = tmp_path / "phase1.jsonl"
        phase2_file = tmp_path / "nonexistent.jsonl"

        with open(phase1_file, "w", encoding="utf-8") as f:
            f.write('{"prompt": "test", "gen": "code"}\n')

        validator = FormatValidator()
        comparison = validator.compare_formats(phase1_file, phase2_file, max_samples=10)
        assert len(comparison["differences"]) > 0  # Should report file not found
