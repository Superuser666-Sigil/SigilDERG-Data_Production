"""
Environment fingerprinting for reproducibility and audit.

Captures Rust toolchain versions, platform info, and tool availability
to ensure "same inputs, same toolchain" can be verified across runs.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.6.0
"""

import logging
import platform
import shutil
import subprocess
import sys
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ToolchainInfo:
    """Rust toolchain version information."""

    rustc_version: str | None = None
    cargo_version: str | None = None
    clippy_version: str | None = None
    rustfmt_version: str | None = None


@dataclass
class CargoToolAvailability:
    """Availability of cargo subcommand tools."""

    clippy: bool = False
    geiger: bool = False
    outdated: bool = False
    deny: bool = False
    audit: bool = False
    license: bool = False


@dataclass
class PlatformInfo:
    """Platform and system information."""

    os: str = ""
    os_release: str = ""
    architecture: str = ""
    python_version: str = ""
    hostname: str = ""


@dataclass
class DependencyVersions:
    """Versions of key Python dependencies."""

    tree_sitter: str | None = None
    tree_sitter_rust: str | None = None
    structlog: str | None = None
    aiohttp: str | None = None
    pydantic: str | None = None


@dataclass
class EnvironmentFingerprint:
    """Complete environment fingerprint for reproducibility."""

    timestamp: str = ""
    toolchain: ToolchainInfo = field(default_factory=ToolchainInfo)
    cargo_tools: CargoToolAvailability = field(default_factory=CargoToolAvailability)
    platform: PlatformInfo = field(default_factory=PlatformInfo)
    dependencies: DependencyVersions = field(default_factory=DependencyVersions)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "toolchain": {
                "rustc_version": self.toolchain.rustc_version,
                "cargo_version": self.toolchain.cargo_version,
                "clippy_version": self.toolchain.clippy_version,
                "rustfmt_version": self.toolchain.rustfmt_version,
            },
            "cargo_tools": {
                "clippy": self.cargo_tools.clippy,
                "geiger": self.cargo_tools.geiger,
                "outdated": self.cargo_tools.outdated,
                "deny": self.cargo_tools.deny,
                "audit": self.cargo_tools.audit,
                "license": self.cargo_tools.license,
            },
            "platform": {
                "os": self.platform.os,
                "os_release": self.platform.os_release,
                "architecture": self.platform.architecture,
                "python_version": self.platform.python_version,
                "hostname": self.platform.hostname,
            },
            "dependencies": {
                "tree_sitter": self.dependencies.tree_sitter,
                "tree_sitter_rust": self.dependencies.tree_sitter_rust,
                "structlog": self.dependencies.structlog,
                "aiohttp": self.dependencies.aiohttp,
                "pydantic": self.dependencies.pydantic,
            },
        }


def _run_version_command(cmd: list[str], timeout: int = 10) -> str | None:
    """
    Run a version command and extract the output.

    Args:
        cmd: Command to run (e.g., ["rustc", "--version"])
        timeout: Timeout in seconds

    Returns:
        Version string or None if command failed
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.debug(f"Failed to run {' '.join(cmd)}: {e}")
        return None


def _check_cargo_tool(tool_name: str) -> bool:
    """
    Check if a cargo subcommand tool is available.

    Args:
        tool_name: Name of the cargo subcommand (e.g., "clippy", "geiger")

    Returns:
        True if tool is available
    """
    # Get the cargo executable
    cargo = shutil.which("cargo.exe") or shutil.which("cargo")
    if not cargo:
        return False

    # Try running cargo <tool> --help (fast check)
    try:
        result = subprocess.run(
            [cargo, tool_name, "--help"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def _get_python_package_version(package_name: str) -> str | None:
    """
    Get the version of an installed Python package.

    Args:
        package_name: Name of the package

    Returns:
        Version string or None if not installed
    """
    try:
        from importlib.metadata import version

        return version(package_name)
    except Exception:
        return None


def capture_toolchain_info() -> ToolchainInfo:
    """
    Capture Rust toolchain version information.

    Returns:
        ToolchainInfo with version strings
    """
    info = ToolchainInfo()

    # Get rustc version
    info.rustc_version = _run_version_command(["rustc", "--version"])

    # Get cargo version
    info.cargo_version = _run_version_command(["cargo", "--version"])

    # Get clippy version (if available)
    clippy_output = _run_version_command(["cargo", "clippy", "--version"])
    if clippy_output:
        info.clippy_version = clippy_output

    # Get rustfmt version (if available)
    rustfmt_output = _run_version_command(["rustfmt", "--version"])
    if rustfmt_output:
        info.rustfmt_version = rustfmt_output

    return info


def capture_cargo_tool_availability() -> CargoToolAvailability:
    """
    Check availability of cargo subcommand tools.

    Returns:
        CargoToolAvailability with boolean flags
    """
    availability = CargoToolAvailability()

    availability.clippy = _check_cargo_tool("clippy")
    availability.geiger = _check_cargo_tool("geiger")
    availability.outdated = _check_cargo_tool("outdated")
    availability.deny = _check_cargo_tool("deny")
    availability.audit = _check_cargo_tool("audit")
    availability.license = _check_cargo_tool("license")

    return availability


def capture_platform_info() -> PlatformInfo:
    """
    Capture platform and system information.

    Returns:
        PlatformInfo with system details
    """
    info = PlatformInfo()

    info.os = platform.system()
    info.os_release = platform.release()
    info.architecture = platform.machine()
    info.python_version = sys.version.split()[0]

    try:
        info.hostname = platform.node()
    except Exception:
        info.hostname = "unknown"

    return info


def capture_dependency_versions() -> DependencyVersions:
    """
    Capture versions of key Python dependencies.

    Returns:
        DependencyVersions with version strings
    """
    versions = DependencyVersions()

    versions.tree_sitter = _get_python_package_version("tree-sitter")
    versions.tree_sitter_rust = _get_python_package_version("tree-sitter-rust")
    versions.structlog = _get_python_package_version("structlog")
    versions.aiohttp = _get_python_package_version("aiohttp")
    versions.pydantic = _get_python_package_version("pydantic")

    return versions


def capture_environment() -> EnvironmentFingerprint:
    """
    Capture complete environment fingerprint.

    Returns:
        EnvironmentFingerprint with all captured information
    """
    fingerprint = EnvironmentFingerprint()

    fingerprint.timestamp = datetime.now(timezone.utc).isoformat()
    fingerprint.toolchain = capture_toolchain_info()
    fingerprint.cargo_tools = capture_cargo_tool_availability()
    fingerprint.platform = capture_platform_info()
    fingerprint.dependencies = capture_dependency_versions()

    return fingerprint


def log_environment_summary(fingerprint: EnvironmentFingerprint) -> None:
    """
    Log a summary of the environment fingerprint.

    Args:
        fingerprint: The captured environment fingerprint
    """
    logger.info("=== Environment Fingerprint ===")
    logger.info(f"Timestamp: {fingerprint.timestamp}")

    # Toolchain
    if fingerprint.toolchain.rustc_version:
        logger.info(f"Rust: {fingerprint.toolchain.rustc_version}")
    else:
        logger.warning("Rust: NOT FOUND")

    if fingerprint.toolchain.cargo_version:
        logger.info(f"Cargo: {fingerprint.toolchain.cargo_version}")
    else:
        logger.warning("Cargo: NOT FOUND")

    if fingerprint.toolchain.clippy_version:
        logger.info(f"Clippy: {fingerprint.toolchain.clippy_version}")

    # Platform
    logger.info(
        f"Platform: {fingerprint.platform.os} {fingerprint.platform.os_release} "
        f"({fingerprint.platform.architecture})"
    )
    logger.info(f"Python: {fingerprint.platform.python_version}")

    # Cargo tools availability
    tools_available = []
    tools_missing = []
    for tool, available in [
        ("clippy", fingerprint.cargo_tools.clippy),
        ("geiger", fingerprint.cargo_tools.geiger),
        ("outdated", fingerprint.cargo_tools.outdated),
        ("deny", fingerprint.cargo_tools.deny),
        ("audit", fingerprint.cargo_tools.audit),
        ("license", fingerprint.cargo_tools.license),
    ]:
        if available:
            tools_available.append(tool)
        else:
            tools_missing.append(tool)

    if tools_available:
        logger.info(f"Cargo tools available: {', '.join(tools_available)}")
    if tools_missing:
        logger.info(f"Cargo tools missing: {', '.join(tools_missing)}")

    # Key dependencies
    if fingerprint.dependencies.tree_sitter:
        logger.info(f"tree-sitter: {fingerprint.dependencies.tree_sitter}")
    if fingerprint.dependencies.tree_sitter_rust:
        logger.info(f"tree-sitter-rust: {fingerprint.dependencies.tree_sitter_rust}")

    logger.info("================================")


def write_environment_file(fingerprint: EnvironmentFingerprint, path: Path) -> None:
    """
    Write environment fingerprint to a JSON file.

    Args:
        fingerprint: The captured environment fingerprint
        path: Path to write the JSON file
    """
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(fingerprint.to_dict(), f, indent=2)
    logger.debug(f"Environment fingerprint written to {path}")


@dataclass
class HardeningToolchainResult:
    """Result of hardening toolchain validation."""

    supported: bool = False
    """Whether the toolchain supports all hardening features."""

    rustc_version: str | None = None
    """Detected rustc version string."""

    rustc_minor: int | None = None
    """Parsed rustc minor version (e.g., 85 for 1.85.0)."""

    rustfmt_supports_2024_style: bool = False
    """Whether rustfmt supports style_edition = '2024'."""

    is_nightly: bool = False
    """Whether using nightly toolchain (better for nursery lints)."""

    error_message: str | None = None
    """Human-readable error message if not supported."""

    warnings: list[str] = field(default_factory=list)
    """Non-fatal warnings about the toolchain."""


def _parse_rustc_version(version_str: str | None) -> tuple[int | None, bool]:
    """
    Parse rustc version string to extract minor version and nightly status.

    Args:
        version_str: Output from `rustc --version` (e.g., "rustc 1.85.0 (abcdef 2025-01-01)")

    Returns:
        Tuple of (minor_version, is_nightly)
    """
    if not version_str:
        return None, False

    # Match patterns like "rustc 1.85.0" or "rustc 1.93.0-nightly"
    match = re.search(r"rustc\s+(\d+)\.(\d+)\.(\d+)(?:-(\w+))?", version_str)
    if not match:
        return None, False

    minor = int(match.group(2))
    channel = match.group(4) if match.group(4) else "stable"
    is_nightly = channel == "nightly"

    return minor, is_nightly


def _parse_rustfmt_version(version_str: str | None) -> tuple[int, int, int] | None:
    if not version_str:
        return None
    match = re.search(r"rustfmt\s+(\d+)\.(\d+)\.(\d+)", version_str)
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def _rustfmt_supports_style_edition(
    style_edition: str, rustfmt_version: str | None
) -> bool:
    if not style_edition:
        return True
    if style_edition != "2024":
        return True
    parsed = _parse_rustfmt_version(rustfmt_version)
    if not parsed:
        return False
    return parsed >= (1, 8, 0)


def check_hardening_toolchain(
    min_edition: str = "2024", style_edition: str | None = None
) -> HardeningToolchainResult:
    """
    Validate that the Rust toolchain supports dataset hardening features.

    Checks:
    1. rustc version >= 1.85 (required for edition 2024)
    2. rustfmt supports the requested style_edition (2024 requires rustfmt 1.8+)
    3. Clippy is available

    Args:
        min_edition: Minimum required edition (default: "2024")
        style_edition: Rustfmt style_edition to validate (defaults to min_edition)

    Returns:
        HardeningToolchainResult with validation results
    """
    result = HardeningToolchainResult()

    # Minimum rustc version for edition 2024
    MIN_RUSTC_MINOR_FOR_2024 = 85

    # Get rustc version
    result.rustc_version = _run_version_command(["rustc", "--version"])
    if not result.rustc_version:
        result.error_message = (
            "rustc not found. Please install Rust toolchain.\n"
            "See: docs/runbooks/RUST_2024_TOOLCHAIN_SETUP.md"
        )
        return result

    # Parse version
    result.rustc_minor, result.is_nightly = _parse_rustc_version(result.rustc_version)
    if result.rustc_minor is None:
        result.error_message = (
            f"Could not parse rustc version from: {result.rustc_version}\n"
            "See: docs/runbooks/RUST_2024_TOOLCHAIN_SETUP.md"
        )
        return result

    # Check minimum version for edition 2024
    if min_edition == "2024" and result.rustc_minor < MIN_RUSTC_MINOR_FOR_2024:
        result.error_message = (
            f"Dataset hardening requires rustc >= 1.{MIN_RUSTC_MINOR_FOR_2024} for "
            f"edition 2024 support.\n"
            f"Current version: {result.rustc_version}\n\n"
            "To install the required toolchain:\n"
            "  rustup update stable\n"
            "  # Or for nightly (recommended for full Clippy nursery support):\n"
            "  rustup install nightly\n"
            "  rustup default nightly\n\n"
            "See: docs/runbooks/RUST_2024_TOOLCHAIN_SETUP.md\n"
            "Rust Edition Guide: https://doc.rust-lang.org/edition-guide/rust-2024/"
        )
        return result

    # Check rustfmt availability and style_edition support
    rustfmt_version = _run_version_command(["rustfmt", "--version"])
    if not rustfmt_version:
        result.error_message = (
            "rustfmt not found. Please install rustfmt:\n"
            "  rustup component add rustfmt\n\n"
            "See: docs/runbooks/RUST_2024_TOOLCHAIN_SETUP.md"
        )
        return result

    # rustfmt with style_edition 2024 requires rustfmt 1.8+ (ships with rustc 1.85+)
    effective_style = (style_edition or min_edition or "").strip()
    if effective_style.lower() in ("none", "null", ""):
        effective_style = ""
    result.rustfmt_supports_2024_style = _rustfmt_supports_style_edition(
        "2024", rustfmt_version
    )
    if effective_style == "2024" and not result.rustfmt_supports_2024_style:
        result.error_message = (
            "rustfmt does not appear to support style_edition = \"2024\".\n"
            f"Detected rustfmt: {rustfmt_version}\n\n"
            "Update rustfmt (via rustup) or set hardening_style_edition to 2021.\n"
            "See: docs/runbooks/RUST_2024_TOOLCHAIN_SETUP.md"
        )
        return result

    # Check Clippy availability
    clippy_available = _check_cargo_tool("clippy")
    if not clippy_available:
        result.error_message = (
            "cargo-clippy not found. Please install Clippy:\n"
            "  rustup component add clippy\n\n"
            "See: docs/runbooks/RUST_2024_TOOLCHAIN_SETUP.md"
        )
        return result

    # Add warnings for non-nightly toolchains
    if not result.is_nightly:
        result.warnings.append(
            "Using stable toolchain. Some Clippy nursery lints may not be available. "
            "For best results, consider using nightly: rustup default nightly"
        )

    # All checks passed
    result.supported = True
    return result


def validate_hardening_toolchain_or_exit(
    min_edition: str = "2024", style_edition: str | None = None
) -> None:
    """
    Validate hardening toolchain and exit with clear error if not supported.

    This function should be called at pipeline startup when --dataset-hardening
    is enabled. It will log errors and raise SystemExit if the toolchain is
    insufficient.

    Args:
        min_edition: Minimum required edition (default: "2024")
        style_edition: Rustfmt style_edition to validate (defaults to min_edition)

    Raises:
        SystemExit: If toolchain does not support hardening features
    """
    result = check_hardening_toolchain(min_edition, style_edition)

    if not result.supported:
        logger.error("=" * 70)
        logger.error("DATASET HARDENING TOOLCHAIN VALIDATION FAILED")
        logger.error("=" * 70)
        logger.error("")
        if result.error_message:
            for line in result.error_message.split("\n"):
                logger.error(line)
        logger.error("")
        logger.error("=" * 70)
        raise SystemExit(1)

    # Log success and any warnings
    logger.info(f"Hardening toolchain validated: {result.rustc_version}")
    if result.is_nightly:
        logger.info("Using nightly toolchain (full Clippy nursery support)")
    else:
        logger.info("Using stable toolchain")

    for warning in result.warnings:
        logger.warning(warning)
