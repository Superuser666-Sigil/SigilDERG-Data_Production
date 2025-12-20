"""
Refactored Task Generator - Quality over Quantity.
Removes unsafe regex transformations and synthetic errors.
"""

import json
import logging
import re
import subprocess
from pathlib import Path
from typing import Any, Iterable

import tree_sitter_rust as tst_rust
from tree_sitter import Language, Parser

logger = logging.getLogger(__name__)


def _get_parser() -> Parser:
    rust_language = Language(tst_rust.language())
    return Parser(rust_language)


def _iter_nodes(root: Any) -> Iterable[Any]:
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(reversed(node.children))


def _find_function_block(
    code: str, start_line: int | None = None, end_line: int | None = None
) -> tuple[int, int, str] | None:
    parser = _get_parser()
    tree = parser.parse(bytes(code, "utf8"))
    root = tree.root_node

    function_nodes = [
        node for node in _iter_nodes(root) if node.type == "function_item"
    ]
    if not function_nodes:
        return None

    def _overlaps(node: Any) -> bool:
        node_start = node.start_point[0] + 1
        node_end = node.end_point[0] + 1
        if start_line is None or end_line is None:
            return True
        return not (node_end < start_line or node_start > end_line)

    candidates = [node for node in function_nodes if _overlaps(node)]
    target = candidates[0] if candidates else function_nodes[0]

    block_node = next(
        (child for child in target.children if child.type == "block"), None
    )
    if not block_node:
        return None

    line_start = code.rfind("\n", 0, block_node.start_byte) + 1
    indent = re.match(r"[\t ]*", code[line_start : block_node.start_byte]).group(0)

    return block_node.start_byte, block_node.end_byte, indent


def _inject_unknown_symbol(
    code: str, start_line: int | None = None, end_line: int | None = None
) -> str | None:
    block_info = _find_function_block(code, start_line=start_line, end_line=end_line)
    if not block_info:
        return None

    start_byte, end_byte, indent = block_info
    injected_block = "{\n" + indent + "    let _ = __sigil_unknown;\n" + indent + "}"

    return code[:start_byte] + injected_block + code[end_byte:]


def _extract_compiler_error(output: str) -> tuple[str | None, str | None]:
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("reason") != "compiler-message":
            continue
        message = payload.get("message", {})
        if message.get("level") != "error":
            continue
        error_message = message.get("message")
        error_code = None
        if isinstance(message.get("code"), dict):
            error_code = message.get("code", {}).get("code")
        return error_message, error_code
    return None, None


def generate_transformation_task(
    code: str, patterns: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    """
    DISABLED: Regex transformations generate invalid Rust code.
    Returns None to prevent generation of broken training data.
    """
    return None


def generate_error_fixing_task(
    code: str,
    method: str,  # retained for compatibility signature
    crate_dir: Path | None = None,
    file_path: str | None = None,
    start_line: int | None = None,
    end_line: int | None = None,
    timeout: int = 120,
) -> dict[str, Any] | None:
    """
    Generate an error-fixing task using REAL compilation only.
    """
    if not crate_dir or not file_path:
        return None

    try:
        error_msg, broken_code, error_code = _inject_real_error(
            code,
            crate_dir,
            file_path,
            start_line,
            end_line,
            timeout,
        )
        if error_msg and broken_code:
            return {
                "instruction": "Fix the compiler error and return the corrected code.",
                "input_code": broken_code,
                "output_json": {
                    "fixed_code": code,
                    "explanation": f"The code failed with {error_code or 'an error'}: {error_msg}",
                    "error_message": error_msg,
                },
                "_task_type": "error_fixing",
            }
    except Exception as exc:
        logger.debug(f"Real error injection failed: {exc}")

    return None


def _inject_real_error(
    code: str,
    crate_dir: Path,
    file_path: str,
    start_line: int | None,
    end_line: int | None,
    timeout: int,
) -> tuple[str | None, str | None, str | None]:
    """
    Injects a temporary breakage and runs cargo check.
    """
    target_file = crate_dir / file_path
    if not target_file.exists():
        return None, None, None

    original_content = target_file.read_text(encoding="utf-8", errors="ignore")
    broken_file_content = _inject_unknown_symbol(
        original_content, start_line=start_line, end_line=end_line
    )
    broken_chunk = _inject_unknown_symbol(code)

    if not broken_file_content or not broken_chunk:
        return None, None, None

    try:
        target_file.write_text(broken_file_content, encoding="utf-8")

        result = subprocess.run(
            ["cargo", "check", "--message-format=json"],
            cwd=crate_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        error_message, error_code = _extract_compiler_error(stdout + "\n" + stderr)
        if error_message:
            return error_message, broken_chunk, error_code
        return None, None, None
    finally:
        try:
            target_file.write_text(original_content, encoding="utf-8")
        except Exception as exc:
            logger.warning(f"Failed to restore {target_file}: {exc}")


def generate_explanation_task(
    code: str, doc_comment: str | None = None
) -> dict[str, Any] | None:
    """
    Generate a docstring generation task ONLY if real docs exist.
    """
    if not doc_comment:
        return None  # Do not synthesize descriptions.

    # Clean up doc comment
    explanation = doc_comment.strip()
    explanation = re.sub(r"^(///|//!)\s*", "", explanation, flags=re.MULTILINE).strip()

    return {
        "instruction": "Explain what this Rust code does.",
        "input_code": code,
        "output_json": {
            "explanation": explanation,
        },
        "_task_type": "explanations",
    }


# Stub functions required by imports but not used in new logic


def determine_task_capabilities(*args, **kwargs):
    return {"code_generation"}


def select_task_type_with_quota(*args, **kwargs):
    return "code_generation"
