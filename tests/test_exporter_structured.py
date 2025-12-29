import json

from sigil_pipeline.exporter import write_jsonl


def test_write_jsonl_prompt_gen_only(tmp_path):
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
    assert count == 1

    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1

    first = json.loads(lines[0])
    assert set(first.keys()) == {"prompt", "gen"}
