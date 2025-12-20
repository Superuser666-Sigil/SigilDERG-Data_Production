"""
Tests for prompt_templates.py.

Covers rendering of prompts for each task type.
"""

from sigil_pipeline.prompt_templates import (
    render_code_gen_prompt,
    render_error_fix_prompt,
    render_explanation_prompt,
)


def test_render_code_gen_prompt():
    prompt = render_code_gen_prompt(
        context="use std::fmt;",
        instruction="Fill in the missing code.",
        signature="fn greet() -> String { todo!() }",
    )
    assert "Context" in prompt
    assert "Fill in the missing code" in prompt
    assert "fn greet" in prompt


def test_render_error_fix_prompt():
    prompt = render_error_fix_prompt(
        context="use std::fmt;",
        instruction="Fix the compiler error.",
        broken_code="fn greet() { let _ = missing; }",
    )
    assert "Fix the compiler error" in prompt
    assert "missing" in prompt


def test_render_explanation_prompt():
    prompt = render_explanation_prompt(
        context="use std::fmt;",
        instruction="Explain this code.",
        code='fn greet() { println!("hi"); }',
    )
    assert "Explain this code" in prompt
    assert "println" in prompt
