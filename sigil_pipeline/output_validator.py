"""
Output validation utilities for LLM-generated Rust code.

Enforces strict quality gates by normalizing LLM output, checking that the
shape/signature matches the original chunk, and compile-checking the crate
after patching the generated code in place.
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Any

from . import sandbox, utils
from .ast_patterns import extract_function_signature

logger = logging.getLogger(__name__)

_CODE_FENCE_RE = re.compile(r"```(?:rust)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_CODEGEN_DISALLOWED_RE = re.compile(
    "(?:```|\\bhere is\\b|\\.{3}|\\u2026)", re.IGNORECASE
)
_CRATE_LOCKS: dict[str, asyncio.Lock] = {}

_NODE_TYPE_TO_CHUNK = {
    "function_item": "function",
    "impl_item": "impl_block",
    "struct_item": "struct",
    "enum_item": "enum",
    "trait_item": "trait",
    "mod_item": "module",
    "type_item": "type",
}
_TOP_LEVEL_SKIP_NODES = {"attribute_item", "inner_attribute_item"}


def _get_crate_lock(crate_dir: Path) -> asyncio.Lock:
    key = str(crate_dir)
    lock = _CRATE_LOCKS.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _CRATE_LOCKS[key] = lock
    return lock


def normalize_llm_code(
    text: str | None, *, task_type: str | None = None
) -> str | None:
    """Extract and normalize code from an LLM response."""
    if not text:
        return None
    if task_type == "code_generation" and _CODEGEN_DISALLOWED_RE.search(text):
        return None
    match = _CODE_FENCE_RE.search(text)
    if match:
        text = match.group(1)
    cleaned = text.strip()
    if task_type == "code_generation" and _CODEGEN_DISALLOWED_RE.search(cleaned):
        return None
    return cleaned if cleaned else None


def _top_level_named_nodes(code: str) -> list[str]:
    if not code:
        return []
    try:
        import tree_sitter_rust as ts_rust
        from tree_sitter import Language, Parser

        rust_language = Language(ts_rust.language())
        try:
            parser = Parser(rust_language)
        except TypeError:
            parser = Parser()
            parser.set_language(rust_language)
        tree = parser.parse(code.encode("utf-8"))
        root = tree.root_node
        if getattr(root, "has_error", False):
            return []
        types: list[str] = []
        for child in root.children:
            if not getattr(child, "is_named", True):
                continue
            if child.type in _TOP_LEVEL_SKIP_NODES:
                continue
            types.append(child.type)
        return types
    except Exception:
        return []


def _extract_node_text(code: str, node: Any) -> str:
    try:
        code_bytes = code.encode("utf-8")
        chunk = code_bytes[node.start_byte : node.end_byte]
        try:
            return chunk.decode("utf-8")
        except UnicodeDecodeError:
            return chunk.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _top_level_nodes(code: str) -> list[Any]:
    if not code:
        return []
    try:
        import tree_sitter_rust as ts_rust
        from tree_sitter import Language, Parser

        rust_language = Language(ts_rust.language())
        try:
            parser = Parser(rust_language)
        except TypeError:
            parser = Parser()
            parser.set_language(rust_language)
        tree = parser.parse(code.encode("utf-8"))
        root = tree.root_node
        nodes = []
        for child in root.children:
            if not getattr(child, "is_named", True):
                continue
            if child.type in _TOP_LEVEL_SKIP_NODES:
                continue
            nodes.append(child)
        return nodes
    except Exception:
        return []


def extract_function_item(code: str, original_code: str | None = None) -> str | None:
    """Extract a single function item from code, optionally matching the original signature."""
    if not code:
        return None
    function_nodes = [
        node for node in _top_level_nodes(code) if node.type == "function_item"
    ]
    if not function_nodes:
        return None
    if original_code:
        matches: list[str] = []
        for node in function_nodes:
            snippet = _extract_node_text(code, node).strip()
            if snippet and signatures_compatible(original_code, snippet):
                matches.append(snippet)
        if len(matches) == 1:
            return matches[0]
    if len(function_nodes) == 1:
        return _extract_node_text(code, function_nodes[0]).strip()
    return None


def classify_chunk_type(code: str) -> str | None:
    """Classify the top-level Rust item type in code."""
    if not code:
        return None
    for node_type in _top_level_named_nodes(code):
        mapped = _NODE_TYPE_TO_CHUNK.get(node_type)
        if mapped:
            return mapped

    # Fallback heuristics (best-effort)
    if re.search(r"\btrait\b", code):
        return "trait"
    if re.search(r"\bimpl\b", code):
        return "impl_block"
    if re.search(r"\bstruct\b", code):
        return "struct"
    if re.search(r"\benum\b", code):
        return "enum"
    if re.search(r"\bmod\b", code):
        return "module"
    if re.search(r"\btype\b", code):
        return "type"
    if re.search(r"\bfn\b", code):
        return "function"
    return None


def has_single_top_level_item(code: str, expected: str | None = None) -> bool:
    """Return True if code has exactly one top-level item, optionally matching expected."""
    nodes = _top_level_named_nodes(code)
    if len(nodes) != 1:
        return False
    if expected is None:
        return True
    mapped = _NODE_TYPE_TO_CHUNK.get(nodes[0])
    return mapped == expected


def _normalize_sig_token(token: str | None) -> str:
    if not token:
        return ""
    return re.sub(r"\s+", "", token)


def signatures_compatible(original_code: str, candidate_code: str) -> bool:
    """Ensure candidate code preserves the original function signature."""
    original = extract_function_signature(original_code)
    candidate = extract_function_signature(candidate_code)
    if not original or not candidate:
        return False
    if original.name != candidate.name:
        return False
    if original.is_async != candidate.is_async:
        return False
    if original.is_pub != candidate.is_pub:
        return False
    if _normalize_sig_token(original.generics) != _normalize_sig_token(candidate.generics):
        return False
    if _normalize_sig_token(original.where_clause) != _normalize_sig_token(candidate.where_clause):
        return False
    if _normalize_sig_token(original.return_type) != _normalize_sig_token(candidate.return_type):
        return False

    if len(original.params) != len(candidate.params):
        return False
    for (orig_name, orig_type), (cand_name, cand_type) in zip(
        original.params, candidate.params
    ):
        if _normalize_sig_token(orig_name) != _normalize_sig_token(cand_name):
            return False
        if _normalize_sig_token(orig_type) != _normalize_sig_token(cand_type):
            return False
    return True


def replace_line_range(
    content: str, start_line: int, end_line: int, replacement: str
) -> str | None:
    """Replace a 1-based inclusive line range with replacement text."""
    if start_line < 1 or end_line < start_line:
        return None
    lines = content.splitlines()
    if end_line > len(lines):
        return None
    replacement_lines = replacement.splitlines()
    new_lines = lines[: start_line - 1] + replacement_lines + lines[end_line:]
    new_content = "\n".join(new_lines)
    if content.endswith("\n"):
        new_content += "\n"
    return new_content


async def validate_with_cargo_check(
    *,
    crate_dir: Path,
    file_path: str,
    start_line: int,
    end_line: int,
    replacement: str,
    cargo_env: dict[str, str] | None = None,
    timeout: int = 120,
    require_rustfmt: bool = False,
    sandbox_mode: str = "auto",
) -> tuple[bool, str]:
    """Patch code into a crate and run cargo check (and optional rustfmt)."""
    if not crate_dir or not file_path:
        return False, "missing_crate_or_path"
    target_path = crate_dir / file_path
    if not target_path.exists():
        return False, "file_not_found"

    lock = _get_crate_lock(crate_dir)
    async with lock:
        try:
            original = target_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return False, "read_failed"

        patched = replace_line_range(original, start_line, end_line, replacement)
        if patched is None:
            return False, "line_replace_failed"

        try:
            target_path.write_text(patched, encoding="utf-8")
            check_cmd = utils.build_cargo_command("check", "--quiet")
            options = sandbox.SandboxOptions(
                mode=sandbox_mode,
                network_enabled=False,
                extra_whitelist=[crate_dir],
            )
            target_dir = None
            if cargo_env:
                target_dir = cargo_env.get("CARGO_TARGET_DIR")
            if target_dir:
                options.extra_whitelist.append(Path(target_dir))

            result = await sandbox.run_sandboxed_command_async(
                check_cmd,
                cwd=crate_dir,
                timeout=timeout,
                env=cargo_env,
                options=options,
            )
            if result.returncode != 0:
                return False, "cargo_check_failed"
            if require_rustfmt:
                fmt_cmd = utils.build_cargo_command("fmt", "--check")
                fmt = await sandbox.run_sandboxed_command_async(
                    fmt_cmd,
                    cwd=crate_dir,
                    timeout=timeout,
                    env=cargo_env,
                    options=options,
                )
                if fmt.returncode != 0:
                    return False, "rustfmt_failed"
            return True, "ok"
        except Exception:
            return False, "cargo_check_error"
        finally:
            try:
                target_path.write_text(original, encoding="utf-8")
            except Exception as exc:
                logger.warning(
                    "Failed to restore original file %s: %s", target_path, exc
                )


def stub_function_body(code: str) -> str | None:
    """Replace a function body with a todo!() stub."""
    if not code:
        return None
    code_bytes = code.encode("utf-8")
    try:
        import tree_sitter_rust as ts_rust
        from tree_sitter import Language, Parser

        rust_language = Language(ts_rust.language())
        try:
            parser = Parser(rust_language)
        except TypeError:
            parser = Parser()
            parser.set_language(rust_language)
        tree = parser.parse(code.encode("utf-8"))
        root = tree.root_node
        for child in root.children:
            if child.type != "function_item":
                continue
            body = child.child_by_field_name("body")
            if body is None:
                continue
            stub = "{\n    todo!()\n}"
            prefix = code_bytes[: body.start_byte]
            suffix = code_bytes[body.end_byte :]
            try:
                prefix_text = prefix.decode("utf-8")
            except UnicodeDecodeError:
                prefix_text = prefix.decode("utf-8", errors="ignore")
            try:
                suffix_text = suffix.decode("utf-8")
            except UnicodeDecodeError:
                suffix_text = suffix.decode("utf-8", errors="ignore")
            return prefix_text + stub + suffix_text
    except Exception:
        pass

    open_brace = code.find("{")
    close_brace = code.rfind("}")
    if open_brace == -1 or close_brace == -1 or close_brace <= open_brace:
        return None
    return code[:open_brace] + "{\n    todo!()\n}" + code[close_brace + 1 :]


__all__ = [
    "normalize_llm_code",
    "classify_chunk_type",
    "has_single_top_level_item",
    "signatures_compatible",
    "extract_function_item",
    "validate_with_cargo_check",
    "stub_function_body",
]
