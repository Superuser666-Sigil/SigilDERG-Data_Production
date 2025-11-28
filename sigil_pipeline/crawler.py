"""
Crawler module for fetching Rust crate source code.

Handles downloading crates from crates.io and iterating through
the Stack Rust dataset (local or HuggingFace).

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.0.0
"""

import asyncio
import hashlib
import logging
import re
import shutil
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Iterator

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import PipelineConfig

logger = logging.getLogger(__name__)

# Rate limiting for crates.io API (respects their 1 request/second guideline)
_last_request_time: float = 0.0
_rate_limit_lock = asyncio.Lock() if hasattr(asyncio, "Lock") else None
CRATES_IO_RATE_LIMIT_SECONDS = 1.0  # 1 request per second


def _rate_limit_sync() -> None:
    """
    Enforce rate limiting for synchronous crates.io API requests.

    Ensures at least CRATES_IO_RATE_LIMIT_SECONDS between requests.
    """
    global _last_request_time
    now = time.monotonic()
    elapsed = now - _last_request_time
    if elapsed < CRATES_IO_RATE_LIMIT_SECONDS:
        time.sleep(CRATES_IO_RATE_LIMIT_SECONDS - elapsed)
    _last_request_time = time.monotonic()


# Optional HuggingFace datasets library
try:
    from datasets import load_dataset  # type: ignore[import-untyped]

    HF_DATASETS_AVAILABLE = True
except ImportError:
    HF_DATASETS_AVAILABLE = False
    load_dataset = None  # type: ignore[assignment]

# Constants
CRATES_IO_API_URL = "https://crates.io/api/v1/crates"
CRATES_IO_STATIC_URL = "https://static.crates.io/crates"

# Retry configuration for network requests
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # Exponential backoff: 1s, 2s, 4s


def validate_crate_name(crate_name: str) -> str:
    """
    Validate crate name to prevent path traversal attacks.

    Args:
        crate_name: Crate name to validate

    Returns:
        Validated crate name

    Raises:
        ValueError: If crate name is invalid
    """
    if not crate_name or not isinstance(crate_name, str):
        raise ValueError("Crate name must be a non-empty string")

    # Crate names must match: [a-z0-9_][a-z0-9_-]*
    if not re.match(r"^[a-z0-9_][a-z0-9_-]*$", crate_name):
        raise ValueError(f"Invalid crate name format: {crate_name}")

    return crate_name


def validate_crate_version(version: str) -> str:
    """
    Validate crate version to prevent path traversal attacks.

    Args:
        version: Version string to validate

    Returns:
        Validated version string

    Raises:
        ValueError: If version is invalid
    """
    if not version or not isinstance(version, str):
        raise ValueError("Version must be a non-empty string")

    # Basic version validation (semver-like)
    if not re.match(r"^[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError(f"Invalid version format: {version}")

    return version


# get_crate_edition moved to utils.py to avoid circular imports


def fetch_crate(
    crate_name: str,
    version: str | None = None,
    config: PipelineConfig | None = None,
    temp_dir: Path | None = None,
) -> Path | None:
    """
    Download a crate from crates.io and extract it.

    Args:
        crate_name: Name of the crate to fetch
        version: Version to fetch (if None, uses latest from API)
        config: Pipeline configuration (optional)
        temp_dir: Temporary directory for extraction (if None, creates one)

    Returns:
        Path to extracted crate directory, or None if failed

    Raises:
        ValueError: If crate name or version is invalid
    """
    # Validate crate name
    try:
        crate_name = validate_crate_name(crate_name)
    except ValueError as e:
        logger.error(f"Invalid crate name '{crate_name}': {e}")
        raise

    # Get version from API if not provided (with retry logic)
    if not version:
        try:
            api_url = f"{CRATES_IO_API_URL}/{crate_name}"

            @retry(
                stop=stop_after_attempt(MAX_RETRIES),
                wait=wait_exponential(multiplier=RETRY_BACKOFF_BASE, min=1, max=10),
                retry=retry_if_exception_type(
                    (requests.RequestException, requests.Timeout)
                ),
                reraise=True,
            )
            def fetch_api_data():
                # Enforce rate limiting for crates.io API
                _rate_limit_sync()
                response = requests.get(api_url, timeout=30)
                response.raise_for_status()
                return response.json()

            data = fetch_api_data()
            version = data.get("crate", {}).get("max_version")
            if not version:
                logger.error(f"Could not determine version for {crate_name}")
                return None

            # Pre-check license before downloading (Priority 1.2)
            if config and config.enable_license_scan:
                from .utils import check_license_compliance

                # License can be in crate object or in the latest version
                crate_info = data.get("crate", {})
                license_str = crate_info.get("license")

                # If not in crate, check latest version
                if not license_str:
                    versions = data.get("versions", [])
                    if versions:
                        # Get the latest version (first in list, sorted by newest)
                        latest_version = versions[0] if versions else {}
                        license_str = latest_version.get("license")

                if license_str:
                    if not check_license_compliance(
                        license_str, config.allowed_licenses
                    ):
                        logger.info(
                            f"Skipping {crate_name}: license '{license_str}' not in allowed list"
                        )
                        return None
                else:
                    # No license declared - skip to be safe
                    logger.info(
                        f"Skipping {crate_name}: no license declared in crates.io metadata"
                    )
                    return None
        except Exception as e:
            logger.error(f"Failed to fetch version for {crate_name}: {e}")
            return None

    # Validate version
    try:
        version = validate_crate_version(version)
    except ValueError as e:
        logger.error(f"Invalid version '{version}': {e}")
        raise

    # Check cache first (if cache directory is configured)
    cache_dir = None
    cached_extract = None
    if config and hasattr(config, "enable_caching") and config.enable_caching:
        if hasattr(config, "cache_dir") and config.cache_dir:
            cache_dir = Path(config.cache_dir)
            cache_dir.mkdir(parents=True, exist_ok=True)
            # Create cache key from crate name and version
            cache_key = hashlib.sha256(f"{crate_name}-{version}".encode()).hexdigest()
            cached_extract = cache_dir / f"{cache_key}-extracted"

            # If cached and extracted directory exists, use it
            if cached_extract.exists() and cached_extract.is_dir():
                logger.info(f"Using cached crate {crate_name} v{version}")
                # Create temp directory if needed
                if temp_dir is None:
                    temp_dir = Path(tempfile.mkdtemp(prefix="sigil_crate_"))
                else:
                    temp_dir = Path(temp_dir)
                    temp_dir.mkdir(parents=True, exist_ok=True)
                # Copy to temp directory
                extract_path = temp_dir / f"{crate_name}-{version}"
                shutil.copytree(cached_extract, extract_path, dirs_exist_ok=True)
                return extract_path

    # Create temp directory if needed
    if temp_dir is None:
        temp_dir = Path(tempfile.mkdtemp(prefix="sigil_crate_"))
    else:
        temp_dir = Path(temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)

    # Download the crate (with retry logic)
    crate_url = f"{CRATES_IO_STATIC_URL}/{crate_name}/{crate_name}-{version}.crate"
    logger.info(f"Downloading {crate_name} v{version} from crates.io")

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=RETRY_BACKOFF_BASE, min=1, max=10),
        retry=retry_if_exception_type((requests.RequestException, requests.Timeout)),
        reraise=True,
    )
    def download_crate():
        # Enforce rate limiting for crates.io downloads
        _rate_limit_sync()
        response = requests.get(crate_url, timeout=60)
        response.raise_for_status()
        return response

    try:
        response = download_crate()
    except Exception as e:
        logger.error(
            f"Failed to download {crate_name} v{version} after {MAX_RETRIES} attempts: {e}"
        )
        return None

    # Save the crate file
    crate_file = temp_dir / f"{crate_name}-{version}.crate"
    try:
        with open(crate_file, "wb") as f:
            f.write(response.content)
    except Exception as e:
        logger.error(f"Failed to save crate file: {e}")
        return None

    # Extract the crate
    extract_path = temp_dir / f"{crate_name}-{version}"
    try:
        with tarfile.open(crate_file, "r:gz") as tar:
            # Security: Extract to a subdirectory to prevent path traversal
            base_dir = temp_dir.resolve()

            # Detect common prefix (crates.io tarballs have a top-level directory)
            members = tar.getmembers()
            if members:
                # Get the first member's path to detect the top-level directory
                first_member_path = Path(members[0].name)
                if first_member_path.parts and len(first_member_path.parts) > 0:
                    # Check if first part matches crate name pattern
                    top_level_dir = first_member_path.parts[0]
                    if top_level_dir.startswith(f"{crate_name}-"):
                        # Strip the top-level directory from all paths
                        prefix_to_strip = f"{top_level_dir}/"
                    else:
                        prefix_to_strip = None
                else:
                    prefix_to_strip = None
            else:
                prefix_to_strip = None

            for member in members:
                # Check for path traversal attempts
                member_path = Path(member.name)
                if member_path.is_absolute() or ".." in member_path.parts:
                    logger.warning(f"Skipping suspicious path in crate: {member.name}")
                    continue

                # Security: Check for symlink attacks (symlinks pointing outside extraction dir)
                if member.issym() or member.islnk():
                    link_target = Path(member.linkname)
                    if link_target.is_absolute() or ".." in link_target.parts:
                        logger.warning(
                            f"Skipping suspicious symlink in crate: "
                            f"{member.name} -> {member.linkname}"
                        )
                        continue

                # Strip the top-level directory if present
                member_name = member.name
                if prefix_to_strip and member_name.startswith(prefix_to_strip):
                    member_name = member_name[len(prefix_to_strip) :]

                # Extract to safe location
                target_path = base_dir / extract_path.name / member_name
                if member.isdir():
                    target_path.mkdir(parents=True, exist_ok=True)
                else:
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    source = tar.extractfile(member)
                    if source is not None:
                        with source:
                            with open(target_path, "wb") as target:
                                target.write(source.read())

        # Cache the crate if cache directory is configured
        if cache_dir and cached_extract:
            try:
                # Save extracted directory to cache
                if not cached_extract.exists():
                    shutil.copytree(extract_path, cached_extract)
                    logger.debug(f"Cached {crate_name} v{version}")
            except Exception as e:
                logger.warning(f"Failed to cache {crate_name} v{version}: {e}")

        # Clean up crate file
        crate_file.unlink()

        # Verify edition
        if config and not config.allow_edition_2018:
            from .utils import get_crate_edition

            edition = get_crate_edition(extract_path)
            if edition and int(edition) < 2021:
                logger.info(
                    f"Skipping {crate_name} v{version}: edition {edition} < 2021"
                )
                return None

        logger.info(f"Successfully extracted {crate_name} v{version} to {extract_path}")
        return extract_path

    except Exception as e:
        logger.error(f"Failed to extract crate {crate_name} v{version}: {e}")
        return None


def iter_stack_files_hf(dataset_name: str, split: str | None = None) -> Iterator[dict]:
    """
    Iterate through code files from HuggingFace Stack Rust dataset.

    Streams files from HuggingFace without downloading entire dataset.

    Args:
        dataset_name: HuggingFace dataset name (e.g., "ammarnasr/the-stack-rust-clean")
        split: Dataset split to use (default: None, uses default split)

    Yields:
        Dictionary with 'path' and 'code' keys for each Rust file
    """
    if not HF_DATASETS_AVAILABLE or load_dataset is None:
        logger.warning(
            "HuggingFace datasets library not available. "
            "Install with: pip install datasets"
        )
        return

    try:
        logger.info(f"Loading HuggingFace dataset: {dataset_name}")
        dataset = load_dataset(dataset_name, split=split, streaming=True)

        for item in dataset:
            # Stack dataset items are dictionaries
            if not isinstance(item, dict):
                continue

            # Stack dataset typically has 'content' or 'text' field with code
            code = item.get("content") or item.get("text") or item.get("code", "")

            if not code:
                continue

            # Get file path/name if available
            file_path = (
                item.get("path")
                or item.get("file_name")
                or item.get("id", "unknown.rs")
            )

            # Ensure it's a .rs file
            if not file_path.endswith(".rs"):
                continue

            yield {
                "path": file_path,
                "code": code,
                "source": "huggingface",
                "dataset": dataset_name,
            }

    except Exception as e:
        logger.error(f"Failed to load HuggingFace dataset {dataset_name}: {e}")
        return


def iter_stack_files(
    dataset_path: str,
    use_streaming: bool = False,
    hf_dataset_name: str | None = None,
) -> Iterator[dict]:
    """
    Iterate through code files from the Stack Rust dataset.

    Checks local directory first, then optionally falls back to HuggingFace streaming.

    Args:
        dataset_path: Path to local Stack dataset directory
        use_streaming: Whether to stream from HuggingFace if local path not found
        hf_dataset_name: HuggingFace dataset name to use if streaming (e.g., "ammarnasr/the-stack-rust-clean")

    Yields:
        Dictionary with 'path' and 'code' keys for each Rust file
    """
    # First, try local directory
    dataset_dir = Path(dataset_path)

    if dataset_dir.exists() and dataset_dir.is_dir():
        logger.info(f"Using local Stack dataset: {dataset_path}")
        # Recursively find all .rs files
        for file_path in dataset_dir.rglob("*.rs"):
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                yield {
                    "path": str(file_path.relative_to(dataset_dir)),
                    "code": content,
                    "full_path": str(file_path),
                    "source": "local",
                }
            except Exception as e:
                logger.warning(f"Failed to read {file_path}: {e}")
                continue
        return  # Return after processing all local files

    # Local path doesn't exist - check if streaming is enabled
    if use_streaming and hf_dataset_name:
        logger.info(
            f"Local dataset not found at {dataset_path}. "
            f"Streaming from HuggingFace: {hf_dataset_name}"
        )
        yield from iter_stack_files_hf(hf_dataset_name)
        return

    # No local path and streaming not enabled
    logger.warning(
        f"Stack dataset path does not exist: {dataset_path}. "
        f"Set use_streaming=True to stream from HuggingFace."
    )
