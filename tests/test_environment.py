"""
Tests for environment.py.

Covers:
- Environment fingerprint capture
- Toolchain version extraction
- Platform detection
- Dependency version detection

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
"""

import json
from pathlib import Path

from sigil_pipeline.environment import (
    CargoToolAvailability,
    DependencyVersions,
    EnvironmentFingerprint,
    PlatformInfo,
    ToolchainInfo,
    capture_dependency_versions,
    capture_environment,
    capture_platform_info,
    log_environment_summary,
    write_environment_file,
)


class TestToolchainInfo:
    """Tests for ToolchainInfo dataclass."""

    def test_default_values(self):
        """Default values are None."""
        info = ToolchainInfo()
        assert info.rustc_version is None
        assert info.cargo_version is None
        assert info.clippy_version is None
        assert info.rustfmt_version is None


class TestCapturePlatformInfo:
    """Tests for capture_platform_info function."""

    def test_returns_platform_info(self):
        """Returns a PlatformInfo with populated fields."""
        info = capture_platform_info()
        assert isinstance(info, PlatformInfo)
        assert info.os  # Should be non-empty
        assert info.python_version  # Should be non-empty
        assert info.architecture  # Should be non-empty

    def test_python_version_format(self):
        """Python version should be in expected format."""
        info = capture_platform_info()
        # Should be something like "3.12.0"
        parts = info.python_version.split(".")
        assert len(parts) >= 2
        assert parts[0].isdigit()
        assert parts[1].isdigit()


class TestCaptureDependencyVersions:
    """Tests for capture_dependency_versions function."""

    def test_returns_dependency_versions(self):
        """Returns a DependencyVersions instance."""
        versions = capture_dependency_versions()
        assert isinstance(versions, DependencyVersions)

    def test_tree_sitter_version_detected(self):
        """tree-sitter version should be detected (required dependency)."""
        versions = capture_dependency_versions()
        # tree-sitter is a required dependency, so should be present
        assert versions.tree_sitter is not None

    def test_tree_sitter_rust_version_detected(self):
        """tree-sitter-rust version should be detected (required dependency)."""
        versions = capture_dependency_versions()
        assert versions.tree_sitter_rust is not None


class TestCaptureEnvironment:
    """Tests for capture_environment function."""

    def test_returns_fingerprint(self):
        """Returns an EnvironmentFingerprint instance."""
        fingerprint = capture_environment()
        assert isinstance(fingerprint, EnvironmentFingerprint)

    def test_timestamp_is_iso_format(self):
        """Timestamp should be in ISO format."""
        fingerprint = capture_environment()
        assert fingerprint.timestamp
        # Should contain T separator for ISO format
        assert "T" in fingerprint.timestamp

    def test_contains_all_components(self):
        """Fingerprint contains all component dataclasses."""
        fingerprint = capture_environment()
        assert isinstance(fingerprint.toolchain, ToolchainInfo)
        assert isinstance(fingerprint.cargo_tools, CargoToolAvailability)
        assert isinstance(fingerprint.platform, PlatformInfo)
        assert isinstance(fingerprint.dependencies, DependencyVersions)


class TestEnvironmentFingerprintToDict:
    """Tests for EnvironmentFingerprint.to_dict method."""

    def test_to_dict_structure(self):
        """to_dict returns expected structure."""
        fingerprint = capture_environment()
        data = fingerprint.to_dict()

        assert "timestamp" in data
        assert "toolchain" in data
        assert "cargo_tools" in data
        assert "platform" in data
        assert "dependencies" in data

    def test_to_dict_is_json_serializable(self):
        """to_dict output can be serialized to JSON."""
        fingerprint = capture_environment()
        data = fingerprint.to_dict()

        # Should not raise
        json_str = json.dumps(data)
        assert json_str

    def test_toolchain_fields_in_dict(self):
        """Toolchain dict contains expected fields."""
        fingerprint = capture_environment()
        data = fingerprint.to_dict()

        toolchain = data["toolchain"]
        assert "rustc_version" in toolchain
        assert "cargo_version" in toolchain
        assert "clippy_version" in toolchain
        assert "rustfmt_version" in toolchain

    def test_cargo_tools_fields_in_dict(self):
        """Cargo tools dict contains expected fields."""
        fingerprint = capture_environment()
        data = fingerprint.to_dict()

        tools = data["cargo_tools"]
        assert "clippy" in tools
        assert "geiger" in tools
        assert "outdated" in tools
        assert "deny" in tools
        assert "audit" in tools
        assert "license" in tools

    def test_platform_fields_in_dict(self):
        """Platform dict contains expected fields."""
        fingerprint = capture_environment()
        data = fingerprint.to_dict()

        platform = data["platform"]
        assert "os" in platform
        assert "os_release" in platform
        assert "architecture" in platform
        assert "python_version" in platform
        assert "hostname" in platform


class TestWriteEnvironmentFile:
    """Tests for write_environment_file function."""

    def test_writes_json_file(self, tmp_path: Path):
        """Writes fingerprint to JSON file."""
        fingerprint = capture_environment()
        file_path = tmp_path / "env.json"

        write_environment_file(fingerprint, file_path)

        assert file_path.exists()
        content = json.loads(file_path.read_text())
        assert "timestamp" in content
        assert "toolchain" in content

    def test_creates_parent_directories(self, tmp_path: Path):
        """Creates parent directories if needed."""
        fingerprint = capture_environment()
        file_path = tmp_path / "nested" / "dir" / "env.json"

        write_environment_file(fingerprint, file_path)

        assert file_path.exists()


class TestLogEnvironmentSummary:
    """Tests for log_environment_summary function."""

    def test_logs_without_error(self, caplog):
        """log_environment_summary runs without errors."""
        import logging

        fingerprint = capture_environment()

        # Set log level to capture INFO logs
        with caplog.at_level(logging.INFO, logger="sigil_pipeline.environment"):
            # Should not raise
            log_environment_summary(fingerprint)

        # Should have logged something
        assert len(caplog.records) > 0


class TestCargoToolAvailability:
    """Tests for CargoToolAvailability dataclass."""

    def test_default_values_are_false(self):
        """Default values are all False."""
        tools = CargoToolAvailability()
        assert tools.clippy is False
        assert tools.geiger is False
        assert tools.outdated is False
        assert tools.deny is False
        assert tools.audit is False
        assert tools.license is False
