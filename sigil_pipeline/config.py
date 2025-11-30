"""
Configuration module for the Sigil Pipeline.

Defines PipelineConfig dataclass with all configurable settings.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.5.0
"""

from dataclasses import dataclass, field
from pathlib import Path

# All types use modern Python 3.12 syntax


@dataclass
class PipelineConfig:
    """
    Configuration for the Sigil Pipeline.

    All settings are configurable via constructor arguments, JSON/YAML files,
    or environment variables.
    """

    # Crates to analyze
    crates: list[str] = field(default_factory=list)
    """List of crate names to analyze. If empty, loads from crate_list_path or default."""

    crate_list_path: str | None = None
    """Path to file containing crate names (one per line). If None, uses default."""

    # Dataset integration
    include_stack_dataset: bool = False
    """Whether to include files from the Stack Rust dataset (disabled by default)."""

    stack_dataset_path: str = "datasets/the-stack-rust-clean"
    """Path to the Stack Rust dataset (local directory, defaults to datasets/)."""

    stack_dataset_use_streaming: bool = False
    """Whether to stream from HuggingFace if local dataset not found. Default: False (local only)."""

    stack_dataset_hf_name: str | None = "ammarnasr/the-stack-rust-clean"
    """HuggingFace dataset name to use if streaming is enabled and local path not found."""

    extra_phase2_shards: list[str] = field(default_factory=list)
    """Additional Phase-2 style JSONL shards to append after generation (e.g., experimental upscales)."""

    phase1_dataset_path: str | None = None
    """Path to Phase 1 dataset JSONL file or HuggingFace dataset name to merge with Phase 2 output."""

    phase1_spec_path: str | None = None
    """Path to Phase 1 format specification JSON file (for validation)."""

    validate_format: bool = True
    """Validate Phase 2 samples against Phase 1 format specification."""

    merge_with_phase1: bool = False
    """Whether to merge Phase 2 output with Phase 1 dataset."""

    shuffle_merged: bool = True
    """Shuffle merged dataset (recommended for training)."""

    phase2_weight: float = 1.0
    """Weight for Phase 2 samples in weighted sampling (1.0 = equal weight with Phase 1)."""

    phase1_phase2_ratio: float | None = None
    """Target ratio of Phase-1:Phase-2 samples (e.g., 10.0 = 10:1 ratio). None = use phase2_weight instead."""

    auto_upsample_phase2: bool = True
    """Automatically up-sample Phase-2 if it's small relative to Phase-1 (prioritizes instruct behavior)."""

    # Train/val split configuration
    create_train_val_split: bool = False
    """Whether to create train/val split after dataset generation."""

    val_ratio: float = 0.1
    """Ratio of sources (crates/files) to put in validation set (default: 0.1 = 10%)."""

    # Performance settings
    max_threads: int = 4
    """Maximum number of parallel threads for crate processing (default: 4, max recommended: 8)."""

    # Output settings
    output_path: str = "output/sigil_phase2_dataset.jsonl"
    """Path to output JSONL file."""

    output_dir: str = "output"
    """Directory for output files."""

    # Quality thresholds
    allow_edition_2018: bool = False
    """Allow Rust 2018 edition crates. Default: False (only 2021+)."""

    max_clippy_warnings: int | None = None
    """Maximum allowed total Clippy warnings (deprecated - use max_bad_code_warnings instead). Default: None."""

    max_bad_code_warnings: int = 0
    """Maximum allowed 'bad_code' category Clippy warnings (unsafe code, memory safety, logic errors). Style/documentation warnings are ignored. Default: 0."""

    require_docs: bool = True
    """Require documentation comments. Default: True."""

    min_doc_coverage: float = 0.0
    """Minimum documentation coverage ratio (0.0-1.0). Default: 0.0 (any docs)."""

    # License filtering
    allowed_licenses: list[str] = field(
        default_factory=lambda: ["MIT", "Apache-2.0", "BSD", "ISC", "MIT/Apache-2.0"]
    )
    """List of allowed licenses. Crates with other licenses will be filtered out."""

    enable_license_scan: bool = True
    """Enable license checking via cargo-license. Default: True."""

    # Quality filtering enhancements
    max_unsafe_items: int | None = None
    """Maximum allowed unsafe code items (from Geiger). None = no filter, 0 = no unsafe allowed."""

    max_outdated_ratio: float | None = None
    """Maximum allowed ratio of outdated dependencies (0.0-1.0). None = no filter."""

    # Cargo-deny configuration
    enable_deny_scan: bool = False
    """Enable cargo-deny security and license auditing. Default: False (optional, can be slow)."""

    max_deny_severity: str | None = None
    """Maximum allowed deny severity level. None = no filter based on severity."""

    fail_on_deny_violations: bool = True
    """Fail crate if cargo-deny reports any violations. Default: True."""

    # File filtering
    max_line_length: int = 100
    """Maximum average line length. Files exceeding this are filtered out (matches Stack dataset criteria)."""

    min_alphabetic_ratio: float = 0.3
    """Minimum ratio of alphabetic characters. Default: 0.3 (filters minified code, matches Stack dataset criteria)."""

    max_line_length_hard_cap: int = 500
    """Hard cap for maximum line length in any code file. Default: 500 (matches Stack dataset criteria)."""

    # Tool configuration
    reuse_cargo_target: bool = True
    """Reuse a shared cargo target directory for faster builds. Default: True."""

    cargo_target_dir: str | None = None
    """Path to shared cargo target directory. If None, uses default location."""

    # Caching configuration
    cache_dir: str | None = None
    """Path to cache directory for downloaded crates. If None, no caching."""

    enable_caching: bool = True
    """Enable caching of downloaded crates. Default: True."""

    # Processing limits
    limit: int | None = None
    """Limit number of crates to process. If None, processes all."""

    # Checkpoint/resume configuration
    checkpoint_path: str | None = None
    """Path to checkpoint file for resuming. If None, no checkpointing."""

    enable_checkpointing: bool = True
    """Enable automatic checkpointing. Default: True."""

    checkpoint_interval: int = 10
    """Save checkpoint every N crates processed. Default: 10."""

    # Logging
    log_level: str = "INFO"
    """Logging level: DEBUG, INFO, WARNING, ERROR."""

    verbose: bool = False
    """Enable verbose logging output."""

    # Phase-2 configuration
    prompt_mode: str = "phase1_compat"
    """Prompt generation mode: 'phase1_compat' (backwards compatible) or 'instruct' (Phase-2)."""

    max_sft_lines: int = 200
    """Maximum lines per snippet for Phase-2 dataset (default: 200)."""

    max_sft_chars: int = 8000
    """Maximum characters per snippet for Phase-2 dataset (default: 8000)."""

    task_type_mix: dict[str, float] = field(
        default_factory=lambda: {
            "code_generation": 0.70,
            "transformations": 0.15,
            "error_fixing": 0.10,
            "explanations": 0.05,
        }
    )
    """Task type distribution for Phase-2 dataset. Must sum to 1.0."""

    enable_error_injection: bool = True
    """Enable error-fixing task generation for Phase-2 dataset."""

    error_injection_method: str = "both"
    """Error injection method: 'real_compile', 'simulate', or 'both'."""

    error_injection_timeout: int = 120
    """Timeout (seconds) for cargo-based real error injection attempts."""

    # Prompt generation configuration
    prompt_seed: int | None = None
    """RNG seed for prompt template randomization. If None, uses system random.
    Stored in dataset metadata for reproducibility."""

    enable_prompt_randomization: bool = True
    """Enable template randomization for prompt diversity. Default: True."""

    # Analysis result caching
    enable_analysis_cache: bool = True
    """Cache cargo tool results to avoid re-running on unchanged crates. Default: True."""

    analysis_cache_dir: str = ".cache/analysis"
    """Directory for analysis cache files. Default: .cache/analysis."""

    # Observability configuration
    enable_structured_logging: bool = True
    """Use structlog for structured JSON logging when available. Default: True."""

    log_file: str | None = None
    """Path to log file. If None, logs only to console."""

    json_logs: bool = False
    """Output logs as JSON (for production/log aggregation). Default: False."""

    enable_prometheus_output: bool = False
    """Export metrics in Prometheus text format alongside JSON. Default: False."""

    prometheus_output_path: str | None = None
    """Path to Prometheus metrics file. If None, uses output_dir/metrics.prom."""

    capture_environment: bool = True
    """Capture and log environment fingerprint at startup. Default: True."""

    # Dataset Hardening Mode (Rust 2024 Benchmark Quality)
    # See ADR-013 and docs/runbooks/RUST_2024_TOOLCHAIN_SETUP.md for details
    dataset_hardening: bool = False
    """Enable strict Rust 2024 dataset hardening mode. When enabled, applies additional
    quality gates: strict Clippy (pedantic/nursery), rustfmt validation, unsafe block
    rejection. Requires rustc 1.85+ for full edition 2024 support. Default: False."""

    hardening_min_edition: str = "2024"
    """Minimum Rust edition required for hardened samples. Default: '2024'.
    Crates with older editions will be filtered out in hardening mode."""

    hardening_strict_clippy: bool = True
    """Enable strict Clippy linting with pedantic and nursery lint groups.
    This is slower than default Clippy but catches more issues. Default: True."""

    hardening_deny_antipatterns: bool = True
    """Deny common anti-patterns: unwrap_used, expect_used, panic.
    Code containing these patterns will be rejected in hardening mode. Default: True."""

    hardening_require_rustfmt: bool = True
    """Require code to pass `cargo fmt --check` with style_edition 2024.
    Unformatted code will be rejected in hardening mode. Default: True."""

    hardening_reject_unsafe: bool = True
    """Reject code containing `unsafe` blocks (not just crate-level Geiger metrics).
    Uses tree-sitter to detect unsafe blocks at the sample level. Default: True."""

    @classmethod
    def from_dict(cls, data: dict) -> "PipelineConfig":
        """Create config from dictionary."""
        return cls(**data)

    @classmethod
    def from_json(cls, path: str | Path) -> "PipelineConfig":
        """Load config from JSON file."""
        import json

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "PipelineConfig":
        """Load config from YAML file."""
        try:
            import yaml

            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return cls.from_dict(data)
        except ImportError:
            raise ImportError("PyYAML is required for YAML config files")

    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        return {
            "crates": self.crates,
            "crate_list_path": self.crate_list_path,
            "include_stack_dataset": self.include_stack_dataset,
            "stack_dataset_path": self.stack_dataset_path,
            "stack_dataset_use_streaming": self.stack_dataset_use_streaming,
            "stack_dataset_hf_name": self.stack_dataset_hf_name,
            "extra_phase2_shards": self.extra_phase2_shards,
            "max_threads": self.max_threads,
            "output_path": self.output_path,
            "output_dir": self.output_dir,
            "allow_edition_2018": self.allow_edition_2018,
            "max_clippy_warnings": self.max_clippy_warnings,
            "max_bad_code_warnings": self.max_bad_code_warnings,
            "require_docs": self.require_docs,
            "min_doc_coverage": self.min_doc_coverage,
            "allowed_licenses": self.allowed_licenses,
            "enable_license_scan": self.enable_license_scan,
            "max_unsafe_items": self.max_unsafe_items,
            "max_outdated_ratio": self.max_outdated_ratio,
            "enable_deny_scan": self.enable_deny_scan,
            "max_deny_severity": self.max_deny_severity,
            "fail_on_deny_violations": self.fail_on_deny_violations,
            "max_line_length": self.max_line_length,
            "min_alphabetic_ratio": self.min_alphabetic_ratio,
            "reuse_cargo_target": self.reuse_cargo_target,
            "cargo_target_dir": self.cargo_target_dir,
            "limit": self.limit,
            "log_level": self.log_level,
            "verbose": self.verbose,
            "phase1_dataset_path": self.phase1_dataset_path,
            "phase1_spec_path": self.phase1_spec_path,
            "validate_format": self.validate_format,
            "merge_with_phase1": self.merge_with_phase1,
            "shuffle_merged": self.shuffle_merged,
            "phase2_weight": self.phase2_weight,
            "prompt_mode": self.prompt_mode,
            "max_sft_lines": self.max_sft_lines,
            "max_sft_chars": self.max_sft_chars,
            "task_type_mix": self.task_type_mix,
            "enable_error_injection": self.enable_error_injection,
            "error_injection_method": self.error_injection_method,
            "error_injection_timeout": self.error_injection_timeout,
            "cache_dir": self.cache_dir,
            "enable_caching": self.enable_caching,
            "max_line_length_hard_cap": self.max_line_length_hard_cap,
            "phase1_phase2_ratio": self.phase1_phase2_ratio,
            "auto_upsample_phase2": self.auto_upsample_phase2,
            "create_train_val_split": self.create_train_val_split,
            "val_ratio": self.val_ratio,
            "prompt_seed": self.prompt_seed,
            "enable_prompt_randomization": self.enable_prompt_randomization,
            "enable_analysis_cache": self.enable_analysis_cache,
            "analysis_cache_dir": self.analysis_cache_dir,
            "enable_structured_logging": self.enable_structured_logging,
            "log_file": self.log_file,
            "json_logs": self.json_logs,
            "enable_prometheus_output": self.enable_prometheus_output,
            "prometheus_output_path": self.prometheus_output_path,
            "capture_environment": self.capture_environment,
            "dataset_hardening": self.dataset_hardening,
            "hardening_min_edition": self.hardening_min_edition,
            "hardening_strict_clippy": self.hardening_strict_clippy,
            "hardening_deny_antipatterns": self.hardening_deny_antipatterns,
            "hardening_require_rustfmt": self.hardening_require_rustfmt,
            "hardening_reject_unsafe": self.hardening_reject_unsafe,
        }
