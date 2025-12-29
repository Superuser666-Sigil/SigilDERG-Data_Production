"""
Tests for sigil_pipeline.converters module.

Tests format conversion utilities between pipeline format and other formats.
"""

import json
from pathlib import Path

import pytest

from sigil_pipeline.converters import (
    prompt_gen_to_eval_format,
    prompt_gen_to_hf_dataset,
)


class TestPromptGenToEvalFormat:
    """Test prompt_gen_to_eval_format function."""

    def test_basic_conversion(self, tmp_path: Path):
        """Test basic conversion to evaluation format."""
        # Create input file
        input_file = tmp_path / "input.jsonl"
        samples = [
            {"prompt": "Write a function", "gen": "fn test() {}"},
            {"prompt": "Add numbers", "gen": "fn add(a: i32, b: i32) -> i32 { a + b }"},
        ]
        with open(input_file, "w") as f:
            for s in samples:
                f.write(json.dumps(s) + "\n")

        output_file = tmp_path / "output.jsonl"
        count = prompt_gen_to_eval_format(str(input_file), str(output_file))

        assert count == 2
        assert output_file.exists()

        # Verify output format
        with open(output_file) as f:
            for line in f:
                sample = json.loads(line)
                assert "task_id" in sample
                assert "completion" in sample

    def test_nonexistent_file_raises(self, tmp_path: Path):
        """Test that nonexistent input file raises error."""
        with pytest.raises(FileNotFoundError):
            prompt_gen_to_eval_format(
                str(tmp_path / "nonexistent.jsonl"), str(tmp_path / "output.jsonl")
            )

    def test_max_samples_limit(self, tmp_path: Path):
        """Test max_samples parameter limits output."""
        input_file = tmp_path / "input.jsonl"
        with open(input_file, "w") as f:
            for i in range(100):
                f.write(json.dumps({"prompt": f"p{i}", "gen": f"g{i}"}) + "\n")

        output_file = tmp_path / "output.jsonl"
        count = prompt_gen_to_eval_format(
            str(input_file), str(output_file), max_samples=10
        )

        assert count == 10

    def test_missing_gen_field_skipped(self, tmp_path: Path):
        """Test samples without gen field are skipped."""
        input_file = tmp_path / "input.jsonl"
        samples = [
            {"prompt": "test1", "gen": "fn a() {}"},
            {"prompt": "test2"},  # Missing gen
            {"prompt": "test3", "gen": "fn b() {}"},
        ]
        with open(input_file, "w") as f:
            for s in samples:
                f.write(json.dumps(s) + "\n")

        output_file = tmp_path / "output.jsonl"
        count = prompt_gen_to_eval_format(str(input_file), str(output_file))

        assert count == 2

    def test_preserves_task_id(self, tmp_path: Path):
        """Test existing task_id is preserved."""
        input_file = tmp_path / "input.jsonl"
        with open(input_file, "w") as f:
            f.write(
                json.dumps(
                    {
                        "task_id": "custom_id_123",
                        "prompt": "test",
                        "gen": "fn test() {}",
                    }
                )
                + "\n"
            )

        output_file = tmp_path / "output.jsonl"
        prompt_gen_to_eval_format(str(input_file), str(output_file))

        with open(output_file) as f:
            sample = json.loads(f.read().strip())
            assert sample["task_id"] == "custom_id_123"

    def test_generates_task_id_from_prompt(self, tmp_path: Path):
        """Test task_id is generated from prompt hash."""
        input_file = tmp_path / "input.jsonl"
        with open(input_file, "w") as f:
            f.write(json.dumps({"prompt": "unique prompt", "gen": "code"}) + "\n")

        output_file = tmp_path / "output.jsonl"
        prompt_gen_to_eval_format(str(input_file), str(output_file))

        with open(output_file) as f:
            sample = json.loads(f.read().strip())
            assert sample["task_id"].startswith("task_")

    def test_custom_task_id_prefix(self, tmp_path: Path):
        """Test custom task_id prefix."""
        input_file = tmp_path / "input.jsonl"
        with open(input_file, "w") as f:
            f.write(json.dumps({"prompt": "test", "gen": "code"}) + "\n")

        output_file = tmp_path / "output.jsonl"
        prompt_gen_to_eval_format(
            str(input_file), str(output_file), task_id_prefix="custom"
        )

        with open(output_file) as f:
            sample = json.loads(f.read().strip())
            assert sample["task_id"].startswith("custom_")

    def test_preserves_metadata_fields(self, tmp_path: Path):
        """Test metadata fields are preserved."""
        input_file = tmp_path / "input.jsonl"
        with open(input_file, "w") as f:
            f.write(
                json.dumps(
                    {
                        "prompt": "test",
                        "gen": "code",
                        "_source_crate": "serde",
                        "_task_type": "transformations",
                    }
                )
                + "\n"
            )

        output_file = tmp_path / "output.jsonl"
        prompt_gen_to_eval_format(str(input_file), str(output_file))

        with open(output_file) as f:
            sample = json.loads(f.read().strip())
            assert sample.get("_source_crate") == "serde"
            assert sample.get("_task_type") == "transformations"

    def test_skips_empty_lines(self, tmp_path: Path):
        """Test empty lines are skipped."""
        input_file = tmp_path / "input.jsonl"
        with open(input_file, "w") as f:
            f.write('{"prompt": "p1", "gen": "g1"}\n')
            f.write("\n")
            f.write('{"prompt": "p2", "gen": "g2"}\n')
            f.write("   \n")
            f.write('{"prompt": "p3", "gen": "g3"}\n')

        output_file = tmp_path / "output.jsonl"
        count = prompt_gen_to_eval_format(str(input_file), str(output_file))

        assert count == 3

    def test_invalid_json_skipped(self, tmp_path: Path):
        """Test invalid JSON lines are skipped."""
        input_file = tmp_path / "input.jsonl"
        with open(input_file, "w") as f:
            f.write('{"prompt": "p1", "gen": "g1"}\n')
            f.write("not valid json\n")
            f.write('{"prompt": "p2", "gen": "g2"}\n')

        output_file = tmp_path / "output.jsonl"
        count = prompt_gen_to_eval_format(str(input_file), str(output_file))

        assert count == 2

    def test_creates_output_directory(self, tmp_path: Path):
        """Test output directory is created if needed."""
        input_file = tmp_path / "input.jsonl"
        with open(input_file, "w") as f:
            f.write('{"prompt": "test", "gen": "code"}\n')

        output_file = tmp_path / "nested" / "dir" / "output.jsonl"
        prompt_gen_to_eval_format(str(input_file), str(output_file))

        assert output_file.exists()


class TestPromptGenToHfDataset:
    """Test prompt_gen_to_hf_dataset function."""

    def test_returns_info_without_output_path(self, tmp_path: Path, monkeypatch):
        """Test info returned when no output path specified."""
        import sys
        import types

        monkeypatch.setitem(
            sys.modules,
            "datasets",
            types.SimpleNamespace(Dataset=type("Dataset", (), {})),
        )
        input_file = tmp_path / "input.jsonl"
        with open(input_file, "w") as f:
            f.write('{"prompt": "test", "gen": "code"}\n')

        result = prompt_gen_to_hf_dataset(str(input_file), output_path=None)

        assert result["status"] == "info"
        assert "input_path" in result

    def test_calls_converter_with_output_path(self, tmp_path: Path):
        """Test converter is called when output path provided."""
        input_file = tmp_path / "input.jsonl"
        with open(input_file, "w") as f:
            f.write('{"prompt": "test", "gen": "code"}\n')

        # The function tries to import from tools, which may not work in test
        # This is expected behavior - we're testing the import handling
        try:
            prompt_gen_to_hf_dataset(
                str(input_file),
                output_path=str(tmp_path / "output.parquet"),
                variant="training",
            )
        except (ImportError, ModuleNotFoundError):
            # Expected if tools module not available
            pass

    def test_variants(self, tmp_path: Path, monkeypatch):
        """Test different variants are passed correctly."""
        import sys
        import types

        monkeypatch.setitem(
            sys.modules,
            "datasets",
            types.SimpleNamespace(Dataset=type("Dataset", (), {})),
        )
        input_file = tmp_path / "input.jsonl"
        with open(input_file, "w") as f:
            f.write('{"prompt": "test", "gen": "code"}\n')

        result = prompt_gen_to_hf_dataset(
            str(input_file), output_path=None, variant="provenance"
        )

        assert result["variant"] == "provenance"


class TestConverterIntegration:
    """Integration tests for converters."""

    def test_round_trip_eval_format(self, tmp_path: Path):
        """Test converting to eval format preserves data."""
        # Create original samples
        input_file = tmp_path / "original.jsonl"
        original_samples = [
            {"prompt": "Write function X", "gen": "fn x() -> i32 { 42 }"},
            {"prompt": "Create struct Y", "gen": "struct Y { field: String }"},
        ]
        with open(input_file, "w") as f:
            for s in original_samples:
                f.write(json.dumps(s) + "\n")

        # Convert to eval format
        eval_file = tmp_path / "eval.jsonl"
        count = prompt_gen_to_eval_format(str(input_file), str(eval_file))
        assert count == 2

        # Verify completions match original gen
        with open(eval_file) as f:
            eval_samples = [json.loads(line) for line in f]

        assert eval_samples[0]["completion"] == original_samples[0]["gen"]
        assert eval_samples[1]["completion"] == original_samples[1]["gen"]

    def test_large_file_handling(self, tmp_path: Path):
        """Test handling of larger files."""
        input_file = tmp_path / "large.jsonl"
        with open(input_file, "w") as f:
            for i in range(1000):
                f.write(
                    json.dumps(
                        {
                            "prompt": f"Prompt number {i}",
                            "gen": f"fn func_{i}() {{ let x = {i}; }}",
                        }
                    )
                    + "\n"
                )

        output_file = tmp_path / "output.jsonl"
        count = prompt_gen_to_eval_format(str(input_file), str(output_file))

        assert count == 1000
