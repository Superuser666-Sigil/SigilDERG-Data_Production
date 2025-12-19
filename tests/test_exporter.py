"""
Tests for sigil_pipeline.exporter module.

Tests JSONL export and merging functionality.
"""

import json

from sigil_pipeline.exporter import merge_jsonl_files, write_jsonl, write_metrics


class TestWriteJsonl:
    """Test write_jsonl function."""

    def test_basic_jsonl_writing(self, tmp_path):
        """Test basic JSONL file writing."""
        output_path = tmp_path / "output.jsonl"
        samples = iter(
            [
                {"prompt": "Write code", "gen": "fn main() {}"},
                {"prompt": "Write function", "gen": "fn test() {}"},
            ]
        )

        count = write_jsonl(samples, str(output_path))
        assert count == 2
        assert output_path.exists()

        with open(output_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            assert len(lines) == 2
            sample1 = json.loads(lines[0])
            assert sample1["input_data"]["prompt"] == "Write code"

    def test_streaming_large_dataset(self, tmp_path):
        """Test streaming write for large dataset."""
        output_path = tmp_path / "large.jsonl"

        def sample_generator():
            for i in range(1000):
                yield {
                    "input_data": {"prompt": f"Prompt {i}", "code": f"code {i}"},
                    "output_data": {"code": f"code {i}"},
                }

        count = write_jsonl(sample_generator(), str(output_path))
        assert count == 1000
        assert output_path.exists()

    def test_invalid_sample_handling(self, tmp_path):
        """Test handling of invalid samples."""
        output_path = tmp_path / "output.jsonl"
        samples = iter(
            [
                {"prompt": "Valid", "gen": "code"},
                {"invalid": "sample"},
                {"prompt": "Valid2", "gen": "code2"},
            ]
        )

        count = write_jsonl(samples, str(output_path))
        assert count == 2

    def test_error_handling_permissions(self, tmp_path):
        """Test error handling for permission issues."""
        output_path = tmp_path / "nonexistent" / "output.jsonl"
        samples = iter([{"prompt": "test", "gen": "code"}])

        count = write_jsonl(samples, str(output_path))
        assert count == 1


class TestMergeJsonlFiles:
    """Test merge_jsonl_files function."""

    def test_basic_merging(self, tmp_path):
        """Test basic file merging."""
        file1 = tmp_path / "file1.jsonl"
        file2 = tmp_path / "file2.jsonl"
        output_path = tmp_path / "merged.jsonl"

        with open(file1, "w", encoding="utf-8") as f:
            f.write(
                '{"input_data": {"prompt": "test1", "code": "code1"}, "output_data": {"code": "code1"}}\n'
            )

        with open(file2, "w", encoding="utf-8") as f:
            f.write(
                '{"input_data": {"prompt": "test2", "code": "code2"}, "output_data": {"code": "code2"}}\n'
            )

        count = merge_jsonl_files(
            [str(file1), str(file2)], str(output_path), shuffle=False
        )
        assert count == 2
        assert output_path.exists()

    def test_merging_with_shuffle(self, tmp_path):
        """Test merging with shuffle enabled."""
        file1 = tmp_path / "file1.jsonl"
        file2 = tmp_path / "file2.jsonl"
        output_path = tmp_path / "merged.jsonl"

        with open(file1, "w", encoding="utf-8") as f:
            for i in range(5):
                f.write(
                    f'{{"input_data": {{"prompt": "test{i}", "code": "code{i}"}}, "output_data": {{"code": "code{i}"}}}}\n'
                )

        with open(file2, "w", encoding="utf-8") as f:
            for i in range(5, 10):
                f.write(
                    f'{{"input_data": {{"prompt": "test{i}", "code": "code{i}"}}, "output_data": {{"code": "code{i}"}}}}\n'
                )

        count = merge_jsonl_files(
            [str(file1), str(file2)], str(output_path), shuffle=True
        )
        assert count == 10

    def test_merging_with_weights(self, tmp_path):
        """Test merging with weights."""
        file1 = tmp_path / "file1.jsonl"
        file2 = tmp_path / "file2.jsonl"
        output_path = tmp_path / "merged.jsonl"

        with open(file1, "w", encoding="utf-8") as f:
            f.write(
                '{"input_data": {"prompt": "test1", "code": "code1"}, "output_data": {"code": "code1"}}\n'
            )

        with open(file2, "w", encoding="utf-8") as f:
            f.write(
                '{"input_data": {"prompt": "test2", "code": "code2"}, "output_data": {"code": "code2"}}\n'
            )

        count = merge_jsonl_files(
            [str(file1), str(file2)],
            str(output_path),
            shuffle=False,
            weights=[2.0, 1.0],
        )
        assert count >= 2

    def test_merging_nonexistent_file(self, tmp_path):
        """Test handling of non-existent input file."""
        file1 = tmp_path / "file1.jsonl"
        output_path = tmp_path / "merged.jsonl"

        with open(file1, "w", encoding="utf-8") as f:
            f.write(
                '{"input_data": {"prompt": "test", "code": "code"}, "output_data": {"code": "code"}}\n'
            )

        count = merge_jsonl_files(
            [str(file1), "/nonexistent/file.jsonl"],
            str(output_path),
            shuffle=False,
        )
        assert count == 1


class TestWriteMetrics:
    """Test write_metrics function."""

    def test_basic_metrics_writing(self, tmp_path):
        """Test basic metrics file writing."""
        output_path = tmp_path / "metrics.json"
        metrics = {
            "total_samples": 100,
            "crates_processed": 10,
            "crates_skipped": 5,
        }

        write_metrics(metrics, str(output_path))
        assert output_path.exists()

        with open(output_path, "r", encoding="utf-8") as f:
            loaded_metrics = json.load(f)
            assert loaded_metrics["total_samples"] == 100
            assert loaded_metrics["crates_processed"] == 10

    def test_complex_metrics_structure(self, tmp_path):
        """Test writing complex metrics structure."""
        output_path = tmp_path / "metrics.json"
        metrics = {
            "total_samples": 100,
            "filter_breakdown": {
                "edition": 5,
                "clippy": 3,
                "docs": 2,
            },
            "config": {"max_threads": 4},
        }

        write_metrics(metrics, str(output_path))
        assert output_path.exists()

        with open(output_path, "r", encoding="utf-8") as f:
            loaded_metrics = json.load(f)
            assert "filter_breakdown" in loaded_metrics
            assert loaded_metrics["filter_breakdown"]["edition"] == 5
