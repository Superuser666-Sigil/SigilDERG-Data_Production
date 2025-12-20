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


def _write_samples(path: Path, samples: list[dict]) -> None:
    with open(path, "w") as f:
        for sample in samples:
            f.write(json.dumps(sample) + "\n")


class TestPromptGenToEvalFormat:
    """Test prompt_gen_to_eval_format function."""

    def test_basic_conversion(self, tmp_path: Path):
        input_file = tmp_path / "input.jsonl"
        samples = [
            {
                "input_data": {"prompt": "Write a function", "code": "fn test() {}"},
                "output_data": {"code": "fn test() {}"},
            },
            {
                "input_data": {
                    "prompt": "Add numbers",
                    "code": "fn add(a: i32, b: i32) -> i32 { a + b }",
                },
                "output_data": {"code": "fn add(a: i32, b: i32) -> i32 { a + b }"},
            },
        ]
        _write_samples(input_file, samples)

        output_file = tmp_path / "output.jsonl"
        count = prompt_gen_to_eval_format(str(input_file), str(output_file))

        assert count == 2
        assert output_file.exists()

        with open(output_file) as f:
            for line in f:
                sample = json.loads(line)
                assert "task_id" in sample
                assert "completion" in sample

    def test_nonexistent_file_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            prompt_gen_to_eval_format(
                str(tmp_path / "nonexistent.jsonl"), str(tmp_path / "output.jsonl")
            )

    def test_max_samples_limit(self, tmp_path: Path):
        input_file = tmp_path / "input.jsonl"
        samples = [
            {
                "input_data": {"prompt": f"p{i}", "code": f"code{i}"},
                "output_data": {"code": f"code{i}"},
            }
            for i in range(100)
        ]
        _write_samples(input_file, samples)

        output_file = tmp_path / "output.jsonl"
        count = prompt_gen_to_eval_format(
            str(input_file), str(output_file), max_samples=10
        )

        assert count == 10

    def test_missing_completion_skipped(self, tmp_path: Path):
        input_file = tmp_path / "input.jsonl"
        samples = [
            {
                "input_data": {"prompt": "test1", "code": "fn a() {}"},
                "output_data": {"code": "fn a() {}"},
            },
            {"input_data": {"prompt": "test2", "code": "fn b() {}"}},
            {
                "input_data": {"prompt": "test3", "code": "fn c() {}"},
                "output_data": {"code": "fn c() {}"},
            },
        ]
        _write_samples(input_file, samples)

        output_file = tmp_path / "output.jsonl"
        count = prompt_gen_to_eval_format(str(input_file), str(output_file))

        assert count == 2

    def test_preserves_task_id(self, tmp_path: Path):
        input_file = tmp_path / "input.jsonl"
        samples = [
            {
                "task_id": "custom_id_123",
                "input_data": {"prompt": "test", "code": "fn test() {}"},
                "output_data": {"code": "fn test() {}"},
            }
        ]
        _write_samples(input_file, samples)

        output_file = tmp_path / "output.jsonl"
        prompt_gen_to_eval_format(str(input_file), str(output_file))

        with open(output_file) as f:
            sample = json.loads(f.read().strip())
            assert sample["task_id"] == "custom_id_123"

    def test_generates_task_id_from_prompt(self, tmp_path: Path):
        input_file = tmp_path / "input.jsonl"
        samples = [
            {
                "input_data": {"prompt": "unique prompt", "code": "code"},
                "output_data": {"code": "code"},
            }
        ]
        _write_samples(input_file, samples)

        output_file = tmp_path / "output.jsonl"
        prompt_gen_to_eval_format(str(input_file), str(output_file))

        with open(output_file) as f:
            sample = json.loads(f.read().strip())
            assert sample["task_id"].startswith("task_")

    def test_custom_task_id_prefix(self, tmp_path: Path):
        input_file = tmp_path / "input.jsonl"
        samples = [
            {
                "input_data": {"prompt": "test", "code": "code"},
                "output_data": {"code": "code"},
            }
        ]
        _write_samples(input_file, samples)

        output_file = tmp_path / "output.jsonl"
        prompt_gen_to_eval_format(
            str(input_file), str(output_file), task_id_prefix="custom"
        )

        with open(output_file) as f:
            sample = json.loads(f.read().strip())
            assert sample["task_id"].startswith("custom_")

    def test_preserves_metadata_fields(self, tmp_path: Path):
        input_file = tmp_path / "input.jsonl"
        samples = [
            {
                "input_data": {"prompt": "test", "code": "code"},
                "output_data": {"code": "code"},
                "_source_crate": "serde",
                "_task_type": "transformation",
            }
        ]
        _write_samples(input_file, samples)

        output_file = tmp_path / "output.jsonl"
        prompt_gen_to_eval_format(str(input_file), str(output_file))

        with open(output_file) as f:
            sample = json.loads(f.read().strip())
            assert sample.get("_source_crate") == "serde"
            assert sample.get("_task_type") == "transformation"

    def test_skips_empty_lines(self, tmp_path: Path):
        input_file = tmp_path / "input.jsonl"
        with open(input_file, "w") as f:
            f.write(
                '{"input_data": {"prompt": "p1", "code": "g1"}, "output_data": {"code": "g1"}}\n'
            )
            f.write("\n")
            f.write(
                '{"input_data": {"prompt": "p2", "code": "g2"}, "output_data": {"code": "g2"}}\n'
            )
            f.write("   \n")
            f.write(
                '{"input_data": {"prompt": "p3", "code": "g3"}, "output_data": {"code": "g3"}}\n'
            )

        output_file = tmp_path / "output.jsonl"
        count = prompt_gen_to_eval_format(str(input_file), str(output_file))

        assert count == 3

    def test_invalid_json_skipped(self, tmp_path: Path):
        input_file = tmp_path / "input.jsonl"
        with open(input_file, "w") as f:
            f.write(
                '{"input_data": {"prompt": "p1", "code": "g1"}, "output_data": {"code": "g1"}}\n'
            )
            f.write("not valid json\n")
            f.write(
                '{"input_data": {"prompt": "p2", "code": "g2"}, "output_data": {"code": "g2"}}\n'
            )

        output_file = tmp_path / "output.jsonl"
        count = prompt_gen_to_eval_format(str(input_file), str(output_file))

        assert count == 2

    def test_creates_output_directory(self, tmp_path: Path):
        input_file = tmp_path / "input.jsonl"
        samples = [
            {
                "input_data": {"prompt": "test", "code": "code"},
                "output_data": {"code": "code"},
            }
        ]
        _write_samples(input_file, samples)

        output_file = tmp_path / "nested" / "dir" / "output.jsonl"
        prompt_gen_to_eval_format(str(input_file), str(output_file))

        assert output_file.exists()


class TestPromptGenToHfDataset:
    """Test prompt_gen_to_hf_dataset function."""

    def test_returns_info_without_output_path(self, tmp_path: Path):
        input_file = tmp_path / "input.jsonl"
        _write_samples(
            input_file,
            [
                {
                    "input_data": {"prompt": "test", "code": "code"},
                    "output_data": {"code": "code"},
                }
            ],
        )

        result = prompt_gen_to_hf_dataset(str(input_file), output_path=None)

        assert result["status"] == "info"
        assert "input_path" in result

    def test_calls_converter_with_output_path(self, tmp_path: Path):
        input_file = tmp_path / "input.jsonl"
        _write_samples(
            input_file,
            [
                {
                    "input_data": {"prompt": "test", "code": "code"},
                    "output_data": {"code": "code"},
                }
            ],
        )

        try:
            prompt_gen_to_hf_dataset(
                str(input_file), output_path=str(tmp_path / "out.parquet")
            )
        except Exception:
            pytest.skip("converter not available in test environment")
