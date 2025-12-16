import json
from sigil_pipeline.exporter import write_jsonl
from pathlib import Path

def test_write_jsonl_legacy_and_structured(tmp_path):
    samples = [
        {"prompt": "Write code", "gen": "fn main() {}"},
        {
            "crate_name": "foo",
            "input_data": {"title": "T"},
            "output_data": {"code": "fn t() {}"},
            "task_category": "code_generation",
            "test": "",
        },
    ]

    out = tmp_path / "out.jsonl"
    count = write_jsonl(iter(samples), str(out))
    assert count == 2

    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2

    first = json.loads(lines[0])
    # legacy converted to structured
    assert "input_data" in first and "output_data" in first
    second = json.loads(lines[1])
    assert second.get("crate_name") == "foo"
