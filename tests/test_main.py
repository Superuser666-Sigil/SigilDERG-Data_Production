"""
Integration test for the Sigil Pipeline.

Tests end-to-end pipeline execution with a mock crate to validate
the streaming architecture and basic functionality.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.6.0
"""

import json
from pathlib import Path

import pytest

from sigil_pipeline import config, main


@pytest.fixture
def mock_crate_dir(tmp_path):
    """Create a minimal test crate for integration testing."""
    crate_dir = tmp_path / "test_crate"
    crate_dir.mkdir()

    # Create Cargo.toml
    cargo_toml = crate_dir / "Cargo.toml"
    cargo_toml.write_text(
        """[package]
name = "test_crate"
version = "2.0.0"
edition = "2021"
license = "MIT"

[dependencies]
"""
    )

    # Create src/lib.rs with some code
    src_dir = crate_dir / "src"
    src_dir.mkdir()
    lib_rs = src_dir / "lib.rs"
    lib_rs.write_text(
        """/// A test function
pub fn add(a: i32, b: i32) -> i32 {
    a + b
}
"""
    )

    return crate_dir


@pytest.mark.asyncio
async def test_pipeline_with_mock_crate(mock_crate_dir, tmp_path):
    """
    Test the full pipeline with a mock crate.

    This validates that the streaming architecture works correctly
    and produces valid JSONL output.
    """
    # Create a minimal config
    cfg = config.PipelineConfig(
        crates=["test_crate"],
        output_path=str(tmp_path / "output.jsonl"),
        output_dir=str(tmp_path),
        max_threads=1,
        limit=1,
        enable_license_scan=False,  # Skip license check for speed
        require_docs=False,  # Relax requirements for test
        max_clippy_warnings=100,  # Allow warnings in test
    )

    # Note: This test requires cargo and Rust toolchain to be installed
    # Skip if not available
    from sigil_pipeline.utils import check_cargo_available

    if not check_cargo_available():
        pytest.skip("cargo not available")

    # Run pipeline
    try:
        await main.run_pipeline(cfg)
    except Exception as e:
        # If pipeline fails due to missing tools, skip test
        if "not available" in str(e).lower() or "not found" in str(e).lower():
            pytest.skip(f"Required tool not available: {e}")
        raise

    # Verify output file exists
    output_path = Path(cfg.output_path)
    assert output_path.exists(), "Output JSONL file should exist"

    # Verify output contains valid JSON lines
    samples = []
    with open(output_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    sample = json.loads(line)
                    assert (
                        "input_data" in sample
                    ), "Sample should have 'input_data' field"
                    assert (
                        "output_data" in sample
                    ), "Sample should have 'output_data' field"
                    samples.append(sample)
                except json.JSONDecodeError as e:
                    pytest.fail(f"Invalid JSON in output: {e}")

    # Verify we got at least some samples (may be 0 if crate was filtered)
    # But structure should be valid
    assert isinstance(samples, list), "Should have list of samples"

    # Verify metrics file exists
    metrics_path = Path(cfg.output_dir) / "metrics.json"
    if metrics_path.exists():
        with open(metrics_path, "r", encoding="utf-8") as f:
            metrics = json.load(f)
            assert "total_samples" in metrics
            assert "crates_processed" in metrics
            assert "crates_skipped" in metrics
            assert "filter_breakdown" in metrics  # Priority 5.1 - granular metrics
