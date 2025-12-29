import pytest

from sigil_pipeline import dataset_builder
from sigil_pipeline.format_validator import FormatValidator


ALLOWED_TASK_TYPES = {
    "code_generation",
    "transformations",
    "error_fixing",
    "explanations",
}


@pytest.mark.asyncio
async def test_builder_outputs_schema_fields(monkeypatch):
    async def fake_code_gen(code, context=""):
        return {"prompt": "Write code", "gen": "fn main() {}", "_task_type": "code_generation"}

    monkeypatch.setattr(dataset_builder, "generate_code_generation_task", fake_code_gen)

    samples = await dataset_builder.build_dataset_entries_async(
        [{"code": "fn main() {}"}],
        task_type_mix={"code_generation": 1.0},
        validate_format=True,
        concurrency=1,
    )

    assert len(samples) == 1
    sample = samples[0]
    assert "prompt" in sample
    assert "gen" in sample
    assert sample.get("_task_type") in ALLOWED_TASK_TYPES


def test_validator_rejects_missing_fields():
    validator = FormatValidator()
    is_valid, errors = validator.validate_sample({"prompt": "Write code"})
    assert not is_valid
    assert errors
