from __future__ import annotations
#!/usr/bin/env python3
"""
Comprehensive test coverage for critical modules with 0% coverage.
Targets: unified_llm_processor, unified_pipeline, progress_monitor, core modules
"""

import os
import sys
import tempfile
import asyncio
from unittest.mock import Mock, patch, AsyncMock
import pytest

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)


class TestUnifiedLLMProcessor:
    """Test coverage for unified_llm_processor.py"""

    def test_llm_processor_initialization(self) -> None:
        """Test LLM processor initialization"""
        from rust_crate_pipeline.unified_llm_processor import UnifiedLLMProcessor, LLMConfig
        
        config = LLMConfig(
            provider="openai",
            model="gpt-4",
            api_key="test-key"
        )
        
        processor = UnifiedLLMProcessor(config)
        assert processor is not None
        assert hasattr(processor, 'enrich_crate')

    def test_llm_processor_config(self) -> None:
        """Test LLM processor with configuration"""
        from rust_crate_pipeline.unified_llm_processor import UnifiedLLMProcessor, LLMConfig
        
        config = LLMConfig(
            provider="openai",
            model="gpt-4",
            api_key="test-key"
        )
        
        processor = UnifiedLLMProcessor(config)
        assert processor.config == config

    @pytest.mark.asyncio
    async def test_llm_processor_enrich_crate(self) -> None:
        """Test processing a crate with LLM"""
        from rust_crate_pipeline.unified_llm_processor import UnifiedLLMProcessor, LLMConfig
        from rust_crate_pipeline.config import CrateMetadata
        
        # Mock crate data
        crate = CrateMetadata(
            name="test-crate",
            version="1.0.0",
            description="A test crate",
            repository="https://github.com/test/test-crate",
            keywords=["test"],
            categories=["development"],
            readme="README.md",
            downloads=1000
        )
        
        config = LLMConfig(
            provider="openai",
            model="gpt-4",
            api_key="test-key"
        )
        
        processor = UnifiedLLMProcessor(config)
        
        # Mock the actual LLM call
        with patch.object(processor, 'call_llm', return_value="Test enrichment"):
            result = processor.enrich_crate(crate)
            assert result is not None

    def test_llm_processor_providers(self) -> None:
        """Test different LLM providers"""
        from rust_crate_pipeline.unified_llm_processor import UnifiedLLMProcessor, LLMConfig
        
        providers = ['openai', 'azure', 'ollama', 'litellm']
        
        for provider in providers:
            config = LLMConfig(provider=provider, model="test-model")
            processor = UnifiedLLMProcessor(config)
            assert processor.config.provider == provider


class TestUnifiedPipeline:
    """Test coverage for unified_pipeline.py"""

    def test_pipeline_initialization(self) -> None:
        """Test pipeline initialization"""
        from rust_crate_pipeline.unified_pipeline import UnifiedSigilPipeline
        from rust_crate_pipeline.config import PipelineConfig
        
        config = PipelineConfig()
        pipeline = UnifiedSigilPipeline(config)
        assert pipeline is not None
        assert pipeline.config == config

    def test_pipeline_components(self) -> None:
        """Test pipeline component initialization"""
        from rust_crate_pipeline.unified_pipeline import UnifiedSigilPipeline
        from rust_crate_pipeline.config import PipelineConfig
        
        config = PipelineConfig()
        pipeline = UnifiedSigilPipeline(config)
        
        # Test that components are initialized
        assert hasattr(pipeline, 'irl_engine')
        assert hasattr(pipeline, 'scraper')
        assert hasattr(pipeline, 'canon_registry')

    @pytest.mark.asyncio
    async def test_pipeline_analyze_crate(self) -> None:
        """Test pipeline crate analysis"""
        from rust_crate_pipeline.unified_pipeline import UnifiedSigilPipeline
        from rust_crate_pipeline.config import PipelineConfig
        
        config = PipelineConfig()
        pipeline = UnifiedSigilPipeline(config)
        
        # Mock the analysis methods to avoid actual processing
        with patch.object(pipeline, '_gather_documentation', return_value={}):
            with patch.object(pipeline, '_perform_sacred_chain_analysis', return_value=Mock()):
                with patch.object(pipeline, '_generate_analysis_report'):
                    result = await pipeline.analyze_crate("test-crate")
                    assert result is not None

    def test_pipeline_summary(self) -> None:
        """Test pipeline summary generation"""
        from rust_crate_pipeline.unified_pipeline import UnifiedSigilPipeline
        from rust_crate_pipeline.config import PipelineConfig
        
        config = PipelineConfig()
        pipeline = UnifiedSigilPipeline(config)
        
        summary = pipeline.get_pipeline_summary()
        assert isinstance(summary, dict)
        assert "pipeline_version" in summary
        assert "components" in summary


class TestProgressMonitor:
    """Test coverage for progress_monitor.py"""

    def test_progress_monitor_initialization(self) -> None:
        """Test progress monitor initialization"""
        from rust_crate_pipeline.progress_monitor import ProgressMonitor
        
        monitor = ProgressMonitor(total_crates=100)
        assert monitor is not None
        assert monitor.metrics.total_crates == 100
        assert monitor.metrics.processed_crates == 0

    def test_progress_monitor_crate_operations(self) -> None:
        """Test progress monitor crate operations"""
        from rust_crate_pipeline.progress_monitor import ProgressMonitor
        
        monitor = ProgressMonitor(total_crates=10)
        
        # Test start and complete crate
        monitor.start_crate("crate1")
        assert monitor.current_crate == "crate1"
        
        monitor.complete_crate("crate1", success=True)
        assert monitor.metrics.processed_crates == 1
        assert monitor.metrics.successful_crates == 1

    def test_progress_monitor_percentage(self) -> None:
        """Test progress percentage calculation"""
        from rust_crate_pipeline.progress_monitor import ProgressMonitor
        
        monitor = ProgressMonitor(total_crates=100)
        
        monitor.complete_crate("crate1", success=True)
        assert monitor.metrics.progress_percentage == 1.0
        
        monitor.complete_crate("crate2", success=True)
        assert monitor.metrics.progress_percentage == 2.0

    def test_progress_monitor_status(self) -> None:
        """Test progress status reporting"""
        from rust_crate_pipeline.progress_monitor import ProgressMonitor
        
        monitor = ProgressMonitor(total_crates=10)
        
        status = monitor.get_status_summary()
        assert "progress" in status
        assert "processed" in status
        assert "success_rate" in status

    def test_progress_monitor_batch_operations(self) -> None:
        """Test progress monitor batch operations"""
        from rust_crate_pipeline.progress_monitor import ProgressMonitor
        
        monitor = ProgressMonitor(total_crates=100)
        
        monitor.start_batch(1, 10)
        assert monitor.metrics.current_batch == 1
        
        monitor.complete_batch(1)
        assert monitor.metrics.current_operation == "Batch completed, preparing next batch"

    def test_progress_monitor_error_handling(self) -> None:
        """Test progress monitor error handling"""
        from rust_crate_pipeline.progress_monitor import ProgressMonitor
        
        monitor = ProgressMonitor(total_crates=10)
        
        monitor.add_error("crate1", "Test error", "Processing")
        assert len(monitor.metrics.errors) == 1
        assert monitor.metrics.errors[0]["crate"] == "crate1"
        
        monitor.add_warning("crate1", "Test warning")
        assert len(monitor.metrics.warnings) == 1
        assert monitor.metrics.warnings[0]["crate"] == "crate1"


class TestCoreModules:
    """Test coverage for core modules"""

    def test_canon_registry(self) -> None:
        """Test canon registry functionality"""
        from rust_crate_pipeline.core.canon_registry import CanonRegistry, CanonEntry
        
        registry = CanonRegistry()
        assert registry is not None
        
        # Test adding canon entry
        success = registry.register_canon(
            key="test-key",
            source="test-source",
            content="test content",
            authority_level=5
        )
        assert success is True
        
        retrieved = registry.get_canon("test-key")
        assert retrieved is not None
        assert retrieved.source == "test-source"

    def test_sacred_chain(self) -> None:
        """Test sacred chain functionality"""
        from rust_crate_pipeline.core.sacred_chain import SacredChainTrace, TrustVerdict
        
        trace = SacredChainTrace(
            input_data="test-crate",
            context_sources=["crates.io"],
            reasoning_steps=["step1"],
            suggestion="ALLOW",
            verdict=TrustVerdict.ALLOW,
            audit_info={},
            irl_score=8.0,
            execution_id="test-123",
            timestamp="2024-01-01T00:00:00Z",
            canon_version="1.0.0"
        )
        
        assert trace.input_data == "test-crate"
        assert trace.verdict == TrustVerdict.ALLOW
        assert trace.irl_score == 8.0

    def test_irl_engine(self) -> None:
        """Test IRL engine functionality"""
        from rust_crate_pipeline.core.irl_engine import IRLEngine
        from rust_crate_pipeline.config import PipelineConfig
        
        config = PipelineConfig()
        engine = IRLEngine(config)
        assert engine is not None
        
        # Test execution ID generation
        exec_id = engine.generate_execution_id("test-input")
        assert isinstance(exec_id, str)
        assert len(exec_id) > 0


class TestPipelineIntegration:
    """Integration tests for pipeline components"""

    def test_llm_processor_with_pipeline(self) -> None:
        """Test LLM processor integration with pipeline"""
        from rust_crate_pipeline.unified_pipeline import UnifiedSigilPipeline
        from rust_crate_pipeline.unified_llm_processor import UnifiedLLMProcessor, LLMConfig
        from rust_crate_pipeline.config import PipelineConfig
        
        config = PipelineConfig()
        pipeline = UnifiedSigilPipeline(config)
        llm_config = LLMConfig(provider="openai", model="gpt-4")
        llm_processor = UnifiedLLMProcessor(llm_config)
        
        # Test that pipeline can use LLM processor
        pipeline.unified_llm_processor = llm_processor
        assert pipeline.unified_llm_processor == llm_processor


class TestAICriticalModules:
    """Test coverage for AI processing modules"""

    def test_ai_processing_import(self) -> None:
        """Test AI processing module import"""
        from rust_crate_pipeline import ai_processing
        assert ai_processing is not None

    def test_azure_ai_processing_import(self) -> None:
        """Test Azure AI processing module import"""
        from rust_crate_pipeline import azure_ai_processing
        assert azure_ai_processing is not None

    def test_azure_ai_processing_initialization(self) -> None:
        """Test Azure AI processing initialization"""
        from rust_crate_pipeline.azure_ai_processing import AzureOpenAIEnricher
        from rust_crate_pipeline.config import PipelineConfig
        
        config = PipelineConfig()
        enricher = AzureOpenAIEnricher(config)
        assert enricher is not None
        assert hasattr(enricher, 'enrich_crate')


class TestNetworkModule:
    """Test coverage for network.py"""

    def test_network_import(self) -> None:
        """Test network module import"""
        from rust_crate_pipeline import network
        assert network is not None

    def test_github_batch_client(self) -> None:
        """Test GitHubBatchClient public methods"""
        from rust_crate_pipeline.network import GitHubBatchClient
        from rust_crate_pipeline.config import PipelineConfig
        config = PipelineConfig()
        client = GitHubBatchClient(config)
        assert hasattr(client, 'check_rate_limit')
        assert hasattr(client, 'get_repo_stats')
        assert hasattr(client, 'batch_get_repo_stats')

    def test_crate_api_client(self) -> None:
        """Test CrateAPIClient public methods"""
        from rust_crate_pipeline.network import CrateAPIClient
        from rust_crate_pipeline.config import PipelineConfig
        config = PipelineConfig()
        client = CrateAPIClient(config)
        assert hasattr(client, 'fetch_crate_metadata')


class TestPipelineModule:
    """Test coverage for pipeline.py"""

    def test_pipeline_import(self) -> None:
        """Test pipeline module import"""
        from rust_crate_pipeline import pipeline
        assert pipeline is not None

    def test_crate_data_pipeline(self) -> None:
        """Test CrateDataPipeline public methods"""
        from rust_crate_pipeline.pipeline import CrateDataPipeline
        from rust_crate_pipeline.config import PipelineConfig
        config = PipelineConfig()
        pipeline = CrateDataPipeline(config)
        assert hasattr(pipeline, 'get_crate_list')
        assert hasattr(pipeline, 'enrich_batch')
        assert hasattr(pipeline, 'fetch_metadata_batch')
        assert hasattr(pipeline, 'analyze_dependencies')


class TestProductionConfig:
    """Test coverage for production_config.py"""

    def test_production_config_import(self) -> None:
        """Test production config module import"""
        from rust_crate_pipeline import production_config
        assert production_config is not None

    def test_production_config_functions(self) -> None:
        """Test production config functions"""
        from rust_crate_pipeline.production_config import get_production_config, is_production
        # Test function existence
        assert callable(get_production_config)
        assert callable(is_production)


class TestGitHubTokenChecker:
    """Test coverage for github_token_checker.py"""

    def test_github_token_checker_import(self) -> None:
        """Test GitHub token checker module import"""
        from rust_crate_pipeline import github_token_checker
        assert github_token_checker is not None

    def test_github_token_checker_functions(self) -> None:
        """Test GitHub token checker functions"""
        from rust_crate_pipeline.github_token_checker import check_github_token_quick, check_and_setup_github_token
        # Test function existence
        assert callable(check_github_token_quick)
        assert callable(check_and_setup_github_token)


class TestMainModule:
    """Test coverage for main.py"""

    def test_main_import(self) -> None:
        """Test main module import"""
        from rust_crate_pipeline import main
        assert main is not None

    def test_main_functions(self) -> None:
        """Test main module functions"""
        from rust_crate_pipeline.main import parse_arguments, configure_logging, check_disk_space, enforce_rule_zero_reinforcement, main
        # Test function existence
        assert callable(parse_arguments)
        assert callable(configure_logging)
        assert callable(check_disk_space)
        assert callable(enforce_rule_zero_reinforcement)
        assert callable(main)


class TestAnalysisModule:
    """Test coverage for analysis.py"""

    def test_analysis_import(self) -> None:
        """Test analysis module import"""
        from rust_crate_pipeline import analysis
        assert analysis is not None

    def test_analysis_classes(self) -> None:
        """Test analysis module classes"""
        from rust_crate_pipeline.analysis import SourceAnalyzer, SecurityAnalyzer, UserBehaviorAnalyzer
        
        # Test class existence
        assert SourceAnalyzer is not None
        assert SecurityAnalyzer is not None
        assert UserBehaviorAnalyzer is not None

    def test_source_analyzer(self) -> None:
        """Test SourceAnalyzer functionality"""
        from rust_crate_pipeline.analysis import SourceAnalyzer
        from rust_crate_pipeline.config import EnrichedCrate
        
        # Create a mock crate
        crate = EnrichedCrate(
            name="test-crate",
            version="1.0.0",
            description="Test crate",
            repository="https://github.com/test/test-crate",
            keywords=["test"],
            categories=["development"],
            readme="README.md",
            downloads=1000,
            dependencies=[],
            features={}
        )
        
        # Test analysis method exists
        result = SourceAnalyzer.analyze_crate_source(crate)
        assert isinstance(result, dict)


class TestCrateAnalysis:
    """Test coverage for crate_analysis.py"""

    def test_crate_analysis_import(self) -> None:
        """Test crate analysis module import"""
        from rust_crate_pipeline import crate_analysis
        assert crate_analysis is not None

    def test_crate_analyzer(self) -> None:
        """Test CrateAnalyzer functionality"""
        from rust_crate_pipeline.crate_analysis import CrateAnalyzer
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = CrateAnalyzer(crate_source_path=tmpdir)
            assert analyzer is not None
            assert hasattr(analyzer, 'analyze_crate')


class TestUnifiedScraper:
    """Test coverage for unified_scraper.py"""

    def test_unified_scraper_import(self) -> None:
        """Test unified scraper module import"""
        from rust_crate_pipeline.scraping import unified_scraper
        assert unified_scraper is not None

    def test_unified_scraper_class(self) -> None:
        """Test UnifiedScraper functionality"""
        from rust_crate_pipeline.scraping.unified_scraper import UnifiedScraper
        
        scraper = UnifiedScraper()
        assert scraper is not None
        assert hasattr(scraper, 'scrape_crate_documentation')


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 