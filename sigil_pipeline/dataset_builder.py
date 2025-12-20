"""
Dataset builder module for creating prompt-gen pairs from code.
Refactored to support 'Context -> JSON' format for high-quality Rust fine-tuning.
"""

import logging
import random
import re
import textwrap
from pathlib import Path
from typing import Any, Iterable, Iterator

import tree_sitter_rust as tst_rust
from tree_sitter import Language, Parser

from .ast_patterns import extract_context_header
from .format_validator import FormatValidator
from .task_generator import (
    generate_error_fixing_task,
    generate_explanation_task,
    generate_transformation_task,
)

logger = logging.getLogger(__name__)


def _get_parser() -> Parser:
    rust_language = Language(tst_rust.language())
    return Parser(rust_language)


def extract_description_from_docs(code: str) -> str | None:
    """Extract a description from doc comments in code."""
    module_doc_match = re.search(
        r"^//![\s]*(.+?)(?:\n\n|\n//[^!]|$)",
        code,
        re.MULTILINE | re.DOTALL,
    )
    if module_doc_match:
        return module_doc_match.group(1).strip()[:500]

    fn_doc_match = re.search(
        r"^///[\s]*(.+?)(?:\n\s*///|\n\s*pub fn|\n\s*fn|$)",
        code,
        re.MULTILINE | re.DOTALL,
    )
    if fn_doc_match:
        return fn_doc_match.group(1).strip()[:500]
    return None


def format_code_for_gen(code: str, phase1_spec: dict[str, Any] | None = None) -> str:
    """Format code to be clean strings."""
    formatted = textwrap.dedent(code).strip()
    formatted = re.sub(r"```rust\n?", "", formatted)
    formatted = re.sub(r"```\n?", "", formatted)
    return formatted.strip()


def _select_task_type(
    task_type_mix: dict[str, float] | None, rng: random.Random
) -> str:
    if not task_type_mix:
        return "code_generation"

    items = [(key, value) for key, value in task_type_mix.items() if value > 0]
    if not items:
        return "code_generation"

    total = sum(value for _, value in items)
    roll = rng.random() * total
    cumulative = 0.0
    for key, weight in items:
        cumulative += weight
        if roll <= cumulative:
            return key
    return items[-1][0]


def _scaffold_function_body(code: str) -> str | None:
    parser = _get_parser()
    tree = parser.parse(bytes(code, "utf8"))
    root = tree.root_node

    function_node = next(
        (node for node in root.children if node.type == "function_item"), None
    )
    if not function_node:
        function_node = next(
            (node for node in root.children if node.type == "impl_item"), None
        )

    if not function_node:
        function_node = next(
            (node for node in root.children if node.type == "mod_item"), None
        )

    if not function_node:
        return None

    target_node = function_node
    if target_node.type != "function_item":
        function_child = next(
            (child for child in target_node.children if child.type == "function_item"),
            None,
        )
        if not function_child:
            return None
        target_node = function_child

    block_node = next(
        (child for child in target_node.children if child.type == "block"), None
    )
    if not block_node:
        return None

    line_start = code.rfind("\n", 0, block_node.start_byte) + 1
    indent = re.match(r"[\t ]*", code[line_start : block_node.start_byte]).group(0)
    scaffold_block = "{\n" + indent + "    todo!()\n" + indent + "}"

    return code[: block_node.start_byte] + scaffold_block + code[block_node.end_byte :]


def _scaffold_generic(code: str) -> str | None:
    lines = code.splitlines()
    if len(lines) < 4:
        return None

    start = max(1, len(lines) // 2 - 1)
    end = min(len(lines) - 1, start + 1)
    placeholder = "    // TODO: fill in"
    new_lines = lines[:start] + [placeholder] + lines[end:]
    return "\n".join(new_lines)


def _generate_scaffold_task(code: str) -> dict[str, Any] | None:
    scaffolded = _scaffold_function_body(code)
    if scaffolded is None:
        scaffolded = _scaffold_generic(code)
    if scaffolded is None:
        return None

    return {
        "instruction": "Fill in the missing Rust implementation marked by TODO.",
        "input_code": scaffolded,
        "output_json": {"code": code},
        "_task_type": "code_generation",
    }


def _attempt_task_generation(
    task_type: str,
    formatted_code: str,
    doc_comment: str | None,
    file_info: dict,
    enable_error_injection: bool,
    error_injection_method: str,
    error_injection_timeout: int,
) -> dict[str, Any] | None:
    if task_type == "explanations":
        return generate_explanation_task(formatted_code, doc_comment)

    if task_type == "error_fixing" and enable_error_injection:
        crate_dir_val = file_info.get("crate_dir")
        crate_path = Path(str(crate_dir_val)) if crate_dir_val else None
        return generate_error_fixing_task(
            formatted_code,
            error_injection_method,
            crate_path,
            file_info.get("path"),
            file_info.get("start_line"),
            file_info.get("end_line"),
            error_injection_timeout,
        )

    if task_type == "transformations":
        return generate_transformation_task(formatted_code)

    if task_type == "code_generation":
        return _generate_scaffold_task(formatted_code)

    return None


def build_dataset_entries(
    files: Iterable[dict],
    validate_format: bool = True,
    phase1_spec_path: Path | None = None,
    prompt_mode: str = "instruct",
    task_type_mix: dict[str, float] | None = None,
    enable_error_injection: bool = True,
    error_injection_method: str = "both",
    error_injection_timeout: int = 120,
    max_sft_lines: int | None = None,
    max_sft_chars: int | None = None,
    prompt_seed: int | None = None,
    enable_prompt_randomization: bool = True,
) -> Iterator[dict]:
    """
    Convert code files into dataset samples with strict JSON output format.
    """
    validator = FormatValidator() if validate_format else None
    rng = random.Random(prompt_seed if enable_prompt_randomization else 0)

    for file_info in files:
        code = file_info.get("code", "")
        if not code:
            continue

        formatted_code = format_code_for_gen(code)

        # 1. Extract Context (Imports/Structs) using AST
        try:
            context_header = file_info.get("file_context") or extract_context_header(
                formatted_code
            )
        except Exception:
            context_header = ""  # Fallback if parsing fails

        doc_comment = extract_description_from_docs(formatted_code)

        # 2. Base Sample Structure (Context + JSON Output)
        sample: dict[str, Any] = {
            "crate_name": file_info.get("crate_name"),
            "input_data": {
                "code": formatted_code,
                "code_context": context_header,
                "prompt": "Write idiomatic Rust code based on the context.",
                "file_path": file_info.get("path"),
                "start_line": file_info.get("start_line"),
                "end_line": file_info.get("end_line"),
            },
            "output_data": {"code": formatted_code},
            "task_category": "code_generation",
            "test": "",
        }

        if prompt_seed is not None:
            sample["_prompt_seed"] = prompt_seed

        if prompt_mode == "instruct":
            selected_task = _select_task_type(task_type_mix, rng)
            task_priority = [selected_task]
            for fallback in ["error_fixing", "explanations", "code_generation"]:
                if fallback not in task_priority:
                    task_priority.append(fallback)

            task_result = None
            for task_type in task_priority:
                task_result = _attempt_task_generation(
                    task_type,
                    formatted_code,
                    doc_comment,
                    file_info,
                    enable_error_injection,
                    error_injection_method,
                    error_injection_timeout,
                )
                if task_result:
                    break

            if task_result:
                sample["input_data"]["prompt"] = task_result["instruction"]
                if "input_code" in task_result:
                    sample["input_data"]["code"] = task_result["input_code"]
                sample["output_data"] = task_result["output_json"]
                sample["task_category"] = task_result["_task_type"]

        if validator:
            is_valid, errors = validator.validate_sample(
                sample, max_lines=max_sft_lines, max_chars=max_sft_chars
            )
            if not is_valid:
                logger.debug(f"Sample failed validation: {errors}")
                continue

        yield sample
