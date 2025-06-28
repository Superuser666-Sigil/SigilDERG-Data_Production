"""Tests for the config module."""

import pytest
import os
from unittest.mock import patch

from rust_crate_pipeline.config import PipelineConfig, CrateMetadata, EnrichedCrate


class TestPipelineConfig:
    """Test PipelineConfig class."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = PipelineConfig()
        
        assert config.model_path == os.path.expanduser(
            "~/models/deepseek/deepseek-coder-6.7b-instruct.Q4_K_M.gguf"
        )
        assert config.max_tokens == 256
        assert config.model_token_limit == 4096
        assert config.prompt_token_margin == 3000
        assert config.checkpoint_interval == 10
        assert config.max_retries == 3
        assert config.cache_ttl == 3600
        assert config.batch_size == 10
        assert config.n_workers == 4
        assert config.enable_crawl4ai is True
        assert config.crawl4ai_timeout == 30
        assert config.output_path == "output"
        assert config.use_azure_openai is True
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = PipelineConfig(
            model_path="custom-model.gguf",
            max_tokens=512,
            enable_crawl4ai=False,
            output_path="/custom/output"
        )
        
        assert config.model_path == "custom-model.gguf"
        assert config.max_tokens == 512
        assert config.enable_crawl4ai is False
        assert config.output_path == "/custom/output"
    
    def test_github_token_from_env(self):
        """Test GitHub token from environment variable."""
        with patch.dict(os.environ, {'GITHUB_TOKEN': 'test_token'}, clear=True):
            # Reload the module to pick up the new environment
            import importlib
            import rust_crate_pipeline.config
            importlib.reload(rust_crate_pipeline.config)
            from rust_crate_pipeline.config import PipelineConfig
            
            config = PipelineConfig()
            assert config.github_token == "test_token"
    
    def test_github_token_default(self):
        """Test GitHub token default when not in environment."""
        with patch.dict(os.environ, {}, clear=True):
            # Reload the module to pick up the new environment
            import importlib
            import rust_crate_pipeline.config
            importlib.reload(rust_crate_pipeline.config)
            from rust_crate_pipeline.config import PipelineConfig
            
            config = PipelineConfig()
            assert config.github_token == ""


class TestCrateMetadata:
    """Test CrateMetadata class."""
    
    def test_crate_metadata_creation(self):
        """Test creating a CrateMetadata instance."""
        metadata = CrateMetadata(
            name="test-crate",
            version="1.0.0",
            description="Test description",
            repository="https://github.com/test/test-crate",
            keywords=["test"],
            categories=["dev-tools"],
            readme="# Test README",
            downloads=1000,
            github_stars=50
        )
        
        assert metadata.name == "test-crate"
        assert metadata.version == "1.0.0"
        assert metadata.description == "Test description"
        assert metadata.repository == "https://github.com/test/test-crate"
        assert metadata.keywords == ["test"]
        assert metadata.categories == ["dev-tools"]
        assert metadata.readme == "# Test README"
        assert metadata.downloads == 1000
        assert metadata.github_stars == 50
        assert metadata.dependencies == []
        assert metadata.features == {}
        assert metadata.code_snippets == []
        assert metadata.readme_sections == {}
        assert metadata.librs_downloads is None
        assert metadata.source == "crates.io"
        assert metadata.enhanced_scraping == {}
        assert metadata.enhanced_features == []
        assert metadata.enhanced_dependencies == []
    
    def test_crate_metadata_to_dict(self):
        """Test converting CrateMetadata to dictionary."""
        metadata = CrateMetadata(
            name="test-crate",
            version="1.0.0",
            description="Test description",
            repository="https://github.com/test/test-crate",
            keywords=["test"],
            categories=["dev-tools"],
            readme="# Test README",
            downloads=1000,
            github_stars=50
        )
        
        result = metadata.to_dict()
        
        assert isinstance(result, dict)
        assert result["name"] == "test-crate"
        assert result["version"] == "1.0.0"
        assert result["description"] == "Test description"
        assert result["downloads"] == 1000
        assert result["github_stars"] == 50


class TestEnrichedCrate:
    """Test EnrichedCrate class."""
    
    def test_enriched_crate_creation(self):
        """Test creating an EnrichedCrate instance."""
        crate = EnrichedCrate(
            name="test-crate",
            version="1.0.0",
            description="Test description",
            repository="https://github.com/test/test-crate",
            keywords=["test"],
            categories=["dev-tools"],
            readme="# Test README",
            downloads=1000,
            github_stars=50,
            readme_summary="Test summary",
            feature_summary="Feature summary",
            use_case="Testing",
            score=0.8,
            factual_counterfactual="Factual info"
        )
        
        assert crate.name == "test-crate"
        assert crate.readme_summary == "Test summary"
        assert crate.feature_summary == "Feature summary"
        assert crate.use_case == "Testing"
        assert crate.score == 0.8
        assert crate.factual_counterfactual == "Factual info"
        assert crate.source_analysis is None
        assert crate.user_behavior is None
        assert crate.security is None
    
    def test_enriched_crate_with_analysis(self):
        """Test EnrichedCrate with analysis data."""
        source_analysis = {"loc": 1000, "complexity": "medium"}
        user_behavior = {"issues": 10, "prs": 5}
        security = {"vulnerabilities": 0}
        
        crate = EnrichedCrate(
            name="test-crate",
            version="1.0.0",
            description="Test description",
            repository="https://github.com/test/test-crate",
            keywords=["test"],
            categories=["dev-tools"],
            readme="# Test README",
            downloads=1000,
            github_stars=50,
            source_analysis=source_analysis,
            user_behavior=user_behavior,
            security=security
        )
        
        assert crate.source_analysis == source_analysis
        assert crate.user_behavior == user_behavior
        assert crate.security == security 