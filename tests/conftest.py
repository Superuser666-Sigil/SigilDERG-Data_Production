"""
Shared pytest fixtures for Sigil Pipeline tests.

Provides reusable test fixtures for creating mock crates, configs, and test data.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from sigil_pipeline.config import PipelineConfig


@pytest.fixture
def sample_crate_dir(tmp_path):
    """Create a temporary crate directory with Cargo.toml and sample code."""
    crate_dir = tmp_path / "test_crate-0.1.0"
    crate_dir.mkdir()

    # Create Cargo.toml
    cargo_toml = crate_dir / "Cargo.toml"
    cargo_toml.write_text(
        """[package]
name = "test_crate"
version = "0.1.0"
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
        """/// A test function that adds two numbers.
///
/// # Examples
///
/// ```
/// use test_crate::add;
/// assert_eq!(add(2, 3), 5);
/// ```
pub fn add(a: i32, b: i32) -> i32 {
    a + b
}
"""
    )

    return crate_dir


@pytest.fixture
def sample_code_file(tmp_path):
    """Create a sample Rust code file."""
    code_file = tmp_path / "sample.rs"
    code_file.write_text(
        """/// A sample function
pub fn hello() {
    println!("Hello, world!");
}
"""
    )
    return code_file


@pytest.fixture
def sample_config():
    """Create a default PipelineConfig for testing."""
    return PipelineConfig(
        crates=[],
        max_threads=1,
        output_path="output/test_output.jsonl",
        output_dir="output",
        allow_edition_2018=False,
        max_clippy_warnings=0,
        require_docs=True,
        enable_license_scan=False,  # Disable for faster tests
    )


@pytest.fixture
def temp_output_dir(tmp_path):
    """Create a temporary output directory."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def sample_jsonl_file(tmp_path):
    """Create a sample JSONL dataset file."""
    jsonl_file = tmp_path / "sample.jsonl"
    samples = [
        {"prompt": "Write a Rust program", "gen": "fn main() {}"},
        {
            "prompt": "Write a function",
            "gen": "fn add(a: i32, b: i32) -> i32 { a + b }",
        },
    ]
    with open(jsonl_file, "w", encoding="utf-8") as f:
        for sample in samples:
            f.write(json.dumps(sample) + "\n")
    return jsonl_file


@pytest.fixture
def mock_clippy_output():
    """Create mock Clippy JSON output."""
    return json.dumps(
        {
            "reason": "compiler-message",
            "message": {
                "level": "warning",
                "message": "unused variable",
            },
        }
    )


@pytest.fixture
def mock_geiger_output():
    """Create mock Geiger JSON output."""
    return json.dumps(
        {
            "packages": [
                {
                    "unsafety": {
                        "used": {
                            "functions": {"unsafe_": 2},
                            "exprs": {"unsafe_": 1},
                            "item_impls": {"unsafe_": 0},
                            "methods": {"unsafe_": 0},
                        }
                    }
                }
            ]
        }
    )


@pytest.fixture
def mock_outdated_output():
    """Create mock cargo outdated JSON output."""
    return json.dumps(
        {
            "dependencies": [
                {"name": "dep1", "project": "1.0.0", "latest": "1.0.0"},
                {"name": "dep2", "project": "1.0.0", "latest": "1.1.0"},
            ]
        }
    )


@pytest.fixture
def phase1_spec(tmp_path):
    """Create a Phase 1 format specification file."""
    spec_file = tmp_path / "phase1_format_spec.json"
    spec = {
        "format_requirements": {
            "required_fields": ["prompt", "gen"],
            "code_formatting": {
                "has_backticks": False,
            },
        },
        "prompt_characteristics": {
            "length_stats": {
                "avg": 50,
                "min": 20,
                "max": 200,
            }
        },
    }
    with open(spec_file, "w", encoding="utf-8") as f:
        json.dump(spec, f)
    return spec_file


def create_mock_crate(
    tmp_path, name: str, edition: str = "2021", license: str = "MIT"
) -> Path:
    """Helper function to create a mock crate structure."""
    crate_dir = tmp_path / f"{name}-0.1.0"
    crate_dir.mkdir()

    cargo_toml = crate_dir / "Cargo.toml"
    cargo_toml.write_text(
        f"""[package]
name = "{name}"
version = "0.1.0"
edition = "{edition}"
license = "{license}"

[dependencies]
"""
    )

    src_dir = crate_dir / "src"
    src_dir.mkdir()
    lib_rs = src_dir / "lib.rs"
    lib_rs.write_text("pub fn test() {}")

    return crate_dir


def create_mock_clippy_output(warnings: int = 0, errors: int = 0) -> str:
    """Helper function to create mock Clippy JSON output."""
    output_lines = []
    for _ in range(warnings):
        output_lines.append(
            json.dumps(
                {
                    "reason": "compiler-message",
                    "message": {
                        "level": "warning",
                        "message": "test warning",
                    },
                }
            )
        )
    for _ in range(errors):
        output_lines.append(
            json.dumps(
                {
                    "reason": "compiler-message",
                    "message": {
                        "level": "error",
                        "message": "test error",
                    },
                }
            )
        )
    return "\n".join(output_lines)


def create_mock_geiger_output(unsafe_items: int = 0) -> str:
    """Helper function to create mock Geiger JSON output."""
    return json.dumps(
        {
            "packages": [
                {
                    "unsafety": {
                        "used": {
                            "functions": {"unsafe_": unsafe_items},
                            "exprs": {"unsafe_": 0},
                            "item_impls": {"unsafe_": 0},
                            "methods": {"unsafe_": 0},
                        }
                    }
                }
            ]
        }
    )


def create_mock_outdated_output(outdated_count: int = 0, total: int = 10) -> str:
    """Helper function to create mock outdated output."""
    deps = []
    for i in range(total):
        is_outdated = i < outdated_count
        deps.append(
            {
                "name": f"dep{i}",
                "project": "1.0.0",
                "latest": "1.1.0" if is_outdated else "1.0.0",
            }
        )
    return json.dumps({"dependencies": deps})


def assert_sample_format(sample: dict[str, Any]) -> None:
    """Helper function to validate sample structure."""
    assert "prompt" in sample, "Sample must have 'prompt' field"
    assert "gen" in sample, "Sample must have 'gen' field"
    assert isinstance(sample["prompt"], str), "Prompt must be a string"
    assert isinstance(sample["gen"], str), "Gen must be a string"
