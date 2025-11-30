"""
Tests for sigil_pipeline.dataset_splitter module.

Tests dataset splitting by source (crate/file) for train/val splits.
"""

import json
from pathlib import Path

import pytest

from sigil_pipeline.dataset_splitter import (
    _remove_metadata,
    split_by_source,
    split_merged_dataset,
)


class TestRemoveMetadata:
    """Test _remove_metadata helper function."""

    def test_removes_underscore_keys(self):
        """Test that keys starting with underscore are removed."""
        sample = {
            "prompt": "test",
            "completion": "test",
            "_source_crate": "serde",
            "_internal": "data",
        }
        result = _remove_metadata(sample)
        assert "prompt" in result
        assert "completion" in result
        assert "_source_crate" not in result
        assert "_internal" not in result

    def test_preserves_regular_keys(self):
        """Test that regular keys are preserved."""
        sample = {
            "prompt": "test prompt",
            "completion": "test completion",
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
        # Create input file with samples from multiple sources
        input_file = tmp_path / "input.jsonl"
        samples = [
            {"prompt": "p1", "_source_crate": "crate_a"},
            {"prompt": "p2", "_source_crate": "crate_a"},
            {"prompt": "p3", "_source_crate": "crate_b"},
            {"prompt": "p4", "_source_crate": "crate_b"},
            {"prompt": "p5", "_source_crate": "crate_c"},
            {"prompt": "p6", "_source_crate": "crate_c"},
            {"prompt": "p7", "_source_crate": "crate_d"},
            {"prompt": "p8", "_source_crate": "crate_d"},
            {"prompt": "p9", "_source_crate": "crate_e"},
            {"prompt": "p10", "_source_crate": "crate_e"},
        ]
        with open(input_file, "w") as f:
            for s in samples:
                f.write(json.dumps(s) + "\n")

        train_path = str(tmp_path / "train.jsonl")
        val_path = str(tmp_path / "val.jsonl")

        train_count, val_count = split_by_source(
            str(input_file), train_path, val_path, val_ratio=0.2
        )

        # Should have split by source, not sample
        assert train_count + val_count == 10
        assert train_count > 0
        assert val_count > 0

        # Verify files exist
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
        samples = [
            {"prompt": "p1", "_source_crate": "only_crate"},
            {"prompt": "p2", "_source_crate": "only_crate"},
        ]
        with open(input_file, "w") as f:
            for s in samples:
                f.write(json.dumps(s) + "\n")

        train_path = str(tmp_path / "train.jsonl")
        val_path = str(tmp_path / "val.jsonl")

        train_count, val_count = split_by_source(str(input_file), train_path, val_path)

        # Single source should go to train
        assert train_count == 2
        assert val_count == 0

    def test_samples_without_source(self, tmp_path: Path):
        """Test samples without source key go to train."""
        input_file = tmp_path / "input.jsonl"
        samples = [
            {"prompt": "p1", "_source_crate": "crate_a"},
            {"prompt": "p2", "_source_crate": "crate_b"},
            {"prompt": "p3"},  # No source
            {"prompt": "p4"},  # No source
        ]
        with open(input_file, "w") as f:
            for s in samples:
                f.write(json.dumps(s) + "\n")

        train_path = str(tmp_path / "train.jsonl")
        val_path = str(tmp_path / "val.jsonl")

        train_count, val_count = split_by_source(
            str(input_file), train_path, val_path, val_ratio=0.5
        )

        # Samples without source should be in train
        assert train_count + val_count == 4

    def test_custom_source_key(self, tmp_path: Path):
        """Test using custom source key."""
        input_file = tmp_path / "input.jsonl"
        samples = [
            {"prompt": "p1", "custom_source": "src_a"},
            {"prompt": "p2", "custom_source": "src_a"},
            {"prompt": "p3", "custom_source": "src_b"},
            {"prompt": "p4", "custom_source": "src_b"},
        ]
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
            {"prompt": "p1", "_source_crate": "crate_a", "_internal": "data"},
            {"prompt": "p2", "_source_crate": "crate_b", "_metadata": "info"},
        ]
        with open(input_file, "w") as f:
            for s in samples:
                f.write(json.dumps(s) + "\n")

        train_path = str(tmp_path / "train.jsonl")
        val_path = str(tmp_path / "val.jsonl")

        split_by_source(str(input_file), train_path, val_path, val_ratio=0.5)

        # Check output files don't contain metadata
        with open(train_path) as f:
            for line in f:
                sample = json.loads(line)
                assert "_source_crate" not in sample
                assert "_internal" not in sample
                assert "_metadata" not in sample
                assert "split" in sample  # Split field should be added

    def test_split_field_added(self, tmp_path: Path):
        """Test that split field is added to samples."""
        input_file = tmp_path / "input.jsonl"
        samples = [
            {"prompt": "p1", "_source_crate": "crate_a"},
            {"prompt": "p2", "_source_crate": "crate_b"},
        ]
        with open(input_file, "w") as f:
            for s in samples:
                f.write(json.dumps(s) + "\n")

        train_path = str(tmp_path / "train.jsonl")
        val_path = str(tmp_path / "val.jsonl")

        split_by_source(str(input_file), train_path, val_path, val_ratio=0.5)

        # Verify train samples have split="train"
        with open(train_path) as f:
            for line in f:
                sample = json.loads(line)
                assert sample.get("split") == "train"

        # Verify val samples have split="val"
        with open(val_path) as f:
            for line in f:
                sample = json.loads(line)
                assert sample.get("split") == "val"

    def test_empty_lines_skipped(self, tmp_path: Path):
        """Test that empty lines in input are skipped."""
        input_file = tmp_path / "input.jsonl"
        with open(input_file, "w") as f:
            f.write('{"prompt": "p1", "_source_crate": "a"}\n')
            f.write("\n")  # Empty line
            f.write('{"prompt": "p2", "_source_crate": "b"}\n')
            f.write("   \n")  # Whitespace line
            f.write('{"prompt": "p3", "_source_crate": "c"}\n')

        train_path = str(tmp_path / "train.jsonl")
        val_path = str(tmp_path / "val.jsonl")

        train_count, val_count = split_by_source(str(input_file), train_path, val_path)

        # Should only count valid samples
        assert train_count + val_count == 3

    def test_invalid_json_skipped(self, tmp_path: Path):
        """Test that invalid JSON lines are skipped."""
        input_file = tmp_path / "input.jsonl"
        with open(input_file, "w") as f:
            f.write('{"prompt": "p1", "_source_crate": "a"}\n')
            f.write("not valid json\n")
            f.write('{"prompt": "p2", "_source_crate": "b"}\n')

        train_path = str(tmp_path / "train.jsonl")
        val_path = str(tmp_path / "val.jsonl")

        train_count, val_count = split_by_source(str(input_file), train_path, val_path)

        # Should only count valid samples
        assert train_count + val_count == 2

    def test_creates_parent_directories(self, tmp_path: Path):
        """Test that parent directories are created for output files."""
        input_file = tmp_path / "input.jsonl"
        with open(input_file, "w") as f:
            f.write('{"prompt": "p1", "_source_crate": "a"}\n')

        train_path = str(tmp_path / "nested" / "dir" / "train.jsonl")
        val_path = str(tmp_path / "another" / "nested" / "val.jsonl")

        split_by_source(str(input_file), train_path, val_path)

        assert Path(train_path).parent.exists()
        assert Path(val_path).parent.exists()


class TestSplitMergedDataset:
    """Test split_merged_dataset function."""

    def test_basic_merged_split(self, tmp_path: Path):
        """Test splitting merged Phase-1/Phase-2 dataset."""
        merged_file = tmp_path / "merged.jsonl"
        samples = [
            # Phase-1 samples (no _source_crate)
            {"prompt": "p1", "task_type": "doc"},
            {"prompt": "p2", "task_type": "doc"},
            # Phase-2 samples
            {"prompt": "p3", "_source_crate": "crate_a"},
            {"prompt": "p4", "_source_crate": "crate_a"},
            {"prompt": "p5", "_source_crate": "crate_b"},
        ]
        with open(merged_file, "w") as f:
            for s in samples:
                f.write(json.dumps(s) + "\n")

        train_path = str(tmp_path / "train.jsonl")
        val_path = str(tmp_path / "val.jsonl")

        train_count, val_count = split_merged_dataset(
            str(merged_file), train_path, val_path, val_ratio=0.3
        )

        assert train_count + val_count == 5
        assert train_count > 0

    def test_nonexistent_merged_file(self, tmp_path: Path):
        """Test with nonexistent merged file."""
        train_count, val_count = split_merged_dataset(
            str(tmp_path / "nonexistent.jsonl"),
            str(tmp_path / "train.jsonl"),
            str(tmp_path / "val.jsonl"),
        )
        assert train_count == 0
        assert val_count == 0

    def test_phase1_grouped_together(self, tmp_path: Path):
        """Test that Phase-1 samples are grouped together."""
        merged_file = tmp_path / "merged.jsonl"
        samples = [
            # All Phase-1 samples (should be grouped under "phase1")
            {"prompt": "p1", "task_type": "doc"},
            {"prompt": "p2", "task_type": "sig"},
            {"prompt": "p3", "task_type": "example"},
        ]
        with open(merged_file, "w") as f:
            for s in samples:
                f.write(json.dumps(s) + "\n")

        train_path = str(tmp_path / "train.jsonl")
        val_path = str(tmp_path / "val.jsonl")

        train_count, val_count = split_merged_dataset(
            str(merged_file), train_path, val_path
        )

        # All Phase-1 samples should be in one group
        # Since only 1 source, may go to either train or val
        assert train_count + val_count == 3

    def test_metadata_removed(self, tmp_path: Path):
        """Test that metadata is removed from merged output."""
        merged_file = tmp_path / "merged.jsonl"
        samples = [
            {"prompt": "p1", "_source_crate": "a", "_internal": "data"},
            {"prompt": "p2", "_source_crate": "b"},
        ]
        with open(merged_file, "w") as f:
            for s in samples:
                f.write(json.dumps(s) + "\n")

        train_path = str(tmp_path / "train.jsonl")
        val_path = str(tmp_path / "val.jsonl")

        split_merged_dataset(str(merged_file), train_path, val_path)

        # Check no metadata in output
        for path in [train_path, val_path]:
            if Path(path).exists():
                with open(path) as f:
                    for line in f:
                        sample = json.loads(line)
                        assert not any(k.startswith("_") for k in sample.keys())
                        assert "split" in sample

    def test_custom_phase1_source_key(self, tmp_path: Path):
        """Test with custom Phase-1 source key."""
        merged_file = tmp_path / "merged.jsonl"
        samples = [
            {"prompt": "p1"},  # Phase-1
            {"prompt": "p2", "_source_crate": "crate_a"},  # Phase-2
        ]
        with open(merged_file, "w") as f:
            for s in samples:
                f.write(json.dumps(s) + "\n")

        train_path = str(tmp_path / "train.jsonl")
        val_path = str(tmp_path / "val.jsonl")

        # Use custom Phase-1 source key
        train_count, val_count = split_merged_dataset(
            str(merged_file), train_path, val_path, phase1_source_key="custom_phase1"
        )

        assert train_count + val_count == 2

    def test_invalid_json_skipped(self, tmp_path: Path):
        """Test that invalid JSON lines are skipped in merged file."""
        merged_file = tmp_path / "merged.jsonl"
        with open(merged_file, "w") as f:
            f.write('{"prompt": "valid"}\n')
            f.write("invalid json\n")
            f.write('{"prompt": "also valid", "_source_crate": "a"}\n')

        train_path = str(tmp_path / "train.jsonl")
        val_path = str(tmp_path / "val.jsonl")

        train_count, val_count = split_merged_dataset(
            str(merged_file), train_path, val_path
        )

        assert train_count + val_count == 2


class TestSplitIntegration:
    """Integration tests for dataset splitting."""

    def test_full_workflow(self, tmp_path: Path):
        """Test complete workflow: create, split, verify."""
        # Create dataset with multiple sources
        input_file = tmp_path / "dataset.jsonl"
        sources = ["serde", "tokio", "reqwest", "actix", "diesel"]
        samples = []
        for source in sources:
            for i in range(5):  # 5 samples per source
                samples.append(
                    {
                        "prompt": f"Prompt for {source} #{i}",
                        "completion": f"Completion {i}",
                        "_source_crate": source,
                    }
                )

        with open(input_file, "w") as f:
            for s in samples:
                f.write(json.dumps(s) + "\n")

        train_path = str(tmp_path / "train.jsonl")
        val_path = str(tmp_path / "val.jsonl")

        train_count, val_count = split_by_source(
            str(input_file), train_path, val_path, val_ratio=0.2
        )

        # Total should be 25 (5 sources * 5 samples)
        assert train_count + val_count == 25

        # Verify no source overlap between train and val
        train_sources = set()
        val_sources = set()

        with open(train_path) as f:
            for line in f:
                sample = json.loads(line)
                # Source is removed but we can check the prompt
                for src in sources:
                    if src in sample.get("prompt", ""):
                        train_sources.add(src)

        with open(val_path) as f:
            for line in f:
                sample = json.loads(line)
                for src in sources:
                    if src in sample.get("prompt", ""):
                        val_sources.add(src)

        # No overlap between train and val sources
        assert train_sources.isdisjoint(val_sources)

    def test_reproducibility_with_seed(self, tmp_path: Path):
        """Test that splits are different with random shuffle."""
        import random

        input_file = tmp_path / "dataset.jsonl"
        sources = [f"crate_{i}" for i in range(20)]
        samples = []
        for source in sources:
            samples.append({"prompt": "test", "_source_crate": source})

        with open(input_file, "w") as f:
            for s in samples:
                f.write(json.dumps(s) + "\n")

        # Run split twice
        results = []
        for i in range(2):
            random.seed(42 + i)  # Different seeds
            train_path = str(tmp_path / f"train_{i}.jsonl")
            val_path = str(tmp_path / f"val_{i}.jsonl")

            train_count, val_count = split_by_source(
                str(input_file), train_path, val_path, val_ratio=0.2
            )
            results.append((train_count, val_count))

        # Counts should be similar but exact samples may differ
        # (depending on shuffle)
        assert all(t + v == 20 for t, v in results)
