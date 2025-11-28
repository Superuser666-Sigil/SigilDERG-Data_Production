"""
Integration tests for SigilDERG ecosystem.

Tests format conversions and integration points between:
- sigil-pipeline
- sigilderg-finetuner
- human-eval-rust

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.2.0
"""

import json
import tempfile
from pathlib import Path

import pytest


def test_prompt_gen_to_eval_format():
    """Test conversion from pipeline format to evaluation format."""
    from sigil_pipeline.converters import prompt_gen_to_eval_format

    # Create test JSONL with pipeline format
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as infile:
        samples = [
            {"prompt": "Write a function", "gen": "pub fn test() {}"},
            {
                "prompt": "Write another",
                "gen": "pub fn test2() {}",
                "task_id": "custom_id",
            },
        ]
        for sample in samples:
            infile.write(json.dumps(sample) + "\n")
        infile_path = infile.name

    # Convert to evaluation format
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False
    ) as outfile:
        outfile_path = outfile.name

    try:
        count = prompt_gen_to_eval_format(
            jsonl_path=infile_path,
            output_path=outfile_path,
            task_id_prefix="test_task",
        )

        assert count == 2

        # Verify output format
        with open(outfile_path, "r") as f:
            lines = f.readlines()
            assert len(lines) == 2

            sample1 = json.loads(lines[0])
            assert "task_id" in sample1
            assert "completion" in sample1
            assert sample1["completion"] == "pub fn test() {}"

            sample2 = json.loads(lines[1])
            assert sample2["task_id"] == "custom_id"
            assert sample2["completion"] == "pub fn test2() {}"
    finally:
        Path(infile_path).unlink(missing_ok=True)
        Path(outfile_path).unlink(missing_ok=True)


def test_jsonl_loader_format():
    """Test that JSONL loader can read pipeline format."""
    try:
        from rust_qlora.dataset_utils.jsonl_loader import load_prompt_gen_jsonl
    except ImportError:
        pytest.skip("sigilderg-finetuner not available")

    # Create test JSONL
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        samples = [
            {"prompt": "Write a function", "gen": "pub fn test() {}"},
        ]
        for sample in samples:
            f.write(json.dumps(sample) + "\n")
        jsonl_path = f.name

    try:
        # Mock tokenizer (minimal interface)
        class MockTokenizer:
            def apply_chat_template(
                self, messages, tokenize=False, add_generation_prompt=False
            ):
                return f"{messages[0]['content']}\n\n{messages[1]['content']}"

        tokenizer = MockTokenizer()

        # Load samples
        samples = list(
            load_prompt_gen_jsonl(
                jsonl_path=jsonl_path,
                tokenizer=tokenizer,
                apply_chat_template=False,
            )
        )

        assert len(samples) == 1
        assert "text" in samples[0]
        assert "pub fn test() {}" in samples[0]["text"]
    finally:
        Path(jsonl_path).unlink(missing_ok=True)


def test_format_compatibility():
    """Test that pipeline format is compatible with finetuner expectations."""
    # Pipeline format
    pipeline_sample = {
        "prompt": "Write a Rust function",
        "gen": "pub fn example() -> i32 { 42 }",
        "split": "train",
    }

    # Should be convertible to finetuner format
    finetuner_text = f"{pipeline_sample['prompt']}\n\n{pipeline_sample['gen']}"
    assert "Write a Rust function" in finetuner_text
    assert "pub fn example() -> i32 { 42 }" in finetuner_text

    # Should be convertible to evaluation format
    eval_sample = {
        "task_id": "test_123",
        "completion": pipeline_sample["gen"],
    }
    assert eval_sample["completion"] == pipeline_sample["gen"]


@pytest.mark.skip(reason="Requires actual finetuner installation")
def test_finetuner_jsonl_loading():
    """Test that finetuner can load pipeline JSONL files."""
    # This would require actual finetuner installation
    # Skip for now, but structure is here for future testing
    pass


@pytest.mark.skip(reason="Requires actual human-eval-rust installation")
def test_humaneval_integration():
    """Test human-eval-rust integration with finetuner."""
    # This would require actual human-eval-rust installation
    # Skip for now, but structure is here for future testing
    pass
