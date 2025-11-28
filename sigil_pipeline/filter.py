"""
Filter module for applying quality heuristics and filtering code files.

Implements filtering logic for crates and code files based on quality criteria.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.0.0
"""

import logging
import platform
from typing import Iterable, Iterator

from .analyzer import CrateAnalysisReport, log_rejection_summary
from .config import PipelineConfig
from .utils import is_platform_specific_crate

logger = logging.getLogger(__name__)


def _format_reason_with_details(reason: str, detail_paths: list[str]) -> str:
    paths = [path for path in detail_paths if path]
    if paths:
        return f"{reason} (details: {', '.join(paths)})"
    return reason


def _reject(
    report: CrateAnalysisReport, reason: str, *detail_paths: str | None
) -> tuple[bool, str | None]:
    summary_path = log_rejection_summary(report, reason)
    details = list(detail_paths)
    if summary_path:
        details.append(summary_path)
    message = _format_reason_with_details(reason, [p for p in details if p])
    logger.info(f"Skipping {report.crate_name}: {message}")
    return False, reason


def is_crate_acceptable(
    report: CrateAnalysisReport, config: PipelineConfig
) -> tuple[bool, str | None]:
    """
    Determine if a crate meets quality criteria.

    Args:
        report: Crate analysis report
        config: Pipeline configuration

    Returns:
        Tuple of (is_acceptable: bool, rejection_reason: str | None)
        If acceptable, reason is None. If rejected, reason describes why.
    """
    # Check for platform-specific crates (pre-filter before compilation)
    platform_specific = is_platform_specific_crate(report.crate_dir)
    if platform_specific:
        current_platform = platform.system().lower()
        # Map platform names
        platform_map = {"darwin": "macos", "linux": "linux", "windows": "windows"}
        current_platform_name = platform_map.get(current_platform, current_platform)

        if platform_specific != current_platform_name:
            reason = f"platform-specific crate (detected: {platform_specific}, current: {current_platform_name})"
            return _reject(report, reason)

    # Check Rust edition
    if not config.allow_edition_2018:
        if report.edition and int(report.edition) < 2021:
            reason = f"edition {report.edition} < 2021"
            return _reject(report, reason)

    # Check Clippy warnings - filter by category, not total count
    # Only reject on "bad_code" warnings (unsafe code, memory safety, logic errors)
    # Style/documentation warnings are ignored
    if config.max_bad_code_warnings is not None:
        bad_code_count = report.clippy.bad_code_warnings if report.clippy else 0
        if bad_code_count > config.max_bad_code_warnings:
            reason = f"{bad_code_count} bad_code clippy warnings > {config.max_bad_code_warnings} (total: {report.clippy.warning_count}, safe_to_ignore: {report.clippy.safe_to_ignore_warnings}, questionable: {report.clippy.questionable_warnings})"
            detail = report.clippy.log_path if report.clippy else None
            return _reject(report, reason, detail)

    # Fallback to total count if max_bad_code_warnings not set (backward compatibility)
    if config.max_clippy_warnings is not None and config.max_bad_code_warnings is None:
        if report.clippy.warning_count > config.max_clippy_warnings:
            reason = f"{report.clippy.warning_count} clippy warnings > {config.max_clippy_warnings}"
            detail = report.clippy.log_path if report.clippy else None
            return _reject(report, reason, detail)

    # Check documentation
    if config.require_docs:
        if not report.docs or not report.docs.has_docs:
            reason = "no documentation found"
            return _reject(report, reason)

        if report.docs.doc_coverage < config.min_doc_coverage:
            reason = f"doc coverage {report.docs.doc_coverage:.2f} < {config.min_doc_coverage:.2f}"
            return _reject(report, reason)

    # Check license if enabled and license check was performed
    if config.enable_license_scan and report.license:
        if not report.license.has_allowed_license:
            reason = f"license not in allowed list (found: {report.license.crate_license or report.license.all_licenses})"
            return _reject(report, reason)

    # Check unsafe code if threshold set (Priority 4.1)
    if config.max_unsafe_items is not None and report.geiger:
        if report.geiger.total_unsafe_items > config.max_unsafe_items:
            reason = f"{report.geiger.total_unsafe_items} unsafe items > {config.max_unsafe_items}"
            detail = report.geiger.log_path if report.geiger else None
            return _reject(report, reason, detail)

    # Check outdated dependencies if threshold set (Priority 4.1)
    if config.max_outdated_ratio is not None and report.outdated:
        if report.outdated.outdated_ratio > config.max_outdated_ratio:
            reason = f"outdated ratio {report.outdated.outdated_ratio:.2f} > {config.max_outdated_ratio:.2f}"
            detail = report.outdated.log_path if report.outdated else None
            return _reject(report, reason, detail)

    # Check cargo-deny results if enabled (Priority 1.4)
    if config.enable_deny_scan and report.deny:
        if config.fail_on_deny_violations and not report.deny.passed:
            reason = f"cargo-deny violations (advisories: {report.deny.advisories_found}, licenses: {report.deny.license_violations}, banned: {report.deny.banned_dependencies})"
            return _reject(report, reason)

        if config.max_deny_severity and report.deny.highest_severity:
            from .analyzer import _severity_rank

            if _severity_rank(report.deny.highest_severity) > _severity_rank(
                config.max_deny_severity
            ):
                reason = f"deny severity {report.deny.highest_severity} exceeds {config.max_deny_severity}"
                return _reject(report, reason)

    return True, None


def looks_like_test(file_path: str, content: str) -> bool:
    """
    Determine if a file appears to be a test file.

    Args:
        file_path: Path to the file
        content: File content

    Returns:
        True if file looks like a test, False otherwise
    """
    path_lower = file_path.lower()

    # Check path patterns
    if (
        "/tests/" in path_lower
        or "/benches/" in path_lower
        or "/test/" in path_lower
        or path_lower.endswith("_test.rs")
        or path_lower.endswith("_tests.rs")
    ):
        return True

    # Check content patterns
    if "#[cfg(test)]" in content or "fn test" in content:
        return True

    return False


def has_doc_comments(content: str) -> bool:
    """
    Check if content has documentation comments.

    Args:
        content: File content

    Returns:
        True if content has doc comments, False otherwise
    """
    return "///" in content or "//!" in content


def meets_size_sanity_criteria(
    file_path: str, content: str, config: PipelineConfig
) -> bool:
    """
    Check if file meets size/sanity filters per refactoring plan.

    Filters out files with extremely long lines or abnormal code-to-text ratios.
    Matches Stack dataset filtering criteria.

    Args:
        file_path: Path to the file
        content: File content
        config: Pipeline configuration

    Returns:
        True if file meets size criteria, False otherwise
    """
    if not content:
        return False

    lines = content.split("\n")
    if not lines:
        return False

    # Check average line length (Stack dataset filtered > 100)
    avg_line_length = sum(len(line) for line in lines) / len(lines)
    if avg_line_length > config.max_line_length:
        logger.debug(
            f"Skipping {file_path}: average line length "
            f"{avg_line_length:.1f} > {config.max_line_length}"
        )
        return False

    # Check alphabetic character ratio (filter minified/generated code)
    total_chars = len(content)
    if total_chars > 0:
        alphabetic_chars = sum(1 for c in content if c.isalpha() or c.isspace())
        alphabetic_ratio = alphabetic_chars / total_chars
        if alphabetic_ratio < config.min_alphabetic_ratio:
            logger.debug(
                f"Skipping {file_path}: alphabetic ratio "
                f"{alphabetic_ratio:.3f} < {config.min_alphabetic_ratio}"
            )
            return False

    # Check for extremely long lines (single line > 500 chars suggests minified)
    max_line_length = max((len(line) for line in lines), default=0)
    max_line_length_hard_cap = getattr(config, "max_line_length_hard_cap", 500)
    if max_line_length > max_line_length_hard_cap:
        logger.debug(
            f"Skipping {file_path}: max line length "
            f"{max_line_length} > {max_line_length_hard_cap}"
        )
        return False

    return True


def filter_code_files(
    file_iter: Iterable[dict], config: PipelineConfig
) -> Iterator[dict]:
    """
    Filter out test/bench files and files that don't meet quality criteria.

    Applies test/bench exclusion and size/sanity filters per refactoring plan.
    Refactored to accept Iterable and yield (Priority 2.1 - Streaming Architecture).

    Args:
        file_iter: Iterable of file dicts with 'path' and 'code' keys
        config: Pipeline configuration

    Yields:
        Filtered file dicts
    """
    for file_info in file_iter:
        path = file_info.get("path", "")
        code = file_info.get("code", "")

        # Skip test/bench files
        if looks_like_test(path, code):
            continue

        # Apply size/sanity filters
        if not meets_size_sanity_criteria(path, code, config):
            continue

        yield file_info
