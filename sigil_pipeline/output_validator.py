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

# Multiple patterns for extracting code from markdown fences
_CODE_FENCE_RE = re.compile(r"```(?:rust|rs)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_CODE_FENCE_TRIPLE_RE = re.compile(r"```(?:rust|rs)?\n(.*?)\n```", re.DOTALL)
_CODE_FENCE_START_RE = re.compile(
    r"^```(?:rust|rs)?\s*\n?", re.IGNORECASE | re.MULTILINE
)
_CODE_FENCE_END_RE = re.compile(r"\n?```\s*$", re.MULTILINE)

_CODEGEN_DISALLOWED_RE = re.compile(
    "(?:```|\\bhere is\\b|\\.{3}|\\u2026)", re.IGNORECASE
)
_CRATE_LOCKS: dict[str, asyncio.Lock] = {}

# Patterns for LLM preamble/postamble that should be stripped
_LLM_PREAMBLE_PATTERNS = [
    re.compile(r"^(?:Here(?:'s| is) (?:the|a|my) .*?:?\s*\n)", re.IGNORECASE),
    re.compile(r"^(?:The (?:completed|updated|refactored) .*?:?\s*\n)", re.IGNORECASE),
    re.compile(
        r"^(?:I've (?:completed|updated|refactored|implemented) .*?:?\s*\n)",
        re.IGNORECASE,
    ),
    re.compile(r"^(?:Sure[,!]? .*?:?\s*\n)", re.IGNORECASE),
    re.compile(r"^(?:Certainly[,!]? .*?:?\s*\n)", re.IGNORECASE),
]
_LLM_POSTAMBLE_PATTERNS = [
    re.compile(r"\n(?:This (?:function|code|implementation) .*?)$", re.IGNORECASE),
    re.compile(r"\n(?:The (?:function|code|implementation) .*?)$", re.IGNORECASE),
    re.compile(r"\n(?:Note:? .*?)$", re.IGNORECASE),
    re.compile(r"\n(?:Explanation:? .*?)$", re.IGNORECASE),
]

# Pattern to detect if text looks like Rust code
_RUST_CODE_INDICATORS = re.compile(
    r"(?:^|\s)(?:fn\s|pub\s+fn\s|async\s+fn\s|impl\s|struct\s|enum\s|trait\s|"
    r"let\s|mut\s|use\s|mod\s|type\s|const\s|static\s|match\s|\->\s)"
)


def _looks_like_rust_code(text: str) -> bool:
    """Check if text appears to be Rust code rather than natural language."""
    if not text:
        return False
    # Must have at least one Rust keyword/pattern
    if not _RUST_CODE_INDICATORS.search(text):
        return False
    # Should have braces for function bodies
    if "{" not in text:
        return False
    # Ratio of code-like characters should be high
    code_chars = sum(1 for c in text if c in "{}();:,<>[]&*!?=+-")
    if len(text) > 20 and code_chars < len(text) * 0.02:
        return False
    return True


# Patterns that indicate hallucinated/placeholder code from smaller LLMs
_HALLUCINATION_PATTERNS = [
    # Placeholder implementations
    re.compile(r"\btodo!\s*\(\s*\)", re.IGNORECASE),
    re.compile(r"\bunimplemented!\s*\(\s*\)", re.IGNORECASE),
    re.compile(r"//\s*(?:TODO|FIXME|XXX|HACK)\b", re.IGNORECASE),
    re.compile(
        r"//\s*(?:implement|implementation)\s+(?:here|goes|todo)", re.IGNORECASE
    ),
    # Hallucinated std methods that don't exist
    re.compile(r"\.to_result\s*\(\s*\)"),
    re.compile(r"\.into_result\s*\(\s*\)"),
    re.compile(r"\.to_option\s*\(\s*\)"),
    re.compile(r"\.as_result\s*\(\s*\)"),
    re.compile(r"\.unwrap_safe\s*\(\s*\)"),
    re.compile(r"\.safe_unwrap\s*\(\s*\)"),
    # Common hallucinated trait methods
    re.compile(r"\.to_bytes\s*\(\s*\)"),  # Often hallucinated on String
    re.compile(r"String::from_bytes\s*\("),  # Doesn't exist
    re.compile(r"\.into_bytes_vec\s*\(\s*\)"),
    # Empty/stub function bodies
    re.compile(r"\{\s*\}$"),  # Just empty braces at end
    re.compile(r"\{\s*//.*\s*\}$"),  # Just a comment in body
]

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


def detect_hallucinations(code: str) -> list[str]:
    """Detect common hallucination patterns in LLM-generated code.

    Returns a list of detected hallucination pattern descriptions.
    An empty list means no obvious hallucinations were detected.
    """
    if not code:
        return []

    detected: list[str] = []
    for pattern in _HALLUCINATION_PATTERNS:
        if pattern.search(code):
            # Get a readable description of what was matched
            pattern_str = pattern.pattern
            if "todo!" in pattern_str.lower():
                detected.append("contains_todo_macro")
            elif "unimplemented!" in pattern_str.lower():
                detected.append("contains_unimplemented_macro")
            elif "TODO" in pattern_str or "FIXME" in pattern_str:
                detected.append("contains_todo_comment")
            elif "to_result" in pattern_str or "into_result" in pattern_str:
                detected.append("hallucinated_result_method")
            elif "to_option" in pattern_str:
                detected.append("hallucinated_option_method")
            elif "unwrap_safe" in pattern_str or "safe_unwrap" in pattern_str:
                detected.append("hallucinated_unwrap_method")
            elif "to_bytes" in pattern_str or "from_bytes" in pattern_str:
                detected.append("hallucinated_bytes_method")
            elif r"\{\s*\}$" in pattern_str or r"\{\s*//.*\s*\}$" in pattern_str:
                detected.append("empty_function_body")
            else:
                detected.append("placeholder_code")

    return detected


def normalize_llm_code(text: str | None, *, task_type: str | None = None) -> str | None:
    """Extract and normalize code from an LLM response.

    This function aggressively cleans LLM output by:
    1. Extracting code from markdown fences
    2. Stripping common LLM preamble/postamble text
    3. Removing stray fence markers
    4. Validating the result is actual Rust code
    """
    if not text:
        return None

    original = text

    # First, try to extract from markdown code fences
    match = _CODE_FENCE_RE.search(text)
    if match:
        text = match.group(1)
    else:
        # Try alternative fence patterns
        match = _CODE_FENCE_TRIPLE_RE.search(text)
        if match:
            text = match.group(1)
        else:
            # Strip fence markers if they exist at start/end
            text = _CODE_FENCE_START_RE.sub("", text)
            text = _CODE_FENCE_END_RE.sub("", text)

    # Strip LLM preamble (e.g., "Here's the completed function:")
    for pattern in _LLM_PREAMBLE_PATTERNS:
        text = pattern.sub("", text)

    # Strip LLM postamble (e.g., "This function implements...")
    for pattern in _LLM_POSTAMBLE_PATTERNS:
        text = pattern.sub("", text)

    # Remove any remaining backticks that might be stray
    text = text.replace("```rust", "").replace("```rs", "").replace("```", "")

    cleaned = text.strip()

    # Validate it looks like Rust code (has fn, impl, struct, etc.)
    if cleaned and not _looks_like_rust_code(cleaned):
        # If it doesn't look like code, the original might have been better
        # Try to salvage from original
        if _looks_like_rust_code(original.strip()):
            cleaned = original.strip()

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


def postprocess_llm_output(code: str) -> str:
    """Apply post-processing fixes to common LLM output issues.

    Attempts to fix:
    - Stray markdown artifacts
    - Extra whitespace issues
    - Common syntax errors from LLMs
    """
    if not code:
        return code

    # Remove stray markdown that might have slipped through
    code = code.replace("```rust", "").replace("```rs", "").replace("```", "")

    # Fix common LLM issues: extra newlines at start/end
    code = code.strip()

    # Fix: LLMs sometimes add trailing semicolons after function bodies
    if code.endswith("};"):
        code = code[:-1]

    # Fix: LLMs sometimes duplicate closing braces
    lines = code.splitlines()
    if len(lines) >= 2 and lines[-1].strip() == "}" and lines[-2].strip() == "}":
        # Check if this is actually a double closing brace issue
        open_count = code.count("{")
        close_count = code.count("}")
        if close_count > open_count:
            code = "\n".join(lines[:-1])

    # Fix: Extra blank lines inside function body (more than 2 consecutive)
    while "\n\n\n" in code:
        code = code.replace("\n\n\n", "\n\n")

    return code


def is_placeholder_code(code: str) -> bool:
    """Check if code is just a placeholder without real implementation."""
    if not code:
        return True

    code_stripped = code.strip()

    # Check for placeholder macros
    if "todo!()" in code or "unimplemented!()" in code:
        return True

    # Check for placeholder comments indicating no implementation
    placeholder_comments = [
        "// implementation here",
        "// implement here",
        "// todo",
        "// add implementation",
        "// your code here",
        "/* implement */",
        "// ...",
    ]
    code_lower = code.lower()
    for comment in placeholder_comments:
        if comment in code_lower:
            return True

    # Check if function body is essentially empty
    # Match pattern like: fn name(...) { } or fn name(...) -> T { }
    if re.search(r"fn\s+\w+\s*\([^)]*\)[^{]*\{\s*\}$", code_stripped):
        return True

    # Check if body is just a comment
    if re.search(r"\{\s*//[^\n]*\s*\}$", code_stripped):
        return True

    return False


def extract_function_item(code: str, original_code: str | None = None) -> str | None:
    """Extract a single function item from code, optionally matching the original signature."""
    if not code:
        return None

    # Apply post-processing first
    code = postprocess_llm_output(code)

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
    if _normalize_sig_token(original.generics) != _normalize_sig_token(
        candidate.generics
    ):
        return False
    if _normalize_sig_token(original.where_clause) != _normalize_sig_token(
        candidate.where_clause
    ):
        return False
    if _normalize_sig_token(original.return_type) != _normalize_sig_token(
        candidate.return_type
    ):
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
