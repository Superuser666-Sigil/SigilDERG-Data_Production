"""
Filter module for applying quality heuristics and filtering code files.

Implements filtering logic for crates and code files based on quality criteria.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.6.0
"""

import hashlib
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

    # Check Rust edition (minimum 2021, editions below 2021 not supported)
    if report.edition and int(report.edition) < 2021:
        reason = f"edition {report.edition} < 2021 (minimum required: 2021)"
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
    require_docs = config.require_docs
    if require_docs and config.require_docs_ratio < 1.0:
        ratio = max(0.0, min(1.0, config.require_docs_ratio))
        if ratio == 0.0:
            require_docs = False
        else:
            digest = hashlib.sha256(report.crate_name.encode("utf-8")).hexdigest()
            sample_value = int(digest, 16) / float(2**256)
            require_docs = sample_value < ratio

    if require_docs:
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

    # Dataset hardening checks
    if config.dataset_hardening:
        # Check minimum edition for hardening
        hardening_min_edition = config.hardening_min_edition
        if report.edition:
            try:
                if int(report.edition) < int(hardening_min_edition):
                    reason = (
                        f"hardening: edition {report.edition} < {hardening_min_edition}"
                    )
                    return _reject(report, reason)
            except ValueError:
                pass  # Can't parse edition, skip check

        # Check strict clippy results
        if config.hardening_strict_clippy and report.strict_clippy:
            if not report.strict_clippy.passed:
                reason = f"hardening: strict clippy failed (denied: {report.strict_clippy.denied_antipatterns}, pedantic: {report.strict_clippy.pedantic_warnings}, nursery: {report.strict_clippy.nursery_warnings})"
                detail = report.strict_clippy.log_path
                return _reject(report, reason, detail)

        # Check rustfmt results
        if config.hardening_require_rustfmt and report.rustfmt:
            if not report.rustfmt.passed:
                unformatted_count = len(report.rustfmt.unformatted_files)
                reason = f"hardening: rustfmt check failed ({unformatted_count} unformatted files)"
                detail = report.rustfmt.log_path
                return _reject(report, reason, detail)

    return True, None


def looks_like_test(file_path: str, content: str) -> bool:
    """
    Determine if a file appears to be a test file.

    Path-based checks: Files in /tests/, /benches/, etc. are always filtered.
    Content-based checks: Only filter if tests make up >50% of the file.

    This allows Rust's idiomatic pattern of inline unit tests (#[cfg(test)])
    in library files while still filtering dedicated test files.

    Args:
        file_path: Path to the file
        content: File content

    Returns:
        True if file looks like a test, False otherwise
    """
    path_lower = file_path.lower()

    # Check path patterns - these are definitely test/bench files
    if (
        "/tests/" in path_lower
        or "/benches/" in path_lower
        or "/test/" in path_lower
        or path_lower.endswith("_test.rs")
        or path_lower.endswith("_tests.rs")
    ):
        return True

    # Content-based check: only filter if file is PRIMARILY tests
    # Rust idiomatically includes inline tests with #[cfg(test)] in library files
    # We want to keep library code that has some tests, but filter files that are mostly tests
    if "#[cfg(test)]" in content or "fn test" in content:
        lines = content.split("\n")
        total_lines = len(lines)
        if total_lines == 0:
            return False

        # Count lines that appear to be test-related
        test_lines = 0
        in_test_module = False
        for line in lines:
            stripped = line.strip()
            # Track if we're inside a #[cfg(test)] module
            if "#[cfg(test)]" in line:
                in_test_module = True
            # End of module (simplistic heuristic: closing brace at start of line)
            if in_test_module and stripped == "}":
                # Could be end of test module, but we'll keep counting conservatively
                pass
            if in_test_module:
                test_lines += 1
            # Also count explicit test function definitions outside modules
            elif stripped.startswith("fn test") or stripped.startswith("#[test]"):
                test_lines += 1

        # Only filter if more than 50% of the file is test code
        test_ratio = test_lines / total_lines
        if test_ratio > 0.5:
            logger.debug(
                f"Filtering {file_path}: {test_ratio:.1%} test code ({test_lines}/{total_lines} lines)"
            )
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


def detect_unsafe_blocks(content: str) -> int:
    """
    Detect the number of `unsafe` blocks in Rust code using tree-sitter.

    This provides sample-level unsafe detection (distinct from cargo-geiger's
    crate-level metrics). Used by dataset hardening mode to reject code
    containing unsafe blocks.

    Args:
        content: Rust source code content

    Returns:
        Count of unsafe blocks found (0 if none or parsing fails)
    """
    try:
        import tree_sitter_rust as ts_rust
        from tree_sitter import Language, Parser
    except ImportError:
        # Fall back to simple string search if tree-sitter not available
        logger.debug("tree-sitter not available, using string-based unsafe detection")
        return content.count("unsafe {") + content.count("unsafe{")

    try:
        # Initialize parser
        rust_language = Language(ts_rust.language())
        parser = Parser(rust_language)

        # Parse the content
        tree = parser.parse(content.encode("utf-8"))
        root = tree.root_node

        # Count unsafe blocks using tree-sitter query
        unsafe_count = 0

        def count_unsafe(node):
            """Recursively count unsafe blocks."""
            nonlocal unsafe_count
            # unsafe_block is the tree-sitter node type for `unsafe { ... }`
            if node.type == "unsafe_block":
                unsafe_count += 1
            for child in node.children:
                count_unsafe(child)

        count_unsafe(root)
        return unsafe_count

    except Exception as e:
        logger.debug(f"tree-sitter parsing failed, falling back to string search: {e}")
        # Fall back to simple string search
        return content.count("unsafe {") + content.count("unsafe{")


def has_unsafe_blocks(content: str) -> bool:
    """
    Check if content contains any `unsafe` blocks.

    Convenience wrapper around detect_unsafe_blocks().

    Args:
        content: Rust source code content

    Returns:
        True if content has unsafe blocks, False otherwise
    """
    return detect_unsafe_blocks(content) > 0


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


def is_api_properly_used(code: str, api_name: str) -> bool:
    """
    Check if an API is properly used in code (excluding comments).

    Args:
        code: Rust source code to check
        api_name: API name to search for

    Returns:
        True if API is used in code (outside comments), False otherwise
    """
    import re

    # Escape special regex characters in API name
    escaped_api = re.escape(api_name)

    # Find all comments in the code
    comments = re.findall(r"//.*$|/\*[\s\S]*?\*/", code, re.MULTILINE)

    # Remove comments from code for checking actual usage
    code_without_comments = code
    for comment in comments:
        code_without_comments = code_without_comments.replace(comment, "")

    # Check if API is mentioned outside of comments
    # Use word boundaries to avoid partial matches
    api_pattern = r"(?<![a-zA-Z0-9_])" + escaped_api + r"(?![a-zA-Z0-9_])"
    return bool(re.search(api_pattern, code_without_comments))


def static_analysis_rust_code(
    code: str, api_name: str | None = None
) -> tuple[bool, str]:
    """
    Perform fast static analysis on Rust code without compilation.

    Validates basic syntax correctness and optional API usage before
    running expensive Clippy compilation. This pre-filter can reject
    obviously invalid code to improve pipeline performance.

    Checks performed:
    - Optional: API usage validation (excluding comments)
    - Function definition presence
    - Bracket/brace/parenthesis matching
    - Quote matching (handles lifetime annotations)

    Args:
        code: Rust source code to validate
        api_name: Optional API name that must be used in the code

    Returns:
        Tuple of (is_valid: bool, message: str)
        - (True, "Static analysis passed") if code passes all checks
        - (False, error_message) if validation fails

    Examples:
        >>> static_analysis_rust_code("fn main() { println!(\"hello\"); }")
        (True, 'Static analysis passed')
        >>> static_analysis_rust_code("fn main() { println!(\"hello\");", "println")
        (True, 'Static analysis passed')
        >>> static_analysis_rust_code("// uses File\\nfn test() {}", "File")
        (False, "Code does not properly use the required API: 'File'")
    """
    import re

    # Optional: Check API usage (excluding comments)
    if api_name:
        api_used = is_api_properly_used(code, api_name)
        if not api_used:
            return False, f"Code does not properly use the required API: '{api_name}'"

    # Basic syntax checks - ensure code has basic Rust structure
    syntax_checks = [
        (r"\bfn\b", "Missing function definition"),
        (r"[{]", "Missing opening braces"),
        (r"[}]", "Missing closing braces"),
    ]

    for pattern, error in syntax_checks:
        if not re.search(pattern, code):
            return False, error

    # Handle lifetime annotations before quote counting
    # Replace lifetime markers to avoid false positives in quote matching
    code_without_lifetimes = re.sub(r"<'[a-zA-Z_]+>|&'[a-zA-Z_]+", "<LIFETIME>", code)

    # Check for obvious syntax errors - unclosed quotes, brackets, etc.
    quotes = code_without_lifetimes.count('"') % 2
    single_quotes = code_without_lifetimes.count("'") % 2
    parentheses = code.count("(") - code.count(")")
    braces = code.count("{") - code.count("}")
    brackets = code.count("[") - code.count("]")

    if quotes != 0:
        return False, "Unclosed double quotes"
    if single_quotes != 0:
        return False, "Unclosed single quotes (not related to lifetimes)"
    if parentheses != 0:
        return False, "Mismatched parentheses"
    if braces != 0:
        return False, "Mismatched braces"
    if brackets != 0:
        return False, "Mismatched brackets"

    # All checks passed
    return True, "Static analysis passed"


def filter_code_files(
    file_iter: Iterable[dict], config: PipelineConfig
) -> Iterator[dict]:
    """
    Filter out test/bench files and files that don't meet quality criteria.

    Applies test/bench exclusion and size/sanity filters per refactoring plan.
    Refactored to accept Iterable and yield (Priority 2.1 - Streaming Architecture).

    When dataset hardening is enabled, also filters files containing unsafe blocks.

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

        # Hardening: reject files with unsafe blocks
        if config.dataset_hardening and config.hardening_reject_unsafe:
            unsafe_count = detect_unsafe_blocks(code)
            if unsafe_count > 0:
                logger.debug(
                    f"Hardening: skipping {path} ({unsafe_count} unsafe blocks)"
                )
                continue

        yield file_info
