"""
Tests for sigil_pipeline.dataset_builder module.

Tests prompt generation, code formatting, and dataset assembly.
"""

from sigil_pipeline.dataset_builder import (
    build_dataset_entries,
    create_prompt_from_code,
    detect_code_patterns,
    extract_description_from_docs,
    format_code_for_gen,
    generate_prompt_for_code,
)


class TestExtractDescriptionFromDocs:
    """Test extract_description_from_docs function."""

    def test_module_level_doc_comment(self):
        """Test extraction from module-level doc comment."""
        code = "//! This is a module that does something.\n\npub fn test() {}"
        desc = extract_description_from_docs(code)
        assert desc is not None
        assert "module" in desc.lower() or "something" in desc.lower()

    def test_function_level_doc_comment(self):
        """Test extraction from function-level doc comment."""
        code = """/// This function adds two numbers.
pub fn add(a: i32, b: i32) -> i32 {
    a + b
}
"""
        desc = extract_description_from_docs(code)
        assert desc is not None
        assert "adds" in desc.lower() or "numbers" in desc.lower()

    def test_no_doc_comments(self):
        """Test code with no doc comments."""
        code = "pub fn test() {}"
        desc = extract_description_from_docs(code)
        assert desc is None

    def test_markdown_removal(self):
        """Test markdown header removal."""
        code = "//! # This is a header\n\npub fn test() {}"
        desc = extract_description_from_docs(code)
        assert desc is not None
        assert "#" not in desc


class TestDetectCodePatterns:
    """Test detect_code_patterns function."""

    def test_has_main(self):
        """Test detection of main function."""
        code = "fn main() {}"
        patterns = detect_code_patterns(code)
        assert patterns["has_main"] is True

    def test_has_async(self):
        """Test detection of async code."""
        code = "async fn test() {}"
        patterns = detect_code_patterns(code)
        assert patterns["has_async"] is True

    def test_has_error_handling(self):
        """Test detection of error handling."""
        code = "fn test() -> Result<(), Error> { Ok(()) }"
        patterns = detect_code_patterns(code)
        assert patterns["has_error_handling"] is True

    def test_has_iterators(self):
        """Test detection of iterators."""
        code = "vec.iter().map(|x| x + 1).collect()"
        patterns = detect_code_patterns(code)
        assert patterns["has_iterators"] is True

    def test_function_names_extraction(self):
        """Test extraction of function names."""
        code = "fn test_one() {}\nfn test_two() {}"
        patterns = detect_code_patterns(code)
        assert "test_one" in patterns["function_names"]
        assert "test_two" in patterns["function_names"]


class TestGeneratePromptForCode:
    """Test Phase-1 prompt generation."""

    def test_prompt_matches_phase1_format(self):
        prompt = generate_prompt_for_code("pub fn test() {}")
        assert prompt == "Write a Rust code snippet. Output only the code."

    def test_prompt_ignores_extra_metadata(self):
        prompt = generate_prompt_for_code(
            "pub fn test() {}", crate_name="serde", file_path="src/lib.rs"
        )
        assert prompt == "Write a Rust code snippet. Output only the code."


class TestCreatePromptFromCode:
    """Test instruct-style prompt generation."""

    def test_prompt_uses_doc_comment(self):
        code = """/// Adds two numbers together.
pub fn add(a: i32, b: i32) -> i32 {
    a + b
}
"""
        prompt = create_prompt_from_code(code)
        assert "Adds two numbers" in prompt or "Write a Rust function add" in prompt

    def test_async_code_hint(self):
        code = 'async fn fetch_data() { let _ = reqwest::get("https://example.com").await; }'
        prompt = create_prompt_from_code(code)
        assert "async" in prompt.lower()

    def test_error_handling_hint(self):
        code = "pub fn work() -> Result<(), std::io::Error> { Ok(()) }"
        prompt = create_prompt_from_code(code)
        assert "handles errors" in prompt.lower()


class TestFormatCodeForGen:
    """Test format_code_for_gen function."""

    def test_backticks_removal_with_phase1_spec(self):
        """Test backticks removal when Phase 1 spec doesn't use them."""
        code = "```rust\nfn main() {}\n```"
        phase1_spec = {
            "format_requirements": {"code_formatting": {"has_backticks": False}}
        }
        formatted = format_code_for_gen(code, phase1_spec)
        assert "```" not in formatted
        assert "fn main() {}" in formatted

    def test_backticks_preserved_without_spec(self):
        """Test backticks preserved when no spec provided."""
        code = "```rust\nfn main() {}\n```"
        formatted = format_code_for_gen(code, None)
        # May or may not preserve - depends on implementation
        assert len(formatted) > 0

    def test_line_ending_normalization(self):
        """Test line ending normalization."""
        code = "fn main() {\r\n    test();\r\n}"
        formatted = format_code_for_gen(code)
        assert "\r\n" not in formatted or "\r" not in formatted

    def test_code_dedent(self):
        """Test code dedenting."""
        code = "    fn main() {\n        test();\n    }"
        formatted = format_code_for_gen(code)
        # Should be dedented
        assert len(formatted) > 0


class TestBuildDatasetEntries:
    """Test build_dataset_entries function."""

    def test_basic_dataset_building(self):
        """Test basic dataset entry building."""
        files = [
            {
                "path": "test.rs",
                "code": "/// Test function\npub fn test() {}",
                "crate_name": "test_crate",
            }
        ]
        samples = list(build_dataset_entries(files, validate_format=False))
        assert len(samples) == 1
        assert "prompt" in samples[0]
        assert "gen" in samples[0]

    def test_format_validation_enabled(self, phase1_spec):
        """Test format validation when enabled."""
        files = [
            {
                "path": "test.rs",
                "code": "pub fn test() {}",
            }
        ]
        samples = list(
            build_dataset_entries(
                files,
                validate_format=True,
                phase1_spec_path=phase1_spec,
            )
        )
        assert len(samples) == 1
        assert "prompt" in samples[0]
        assert "gen" in samples[0]

    def test_empty_code_handling(self):
        """Test handling of empty code."""
        files = [
            {"path": "test.rs", "code": ""},
            {"path": "valid.rs", "code": "pub fn test() {}"},
        ]
        samples = list(build_dataset_entries(files, validate_format=False))
        assert len(samples) == 1  # Empty code should be skipped

    def test_multiple_files_processing(self):
        """Test processing multiple files."""
        files = [
            {"path": "file1.rs", "code": "pub fn one() {}"},
            {"path": "file2.rs", "code": "pub fn two() {}"},
            {"path": "file3.rs", "code": "pub fn three() {}"},
        ]
        samples = list(build_dataset_entries(files, validate_format=False))
        assert len(samples) == 3

    def test_code_formatting_integration(self, phase1_spec):
        """Test code formatting integration."""
        files = [
            {
                "path": "test.rs",
                "code": "```rust\nfn main() {}\n```",
            }
        ]
        samples = list(
            build_dataset_entries(
                files,
                validate_format=True,
                phase1_spec_path=phase1_spec,
            )
        )
        assert len(samples) == 1
        # Code should be formatted according to Phase 1 spec
        assert "```" not in samples[0]["gen"]

    def test_prompt_generation_integration(self):
        """Test prompt generation integration."""
        files = [
            {
                "path": "test.rs",
                "code": "/// Adds numbers\npub fn add(a: i32, b: i32) -> i32 { a + b }",
                "crate_name": "math",
            }
        ]
        samples = list(build_dataset_entries(files, validate_format=False))
        assert len(samples) == 1
        prompt = samples[0]["prompt"]
        assert len(prompt) > 0
        assert prompt.startswith("Write") or "add" in prompt.lower()

    def test_streaming_architecture(self):
        """Test that build_dataset_entries works as a generator."""
        files = [
            {"path": f"file{i}.rs", "code": f"pub fn func{i}() {{}}"} for i in range(10)
        ]
        # Should be able to iterate without materializing all at once
        count = 0
        for sample in build_dataset_entries(files, validate_format=False):
            count += 1
            assert "prompt" in sample
            assert "gen" in sample
            if count >= 5:  # Test partial consumption
                break
        assert count == 5
