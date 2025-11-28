"""
Utility functions for the Sigil Pipeline.

Provides subprocess wrappers, file I/O, temporary directory management,
and OS-agnostic cargo command construction.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.2.0
"""

import asyncio
import hashlib
import json
import logging
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def run_command(
    cmd: list[str],
    cwd: Path | None = None,
    timeout: int | None = None,
) -> subprocess.CompletedProcess:
    """
    Run a command with proper error handling and cross-platform support.

    Args:
        cmd: Command as list of strings
        cwd: Working directory (optional)
        timeout: Command timeout in seconds (optional)

    Returns:
        CompletedProcess with stdout, stderr, returncode
    """
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result
    except subprocess.TimeoutExpired:
        logger.warning(f"Command timed out: {' '.join(cmd)}")
        raise
    except Exception as e:
        logger.error(f"Failed to run command {' '.join(cmd)}: {e}")
        raise


async def run_command_async(
    cmd: list[str],
    cwd: Path | None = None,
    timeout: int | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """
    Run a command asynchronously to avoid blocking the event loop.

    Args:
        cmd: Command as list of strings
        cwd: Working directory (optional)
        timeout: Command timeout in seconds (optional)
        env: Environment variables dict (optional)

    Returns:
        CompletedProcess with stdout, stderr, returncode
    """
    try:
        # Merge with system environment if env provided
        process_env = None
        if env:
            import os

            process_env = os.environ.copy()
            process_env.update(env)

        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=process_env,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise subprocess.TimeoutExpired(cmd, timeout if timeout is not None else 0)

        return subprocess.CompletedProcess(
            args=cmd,
            returncode=process.returncode if process.returncode is not None else -1,
            stdout=stdout.decode("utf-8") if stdout else "",
            stderr=stderr.decode("utf-8") if stderr else "",
        )
    except subprocess.TimeoutExpired:
        logger.warning(f"Command timed out: {' '.join(cmd)}")
        raise
    except Exception as e:
        logger.error(f"Failed to run command {' '.join(cmd)}: {e}")
        raise


def read_json(path: str | Path) -> dict[str, Any]:
    """
    Read a JSON file.

    Args:
        path: Path to JSON file

    Returns:
        Parsed JSON data as dictionary
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str | Path, data: dict[str, Any]) -> None:
    """
    Write data to a JSON file.

    Args:
        path: Path to output JSON file
        data: Data to write (must be JSON-serializable)
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class TempDir:
    """
    Context manager for temporary directories.

    Automatically cleans up the directory when exiting the context.
    """

    def __init__(
        self,
        prefix: str = "sigil_",
        cleanup: bool = True,
        resume_path: Path | None = None,
    ):
        """
        Initialize temporary directory.

        Args:
            prefix: Prefix for temporary directory name
            cleanup: Whether to clean up on exit (default: True)
            resume_path: Optional path to existing temp directory to resume from
        """
        self.prefix = prefix
        self.cleanup = cleanup
        self.resume_path = resume_path
        self.path: Path | None = None

    def __enter__(self) -> Path:
        """Create and return temporary directory path."""
        if self.resume_path and self.resume_path.exists():
            logger.info(f"Resuming with existing temp directory: {self.resume_path}")
            self.path = self.resume_path
            return self.path
        self.path = Path(tempfile.mkdtemp(prefix=self.prefix))
        return self.path

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up temporary directory."""
        if self.cleanup and self.path and self.path.exists() and not self.resume_path:
            try:
                shutil.rmtree(self.path)
            except Exception as e:
                logger.warning(f"Failed to clean up temp directory {self.path}: {e}")


class CheckpointManager:
    """
    Manages checkpoint/resume functionality for the pipeline.

    Tracks processed crates and allows resuming from a previous run.
    """

    def __init__(self, checkpoint_path: Path | str):
        """
        Initialize checkpoint manager.

        Args:
            checkpoint_path: Path to checkpoint JSON file
        """
        self.checkpoint_path = Path(checkpoint_path)
        self.processed_crates: dict[str, dict[str, Any]] = {}
        self.temp_dir_path: Path | None = None
        self.config_hash: str | None = None
        self.timestamp: str | None = None

    def load(self) -> bool:
        """
        Load checkpoint from file.

        Returns:
            True if checkpoint was loaded successfully, False otherwise
        """
        if not self.checkpoint_path.exists():
            return False

        try:
            with open(self.checkpoint_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.processed_crates = data.get("processed_crates", {})
            temp_dir_str = data.get("temp_dir_path")
            if temp_dir_str:
                self.temp_dir_path = Path(temp_dir_str)
            self.config_hash = data.get("config_hash")
            self.timestamp = data.get("timestamp")

            logger.info(
                f"Loaded checkpoint: {len(self.processed_crates)} crates processed, "
                f"temp_dir={self.temp_dir_path}"
            )
            return True
        except Exception as e:
            logger.warning(f"Failed to load checkpoint: {e}")
            return False

    def save(
        self,
        processed_crates: dict[str, dict[str, Any]],
        temp_dir_path: Path | None = None,
        config_hash: str | None = None,
    ) -> None:
        """
        Save checkpoint to file.

        Args:
            processed_crates: Dictionary mapping crate names to their status
            temp_dir_path: Path to temp directory (for resuming)
            config_hash: Hash of config to verify compatibility
        """
        self.processed_crates = processed_crates
        self.temp_dir_path = temp_dir_path
        self.config_hash = config_hash

        import datetime

        self.timestamp = datetime.datetime.now().isoformat()

        data = {
            "processed_crates": processed_crates,
            "temp_dir_path": str(temp_dir_path) if temp_dir_path else None,
            "config_hash": config_hash,
            "timestamp": self.timestamp,
        }

        try:
            # Create parent directory if needed
            self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.checkpoint_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Checkpoint saved: {len(processed_crates)} crates")
        except Exception as e:
            logger.warning(f"Failed to save checkpoint: {e}")

    def is_processed(self, crate_name: str) -> bool:
        """Check if a crate has been processed."""
        return crate_name in self.processed_crates

    def get_processed_status(self, crate_name: str) -> dict[str, Any] | None:
        """Get processing status for a crate."""
        return self.processed_crates.get(crate_name)

    def mark_processed(
        self,
        crate_name: str,
        status: str,
        reason: str | None = None,
        files: list[dict] | None = None,
    ) -> None:
        """
        Mark a crate as processed.

        Args:
            crate_name: Name of the crate
            status: "accepted" or "rejected"
            reason: Rejection reason (if rejected)
            files: List of file dicts (if accepted)
        """
        self.processed_crates[crate_name] = {
            "status": status,
            "reason": reason,
            "file_count": len(files) if files else 0,
        }

    def filter_unprocessed(self, crate_list: list[str]) -> list[str]:
        """
        Filter out crates that have already been processed.

        Args:
            crate_list: List of crate names to filter

        Returns:
            List of unprocessed crate names
        """
        unprocessed = [crate for crate in crate_list if not self.is_processed(crate)]
        skipped = len(crate_list) - len(unprocessed)
        if skipped > 0:
            logger.info(f"Resuming: skipping {skipped} already-processed crates")
        return unprocessed

    def get_temp_dir_path(self) -> Path | None:
        """Get the temp directory path from checkpoint (for resuming)."""
        if self.temp_dir_path and self.temp_dir_path.exists():
            return self.temp_dir_path
        return None


def compute_config_hash(config: Any) -> str:
    """
    Compute a hash of the config for checkpoint compatibility checking.

    Args:
        config: PipelineConfig instance

    Returns:
        SHA256 hash as hex string
    """
    # Convert config to dict and sort keys for consistent hashing
    config_dict = config.to_dict() if hasattr(config, "to_dict") else {}

    # Remove checkpoint-related fields from hash (they shouldn't affect compatibility)
    config_dict.pop("checkpoint_path", None)
    config_dict.pop("enable_checkpointing", None)
    config_dict.pop("checkpoint_interval", None)

    # Create deterministic JSON string
    config_json = json.dumps(config_dict, sort_keys=True, default=str)

    # Compute hash
    return hashlib.sha256(config_json.encode()).hexdigest()


def get_crate_edition(crate_dir: Path) -> str | None:
    """
    Read the Rust edition from Cargo.toml.

    Args:
        crate_dir: Path to extracted crate directory

    Returns:
        Edition string (e.g., "2021", "2018") or None if not found
    """
    import re

    cargo_toml = crate_dir / "Cargo.toml"
    if not cargo_toml.exists():
        return None

    try:
        content = cargo_toml.read_text(encoding="utf-8")
        # Look for edition = "2021" or edition = "2018"
        match = re.search(r'edition\s*=\s*["\'](\d+)["\']', content)
        if match:
            return match.group(1)
    except Exception as e:
        logger.warning(f"Failed to read Cargo.toml in {crate_dir}: {e}")

    return None


def setup_logging(level: str = "INFO") -> None:
    """
    Set up basic logging configuration.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    import logging as log_module

    log_level = getattr(log_module, level.upper(), log_module.INFO)
    log_module.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def cleanup_temp_artifacts(prefixes: list[str] | None = None) -> int:
    """
    Remove leftover temporary directories created by the pipeline.

    Args:
        prefixes: Optional list of prefixes to match. Defaults to Sigil templates.

    Returns:
        Number of directories successfully removed.
    """
    temp_root = Path(tempfile.gettempdir())
    default_prefixes = ["sigil_", "sigil_crate_", "sigil_crates_"]
    prefixes = prefixes or default_prefixes

    removed = 0
    for entry in temp_root.iterdir():
        if not entry.is_dir():
            continue
        if not any(entry.name.startswith(prefix) for prefix in prefixes):
            continue
        try:
            shutil.rmtree(entry)
            removed += 1
        except Exception as exc:
            logger.warning(f"Failed to remove temp directory {entry}: {exc}")
    return removed


# ============================================================================
# OS-agnostic cargo command utilities
# ============================================================================


def get_cargo_command() -> str:
    """
    Get the appropriate cargo command for the current platform.

    On Windows, returns 'cargo.exe' if it exists, otherwise 'cargo'.
    On Unix-like systems (Linux, macOS), returns 'cargo'.

    This function checks if cargo is available in PATH and returns the
    appropriate executable name based on the platform.

    Returns:
        str: The cargo command to use ('cargo' or 'cargo.exe')

    Examples:
        >>> cmd = get_cargo_command()
        >>> # On Windows: 'cargo.exe' (if available) or 'cargo'
        >>> # On Linux/macOS: 'cargo'
    """
    system = platform.system().lower()

    if system == "windows":
        # On Windows, try cargo.exe first, then fall back to cargo
        # (cargo.exe is more reliable on Windows)
        if shutil.which("cargo.exe"):
            return "cargo.exe"
        elif shutil.which("cargo"):
            return "cargo"
        else:
            # If neither found, default to cargo.exe (Windows convention)
            return "cargo.exe"
    else:
        # On Unix-like systems (Linux, macOS, etc.), use 'cargo'
        return "cargo"


def build_cargo_command(subcommand: str, *args: str) -> list[str]:
    """
    Build a cargo command list with OS-agnostic cargo executable.

    Args:
        subcommand: The cargo subcommand (e.g., 'build', 'test', 'clippy')
        *args: Additional arguments to pass to the cargo command

    Returns:
        list[str]: Command list ready for subprocess execution

    Examples:
        >>> cmd = build_cargo_command('build', '--release')
        >>> # Returns: ['cargo.exe', 'build', '--release'] on Windows
        >>> # Returns: ['cargo', 'build', '--release'] on Linux/macOS

        >>> cmd = build_cargo_command('clippy', '--message-format=json', '--', '-W', 'clippy::all')
        >>> # Returns: ['cargo.exe', 'clippy', '--message-format=json', '--', '-W', 'clippy::all'] on Windows
    """
    cargo_cmd = get_cargo_command()
    return [cargo_cmd, subcommand] + list(args)


def build_cargo_subcommand_command(subcommand: str, *args: str) -> list[str]:
    """
    Build a cargo subcommand command (e.g., cargo-audit, cargo-geiger).

    Cargo subcommands are installed as separate executables (cargo-audit, cargo-geiger, etc.)
    and are invoked via 'cargo <subcommand>' syntax.

    Args:
        subcommand: The cargo subcommand name (e.g., 'audit', 'geiger', 'outdated')
        *args: Additional arguments to pass to the subcommand

    Returns:
        list[str]: Command list ready for subprocess execution

    Examples:
        >>> cmd = build_cargo_subcommand_command('audit', '--json')
        >>> # Returns: ['cargo.exe', 'audit', '--json'] on Windows
        >>> # Returns: ['cargo', 'audit', '--json'] on Linux/macOS
    """
    cargo_cmd = get_cargo_command()
    return [cargo_cmd, subcommand] + list(args)


def check_cargo_available() -> bool:
    """
    Check if cargo is available in the system PATH.

    Returns:
        bool: True if cargo is available, False otherwise
    """
    cargo_cmd = get_cargo_command()
    return shutil.which(cargo_cmd) is not None


def check_license_compliance(license_str: str, allowed_list: list[str]) -> bool:
    """
    Check if a license string (possibly SPDX expression) matches any allowed license.

    Handles SPDX expressions like "MIT OR Apache-2.0" by splitting on OR/AND
    and checking if any component matches the allowlist.

    Args:
        license_str: License string from Cargo.toml or crates.io (may be SPDX expression)
        allowed_list: List of allowed license names (e.g., ["MIT", "Apache-2.0"])

    Returns:
        True if license is allowed, False otherwise
    """
    if not license_str or not allowed_list:
        return False

    # Normalize input: lowercase, strip whitespace
    license_normalized = license_str.strip().lower()

    # Normalize allowed list
    allowed_normalized = {
        lic.lower().strip().replace("-", "").replace("_", "") for lic in allowed_list
    }

    # Handle SPDX expressions: split on " OR " or " AND " or "/"
    # Common patterns: "MIT OR Apache-2.0", "MIT/Apache-2.0", "MIT AND Apache-2.0"
    separators = [" or ", " and ", "/"]
    components = [license_normalized]

    for sep in separators:
        new_components = []
        for comp in components:
            new_components.extend(part.strip() for part in comp.split(sep))
        components = new_components

    # Check if any component matches an allowed license
    for component in components:
        component_clean = component.replace("-", "").replace("_", "")
        if component_clean in allowed_normalized:
            return True

    # Also check exact match (normalized)
    license_clean = license_normalized.replace("-", "").replace("_", "")
    return license_clean in allowed_normalized


def is_platform_specific_crate(crate_dir: Path) -> str | None:
    """
    Detect if a crate is platform-specific by checking Cargo.toml dependencies.

    Checks for known platform-specific dependencies that indicate the crate
    may not compile on the current platform.

    Args:
        crate_dir: Path to crate directory

    Returns:
        Platform name if platform-specific detected (e.g., "windows", "unix"),
        None if not clearly platform-specific or if detection failed
    """
    cargo_toml = crate_dir / "Cargo.toml"
    if not cargo_toml.exists():
        return None

    try:
        content = cargo_toml.read_text(encoding="utf-8")
        current_platform = platform.system().lower()

        # Known Windows-specific dependencies
        windows_deps = [
            "winapi",
            "windows",
            "windows-sys",
            "winreg",
            "winres",
            "winrt",
        ]

        # Known Unix/Linux-specific dependencies
        unix_deps = [
            "libc",
            "nix",
            "sysinfo",
            "alsa",
            "pulseaudio",
            "wayland",
            "x11",
        ]

        # Known macOS-specific dependencies
        macos_deps = [
            "core-foundation",
            "core-graphics",
            "cocoa",
            "objc",
        ]

        # Check for platform-specific dependencies
        content_lower = content.lower()

        def has_dependency(dep: str, text: str) -> bool:
            """Check if dependency exists in TOML as key or quoted value."""
            # Check as TOML key (e.g., 'winapi =' or 'winapi=')
            if f"{dep} =" in text or f"{dep}=" in text:
                return True
            # Check as quoted value (e.g., in dependencies list)
            if f'"{dep}"' in text or f"'{dep}'" in text:
                return True
            return False

        if current_platform == "windows":
            # On Windows, check for Unix/macOS-specific deps
            for dep in unix_deps + macos_deps:
                if has_dependency(dep, content_lower):
                    return "unix"  # Likely Unix/macOS-only
        elif current_platform == "linux":
            # On Linux, check for Windows/macOS-specific deps
            for dep in windows_deps:
                if has_dependency(dep, content_lower):
                    return "windows"  # Likely Windows-only
            for dep in macos_deps:
                if has_dependency(dep, content_lower):
                    return "macos"  # Likely macOS-only
        elif current_platform == "darwin":  # macOS
            # On macOS, check for Windows-specific deps
            for dep in windows_deps:
                if has_dependency(dep, content_lower):
                    return "windows"  # Likely Windows-only

        # Check for platform-specific features
        if "[target." in content:
            # Has platform-specific targets, but we can't determine compatibility
            # without more analysis - let compilation handle it
            return None

        return None

    except Exception as e:
        logger.debug(f"Failed to check platform-specific dependencies: {e}")
        return None
