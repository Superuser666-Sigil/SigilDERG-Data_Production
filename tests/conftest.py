#!/usr/bin/env python3
"""
Optimized pytest configuration for fast development cycles and token efficiency.
Rule Zero-aligned: maximum performance, minimal overhead.
"""

import pytest
from typing import List
from _pytest.config import Config
from _pytest.nodes import Item
from _pytest.config.argparsing import Parser


def pytest_addoption(parser: Parser) -> None:
    """Add custom command line options for test optimization."""
    parser.addoption("--fast", action="store_true", help="Run only fast tests")
    parser.addoption(
        "--coverage-focus",
        action="store_true",
        help="Run coverage tests only",
    )


def pytest_collection_modifyitems(config: Config, items: List[Item]) -> None:
    """Optimize test collection for speed."""
    if config.getoption("--fast"):
        # Skip slow tests
        skip_slow = pytest.mark.skip(reason="--fast mode")
        for item in items:
            if "slow" in item.keywords or any(
                name in str(item.fspath) for name in ["crawl4ai", "integration"]
            ):
                item.add_marker(skip_slow)

    if config.getoption("--coverage-focus"):
        # Run only coverage tests
        coverage_files = [
            "test_config_coverage.py",
            "test_github_token_checker_coverage.py",
            "test_main_module_coverage.py",
            "test_rust_analyzer_coverage.py",
        ]
        skip_non_coverage = pytest.mark.skip(reason="not coverage-focused")
        for item in items:
            if not any(cf in str(item.fspath) for cf in coverage_files):
                item.add_marker(skip_non_coverage)


@pytest.fixture
def mock_config() -> None:
    """Fast mock configuration."""
    from rust_crate_pipeline.config import PipelineConfig

    return PipelineConfig(
        batch_size=2,
        n_workers=1,
        enable_crawl4ai=False,
        max_tokens=50,
    )
