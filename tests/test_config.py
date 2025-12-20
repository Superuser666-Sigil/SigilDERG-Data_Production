"""
Tests for sigil_pipeline.config module.

Tests PipelineConfig class initialization, loading from files, and validation.
"""

import json

import pytest

from sigil_pipeline.config import PipelineConfig


class TestPipelineConfig:
    """Test PipelineConfig class."""

    def test_default_configuration_values(self):
        """Test that default configuration values are correct."""
        config = PipelineConfig()
        assert config.crates == []
        assert config.max_threads == 4
        assert config.output_path == "output/sigil_phase2_dataset.jsonl"

        assert config.max_clippy_warnings is None
        assert config.max_bad_code_warnings == 0
        assert config.require_docs is True
        assert config.enable_license_scan is True

    def test_configuration_from_dictionary(self):
        """Test creating config from dictionary."""
        data = {
            "crates": ["test_crate"],
            "max_threads": 2,
            "output_path": "custom/output.jsonl",
        }
        config = PipelineConfig.from_dict(data)
        assert config.crates == ["test_crate"]
        assert config.max_threads == 2
        assert config.output_path == "custom/output.jsonl"

    def test_configuration_from_json_file(self, tmp_path):
        """Test loading config from JSON file."""
        config_file = tmp_path / "config.json"
        config_data = {
            "crates": ["crate1", "crate2"],
            "max_threads": 8,
            "output_path": "test/output.jsonl",
        }
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        config = PipelineConfig.from_json(config_file)
        assert config.crates == ["crate1", "crate2"]
        assert config.max_threads == 8
        assert config.output_path == "test/output.jsonl"

    def test_configuration_from_yaml_file(self, tmp_path):
        """Test loading config from YAML file."""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not available")

        config_file = tmp_path / "config.yaml"
        config_data = {
            "crates": ["crate1"],
            "max_threads": 4,
        }
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f)

        config = PipelineConfig.from_yaml(config_file)
        assert config.crates == ["crate1"]
        assert config.max_threads == 4

    def test_to_dict_method(self):
        """Test converting config to dictionary."""
        config = PipelineConfig(
            crates=["test"],
            max_threads=2,
            output_path="test.jsonl",
        )
        config_dict = config.to_dict()
        assert isinstance(config_dict, dict)
        assert config_dict["crates"] == ["test"]
        assert config_dict["max_threads"] == 2
        assert config_dict["output_path"] == "test.jsonl"

    def test_all_field_types(self):
        """Test all field types are correct."""
        config = PipelineConfig()
        assert isinstance(config.crates, list)
        assert isinstance(config.max_threads, int)
        assert isinstance(config.output_path, str)

        assert config.max_clippy_warnings is None or isinstance(
            config.max_clippy_warnings, int
        )
        assert isinstance(config.max_bad_code_warnings, int)
        assert isinstance(config.require_docs, bool)
        assert isinstance(config.allowed_licenses, list)

    def test_edge_cases_empty_lists(self):
        """Test edge cases with empty lists."""
        config = PipelineConfig(crates=[])
        assert config.crates == []
        assert config.allowed_licenses == [
            "MIT",
            "Apache-2.0",
            "BSD",
            "ISC",
            "MIT/Apache-2.0",
        ]

    def test_edge_cases_none_values(self):
        """Test edge cases with None values."""
        config = PipelineConfig(
            crate_list_path=None,
            cache_dir=None,
            checkpoint_path=None,
        )
        assert config.crate_list_path is None
        assert config.cache_dir is None
        assert config.checkpoint_path is None

    def test_invalid_paths(self):
        """Test handling of invalid paths."""
        # Should not raise error, just store the path
        config = PipelineConfig(
            crate_list_path="/nonexistent/path.txt",
            output_path="/nonexistent/output.jsonl",
        )
        assert config.crate_list_path == "/nonexistent/path.txt"
        assert config.output_path == "/nonexistent/output.jsonl"

    def test_license_configuration(self):
        """Test license-related configuration."""
        config = PipelineConfig(
            allowed_licenses=["MIT", "Apache-2.0"],
            enable_license_scan=True,
        )
        assert config.allowed_licenses == ["MIT", "Apache-2.0"]
        assert config.enable_license_scan is True

    def test_deny_configuration(self):
        """Test cargo-deny configuration."""
        config = PipelineConfig(
            enable_deny_scan=True,
            max_deny_severity="high",
            fail_on_deny_violations=True,
        )
        assert config.enable_deny_scan is True
        assert config.max_deny_severity == "high"
        assert config.fail_on_deny_violations is True

    def test_quality_thresholds(self):
        """Test quality threshold configuration."""
        config = PipelineConfig(
            max_clippy_warnings=5,
            max_bad_code_warnings=2,
            require_docs=True,
            min_doc_coverage=0.5,
            max_unsafe_items=10,
            max_outdated_ratio=0.2,
        )
        assert config.max_clippy_warnings == 5
        assert config.max_bad_code_warnings == 2
        assert config.require_docs is True
        assert config.min_doc_coverage == 0.5
        assert config.max_unsafe_items == 10
        assert config.max_outdated_ratio == 0.2

    def test_file_filtering_config(self):
        """Test file filtering configuration."""
        config = PipelineConfig(
            max_line_length=120,
            min_alphabetic_ratio=0.4,
            max_line_length_hard_cap=600,
        )
        assert config.max_line_length == 120
        assert config.min_alphabetic_ratio == 0.4
        assert config.max_line_length_hard_cap == 600

    def test_phase2_configuration(self):
        """Test Phase-2 instruct mode configuration (now the only mode)."""
        config = PipelineConfig(
            max_sft_lines=150,
            max_sft_chars=6000,
            task_type_mix={
                "code_generation": 0.60,
                "transformations": 0.20,
                "error_fixing": 0.15,
                "explanations": 0.05,
            },
            enable_error_injection=True,
            error_injection_method="both",
            enable_prompt_randomization=True,
        )
        assert config.max_sft_lines == 150
        assert config.max_sft_chars == 6000
        assert config.task_type_mix["code_generation"] == 0.60
        assert config.enable_error_injection is True
        assert config.error_injection_method == "both"
        assert config.enable_prompt_randomization is True
