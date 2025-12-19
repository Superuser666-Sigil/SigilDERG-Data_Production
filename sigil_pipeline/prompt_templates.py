"""
Prompt template module for JSON-based instruction tuning.

Provides Jinja2-style templates that enforce strict JSON output schemas.
Removes legacy randomization to ensure consistent, high-quality instruction following.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.5.0
"""

import logging

from jinja2 import Environment, select_autoescape

logger = logging.getLogger(__name__)

# Jinja2 environment with autoescaping enabled to avoid unsafe template rendering.
jinji_env = Environment(autoescape=select_autoescape(default=True))

# Standard System Prompt
SYSTEM_PROMPT = "You are a Rust engineering assistant. Output valid JSON."

# Template for Code Generation
# Input: context, instruction, code_signature
# Output: JSON with 'code' key
CODE_GEN_TEMPLATE = jinji_env.from_string(
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
ERROR_FIX_TEMPLATE = jinji_env.from_string(
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
EXPLANATION_TEMPLATE = jinji_env.from_string(
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
