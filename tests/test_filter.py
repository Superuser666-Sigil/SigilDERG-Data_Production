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
    is_crate_acceptable,
    looks_like_test,
    meets_size_sanity_criteria,
)


class TestIsCrateAcceptable:
    """Test is_crate_acceptable function."""

    def test_edition_filtering_2018(self, sample_crate_dir):
        """Test edition filtering (2018 vs 2021+)."""
        config = PipelineConfig(allow_edition_2018=False)
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
        config = PipelineConfig(allow_edition_2018=False, require_docs=False)
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
            allow_edition_2018=False,
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

    def test_cfg_test_attribute(self):
        """Test files with #[cfg(test)] attribute."""
        code = "#[cfg(test)]\nmod tests {}"
        assert looks_like_test("lib.rs", code) is True

    def test_fn_test_pattern(self):
        """Test files with fn test pattern."""
        code = "fn test_something() {}"
        assert looks_like_test("lib.rs", code) is True

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
