"""
Tests for sigil_pipeline.ast_patterns module.

Tests AST-based extraction of contextual headers for Rust code.
"""

from sigil_pipeline.ast_patterns import extract_context_header


def test_extract_context_header_collects_imports_and_types():
    code = """
use std::fmt;

const MAX: usize = 10;

struct Widget {
    id: usize,
}

fn helper() {}
"""
    context = extract_context_header(code)
    assert "use std::fmt" in context
    assert "const MAX" in context
    assert "struct Widget" in context
    assert "fn helper" not in context


def test_extract_context_header_handles_empty():
    code = "fn main() {}"
    context = extract_context_header(code)
    assert context == ""
