import importlib
import json
import sys
import types
from pathlib import Path


class DummyDataset:
    def __init__(self, rows):
        self.rows = rows
        self.column_names = list(rows[0].keys()) if rows else []

    @classmethod
    def from_generator(cls, generator_fn):
        return cls(list(generator_fn()))

    def to_parquet(self, output_path):
        Path(output_path).write_text("parquet")


def _load_module(monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "datasets",
        types.SimpleNamespace(Dataset=DummyDataset),
    )
    module = importlib.import_module("tools.convert_jsonl_to_parquet")
    return importlib.reload(module)


def test_sample_generator_training_strips_metadata(tmp_path, monkeypatch):
    module = _load_module(monkeypatch)
    input_file = tmp_path / "input.jsonl"
    input_file.write_text(
        json.dumps(
            {
                "prompt": "p",
                "gen": "g",
                "_source_crate": "serde",
                "split": "train",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    samples = list(module._sample_generator([input_file], "training"))
    assert samples == [{"prompt": "p", "gen": "g", "split": "train"}]


def test_sample_generator_provenance_preserves_fields(tmp_path, monkeypatch):
    module = _load_module(monkeypatch)
    input_file = tmp_path / "input.jsonl"
    input_file.write_text(
        json.dumps(
            {
                "prompt": "p",
                "gen": "g",
                "_source_crate": "serde",
                "extra": "x",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    samples = list(module._sample_generator([input_file], "provenance"))
    assert samples[0]["_source_crate"] == "serde"
    assert samples[0]["extra"] == "x"


def test_convert_jsonl_to_parquet_writes_file(tmp_path, monkeypatch):
    module = _load_module(monkeypatch)
    input_file = tmp_path / "input.jsonl"
    output_file = tmp_path / "output.parquet"
    input_file.write_text(
        json.dumps({"prompt": "p", "gen": "g"}) + "\n",
        encoding="utf-8",
    )

    module.convert_jsonl_to_parquet(
        jsonl_path=str(input_file),
        output_path=str(output_file),
        variant="training",
    )

    assert output_file.exists()
