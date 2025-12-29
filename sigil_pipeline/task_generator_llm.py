"""
task_generator_llm
==================

Asynchronous helper functions for generating instruction/response pairs
using a large language model (LLM). The default provider is a local
llama-cpp-python model when available, with optional fallbacks to
OpenAI, Gemini, or Claude.

Provider selection:
- SIGIL_LLM_PROVIDER=auto (default): try llama_cpp -> openai -> gemini -> claude
- SIGIL_LLM_PROVIDER=llama_cpp|openai|gemini|claude: force a provider

Local llama-cpp configuration:
- LLAMA_CPP_MODEL_PATH or SIGIL_LLM_MODEL_PATH: required model path
- LLAMA_CPP_N_CTX: context length
- LLAMA_CPP_N_GPU_LAYERS: GPU layers
- LLAMA_CPP_CHAT_FORMAT: chat format name
- LLAMA_CPP_N_THREADS: CPU threads
- LLAMA_CPP_N_BATCH: prompt batch size
- LLAMA_CPP_MAX_TOKENS or SIGIL_LLM_MAX_TOKENS: cap generation length

Cloud configuration:
- OPENAI_API_KEY / OPENAI_MODEL
- GEMINI_API_KEY or GOOGLE_API_KEY / GEMINI_MODEL
- ANTHROPIC_API_KEY / ANTHROPIC_MODEL
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from . import ast_patterns, output_validator, prompt_templates

logger = logging.getLogger(__name__)

_LLAMA = None
_LLAMA_LOCK = threading.Lock()
_DEFAULT_LLAMA_CPP_MODEL_PATH = (
    "/home/dave/models/deepskeek-coder-v2-lite/"
    "deepseek-coder-v2-lite-instruct-q4_k_m.gguf"
)

def _read_int_env(name: str) -> Optional[int]:
    value = os.getenv(name)
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        logger.warning(f"Invalid integer for {name}: {value!r}")
        return None


def _normalize_provider(name: str) -> str:
    return name.strip().lower().replace("-", "_")


def _provider_chain() -> list[str]:
    provider = os.getenv("SIGIL_LLM_PROVIDER", "auto")
    provider = _normalize_provider(provider)
    if provider in ("", "auto", "default"):
        return ["llama_cpp", "openai", "gemini", "claude"]
    return [provider]


def _get_llama():
    global _LLAMA
    if _LLAMA is not None:
        return _LLAMA

    model_path = os.getenv("LLAMA_CPP_MODEL_PATH") or os.getenv("SIGIL_LLM_MODEL_PATH")
    if not model_path:
        if Path(_DEFAULT_LLAMA_CPP_MODEL_PATH).is_file():
            model_path = _DEFAULT_LLAMA_CPP_MODEL_PATH
        else:
            return None

    try:
        from llama_cpp import Llama
    except ImportError:
        return None

    kwargs: dict[str, Any] = {}
    n_ctx = _read_int_env("LLAMA_CPP_N_CTX")
    if n_ctx is not None:
        kwargs["n_ctx"] = n_ctx
    n_gpu_layers = _read_int_env("LLAMA_CPP_N_GPU_LAYERS")
    if n_gpu_layers is not None:
        kwargs["n_gpu_layers"] = n_gpu_layers
    n_threads = _read_int_env("LLAMA_CPP_N_THREADS")
    if n_threads is not None:
        kwargs["n_threads"] = n_threads
    n_batch = _read_int_env("LLAMA_CPP_N_BATCH")
    if n_batch is not None:
        kwargs["n_batch"] = n_batch
    chat_format = os.getenv("LLAMA_CPP_CHAT_FORMAT")
    if chat_format:
        kwargs["chat_format"] = chat_format

    _LLAMA = Llama(model_path=model_path, **kwargs)
    return _LLAMA


async def _call_llama_cpp(
    system_prompt: str, user_prompt: str, *, temperature: float
) -> Optional[str]:
    llama = _get_llama()
    if llama is None:
        return None

    def _run() -> Optional[str]:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        call_kwargs: dict[str, Any] = {"temperature": temperature}
        max_tokens = _read_int_env("LLAMA_CPP_MAX_TOKENS") or _read_int_env(
            "SIGIL_LLM_MAX_TOKENS"
        )
        if max_tokens is not None:
            call_kwargs["max_tokens"] = max_tokens
        try:
            with _LLAMA_LOCK:
                response = llama.create_chat_completion(
                    messages=messages, **call_kwargs
                )
        except Exception:
            return None
        if not response or "choices" not in response:
            return None
        choice = response["choices"][0]
        message = choice.get("message") or {}
        content = message.get("content") if isinstance(message, dict) else None
        if not content and "text" in choice:
            content = choice.get("text")
        return content.strip() if content else None

    return await asyncio.to_thread(_run)


async def _call_openai(
    system_prompt: str, user_prompt: str, *, temperature: float
) -> Optional[str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        import openai
    except ImportError:
        return None

    openai.api_key = api_key
    model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")

    try:
        response = await openai.ChatCompletion.acreate(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
        )
    except Exception:
        return None

    if not response or not response.choices:
        return None
    content = response.choices[0].message.get("content")
    return content.strip() if content else None


async def _call_gemini(
    system_prompt: str, user_prompt: str, *, temperature: float
) -> Optional[str]:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None
    try:
        import google.generativeai as genai
    except ImportError:
        return None

    model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    prompt = f"{system_prompt}\n\n{user_prompt}".strip()

    def _run() -> Optional[str]:
        try:
            response = model.generate_content(
                prompt, generation_config={"temperature": temperature}
            )
        except Exception:
            return None
        text = getattr(response, "text", None)
        return text.strip() if text else None

    return await asyncio.to_thread(_run)


async def _call_claude(
    system_prompt: str, user_prompt: str, *, temperature: float
) -> Optional[str]:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic
    except ImportError:
        return None

    model = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
    max_tokens = int(os.getenv("ANTHROPIC_MAX_TOKENS", "2048"))
    client = anthropic.Anthropic(api_key=api_key)

    def _run() -> Optional[str]:
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except Exception:
            return None
        content_blocks = getattr(response, "content", None) or []
        parts = []
        for block in content_blocks:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        text = "".join(parts)
        return text.strip() if text else None

    return await asyncio.to_thread(_run)


async def _call_llm(
    system_prompt: str, user_prompt: str, *, temperature: float = 0.2
) -> Optional[str]:
    """Invoke the underlying LLM with provider fallback."""
    for provider in _provider_chain():
        if provider == "llama_cpp":
            result = await _call_llama_cpp(
                system_prompt, user_prompt, temperature=temperature
            )
        elif provider == "openai":
            result = await _call_openai(
                system_prompt, user_prompt, temperature=temperature
            )
        elif provider == "gemini":
            result = await _call_gemini(
                system_prompt, user_prompt, temperature=temperature
            )
        elif provider == "claude":
            result = await _call_claude(
                system_prompt, user_prompt, temperature=temperature
            )
        else:
            logger.warning(f"Unknown LLM provider: {provider}")
            result = None

        if result:
            return result
    return None


def _select_instruction(options: list[str]) -> str:
    return prompt_templates.select_random(
        options, enable_randomization=prompt_templates.is_prompt_randomization_enabled()
    )


def _extract_function_name(code: str) -> str | None:
    signature = ast_patterns.extract_function_signature(code)
    return signature.name if signature else None


def _style_hints(code: str, *, max_hints: int = 2) -> str:
    patterns = ast_patterns.detect_code_patterns_ast(code or "")
    hints: list[str] = []
    if patterns.get("has_async"):
        hints.append("Use async/await patterns where appropriate.")
    if patterns.get("has_error_handling"):
        hints.append("Handle errors with Result types where appropriate.")
    if patterns.get("has_serde"):
        hints.append("Use Serde for serialization/deserialization where it fits.")
    if patterns.get("has_io"):
        hints.append("Handle I/O failures carefully.")
    if patterns.get("has_iterators"):
        hints.append("Prefer iterator-based processing when it fits.")

    if not hints:
        return ""

    if prompt_templates.is_prompt_randomization_enabled():
        rng = prompt_templates.get_prompt_rng()
        rng.shuffle(hints)
        return " ".join(hints[:max_hints])
    return hints[0]


def _explanation_subject(code: str) -> str:
    chunk_type = output_validator.classify_chunk_type(code) or "code"
    name = _extract_function_name(code)
    if chunk_type == "function":
        return f"Rust function `{name}`" if name else "Rust function"
    if chunk_type == "struct":
        struct_name = ast_patterns.extract_struct_name(code)
        return f"Rust struct `{struct_name}`" if struct_name else "Rust struct"
    if chunk_type == "enum":
        return "Rust enum"
    if chunk_type == "trait":
        return "Rust trait"
    if chunk_type == "type":
        return "Rust type alias"
    if chunk_type == "impl_block":
        return "Rust impl block"
    if chunk_type == "module":
        return "Rust module"
    return "Rust code"


async def generate_refactoring_task(
    code: str, context: str = ""
) -> Optional[Dict[str, Any]]:
    """Generate a transformation task for the given Rust ``code``."""
    fn_name = _extract_function_name(code)
    name_phrase = f" `{fn_name}`" if fn_name else ""
    instruction = _select_instruction(
        [
            (
                "Refactor this Rust function to be more idiomatic while preserving behavior and "
                "public API. Keep names, signatures, generics, where-clauses, and visibility the "
                "same. Return only the refactored function."
            ),
            (
                "Make this Rust function cleaner and more idiomatic without changing what it does or "
                "its public surface. Keep the signature and item shape unchanged. Output just the "
                "function."
            ),
            (
                "Improve the style of the Rust function below while preserving behavior. Keep all "
                "names, generics, where-clauses, and visibility unchanged. Return only the updated "
                "function."
            ),
            (
                "Rewrite the Rust function"
                f"{name_phrase} for idiomatic style while keeping the public API identical. Output "
                "only the refactored function."
            ),
        ]
    )
    instruction = (
        f"{instruction} Use any provided context only for reference and do not repeat it. "
        "Output a single function item only; no extra items, imports, or commentary."
    )
    user_prompt = code
    if context:
        user_prompt += "\n\n// Context:\n" + context

    completion = await _call_llm(
        "You are an expert Rust programmer.", instruction + "\n\n" + user_prompt
    )
    if not completion:
        return None

    return {
        "prompt": instruction + "\n\n" + code,
        "gen": completion,
        "_task_type": "transformations",
    }


async def generate_bug_fixing_task(
    code: str, context: str = ""
) -> Optional[Dict[str, Any]]:
    """Generate an error-fixing task for the given Rust ``code``."""
    fn_name = _extract_function_name(code)
    name_phrase = f" `{fn_name}`" if fn_name else ""
    instruction = _select_instruction(
        [
            (
                "Fix the bug or compile error in the Rust function below. Preserve the public API "
                "and item shape; keep names, signatures, generics, where-clauses, and visibility "
                "unchanged. Return only the corrected function."
            ),
            (
                "Repair the Rust function below so it compiles and behaves correctly. Keep the "
                "signature and public surface unchanged. Output just the fixed function."
            ),
            (
                "This Rust function is incorrect or fails to compile. Make it correct without changing "
                "its public API. Return only the corrected function."
            ),
            (
                "Correct the Rust function"
                f"{name_phrase} while keeping the signature identical. Output just the fixed function."
            ),
        ]
    )
    instruction = (
        f"{instruction} Use any provided context only for reference and do not repeat it. "
        "Output a single function item only; no extra items, imports, or commentary."
    )
    user_prompt = code
    if context:
        user_prompt += "\n\n// Context:\n" + context

    completion = await _call_llm(
        "You are a Rust compiler assistant.", instruction + "\n\n" + user_prompt
    )
    if not completion:
        return None

    return {
        "prompt": instruction + "\n\n" + code,
        "gen": completion,
        "_task_type": "error_fixing",
    }


async def generate_documentation_task(
    code: str, context: str = ""
) -> Optional[Dict[str, Any]]:
    """Generate an explanation task for the given Rust ``code``."""
    subject = _explanation_subject(code)
    instruction = _select_instruction(
        [
            f"In plain English, explain what this {subject} does. Keep it brief and in paragraph form.",
            f"Describe the purpose and behavior of this {subject} in a short, plain-language paragraph.",
            f"Give a concise explanation of this {subject} in plain text. Avoid lists or markdown.",
            f"Summarize what this {subject} does in a few plain sentences.",
            f"Explain this {subject} to a Rust developer in a short paragraph.",
            f"Briefly explain the intent and behavior of this {subject} in plain language.",
            f"Provide a short, plain-English summary of this {subject}.",
            f"Write a compact explanation of this {subject} using plain sentences only.",
            f"Describe what this {subject} does in a brief paragraph of plain text.",
            f"Explain the role of this {subject} in clear, plain language.",
        ]
    )
    user_prompt = code
    if context:
        user_prompt += "\n\n// Context:\n" + context

    completion = await _call_llm(
        "You are an expert technical writer who explains Rust code clearly.",
        instruction + "\n\n" + user_prompt,
    )
    if not completion:
        return None

    return {
        "prompt": instruction + "\n\n" + code,
        "gen": completion,
        "_task_type": "explanations",
    }


async def generate_code_generation_task(
    code: str, context: str = ""
) -> Optional[Dict[str, Any]]:
    """Generate a code completion task for the given Rust ``code``."""
    fn_name = _extract_function_name(code)
    name_phrase = f" `{fn_name}`" if fn_name else ""
    base = _select_instruction(
        [
            (
                "Write the missing body for the Rust function below. Keep the signature unchanged and "
                "return only the completed function."
            ),
            (
                "Complete the body of this Rust function using idiomatic Rust. Keep the signature exactly "
                "the same and output just the function."
            ),
            (
                "Fill in the function body below and preserve the signature. Return only the completed "
                "function."
            ),
            (
                "Implement the missing body for this Rust function. Keep the signature unchanged and "
                "output only the function."
            ),
            (
                "Complete the Rust function"
                f"{name_phrase} by filling in the missing body. Return only the completed function with "
                "the same signature."
            ),
        ]
    )
    hints = _style_hints(code)
    instruction = f"{base} {hints}".strip()
    instruction = (
        f"{instruction} Use any provided context only for reference and do not repeat it. "
        "Output a single function item only; no extra items, imports, or commentary."
    )
    user_prompt = code
    if context:
        user_prompt += "\n\n// Context:\n" + context

    completion = await _call_llm(
        "You are an expert Rust developer who writes idiomatic code.",
        instruction + "\n\n" + user_prompt,
    )
    if not completion:
        return None

    return {
        "prompt": instruction + "\n\n" + code,
        "gen": completion,
        "_task_type": "code_generation",
    }


__all__ = [
    "generate_refactoring_task",
    "generate_bug_fixing_task",
    "generate_documentation_task",
    "generate_code_generation_task",
]
