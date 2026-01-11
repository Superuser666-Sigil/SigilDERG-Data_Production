"""
dataset_builder
=================

This module contains a high‑level builder for constructing instruction/
response pairs from pre‑screened Rust code snippets.  Unlike the legacy
implementation which produced nested ``input_data`` and ``output_data``
dictionaries and a ``task_category`` field, this builder emits samples
conforming to a simplified instruct fine‑tuning format.  Each sample is a
dictionary with two top‑level keys:

``prompt``
    The instruction given to the language model.  It includes a short
    task description followed by the relevant code snippet.  The prompt
    should not contain the answer.

``gen``
    The expected answer from the language model.  For refactoring and
    bug‑fixing tasks this is rewritten Rust code; for documentation tasks
    it is a natural‑language explanation; for code‑generation tasks it is
    the completed function.  Additional metadata keys prefixed with an
    underscore are attached to aid analysis but are removed when writing
    training data.

The builder relies on helper functions from ``task_generator_llm`` to
generate the different task types.  It supports concurrency to improve
throughput and uses weighted random selection to diversify the tasks.
"""

from __future__ import annotations

import asyncio
import json
import random
import threading
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Any,
    AsyncIterable,
    AsyncIterator,
    Dict,
    Iterable,
    List,
    Optional,
    TextIO,
)

from .format_validator import FormatValidator
from . import output_validator
from . import task_generator as deterministic_task_generator
from .task_generator_llm import (
    generate_bug_fixing_task,
    generate_code_generation_task,
    generate_documentation_task,
    generate_fim_task,
    generate_refactoring_task,
)


# Default mixture of task types.  The values represent relative weights.  They
# need not sum to one.  If all values are zero or the dictionary is empty the
# builder will always fall back to ``code_generation``.
DEFAULT_TASK_TYPE_MIX: Dict[str, float] = {
    "code_generation": 0.30,
    "fill_in_middle": 0.25,
    "error_fixing": 0.20,
    "transformations": 0.15,
    "explanations": 0.10,
}

_TASK_TYPE_ALIASES = {
    "refactoring": "transformations",
    "transformations": "transformations",
    "transformation": "transformations",
    "bug_fixing": "error_fixing",
    "bugfixing": "error_fixing",
    "error_fixing": "error_fixing",
    "documentation": "explanations",
    "explanation": "explanations",
    "explanations": "explanations",
    "code_generation": "code_generation",
    "fill_in_middle": "fill_in_middle",
    "fim": "fill_in_middle",
    "infill": "fill_in_middle",
}


@dataclass
class RejectionTracker:
    max_examples: int = 3
    counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    examples: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)
    dump_path: Path | None = None
    _dump_file: TextIO | None = None
    _dump_lock: threading.Lock = field(default_factory=threading.Lock)

    def record(
        self,
        reason: str,
        file_info: Dict[str, Any] | None,
        task_type: str | None = None,
        detail: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        if not reason:
            return
        with self.lock:
            self.counts[reason] += 1
            if self.max_examples <= 0:
                return
            bucket = self.examples.setdefault(reason, [])
            if len(bucket) >= self.max_examples:
                return
            entry = {
                "crate": None,
                "path": None,
                "chunk_type": None,
                "task_type": task_type,
                "detail": detail,
            }
            if file_info:
                entry["crate"] = file_info.get("crate_name") or file_info.get(
                    "_source_crate"
                )
                entry["path"] = file_info.get("path") or file_info.get("_file_path")
                entry["chunk_type"] = file_info.get("chunk_type") or file_info.get(
                    "_chunk_type"
                )
            bucket.append(entry)

        if self.dump_path and payload:
            record = {
                "reason": reason,
                "task_type": task_type,
                "detail": detail,
                "crate": None,
                "path": None,
                "chunk_type": None,
                "start_line": None,
                "end_line": None,
                **payload,
            }
            if file_info:
                record["crate"] = file_info.get("crate_name") or file_info.get(
                    "_source_crate"
                )
                record["path"] = file_info.get("path") or file_info.get("_file_path")
                record["chunk_type"] = file_info.get("chunk_type") or file_info.get(
                    "_chunk_type"
                )
                record["start_line"] = file_info.get("start_line") or file_info.get(
                    "_start_line"
                )
                record["end_line"] = file_info.get("end_line") or file_info.get(
                    "_end_line"
                )
            with self._dump_lock:
                if self._dump_file is None:
                    self.dump_path.parent.mkdir(parents=True, exist_ok=True)
                    self._dump_file = self.dump_path.open("w", encoding="utf-8")
                self._dump_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                self._dump_file.flush()

    def summary(self) -> dict[str, Any]:
        with self.lock:
            return {"counts": dict(self.counts), "examples": dict(self.examples)}

    def close(self) -> None:
        with self._dump_lock:
            if self._dump_file is not None:
                try:
                    self._dump_file.flush()
                    self._dump_file.close()
                finally:
                    self._dump_file = None


def _normalize_task_type(name: str) -> str | None:
    if not name:
        return None
    key = str(name).strip().lower()
    return _TASK_TYPE_ALIASES.get(key)


def _error_fixing_enabled(
    *,
    enable_error_injection: bool,
    error_injection_method: str | None,
    allow_simulated_error_fixing: bool,
) -> bool:
    if not enable_error_injection:
        return False
    method = (error_injection_method or "").strip().lower()
    if method in ("real", "real_compile"):
        return True
    if method in ("both", "simulate", ""):
        return allow_simulated_error_fixing
    return allow_simulated_error_fixing


def _normalize_task_mix(
    task_type_mix: Dict[str, float],
    *,
    enable_error_injection: bool,
    error_injection_method: str | None,
    allow_simulated_error_fixing: bool,
) -> Dict[str, float]:
    normalized: Dict[str, float] = {}
    allow_error_fixing = _error_fixing_enabled(
        enable_error_injection=enable_error_injection,
        error_injection_method=error_injection_method,
        allow_simulated_error_fixing=allow_simulated_error_fixing,
    )
    for key, weight in task_type_mix.items():
        norm = _normalize_task_type(key)
        if not norm:
            continue
        if norm == "error_fixing" and not allow_error_fixing:
            continue
        normalized[norm] = normalized.get(norm, 0.0) + float(weight)
    return normalized


def _select_task_type(
    task_type_mix: Dict[str, float],
    rng: random.Random,
    available: set[str] | None = None,
) -> str:
    """Choose a task type according to the provided weight distribution.

    If ``task_type_mix`` is empty or all weights are non‑positive, returns
    ``"code_generation"``.  The function draws a random number and selects
    the task where the cumulative weight exceeds the draw.
    """
    items = [(k, v) for k, v in task_type_mix.items() if v > 0]
    if available is not None:
        items = [(k, v) for k, v in items if k in available]
    if not items:
        if available:
            return next(iter(available))
        return "code_generation"
    total = sum(v for _, v in items)
    roll = rng.random() * total
    cumulative = 0.0
    for key, weight in items:
        cumulative += weight
        if roll <= cumulative:
            return key
    return items[-1][0]


def _available_task_types(
    file_info: Dict[str, Any],
    *,
    enable_error_injection: bool,
    error_injection_method: str | None,
    allow_simulated_error_fixing: bool,
    allow_explanations: bool,
) -> set[str]:
    chunk_type = file_info.get("chunk_type")
    available: set[str] = set()
    allow_error_fixing = _error_fixing_enabled(
        enable_error_injection=enable_error_injection,
        error_injection_method=error_injection_method,
        allow_simulated_error_fixing=allow_simulated_error_fixing,
    )
    if chunk_type == "function":
        available.add("code_generation")
        available.add("fill_in_middle")
        available.add("transformations")
        if allow_error_fixing:
            available.add("error_fixing")
        if allow_explanations:
            available.add("explanations")
    elif chunk_type in ("impl_block", "module"):
        # impl_blocks and modules can have explanations
        if allow_explanations:
            available.add("explanations")
    elif chunk_type in ("struct", "enum", "trait", "type"):
        if allow_explanations:
            available.add("explanations")
    else:
        if allow_explanations:
            available.add("explanations")
    return available


_EXPLANATION_BULLET_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
_EXPLANATION_JOKE_START_RE = re.compile(r"^\s*(?:what a|wow|haha|lol)\b", re.IGNORECASE)
_EXPLANATION_PREAMBLE_RE = re.compile(
    r"^\s*(?:here\s+(?:is|are)|in\s+summary|summary:)\b", re.IGNORECASE
)
_EXPLANATION_NOTE_RE = re.compile(r"^\s*note\s*[:\-–—]", re.IGNORECASE)
_EXPLANATION_NIGHTLY_RE = re.compile(r"\b(nightly|unstable)\b", re.IGNORECASE)
_STRICT_TODO_RE = re.compile(r"\btodo!\s*(?:\(\s*\))?\b", re.IGNORECASE)
_STRICT_PLACEHOLDER_RE = re.compile(
    r"^\s*//\s*(?:implementation goes here|placeholder\b)",
    re.IGNORECASE | re.MULTILINE,
)
_STRICT_IMPORT_RE = re.compile(
    r"^\s*(?:pub\s+)?use\b|^\s*extern\s+crate\b",
    re.MULTILINE,
)
_PROMPT_NO_IMPORTS_RE = re.compile(r"no extra items,?\s+imports", re.IGNORECASE)


def _forbidden_imports(prompt: str | None, gen: str) -> bool:
    if not isinstance(prompt, str) or not _PROMPT_NO_IMPORTS_RE.search(prompt):
        return False
    if not _STRICT_IMPORT_RE.search(gen):
        return False
    return not _STRICT_IMPORT_RE.search(prompt)


def _count_sentences(text: str) -> int:
    cleaned = re.sub(r"\s+", " ", text.strip())
    if not cleaned:
        return 0
    parts = re.split(r"[.!?]+", cleaned)
    return len([part for part in parts if part.strip()])


def _code_mentions_nightly(code: str | None) -> bool:
    if not code:
        return False
    if re.search(r"#!\s*\[\s*feature\b", code):
        return True
    if re.search(r"#\s*\[\s*feature\b", code):
        return True
    if "feature(" in code or "feature =" in code or 'feature="' in code:
        return True
    return False


def _explanation_violations(text: str, code: str | None = None) -> list[str]:
    text = str(text or "")
    violations: list[str] = []
    if "```" in text:
        violations.append("code_fence")
    if any(_EXPLANATION_BULLET_RE.match(line) for line in text.splitlines()):
        violations.append("bullets")
    if _EXPLANATION_JOKE_START_RE.match(text):
        violations.append("jokey_open")
    if re.search(r"\n\s*\n", text):
        violations.append("blank_lines")
    for line in text.splitlines():
        if _EXPLANATION_PREAMBLE_RE.match(line):
            violations.append("preamble")
            break
        if _EXPLANATION_NOTE_RE.match(line):
            violations.append("note")
            break
    if _EXPLANATION_NIGHTLY_RE.search(text) and not _code_mentions_nightly(code):
        violations.append("unsupported_nightly_claim")
    sentence_count = _count_sentences(text)
    if sentence_count < 2 or sentence_count > 6:
        violations.append(f"sentence_count={sentence_count}")
    return violations


def _explanation_code_is_substantial(code: str) -> bool:
    if not code or not code.strip():
        return False
    non_empty_lines = [line for line in code.splitlines() if line.strip()]
    if len(non_empty_lines) < 4:
        return False
    if len(code.strip()) < 80:
        return False
    return True


def _prompt_key(sample: dict[str, Any]) -> str | None:
    prompt = sample.get("prompt")
    if not isinstance(prompt, str):
        return None
    key = prompt.strip()
    return key if key else None


def strict_sample_errors(
    sample: dict[str, Any],
    *,
    validator: FormatValidator | None = None,
    max_lines: int | None = None,
    max_chars: int | None = None,
) -> list[str]:
    errors: list[str] = []
    if validator:
        is_valid, format_errors = validator.validate_sample(
            sample, max_lines=max_lines, max_chars=max_chars
        )
        if not is_valid:
            errors.extend(format_errors)

    prompt = sample.get("prompt")
    gen = sample.get("gen")
    task_type = sample.get("_task_type")

    if prompt is None:
        errors.append("prompt_missing")
    elif isinstance(prompt, str):
        if max_lines and prompt.count("\n") > max_lines:
            errors.append("prompt_too_long_lines")
        if max_chars and len(prompt) > max_chars:
            errors.append("prompt_too_long_chars")
    elif prompt is not None:
        errors.append("prompt_not_string")

    if gen is None:
        errors.append("gen_missing")
    elif isinstance(gen, str):
        if validator is None:
            if max_lines and gen.count("\n") > max_lines:
                errors.append("gen_too_long_lines")
            if max_chars and len(gen) > max_chars:
                errors.append("gen_too_long_chars")
    elif gen is not None:
        errors.append("gen_not_string")

    if task_type in ("code_generation", "transformations", "error_fixing"):
        if isinstance(gen, str):
            if _STRICT_TODO_RE.search(gen):
                errors.append("gen_contains_todo")
            if _STRICT_PLACEHOLDER_RE.search(gen):
                errors.append("gen_contains_placeholder")
            if _forbidden_imports(prompt, gen):
                errors.append("gen_contains_imports")
        if task_type == "error_fixing":
            broken = sample.get("_broken_code")
            if not isinstance(broken, str) or not broken.strip():
                errors.append("error_fix_missing_broken_code")
            elif isinstance(gen, str) and gen.strip() == broken.strip():
                errors.append("error_fix_no_change")

    return errors


async def enforce_sample_gates_async(
    samples: AsyncIterable[Dict[str, Any]],
    *,
    validate_format: bool = True,
    max_lines: int | None = None,
    max_chars: int | None = None,
    strict_validation: bool = False,
    deduplicate_prompts: bool = False,
    seen_prompts: set[str] | None = None,
    rejection_tracker: RejectionTracker | None = None,
) -> AsyncIterator[Dict[str, Any]]:
    """Apply strict validation and prompt deduplication to an async sample stream."""
    validator = FormatValidator() if validate_format else None
    prompt_cache = seen_prompts if seen_prompts is not None else set()

    async for sample in samples:
        errors = strict_sample_errors(
            sample,
            validator=validator,
            max_lines=max_lines,
            max_chars=max_chars,
        )
        if errors:
            if rejection_tracker:
                rejection_tracker.record(
                    "sample_strict_invalid",
                    sample,
                    sample.get("_task_type"),
                    detail=";".join(errors),
                    payload={"prompt": sample.get("prompt"), "gen": sample.get("gen")},
                )
            if strict_validation:
                location = sample.get("_file_path") or "<unknown>"
                task = sample.get("_task_type") or "unknown"
                raise ValueError(
                    f"Strict validation failed for {location} ({task}): {', '.join(errors)}"
                )
            continue

        if deduplicate_prompts:
            key = _prompt_key(sample)
            if not key:
                if strict_validation:
                    raise ValueError(
                        "Strict validation failed: missing prompt for dedup"
                    )
                if rejection_tracker:
                    rejection_tracker.record(
                        "sample_prompt_missing_for_dedup",
                        sample,
                        sample.get("_task_type"),
                        payload={
                            "prompt": sample.get("prompt"),
                            "gen": sample.get("gen"),
                        },
                    )
                continue
            if key in prompt_cache:
                if rejection_tracker:
                    rejection_tracker.record(
                        "sample_duplicate_prompt",
                        sample,
                        sample.get("_task_type"),
                        payload={
                            "prompt": sample.get("prompt"),
                            "gen": sample.get("gen"),
                        },
                    )
                if strict_validation:
                    location = sample.get("_file_path") or "<unknown>"
                    raise ValueError(
                        f"Duplicate prompt detected in {location} during strict validation"
                    )
                continue
            prompt_cache.add(key)

        yield sample


async def _process_file(
    file_info: Dict[str, Any],
    task_type_mix: Dict[str, float],
    rng: random.Random,
    semaphore: asyncio.Semaphore,
    *,
    validate_outputs: bool,
    cargo_env: dict[str, str] | None,
    validation_timeout: int,
    require_rustfmt: bool,
    sandbox_mode: str,
    enable_error_injection: bool,
    error_injection_method: str,
    allow_simulated_error_fixing: bool,
    error_injection_timeout: int,
    allow_explanations: bool,
    prompt_seed: int | None = None,
    rejection_tracker: RejectionTracker | None = None,
) -> Optional[Dict[str, Any]]:
    """Asynchronously generate a single sample for the given file.

    This function determines the task type, invokes the appropriate helper
    from ``task_generator_llm`` and assembles the resulting dictionary.  If
    the LLM helper returns ``None`` or raises an exception, a fallback
    code‑generation sample is produced.  Metadata such as the source file
    path and line range are attached under underscore‑prefixed keys.
    """
    task_type: str | None = None

    def reject(
        reason: str,
        detail: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        if rejection_tracker:
            rejection_tracker.record(reason, file_info, task_type, detail, payload)

    def llm_payload(
        llm_result: dict[str, Any] | None = None,
        *,
        candidate: str | None = None,
        broken_code: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "source_code": code,
            "context": context,
        }
        if llm_result:
            prompt = llm_result.get("prompt")
            gen = llm_result.get("gen")
            if prompt:
                payload["prompt"] = prompt
            if gen:
                payload["gen"] = gen
        if candidate:
            payload["normalized_gen"] = candidate
        if broken_code:
            payload["broken_code"] = broken_code
        return payload

    code: str = file_info.get("code", "")
    if not code:
        reject("missing_code")
        return None
    # Build a context string from any additional fields.  Many heuristics
    # attach imports or type definitions under ``file_context`` or
    # ``context``; include both if present.
    context_parts: List[str] = []
    for ctx_key in ("file_context", "context"):
        ctx_val = file_info.get(ctx_key)
        if ctx_val:
            context_parts.append(str(ctx_val))
    context = "\n".join(context_parts)

    chunk_type = file_info.get("chunk_type")
    available = _available_task_types(
        file_info,
        enable_error_injection=enable_error_injection,
        error_injection_method=error_injection_method,
        allow_simulated_error_fixing=allow_simulated_error_fixing,
        allow_explanations=allow_explanations,
    )
    if available is not None and not available:
        reject("no_available_task_types", str(chunk_type))
        return None
    task_type = _select_task_type(task_type_mix, rng, available=available or None)
    file_path = file_info.get("path") or file_info.get("file_path")
    crate_dir = file_info.get("crate_dir")
    start_line = file_info.get("start_line")
    end_line = file_info.get("end_line")

    async def _run_llm(task: str, input_code: str) -> Optional[Dict[str, Any]]:
        async with semaphore:
            try:
                if task == "transformations":
                    return await generate_refactoring_task(input_code, context)
                if task == "error_fixing":
                    return await generate_bug_fixing_task(input_code, context)
                if task == "explanations":
                    return await generate_documentation_task(input_code, context)
                return await generate_code_generation_task(input_code, context)
            except Exception:
                return None

    result: Dict[str, Any] | None = None

    if task_type == "code_generation":
        if chunk_type not in ("function", None):
            reject("codegen_invalid_chunk_type", str(chunk_type))
            return None
        if chunk_type is None and validate_outputs:
            reject("codegen_missing_chunk_type_for_validation")
            return None
        stubbed = output_validator.stub_function_body(code)
        if not stubbed:
            reject("codegen_stub_failed")
            return None
        llm_result = await _run_llm(task_type, stubbed)
        if not llm_result:
            reject("codegen_llm_no_result")
            return None
        candidate = output_validator.normalize_llm_code(
            llm_result.get("gen"), task_type="code_generation"
        )
        if not candidate:
            extracted = output_validator.extract_function_item(
                llm_result.get("gen") or "", original_code=code
            )
            if extracted:
                candidate = output_validator.normalize_llm_code(
                    extracted, task_type="code_generation"
                )
        if not candidate:
            reject("codegen_llm_empty", payload=llm_payload(llm_result))
            return None
        # Apply post-processing to fix common LLM issues
        candidate = output_validator.postprocess_llm_output(candidate)
        # Early rejection for placeholder code (before expensive cargo check)
        if output_validator.is_placeholder_code(candidate):
            reject(
                "codegen_placeholder_code",
                payload=llm_payload(llm_result, candidate=candidate),
            )
            return None
        extracted = output_validator.extract_function_item(
            candidate, original_code=code
        )
        if extracted:
            candidate = extracted
        if not output_validator.has_single_top_level_item(
            candidate, expected="function"
        ):
            reject(
                "codegen_shape_mismatch",
                payload=llm_payload(llm_result, candidate=candidate),
            )
            return None
        if not output_validator.signatures_compatible(code, candidate):
            reject(
                "codegen_signature_mismatch",
                payload=llm_payload(llm_result, candidate=candidate),
            )
            return None
        if _forbidden_imports(llm_result.get("prompt"), candidate):
            reject(
                "gen_contains_imports",
                payload=llm_payload(llm_result, candidate=candidate),
            )
            return None
        if validate_outputs:
            if not crate_dir or start_line is None or end_line is None or not file_path:
                reject("codegen_missing_location")
                return None
            ok, _reason = await output_validator.validate_with_cargo_check(
                crate_dir=Path(crate_dir),
                file_path=file_path,
                start_line=int(start_line),
                end_line=int(end_line),
                replacement=candidate,
                cargo_env=cargo_env,
                timeout=validation_timeout,
                require_rustfmt=require_rustfmt,
                sandbox_mode=sandbox_mode,
            )
            if not ok:
                reject(
                    "codegen_cargo_check_failed",
                    _reason,
                    payload=llm_payload(llm_result, candidate=candidate),
                )
                return None
        # Check for common hallucination patterns
        hallucinations = output_validator.detect_hallucinations(candidate)
        if hallucinations:
            reject(
                "codegen_hallucination_detected",
                ";".join(hallucinations),
                payload=llm_payload(llm_result, candidate=candidate),
            )
            return None
        llm_result["gen"] = candidate
        result = llm_result

    elif task_type == "transformations":
        if chunk_type != "function":
            reject("transform_invalid_chunk_type", str(chunk_type))
            return None
        llm_result = await _run_llm(task_type, code)
        if not llm_result:
            reject("transform_llm_no_result")
            return None
        candidate = output_validator.normalize_llm_code(llm_result.get("gen"))
        if not candidate:
            reject("transform_llm_empty", payload=llm_payload(llm_result))
            return None
        # Apply post-processing to fix common LLM issues
        candidate = output_validator.postprocess_llm_output(candidate)
        # Early rejection for placeholder code (before expensive cargo check)
        if output_validator.is_placeholder_code(candidate):
            reject(
                "transform_placeholder_code",
                payload=llm_payload(llm_result, candidate=candidate),
            )
            return None
        extracted = output_validator.extract_function_item(
            candidate, original_code=code
        )
        if extracted:
            candidate = extracted
        if not output_validator.has_single_top_level_item(
            candidate, expected=chunk_type
        ):
            reject(
                "transform_shape_mismatch",
                payload=llm_payload(llm_result, candidate=candidate),
            )
            return None
        if chunk_type == "function" and not output_validator.signatures_compatible(
            code, candidate
        ):
            reject(
                "transform_signature_mismatch",
                payload=llm_payload(llm_result, candidate=candidate),
            )
            return None
        if _forbidden_imports(llm_result.get("prompt"), candidate):
            reject(
                "gen_contains_imports",
                payload=llm_payload(llm_result, candidate=candidate),
            )
            return None
        if validate_outputs and chunk_type is not None:
            if not crate_dir or start_line is None or end_line is None or not file_path:
                reject("transform_missing_location")
                return None
            ok, _reason = await output_validator.validate_with_cargo_check(
                crate_dir=Path(crate_dir),
                file_path=file_path,
                start_line=int(start_line),
                end_line=int(end_line),
                replacement=candidate,
                cargo_env=cargo_env,
                timeout=validation_timeout,
                require_rustfmt=require_rustfmt,
                sandbox_mode=sandbox_mode,
            )
            if not ok:
                reject(
                    "transform_cargo_check_failed",
                    _reason,
                    payload=llm_payload(llm_result, candidate=candidate),
                )
                return None
        # Reject identity transformations (refactor must actually change something)
        if candidate.strip() == code.strip():
            reject(
                "transform_no_change",
                payload=llm_payload(llm_result, candidate=candidate),
            )
            return None
        # Check for common hallucination patterns
        hallucinations = output_validator.detect_hallucinations(candidate)
        if hallucinations:
            reject(
                "transform_hallucination_detected",
                ";".join(hallucinations),
                payload=llm_payload(llm_result, candidate=candidate),
            )
            return None
        llm_result["gen"] = candidate
        result = llm_result

    elif task_type == "error_fixing":
        if chunk_type not in ("function", None):
            reject("error_fix_invalid_chunk_type", str(chunk_type))
            return None
        if chunk_type is None and validate_outputs:
            reject("error_fix_missing_chunk_type_for_validation")
            return None
        injected = deterministic_task_generator.generate_error_fixing_task(
            code,
            method=error_injection_method,
            crate_dir=Path(crate_dir) if crate_dir else None,
            timeout=error_injection_timeout,
        )
        if not injected:
            reject("error_fix_injection_failed")
            return None
        broken_code = injected.get("broken")
        if not broken_code:
            reject("error_fix_missing_broken")
            return None
        if validate_outputs:
            if not crate_dir or start_line is None or end_line is None or not file_path:
                reject("error_fix_missing_location")
                return None
            ok, reason = await output_validator.validate_with_cargo_check(
                crate_dir=Path(crate_dir),
                file_path=file_path,
                start_line=int(start_line),
                end_line=int(end_line),
                replacement=broken_code,
                cargo_env=cargo_env,
                timeout=validation_timeout,
                require_rustfmt=False,
                sandbox_mode=sandbox_mode,
            )
            if ok or reason != "cargo_check_failed":
                if ok:
                    reject("error_fix_broken_compiles")
                else:
                    reject("error_fix_broken_validation_failed", reason)
                return None
        llm_result = await _run_llm(task_type, broken_code)
        if not llm_result:
            reject("error_fix_llm_no_result")
            return None
        candidate = output_validator.normalize_llm_code(llm_result.get("gen"))
        if not candidate:
            reject(
                "error_fix_llm_empty",
                payload=llm_payload(llm_result, broken_code=broken_code),
            )
            return None
        # Apply post-processing to fix common LLM issues
        candidate = output_validator.postprocess_llm_output(candidate)
        # Early rejection for placeholder code (before expensive cargo check)
        if output_validator.is_placeholder_code(candidate):
            reject(
                "error_fix_placeholder_code",
                payload=llm_payload(
                    llm_result, candidate=candidate, broken_code=broken_code
                ),
            )
            return None
        extracted = output_validator.extract_function_item(
            candidate, original_code=code
        )
        if extracted:
            candidate = extracted
        if not output_validator.has_single_top_level_item(
            candidate, expected="function"
        ):
            reject(
                "error_fix_shape_mismatch",
                payload=llm_payload(
                    llm_result, candidate=candidate, broken_code=broken_code
                ),
            )
            return None
        if not output_validator.signatures_compatible(code, candidate):
            reject(
                "error_fix_signature_mismatch",
                payload=llm_payload(
                    llm_result, candidate=candidate, broken_code=broken_code
                ),
            )
            return None
        if candidate.strip() == broken_code.strip():
            reject(
                "error_fix_no_change",
                payload=llm_payload(
                    llm_result, candidate=candidate, broken_code=broken_code
                ),
            )
            return None
        if _forbidden_imports(llm_result.get("prompt"), candidate):
            reject(
                "gen_contains_imports",
                payload=llm_payload(
                    llm_result, candidate=candidate, broken_code=broken_code
                ),
            )
            return None
        if validate_outputs:
            ok, _reason = await output_validator.validate_with_cargo_check(
                crate_dir=Path(crate_dir),
                file_path=file_path,
                start_line=int(start_line),
                end_line=int(end_line),
                replacement=candidate,
                cargo_env=cargo_env,
                timeout=validation_timeout,
                require_rustfmt=require_rustfmt,
                sandbox_mode=sandbox_mode,
            )
            if not ok:
                reject(
                    "error_fix_cargo_check_failed",
                    _reason,
                    payload=llm_payload(
                        llm_result, candidate=candidate, broken_code=broken_code
                    ),
                )
                return None
        # Check for common hallucination patterns
        hallucinations = output_validator.detect_hallucinations(candidate)
        if hallucinations:
            reject(
                "error_fix_hallucination_detected",
                ";".join(hallucinations),
                payload=llm_payload(
                    llm_result, candidate=candidate, broken_code=broken_code
                ),
            )
            return None
        llm_result["gen"] = candidate
        llm_result["_broken_code"] = broken_code
        result = llm_result

    elif task_type == "fill_in_middle":
        if chunk_type != "function":
            reject("fim_invalid_chunk_type", str(chunk_type))
            return None
        # FIM tasks don't use LLM - they're deterministic extractions
        fim_result = await generate_fim_task(code, context)
        if not fim_result:
            reject("fim_extraction_failed")
            return None
        # Validate the FIM structure
        prompt = fim_result.get("prompt", "")
        gen = fim_result.get("gen", "")
        if not prompt or not gen:
            reject("fim_empty_result", payload={"prompt": prompt, "gen": gen})
            return None
        # FIM doesn't need cargo check - the code is already known to compile
        result = fim_result

    elif task_type == "explanations":
        if not _explanation_code_is_substantial(code):
            reject("explain_code_too_small")
            return None
        llm_result = await _run_llm(task_type, code)
        if not llm_result:
            reject("explain_llm_no_result")
            return None
        violations = _explanation_violations(llm_result.get("gen", ""), code=code)
        if violations:
            reject(
                "explain_output_filtered",
                ";".join(violations),
                payload=llm_payload(llm_result),
            )
            return None
        result = llm_result

    if result is None and not validate_outputs:
        fallback_prompt = f"Complete the following Rust code:\n\n{code}"
        result = {
            "prompt": fallback_prompt,
            "gen": code,
            "_task_type": "code_generation",
            "_llm_failure": True,
        }
    if result is None:
        return None

    # Attach metadata about the source location if available.
    if file_path:
        result["_file_path"] = file_path
    if file_info.get("crate_name"):
        result["_source_crate"] = file_info["crate_name"]
    if (
        file_info.get("start_line") is not None
        and file_info.get("end_line") is not None
    ):
        result["_start_line"] = file_info["start_line"]
        result["_end_line"] = file_info["end_line"]
    if chunk_type:
        result["_chunk_type"] = chunk_type
    if prompt_seed is not None:
        result["_prompt_seed"] = prompt_seed

    return result


async def _iter_samples_async(
    file_infos: Iterable[Dict[str, Any]],
    task_type_mix: Dict[str, float],
    concurrency: int,
    *,
    validate_outputs: bool,
    cargo_env: dict[str, str] | None,
    validation_timeout: int,
    require_rustfmt: bool,
    sandbox_mode: str,
    enable_error_injection: bool,
    error_injection_method: str,
    allow_simulated_error_fixing: bool,
    error_injection_timeout: int,
    allow_explanations: bool,
    prompt_seed: int | None = None,
    rejection_tracker: RejectionTracker | None = None,
) -> AsyncIterator[Dict[str, Any]]:
    """Concurrent helper to yield dataset entries asynchronously.

    Spawns coroutines for each file and awaits them in the order they
    complete.  Errors are swallowed; only successful samples are yielded.
    Use a semaphore to limit the number of concurrent LLM requests.
    """
    rng = random.Random()
    semaphore = asyncio.Semaphore(max(1, concurrency))
    coroutines = [
        _process_file(
            file_info,
            task_type_mix,
            rng,
            semaphore,
            validate_outputs=validate_outputs,
            cargo_env=cargo_env,
            validation_timeout=validation_timeout,
            require_rustfmt=require_rustfmt,
            sandbox_mode=sandbox_mode,
            enable_error_injection=enable_error_injection,
            error_injection_method=error_injection_method,
            allow_simulated_error_fixing=allow_simulated_error_fixing,
            error_injection_timeout=error_injection_timeout,
            allow_explanations=allow_explanations,
            prompt_seed=prompt_seed,
            rejection_tracker=rejection_tracker,
        )
        for file_info in file_infos
    ]
    for coro in asyncio.as_completed(coroutines):
        try:
            sample = await coro
        except Exception:
            sample = None
        if sample:
            yield sample


async def iter_dataset_entries_async(
    file_infos: Iterable[Dict[str, Any]],
    task_type_mix: Optional[Dict[str, float]] = None,
    *,
    validate_format: bool = True,
    validate_outputs: bool = False,
    validation_timeout: int = 160,
    cargo_env: dict[str, str] | None = None,
    require_rustfmt: bool = False,
    sandbox_mode: str = "auto",
    allow_explanations: bool = True,
    enable_error_injection: bool = True,
    error_injection_method: str = "both",
    allow_simulated_error_fixing: bool = False,
    error_injection_timeout: int = 120,
    prompt_seed: int | None = None,
    max_sft_lines: int | None = None,
    max_sft_chars: int | None = None,
    max_lines: int = 200,
    max_chars: int = 8000,
    concurrency: int = 5,
    rejection_tracker: RejectionTracker | None = None,
) -> AsyncIterator[Dict[str, Any]]:
    """Yield dataset entries from ``file_infos`` as they complete (async)."""
    effective_max_lines = max_sft_lines if max_sft_lines is not None else max_lines
    effective_max_chars = max_sft_chars if max_sft_chars is not None else max_chars

    mix = task_type_mix or DEFAULT_TASK_TYPE_MIX.copy()
    normalized_mix = _normalize_task_mix(
        mix,
        enable_error_injection=enable_error_injection,
        error_injection_method=error_injection_method,
        allow_simulated_error_fixing=allow_simulated_error_fixing,
    )
    if not normalized_mix:
        normalized_mix = {"code_generation": 1.0}

    validator = FormatValidator() if validate_format else None
    async for sample in _iter_samples_async(
        file_infos,
        normalized_mix,
        concurrency,
        validate_outputs=validate_outputs,
        cargo_env=cargo_env,
        validation_timeout=validation_timeout,
        require_rustfmt=require_rustfmt,
        sandbox_mode=sandbox_mode,
        enable_error_injection=enable_error_injection,
        error_injection_method=error_injection_method,
        allow_simulated_error_fixing=allow_simulated_error_fixing,
        error_injection_timeout=error_injection_timeout,
        allow_explanations=allow_explanations,
        prompt_seed=prompt_seed,
        rejection_tracker=rejection_tracker,
    ):
        prompt = sample.get("prompt", "")
        gen = sample.get("gen", "")
        # Basic validation: ensure prompt and gen are non-empty strings.
        if not isinstance(prompt, str) or not prompt.strip():
            if rejection_tracker:
                rejection_tracker.record(
                    "sample_prompt_empty",
                    sample,
                    sample.get("_task_type"),
                    payload={"prompt": sample.get("prompt"), "gen": sample.get("gen")},
                )
            continue
        if not isinstance(gen, str) or not gen.strip():
            if rejection_tracker:
                rejection_tracker.record(
                    "sample_gen_empty",
                    sample,
                    sample.get("_task_type"),
                    payload={"prompt": sample.get("prompt"), "gen": sample.get("gen")},
                )
            continue
        # Enforce line and character limits.
        if (
            prompt.count("\n") > effective_max_lines
            or len(prompt) > effective_max_chars
        ):
            if rejection_tracker:
                rejection_tracker.record(
                    "sample_prompt_too_long",
                    sample,
                    sample.get("_task_type"),
                    payload={"prompt": sample.get("prompt"), "gen": sample.get("gen")},
                )
            continue
        if gen.count("\n") > effective_max_lines or len(gen) > effective_max_chars:
            if rejection_tracker:
                rejection_tracker.record(
                    "sample_gen_too_long",
                    sample,
                    sample.get("_task_type"),
                    payload={"prompt": sample.get("prompt"), "gen": sample.get("gen")},
                )
            continue
        if validator:
            is_valid, _errors = validator.validate_sample(
                sample,
                max_lines=effective_max_lines,
                max_chars=effective_max_chars,
            )
            if not is_valid:
                if rejection_tracker:
                    rejection_tracker.record(
                        "sample_format_invalid",
                        sample,
                        sample.get("_task_type"),
                        payload={
                            "prompt": sample.get("prompt"),
                            "gen": sample.get("gen"),
                        },
                    )
                continue
        yield sample


async def build_dataset_entries_async(
    file_infos: Iterable[Dict[str, Any]],
    task_type_mix: Optional[Dict[str, float]] = None,
    *,
    validate_format: bool = True,
    validate_outputs: bool = False,
    validation_timeout: int = 160,
    cargo_env: dict[str, str] | None = None,
    require_rustfmt: bool = False,
    sandbox_mode: str = "auto",
    allow_explanations: bool = True,
    enable_error_injection: bool = True,
    error_injection_method: str = "both",
    allow_simulated_error_fixing: bool = False,
    error_injection_timeout: int = 120,
    prompt_seed: int | None = None,
    max_sft_lines: int | None = None,
    max_sft_chars: int | None = None,
    max_lines: int = 200,
    max_chars: int = 8000,
    concurrency: int = 5,
    rejection_tracker: RejectionTracker | None = None,
) -> List[Dict[str, Any]]:
    """Build a list of dataset entries from ``file_infos`` (async)."""
    return [
        sample
        async for sample in iter_dataset_entries_async(
            file_infos,
            task_type_mix=task_type_mix,
            validate_format=validate_format,
            validate_outputs=validate_outputs,
            validation_timeout=validation_timeout,
            cargo_env=cargo_env,
            require_rustfmt=require_rustfmt,
            sandbox_mode=sandbox_mode,
            allow_explanations=allow_explanations,
            enable_error_injection=enable_error_injection,
            error_injection_method=error_injection_method,
            allow_simulated_error_fixing=allow_simulated_error_fixing,
            error_injection_timeout=error_injection_timeout,
            prompt_seed=prompt_seed,
            max_sft_lines=max_sft_lines,
            max_sft_chars=max_sft_chars,
            max_lines=max_lines,
            max_chars=max_chars,
            concurrency=concurrency,
            rejection_tracker=rejection_tracker,
        )
    ]


def _run_async_in_thread(coro):
    result: dict[str, Any] = {}
    error: dict[str, BaseException] = {}

    def runner():
        try:
            result["value"] = asyncio.run(coro)
        except BaseException as exc:
            error["exc"] = exc

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()
    if error:
        raise error["exc"]
    return result.get("value", [])


def build_dataset_entries(
    file_infos: Iterable[Dict[str, Any]],
    task_type_mix: Optional[Dict[str, float]] = None,
    *,
    validate_format: bool = True,
    validate_outputs: bool = False,
    validation_timeout: int = 160,
    cargo_env: dict[str, str] | None = None,
    require_rustfmt: bool = False,
    sandbox_mode: str = "auto",
    allow_explanations: bool = True,
    enable_error_injection: bool = True,
    error_injection_method: str = "both",
    allow_simulated_error_fixing: bool = False,
    error_injection_timeout: int = 120,
    prompt_seed: int | None = None,
    max_sft_lines: int | None = None,
    max_sft_chars: int | None = None,
    max_lines: int = 200,
    max_chars: int = 8000,
    concurrency: int = 5,
    rejection_tracker: RejectionTracker | None = None,
) -> List[Dict[str, Any]]:
    """Build a list of dataset entries from ``file_infos`` (sync wrapper)."""
    coro = build_dataset_entries_async(
        file_infos,
        task_type_mix,
        validate_format=validate_format,
        validate_outputs=validate_outputs,
        validation_timeout=validation_timeout,
        cargo_env=cargo_env,
        require_rustfmt=require_rustfmt,
        sandbox_mode=sandbox_mode,
        allow_explanations=allow_explanations,
        enable_error_injection=enable_error_injection,
        error_injection_method=error_injection_method,
        allow_simulated_error_fixing=allow_simulated_error_fixing,
        error_injection_timeout=error_injection_timeout,
        prompt_seed=prompt_seed,
        max_sft_lines=max_sft_lines,
        max_sft_chars=max_sft_chars,
        max_lines=max_lines,
        max_chars=max_chars,
        concurrency=concurrency,
        rejection_tracker=rejection_tracker,
    )

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    return _run_async_in_thread(coro)


__all__ = [
    "build_dataset_entries",
    "build_dataset_entries_async",
    "enforce_sample_gates_async",
    "iter_dataset_entries_async",
    "strict_sample_errors",
]
