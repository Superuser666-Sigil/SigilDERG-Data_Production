"""Test configuration and fixtures for rust_crate_pipeline."""

# Standard library imports
import os
import sys
import tempfile
# Third-party imports
import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any
# Local imports must come after the project root is on sys.path

# Ensure the project root is on the Python path _before_ attempting local imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rust_crate_pipeline.config import PipelineConfig, EnrichedCrate


@pytest.fixture
def sample_crate() -> EnrichedCrate:
    """Create a sample crate for testing."""
    return EnrichedCrate(
        name="test-crate",
        version="1.0.0",
        description="A test crate for unit testing",
        repository="https://github.com/test/test-crate",
        keywords=["test", "example"],
        categories=["development-tools"],
        readme="# Test Crate\n\nThis is a test crate for unit testing.",
        downloads=1000,
        github_stars=50,
        dependencies=[],
        features={},
        code_snippets=[],
        readme_sections={},
        librs_downloads=None,
        source="crates.io",
        enhanced_scraping={},
        enhanced_features=[],
        enhanced_dependencies=[],
        readme_summary="A test crate for unit testing",
        feature_summary="Basic functionality for testing",
        use_case="Unit testing and development",
        score=0.8,
        factual_counterfactual="This is a factual test crate",
        source_analysis=None,
        user_behavior=None,
        security=None,
    )


@pytest.fixture
def basic_config() -> PipelineConfig:
    """Create a basic pipeline configuration for testing."""
    return PipelineConfig(
        enable_crawl4ai=False,
        model_path="test-model.gguf",
        output_path="./test_output",
    )


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def mock_requests():
    """Mock requests for testing network calls."""
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"test": "data"}
        mock_response.text = '{"test": "data"}'
        mock_get.return_value = mock_response
        yield mock_get


@pytest.fixture
def mock_github_token():
    """Mock GitHub token environment variable."""
    with patch.dict(os.environ, {'GITHUB_TOKEN': 'test_token'}):
        yield 'test_token'


@pytest.fixture
def sample_rust_code() -> str:
    """Sample Rust code for testing analysis."""
    return '''
pub struct TestStruct {
    pub field1: String,
    field2: i32,
}

impl TestStruct {
    pub fn new() -> Self {
        Self {
            field1: String::new(),
            field2: 0,
        }
    }
    
    pub fn test_method(&self) -> bool {
        if self.field2 > 0 {
            true
        } else {
            false
        }
    }
}

pub enum TestEnum {
    Variant1,
    Variant2(String),
}

pub trait TestTrait {
    fn trait_method(&self) -> String;
}

impl TestTrait for TestStruct {
    fn trait_method(&self) -> String {
        self.field1.clone()
    }
}
''' 