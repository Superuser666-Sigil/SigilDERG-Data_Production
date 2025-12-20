"""
Tests for sigil_pipeline.filter module.

Tests quality filtering heuristics and file filtering.
"""

from sigil_pipeline.analyzer import (
    ClippyResult,
    CrateAnalysisReport,
    DenyResult,
    DocStats,
    GeigerResult,
    LicenseResult,
    OutdatedResult,
)
from sigil_pipeline.config import PipelineConfig
from sigil_pipeline.filter import (
    filter_code_files,
    has_doc_comments,
    is_api_properly_used,
    is_crate_acceptable,
    looks_like_test,
    meets_size_sanity_criteria,
    static_analysis_rust_code,
)


class TestIsCrateAcceptable:
    """Test is_crate_acceptable function."""

    def test_edition_filtering_2018(self, sample_crate_dir):
        """Test edition filtering (2018 vs 2021+)."""
        config = PipelineConfig()
        report = CrateAnalysisReport(
            crate_name="test",
            crate_dir=sample_crate_dir,
            clippy=ClippyResult(),
            edition="2018",
        )
        is_acceptable, reason = is_crate_acceptable(report, config)
        assert is_acceptable is False
        assert "edition" in reason

    def test_edition_filtering_2021(self, sample_crate_dir):
        """Test edition 2021 is allowed."""
        config = PipelineConfig(require_docs=False)
        report = CrateAnalysisReport(
            crate_name="test",
            crate_dir=sample_crate_dir,
            clippy=ClippyResult(),
            edition="2021",
            docs=DocStats(has_docs=True),
        )
        is_acceptable, reason = is_crate_acceptable(report, config)
        assert is_acceptable is True
        assert reason is None

    def test_clippy_warning_threshold_zero(self, sample_crate_dir):
        """Test bad_code warning threshold (0 warnings allowed)."""
        config = PipelineConfig(max_bad_code_warnings=0, require_docs=False)
        report = CrateAnalysisReport(
            crate_name="test",
            crate_dir=sample_crate_dir,
            clippy=ClippyResult(
                warning_count=1, bad_code_warnings=1, safe_to_ignore_warnings=0
            ),
            docs=DocStats(has_docs=True),
        )
        is_acceptable, reason = is_crate_acceptable(report, config)
        assert is_acceptable is False
        assert "bad_code clippy warnings" in reason

    def test_clippy_warning_threshold_ten(self, sample_crate_dir):
        """Test Clippy warning threshold (10 warnings allowed)."""
        config = PipelineConfig(
            max_bad_code_warnings=None, max_clippy_warnings=10, require_docs=False
        )
        report = CrateAnalysisReport(
            crate_name="test",
            crate_dir=sample_crate_dir,
            clippy=ClippyResult(warning_count=5),
            docs=DocStats(has_docs=True),
        )
        is_acceptable, reason = is_crate_acceptable(report, config)
        assert is_acceptable is True

    def test_documentation_requirements_with_docs(self, sample_crate_dir):
        """Test documentation requirements (with docs)."""
        config = PipelineConfig(require_docs=True)
        report = CrateAnalysisReport(
            crate_name="test",
            crate_dir=sample_crate_dir,
            clippy=ClippyResult(),
            docs=DocStats(has_docs=True, doc_coverage=0.5),
        )
        is_acceptable, reason = is_crate_acceptable(report, config)
        assert is_acceptable is True

    def test_documentation_requirements_without_docs(self, sample_crate_dir):
        """Test documentation requirements (without docs)."""
        config = PipelineConfig(require_docs=True)
        report = CrateAnalysisReport(
            crate_name="test",
            crate_dir=sample_crate_dir,
            clippy=ClippyResult(),
            docs=DocStats(has_docs=False),
        )
        is_acceptable, reason = is_crate_acceptable(report, config)
        assert is_acceptable is False
        assert "documentation" in reason or "docs" in reason

    def test_platform_specific_crate_filtering(self, sample_crate_dir, tmp_path):
        """Test platform-specific crate filtering."""
        # Create a crate with Windows-specific dependencies
        cargo_toml = sample_crate_dir / "Cargo.toml"
        cargo_toml.write_text(
            '[package]\nname = "test"\n[dependencies]\nwinapi = "0.3"\n'
        )

        config = PipelineConfig()
        report = CrateAnalysisReport(
            crate_name="test",
            crate_dir=sample_crate_dir,
            clippy=ClippyResult(),
        )

        # On non-Windows, this should be filtered
        # Note: Actual platform detection happens in is_platform_specific_crate
        # This test verifies the integration
        is_acceptable, reason = is_crate_acceptable(report, config)
        # Result depends on current platform - just verify it doesn't crash

    def test_license_filtering_allowed(self, sample_crate_dir):
        """Test license filtering (allowed license)."""
        config = PipelineConfig(
            enable_license_scan=True,
            allowed_licenses=["MIT", "Apache-2.0"],
            require_docs=False,
        )
        report = CrateAnalysisReport(
            crate_name="test",
            crate_dir=sample_crate_dir,
            clippy=ClippyResult(),
            docs=DocStats(has_docs=True),
            license=LicenseResult(
                crate_license="MIT",
                has_allowed_license=True,
            ),
        )
        is_acceptable, reason = is_crate_acceptable(report, config)
        assert is_acceptable is True

    def test_license_filtering_disallowed(self, sample_crate_dir):
        """Test license filtering (disallowed license)."""
        config = PipelineConfig(
            enable_license_scan=True,
            allowed_licenses=["MIT"],
            require_docs=False,
        )
        report = CrateAnalysisReport(
            crate_name="test",
            crate_dir=sample_crate_dir,
            clippy=ClippyResult(),
            docs=DocStats(has_docs=True),
            license=LicenseResult(
                crate_license="GPL-3.0",
                has_allowed_license=False,
            ),
        )
        is_acceptable, reason = is_crate_acceptable(report, config)
        assert is_acceptable is False
        assert "license" in reason

    def test_unsafe_code_filtering(self, sample_crate_dir):
        """Test unsafe code filtering."""
        config = PipelineConfig(max_unsafe_items=5, require_docs=False)
        report = CrateAnalysisReport(
            crate_name="test",
            crate_dir=sample_crate_dir,
            clippy=ClippyResult(),
            docs=DocStats(has_docs=True),
            geiger=GeigerResult(total_unsafe_items=10),
        )
        is_acceptable, reason = is_crate_acceptable(report, config)
        assert is_acceptable is False
        assert "unsafe" in reason

    def test_outdated_dependency_filtering(self, sample_crate_dir):
        """Test outdated dependency filtering."""
        config = PipelineConfig(max_outdated_ratio=0.2, require_docs=False)
        report = CrateAnalysisReport(
            crate_name="test",
            crate_dir=sample_crate_dir,
            clippy=ClippyResult(),
            docs=DocStats(has_docs=True),
            outdated=OutdatedResult(
                outdated_ratio=0.5,
                total_dependencies=10,
                outdated_count=5,
            ),
        )
        is_acceptable, reason = is_crate_acceptable(report, config)
        assert is_acceptable is False
        assert "outdated" in reason

    def test_deny_check_filtering(self, sample_crate_dir):
        """Test cargo-deny filtering."""
        config = PipelineConfig(
            enable_deny_scan=True,
            fail_on_deny_violations=True,
            require_docs=False,
        )
        report = CrateAnalysisReport(
            crate_name="test",
            crate_dir=sample_crate_dir,
            clippy=ClippyResult(),
            docs=DocStats(has_docs=True),
            deny=DenyResult(
                passed=False,
                advisories_found=1,
            ),
        )
        is_acceptable, reason = is_crate_acceptable(report, config)
        assert is_acceptable is False
        assert "deny" in reason or "advisory" in reason

    def test_deny_severity_filtering(self, sample_crate_dir):
        """Test deny severity filtering."""
        config = PipelineConfig(
            enable_deny_scan=True,
            max_deny_severity="medium",
            require_docs=False,
        )
        report = CrateAnalysisReport(
            crate_name="test",
            crate_dir=sample_crate_dir,
            clippy=ClippyResult(),
            docs=DocStats(has_docs=True),
            deny=DenyResult(
                passed=True,
                highest_severity="high",
            ),
        )
        is_acceptable, reason = is_crate_acceptable(report, config)
        assert is_acceptable is False
        assert "severity" in reason

    def test_multiple_filters_combined(self, sample_crate_dir):
        """Test multiple filters combined."""
        config = PipelineConfig(
            max_clippy_warnings=0,
            require_docs=True,
        )
        report = CrateAnalysisReport(
            crate_name="test",
            crate_dir=sample_crate_dir,
            clippy=ClippyResult(warning_count=0),
            edition="2021",
            docs=DocStats(has_docs=True),
        )
        is_acceptable, reason = is_crate_acceptable(report, config)
        assert is_acceptable is True


class TestLooksLikeTest:
    """Test looks_like_test function."""

    def test_test_directory(self):
        """Test files in tests/ directory."""
        # Function checks for "/tests/" pattern (with slashes on both sides)
        assert looks_like_test("src/tests/test.rs", "") is True
        assert looks_like_test("some/path/tests/file.rs", "") is True
        # Also checks for "/test/" pattern
        assert looks_like_test("src/test/file.rs", "") is True
        # And "/benches/" pattern
        assert looks_like_test("src/benches/bench.rs", "") is True

    def test_benches_directory(self):
        """Test files in benches/ directory."""
        # Function checks for "/benches/" pattern (with slashes on both sides)
        assert looks_like_test("src/benches/bench.rs", "") is True
        assert looks_like_test("some/path/benches/file.rs", "") is True

    def test_test_file_suffix(self):
        """Test files with _test.rs suffix."""
        assert looks_like_test("file_test.rs", "") is True
        assert looks_like_test("file_tests.rs", "") is True

    def test_cfg_test_attribute_mostly_tests(self):
        """Test files with #[cfg(test)] that are mostly test code are filtered."""
        # Create a file that's >50% test code
        code = """pub fn small() {}

#[cfg(test)]
mod tests {
    fn test_one() {}
    fn test_two() {}
    fn test_three() {}
    fn test_four() {}
    fn test_five() {}
}
"""
        assert looks_like_test("lib.rs", code) is True

    def test_cfg_test_attribute_mostly_library(self):
        """Test files with inline tests but mostly library code pass through.

        Rust idiomatically includes unit tests inline with library code.
        Files that are mostly production code should NOT be filtered.
        """
        # Create a file that's <50% test code (like scopeguard)
        code = """//! Module documentation
//!
//! This is a library module with lots of production code.

/// Public function documentation
pub fn production_function_one() {
    // Implementation
}

/// Another public function
pub fn production_function_two() {
    // More implementation
}

/// Yet another function
pub fn production_function_three() {
    // Even more implementation
}

#[cfg(test)]
mod tests {
    fn test_one() {}
}
"""
        assert looks_like_test("lib.rs", code) is False

    def test_fn_test_pattern_mostly_tests(self):
        """Test files that are mostly test functions are filtered."""
        code = """fn test_something() {}
fn test_another() {}
fn test_third() {}
fn test_fourth() {}
"""
        assert looks_like_test("lib.rs", code) is True

    def test_fn_test_pattern_in_library_code(self):
        """Test library files with a few test mentions pass through."""
        code = """/// This function does something
pub fn main_function() {
    // lots of code here
}

/// Another production function
pub fn helper() {
    // more code
}

// Note: we should test this later
// fn test_example would go in tests/
"""
        assert looks_like_test("lib.rs", code) is False

    def test_normal_file(self):
        """Test normal file (not a test)."""
        assert looks_like_test("src/lib.rs", "pub fn normal() {}") is False


class TestHasDocComments:
    """Test has_doc_comments function."""

    def test_has_triple_slash(self):
        """Test content with /// doc comments."""
        assert has_doc_comments("/// Doc comment\npub fn test() {}") is True

    def test_has_bang_doc(self):
        """Test content with //! doc comments."""
        assert has_doc_comments("//! Module docs\n") is True

    def test_no_doc_comments(self):
        """Test content without doc comments."""
        assert has_doc_comments("pub fn test() {}") is False

    def test_regular_comments(self):
        """Test regular comments don't count."""
        assert has_doc_comments("// Regular comment\npub fn test() {}") is False


class TestMeetsSizeSanityCriteria:
    """Test meets_size_sanity_criteria function."""

    def test_average_line_length_filter(self):
        """Test average line length filtering."""
        config = PipelineConfig(max_line_length=50)
        # Create content with long average lines
        content = "a" * 100 + "\n" + "b" * 100 + "\n" + "c" * 100
        assert meets_size_sanity_criteria("test.rs", content, config) is False

    def test_alphabetic_ratio_filter(self):
        """Test alphabetic ratio filtering."""
        config = PipelineConfig(min_alphabetic_ratio=0.3)
        # Create content with low alphabetic ratio (mostly symbols)
        content = "!" * 100 + "a" * 10
        assert meets_size_sanity_criteria("test.rs", content, config) is False

    def test_hard_cap_line_length(self):
        """Test hard cap for maximum line length."""
        config = PipelineConfig(max_line_length_hard_cap=100)
        # Create content with one very long line
        content = "a" * 500 + "\nshort line"
        assert meets_size_sanity_criteria("test.rs", content, config) is False

    def test_valid_file(self):
        """Test file that meets all criteria."""
        config = PipelineConfig(
            max_line_length=100,
            min_alphabetic_ratio=0.3,
            max_line_length_hard_cap=500,
        )
        content = 'pub fn test() {\n    println!("Hello");\n}'
        assert meets_size_sanity_criteria("test.rs", content, config) is True

    def test_empty_file(self):
        """Test empty file."""
        config = PipelineConfig()
        assert meets_size_sanity_criteria("test.rs", "", config) is False


class TestFilterCodeFiles:
    """Test filter_code_files function."""

    def test_filter_test_files(self, sample_config):
        """Test filtering out test files."""
        sample_config.require_docs = False  # Disable doc requirement for this test
        # Use code that doesn't match "fn test" pattern to avoid false positives
        files = [
            {"path": "src/lib.rs", "code": "pub fn example() {}"},
            {
                "path": "src/tests/test.rs",
                "code": "fn test_example() {}",
            },  # In tests/ directory
        ]
        filtered = list(filter_code_files(files, sample_config))
        assert len(filtered) == 1
        assert filtered[0]["path"] == "src/lib.rs"

    def test_filter_size_criteria(self, sample_config):
        """Test filtering by size criteria."""
        sample_config.require_docs = False  # Disable doc requirement
        sample_config.max_line_length = 50
        files = [
            {"path": "src/lib.rs", "code": "pub fn example() {}"},
            {"path": "src/long.rs", "code": "a" * 200 + "\n" + "b" * 200},
        ]
        filtered = list(filter_code_files(files, sample_config))
        assert len(filtered) == 1
        assert filtered[0]["path"] == "src/lib.rs"

    def test_end_to_end_filtering(self, sample_config):
        """Test end-to-end file filtering."""
        sample_config.require_docs = False  # Disable doc requirement
        files = [
            {"path": "src/lib.rs", "code": "/// Doc\npub fn example() {}"},
            {
                "path": "src/tests/test.rs",
                "code": "fn test_example() {}",
            },  # In tests/ directory
            {"path": "src/bad.rs", "code": "!" * 1000},  # Low alphabetic ratio
        ]
        filtered = list(filter_code_files(files, sample_config))
        assert len(filtered) == 1
        assert filtered[0]["path"] == "src/lib.rs"

    def test_empty_file_list(self, sample_config):
        """Test filtering empty file list."""
        filtered = list(filter_code_files([], sample_config))
        assert len(filtered) == 0


class TestIsApiProperlyUsed:
    """Test is_api_properly_used function."""

    def test_api_used_in_code(self):
        """Test API used directly in code."""
        code = """
        fn main() {
            let file = File::open("test.txt");
        }
        """
        assert is_api_properly_used(code, "File") is True

    def test_api_not_used(self):
        """Test API not present in code."""
        code = """
        fn main() {
            println!("hello");
        }
        """
        assert is_api_properly_used(code, "File") is False

    def test_api_only_in_comment(self):
        """Test API only mentioned in comment."""
        code = """
        // Uses File for reading
        fn main() {
            println!("hello");
        }
        """
        assert is_api_properly_used(code, "File") is False

    def test_api_only_in_block_comment(self):
        """Test API only mentioned in block comment."""
        code = """
        /* Uses File for reading */
        fn main() {
            println!("hello");
        }
        """
        assert is_api_properly_used(code, "File") is False

    def test_api_in_both_comment_and_code(self):
        """Test API in both comment and code."""
        code = """
        // File handling function
        fn main() {
            let file = File::open("test.txt");
        }
        """
        assert is_api_properly_used(code, "File") is True

    def test_api_partial_match_prevented(self):
        """Test that partial matches are prevented."""
        code = """
        fn main() {
            let filename = "test.txt";
        }
        """
        # "File" should not match "filename"
        assert is_api_properly_used(code, "File") is False

    def test_api_with_special_chars(self):
        """Test API name with special regex characters."""
        code = """
        fn main() {
            let v = vec![1, 2, 3];
        }
        """
        assert is_api_properly_used(code, "vec!") is True


class TestStaticAnalysisRustCode:
    """Test static_analysis_rust_code function."""

    def test_valid_simple_function(self):
        """Test valid simple function passes."""
        code = 'fn main() { println!("hello"); }'
        is_valid, message = static_analysis_rust_code(code)
        assert is_valid is True
        assert message == "Static analysis passed"

    def test_missing_function_definition(self):
        """Test code without function definition fails."""
        code = "let x = 5;"
        is_valid, message = static_analysis_rust_code(code)
        assert is_valid is False
        assert "function" in message.lower()

    def test_missing_opening_brace(self):
        """Test code without opening brace fails."""
        code = "fn main()"
        is_valid, message = static_analysis_rust_code(code)
        assert is_valid is False
        assert "brace" in message.lower()

    def test_unclosed_double_quotes(self):
        """Test unclosed double quotes detected."""
        code = 'fn main() { let s = "unclosed; }'
        is_valid, message = static_analysis_rust_code(code)
        assert is_valid is False
        assert "quote" in message.lower()

    def test_mismatched_parentheses(self):
        """Test mismatched parentheses detected."""
        code = "fn main() { let x = (1 + 2; }"
        is_valid, message = static_analysis_rust_code(code)
        assert is_valid is False
        assert "parenthes" in message.lower()

    def test_mismatched_braces(self):
        """Test mismatched braces detected."""
        code = "fn main() { if true { } }"  # Valid
        is_valid, _ = static_analysis_rust_code(code)
        assert is_valid is True

        code_bad = "fn main() { if true { }"  # Missing brace
        is_valid, message = static_analysis_rust_code(code_bad)
        assert is_valid is False
        assert "brace" in message.lower()

    def test_mismatched_brackets(self):
        """Test mismatched brackets detected."""
        code = "fn main() { let v = [1, 2, 3; }"
        is_valid, message = static_analysis_rust_code(code)
        assert is_valid is False
        assert "bracket" in message.lower()

    def test_api_usage_check_passes(self):
        """Test API usage check passes when API is used."""
        code = """
        fn main() {
            let file = File::open("test.txt");
        }
        """
        is_valid, message = static_analysis_rust_code(code, api_name="File")
        assert is_valid is True

    def test_api_usage_check_fails(self):
        """Test API usage check fails when API not used."""
        code = """
        fn main() {
            println!("hello");
        }
        """
        is_valid, message = static_analysis_rust_code(code, api_name="File")
        assert is_valid is False
        assert "File" in message

    def test_api_in_comment_only_fails(self):
        """Test API only in comment fails validation."""
        code = """
        // Uses File for reading
        fn main() {
            println!("hello");
        }
        """
        is_valid, message = static_analysis_rust_code(code, api_name="File")
        assert is_valid is False
        assert "File" in message

    def test_lifetime_annotations_handled(self):
        """Test that lifetime annotations don't cause false positives."""
        code = """
        fn process<'a>(data: &'a str) -> &'a str {
            data
        }
        """
        is_valid, message = static_analysis_rust_code(code)
        assert is_valid is True

    def test_complex_valid_code(self):
        """Test complex but valid code passes."""
        code = """
        fn process(items: &[i32]) -> Vec<i32> {
            let result: Vec<i32> = items.iter().cloned().collect();
            result
        }
        """
        is_valid, message = static_analysis_rust_code(code)
        assert is_valid is True
        assert is_valid is True

    def test_char_literals_handled(self):
        """Test character literals don't break quote counting."""
        code = """
        fn main() {
            let c = 'a';
            let d = 'b';
        }
        """
        is_valid, message = static_analysis_rust_code(code)
        assert is_valid is True
