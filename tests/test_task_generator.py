"""
Tests for sigil_pipeline.task_generator module.

Tests task generation for transformations, explanations, and error fixing guardrails.
"""

from pathlib import Path

from sigil_pipeline.task_generator import (
    generate_error_fixing_task,
    generate_explanation_task,
    generate_transformation_task,
)


class TestGenerateTransformationTask:
    """Test generate_transformation_task function."""

    def test_transformations_disabled(self):
        """Transformations are disabled to avoid unsafe regex edits."""
        code = "pub fn add(a: i32, b: i32) -> i32 { a + b }"
        result = generate_transformation_task(code)
        assert result is None


class TestGenerateExplanationTask:
    """Test generate_explanation_task function."""

    def test_explanation_requires_doc_comment(self):
        code = "pub fn add(a: i32, b: i32) -> i32 { a + b }"
        result = generate_explanation_task(code, None)
        assert result is None

    def test_explanation_with_doc_comment(self):
        code = "/// Adds two numbers.\npub fn add(a: i32, b: i32) -> i32 { a + b }"
        result = generate_explanation_task(code, "Adds two numbers.")
        assert result is not None
        assert result["output_json"]["explanation"] == "Adds two numbers."


class TestGenerateErrorFixingTask:
    """Test generate_error_fixing_task function."""

    def test_error_fixing_requires_crate_and_path(self):
        code = "pub fn add(a: i32, b: i32) -> i32 { a + b }"
        result = generate_error_fixing_task(code, method="real_compile")
        assert result is None

        result = generate_error_fixing_task(
            code,
            method="real_compile",
            crate_dir=Path("/tmp"),
            file_path=None,
        )
        assert result is None
