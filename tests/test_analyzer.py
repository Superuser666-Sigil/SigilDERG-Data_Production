"""Tests for sigil_pipeline.analyzer module."""

import json
import subprocess
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from sigil_pipeline.analyzer import (
    ClippyResult,
    CrateAnalysisReport,
    DenyResult,
    DocStats,
    GeigerResult,
    LicenseResult,
    OutdatedResult,
    _severity_rank,
    analyze_crate,
    get_crate_source_paths,
    run_clippy,
    run_deny_check,
    run_doc_check,
    run_geiger,
    run_license_check,
    run_outdated,
)
from sigil_pipeline.config import PipelineConfig


class TestDataclasses:
    def test_clippy_result_defaults(self):
        result = ClippyResult()
        assert result.warning_count == 0
        assert result.error_count == 0
        assert result.warnings == []
        assert result.errors == []
        assert result.success is True

    def test_geiger_result_defaults(self):
        result = GeigerResult()
        assert result.total_unsafe_items == 0
        assert result.success is True

    def test_outdated_result_defaults(self):
        result = OutdatedResult()
        assert result.outdated_count == 0
        assert result.total_dependencies == 0
        assert result.outdated_ratio == 0.0
        assert result.success is True

    def test_doc_stats_defaults(self):
        stats = DocStats()
        assert stats.total_files == 0
        assert stats.files_with_docs == 0
        assert stats.total_doc_comments == 0
        assert stats.doc_coverage == 0.0
        assert stats.has_docs is False

    def test_license_result_defaults(self):
        result = LicenseResult()
        assert result.crate_license is None
        assert result.all_licenses == []
        assert result.has_allowed_license is True
        assert result.success is True

    def test_deny_result_defaults(self):
        result = DenyResult()
        assert result.advisories_found == 0
        assert result.license_violations == 0
        assert result.banned_dependencies == 0
        assert result.highest_severity is None
        assert result.passed is True
        assert result.success is True

    def test_crate_analysis_report_fields(self, sample_crate_dir):
        clippy = ClippyResult(warning_count=5)
        geiger = GeigerResult(total_unsafe_items=2)
        docs = DocStats(total_files=10, files_with_docs=8)
        report = CrateAnalysisReport(
            crate_name="test",
            crate_dir=sample_crate_dir,
            clippy=clippy,
            geiger=geiger,
            docs=docs,
        )
        assert report.clippy.warning_count == 5
        assert report.geiger.total_unsafe_items == 2
        assert report.docs.total_files == 10
        assert report.docs.files_with_docs == 8


@pytest.fixture
def async_result():
    def _create(stdout: str = "", stderr: str = "", returncode: int = 0):
        return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)

    return _create


@pytest.mark.asyncio
async def test_run_clippy_categorizes_warnings(sample_crate_dir, async_result):
    warning_json = json.dumps(
        {
            "reason": "compiler-message",
            "message": {
                "level": "warning",
                "message": "style issue",
                "code": {"code": "clippy::doc_markdown"},
            },
        }
    )
    with (
        patch("sigil_pipeline.analyzer.check_cargo_available", return_value=True),
        patch(
            "sigil_pipeline.analyzer.run_command_async", new_callable=AsyncMock
        ) as mock_run,
    ):
        mock_run.return_value = async_result(stdout=f"{warning_json}\n")
        result = await run_clippy(sample_crate_dir, crate_name="demo")

    assert result.warning_count == 1
    assert result.safe_to_ignore_warnings == 1
    assert result.bad_code_warnings == 0


@pytest.mark.asyncio
async def test_run_clippy_records_errors(sample_crate_dir, async_result):
    error_json = json.dumps(
        {
            "reason": "compiler-message",
            "message": {"level": "error", "message": "compilation failed"},
        }
    )
    with (
        patch("sigil_pipeline.analyzer.check_cargo_available", return_value=True),
        patch(
            "sigil_pipeline.analyzer.run_command_async", new_callable=AsyncMock
        ) as mock_run,
    ):
        mock_run.return_value = async_result(stdout=f"{error_json}\n")
        result = await run_clippy(sample_crate_dir)

    assert result.error_count == 1


@pytest.mark.asyncio
async def test_run_clippy_invalid_json(sample_crate_dir, async_result):
    with (
        patch("sigil_pipeline.analyzer.check_cargo_available", return_value=True),
        patch(
            "sigil_pipeline.analyzer.run_command_async", new_callable=AsyncMock
        ) as mock_run,
    ):
        mock_run.return_value = async_result(stdout="not json\n")
        result = await run_clippy(sample_crate_dir)

    assert result.warning_count == 0
    assert result.error_count == 0


@pytest.mark.asyncio
async def test_run_clippy_cargo_missing(sample_crate_dir):
    with patch("sigil_pipeline.analyzer.check_cargo_available", return_value=False):
        result = await run_clippy(sample_crate_dir)
    assert result.success is False


@pytest.mark.asyncio
async def test_run_clippy_timeout(sample_crate_dir):
    with (
        patch("sigil_pipeline.analyzer.check_cargo_available", return_value=True),
        patch(
            "sigil_pipeline.analyzer.run_command_async", new_callable=AsyncMock
        ) as mock_run,
    ):
        mock_run.side_effect = subprocess.TimeoutExpired("cargo", 600)
        result = await run_clippy(sample_crate_dir, timeout=600)
    assert result.success is False


@pytest.mark.asyncio
async def test_run_geiger_parses_output(sample_crate_dir, async_result):
    stdout = json.dumps(
        {
            "packages": [
                {
                    "unsafety": {
                        "used": {
                            "functions": {"unsafe_": 2},
                            "exprs": {"unsafe_": 1},
                            "item_impls": {"unsafe_": 0},
                            "methods": {"unsafe_": 0},
                        }
                    }
                }
            ]
        }
    )
    with (
        patch("sigil_pipeline.analyzer.check_cargo_available", return_value=True),
        patch(
            "sigil_pipeline.analyzer.run_command_async", new_callable=AsyncMock
        ) as mock_run,
    ):
        mock_run.return_value = async_result(stdout=stdout)
        result = await run_geiger(sample_crate_dir, crate_name="demo")

    assert result is not None
    assert result.total_unsafe_items == 3
    assert result.packages_with_unsafe == 1


@pytest.mark.asyncio
async def test_run_geiger_returns_none_on_failure(sample_crate_dir, async_result):
    with (
        patch("sigil_pipeline.analyzer.check_cargo_available", return_value=True),
        patch(
            "sigil_pipeline.analyzer.run_command_async", new_callable=AsyncMock
        ) as mock_run,
    ):
        mock_run.return_value = async_result(stdout="", returncode=1)
        result = await run_geiger(sample_crate_dir)

    assert result is None


@pytest.mark.asyncio
async def test_run_outdated_parses_dependencies(sample_crate_dir, async_result):
    stdout = json.dumps(
        {
            "dependencies": [
                {"name": "dep1", "project": "1.0.0", "latest": "1.0.0"},
                {"name": "dep2", "project": "1.0.0", "latest": "1.1.0"},
            ]
        }
    )
    with (
        patch("sigil_pipeline.analyzer.check_cargo_available", return_value=True),
        patch(
            "sigil_pipeline.analyzer.run_command_async", new_callable=AsyncMock
        ) as mock_run,
    ):
        mock_run.return_value = async_result(stdout=stdout)
        result = await run_outdated(sample_crate_dir, crate_name="demo")

    assert result is not None
    assert result.total_dependencies == 2
    assert result.outdated_count == 1
    assert result.outdated_ratio == 0.5


@pytest.mark.asyncio
async def test_run_license_check_from_cargo_license(sample_crate_dir, async_result):
    stdout = json.dumps([{"name": "demo", "license": "MIT"}])
    with (
        patch("sigil_pipeline.analyzer.check_cargo_available", return_value=True),
        patch(
            "sigil_pipeline.analyzer.run_command_async", new_callable=AsyncMock
        ) as mock_run,
    ):
        mock_run.return_value = async_result(stdout=stdout)
        result = await run_license_check(sample_crate_dir, ["MIT"], crate_name="demo")

    assert result is not None
    assert result.crate_license == "MIT"
    assert result.has_allowed_license is True


@pytest.mark.asyncio
async def test_run_license_check_cargo_toml_fallback(tmp_path, async_result):
    crate_dir = tmp_path / "test_crate"
    crate_dir.mkdir()
    (crate_dir / "Cargo.toml").write_text('[package]\nname="demo"\nlicense="MIT"\n')

    with (
        patch("sigil_pipeline.analyzer.check_cargo_available", return_value=True),
        patch(
            "sigil_pipeline.analyzer.run_command_async", new_callable=AsyncMock
        ) as mock_run,
    ):
        mock_run.return_value = async_result(stdout="", returncode=1)
        result = await run_license_check(crate_dir, ["MIT"])

    assert result is not None
    assert result.crate_license == "MIT"


@pytest.mark.asyncio
async def test_run_deny_check_parses_severity(sample_crate_dir, async_result):
    stdout = json.dumps(
        {
            "advisories": {"found": [{"severity": "high"}]},
            "licenses": {"violations": []},
            "bans": {"violations": []},
        }
    )
    with (
        patch("sigil_pipeline.analyzer.check_cargo_available", return_value=True),
        patch(
            "sigil_pipeline.analyzer.run_command_async", new_callable=AsyncMock
        ) as mock_run,
    ):
        mock_run.return_value = async_result(stdout=stdout)
        result = await run_deny_check(sample_crate_dir)

    assert result is not None
    assert result.advisories_found == 1
    assert result.highest_severity == "high"
    assert result.passed is False


class TestRunDocCheck:
    def test_doc_comment_counting(self, tmp_path):
        crate_dir = tmp_path / "test_crate"
        crate_dir.mkdir()
        src_dir = crate_dir / "src"
        src_dir.mkdir()

        (src_dir / "lib.rs").write_text(
            """//! Module-level docs

/// Function docs
pub fn test() {}
"""
        )

        result = run_doc_check(crate_dir)
        assert result.total_files == 1
        assert result.files_with_docs == 1
        assert result.total_doc_comments >= 2
        assert result.has_docs is True

    def test_no_doc_comments(self, tmp_path):
        crate_dir = tmp_path / "test_crate"
        crate_dir.mkdir()
        src_dir = crate_dir / "src"
        src_dir.mkdir()
        (src_dir / "lib.rs").write_text("pub fn test() {}")

        result = run_doc_check(crate_dir)
        assert result.has_docs is False
        assert result.total_doc_comments == 0


class TestSeverityRank:
    def test_severity_ranking(self):
        assert _severity_rank("critical") == 4
        assert _severity_rank("high") == 3
        assert _severity_rank("medium") == 2
        assert _severity_rank("low") == 1
        assert _severity_rank("unknown") == 0
        assert _severity_rank("invalid") == 0


@pytest.mark.asyncio
async def test_analyze_crate_collects_results(sample_crate_dir):
    config = PipelineConfig(
        enable_license_scan=True,
        allowed_licenses=["MIT"],
        enable_deny_scan=True,
        require_docs=False,
        enable_analysis_cache=False,  # Disable cache to ensure all functions are called
    )
    with (
        patch("sigil_pipeline.utils.get_crate_edition", return_value="2021"),
        patch(
            "sigil_pipeline.analyzer.run_clippy",
            new_callable=AsyncMock,
            return_value=ClippyResult(),
        ) as mock_clippy,
        patch(
            "sigil_pipeline.analyzer.run_geiger",
            new_callable=AsyncMock,
            return_value=GeigerResult(),
        ),
        patch(
            "sigil_pipeline.analyzer.run_outdated",
            new_callable=AsyncMock,
            return_value=OutdatedResult(),
        ),
        patch(
            "sigil_pipeline.analyzer.run_license_check",
            new_callable=AsyncMock,
            return_value=LicenseResult(crate_license="MIT"),
        ),
        patch(
            "sigil_pipeline.analyzer.run_deny_check",
            new_callable=AsyncMock,
            return_value=DenyResult(advisories_found=0),
        ),
        patch(
            "sigil_pipeline.analyzer.run_doc_check",
            return_value=DocStats(has_docs=True),
        ),
    ):
        report = await analyze_crate(sample_crate_dir, config=config)

    mock_clippy.assert_awaited()
    assert isinstance(report, CrateAnalysisReport)
    assert report.license.crate_license == "MIT"
    assert report.docs.has_docs is True


class TestGetCrateSourcePaths:
    """Tests for get_crate_source_paths() which discovers source directories from Cargo.toml."""

    def test_standard_src_layout(self, tmp_path):
        """Crate with standard src/ directory should return ['src']."""
        crate_dir = tmp_path / "standard_crate"
        crate_dir.mkdir()
        (crate_dir / "src").mkdir()
        (crate_dir / "Cargo.toml").write_text(
            '[package]\nname = "standard"\nversion = "1.0.0"\n'
        )

        paths = get_crate_source_paths(crate_dir)
        assert paths == [crate_dir / "src"]

    def test_custom_lib_path(self, tmp_path):
        """Crate with custom lib.path should return that directory."""
        crate_dir = tmp_path / "custom_lib"
        crate_dir.mkdir()
        (crate_dir / "binding_rust").mkdir()
        (crate_dir / "binding_rust" / "lib.rs").write_text("// library code")
        (crate_dir / "Cargo.toml").write_text(
            '[package]\nname = "custom"\nversion = "1.0.0"\n\n'
            '[lib]\npath = "binding_rust/lib.rs"\n'
        )

        paths = get_crate_source_paths(crate_dir)
        assert crate_dir / "binding_rust" in paths

    def test_custom_lib_and_standard_src(self, tmp_path):
        """Crate with both custom lib.path and src/ should return both."""
        crate_dir = tmp_path / "hybrid_crate"
        crate_dir.mkdir()
        (crate_dir / "src").mkdir()
        (crate_dir / "src" / "main.rs").write_text("fn main() {}")
        (crate_dir / "binding_rust").mkdir()
        (crate_dir / "binding_rust" / "lib.rs").write_text("// library")
        (crate_dir / "Cargo.toml").write_text(
            '[package]\nname = "hybrid"\nversion = "1.0.0"\n\n'
            '[lib]\npath = "binding_rust/lib.rs"\n'
        )

        paths = get_crate_source_paths(crate_dir)
        assert crate_dir / "src" in paths
        assert crate_dir / "binding_rust" in paths

    def test_multiple_binaries(self, tmp_path):
        """Crate with multiple [[bin]] entries should return all directories."""
        crate_dir = tmp_path / "multi_bin"
        crate_dir.mkdir()
        (crate_dir / "src").mkdir()
        (crate_dir / "src" / "lib.rs").write_text("// lib")
        (crate_dir / "bins").mkdir()
        (crate_dir / "bins" / "cli.rs").write_text("fn main() {}")
        (crate_dir / "bins" / "server.rs").write_text("fn main() {}")
        (crate_dir / "Cargo.toml").write_text(
            '[package]\nname = "multi"\nversion = "1.0.0"\n\n'
            '[[bin]]\nname = "cli"\npath = "bins/cli.rs"\n\n'
            '[[bin]]\nname = "server"\npath = "bins/server.rs"\n'
        )

        paths = get_crate_source_paths(crate_dir)
        assert crate_dir / "src" in paths
        assert crate_dir / "bins" in paths

    def test_missing_cargo_toml(self, tmp_path):
        """Directory without Cargo.toml should return src/ if it exists."""
        crate_dir = tmp_path / "no_cargo"
        crate_dir.mkdir()
        (crate_dir / "src").mkdir()

        paths = get_crate_source_paths(crate_dir)
        assert paths == [crate_dir / "src"]

    def test_no_src_no_cargo_toml(self, tmp_path):
        """Directory without Cargo.toml or src/ should return empty list."""
        crate_dir = tmp_path / "empty"
        crate_dir.mkdir()

        paths = get_crate_source_paths(crate_dir)
        assert paths == []

    def test_workspace_member_skipped(self, tmp_path):
        """Workspace root (without [package]) should fall back to src/."""
        crate_dir = tmp_path / "workspace"
        crate_dir.mkdir()
        (crate_dir / "src").mkdir()
        (crate_dir / "Cargo.toml").write_text(
            '[workspace]\nmembers = ["crate_a", "crate_b"]\n'
        )

        paths = get_crate_source_paths(crate_dir)
        assert paths == [crate_dir / "src"]

    def test_invalid_cargo_toml(self, tmp_path):
        """Invalid TOML should fall back to src/ if it exists."""
        crate_dir = tmp_path / "invalid_toml"
        crate_dir.mkdir()
        (crate_dir / "src").mkdir()
        (crate_dir / "Cargo.toml").write_text("this is not valid { toml ][")

        paths = get_crate_source_paths(crate_dir)
        assert paths == [crate_dir / "src"]

    def test_nested_source_path(self, tmp_path):
        """Source path with nested directories should be resolved correctly."""
        crate_dir = tmp_path / "nested"
        crate_dir.mkdir()
        (crate_dir / "src" / "rust" / "bindings").mkdir(parents=True)
        (crate_dir / "src" / "rust" / "bindings" / "lib.rs").write_text("// nested lib")
        (crate_dir / "Cargo.toml").write_text(
            '[package]\nname = "nested"\nversion = "1.0.0"\n\n'
            '[lib]\npath = "src/rust/bindings/lib.rs"\n'
        )

        paths = get_crate_source_paths(crate_dir)
        assert crate_dir / "src/rust/bindings" in paths

    def test_deduplicates_paths(self, tmp_path):
        """Same directory referenced multiple times should only appear once."""
        crate_dir = tmp_path / "dedup"
        crate_dir.mkdir()
        (crate_dir / "src").mkdir()
        (crate_dir / "Cargo.toml").write_text(
            '[package]\nname = "dedup"\nversion = "1.0.0"\n\n'
            '[lib]\npath = "src/lib.rs"\n\n'
            '[[bin]]\nname = "main"\npath = "src/main.rs"\n'
        )

        paths = get_crate_source_paths(crate_dir)
        # src/ should only appear once, not duplicated
        src_count = sum(1 for p in paths if p == crate_dir / "src")
        assert src_count == 1


class TestRunDocCheckWithMultipleSources:
    """Tests for run_doc_check() with non-standard source paths."""

    def test_doc_check_custom_lib_path(self, tmp_path):
        """run_doc_check should find docs in custom lib path."""
        crate_dir = tmp_path / "custom_docs"
        crate_dir.mkdir()
        (crate_dir / "binding_rust").mkdir()
        (crate_dir / "Cargo.toml").write_text(
            '[package]\nname = "custom"\nversion = "1.0.0"\n\n'
            '[lib]\npath = "binding_rust/lib.rs"\n'
        )
        (crate_dir / "binding_rust" / "lib.rs").write_text(
            "//! Module docs\n\n/// Function docs\npub fn foo() {}\n"
        )

        result = run_doc_check(crate_dir)
        assert result.total_files == 1
        assert result.has_docs is True
        assert result.total_doc_comments >= 2

    def test_doc_check_multiple_sources(self, tmp_path):
        """run_doc_check should aggregate docs from all source directories."""
        crate_dir = tmp_path / "multi_source"
        crate_dir.mkdir()
        (crate_dir / "src").mkdir()
        (crate_dir / "binding_rust").mkdir()
        (crate_dir / "Cargo.toml").write_text(
            '[package]\nname = "multi"\nversion = "1.0.0"\n\n'
            '[lib]\npath = "binding_rust/lib.rs"\n'
        )
        (crate_dir / "src" / "main.rs").write_text("/// Main function\nfn main() {}\n")
        (crate_dir / "binding_rust" / "lib.rs").write_text(
            "//! Library docs\n\n/// Helper\npub fn helper() {}\n"
        )

        result = run_doc_check(crate_dir)
        assert result.total_files == 2
        assert result.files_with_docs == 2
        assert result.has_docs is True
