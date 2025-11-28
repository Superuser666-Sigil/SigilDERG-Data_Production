"""
Analyzer module for running static analysis tools on Rust crates.

Provides functions to run Clippy, Geiger, outdated, and documentation checks.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.0.0
"""

import json
import logging
import re
import subprocess
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Import OS-agnostic cargo utilities from sigil_pipeline.utils
from .utils import (
    build_cargo_command,
    build_cargo_subcommand_command,
    check_cargo_available,
    run_command_async,
)

logger = logging.getLogger(__name__)


def categorize_clippy_warning(code: str) -> str:
    """
    Categorize clippy warning code into safe_to_ignore, questionable, or bad_code.

    Args:
        code: Warning code string (e.g., "clippy::unwrap_used")

    Returns:
        Category: "safe_to_ignore", "questionable", "bad_code", or "unknown"
    """
    if not code or "clippy::" not in code:
        return "unknown"

    warning_name = code.split("::")[-1].lower()

    # Safe to ignore - style/documentation warnings
    safe_patterns = [
        "doc_lazy_continuation",  # Doc formatting
        "doc_markdown",  # Doc markdown style
        "missing_docs_in_private_items",  # Private item docs
        "too_many_lines",  # File length
        "too_many_arguments",  # Function design
        "cognitive_complexity",  # Complexity metrics
        "type_complexity",  # Type complexity
        "module_inception",  # Module structure
        "similar_names",  # Variable naming
        "just_underscores_and_digits",  # Variable naming
        "single_char_lifetime_names",  # Lifetime naming
        "module_name_repetitions",  # Module naming
        "unreadable_literal",  # Number formatting
        "zero_prefixed_literal",  # Number formatting
        "decimal_literal_representation",  # Number formatting
        "excessive_precision",  # Float precision
        "cast_possible_truncation",  # Cast warnings (often intentional)
        "cast_possible_wrap",  # Cast warnings
        "cast_sign_loss",  # Cast warnings
        "cast_lossless",  # Cast warnings
        "unnecessary_cast",  # Cast warnings
        "identity_op",  # Identity operations
        "erasing_op",  # Type erasure
        "redundant_pattern_matching",  # Pattern style
        "match_same_arms",  # Match arms (sometimes intentional)
        "single_char_pattern",  # Pattern style
        "wildcard_imports",  # Import style
        "enum_glob_use",  # Import style
        "unused_qualifications",  # Import qualifications
        "redundant_closure",  # Closure style
        "redundant_closure_call",  # Closure style
        "unnecessary_lazy_evaluations",  # Lazy evaluation
        "manual_",  # Manual implementations (preference)
        "needless_",  # Needless operations (often false positives)
        "collapsible_",  # Control flow style
    ]

    # Bad code - actual problems that should cause rejection
    bad_patterns = [
        "unwrap_used",  # Unsafe unwrapping
        "expect_used",  # Unsafe expecting
        "panic",  # Panic usage
        "unreachable",  # Unreachable code
        "unused_variables",  # Unused code
        "unused_imports",  # Unused imports
        "unused_mut",  # Unused mutability
        "unused_assignments",  # Unused assignments
        "unused_must_use",  # Ignored must-use
        "unused_results",  # Ignored results
        "let_underscore_drop",  # Resource leaks
        "drop_copy",  # Resource leaks
        "drop_ref",  # Resource leaks
        "forget_copy",  # Resource leaks
        "forget_ref",  # Resource leaks
        "mem_forget",  # Memory leaks
        "transmute",  # Unsafe transmutation
        "as_conversions",  # Unsafe casts
        "cast_ptr_alignment",  # Unsafe casts
        "cast_ref_to_mut",  # Unsafe casts
        "mut_from_ref",  # Unsafe mutability
        "mut_mut",  # Unsafe mutability
        "borrow_as_ptr",  # Unsafe borrowing
        "invalid_atomic_ordering",  # Atomic ordering
        "invalid_ref",  # Invalid references
        "invalid_utf8_in_unchecked",  # Unsafe UTF-8
        "invalid_nan_comparison",  # NaN comparisons
        "indexing_slicing",  # Unsafe indexing
        "out_of_bounds_indexing",  # Unsafe indexing
        "todo",  # TODO comments
        "unimplemented",  # Unimplemented code
    ]

    # Check patterns
    for pattern in safe_patterns:
        if pattern in warning_name:
            return "safe_to_ignore"

    for pattern in bad_patterns:
        if pattern in warning_name:
            return "bad_code"

    return "questionable"


@dataclass
class ClippyResult:
    """Results from running cargo clippy."""

    warning_count: int = 0
    error_count: int = 0
    warnings: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    success: bool = True
    log_path: str | None = None
    # Category-based counts
    bad_code_warnings: int = 0
    """Count of warnings indicating actual code quality problems."""
    safe_to_ignore_warnings: int = 0
    """Count of style/documentation warnings that can be ignored."""
    questionable_warnings: int = 0
    """Count of warnings that might indicate issues but are often false positives."""

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.errors is None:
            self.errors = []


@dataclass
class GeigerResult:
    """Results from running cargo geiger."""

    total_unsafe_items: int = 0
    unsafe_functions: int = 0
    unsafe_expressions: int = 0
    unsafe_impls: int = 0
    unsafe_methods: int = 0
    packages_with_unsafe: int = 0
    success: bool = True
    log_path: str | None = None


@dataclass
class OutdatedResult:
    """Results from running cargo outdated."""

    outdated_count: int = 0
    total_dependencies: int = 0
    outdated_ratio: float = 0.0
    success: bool = True
    log_path: str | None = None


@dataclass
class DocStats:
    """Documentation statistics for a crate."""

    total_files: int = 0
    files_with_docs: int = 0
    total_doc_comments: int = 0
    doc_coverage: float = 0.0
    has_docs: bool = False


@dataclass
class LicenseResult:
    """Results from license checking."""

    crate_license: str | None = None
    """Primary license of the crate (from Cargo.toml)."""
    all_licenses: list[str] = field(default_factory=list)
    """All licenses found in crate and dependencies."""
    has_allowed_license: bool = True
    """Whether crate has at least one allowed license."""
    success: bool = True
    log_path: str | None = None
    """Path to detailed license log file."""

    def __post_init__(self):
        if self.all_licenses is None:
            self.all_licenses = []


@dataclass
class DenyResult:
    """Results from cargo-deny security and license auditing."""

    advisories_found: int = 0
    """Number of security advisories found."""
    license_violations: int = 0
    """Number of license violations."""
    banned_dependencies: int = 0
    """Number of banned dependencies."""
    highest_severity: str | None = None
    """Highest severity level found (e.g., 'critical', 'high', 'medium', 'low')."""
    passed: bool = True
    """Whether all deny checks passed."""
    success: bool = True
    """Whether cargo-deny ran successfully."""


@dataclass
class CrateAnalysisReport:
    """Complete analysis report for a crate."""

    crate_name: str
    crate_dir: Path
    clippy: ClippyResult
    geiger: GeigerResult | None = None
    outdated: OutdatedResult | None = None
    docs: DocStats | None = None
    license: LicenseResult | None = None
    deny: DenyResult | None = None
    edition: str | None = None
    rejection_log_path: str | None = None


_ANALYSIS_LOG_DIR: Path | None = None
_ANALYSIS_LOG_DIR_LOCK = threading.Lock()


def _sanitize_name(name: str) -> str:
    """Sanitize crate name for use in file paths."""
    sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "_", name or "")
    return sanitized or "unknown_crate"


def _get_analysis_log_dir() -> Path:
    """
    Get or create the analysis log directory (thread-safe).

    Uses a lock to prevent race conditions when multiple threads
    attempt to create the directory simultaneously.

    Returns:
        Path to the analysis log directory
    """
    global _ANALYSIS_LOG_DIR
    with _ANALYSIS_LOG_DIR_LOCK:
        if _ANALYSIS_LOG_DIR is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            _ANALYSIS_LOG_DIR = Path("logs") / f"analysis_{timestamp}"
            _ANALYSIS_LOG_DIR.mkdir(parents=True, exist_ok=True)
        return _ANALYSIS_LOG_DIR


def _write_analysis_log(crate_name: str, filename: str, content: str) -> Path:
    log_root = _get_analysis_log_dir()
    crate_dir = log_root / _sanitize_name(crate_name)
    crate_dir.mkdir(parents=True, exist_ok=True)
    log_path = crate_dir / filename
    log_path.write_text(content, encoding="utf-8", errors="ignore")
    return log_path


def log_rejection_summary(report: CrateAnalysisReport, reason: str) -> str | None:
    """
    Write a concise rejection summary for a crate to the analysis log directory.
    """
    try:
        payload = {
            "crate": report.crate_name,
            "reason": reason,
            "clippy_warning_count": (
                report.clippy.warning_count if report.clippy else None
            ),
            "clippy_error_count": report.clippy.error_count if report.clippy else None,
            "docs": {
                "has_docs": report.docs.has_docs if report.docs else None,
                "doc_coverage": report.docs.doc_coverage if report.docs else None,
            },
            "geiger_total_unsafe": (
                report.geiger.total_unsafe_items if report.geiger else None
            ),
            "outdated_ratio": (
                report.outdated.outdated_ratio if report.outdated else None
            ),
            "license": {
                "crate_license": (
                    report.license.crate_license if report.license else None
                ),
                "all_licenses": (
                    report.license.all_licenses if report.license else None
                ),
                "has_allowed_license": (
                    report.license.has_allowed_license if report.license else None
                ),
            },
            "tools_executed": {
                "clippy": report.clippy is not None,
                "geiger": report.geiger is not None,
                "outdated": report.outdated is not None,
                "license": report.license is not None,
                "deny": report.deny is not None,
            },
            "edition": report.edition,
        }
        log_path = _write_analysis_log(
            report.crate_name, "rejection_summary.json", json.dumps(payload, indent=2)
        )
        report.rejection_log_path = str(log_path)
        return str(log_path)
    except Exception as exc:  # pragma: no cover - logging best-effort
        logger.debug(
            f"Failed to write rejection summary for {report.crate_name}: {exc}"
        )
        return None


async def run_clippy(
    crate_dir: Path,
    timeout: int = 300,
    env: dict[str, str] | None = None,
    crate_name: str | None = None,
) -> ClippyResult:
    """
    Run cargo clippy on a crate and parse the results.

    Args:
        crate_dir: Path to crate directory
        timeout: Command timeout in seconds

    Returns:
        ClippyResult with warning/error counts
    """
    if not check_cargo_available():
        logger.error("cargo is not available")
        return ClippyResult(success=False)

    cmd = build_cargo_command(
        "clippy",
        "--message-format=json",
        "--quiet",
        "--",
        "-W",
        "clippy::all",
    )

    try:
        result = await run_command_async(
            cmd,
            cwd=crate_dir,
            timeout=timeout,
            env=env,
        )
        # Decode bytes to string if needed
        if isinstance(result.stdout, bytes):
            result.stdout = result.stdout.decode("utf-8", errors="replace")
        if isinstance(result.stderr, bytes):
            result.stderr = result.stderr.decode("utf-8", errors="replace")

        warnings = []
        errors = []
        bad_code_count = 0
        safe_to_ignore_count = 0
        questionable_count = 0

        # Parse JSON output (line-delimited JSON)
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            try:
                msg = json.loads(line)
                if msg.get("reason") == "compiler-message":
                    message_data = msg.get("message", {})
                    level = message_data.get("level", "")
                    if level == "warning":
                        warnings.append(msg)
                        # Categorize warning
                        code_obj = message_data.get("code", {})
                        if code_obj:
                            code_str = code_obj.get("code", "")
                            if code_str:
                                category = categorize_clippy_warning(code_str)
                                if category == "bad_code":
                                    bad_code_count += 1
                                elif category == "safe_to_ignore":
                                    safe_to_ignore_count += 1
                                elif category == "questionable":
                                    questionable_count += 1
                    elif level == "error":
                        errors.append(msg)
            except json.JSONDecodeError:
                continue

        log_path = None
        if crate_name and (warnings or errors):
            log_content = result.stdout or result.stderr or ""
            log_path = str(
                _write_analysis_log(crate_name, "clippy.log", log_content.strip())
            )

        return ClippyResult(
            warning_count=len(warnings),
            error_count=len(errors),
            warnings=warnings,
            errors=errors,
            success=result.returncode == 0 or len(errors) == 0,
            log_path=log_path,
            bad_code_warnings=bad_code_count,
            safe_to_ignore_warnings=safe_to_ignore_count,
            questionable_warnings=questionable_count,
        )

    except subprocess.TimeoutExpired:
        logger.warning(f"Clippy timed out for {crate_dir}")
        return ClippyResult(success=False)
    except Exception as e:
        logger.error(f"Failed to run clippy on {crate_dir}: {e}")
        return ClippyResult(success=False)


async def run_geiger(
    crate_dir: Path,
    timeout: int = 300,
    env: dict[str, str] | None = None,
    crate_name: str | None = None,
) -> GeigerResult | None:
    """
    Run cargo geiger on a crate and parse the results.

    Args:
        crate_dir: Path to crate directory
        timeout: Command timeout in seconds

    Returns:
        GeigerResult with unsafe code metrics, or None if failed
    """
    if not check_cargo_available():
        logger.warning("cargo is not available")
        return None

    cmd = build_cargo_subcommand_command("geiger", "--format=json")

    try:
        result = await run_command_async(
            cmd,
            cwd=crate_dir,
            timeout=timeout,
            env=env,
        )
        # Decode bytes to string if needed
        if isinstance(result.stdout, bytes):
            result.stdout = result.stdout.decode("utf-8", errors="replace")
        if isinstance(result.stderr, bytes):
            result.stderr = result.stderr.decode("utf-8", errors="replace")

        if result.returncode != 0 or not result.stdout:
            return None

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse geiger JSON for {crate_dir}")
            return None

        packages = data.get("packages", [])

        total_unsafe_functions = 0
        total_unsafe_expressions = 0
        total_unsafe_impls = 0
        total_unsafe_methods = 0
        packages_with_unsafe = 0

        for package in packages:
            unsafety = package.get("unsafety", {})
            used = unsafety.get("used", {})

            unsafe_functions = used.get("functions", {}).get("unsafe_", 0)
            unsafe_expressions = used.get("exprs", {}).get("unsafe_", 0)
            unsafe_impls = used.get("item_impls", {}).get("unsafe_", 0)
            unsafe_methods = used.get("methods", {}).get("unsafe_", 0)

            total_unsafe_functions += unsafe_functions
            total_unsafe_expressions += unsafe_expressions
            total_unsafe_impls += unsafe_impls
            total_unsafe_methods += unsafe_methods

            if any(
                [unsafe_functions, unsafe_expressions, unsafe_impls, unsafe_methods]
            ):
                packages_with_unsafe += 1

        total_unsafe_items = (
            total_unsafe_functions
            + total_unsafe_expressions
            + total_unsafe_impls
            + total_unsafe_methods
        )

        # Log geiger results for all crates (even with 0 unsafe) to confirm tool ran
        log_path = None
        if crate_name:
            raw_output = result.stdout or json.dumps(data, indent=2)
            log_path = str(
                _write_analysis_log(crate_name, "geiger.json", raw_output.strip())
            )

        return GeigerResult(
            total_unsafe_items=total_unsafe_items,
            unsafe_functions=total_unsafe_functions,
            unsafe_expressions=total_unsafe_expressions,
            unsafe_impls=total_unsafe_impls,
            unsafe_methods=total_unsafe_methods,
            packages_with_unsafe=packages_with_unsafe,
            success=True,
            log_path=log_path,
        )

    except subprocess.TimeoutExpired:
        logger.warning(f"Geiger timed out for {crate_dir}")
        return None
    except Exception as e:
        logger.warning(f"Failed to run geiger on {crate_dir}: {e}")
        return None


async def run_outdated(
    crate_dir: Path,
    timeout: int = 300,
    env: dict[str, str] | None = None,
    crate_name: str | None = None,
) -> OutdatedResult | None:
    """
    Run cargo outdated on a crate and parse the results.

    Args:
        crate_dir: Path to crate directory
        timeout: Command timeout in seconds

    Returns:
        OutdatedResult with dependency age metrics, or None if failed
    """
    if not check_cargo_available():
        logger.warning("cargo is not available")
        return None

    cmd = build_cargo_subcommand_command("outdated", "--format=json")

    try:
        result = await run_command_async(
            cmd,
            cwd=crate_dir,
            timeout=timeout,
            env=env,
        )
        # Decode bytes to string if needed
        if isinstance(result.stdout, bytes):
            result.stdout = result.stdout.decode("utf-8", errors="replace")
        if isinstance(result.stderr, bytes):
            result.stderr = result.stderr.decode("utf-8", errors="replace")

        if result.returncode != 0:
            return None

        outdated_count = 0
        total_dependencies = 0

        data = None
        try:
            data = json.loads(result.stdout)
            if isinstance(data, dict) and "dependencies" in data:
                dependencies = data["dependencies"]
                total_dependencies = len(dependencies)
                outdated_deps = [
                    dep
                    for dep in dependencies
                    if dep.get("latest") != dep.get("project")
                ]
                outdated_count = len(outdated_deps)
        except json.JSONDecodeError:
            # Try parsing text output
            lines = result.stdout.split("\n")
            outdated_lines = [
                line for line in lines if "outdated" in line.lower() or "->" in line
            ]
            outdated_count = len(outdated_lines)

        outdated_ratio = (
            outdated_count / total_dependencies if total_dependencies > 0 else 0.0
        )

        log_path = None
        if crate_name and outdated_count > 0:
            raw_output = result.stdout
            if not raw_output:
                try:
                    raw_output = json.dumps(data, indent=2)  # type: ignore[name-defined]
                except Exception:
                    raw_output = ""
            log_path = str(
                _write_analysis_log(crate_name, "outdated.json", raw_output.strip())
            )

        return OutdatedResult(
            outdated_count=outdated_count,
            total_dependencies=total_dependencies,
            outdated_ratio=outdated_ratio,
            success=True,
            log_path=log_path,
        )

    except subprocess.TimeoutExpired:
        logger.warning(f"Outdated timed out for {crate_dir}")
        return None
    except Exception as e:
        logger.warning(f"Failed to run outdated on {crate_dir}: {e}")
        return None


def run_doc_check(crate_dir: Path) -> DocStats:
    """
    Check documentation coverage in a crate.

    Args:
        crate_dir: Path to crate directory

    Returns:
        DocStats with documentation metrics
    """
    src_dir = crate_dir / "src"
    if not src_dir.exists():
        return DocStats()

    total_files = 0
    files_with_docs = 0
    total_doc_comments = 0

    # Count .rs files and doc comments
    for rs_file in src_dir.rglob("*.rs"):
        total_files += 1
        try:
            content = rs_file.read_text(encoding="utf-8", errors="ignore")
            # Count doc comments (/// and //!)
            doc_count = content.count("///") + content.count("//!")
            if doc_count > 0:
                files_with_docs += 1
                total_doc_comments += doc_count
        except Exception as e:
            logger.debug(f"Failed to read {rs_file}: {e}")
            continue

    doc_coverage = files_with_docs / total_files if total_files > 0 else 0.0

    return DocStats(
        total_files=total_files,
        files_with_docs=files_with_docs,
        total_doc_comments=total_doc_comments,
        doc_coverage=doc_coverage,
        has_docs=files_with_docs > 0,
    )


async def run_license_check(
    crate_dir: Path,
    allowed_licenses: list[str] | None = None,
    timeout: int = 180,
    env: dict[str, str] | None = None,
    crate_name: str | None = None,
) -> LicenseResult | None:
    """
    Check licenses for a crate using cargo-license.

    Args:
        crate_dir: Path to crate directory
        allowed_licenses: List of allowed license names (optional)
        timeout: Command timeout in seconds

    Returns:
        LicenseResult with license information, or None if failed
    """
    if not check_cargo_available():
        logger.warning("cargo is not available")
        return None

    # Try cargo-license first (more reliable)
    cmd = build_cargo_subcommand_command("license", "--json")

    try:
        result = await run_command_async(
            cmd,
            cwd=crate_dir,
            timeout=timeout,
            env=env,
        )
        # Decode bytes to string if needed
        if isinstance(result.stdout, bytes):
            result.stdout = result.stdout.decode("utf-8", errors="replace")
        if isinstance(result.stderr, bytes):
            result.stderr = result.stderr.decode("utf-8", errors="replace")

        if result.returncode == 0 and result.stdout:
            try:
                data = json.loads(result.stdout)
                licenses = []
                crate_license = None

                # Parse cargo-license JSON output
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            license_name = item.get("license")
                            if license_name:
                                licenses.append(license_name)
                                # First item is usually the crate itself
                                if crate_license is None:
                                    crate_license = license_name
                elif isinstance(data, dict):
                    # Alternative format
                    crate_license = data.get("license") or data.get("crate_license")
                    deps = data.get("dependencies", [])
                    for dep in deps:
                        dep_license = dep.get("license")
                        if dep_license:
                            licenses.append(dep_license)

                # Check if any license is allowed using centralized function
                has_allowed = True
                if allowed_licenses and licenses:
                    from .utils import check_license_compliance

                    # Check each found license against allowlist
                    has_allowed = any(
                        check_license_compliance(lic, allowed_licenses)
                        for lic in licenses
                    )

                # Log license results
                log_path = None
                if crate_name:
                    raw_output = result.stdout or json.dumps(data, indent=2)
                    log_path = str(
                        _write_analysis_log(
                            crate_name, "license.json", raw_output.strip()
                        )
                    )

                return LicenseResult(
                    crate_license=crate_license,
                    all_licenses=list(set(licenses)),  # Deduplicate
                    has_allowed_license=has_allowed,
                    success=True,
                    log_path=log_path,
                )
            except json.JSONDecodeError:
                # Fall through to text parsing
                pass

        # Fallback: Try to parse Cargo.toml directly
        cargo_toml = crate_dir / "Cargo.toml"
        if cargo_toml.exists():
            try:
                content = cargo_toml.read_text(encoding="utf-8")
                # Simple regex to find license field
                license_match = re.search(
                    r'license\s*=\s*["\']([^"\']+)["\']', content, re.IGNORECASE
                )
                if license_match:
                    crate_license = license_match.group(1)
                    licenses = [crate_license]

                    # Check if license is allowed using centralized function
                    has_allowed = True
                    if allowed_licenses:
                        from .utils import check_license_compliance

                        has_allowed = check_license_compliance(
                            crate_license, allowed_licenses
                        )

                    # Log license results (from Cargo.toml fallback)
                    log_path = None
                    if crate_name:
                        license_data = {
                            "crate_license": crate_license,
                            "all_licenses": licenses,
                            "has_allowed_license": has_allowed,
                            "source": "Cargo.toml_fallback",
                        }
                        raw_output = json.dumps(license_data, indent=2)
                        log_path = str(
                            _write_analysis_log(
                                crate_name, "license.json", raw_output.strip()
                            )
                        )

                    return LicenseResult(
                        crate_license=crate_license,
                        all_licenses=licenses,
                        has_allowed_license=has_allowed,
                        success=True,
                        log_path=log_path,
                    )
            except Exception as e:
                logger.debug(f"Failed to parse Cargo.toml for license: {e}")

        # If cargo-license failed, return None (license check unavailable)
        return None

    except subprocess.TimeoutExpired:
        logger.warning(f"License check timed out for {crate_dir}")
        return None
    except Exception as e:
        logger.warning(f"Failed to run license check on {crate_dir}: {e}")
        return None


async def run_deny_check(
    crate_dir: Path, timeout: int = 300, env: dict[str, str] | None = None
) -> DenyResult | None:
    """
    Run cargo deny on a crate to check for security advisories and license violations.

    Args:
        crate_dir: Path to crate directory
        timeout: Command timeout in seconds
        env: Optional environment variables dict to pass to subprocess

    Returns:
        DenyResult with security and license audit results, or None if failed
    """
    if not check_cargo_available():
        logger.warning("cargo is not available")
        return None

    cmd = build_cargo_subcommand_command("deny", "check", "--format", "json")

    try:
        result = await run_command_async(
            cmd,
            cwd=crate_dir,
            timeout=timeout,
            env=env,
        )
        # Decode bytes to string if needed
        if isinstance(result.stdout, bytes):
            result.stdout = result.stdout.decode("utf-8", errors="replace")
        if isinstance(result.stderr, bytes):
            result.stderr = result.stderr.decode("utf-8", errors="replace")

        if result.returncode != 0 and not result.stdout:
            # cargo-deny may return non-zero on violations, but still output JSON
            return None

        advisories_found = 0
        license_violations = 0
        banned_dependencies = 0
        highest_severity = None
        passed = True

        try:
            data = json.loads(result.stdout)
            # Parse cargo-deny JSON output structure
            # Structure varies by version, but typically has 'advisories', 'licenses', 'bans'
            if isinstance(data, dict):
                # Advisories
                advisories = data.get("advisories", {})
                if isinstance(advisories, dict):
                    advisories_found = len(advisories.get("found", []))
                    # Extract highest severity
                    for adv in advisories.get("found", []):
                        severity = adv.get("severity", "").lower()
                        if severity and (
                            highest_severity is None
                            or _severity_rank(severity)
                            > _severity_rank(highest_severity)
                        ):
                            highest_severity = severity

                # License violations
                licenses = data.get("licenses", {})
                if isinstance(licenses, dict):
                    license_violations = len(licenses.get("violations", []))

                # Banned dependencies
                bans = data.get("bans", {})
                if isinstance(bans, dict):
                    banned_dependencies = len(bans.get("violations", []))

                # Determine if passed (no violations)
                passed = (
                    advisories_found == 0
                    and license_violations == 0
                    and banned_dependencies == 0
                )
        except json.JSONDecodeError:
            # If JSON parsing fails, check return code
            # cargo-deny returns 0 on success, non-zero on violations
            passed = result.returncode == 0

        return DenyResult(
            advisories_found=advisories_found,
            license_violations=license_violations,
            banned_dependencies=banned_dependencies,
            highest_severity=highest_severity,
            passed=passed,
            success=True,
        )

    except subprocess.TimeoutExpired:
        logger.warning(f"Deny check timed out for {crate_dir}")
        return None
    except Exception as e:
        logger.warning(f"Failed to run deny check on {crate_dir}: {e}")
        return None


def _severity_rank(severity: str) -> int:
    """Rank severity levels for comparison (higher = more severe)."""
    ranks = {"critical": 4, "high": 3, "medium": 2, "low": 1, "unknown": 0}
    return ranks.get(severity.lower(), 0)


async def analyze_crate(
    crate_dir: Path, config: Any | None = None, env: dict[str, str] | None = None
) -> CrateAnalysisReport:
    """
    Run all static analysis tools on a crate with early exit optimization.

    Early exit strategy:
    1. Check edition first (fast, synchronous)
    2. Run clippy (async, but checked before other tools)
    3. If clippy fails quality threshold, skip remaining analysis
    4. Run remaining tools in parallel only if crate passes early checks

    Args:
        crate_dir: Path to crate directory
        config: Optional pipeline config (for license checking)
        env: Optional environment variables for cargo commands

    Returns:
        CrateAnalysisReport with all analysis results
    """
    import asyncio

    from .utils import get_crate_edition

    crate_name = crate_dir.name.split("-")[0]  # Extract name from dir

    logger.info(f"Analyzing {crate_name}...")

    # STEP 1: Get edition first (synchronous, fast) - early exit if wrong edition
    edition = get_crate_edition(crate_dir)

    # STEP 2: Run clippy first (async) - early exit if too many warnings
    clippy_result = await run_clippy(crate_dir, env=env, crate_name=crate_name)

    # Early exit check: If clippy has too many bad_code warnings, skip expensive analysis
    # Use max_bad_code_warnings if set, otherwise fall back to max_clippy_warnings for backward compatibility
    if config:
        max_bad_code = getattr(config, "max_bad_code_warnings", None)
        max_total = getattr(config, "max_clippy_warnings", None)

        if max_bad_code is not None:
            if clippy_result.bad_code_warnings > max_bad_code:
                logger.debug(
                    f"{crate_name}: Early exit - {clippy_result.bad_code_warnings} bad_code clippy warnings "
                    f"> {max_bad_code}, skipping remaining analysis"
                )
        elif max_total is not None:
            if clippy_result.warning_count > max_total:
                logger.debug(
                    f"{crate_name}: Early exit - {clippy_result.warning_count} clippy warnings "
                    f"> {max_total}, skipping remaining analysis"
                )
            # Return minimal report with just edition and clippy results
            doc_stats = run_doc_check(crate_dir)  # Still need docs for filtering
            return CrateAnalysisReport(
                crate_name=crate_name,
                crate_dir=crate_dir,
                clippy=clippy_result,
                geiger=None,  # Skipped
                outdated=None,  # Skipped
                docs=doc_stats,
                license=None,  # Skipped
                deny=None,  # Skipped
                edition=edition,
            )

    # STEP 3: Run remaining analysis tools in parallel (only if crate passed early checks)
    # Run doc check (synchronous, fast - just file scanning)
    doc_stats = run_doc_check(crate_dir)

    # Run remaining analysis tools in parallel
    task_list = [
        run_geiger(crate_dir, env=env, crate_name=crate_name),
        run_outdated(crate_dir, env=env, crate_name=crate_name),
    ]

    # Add license check if enabled
    license_task = None
    if config and getattr(config, "enable_license_scan", False):
        allowed_licenses = getattr(config, "allowed_licenses", None)
        license_task = run_license_check(
            crate_dir, allowed_licenses, env=env, crate_name=crate_name
        )
        task_list.append(license_task)

    # Add cargo-deny check if enabled
    deny_task = None
    if config and getattr(config, "enable_deny_scan", False):
        deny_task = run_deny_check(crate_dir, env=env)
        task_list.append(deny_task)

    # Run remaining tasks in parallel
    results = await asyncio.gather(*task_list, return_exceptions=True)

    # Extract results (first 2 are always geiger, outdated)
    geiger_result: GeigerResult | None = None
    if not isinstance(results[0], BaseException):
        geiger_result = results[0]

    outdated_result: OutdatedResult | None = None
    if not isinstance(results[1], BaseException):
        outdated_result = results[1]

    # Extract optional results
    license_result: LicenseResult | None = None
    if license_task:
        license_idx = 2
        if license_idx < len(results):
            lr = results[license_idx]
            if not isinstance(lr, BaseException):
                license_result = lr  # type: ignore[assignment]

    deny_result: DenyResult | None = None
    if deny_task:
        deny_idx = 2 + (1 if license_task else 0)
        if deny_idx < len(results):
            dr = results[deny_idx]
            if not isinstance(dr, BaseException):
                deny_result = dr  # type: ignore[assignment]

    return CrateAnalysisReport(
        crate_name=crate_name,
        crate_dir=crate_dir,
        clippy=clippy_result,
        geiger=geiger_result,
        outdated=outdated_result,
        docs=doc_stats,
        license=license_result,
        deny=deny_result,
        edition=edition,
    )
