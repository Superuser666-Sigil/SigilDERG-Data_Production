"""
Prompt template module for diverse prompt generation.

Provides template randomization with seeded RNG for reproducible prompt diversity.
Combines multiple detected patterns into rich, natural language prompts.

Supports runtime-agnostic async prompts to avoid biasing models toward any
specific async runtime (Tokio, async-std, smol, Embassy, etc.).

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.4.0
"""

import logging
import random
import re
from typing import Any

logger = logging.getLogger(__name__)

# Async runtime detection patterns
# Used to detect which runtime the code is using (if any)
ASYNC_RUNTIME_PATTERNS: dict[str, list[str]] = {
    "tokio": [
        r"use\s+tokio\b",
        r"tokio::",
        r"#\[tokio::main\]",
        r"#\[tokio::test\]",
    ],
    "async-std": [
        r"use\s+async_std\b",
        r"async_std::",
        r"#\[async_std::main\]",
        r"#\[async_std::test\]",
    ],
    "smol": [
        r"use\s+smol\b",
        r"smol::",
        r"smol::block_on",
    ],
    "embassy": [
        r"use\s+embassy\b",
        r"embassy::",
        r"embassy_executor",
        r"#\[embassy_executor::main\]",
    ],
    "futures": [
        r"use\s+futures\b",
        r"futures::",
        r"futures_util::",
    ],
}

# Runtime-specific phrase templates
# NOTE: For Phase-2 dataset generation, we ALWAYS use "generic" phrases to avoid
# biasing models toward any specific runtime. The runtime-specific entries are
# retained for:
#   1. Future use cases where runtime-specific prompts might be desired
#   2. Analysis/tooling that wants to generate runtime-aware documentation
#   3. Potential A/B testing of runtime-specific vs generic prompts
# See ADR-007 and build_async_prompt() for the runtime-agnostic design decision.
RUNTIME_PHRASES: dict[str, list[str]] = {
    "tokio": [
        "Using Tokio",
        "With the Tokio runtime",
        "Leveraging Tokio's async runtime",
    ],
    "async-std": [
        "Using async-std",
        "With the async-std runtime",
        "Leveraging async-std",
    ],
    "smol": [
        "Using smol",
        "With the smol runtime",
        "Leveraging smol's executor",
    ],
    "embassy": [
        "Using Embassy",
        "With Embassy's embedded runtime",
        "For embedded async with Embassy",
    ],
    "generic": [
        "Using async Rust",
        "With Rust's async/await",
        "Using asynchronous Rust",
        "Leveraging Rust's async capabilities",
    ],
}

# Template phrase variations for lexical diversity
ACTION_VERBS = ["Write", "Implement", "Create", "Build", "Design", "Develop"]
FUNCTION_PHRASES = [
    "a Rust function",
    "a function in Rust",
    "Rust code for a function",
]
STRUCT_PHRASES = [
    "a Rust struct",
    "a struct in Rust",
    "a Rust data structure",
]
ASYNC_PHRASES = [
    "an async function",
    "an asynchronous function",
    "async Rust code",
]
ERROR_PHRASES = [
    "with proper error handling",
    "that handles errors gracefully",
    "with Result-based error handling",
    "using idiomatic error handling",
]
SERDE_PHRASES = [
    "with Serde serialization",
    "that can be serialized/deserialized",
    "with JSON serialization support",
    "with Serde derives",
]
ITERATOR_PHRASES = [
    "using iterator methods",
    "with functional iterator chains",
    "using Rust's iterator API",
]
IO_PHRASES = [
    "that performs file I/O",
    "for file operations",
    "that reads/writes files",
]
NETWORK_PHRASES = [
    "for HTTP requests",
    "that makes network requests",
    "for networking operations",
]
CONCURRENCY_PHRASES = [
    "with thread-safe shared state",
    "using concurrency primitives",
    "with Arc/Mutex synchronization",
]

# Pattern to phrase mapping
PATTERN_PHRASES: dict[str, list[str]] = {
    "has_async": ASYNC_PHRASES,
    "has_error_handling": ERROR_PHRASES,
    "has_serde": SERDE_PHRASES,
    "has_iterators": ITERATOR_PHRASES,
    "has_io": IO_PHRASES,
    "has_networking": NETWORK_PHRASES,
    "has_concurrency": CONCURRENCY_PHRASES,
}

# Global RNG instance (set via initialize_prompt_rng)
# THREAD-SAFETY NOTE: This global RNG assumes single-threaded access.
# The pipeline uses asyncio with a semaphore (cooperative multitasking),
# so this is safe. If you ever move to ThreadPoolExecutor or multi-threaded
# sample building, you'll need either:
#   - A threading.Lock around rng.choice calls, or
#   - Per-thread RNG via contextvars or threading.local()
_prompt_rng: random.Random | None = None


def initialize_prompt_rng(seed: int | None = None) -> int:
    """
    Initialize the prompt RNG with an optional seed.

    IMPORTANT: Call this once at pipeline startup with an explicit seed
    from config (e.g., cfg.prompt_seed) for reproducibility. The seed
    should be logged and stored in metrics.json for audit purposes.

    Args:
        seed: RNG seed for reproducibility. If None, generates a random seed.

    Returns:
        The seed that was used (for logging/metadata).

    Example:
        seed_used = initialize_prompt_rng(cfg.prompt_seed)
        logger.info("Initialized prompt RNG", extra={"seed": seed_used})
    """
    global _prompt_rng

    if seed is None:
        # Generate a random seed and record it
        seed = random.randint(0, 2**32 - 1)

    _prompt_rng = random.Random(seed)
    logger.info("Prompt RNG initialized", extra={"seed": seed})
    return seed


def get_prompt_rng() -> random.Random:
    """
    Get the prompt RNG instance.

    Returns:
        The initialized Random instance, or creates one if not initialized.
    """
    global _prompt_rng

    if _prompt_rng is None:
        initialize_prompt_rng()

    return _prompt_rng  # type: ignore[return-value]


def select_random(choices: list[str], enable_randomization: bool = True) -> str:
    """
    Select a random item from choices using the prompt RNG.

    Args:
        choices: List of choices
        enable_randomization: If False, always returns first choice

    Returns:
        Selected choice
    """
    if not choices:
        return ""

    if not enable_randomization:
        return choices[0]

    rng = get_prompt_rng()
    return rng.choice(choices)


def detect_async_runtime(code: str) -> str | None:
    """
    Detect which async runtime is used in the code.

    Examines imports and macros to determine if the code uses a specific
    async runtime (Tokio, async-std, smol, Embassy) or is runtime-agnostic.

    Args:
        code: The Rust source code to analyze

    Returns:
        Runtime name ("tokio", "async-std", "smol", "embassy", "futures")
        or None if no specific runtime detected
    """
    if not code:
        return None

    for runtime, patterns in ASYNC_RUNTIME_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, code):
                logger.debug("Detected async runtime", extra={"runtime": runtime})
                return runtime

    return None


def get_runtime_phrase(
    runtime: str | None,
    enable_randomization: bool = True,
) -> str:
    """
    Get an appropriate phrase for the detected async runtime.

    For Phase-2 dataset generation, this should ALWAYS be called with
    runtime=None to enforce runtime-agnostic phrasing and avoid biasing
    models toward any specific async runtime. See build_async_prompt().

    The runtime-specific phrases are retained for future use cases
    (analysis tooling, documentation generation, A/B testing).

    Args:
        runtime: Detected runtime name, or None for generic (recommended)
        enable_randomization: Enable phrase randomization

    Returns:
        Runtime-specific or generic async phrase from RUNTIME_PHRASES
    """
    if runtime and runtime in RUNTIME_PHRASES:
        phrases = RUNTIME_PHRASES[runtime]
    else:
        phrases = RUNTIME_PHRASES["generic"]

    return select_random(phrases, enable_randomization)


def build_combined_prompt(
    fn_name: str | None,
    params_str: str | None,
    return_type: str | None,
    patterns: dict[str, Any],
    doc_desc: str | None = None,
    struct_name: str | None = None,
    struct_fields: str | None = None,
    enable_randomization: bool = True,
) -> str:
    """
    Build a prompt that combines multiple detected patterns.

    Args:
        fn_name: Function name if available
        params_str: Formatted parameters string
        return_type: Return type string
        patterns: Detected code patterns dict
        doc_desc: Documentation description if available
        struct_name: Struct name if available
        struct_fields: Formatted struct fields string
        enable_randomization: Enable template randomization

    Returns:
        Combined natural language prompt
    """
    # Collect active pattern phrases (max 3 to avoid overly long prompts)
    active_phrases = []
    for pattern_key, phrases in PATTERN_PHRASES.items():
        if patterns.get(pattern_key):
            phrase = select_random(phrases, enable_randomization)
            active_phrases.append(phrase)
            if len(active_phrases) >= 3:
                break

    # Select action verb
    action = select_random(ACTION_VERBS, enable_randomization)

    # Build the prompt based on what we have
    if fn_name:
        # Function-based prompt
        fn_phrase = select_random(FUNCTION_PHRASES, enable_randomization)

        # Base prompt with function signature
        if return_type:
            base = (
                f"{action} {fn_phrase} `{fn_name}({params_str or ''}) -> {return_type}`"
            )
        else:
            base = f"{action} {fn_phrase} `{fn_name}({params_str or ''})`"

        # Add pattern qualifiers
        if active_phrases:
            qualifiers = " ".join(active_phrases[:2])  # Max 2 qualifiers
            prompt = f"{base} {qualifiers}"
        else:
            prompt = base

        # Add doc description if available
        if doc_desc:
            prompt = f"{prompt}. {doc_desc}"
        else:
            prompt = f"{prompt}."

    elif struct_name:
        # Struct-based prompt
        struct_phrase = select_random(STRUCT_PHRASES, enable_randomization)

        if struct_fields:
            base = (
                f"{action} {struct_phrase} `{struct_name}` with fields: {struct_fields}"
            )
        else:
            base = f"{action} {struct_phrase} `{struct_name}`"

        # Add Serde if detected
        if patterns.get("has_serde"):
            serde_phrase = select_random(SERDE_PHRASES, enable_randomization)
            prompt = f"{base} {serde_phrase}."
        else:
            prompt = f"{base}."

    else:
        # Fallback: pattern-only prompt
        if active_phrases:
            qualifiers = ", ".join(active_phrases[:2])
            prompt = f"{action} Rust code {qualifiers}."
        else:
            prompt = f"{action} a Rust code snippet."

    return prompt


def build_async_prompt(
    fn_name: str | None,
    patterns: dict[str, Any],
    enable_randomization: bool = True,
    code: str | None = None,
) -> tuple[str, str | None]:
    """
    Build a prompt specifically for async code.

    IMPORTANT: Always uses runtime-agnostic phrasing to avoid biasing models
    toward any specific async runtime (Tokio, async-std, smol, Embassy).
    The detected runtime is returned separately as metadata for logging.

    Args:
        fn_name: Function name if available
        patterns: Detected code patterns
        enable_randomization: Enable template randomization
        code: Optional source code for runtime detection (for metadata only)

    Returns:
        Tuple of (prompt, detected_runtime):
        - prompt: Async-focused prompt with generic runtime phrasing
        - detected_runtime: The actual runtime detected in code (for metadata),
          or None if no specific runtime was detected
    """
    action = select_random(ACTION_VERBS, enable_randomization)
    async_phrase = select_random(ASYNC_PHRASES, enable_randomization)

    # Detect runtime from code for metadata purposes only
    # We intentionally DO NOT use runtime-specific phrasing to avoid bias
    detected_runtime = detect_async_runtime(code) if code else None
    if detected_runtime:
        logger.debug(
            "Detected runtime but using generic phrasing",
            extra={"detected_runtime": detected_runtime},
        )

    # Always use generic async phrasing to avoid runtime bias
    runtime_phrase = get_runtime_phrase(None, enable_randomization)

    additional_qualifiers = []
    if patterns.get("has_error_handling"):
        additional_qualifiers.append(select_random(ERROR_PHRASES, enable_randomization))
    if patterns.get("has_networking"):
        additional_qualifiers.append(
            select_random(NETWORK_PHRASES, enable_randomization)
        )
    if patterns.get("has_io"):
        additional_qualifiers.append(select_random(IO_PHRASES, enable_randomization))

    # Build base prompt with generic runtime phrase
    if fn_name:
        base = f"{runtime_phrase}, {action.lower()} {async_phrase} `{fn_name}`"
    else:
        base = f"{runtime_phrase}, {action.lower()} {async_phrase}"

    if additional_qualifiers:
        qualifiers = " ".join(additional_qualifiers[:2])
        prompt = f"{base} {qualifiers}."
    else:
        prompt = f"{base} that handles asynchronous operations."

    return prompt, detected_runtime


def build_serde_prompt(
    struct_name: str | None,
    fields: list[tuple[str, str]] | None,
    patterns: dict[str, Any],
    enable_randomization: bool = True,
) -> str:
    """
    Build a prompt specifically for Serde serialization.

    Args:
        struct_name: Struct name
        fields: List of (field_name, field_type) tuples
        patterns: Detected code patterns
        enable_randomization: Enable template randomization

    Returns:
        Serde-focused prompt
    """
    action = select_random(ACTION_VERBS, enable_randomization)
    struct_phrase = select_random(STRUCT_PHRASES, enable_randomization)
    serde_phrase = select_random(SERDE_PHRASES, enable_randomization)

    if struct_name:
        if fields:
            fields_str = ", ".join(f"{name}: {ftype}" for name, ftype in fields[:5])
            return (
                f"{action} {struct_phrase} `{struct_name}` with {fields_str}, "
                f"{serde_phrase}."
            )
        return f"{action} {struct_phrase} `{struct_name}` {serde_phrase}."

    return f"{action} {struct_phrase} {serde_phrase}."


def build_error_handling_prompt(
    fn_name: str | None,
    patterns: dict[str, Any],
    enable_randomization: bool = True,
) -> str:
    """
    Build a prompt focused on error handling.

    Args:
        fn_name: Function name if available
        patterns: Detected code patterns (used to add context like IO/networking)
        enable_randomization: Enable template randomization

    Returns:
        Error handling-focused prompt
    """
    action = select_random(ACTION_VERBS, enable_randomization)
    fn_phrase = select_random(FUNCTION_PHRASES, enable_randomization)
    error_phrase = select_random(ERROR_PHRASES, enable_randomization)

    # Add context from patterns if available
    context_phrase = ""
    if patterns.get("has_io"):
        context_phrase = " that performs file I/O"
    elif patterns.get("has_networking"):
        context_phrase = " that makes network requests"
    elif patterns.get("has_async"):
        context_phrase = " that handles async operations"

    if fn_name:
        return f"{action} {fn_phrase} `{fn_name}`{context_phrase} {error_phrase}."

    return f"{action} {fn_phrase}{context_phrase} {error_phrase}."
