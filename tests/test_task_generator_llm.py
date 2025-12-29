import pytest

from sigil_pipeline import task_generator_llm as llm


def test_provider_chain_auto(monkeypatch):
    monkeypatch.delenv("SIGIL_LLM_PROVIDER", raising=False)
    chain = llm._provider_chain()
    assert chain[0] == "llama_cpp"
    assert "openai" in chain
    assert "gemini" in chain
    assert "claude" in chain


def test_provider_chain_forced(monkeypatch):
    monkeypatch.setenv("SIGIL_LLM_PROVIDER", "claude")
    chain = llm._provider_chain()
    assert chain == ["claude"]


def test_normalize_provider():
    assert llm._normalize_provider("LLaMA-CPP") == "llama_cpp"
    assert llm._normalize_provider(" openai ") == "openai"


@pytest.mark.asyncio
async def test_call_llm_fallback(monkeypatch):
    calls = []

    async def fake_llama(*args, **kwargs):
        calls.append("llama_cpp")
        return None

    async def fake_openai(*args, **kwargs):
        calls.append("openai")
        return "ok"

    monkeypatch.setattr(llm, "_provider_chain", lambda: ["llama_cpp", "openai"])
    monkeypatch.setattr(llm, "_call_llama_cpp", fake_llama)
    monkeypatch.setattr(llm, "_call_openai", fake_openai)

    result = await llm._call_llm("system", "user")
    assert result == "ok"
    assert calls == ["llama_cpp", "openai"]
