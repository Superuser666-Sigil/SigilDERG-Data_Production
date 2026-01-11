"""
Prompt template module for JSON-based instruction tuning.

Provides Jinja2-style templates that enforce strict JSON output schemas.
Removes legacy randomization to ensure consistent, high-quality instruction following.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.6.0
"""

import logging

from jinja2 import Template
import random
from typing import Iterable, List

logger = logging.getLogger(__name__)

# Standard System Prompt
SYSTEM_PROMPT = "You are a Rust engineering assistant. Output valid JSON."

# Template for Code Generation
# Input: context, instruction, code_signature
# Output: JSON with 'code' key
CODE_GEN_TEMPLATE = Template(
    """
You are a Rust engineering assistant.
Context:
{{ context }}

Task: {{ instruction }}

Input Code:
{{ code }}

Return a JSON object with keys: ['code'].
""".strip()
)

# Template for Error Fixing
# Input: context, instruction, broken_code
# Output: JSON with 'fixed_code' and 'explanation' keys
ERROR_FIX_TEMPLATE = Template(
    """
You are a Rust engineering assistant.
Context:
{{ context }}

Task: {{ instruction }}

Input Code:
{{ code }}

Return a JSON object with keys: ['fixed_code', 'explanation'].
""".strip()
)

# Template for Explanations
# Input: context, instruction, code
# Output: JSON with 'explanation' key
EXPLANATION_TEMPLATE = Template(
    """
You are a Rust engineering assistant.
Context:
{{ context }}

Task: {{ instruction }}

Input Code:
{{ code }}

Return a JSON object with keys: ['explanation'].
""".strip()
)


def render_code_gen_prompt(context: str, instruction: str, signature: str) -> str:
    """Render the prompt for code generation tasks."""
    return CODE_GEN_TEMPLATE.render(
        context=context, instruction=instruction, code=signature
    )


def render_error_fix_prompt(context: str, instruction: str, broken_code: str) -> str:
    """Render the prompt for error fixing tasks."""
    return ERROR_FIX_TEMPLATE.render(
        context=context, instruction=instruction, code=broken_code
    )


def render_explanation_prompt(context: str, instruction: str, code: str) -> str:
    """Render the prompt for explanation tasks."""
    return EXPLANATION_TEMPLATE.render(
        context=context, instruction=instruction, code=code
    )


# --- Prompt generation utilities used by dataset builder tests ---

# Phrases keyed by runtime type
RUNTIME_PHRASES = {
    "generic": [
        "Use idiomatic async patterns where appropriate.",
        "Prefer clear error handling and concise code.",
        "Write code that is easy to read and maintain.",
    ],
    "tokio": [
        "Use Tokio-compatible async patterns.",
        "Use tokio::spawn or tokio utilities as appropriate.",
    ],
    "async-std": ["Use async-std task utilities."],
    "smol": ["Use smol executor conventions."],
    "embassy": ["Use embassy executor and embedded-friendly patterns."],
    "futures": ["Use futures crate combinators and adapters."],
}


# Module-level RNG for deterministic tests
_PROMPT_RNG: random.Random | None = None
_PROMPT_SEED: int | None = None
_PROMPT_RANDOMIZATION: bool = True


def initialize_prompt_rng(seed: int | None = None) -> int:
    """Initialize (or reinitialize) the prompt RNG. Returns the seed used."""
    global _PROMPT_RNG, _PROMPT_SEED
    if seed is None:
        seed = random.randrange(0, 2 ** 32)
    _PROMPT_RNG = random.Random(seed)
    _PROMPT_SEED = seed
    return seed


def set_prompt_randomization(enabled: bool) -> None:
    """Enable or disable prompt randomization globally."""
    global _PROMPT_RANDOMIZATION
    _PROMPT_RANDOMIZATION = bool(enabled)


def is_prompt_randomization_enabled() -> bool:
    """Return whether prompt randomization is enabled."""
    return _PROMPT_RANDOMIZATION


def get_prompt_seed() -> int | None:
    """Return the current prompt RNG seed if initialized."""
    return _PROMPT_SEED


def get_prompt_rng() -> random.Random:
    """Return the active prompt RNG (or module random as fallback)."""
    return _PROMPT_RNG or random


def select_random(choices: Iterable[str], enable_randomization: bool | None = True) -> str:
    """Select an element from choices respecting the enable_randomization flag."""
    choices = list(choices)
    if not choices:
        return ""
    if enable_randomization is None:
        enable_randomization = _PROMPT_RANDOMIZATION
    if not enable_randomization:
        return choices[0]
    return get_prompt_rng().choice(choices)


def detect_async_runtime(code: str | None) -> str | None:
    """Detect common async runtimes from code heuristics.

    Returns runtime key (e.g., 'tokio') or None.
    """
    if not code:
        return None
    if "tokio::" in code or "#[tokio::main]" in code or "#[tokio::test]" in code:
        return "tokio"
    if "async_std::" in code or "#[async_std::main]" in code:
        return "async-std"
    if "smol::" in code or "smol::block_on" in code:
        return "smol"
    if "embassy::" in code or "#[embassy_executor::main]" in code:
        return "embassy"
    if "futures::" in code:
        return "futures"
    return None


def get_runtime_phrase(runtime: str | None, enable_randomization: bool = True) -> str:
    """Return a runtime phrase for the detected runtime, falling back to generic."""
    key = runtime if runtime in RUNTIME_PHRASES else "generic"
    return select_random(RUNTIME_PHRASES.get(key, RUNTIME_PHRASES["generic"]), enable_randomization)


def build_async_prompt(
    fn_name: str | None = None, patterns: dict | None = None, code: str | None = None
) -> tuple[str, str | None]:
    """Build a short async-focused prompt.

    Per tests, the prompt should use generic phrasing even when runtime is detected.
    Returns (prompt, detected_runtime)
    """
    detected = detect_async_runtime(code) if code is not None else None
    phrase = get_runtime_phrase(None, enable_randomization=True)
    name = fn_name or "function"
    prompt_parts = [f"Implement the async function {name}.", phrase]
    if patterns and patterns.get("has_error_handling"):
        prompt_parts.append("Handle errors gracefully and return Result where appropriate.")
    return " ".join(prompt_parts), detected


def _pattern_phrases_from_patterns(patterns: dict) -> List[str]:
    phrases = []
    if not patterns:
        return phrases
    if patterns.get("has_async"):
        phrases.append("asynchronous operations")
    if patterns.get("has_serde"):
        phrases.append("Serde serialization/deserialization")
    if patterns.get("has_error_handling"):
        phrases.append("error handling with Result types")
    if patterns.get("has_iterators"):
        phrases.append("iterator-based processing")
    if patterns.get("has_io"):
        phrases.append("file I/O")
    return phrases


def build_combined_prompt(
    fn_name: str | None,
    params_str: str | None,
    return_type: str | None,
    patterns: dict | None,
    struct_name: str | None = None,
) -> str:
    """Build a combined prompt describing the function/struct and detected patterns.

    Keeps the prompt reasonably short and deterministic under the seeded RNG.
    """
    name = fn_name or struct_name or "function"
    head = f"Write a Rust implementation for {name}."
    pattern_phrases = _pattern_phrases_from_patterns(patterns or {})
    # Limit to 3 phrases
    pattern_phrases = pattern_phrases[:3]
    tail = " ".join([f"Focus on {p}." for p in pattern_phrases])
    return " ".join([head, tail]).strip()


def build_error_handling_prompt(fn_name: str | None, patterns: dict | None) -> str:
    name = fn_name or "function"
    parts = [f"Write robust error handling for {name}."]
    if patterns and patterns.get("has_io"):
        parts.append("Consider I/O failures and use Result types.")
    if patterns and patterns.get("has_networking"):
        parts.append("Consider network request failures and retries.")
    return " ".join(parts)


def build_serde_prompt(struct_name: str, fields: List[tuple], patterns: dict | None) -> str:
    # Include up to 5 fields
    field_list = fields[:5]
    fields_str = ", ".join([f"{n}: {t}" for n, t in field_list])
    return f"Create Serde (Serialize/Deserialize) implementations for {struct_name} with fields: {fields_str}."
