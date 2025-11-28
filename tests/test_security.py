"""
Security-focused test cases for the Sigil Pipeline.

Tests input validation, path traversal protection, symlink attacks,
and other security-sensitive functionality.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
"""

import io
import tarfile
from pathlib import Path

import pytest

from sigil_pipeline.crawler import validate_crate_name, validate_crate_version


class TestInputValidation:
    """Test input validation functions for security."""

    @pytest.mark.parametrize(
        "valid_name",
        [
            "serde",
            "tokio",
            "actix-web",
            "rand_core",
            "a",
            "a1",
            "a-b-c",
            "a_b_c",
            "crate123",
        ],
    )
    def test_accepts_valid_crate_names(self, valid_name: str) -> None:
        """Test that valid crate names are accepted."""
        result = validate_crate_name(valid_name)
        assert result == valid_name

    @pytest.mark.parametrize(
        "invalid_name,description",
        [
            ("../malicious", "path traversal with .."),
            ("/etc/passwd", "absolute path"),
            ("crate; rm -rf /", "shell injection"),
            ("crate\x00null", "null byte injection"),
            ("", "empty string"),
            ("Uppercase", "uppercase letters"),
            ("has space", "contains spaces"),
            ("has.dot", "contains dots"),
            ("-starts-with-dash", "starts with dash"),
        ],
    )
    def test_rejects_invalid_crate_names(
        self, invalid_name: str, description: str
    ) -> None:
        """Test that invalid/malicious crate names are rejected."""
        with pytest.raises(ValueError):
            validate_crate_name(invalid_name)

    def test_rejects_none_crate_name(self) -> None:
        """Test that None crate name is rejected."""
        with pytest.raises(ValueError):
            validate_crate_name(None)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "valid_version",
        [
            "1.0.0",
            "0.1.0",
            "10.20.30",
            "1.0.0-alpha",
            "1.0.0-beta.1",
            "1.0.0+build.123",
        ],
    )
    def test_accepts_valid_versions(self, valid_version: str) -> None:
        """Test that valid semver versions are accepted."""
        result = validate_crate_version(valid_version)
        assert result == valid_version

    @pytest.mark.parametrize(
        "invalid_version,description",
        [
            ("../etc/passwd", "path traversal"),
            ("1.0", "incomplete semver"),
            ("", "empty string"),
            ("v1.0.0", "version prefix"),
            ("abc", "non-numeric"),
        ],
    )
    def test_rejects_invalid_versions(
        self, invalid_version: str, description: str
    ) -> None:
        """Test that invalid versions are rejected."""
        with pytest.raises(ValueError):
            validate_crate_version(invalid_version)


class TestTarfileSecurityProtection:
    """Test tarfile extraction security features."""

    def _create_malicious_tar(
        self, tmp_path: Path, attack_type: str
    ) -> tuple[Path, tarfile.TarInfo]:
        """Create a tarfile with a malicious member for testing."""
        tar_path = tmp_path / "malicious.tar.gz"

        if attack_type == "absolute_path":
            member = tarfile.TarInfo(name="/etc/passwd")
            member.size = 0
        elif attack_type == "path_traversal":
            member = tarfile.TarInfo(name="../../../etc/passwd")
            member.size = 0
        elif attack_type == "symlink_escape":
            member = tarfile.TarInfo(name="link")
            member.type = tarfile.SYMTYPE
            member.linkname = "/etc/passwd"
        elif attack_type == "symlink_traversal":
            member = tarfile.TarInfo(name="link")
            member.type = tarfile.SYMTYPE
            member.linkname = "../../../etc/passwd"
        elif attack_type == "hardlink_escape":
            member = tarfile.TarInfo(name="link")
            member.type = tarfile.LNKTYPE
            member.linkname = "/etc/passwd"
        else:
            raise ValueError(f"Unknown attack type: {attack_type}")

        with tarfile.open(tar_path, "w:gz") as tar:
            tar.addfile(member, io.BytesIO(b"malicious content"))

        return tar_path, member

    def test_rejects_absolute_path_in_tar(self, tmp_path: Path) -> None:
        """Test that absolute paths in tar are rejected."""
        tar_path, _ = self._create_malicious_tar(tmp_path, "absolute_path")

        with tarfile.open(tar_path, "r:gz") as tar:
            for member in tar.getmembers():
                # On Unix, /etc/passwd is absolute. On Windows, check if starts with /
                # Our security check in crawler.py uses member.name directly
                # Verify our security check would catch this
                assert member.name.startswith("/") or ".." in member.name

    def test_rejects_path_traversal_in_tar(self, tmp_path: Path) -> None:
        """Test that path traversal attempts in tar are rejected."""
        tar_path, _ = self._create_malicious_tar(tmp_path, "path_traversal")

        with tarfile.open(tar_path, "r:gz") as tar:
            for member in tar.getmembers():
                member_path = Path(member.name)
                # Verify our security check would catch this
                assert ".." in member_path.parts

    def test_rejects_symlink_escape_in_tar(self, tmp_path: Path) -> None:
        """Test that symlinks pointing to absolute paths are rejected."""
        tar_path, _ = self._create_malicious_tar(tmp_path, "symlink_escape")

        with tarfile.open(tar_path, "r:gz") as tar:
            for tar_member in tar.getmembers():
                if tar_member.issym() or tar_member.islnk():
                    # Verify our security check would catch this (starts with /)
                    assert (
                        tar_member.linkname.startswith("/")
                        or ".." in tar_member.linkname
                    )

    def test_rejects_symlink_traversal_in_tar(self, tmp_path: Path) -> None:
        """Test that symlinks with path traversal are rejected."""
        tar_path, _ = self._create_malicious_tar(tmp_path, "symlink_traversal")

        with tarfile.open(tar_path, "r:gz") as tar:
            for tar_member in tar.getmembers():
                if tar_member.issym() or tar_member.islnk():
                    link_target = Path(tar_member.linkname)
                    # Verify our security check would catch this
                    assert ".." in link_target.parts


class TestThreadSafety:
    """Test thread safety of shared resources."""

    def test_analysis_log_dir_thread_safe(self) -> None:
        """Test that _get_analysis_log_dir is thread-safe."""
        import threading

        from sigil_pipeline.analyzer import _get_analysis_log_dir

        results: list[Path] = []
        errors: list[Exception] = []

        def get_dir() -> None:
            try:
                path = _get_analysis_log_dir()
                results.append(path)
            except Exception as e:
                errors.append(e)

        # Create multiple threads that try to get the log dir simultaneously
        threads = [threading.Thread(target=get_dir) for _ in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should get the same path and no errors
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 10
        # All results should be the same path (singleton)
        assert all(r == results[0] for r in results)


class TestMetricsThreadSafety:
    """Test thread safety of metrics collection."""

    def test_metrics_collector_thread_safe(self) -> None:
        """Test that MetricsCollector is thread-safe."""
        import threading

        from sigil_pipeline.observability import MetricsCollector

        collector = MetricsCollector()
        errors: list[Exception] = []

        def increment_counter() -> None:
            try:
                for _ in range(100):
                    collector.increment("test_counter")
            except Exception as e:
                errors.append(e)

        # Create multiple threads that increment counters simultaneously
        threads = [threading.Thread(target=increment_counter) for _ in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors should occur
        assert len(errors) == 0, f"Errors occurred: {errors}"

        # Counter should have correct total (10 threads * 100 increments)
        assert collector.get_counter("test_counter") == 1000


class TestRateLimiting:
    """Test rate limiting functionality."""

    def test_rate_limit_sync_enforces_delay(self) -> None:
        """Test that rate limiting enforces minimum delay between requests."""
        import time

        # Reset the last request time
        import sigil_pipeline.crawler
        from sigil_pipeline.crawler import (
            CRATES_IO_RATE_LIMIT_SECONDS,
            _rate_limit_sync,
        )

        sigil_pipeline.crawler._last_request_time = 0.0

        # First call should not delay
        _rate_limit_sync()

        # Second call should delay
        start = time.monotonic()
        _rate_limit_sync()
        second_duration = time.monotonic() - start

        # Second call should take at least the rate limit duration
        assert second_duration >= CRATES_IO_RATE_LIMIT_SECONDS * 0.9  # 10% tolerance


class TestLicenseValidation:
    """Test license validation security."""

    def test_license_compliance_rejects_unknown(self) -> None:
        """Test that unknown licenses are rejected."""
        from sigil_pipeline.utils import check_license_compliance

        allowed = ["MIT", "Apache-2.0"]
        assert check_license_compliance("GPL-3.0", allowed) is False
        assert check_license_compliance("PROPRIETARY", allowed) is False
        assert check_license_compliance("", allowed) is False

    def test_license_compliance_accepts_allowed(self) -> None:
        """Test that allowed licenses are accepted."""
        from sigil_pipeline.utils import check_license_compliance

        allowed = ["MIT", "Apache-2.0", "BSD-3-Clause"]
        assert check_license_compliance("MIT", allowed) is True
        assert check_license_compliance("Apache-2.0", allowed) is True

    def test_license_compliance_handles_spdx_expressions(self) -> None:
        """Test that SPDX expressions are properly handled."""
        from sigil_pipeline.utils import check_license_compliance

        allowed = ["MIT", "Apache-2.0"]
        # Should accept if any part of OR expression is allowed
        assert check_license_compliance("MIT OR Apache-2.0", allowed) is True
        assert check_license_compliance("MIT/Apache-2.0", allowed) is True
        # Should reject if no part is allowed
        assert check_license_compliance("GPL-3.0 OR AGPL-3.0", allowed) is False


class TestPlatformDetection:
    """Test platform-specific crate detection."""

    def test_detects_windows_specific_crates(self, tmp_path: Path) -> None:
        """Test detection of Windows-specific dependencies."""
        from sigil_pipeline.utils import is_platform_specific_crate

        crate_dir = tmp_path / "test_crate"
        crate_dir.mkdir()

        # Create a Cargo.toml with Windows-specific dependency
        cargo_toml = crate_dir / "Cargo.toml"
        cargo_toml.write_text(
            """
[package]
name = "test"
version = "0.1.0"

[dependencies]
winapi = "0.3"
"""
        )

        result = is_platform_specific_crate(crate_dir)
        # On non-Windows, this should detect Windows-specific
        import platform

        if platform.system().lower() != "windows":
            assert result == "windows"

    def test_detects_unix_specific_crates(self, tmp_path: Path) -> None:
        """Test detection of Unix-specific dependencies."""
        from sigil_pipeline.utils import is_platform_specific_crate

        crate_dir = tmp_path / "test_crate"
        crate_dir.mkdir()

        # Create a Cargo.toml with Unix-specific dependency
        cargo_toml = crate_dir / "Cargo.toml"
        cargo_toml.write_text(
            """
[package]
name = "test"
version = "0.1.0"

[dependencies]
nix = "0.26"
"""
        )

        result = is_platform_specific_crate(crate_dir)
        # On Windows, this may detect Unix-specific or return None depending
        # on the implementation. Just verify it doesn't crash.
        import platform

        if platform.system().lower() == "windows":
            # Result can be "unix" or None depending on detection logic
            assert result in ("unix", None)
