"""
Tests for sigil_pipeline.format_validator module.

Tests format validation and format comparison.
"""

from sigil_pipeline.format_validator import FormatValidator


class TestFormatValidatorInit:
    """Test FormatValidator initialization."""

    def test_init_without_spec(self):
        """Test initialization without spec."""
        validator = FormatValidator()
        assert validator is not None


class TestValidateSample:
    """Test validate_sample method."""

    def test_valid_sample(self):
        """Test validation of valid sample."""
        validator = FormatValidator()
        sample = {
            "input_data": {"prompt": "Write code", "code": "fn main() {}"},
            "output_data": {"code": "fn main() {}"},
        }
        is_valid, errors = validator.validate_sample(sample)
        assert is_valid is True
        assert len(errors) == 0

    def test_missing_input_data_field(self):
        """Test validation with missing input_data field."""
        validator = FormatValidator()
        sample = {"output_data": {"code": "fn main() {}"}}
        is_valid, errors = validator.validate_sample(sample)
        assert is_valid is False
        assert any("input_data" in str(e).lower() for e in errors)

    def test_missing_output_data_field(self):
        """Test validation with missing output_data field."""
        validator = FormatValidator()
        sample = {"input_data": {"prompt": "Write code", "code": "fn main() {}"}}
        is_valid, errors = validator.validate_sample(sample)
        assert is_valid is False
        assert any("output_data" in str(e).lower() for e in errors)

    def test_wrong_field_types(self):
        """Test validation with wrong field types."""
        validator = FormatValidator()
        sample = {"input_data": 123, "output_data": ["not", "a", "dict"]}
        is_valid, errors = validator.validate_sample(sample)
        assert is_valid is False
        assert len(errors) > 0

    def test_code_length_validation(self):
        """Test code length validation with max limits."""
        validator = FormatValidator()
        sample = {
            "input_data": {"prompt": "Write code", "code": "a" * 10000},
            "output_data": {"code": "a"},
        }
        is_valid, errors = validator.validate_sample(sample, max_chars=8000)
        assert is_valid is False
        assert any("max_chars" in str(e) for e in errors)

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
            "input_data": {"prompt": "a" * 10000, "code": "b" * 10000},
            "output_data": {"code": "b" * 10000},
        }
        is_valid, errors = validator.validate_sample(sample)
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
            f.write('{"input_data": {"prompt": "test"}}\n')
            f.write('{"output_data": {"code": "code"}}\n')
            f.write(
                '{"input_data": {"prompt": "test", "code": "code"}, "output_data": {"code": "code"}}\n'
            )

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
                    f.write(
                        f'{{"input_data": {{"prompt": "test{i}", "code": "code{i}"}}, "output_data": {{"code": "code{i}"}}}}\n'
                    )
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
            f.write(
                '{"input_data": {"prompt": "test2", "code": "code2"}, "output_data": {"code": "code2"}}\n'
            )

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
            f.write('{"instruction": "test", "output": "code"}\n')

        validator = FormatValidator()
        comparison = validator.compare_formats(phase1_file, phase2_file, max_samples=10)
        assert comparison["samples_compared"] > 0

    def test_compare_type_mismatch(self, tmp_path):
        """Test comparison with type mismatches."""
        phase1_file = tmp_path / "phase1.jsonl"
        phase2_file = tmp_path / "phase2.jsonl"

        with open(phase1_file, "w", encoding="utf-8") as f:
            f.write('{"prompt": "test", "gen": "code"}\n')

        with open(phase2_file, "w", encoding="utf-8") as f:
            f.write('{"input_data": 123, "output_data": ["not", "dict"]}\n')

        validator = FormatValidator()
        comparison = validator.compare_formats(phase1_file, phase2_file, max_samples=10)
        assert comparison["samples_compared"] > 0
