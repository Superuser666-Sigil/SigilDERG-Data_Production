"""
Tests for sigil_pipeline.dataset_splitter module.

Tests dataset splitting by source (crate/file) for train/val splits.
"""

import json
from pathlib import Path

from sigil_pipeline.dataset_splitter import (
    _remove_metadata,
    split_by_source,
)


def _sample(prompt: str, source: str | None = None) -> dict:
    sample = {
        "input_data": {"prompt": prompt, "code": "fn main() {}"},
        "output_data": {"code": "fn main() {}"},
    }
    if source:
        sample["_source_crate"] = source
    return sample


class TestRemoveMetadata:
    """Test _remove_metadata helper function."""

    def test_removes_underscore_keys(self):
        """Test that keys starting with underscore are removed."""
        sample = {
            "input_data": {"prompt": "test", "code": "fn main() {}"},
            "output_data": {"code": "fn main() {}"},
            "_source_crate": "serde",
            "_internal": "data",
        }
        result = _remove_metadata(sample)
        assert "input_data" in result
        assert "output_data" in result
        assert "_source_crate" not in result
        assert "_internal" not in result

    def test_preserves_regular_keys(self):
        """Test that regular keys are preserved."""
        sample = {
            "input_data": {"prompt": "test", "code": "fn main() {}"},
            "output_data": {"code": "fn main() {}"},
            "task_type": "documentation",
        }
        result = _remove_metadata(sample)
        assert result == sample

    def test_empty_dict(self):
        """Test with empty dictionary."""
        result = _remove_metadata({})
        assert result == {}

    def test_only_metadata(self):
        """Test dict with only metadata keys."""
        sample = {"_private": "data", "_internal": "value"}
        result = _remove_metadata(sample)
        assert result == {}


class TestSplitBySource:
    """Test split_by_source function."""

    def test_basic_split(self, tmp_path: Path):
        """Test basic train/val split."""
        input_file = tmp_path / "input.jsonl"
        samples = [
            _sample("p1", "crate_a"),
            _sample("p2", "crate_a"),
            _sample("p3", "crate_b"),
            _sample("p4", "crate_b"),
            _sample("p5", "crate_c"),
            _sample("p6", "crate_c"),
            _sample("p7", "crate_d"),
            _sample("p8", "crate_d"),
            _sample("p9", "crate_e"),
            _sample("p10", "crate_e"),
        ]
        with open(input_file, "w") as f:
            for s in samples:
                f.write(json.dumps(s) + "\n")

        train_path = str(tmp_path / "train.jsonl")
        val_path = str(tmp_path / "val.jsonl")

        train_count, val_count = split_by_source(
            str(input_file), train_path, val_path, val_ratio=0.2
        )

        assert train_count + val_count == 10
        assert train_count > 0
        assert val_count > 0
        assert Path(train_path).exists()
        assert Path(val_path).exists()

    def test_nonexistent_input_file(self, tmp_path: Path):
        """Test with nonexistent input file."""
        train_count, val_count = split_by_source(
            str(tmp_path / "nonexistent.jsonl"),
            str(tmp_path / "train.jsonl"),
            str(tmp_path / "val.jsonl"),
        )
        assert train_count == 0
        assert val_count == 0

    def test_single_source(self, tmp_path: Path):
        """Test with only one source (all goes to train)."""
        input_file = tmp_path / "input.jsonl"
        samples = [_sample("p1", "only_crate"), _sample("p2", "only_crate")]
        with open(input_file, "w") as f:
            for s in samples:
                f.write(json.dumps(s) + "\n")

        train_path = str(tmp_path / "train.jsonl")
        val_path = str(tmp_path / "val.jsonl")

        train_count, val_count = split_by_source(str(input_file), train_path, val_path)

        assert train_count == 2
        assert val_count == 0

    def test_samples_without_source(self, tmp_path: Path):
        """Test samples without source key go to train."""
        input_file = tmp_path / "input.jsonl"
        samples = [
            _sample("p1", "crate_a"),
            _sample("p2", "crate_b"),
            _sample("p3"),
            _sample("p4"),
        ]
        with open(input_file, "w") as f:
            for s in samples:
                f.write(json.dumps(s) + "\n")

        train_path = str(tmp_path / "train.jsonl")
        val_path = str(tmp_path / "val.jsonl")

        train_count, val_count = split_by_source(
            str(input_file), train_path, val_path, val_ratio=0.5
        )

        assert train_count + val_count == 4

    def test_custom_source_key(self, tmp_path: Path):
        """Test using custom source key."""
        input_file = tmp_path / "input.jsonl"
        samples = [
            _sample("p1"),
            _sample("p2"),
            _sample("p3"),
            _sample("p4"),
        ]
        for sample, source in zip(samples, ["src_a", "src_a", "src_b", "src_b"]):
            sample["custom_source"] = source

        with open(input_file, "w") as f:
            for s in samples:
                f.write(json.dumps(s) + "\n")

        train_path = str(tmp_path / "train.jsonl")
        val_path = str(tmp_path / "val.jsonl")

        train_count, val_count = split_by_source(
            str(input_file),
            train_path,
            val_path,
            source_key="custom_source",
            val_ratio=0.5,
        )

        assert train_count + val_count == 4

    def test_metadata_removed_from_output(self, tmp_path: Path):
        """Test that metadata keys are removed from output."""
        input_file = tmp_path / "input.jsonl"
        samples = [
            _sample("p1", "crate_a"),
            _sample("p2", "crate_b"),
        ]
        samples[0]["_internal"] = "data"
        samples[1]["_metadata"] = "info"

        with open(input_file, "w") as f:
            for s in samples:
                f.write(json.dumps(s) + "\n")

        train_path = str(tmp_path / "train.jsonl")
        val_path = str(tmp_path / "val.jsonl")

        split_by_source(str(input_file), train_path, val_path, val_ratio=0.5)

        with open(train_path) as f:
            for line in f:
                sample = json.loads(line)
                assert "_source_crate" not in sample
                assert "_internal" not in sample
                assert "_metadata" not in sample
                assert "split" in sample

    def test_split_field_added(self, tmp_path: Path):
        """Test that split field is added to samples."""
        input_file = tmp_path / "input.jsonl"
        samples = [_sample("p1", "crate_a"), _sample("p2", "crate_b")]
        with open(input_file, "w") as f:
            for s in samples:
                f.write(json.dumps(s) + "\n")

        train_path = str(tmp_path / "train.jsonl")
        val_path = str(tmp_path / "val.jsonl")

        split_by_source(str(input_file), train_path, val_path, val_ratio=0.5)

        with open(train_path) as f:
            for line in f:
                sample = json.loads(line)
                assert sample.get("split") == "train"
