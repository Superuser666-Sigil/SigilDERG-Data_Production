"""
Refactored Task Generator - Quality over Quantity.
Removes unsafe regex transformations and synthetic errors.
"""

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
_TS_PARSER = None


def _get_ts_parser():
    global _TS_PARSER
    if _TS_PARSER is not None:
        return _TS_PARSER
    try:
        import tree_sitter_rust as tst_rust
        from tree_sitter import Language, Parser
    except Exception:
        return None
    try:
        rust_language = Language(tst_rust.language())
        try:
            parser = Parser(rust_language)
        except TypeError:
            parser = Parser()
            parser.set_language(rust_language)
        _TS_PARSER = parser
        return _TS_PARSER
    except Exception:
        return None


def _iter_nodes(node: Any):
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        children = getattr(current, "children", None)
        if children:
            stack.extend(reversed(children))


def _find_function_block(code: str) -> Any | None:
    parser = _get_ts_parser()
    if parser is None:
        return None
    try:
        tree = parser.parse(code.encode("utf-8"))
    except Exception:
        return None
    root = tree.root_node
    if getattr(root, "has_error", False):
        return None
    for node in _iter_nodes(root):
        if node.type != "function_item":
            continue
        block_node = None
        if hasattr(node, "child_by_field_name"):
            block_node = node.child_by_field_name("body")
        if block_node is None:
            block_node = next(
                (child for child in node.children if child.type == "block"), None
            )
        if block_node is not None:
            return block_node
    return None


def _block_inner_indent(code: str, block_node: Any) -> str:
    code_bytes = code.encode("utf-8")
    block_bytes = code_bytes[block_node.start_byte : block_node.end_byte]
    block_text = block_bytes.decode("utf-8", errors="ignore")
    lines = block_text.splitlines()
    for line in lines[1:]:
        stripped = line.lstrip()
        if not stripped or stripped == "}":
            continue
        return line[: len(line) - len(stripped)]
    return "    "


def _unique_ident(code: str, base: str) -> str:
    if base not in code:
        return base
    idx = 1
    while f"{base}_{idx}" in code:
        idx += 1
    return f"{base}_{idx}"


def _inject_ast_borrow_conflict(code: str) -> str | None:
    block_node = _find_function_block(code)
    if block_node is None:
        return None
    code_bytes = code.encode("utf-8")
    insert_pos = code_bytes.rfind(b"}", block_node.start_byte, block_node.end_byte)
    if insert_pos == -1:
        return None
    indent = _block_inner_indent(code, block_node)
    value_name = _unique_ident(code, "__sigil_value")
    ref_name = _unique_ident(code, "__sigil_ref")
    mut_ref_name = _unique_ident(code, "__sigil_mut_ref")
    injection_lines = [
        f"let mut {value_name} = 1;",
        f"let {ref_name} = &{value_name};",
        f"let {mut_ref_name} = &mut {value_name};",
        f"let _ = {ref_name};",
        f"let _ = {mut_ref_name};",
    ]
    injection = "\n" + "\n".join(
        f"{indent}{line}" for line in injection_lines
    ) + "\n"
    injection_bytes = injection.encode("utf-8")
    updated = code_bytes[:insert_pos] + injection_bytes + code_bytes[insert_pos:]
    return updated.decode("utf-8", errors="ignore")


def generate_error_fixing_task(
    code: str,
    method: str = "simulate",  # 'simulate', 'real_compile', or 'both'
    crate_dir: Path | None = None,
    timeout: int = 120,
) -> dict[str, Any] | None:
    """Generate an error-fixing task.

    If method is 'simulate' we attempt simulated error injection. If
    'real_compile' and a crate_dir is provided, attempt an AST-guided
    borrow-checker injection. 'both' will try real first then fallback
    to simulated.
    """
    method = (method or "").lower()
    if method == "real_compile":
        method = "real"

    # Try real compilation when requested and available
    if method in ("real", "both") and crate_dir is not None:
        try:
            error_msg, broken_code, error_code = _inject_real_error(
                code, crate_dir, timeout
            )
            if error_msg and broken_code:
                return {
                    "prompt": f"Fix the compiler error {error_code}.",
                    "gen": code.strip(),
                    "broken": broken_code,
                }
        except Exception:
            logger.debug("Real error injection failed; falling back to simulated.")

    # Simulated injection
    if method in ("simulate", "both") or method == "":
        err_desc, broken_code, error_code = _inject_simulated_error(code)
        if err_desc and broken_code:
            return {
                "prompt": f"Fix the compiler error {error_code}: {err_desc}",
                "gen": code.strip(),
                "broken": broken_code,
            }
        # If no simulated injection, return None (no task)
    return None


def _inject_real_error(
    code: str, crate_dir: Path, timeout: int
) -> tuple[str | None, str | None, str | None]:
    """
    Injects an AST-guided borrow-checker error into the function body.
    """
    _ = crate_dir
    _ = timeout
    broken = _inject_ast_borrow_conflict(code)
    if not broken or broken == code:
        return None, None, None
    return (
        "cannot borrow value as mutable because it is also borrowed as immutable",
        broken,
        "E0502",
    )


# --- Simulated error injection helpers (regex-based, best-effort) ---


def _inject_simulated_error(code: str) -> tuple[str | None, str | None, str | None]:
    """Attempt a variety of simulated compiler error injections and return
    a tuple (description, broken_code, error_code).
    """
    if not code or not code.strip():
        return None, None, None

    # Try type mismatch
    tm = _inject_type_mismatch_error(code)
    if tm != code:
        return "type mismatch injected", tm, "E0308"

    mv = _inject_moved_value_error(code)
    if mv != code:
        return "moved value", mv, "E0382"

    br = _inject_borrow_error(code)
    if br != code:
        return "borrow after drop", br, "E0597"

    mv2 = _inject_move_error(code)
    if mv2 != code:
        return "move error", mv2, "E0507"

    fb = _inject_fallback_type_mismatch(code)
    if fb != code:
        return "type mismatch injected", fb, "E0308"

    # Nothing injected
    return None, None, None


def _inject_move_error(code: str) -> str:
    # Replace obvious `.value` access on borrowed param to a moved access name
    return re.sub(r"(\b[A-Za-z_][A-Za-z0-9_]*\.)value\b", r"\1_moved_value", code)


def _inject_moved_value_error(code: str) -> str:
    # If a variable is printed twice, insert a move before the second use
    lines = code.splitlines()
    for i in range(len(lines) - 1):
        if "println!" in lines[i] and "println!" in lines[i + 1]:
            # Insert a move between them
            m = re.search(r"let\s+([A-Za-z_][A-Za-z0-9_]*)\s*=", code)
            if m:
                var = m.group(1)
                insert = f"    let _moved_{var} = {var};"
                lines.insert(i + 1, insert)
                # Replace subsequent prints to use moved var
                lines[i + 2] = lines[i + 2].replace(f"{var}", f"_moved_{var}")
                return "\n".join(lines)
    return code


def _inject_borrow_error(code: str) -> str:
    # Look for a simple 'let x = String::from' then a println; inject borrow/drop pattern
    m = re.search(r"let\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*String::from\([^)]+\)", code)
    if not m:
        return code
    var = m.group(1)
    # Insert borrow and drop before the final println using the borrowed reference
    lines = code.splitlines()
    for idx, line in enumerate(lines):
        if f"println!" in line and var in line:
            borrow = f"    let _borrowed_{var} = &{var};"
            drop_line = f"    drop({var});"
            lines.insert(idx + 1, borrow)
            lines.insert(idx + 2, drop_line)
            # change subsequent print to use _borrowed_var
            lines[idx + 3] = lines[idx + 3].replace(var, f"_borrowed_{var}") if idx + 3 < len(lines) else lines[idx + 2]
            return "\n".join(lines)
    return code


def _inject_type_mismatch_error(code: str) -> str:
    # Replace typed integer initializers with a string literal to cause E0308
    return re.sub(
        r"(let\s+[A-Za-z_][A-Za-z0-9_]*\s*:\s*(?:i|u)\d*\s*=)\s*\d+;",
        r"\1 \"mismatch\";",
        code,
    )


def _inject_fallback_type_mismatch(code: str) -> str:
    open_brace = code.find("{")
    close_brace = code.rfind("}")
    if open_brace == -1 or close_brace <= open_brace:
        return code
    indent = "    "
    body = code[open_brace + 1 : close_brace]
    for line in body.splitlines():
        stripped = line.lstrip()
        if stripped:
            indent = line[: len(line) - len(stripped)]
            break
    injection = f"\n{indent}let __sigil_mismatch: u8 = \"mismatch\";"
    return code[: open_brace + 1] + injection + code[open_brace + 1 :]


def _looks_error_fixable(code: str, method: str | None = None) -> bool:
    # Simulated injection requires a bit more substance (>=4 lines and a let)
    lines = code.splitlines() if isinstance(code, str) else []
    if method == "simulate":
        return len(lines) >= 4 and "let " in code
    if method in ("real", "real_compile"):
        return len(lines) >= 4
    # default heuristic
    return bool(re.search(r"let\s+[A-Za-z_][A-Za-z0-9_]*\s*:\s*[A-Za-z0-9_:<>]+\s*=", code))


def _looks_explainable(code: str, doc_comment: str | None = None) -> bool:
    if doc_comment:
        return True
    return bool(re.search(r"\bfn\s+[A-Za-z_][A-Za-z0-9_]*\b", code or ""))


def _looks_transformable(code: str, patterns: dict | None = None) -> bool:
    if patterns and patterns.get("has_io"):
        return True
    if "unwrap" in (code or ""):
        return True
    if "match" in (code or ""):
        return True
    if "for " in (code or "") and "in " in (code or ""):
        return True
    return False


def _synthesize_explanation_from_code(code: str) -> str | None:
    # Try to extract function signature information
    try:
        from .ast_patterns import extract_function_signature

        sig = extract_function_signature(code)
    except Exception:
        sig = None

    if not sig:
        return None

    parts = []
    parts.append(f"This function {sig.name} ")
    if not sig.params:
        parts.append("does not take any parameters.")
    else:
        parts.append(f"takes {len(sig.params)} parameter")
        if len(sig.params) != 1:
            parts[-1] += "s"
        parts[-1] += "."

    if sig.is_async:
        parts.append("It is asynchronous and uses async/await patterns.")

    if sig.return_type and "Result" in (sig.return_type or ""):
        parts.append("It returns a Result and is fallible; handle errors appropriately.")

    return " ".join(parts)


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
        "instruction": "Generate documentation for this Rust code.",
        "input_code": code,
        "output_json": {"docstring": explanation},
        "_task_type": "explanations",
    }


# Stub functions required by imports but not used in new logic
def determine_task_capabilities(*args, **kwargs):
    # Backwards-compatible capability detection
    # Signature: (code, patterns, doc_comment, enable_error_injection, error_injection_method)
    code = args[0] if len(args) > 0 else kwargs.get("code")
    patterns = args[1] if len(args) > 1 else kwargs.get("patterns")
    doc_comment = args[2] if len(args) > 2 else kwargs.get("doc_comment")
    enable_error_injection = kwargs.get("enable_error_injection", False)
    error_injection_method = kwargs.get("error_injection_method", "simulate")

    caps = {"code_generation"}
    if _looks_transformable(code, patterns):
        caps.add("transformations")
    if _looks_explainable(code, doc_comment):
        caps.add("explanations")
    if enable_error_injection and _looks_error_fixable(code, error_injection_method):
        caps.add("error_fixing")
    return caps


def select_task_type_with_quota(*args, **kwargs):
    # Signature: (task_mix, available, counts)
    if args:
        task_mix = args[0]
        available = args[1] if len(args) > 1 else None
        counts = args[2] if len(args) > 2 else None
    else:
        task_mix = kwargs.get("task_mix", {})
        available = kwargs.get("available", None)
        counts = kwargs.get("counts", None)

    if not task_mix:
        return "code_generation"

    if available is None:
        available = set(task_mix.keys())

    counts = counts or {}
    # Compute simple deficit-aware weights
    max_count = max(counts.values()) if counts else 0
    weighted = {}
    for t, w in task_mix.items():
        if t not in available:
            continue
        deficit = max_count - counts.get(t, 0)
        score = max(0.0, float(w)) + float(deficit) * 0.01
        weighted[t] = score

    if not weighted:
        return "code_generation"

    # Normalize and choose randomly
    total = sum(weighted.values())
    import random

    rnd = random.random()
    upto = 0.0
    for t, s in weighted.items():
        upto += s / total
        if rnd <= upto:
            return t
    return next(iter(weighted))


def select_task_type(arg, patterns: dict | None = None) -> str | None:
    """Dual-purpose selector.

    If `arg` is a dict, treat it as a task_mix mapping task->weight and
    select a task from that distribution. Otherwise, `arg` is treated as
    source code and heuristics are used to pick a task type.
    """
    # If arg is a mapping, interpret as task_mix
    if isinstance(arg, dict):
        task_mix = arg
        if not task_mix:
            return "code_generation"
        import random

        total = sum(float(v) for v in task_mix.values())
        if total <= 0:
            return next(iter(task_mix))
        r = random.random() * total
        upto = 0.0
        for t, w in task_mix.items():
            upto += float(w)
            if r <= upto:
                return t
        return next(iter(task_mix))

    # Otherwise, run heuristics on code
    code = arg
    if not code:
        return None
    if _looks_error_fixable(code):
        return "error_fixing"
    if _looks_transformable(code, patterns):
        return "transformations"
    if _looks_explainable(code):
        return "explanations"
    return "code_generation"
