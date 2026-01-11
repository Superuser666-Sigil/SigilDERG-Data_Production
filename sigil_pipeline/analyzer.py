"""
Analyzer module for running static analysis tools on Rust crates.

Provides functions to run Clippy, Geiger, outdated, and documentation checks.
Includes optional caching of analysis results to avoid re-running expensive tools.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.6.0
"""

import json
import logging
import re
import subprocess
import threading
import tomllib
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .analysis_cache import AnalysisCache, get_cache
from . import sandbox
from .observability import get_metrics

# Import OS-agnostic cargo utilities from sigil_pipeline.utils
from .utils import (
    build_cargo_command,
    build_cargo_subcommand_command,
    check_cargo_available,
    run_command_async,
)

logger = logging.getLogger(__name__)


def _build_sandbox_options(
    crate_dir: Path,
    *,
    env: dict[str, str] | None,
    sandbox_mode: str,
    network_enabled: bool,
) -> sandbox.SandboxOptions:
    options = sandbox.SandboxOptions(
        mode=sandbox_mode,
        network_enabled=network_enabled,
        extra_whitelist=[crate_dir],
    )
    if env:
        target_dir = env.get("CARGO_TARGET_DIR")
        if target_dir:
            options.extra_whitelist.append(Path(target_dir))
    return options


async def _prefetch_dependencies(
    crate_dir: Path,
    *,
    env: dict[str, str] | None,
    timeout: int,
    sandbox_mode: str,
) -> None:
    """Fetch crate dependencies with networking enabled before sandboxed builds."""
    cmd = build_cargo_command("fetch")
    options = _build_sandbox_options(
        crate_dir, env=env, sandbox_mode=sandbox_mode, network_enabled=True
    )
    try:
        await sandbox.run_sandboxed_command_async(
            cmd,
            cwd=crate_dir,
            timeout=timeout,
            env=env,
            options=options,
        )
    except Exception as exc:
        logger.debug(f"Dependency prefetch failed for {crate_dir}: {exc}")


def parse_assistant_json_output(text: str) -> dict[str, Any]:
    """
    Robustly parse assistant output that is intended to be a single JSON object.

    Strategy:
    1. Try json.loads on the whole text.
    2. If that fails, try parsing JSON blocks from code fences.
    3. If still fails, search for a balanced `{...}` substring outside code fences.
    4. If still fails, attempt to extract code fences and assemble a minimal object.

    Returns a dict (possibly empty) with parsed keys.
    """
    text = text or ""
    stripped = text.strip()
    metrics = get_metrics()
    parse_success = False
    used_fallback = False

    def record_result() -> None:
        metrics.increment(
            "llm_json_parse_total",
            help_text="Total LLM JSON parse attempts",
        )
        if parse_success:
            metrics.increment(
                "llm_json_parse_success",
                help_text="LLM JSON parse successes",
            )
        else:
            metrics.increment(
                "llm_json_parse_failure",
                help_text="LLM JSON parse failures",
            )
        if used_fallback:
            metrics.increment(
                "llm_json_parse_fallback",
                help_text="LLM JSON parse fallbacks to non-JSON extraction",
            )

    def parse_json_object(candidate: str, allow_empty: bool) -> dict[str, Any] | None:
        try:
            parsed = json.loads(candidate)
        except Exception:
            return None
        if not isinstance(parsed, dict):
            return None
        if parsed or allow_empty:
            return parsed
        return None

    def looks_like_json_object(candidate: str, allow_empty: bool) -> bool:
        if candidate.strip() == "{}":
            return allow_empty
        if ":" not in candidate:
            return False
        return bool(re.search(r'"[^"]+"\s*:', candidate))

    def iter_brace_candidates(payload: str) -> list[str]:
        stack: list[int] = []
        start = None
        candidates: list[str] = []
        for i, ch in enumerate(payload):
            if ch == "{":
                if start is None:
                    start = i
                stack.append(i)
            elif ch == "}":
                if stack:
                    stack.pop()
                    if not stack and start is not None:
                        candidates.append(payload[start : i + 1])
                        start = None
        return candidates

    def extract_json_object(payload: str, allow_empty: bool) -> dict[str, Any] | None:
        candidate = payload.strip()
        if candidate:
            parsed = parse_json_object(candidate, allow_empty)
            if parsed is not None:
                return parsed
        for brace_candidate in iter_brace_candidates(payload):
            if not looks_like_json_object(brace_candidate, allow_empty):
                continue
            parsed = parse_json_object(brace_candidate, allow_empty)
            if parsed is not None:
                return parsed
        return None

    allow_empty = stripped == "{}"

    # 1) Try full JSON
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            parse_success = True
            record_result()
            return parsed
    except Exception:
        pass

    # 2) Try JSON in code fences
    code_blocks: list[str] = []
    for match in re.finditer(
        r"```(?P<lang>[A-Za-z0-9_+-]+)?\s*\n(?P<content>[\s\S]*?)```",
        text,
        flags=re.IGNORECASE,
    ):
        content = match.group("content").strip()
        if not content:
            continue
        code_blocks.append(content)
        parsed = extract_json_object(content, allow_empty)
        if parsed is not None:
            parse_success = True
            record_result()
            return parsed

    # 3) Search for JSON outside of code fences
    text_without_fences = re.sub(r"```[\s\S]*?```", "", text)
    parsed = extract_json_object(text_without_fences, allow_empty)
    if parsed is not None:
        parse_success = True
        record_result()
        return parsed

    # 4) Fallback: extract code blocks and key-like prefixes
    result: dict[str, Any] = {}
    used_fallback = True
    # Extract code fences ```...```
    if code_blocks:
        # Put first block into 'code_after' and raw into 'code'
        result["code_after"] = code_blocks[0].strip()
    # Extract lines like 'Explanation: ...' or 'Rationale: ...'
    for key in ("explanation", "rationale", "review_comment", "test"):
        m = re.search(rf"{key.capitalize()}:\s*(.+)", text)
        if m:
            result[key] = m.group(1).strip()

    # If nothing found, put whole assistant text into 'assistant' key
    if not result:
        result["assistant"] = text.strip()

    record_result()
    return result


def get_crate_source_paths(crate_dir: Path) -> list[Path]:
    """
    Get the source directories for a Rust crate by parsing Cargo.toml.

    Handles non-standard layouts where source files are not in src/
    (e.g., tree-sitter uses binding_rust/lib.rs).

    Args:
        crate_dir: Path to the crate directory.

    Returns:
        List of directories containing .rs source files.
        Falls back to [crate_dir / "src"] if parsing fails or no paths found.
    """
    cargo_toml = crate_dir / "Cargo.toml"
    source_dirs: set[Path] = set()

    # Default fallback
    default_src = crate_dir / "src"

    if not cargo_toml.exists():
        return [default_src] if default_src.exists() else []

    try:
        content = cargo_toml.read_text(encoding="utf-8")
        manifest = tomllib.loads(content)

        # Check [lib] section for custom path
        if "lib" in manifest:
            lib_path = manifest["lib"].get("path")
            if lib_path:
                lib_file = crate_dir / lib_path
                if lib_file.exists():
                    source_dirs.add(lib_file.parent)

        # Check [[bin]] sections for custom paths
        for bin_target in manifest.get("bin", []):
            bin_path = bin_target.get("path")
            if bin_path:
                bin_file = crate_dir / bin_path
                if bin_file.exists():
                    source_dirs.add(bin_file.parent)

        # Check [[example]], [[test]], [[bench]] sections
        for section in ("example", "test", "bench"):
            for target in manifest.get(section, []):
                target_path = target.get("path")
                if target_path:
                    target_file = crate_dir / target_path
                    if target_file.exists():
                        source_dirs.add(target_file.parent)

    except (tomllib.TOMLDecodeError, OSError, KeyError) as e:
        logger.debug(f"Failed to parse Cargo.toml for source paths: {e}")

    # Always include src/ if it exists (standard layout)
    if default_src.exists():
        source_dirs.add(default_src)

    # If no source dirs found, fall back to default
    if not source_dirs:
        return [default_src] if default_src.exists() else []

    return list(source_dirs)


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
class RustfmtResult:
    """Results from running cargo fmt --check."""

    passed: bool = False
    """Whether all files are properly formatted."""
    unformatted_files: list[str] = field(default_factory=list)
    """List of files that need formatting."""
    style_edition: str | None = None
    """Style edition used for formatting check."""
    success: bool = True
    """Whether cargo fmt ran successfully."""
    log_path: str | None = None
    """Path to detailed log file."""


@dataclass
class StrictClippyResult:
    """Results from strict Clippy analysis (pedantic/nursery)."""

    passed: bool = False
    """Whether all strict Clippy checks passed."""
    pedantic_warnings: int = 0
    """Count of pedantic lint warnings."""
    nursery_warnings: int = 0
    """Count of nursery lint warnings."""
    denied_antipatterns: int = 0
    """Count of denied anti-patterns (unwrap, expect, panic)."""
    warning_details: list[dict] = field(default_factory=list)
    """Details of each warning for debugging."""
    success: bool = True
    """Whether strict Clippy ran successfully."""
    log_path: str | None = None
    """Path to detailed log file."""


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
    # Hardening mode results
    rustfmt: RustfmtResult | None = None
    strict_clippy: StrictClippyResult | None = None


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
    sandbox_mode: str = "auto",
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
        options = _build_sandbox_options(
            crate_dir, env=env, sandbox_mode=sandbox_mode, network_enabled=False
        )
        result = await sandbox.run_sandboxed_command_async(
            cmd,
            cwd=crate_dir,
            timeout=timeout,
            env=env,
            options=options,
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


async def run_clippy_strict(
    crate_dir: Path,
    timeout: int = 600,
    env: dict[str, str] | None = None,
    crate_name: str | None = None,
    deny_antipatterns: bool = True,
    sandbox_mode: str = "auto",
) -> StrictClippyResult:
    """
    Run cargo clippy with strict settings for dataset hardening.

    Enables pedantic and nursery lint groups, and optionally denies
    common anti-patterns (unwrap, expect, panic).

    Args:
        crate_dir: Path to crate directory
        timeout: Command timeout in seconds (default: 600, longer than regular Clippy)
        env: Environment variables for cargo
        crate_name: Crate name for logging
        deny_antipatterns: Whether to deny unwrap/expect/panic (default: True)

    Returns:
        StrictClippyResult with detailed analysis
    """
    if not check_cargo_available():
        logger.error("cargo is not available")
        return StrictClippyResult(success=False)

    # Build strict Clippy command with pedantic and nursery
    cmd_args = [
        "clippy",
        "--message-format=json",
        "--quiet",
        "--",
        "-W",
        "clippy::all",
        "-W",
        "clippy::pedantic",
        "-W",
        "clippy::nursery",
    ]

    # Add deny flags for anti-patterns
    if deny_antipatterns:
        cmd_args.extend(
            [
                "-D",
                "clippy::unwrap_used",
                "-D",
                "clippy::expect_used",
                "-D",
                "clippy::panic",
            ]
        )

    cmd = build_cargo_command(*cmd_args)

    try:
        options = _build_sandbox_options(
            crate_dir, env=env, sandbox_mode=sandbox_mode, network_enabled=False
        )
        result = await sandbox.run_sandboxed_command_async(
            cmd,
            cwd=crate_dir,
            timeout=timeout,
            env=env,
            options=options,
        )

        # Decode bytes to string if needed
        if isinstance(result.stdout, bytes):
            result.stdout = result.stdout.decode("utf-8", errors="replace")
        if isinstance(result.stderr, bytes):
            result.stderr = result.stderr.decode("utf-8", errors="replace")

        pedantic_warnings = 0
        nursery_warnings = 0
        denied_antipatterns = 0
        warning_details: list[dict] = []
        errors = []

        # Parse JSON output
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            try:
                msg = json.loads(line)
                if msg.get("reason") == "compiler-message":
                    message_data = msg.get("message", {})
                    level = message_data.get("level", "")
                    code_obj = message_data.get("code", {})
                    code_str = code_obj.get("code", "") if code_obj else ""

                    if level in ("warning", "error"):
                        detail = {
                            "level": level,
                            "code": code_str,
                            "message": message_data.get("message", ""),
                        }
                        warning_details.append(detail)

                        # Categorize by lint source
                        if "clippy::pedantic" in code_str or any(
                            p in code_str
                            for p in [
                                "doc_markdown",
                                "too_many_lines",
                                "cognitive_complexity",
                                "similar_names",
                            ]
                        ):
                            pedantic_warnings += 1
                        elif "clippy::nursery" in code_str:
                            nursery_warnings += 1

                        # Track denied anti-patterns
                        if code_str in (
                            "clippy::unwrap_used",
                            "clippy::expect_used",
                            "clippy::panic",
                        ):
                            denied_antipatterns += 1

                    if level == "error":
                        errors.append(msg)

            except json.JSONDecodeError:
                continue

        # Write log
        log_path = None
        if crate_name:
            log_content = result.stdout or result.stderr or ""
            log_path = str(
                _write_analysis_log(
                    crate_name, "clippy_strict.log", log_content.strip()
                )
            )

        # Strict check passes only if no errors and no denied antipatterns
        passed = len(errors) == 0 and denied_antipatterns == 0

        return StrictClippyResult(
            passed=passed,
            pedantic_warnings=pedantic_warnings,
            nursery_warnings=nursery_warnings,
            denied_antipatterns=denied_antipatterns,
            warning_details=warning_details,
            success=True,
            log_path=log_path,
        )

    except subprocess.TimeoutExpired:
        logger.warning(f"Strict Clippy timed out for {crate_dir}")
        return StrictClippyResult(success=False)
    except Exception as e:
        logger.error(f"Failed to run strict clippy on {crate_dir}: {e}")
        return StrictClippyResult(success=False)


async def run_rustfmt_check(
    crate_dir: Path,
    timeout: int = 120,
    env: dict[str, str] | None = None,
    crate_name: str | None = None,
    style_edition: str | None = None,
    sandbox_mode: str = "auto",
) -> RustfmtResult:
    """
    Run cargo fmt --check to verify code formatting.

    Optionally validates against a specific style edition (e.g., 2024).

    Args:
        crate_dir: Path to crate directory
        timeout: Command timeout in seconds
        env: Environment variables for cargo
        crate_name: Crate name for logging
        style_edition: Target style edition (optional)

    Returns:
        RustfmtResult with formatting check results
    """
    if not check_cargo_available():
        logger.error("cargo is not available")
        return RustfmtResult(success=False)

    # Create temporary rustfmt.toml with style_edition if requested
    rustfmt_toml = crate_dir / ".rustfmt.toml"
    rustfmt_toml_existed = rustfmt_toml.exists()
    temp_rustfmt_created = False

    try:
        if style_edition:
            # Check if .rustfmt.toml already has style_edition
            if rustfmt_toml_existed:
                content = rustfmt_toml.read_text(encoding="utf-8")
                if "style_edition" not in content:
                    # Append style_edition to existing config
                    with open(rustfmt_toml, "a", encoding="utf-8") as f:
                        f.write(f'\nstyle_edition = "{style_edition}"\n')
                    temp_rustfmt_created = True
            else:
                # Create new config with style_edition
                rustfmt_toml.write_text(
                    f'style_edition = "{style_edition}"\n', encoding="utf-8"
                )
                temp_rustfmt_created = True

        cmd = build_cargo_command("fmt", "--check")

        options = _build_sandbox_options(
            crate_dir, env=env, sandbox_mode=sandbox_mode, network_enabled=False
        )
        result = await sandbox.run_sandboxed_command_async(
            cmd,
            cwd=crate_dir,
            timeout=timeout,
            env=env,
            options=options,
        )

        # Decode output
        if isinstance(result.stdout, bytes):
            result.stdout = result.stdout.decode("utf-8", errors="replace")
        if isinstance(result.stderr, bytes):
            result.stderr = result.stderr.decode("utf-8", errors="replace")

        # Parse unformatted files from output
        unformatted_files: list[str] = []
        output = result.stdout + result.stderr
        for line in output.splitlines():
            # cargo fmt --check outputs "Diff in <file>" lines
            if line.startswith("Diff in "):
                file_path = line.replace("Diff in ", "").strip()
                unformatted_files.append(file_path)

        # Write log
        log_path = None
        if crate_name and (unformatted_files or result.returncode != 0):
            log_path = str(
                _write_analysis_log(crate_name, "rustfmt.log", output.strip())
            )

        passed = result.returncode == 0

        return RustfmtResult(
            passed=passed,
            unformatted_files=unformatted_files,
            style_edition=style_edition,
            success=True,
            log_path=log_path,
        )

    except subprocess.TimeoutExpired:
        logger.warning(f"rustfmt timed out for {crate_dir}")
        return RustfmtResult(success=False)
    except Exception as e:
        logger.error(f"Failed to run rustfmt on {crate_dir}: {e}")
        return RustfmtResult(success=False)
    finally:
        # Clean up temporary rustfmt.toml modifications
        if temp_rustfmt_created and style_edition:
            try:
                if rustfmt_toml_existed:
                    # Restore original file by removing our addition
                    content = rustfmt_toml.read_text(encoding="utf-8")
                    content = content.replace(
                        f'\nstyle_edition = "{style_edition}"\n', ""
                    )
                    rustfmt_toml.write_text(content, encoding="utf-8")
                else:
                    # Remove file we created
                    rustfmt_toml.unlink()
            except Exception:
                pass  # Best effort cleanup


async def run_geiger(
    crate_dir: Path,
    timeout: int = 300,
    env: dict[str, str] | None = None,
    crate_name: str | None = None,
    sandbox_mode: str = "auto",
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
        options = _build_sandbox_options(
            crate_dir, env=env, sandbox_mode=sandbox_mode, network_enabled=False
        )
        result = await sandbox.run_sandboxed_command_async(
            cmd,
            cwd=crate_dir,
            timeout=timeout,
            env=env,
            options=options,
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

    Handles non-standard source layouts by parsing Cargo.toml to find
    actual source directories (e.g., tree-sitter uses binding_rust/).

    Args:
        crate_dir: Path to crate directory

    Returns:
        DocStats with documentation metrics
    """
    source_dirs = get_crate_source_paths(crate_dir)
    if not source_dirs:
        return DocStats()

    total_files = 0
    files_with_docs = 0
    total_doc_comments = 0
    seen_files: set[Path] = set()

    # Count .rs files and doc comments across all source directories
    for src_dir in source_dirs:
        for rs_file in src_dir.rglob("*.rs"):
            # Avoid counting files twice if directories overlap
            if rs_file in seen_files:
                continue
            seen_files.add(rs_file)

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
    crate_dir: Path,
    config: Any | None = None,
    env: dict[str, str] | None = None,
    use_cache: bool | None = None,
) -> CrateAnalysisReport:
    """
    Run all static analysis tools on a crate with early exit optimization and caching.

    Early exit strategy:
    1. Check edition first (fast, synchronous)
    2. Run clippy (async, but checked before other tools)
    3. If clippy fails quality threshold, skip remaining analysis
    4. Run remaining tools in parallel only if crate passes early checks

    Caching:
    - If enabled, computes a content hash of the crate
    - Returns cached results if available and valid
    - Caches new results after successful analysis

    Args:
        crate_dir: Path to crate directory
        config: Optional pipeline config (for license checking and cache settings)
        env: Optional environment variables for cargo commands
        use_cache: Override cache setting (uses config.enable_analysis_cache if None)

    Returns:
        CrateAnalysisReport with all analysis results
    """
    import asyncio

    from .utils import get_crate_edition

    crate_name = crate_dir.name.split("-")[0]  # Extract name from dir

    logger.info(f"Analyzing {crate_name}...")

    # Determine if caching is enabled
    cache_enabled = use_cache
    if cache_enabled is None and config:
        cache_enabled = getattr(config, "enable_analysis_cache", True)
    if cache_enabled is None:
        cache_enabled = True  # Default to enabled

    # Get cache instance if enabled
    cache: AnalysisCache | None = None
    crate_hash: str | None = None
    if cache_enabled:
        cache_dir = (
            getattr(config, "analysis_cache_dir", ".cache/analysis")
            if config
            else ".cache/analysis"
        )
        cache = get_cache(cache_dir)
        crate_hash = cache.compute_crate_hash(crate_dir)

        # Try to get cached full report
        cached_report = cache.get(crate_hash, "full_report")
        if cached_report:
            logger.debug(f"Cache hit for {crate_name}, using cached analysis")
            return _deserialize_report(cached_report, crate_dir)

    # STEP 1: Get edition first (synchronous, fast) - early exit if wrong edition
    edition = get_crate_edition(crate_dir)

    # STEP 2: Run clippy first (async) - early exit if too many warnings
    sandbox_mode = getattr(config, "sandbox_mode", "auto") if config else "auto"
    try:
        resolved_mode = sandbox.resolve_mode(sandbox_mode)
    except Exception:
        resolved_mode = "none"
    if resolved_mode == "firejail":
        prefetch_timeout = 300
        await _prefetch_dependencies(
            crate_dir, env=env, timeout=prefetch_timeout, sandbox_mode=sandbox_mode
        )
    clippy_result = await run_clippy(
        crate_dir, env=env, crate_name=crate_name, sandbox_mode=sandbox_mode
    )

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
        run_geiger(
            crate_dir, env=env, crate_name=crate_name, sandbox_mode=sandbox_mode
        ),
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

    # STEP 4: Run hardening checks if enabled
    strict_clippy_result: StrictClippyResult | None = None
    rustfmt_result: RustfmtResult | None = None

    if config and getattr(config, "dataset_hardening", False):
        hardening_tasks = []

        # Add strict clippy if enabled
        if getattr(config, "hardening_strict_clippy", True):
            deny_antipatterns = getattr(config, "hardening_deny_antipatterns", True)
            hardening_tasks.append(
                run_clippy_strict(
                    crate_dir,
                    env=env,
                    crate_name=crate_name,
                    deny_antipatterns=deny_antipatterns,
                    sandbox_mode=sandbox_mode,
                )
            )
        else:
            # Use asyncio.sleep(0) as a lightweight coroutine that returns None
            hardening_tasks.append(asyncio.sleep(0))  # Placeholder

        # Add rustfmt check if enabled
        if getattr(config, "hardening_require_rustfmt", True):
            style_edition = getattr(config, "rustfmt_style_edition", None)
            if style_edition:
                style_edition = str(style_edition).strip()
                if style_edition.lower() in ("none", "null", ""):
                    style_edition = None
            hardening_tasks.append(
                run_rustfmt_check(
                    crate_dir,
                    env=env,
                    crate_name=crate_name,
                    style_edition=style_edition,
                    sandbox_mode=sandbox_mode,
                )
            )
        else:
            # Use asyncio.sleep(0) as a lightweight coroutine that returns None
            hardening_tasks.append(asyncio.sleep(0))  # Placeholder

        hardening_results = await asyncio.gather(
            *hardening_tasks, return_exceptions=True
        )

        # Extract hardening results
        if getattr(config, "hardening_strict_clippy", True):
            hr = hardening_results[0]
            if not isinstance(hr, BaseException) and hr is not None:
                strict_clippy_result = hr

        if getattr(config, "hardening_require_rustfmt", True):
            hr = hardening_results[1]
            if not isinstance(hr, BaseException) and hr is not None:
                rustfmt_result = hr

    report = CrateAnalysisReport(
        crate_name=crate_name,
        crate_dir=crate_dir,
        clippy=clippy_result,
        geiger=geiger_result,
        outdated=outdated_result,
        docs=doc_stats,
        license=license_result,
        deny=deny_result,
        edition=edition,
        rustfmt=rustfmt_result,
        strict_clippy=strict_clippy_result,
    )

    # Cache the result if caching is enabled
    if cache and crate_hash:
        try:
            serialized = _serialize_report(report)
            cache.put(crate_hash, "full_report", serialized)
            logger.debug(f"Cached analysis result for {crate_name}")
        except Exception as e:
            logger.debug(f"Failed to cache result for {crate_name}: {e}")

    return report


def _serialize_report(report: CrateAnalysisReport) -> dict[str, Any]:
    """Serialize a CrateAnalysisReport to a dict for caching."""
    return {
        "crate_name": report.crate_name,
        "crate_dir": str(report.crate_dir),
        "clippy": asdict(report.clippy) if report.clippy else None,
        "geiger": asdict(report.geiger) if report.geiger else None,
        "outdated": asdict(report.outdated) if report.outdated else None,
        "docs": asdict(report.docs) if report.docs else None,
        "license": asdict(report.license) if report.license else None,
        "deny": asdict(report.deny) if report.deny else None,
        "edition": report.edition,
        "rejection_log_path": report.rejection_log_path,
        "rustfmt": asdict(report.rustfmt) if report.rustfmt else None,
        "strict_clippy": asdict(report.strict_clippy) if report.strict_clippy else None,
    }


def _deserialize_report(data: dict[str, Any], crate_dir: Path) -> CrateAnalysisReport:
    """Deserialize a cached dict back to a CrateAnalysisReport."""
    clippy = ClippyResult(**data["clippy"]) if data.get("clippy") else ClippyResult()
    geiger = GeigerResult(**data["geiger"]) if data.get("geiger") else None
    outdated = OutdatedResult(**data["outdated"]) if data.get("outdated") else None
    docs = DocStats(**data["docs"]) if data.get("docs") else None
    license_result = LicenseResult(**data["license"]) if data.get("license") else None
    deny = DenyResult(**data["deny"]) if data.get("deny") else None
    rustfmt = RustfmtResult(**data["rustfmt"]) if data.get("rustfmt") else None
    strict_clippy = (
        StrictClippyResult(**data["strict_clippy"])
        if data.get("strict_clippy")
        else None
    )

    return CrateAnalysisReport(
        crate_name=data["crate_name"],
        crate_dir=crate_dir,
        clippy=clippy,
        geiger=geiger,
        outdated=outdated,
        docs=docs,
        license=license_result,
        deny=deny,
        edition=data.get("edition"),
        rejection_log_path=data.get("rejection_log_path"),
        rustfmt=rustfmt,
        strict_clippy=strict_clippy,
    )
