import pytest

from sigil_pipeline import dataset_builder


@pytest.mark.asyncio
async def test_build_dataset_entries_async_code_generation(monkeypatch):
    async def fake_code_gen(code, context=""):
        return {
            "prompt": f"Complete: {code}",
            "gen": f"{code} // done",
            "_task_type": "code_generation",
        }

    monkeypatch.setattr(
        dataset_builder, "generate_code_generation_task", fake_code_gen
    )

    file_infos = [{"code": "fn main() {}", "path": "src/lib.rs"}]
    samples = await dataset_builder.build_dataset_entries_async(
        file_infos,
        task_type_mix={"code_generation": 1.0},
        validate_format=True,
        concurrency=1,
    )

    assert len(samples) == 1
    assert samples[0]["_task_type"] == "code_generation"


@pytest.mark.asyncio
async def test_build_dataset_entries_async_normalizes_task_mix(monkeypatch):
    async def fake_refactor(code, context=""):
        return {
            "prompt": f"Refactor: {code}",
            "gen": f"{code} // refactored",
            "_task_type": "transformations",
        }

    monkeypatch.setattr(dataset_builder, "generate_refactoring_task", fake_refactor)

    file_infos = [{"code": "fn add(a: i32, b: i32) -> i32 { a + b }"}]
    samples = await dataset_builder.build_dataset_entries_async(
        file_infos,
        task_type_mix={"refactoring": 1.0},
        validate_format=True,
        concurrency=1,
    )

    assert len(samples) == 1
    assert samples[0]["_task_type"] == "transformations"


@pytest.mark.asyncio
async def test_build_dataset_entries_filters_invalid_samples(monkeypatch):
    async def fake_code_gen(code, context=""):
        return {"prompt": "", "gen": "ok", "_task_type": "code_generation"}

    monkeypatch.setattr(
        dataset_builder, "generate_code_generation_task", fake_code_gen
    )

    file_infos = [{"code": "fn main() {}"}]
    samples = await dataset_builder.build_dataset_entries_async(
        file_infos,
        task_type_mix={"code_generation": 1.0},
        validate_format=True,
        concurrency=1,
    )

    assert samples == []


@pytest.mark.asyncio
async def test_build_dataset_entries_respects_max_limits(monkeypatch):
    async def fake_code_gen(code, context=""):
        return {
            "prompt": "line1\nline2\nline3",
            "gen": "ok",
            "_task_type": "code_generation",
        }

    monkeypatch.setattr(
        dataset_builder, "generate_code_generation_task", fake_code_gen
    )

    file_infos = [{"code": "fn main() {}"}]
    samples = await dataset_builder.build_dataset_entries_async(
        file_infos,
        task_type_mix={"code_generation": 1.0},
        max_sft_lines=1,
        validate_format=True,
        concurrency=1,
    )

    assert samples == []


@pytest.mark.asyncio
async def test_build_dataset_entries_sync_wrapper_from_event_loop(monkeypatch):
    async def fake_code_gen(code, context=""):
        return {
            "prompt": f"Complete: {code}",
            "gen": f"{code} // done",
            "_task_type": "code_generation",
        }

    monkeypatch.setattr(
        dataset_builder, "generate_code_generation_task", fake_code_gen
    )

    file_infos = [{"code": "fn main() {}"}]
    samples = dataset_builder.build_dataset_entries(
        file_infos,
        task_type_mix={"code_generation": 1.0},
        validate_format=False,
        concurrency=1,
    )

    assert len(samples) == 1
