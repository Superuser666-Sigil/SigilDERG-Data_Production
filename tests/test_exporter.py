"""
Tests for sigil_pipeline.exporter module.

Tests JSONL export, dataset loading, and merging functionality.
"""

import json
from unittest.mock import patch

from sigil_pipeline.exporter import (
    load_phase1_dataset,
    merge_jsonl_files,
    merge_phase1_phase2,
    write_jsonl,
    write_metrics,
)


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

        # Verify content
        with open(output_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            assert len(lines) == 2
            sample1 = json.loads(lines[0])
            assert sample1["prompt"] == "Write code"

    def test_streaming_large_dataset(self, tmp_path):
        """Test streaming write for large dataset."""
        output_path = tmp_path / "large.jsonl"

        def sample_generator():
            for i in range(1000):
                yield {"prompt": f"Prompt {i}", "gen": f"code {i}"}

        count = write_jsonl(sample_generator(), str(output_path))
        assert count == 1000
        assert output_path.exists()

    def test_invalid_sample_handling(self, tmp_path):
        """Test handling of invalid samples."""
        output_path = tmp_path / "output.jsonl"
        samples = iter(
            [
                {"prompt": "Valid", "gen": "code"},
                {"invalid": "sample"},  # Missing required fields
                {"prompt": "Valid2", "gen": "code2"},
            ]
        )

        count = write_jsonl(samples, str(output_path))
        assert count == 2  # Only valid samples written

    def test_error_handling_permissions(self, tmp_path):
        """Test error handling for permission issues."""
        # Create a directory to simulate permission error
        output_path = tmp_path / "nonexistent" / "output.jsonl"
        samples = iter([{"prompt": "test", "gen": "code"}])

        # Should create parent directory
        count = write_jsonl(samples, str(output_path))
        assert count == 1


class TestLoadPhase1Dataset:
    """Test load_phase1_dataset function."""

    def test_load_local_jsonl_file(self, sample_jsonl_file):
        """Test loading Phase 1 dataset from local JSONL file."""
        samples = list(load_phase1_dataset(str(sample_jsonl_file)))
        assert len(samples) == 2
        assert all("prompt" in s and "gen" in s for s in samples)

    def test_load_local_with_max_samples(self, sample_jsonl_file):
        """Test loading with max_samples limit."""
        samples = list(load_phase1_dataset(str(sample_jsonl_file), max_samples=1))
        assert len(samples) == 1

    def test_nonexistent_file(self):
        """Test handling of non-existent file."""
        samples = list(load_phase1_dataset("/nonexistent/file.jsonl"))
        assert len(samples) == 0

    @patch("sigil_pipeline.exporter.load_dataset")
    def test_load_huggingface_dataset(self, mock_load_dataset):
        """Test loading from HuggingFace dataset."""
        mock_dataset = [
            {"prompt": "Write code", "gen": "fn main() {}"},
            {
                "instruction": "Write code",
                "output": "fn main() {}",
            },  # Alternative format
        ]
        mock_load_dataset.return_value = iter(mock_dataset)

        with patch("sigil_pipeline.exporter.HF_DATASETS_AVAILABLE", True):
            samples = list(load_phase1_dataset("test/dataset"))
            assert len(samples) == 2

    def test_invalid_json_handling(self, tmp_path):
        """Test handling of invalid JSON in file."""
        jsonl_file = tmp_path / "invalid.jsonl"
        with open(jsonl_file, "w", encoding="utf-8") as f:
            f.write('{"prompt": "test1", "gen": "code1"}\n')  # Valid
            f.write("invalid json\n")  # Invalid - should be skipped
            f.write('{"prompt": "test2", "gen": "code2"}\n')  # Valid

        samples = list(load_phase1_dataset(str(jsonl_file)))
        # Should have 2 valid samples (invalid line is skipped)
        assert len(samples) >= 1  # At least the valid ones
        assert all("prompt" in s and "gen" in s for s in samples)


class TestMergeJsonlFiles:
    """Test merge_jsonl_files function."""

    def test_basic_merging(self, tmp_path):
        """Test basic file merging."""
        # Create input files
        file1 = tmp_path / "file1.jsonl"
        file2 = tmp_path / "file2.jsonl"
        output_path = tmp_path / "merged.jsonl"

        with open(file1, "w", encoding="utf-8") as f:
            f.write('{"prompt": "test1", "gen": "code1"}\n')

        with open(file2, "w", encoding="utf-8") as f:
            f.write('{"prompt": "test2", "gen": "code2"}\n')

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
                f.write(f'{{"prompt": "test{i}", "gen": "code{i}"}}\n')

        with open(file2, "w", encoding="utf-8") as f:
            for i in range(5, 10):
                f.write(f'{{"prompt": "test{i}", "gen": "code{i}"}}\n')

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
            f.write('{"prompt": "test1", "gen": "code1"}\n')

        with open(file2, "w", encoding="utf-8") as f:
            f.write('{"prompt": "test2", "gen": "code2"}\n')

        count = merge_jsonl_files(
            [str(file1), str(file2)],
            str(output_path),
            shuffle=False,
            weights=[2.0, 1.0],
        )
        # With weight 2.0, file1 samples should be repeated
        assert count >= 2

    def test_merging_nonexistent_file(self, tmp_path):
        """Test handling of non-existent input file."""
        file1 = tmp_path / "file1.jsonl"
        output_path = tmp_path / "merged.jsonl"

        with open(file1, "w", encoding="utf-8") as f:
            f.write('{"prompt": "test", "gen": "code"}\n')

        count = merge_jsonl_files(
            [str(file1), "/nonexistent/file.jsonl"],
            str(output_path),
            shuffle=False,
        )
        assert count == 1  # Only valid file processed


class TestMergePhase1Phase2:
    """Test merge_phase1_phase2 function."""

    def test_basic_phase1_phase2_merging(self, tmp_path):
        """Test basic Phase 1/Phase 2 merging."""
        phase1_file = tmp_path / "phase1.jsonl"
        phase2_file = tmp_path / "phase2.jsonl"
        output_path = tmp_path / "merged.jsonl"

        with open(phase1_file, "w", encoding="utf-8") as f:
            f.write('{"prompt": "phase1", "gen": "code1"}\n')

        with open(phase2_file, "w", encoding="utf-8") as f:
            f.write('{"prompt": "phase2", "gen": "code2"}\n')

        count = merge_phase1_phase2(
            str(phase1_file),
            str(phase2_file),
            str(output_path),
            shuffle=False,
        )
        assert count == 2
        assert output_path.exists()

    def test_merging_with_weighting(self, tmp_path):
        """Test merging with Phase 2 weighting."""
        phase1_file = tmp_path / "phase1.jsonl"
        phase2_file = tmp_path / "phase2.jsonl"
        output_path = tmp_path / "merged.jsonl"

        with open(phase1_file, "w", encoding="utf-8") as f:
            f.write('{"prompt": "phase1", "gen": "code1"}\n')

        with open(phase2_file, "w", encoding="utf-8") as f:
            f.write('{"prompt": "phase2", "gen": "code2"}\n')

        count = merge_phase1_phase2(
            str(phase1_file),
            str(phase2_file),
            str(output_path),
            shuffle=False,
            phase2_weight=2.0,
        )
        # Phase 2 should be weighted (repeated)
        assert count >= 2

    def test_merging_with_shuffle(self, tmp_path):
        """Test merging with shuffle enabled."""
        phase1_file = tmp_path / "phase1.jsonl"
        phase2_file = tmp_path / "phase2.jsonl"
        output_path = tmp_path / "merged.jsonl"

        with open(phase1_file, "w", encoding="utf-8") as f:
            for i in range(5):
                f.write(f'{{"prompt": "p1_{i}", "gen": "code{i}"}}\n')

        with open(phase2_file, "w", encoding="utf-8") as f:
            for i in range(5):
                f.write(f'{{"prompt": "p2_{i}", "gen": "code{i}"}}\n')

        count = merge_phase1_phase2(
            str(phase1_file),
            str(phase2_file),
            str(output_path),
            shuffle=True,
        )
        assert count == 10

    @patch("sigil_pipeline.exporter.load_phase1_dataset")
    def test_merging_with_huggingface_phase1(self, mock_load, tmp_path):
        """Test merging with HuggingFace Phase 1 dataset."""
        mock_load.return_value = iter(
            [
                {"prompt": "hf_prompt", "gen": "hf_code"},
            ]
        )

        phase2_file = tmp_path / "phase2.jsonl"
        output_path = tmp_path / "merged.jsonl"

        with open(phase2_file, "w", encoding="utf-8") as f:
            f.write('{"prompt": "phase2", "gen": "code2"}\n')

        count = merge_phase1_phase2(
            "test/dataset",  # HuggingFace dataset name
            str(phase2_file),
            str(output_path),
            shuffle=False,
        )
        assert count == 2


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
