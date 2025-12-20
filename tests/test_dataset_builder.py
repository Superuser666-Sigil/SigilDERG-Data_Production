"""
Tests for sigil_pipeline.dataset_builder module.

Tests code formatting and dataset assembly.
"""

from sigil_pipeline.dataset_builder import (
    build_dataset_entries,
    extract_description_from_docs,
    format_code_for_gen,
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


class TestFormatCodeForGen:
    """Test format_code_for_gen function."""

    def test_basic_code_formatting(self):
        """Test basic code formatting without spec."""
        code = "fn main() {}"
        formatted = format_code_for_gen(code)
        assert len(formatted) > 0
        assert "fn main() {}" in formatted

    def test_line_ending_normalization(self):
        """Test line ending normalization."""
        code = "fn main() {\r\n    test();\r\n}"
        formatted = format_code_for_gen(code)
        assert "\r\n" not in formatted or "\r" not in formatted

    def test_code_dedent(self):
        """Test code dedenting."""
        code = "    fn main() {\n        test();\n    }"
        formatted = format_code_for_gen(code)
        assert len(formatted) > 0


class TestBuildDatasetEntries:
    """Test build_dataset_entries function."""

    def test_basic_dataset_building(self):
        """Test basic dataset entry building."""
        files = [
            {
                "path": "test.rs",
                "code": "pub fn test() {}",
                "crate_name": "test_crate",
            }
        ]
        samples = list(
            build_dataset_entries(
                files, validate_format=False, task_type_mix={"code_generation": 1.0}
            )
        )
        assert len(samples) == 1
        assert "input_data" in samples[0]
        assert "output_data" in samples[0]
        assert samples[0]["input_data"]["prompt"]

    def test_empty_code_handling(self):
        """Test handling of empty code."""
        files = [
            {"path": "test.rs", "code": ""},
            {"path": "valid.rs", "code": "pub fn test() {}"},
        ]
        samples = list(build_dataset_entries(files, validate_format=False))
        assert len(samples) == 1

    def test_multiple_files_processing(self):
        """Test processing multiple files."""
        files = [
            {"path": "file1.rs", "code": "pub fn one() {}"},
            {"path": "file2.rs", "code": "pub fn two() {}"},
            {"path": "file3.rs", "code": "pub fn three() {}"},
        ]
        samples = list(build_dataset_entries(files, validate_format=False))
        assert len(samples) == 3

    def test_code_formatting_integration(self):
        """Test code formatting integration."""
        files = [
            {
                "path": "test.rs",
                "code": "fn main() {}",
            }
        ]
        samples = list(build_dataset_entries(files, validate_format=True))
        assert len(samples) == 1
        assert "fn main() {}" in samples[0]["output_data"]["code"]

    def test_scaffolded_code_generation(self):
        """Test scaffolded code generation tasks."""
        files = [
            {
                "path": "test.rs",
                "code": "pub fn add(a: i32, b: i32) -> i32 { a + b }",
            }
        ]
        samples = list(
            build_dataset_entries(
                files,
                validate_format=False,
                task_type_mix={"code_generation": 1.0},
            )
        )
        assert len(samples) == 1
        input_code = samples[0]["input_data"]["code"]
        assert "todo!" in input_code or "TODO" in input_code
        assert samples[0]["output_data"]["code"].startswith("pub fn add")

    def test_streaming_architecture(self):
        """Test that build_dataset_entries works as a generator."""
        files = [
            {"path": f"file{i}.rs", "code": f"pub fn func{i}() {{}}"} for i in range(10)
        ]
        count = 0
        for sample in build_dataset_entries(files, validate_format=False):
            count += 1
            assert "input_data" in sample
            assert "output_data" in sample
            if count >= 5:
                break
        assert count == 5

    def test_prompt_seed_in_metadata(self):
        """Test that prompt seed is stored in sample metadata."""
        files = [
            {"path": "test.rs", "code": "pub fn test() {}"},
        ]
        samples = list(
            build_dataset_entries(
                files,
                validate_format=False,
                task_type_mix={"code_generation": 1.0},
                prompt_seed=12345,
            )
        )
        assert len(samples) == 1
        assert "_prompt_seed" in samples[0]
        assert samples[0]["_prompt_seed"] == 12345

    def test_prompt_seed_reproducibility(self):
        """Test that same seed produces identical prompts."""
        files = [
            {
                "path": "test.rs",
                "code": "pub fn process(x: Vec<i32>) -> i32 { x.iter().sum() }",
            },
        ]

        samples1 = list(
            build_dataset_entries(
                files,
                validate_format=False,
                task_type_mix={"code_generation": 1.0},
                prompt_seed=42,
                enable_prompt_randomization=True,
            )
        )

        samples2 = list(
            build_dataset_entries(
                files,
                validate_format=False,
                task_type_mix={"code_generation": 1.0},
                prompt_seed=42,
                enable_prompt_randomization=True,
            )
        )

        assert (
            samples1[0]["input_data"]["prompt"] == samples2[0]["input_data"]["prompt"]
        )

    def test_randomization_disabled(self):
        """Test that disabling randomization produces deterministic prompts."""
        files = [
            {"path": "test.rs", "code": "pub fn add(a: i32, b: i32) -> i32 { a + b }"},
        ]

        samples1 = list(
            build_dataset_entries(
                files,
                validate_format=False,
                task_type_mix={"code_generation": 1.0},
                enable_prompt_randomization=False,
            )
        )

        samples2 = list(
            build_dataset_entries(
                files,
                validate_format=False,
                task_type_mix={"code_generation": 1.0},
                enable_prompt_randomization=False,
            )
        )

        assert (
            samples1[0]["input_data"]["prompt"] == samples2[0]["input_data"]["prompt"]
        )
