"""
Refactored Task Generator - Quality over Quantity.
Removes unsafe regex transformations and synthetic errors.
"""
import logging
import random
import subprocess
import tempfile
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

def generate_transformation_task(code: str, patterns: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """
    DISABLED: Regex transformations generate invalid Rust code.
    Returns None to prevent generation of broken training data.
    """
    return None

def generate_error_fixing_task(
    code: str,
    method: str,  # retained for compatibility signature
    crate_dir: Path | None = None,
    timeout: int = 120,
) -> dict[str, Any] | None:
    """
    Generate an error-fixing task using REAL compilation only.
    """
    if not crate_dir:
        return None

    # Only use real compilation. Synthetic errors teach bad debugging habits.
    try:
        error_msg, broken_code, error_code = _inject_real_error(code, crate_dir, timeout)
        
        if error_msg and broken_code:
            return {
                "instruction": f"Fix the compiler error {error_code}.",
                "input_code": broken_code,
                "output_json": {
                    "fixed_code": code,
                    "explanation": f"The code failed with {error_code}: {error_msg}",
                    "error_message": error_msg
                },
                "_task_type": "bug_detection"
            }
    except Exception as e:
        logger.debug(f"Real error injection failed: {e}")

    return None

def _inject_real_error(
    code: str, crate_dir: Path, timeout: int
) -> tuple[str | None, str | None, str | None]:
    """
    Injects a temporary breakage and runs cargo check.
    Currently disabled (returns None) until AST-based breakage is implemented
    to ensure we don't just generate syntax errors.
    """
    # Placeholder: Implement AST-based lifetime deletion here.
    return None, None, None

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
        "output_json": {
            "docstring": explanation
        },
        "_task_type": "docstring_generation"
    }

# Stub functions required by imports but not used in new logic
def determine_task_capabilities(*args, **kwargs): return {"code_generation"}
def select_task_type_with_quota(*args, **kwargs): return "code_generation"