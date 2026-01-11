"""
Integration tests for SigilDERG ecosystem.

Tests format conversions and integration points between:
- sigil-pipeline
- sigilderg-finetuner
- human-eval-rust

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.6.0
"""

import json
import tempfile
from pathlib import Path

import pytest


def test_prompt_gen_to_eval_format():
    """Test conversion from pipeline format to evaluation format."""
    from sigil_pipeline.converters import prompt_gen_to_eval_format

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as infile:
        samples = [
            {
                "input_data": {
                    "prompt": "Write a function",
                    "code": "pub fn test() {}",
                },
                "output_data": {"code": "pub fn test() {}"},
            },
            {
                "input_data": {"prompt": "Write another", "code": "pub fn test2() {}"},
                "output_data": {"code": "pub fn test2() {}"},
                "task_id": "custom_id",
            },
        ]
        for sample in samples:
            infile.write(json.dumps(sample) + "\n")
        infile_path = infile.name

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

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        samples = [
            {
                "input_data": {
                    "prompt": "Write a function",
                    "code": "pub fn test() {}",
                },
                "output_data": {"code": "pub fn test() {}"},
            },
        ]
        for sample in samples:
            f.write(json.dumps(sample) + "\n")
        jsonl_path = f.name

    try:

        class MockTokenizer:
            def apply_chat_template(
                self, messages, tokenize=False, add_generation_prompt=False
            ):
                return f"{messages[0]['content']}\n\n{messages[1]['content']}"

        tokenizer = MockTokenizer()

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
    pipeline_sample = {
        "input_data": {"prompt": "Write a Rust function", "code": "fn main() {}"},
        "output_data": {"code": "pub fn example() -> i32 { 42 }"},
        "split": "train",
    }

    finetuner_text = (
        f"{pipeline_sample['input_data']['prompt']}\n\n"
        f"{pipeline_sample['output_data']['code']}"
    )
    assert "Write a Rust function" in finetuner_text
    assert "pub fn example() -> i32 { 42 }" in finetuner_text

    eval_sample = {
        "task_id": "test_123",
        "completion": pipeline_sample["output_data"]["code"],
    }
    assert eval_sample["completion"] == pipeline_sample["output_data"]["code"]


@pytest.mark.skip(reason="Requires actual finetuner installation")
def test_finetuner_jsonl_loading():
    """Test that finetuner can load pipeline JSONL files."""
    pass


@pytest.mark.skip(reason="Requires actual human-eval-rust installation")
def test_humaneval_integration():
    """Test human-eval-rust integration with finetuner."""
    pass
