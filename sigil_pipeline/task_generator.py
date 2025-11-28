"""
Task type generation module for Phase-2 dataset.

Generates diverse task types: code generation, transformations, error-fixing, and explanations.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.1.0
"""

import logging
import random
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

# Import functions directly to avoid circular import
# These are used in task generation but defined in dataset_builder
# We'll import them locally when needed

logger = logging.getLogger(__name__)


def generate_transformation_task(
    code: str, patterns: dict[str, Any] | None = None
) -> dict[str, str] | None:
    """
    Generate a transformation task from code.

    Args:
        code: Original code snippet
        patterns: Detected code patterns (optional, will detect if not provided)

    Returns:
        Dict with 'prompt' and 'gen' keys, or None if transformation not applicable
    """
    # Import locally to avoid circular import
    if patterns is None:
        from .dataset_builder import detect_code_patterns

        patterns = detect_code_patterns(code)

    # Sync -> Async transformation
    if not patterns.get("has_async") and ("fn " in code or "fn main" in code):
        # Check if function could be async (has I/O, networking, etc.)
        if patterns.get("has_io") or patterns.get("has_networking"):
            fn_match = re.search(
                r"(?:pub\s+)?fn\s+(\w+)\s*\(([^)]*)\)\s*(?:->\s*([^{]+))?",
                code,
            )
            if fn_match:
                fn_name = fn_match.group(1)

                # Simple async transformation (add async, use tokio runtime)
                transformed = code
                transformed = re.sub(
                    r"(?:pub\s+)?fn\s+",
                    r"pub async fn ",
                    transformed,
                    count=1,
                )

                # Add tokio::main if it's main function
                if "fn main" in transformed:
                    transformed = "#[tokio::main]\n" + transformed

                prompt = f"Convert this synchronous function {fn_name} into an async version using Tokio."
                return {"prompt": prompt, "gen": transformed.strip()}

    # Match -> ? operator transformation
    if "match " in code and "Result<" in code:
        # Find match expressions on Result types
        match_pattern = re.compile(
            r"match\s+(\w+)\s*\{[^}]*Ok\(([^)]+)\)\s*=>\s*([^,}]+),?\s*Err\(([^)]+)\)\s*=>\s*([^}]+)\}",
            re.DOTALL,
        )
        match_obj = match_pattern.search(code)
        if match_obj:
            ok_expr = match_obj.group(3).strip()

            # Transform to ? operator
            transformed = code
            # Replace the match with ? operator (simplified)
            transformed = re.sub(
                match_pattern,
                f"{ok_expr}?",
                transformed,
            )

            prompt = "Convert this match expression to use the ? operator for error handling."
            return {"prompt": prompt, "gen": transformed.strip()}

    # unwrap() -> explicit match propagation
    if "Result<" in code and ".unwrap()" in code:
        unwrap_match = re.search(r"([A-Za-z0-9_:\.]+)\.unwrap\(\)", code)
        if unwrap_match:
            expr = unwrap_match.group(1)
            replacement = (
                f"match {expr} {{\n"
                f"    Ok(value) => value,\n"
                f"    Err(err) => return Err(err),\n"
                f"}}"
            )
            transformed = code.replace(f"{expr}.unwrap()", replacement, 1)
            prompt = "Replace unwrap calls with explicit error propagation using match blocks."
            return {"prompt": prompt, "gen": transformed.strip()}

    # Iterator transformation (loops -> iterator chains)
    if "for " in code and "in " in code and not patterns.get("has_iterators"):
        # Simple transformation: convert for loop to iterator
        # This is a simplified version - full implementation would be more complex
        loop_match = re.search(
            r"for\s+(\w+)\s+in\s+([^:]+):\s*\{([^}]+)\}",
            code,
            re.DOTALL,
        )
        if loop_match:
            var = loop_match.group(1)
            iterable = loop_match.group(2).strip()
            body = loop_match.group(3).strip()

            # Check if body is a simple operation that can be converted
            if ".push(" in body or "println!" in body:
                # Convert to iterator chain (simplified)
                transformed = code.replace(
                    f"for {var} in {iterable}:",
                    f"{iterable}.iter().for_each(|{var}|",
                )
                transformed = transformed.replace("}", "})")

                prompt = "Convert this for loop to use iterator methods."
                return {"prompt": prompt, "gen": transformed.strip()}

    return None


def generate_error_fixing_task(
    code: str,
    method: str,
    crate_dir: Path | None = None,
    timeout: int = 120,
) -> dict[str, str] | None:
    """
    Generate an error-fixing task from code.

    Args:
        code: Original code snippet
        method: Error injection method ('real_compile', 'simulate', or 'both')
        crate_dir: Optional crate directory for real compilation
        timeout: Timeout in seconds for cargo-based compilation attempts

    Returns:
        Dict with 'prompt' and 'gen' keys, or None if error injection failed
    """
    simulated_result = None

    if method in ("simulate", "both"):
        # Simulate common Rust errors - try all error types to maximize success
        error_type, broken_code, error_code = _inject_simulated_error(code)
        if error_type and broken_code:
            prompt = (
                f"This Rust code fails with error {error_code}: {error_type}. Fix it."
            )
            simulated_result = {"prompt": prompt, "gen": code.strip()}
            # If method is "simulate" only, return immediately
            if method == "simulate":
                return simulated_result

    if method in ("real_compile", "both") and crate_dir:
        # Try real compilation with timeout handling
        try:
            error_type, broken_code, error_code = _inject_real_error(
                code, crate_dir, timeout
            )
            if error_type and broken_code:
                prompt = f"This Rust code fails with error {error_code}: {error_type}. Fix it."
                return {"prompt": prompt, "gen": code.strip()}
        except Exception as e:
            logger.debug(f"Real error injection failed: {e}")
            # Fall through to return simulated result if available

    # If we have a simulated result (from "both" method), use it even if real_compile failed
    if simulated_result:
        return simulated_result

    return None


def _inject_simulated_error(
    code: str,
) -> tuple[str | None, str | None, str | None]:
    """Inject a simulated Rust compiler error.

    Tries all error types in random order until one succeeds.
    """
    error_types = [
        ("E0507", "cannot move out of borrowed content", _inject_move_error),
        ("E0382", "use of moved value", _inject_moved_value_error),
        ("E0597", "value dropped while still borrowed", _inject_borrow_error),
        ("E0308", "mismatched types", _inject_type_mismatch_error),
    ]

    # Try all error types in random order to maximize success rate
    shuffled = error_types.copy()
    random.shuffle(shuffled)

    for error_code, error_desc, inject_func in shuffled:
        try:
            broken_code = inject_func(code)
            if broken_code and broken_code != code:
                return error_desc, broken_code, error_code
        except Exception as e:
            logger.debug(f"Error injection {error_code} failed: {e}")
            continue

    return None, None, None


def _inject_move_error(code: str) -> str:
    """Inject E0507: cannot move out of borrowed content."""
    # Find a struct field access and try to move it
    pattern = r"(\w+)\.(\w+)"
    matches = list(re.finditer(pattern, code))
    if matches:
        match = random.choice(matches)
        # Create code that tries to move from borrowed reference
        # Insert a move operation before the original usage
        original_expr = match.group(0)
        broken = code.replace(
            original_expr,
            f"let _moved = {original_expr}; {original_expr}",
            1,  # Only replace first occurrence
        )
        if broken != code:
            return broken
    return code


def _inject_moved_value_error(code: str) -> str:
    """Inject E0382: use of moved value."""
    lines = code.splitlines()
    for idx, line in enumerate(lines):
        match = re.search(r"let\s+(?:mut\s+)?(\w+)\s*=\s*([^;]+);", line)
        if not match:
            continue
        var = match.group(1)
        indent_match = re.match(r"\s*", line)
        indent = indent_match.group(0) if indent_match else ""
        for j in range(idx + 1, len(lines)):
            if re.search(rf"\b{var}\b", lines[j]):
                injection = f"{indent}let _moved_{var} = {var};"
                lines.insert(j, injection)
                return "\n".join(lines)
    return code


def _inject_borrow_error(code: str) -> str:
    """Inject E0597: value dropped while still borrowed."""
    lines = code.splitlines()
    for idx, line in enumerate(lines):
        match = re.search(r"let\s+(?:mut\s+)?(\w+)\s*=\s*([^;]+);", line)
        if not match:
            continue
        var = match.group(1)
        indent_match = re.match(r"\s*", line)
        indent = indent_match.group(0) if indent_match else ""
        borrow_line = f"{indent}let _borrowed_{var} = &{var};"
        drop_line = f"{indent}drop({var});"
        use_line = f"{indent}let _still_borrowed_{var} = _borrowed_{var};"
        lines[idx : idx + 1] = [line, borrow_line, drop_line, use_line]
        return "\n".join(lines)
    return code


def _inject_type_mismatch_error(code: str) -> str:
    """Inject E0308: mismatched types by altering a literal assignment."""
    pattern = re.compile(
        r"(let\s+(?:mut\s+)?(\w+)\s*:\s*(u|i)(8|16|32|64|128|size)\s*=\s*)([^;]+);"
    )
    match = pattern.search(code)
    if not match:
        return code
    prefix = match.group(1)
    suffix = code[match.end() :]
    new_line = f'{prefix}"mismatch";'
    return code[: match.start()] + new_line + suffix


def _inject_real_error(
    code: str, crate_dir: Path, timeout: int
) -> tuple[str | None, str | None, str | None]:
    """Inject error and compile to get real compiler error."""
    try:
        # Create a temporary file with broken code
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".rs", delete=False, dir=crate_dir / "src"
        ) as f:
            f.write(code)
            temp_file = Path(f.name)

        # Try to compile
        result = subprocess.run(
            ["cargo", "check", "--message-format=json"],
            cwd=crate_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        # Parse errors
        for line in result.stdout.splitlines():
            if "error[" in line.lower():
                # Extract error code and message
                error_match = re.search(r"error\[(E\d+)\]:\s*(.+)", line)
                if error_match:
                    error_code = error_match.group(1)
                    error_msg = error_match.group(2)
                    return error_msg, code, error_code

        # Clean up
        temp_file.unlink()

    except Exception as e:
        logger.debug(f"Real error injection failed: {e}")

    return None, None, None


def generate_explanation_task(
    code: str, doc_comment: str | None = None
) -> dict[str, str] | None:
    """
    Generate an explanation task from code.

    Args:
        code: Code snippet
        doc_comment: Optional doc comment to use as explanation

    Returns:
        Dict with 'prompt' and 'gen' keys, or None if not applicable
    """
    if not doc_comment:
        # Import locally to avoid circular import
        from .dataset_builder import extract_description_from_docs

        doc_comment = extract_description_from_docs(code)
        if not doc_comment:
            doc_comment = _synthesize_explanation_from_code(code)

    if doc_comment:
        # Clean up doc comment
        explanation = doc_comment.strip()
        explanation = re.sub(r"^(///|//!)\s*", "", explanation, flags=re.MULTILINE)
        explanation = re.sub(r"\s+", " ", explanation)

        # Variation 1: Simple explanation
        if random.random() < 0.7:
            prompt = f"Explain this Rust function in simple terms:\n\n{code}"
            return {"prompt": prompt, "gen": explanation}

        # Variation 2: Explanation + usage example
        else:
            # Extract function signature for usage example
            fn_match = re.search(
                r"(?:pub\s+)?fn\s+(\w+)\s*\(([^)]*)\)",
                code,
            )
            if fn_match:
                fn_name = fn_match.group(1)
                params = fn_match.group(2)
                # Create simple usage example
                usage_example = (
                    f"// Example usage:\n// let result = {fn_name}({params});"
                )
                gen = f"{explanation}\n\n{usage_example}"
                prompt = f"Explain what this Rust function does, then show how to use it in a small example:\n\n{code}"
                return {"prompt": prompt, "gen": gen}

    return None


def select_task_type(task_type_mix: dict[str, float]) -> str:
    """
    Select a task type based on distribution.

    Args:
        task_type_mix: Dictionary mapping task types to probabilities

    Returns:
        Selected task type name
    """
    rand = random.random()
    cumulative = 0.0

    for task_type, probability in task_type_mix.items():
        cumulative += probability
        if rand <= cumulative:
            return task_type

    # Fallback to code_generation
    return "code_generation"


def determine_task_capabilities(
    code: str,
    patterns: dict[str, Any],
    doc_comment: str | None,
    *,
    enable_error_injection: bool,
    error_injection_method: str,
) -> set[str]:
    """
    Estimate which task types are feasible for the snippet before attempting generation.
    """
    capabilities = {"code_generation"}

    if _looks_transformable(code, patterns):
        capabilities.add("transformations")

    if _looks_explainable(code, doc_comment):
        capabilities.add("explanations")

    if enable_error_injection and _looks_error_fixable(code, error_injection_method):
        capabilities.add("error_fixing")

    return capabilities


def select_task_type_with_quota(
    task_type_mix: dict[str, float],
    available_tasks: set[str],
    task_counts: dict[str, int],
) -> str:
    """
    Pick the next task type while nudging toward the configured distribution.
    """
    usable_tasks = [task for task in available_tasks if task in task_type_mix]
    if not usable_tasks:
        return "code_generation"

    total_samples = sum(task_counts.values())
    weights: dict[str, float] = {}

    if total_samples > 0:
        for task in usable_tasks:
            expected = task_type_mix.get(task, 0.0) * total_samples
            actual = float(task_counts.get(task, 0))
            deficit = expected - actual
            if deficit > 0:
                weights[task] = deficit

    if not weights:
        weights = {task: task_type_mix.get(task, 0.0) for task in usable_tasks}

    if not weights:
        weights = {task: 1.0 for task in usable_tasks}

    total_weight = sum(weights.values())
    pick = random.random() * total_weight
    cumulative = 0.0
    for task, weight in weights.items():
        cumulative += weight
        if pick <= cumulative:
            return task

    return usable_tasks[-1]


def _looks_explainable(code: str, doc_comment: str | None) -> bool:
    if doc_comment and doc_comment.strip():
        return True
    return "///" in code or "//!" in code


def _looks_transformable(code: str, patterns: dict[str, Any]) -> bool:
    if not patterns.get("has_async") and ("fn " in code or "fn(" in code):
        if patterns.get("has_io") or patterns.get("has_networking"):
            return True

    if "match " in code and "Result<" in code:
        return True

    if "for " in code and " in " in code and not patterns.get("has_iterators"):
        return True

    return False


def _looks_error_fixable(code: str, method: str) -> bool:
    line_count = code.count("\n") + 1
    if line_count < 4:
        return False

    has_function = "fn " in code
    has_struct = "struct " in code
    has_enum = "enum " in code

    if method == "simulate":
        return has_function or has_struct or has_enum

    if method in {"real_compile", "both"}:
        return has_function and line_count < 400

    return False


def _synthesize_explanation_from_code(code: str) -> str | None:
    """
    Best-effort summary derived from the function signature when docs are missing.
    """
    fn_match = re.search(
        r"(?:pub\s+)?(?:async\s+)?fn\s+(\w+)\s*\(([^)]*)\)\s*(?:->\s*([^{]+))?",
        code,
    )
    if not fn_match:
        return None

    fn_name = fn_match.group(1)
    params_raw = [
        param.strip()
        for param in fn_match.group(2).split(",")
        if param and param.strip()
    ]
    if params_raw:
        param_names = [p.split(":")[0].strip() for p in params_raw]
        param_text = ", ".join(param_names)
        param_clause = f"accepts parameters {param_text}"
    else:
        param_clause = "does not take any parameters"

    return_type = fn_match.group(3).strip() if fn_match.group(3) else None
    return_clause = f" and returns {return_type}" if return_type else ""

    traits = []
    lower_code = code.lower()
    if "async fn" in lower_code:
        traits.append("asynchronous")
    if "Result<" in code:
        traits.append("fallible")
    if ".iter(" in code or "Iterator" in code:
        traits.append("iterator-based")

    trait_clause = ""
    if traits:
        trait_clause = f" It is {' and '.join(traits)}."

    return f"The function {fn_name} {param_clause}{return_clause}.{trait_clause}"
