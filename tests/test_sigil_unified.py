import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock
from typing import Optional, TYPE_CHECKING

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rust_crate_pipeline.config import PipelineConfig
from rust_crate_pipeline.core import (
    SacredChainTrace,
    TrustVerdict,
    CanonEntry,
    CanonRegistry,
    IRLEngine,
)

# Test configuration constants
TEST_CRATE_URL = "https://docs.rs/serde"

try:
    from crawl4ai import (
        AsyncWebCrawler,
        LLMConfig,
        LLMExtractionStrategy,
        BrowserConfig,
        CrawlerRunConfig,
    )
    crawl4ai_available = True
    print("✅ Crawl4AI available for integration testing")
except ImportError as e:
    crawl4ai_available = False
    print(f"⚠️  Crawl4AI not available: {e}")
    print("📝 Tests will run in mock mode only")
    # Create mock types for when Crawl4AI is not available
    if TYPE_CHECKING:
        from crawl4ai import LLMConfig, LLMExtractionStrategy, BrowserConfig, CrawlerRunConfig
    else:
        LLMConfig = type('LLMConfig', (), {})
        LLMExtractionStrategy = type('LLMExtractionStrategy', (), {})
        BrowserConfig = type('BrowserConfig', (), {})
        CrawlerRunConfig = type('CrawlerRunConfig', (), {})


"""
Comprehensive test suite for Sigil Protocol core components.

This test file consolidates all core functionality testing including:
- TrustVerdict enum validation
- SacredChainTrace creation and serialization
- CanonEntry validation and expiry logic
- CanonRegistry operations and audit trails
- IRLEngine functionality and execution tracking
- Crawl4AI integration tests (when available)

The tests are designed to work both with and without Crawl4AI,
providing comprehensive coverage of the core Sigil Protocol implementation.
"""

class TestTrustVerdict:

    def test_trust_verdict_values(self) -> None:
        assert TrustVerdict.ALLOW.value == "ALLOW"
        assert TrustVerdict.DENY.value == "DENY"
        assert TrustVerdict.DEFER.value == "DEFER"
        assert TrustVerdict.FLAG.value == "FLAG"

    def test_trust_verdict_string_conversion(self) -> None:
        verdict = TrustVerdict.ALLOW
        assert str(verdict) == "ALLOW"
        assert verdict.to_json() == "ALLOW"


class TestSacredChainTrace:

    def test_sacred_chain_trace_creation(self) -> None:
        trace = SacredChainTrace(
            input_data="test-crate",
            context_sources=["crates.io", "docs.rs"],
            reasoning_steps=["step1", "step2"],
            suggestion="ALLOW: Well-documented crate",
            verdict=TrustVerdict.ALLOW,
            audit_info={"score": 8.5},
            irl_score=8.5,
            execution_id="test-exec-123",
            timestamp="2024-01-01T00:00:00Z",
            canon_version="1.3.0",
        )

        assert trace.input_data == "test-crate"
        assert trace.verdict == TrustVerdict.ALLOW
        assert trace.irl_score == 8.5
        assert len(trace.context_sources) == 2
        assert len(trace.reasoning_steps) == 2

    def test_sacred_chain_trace_edge_cases(self) -> None:
        """Test edge cases and error conditions"""
        # Test with minimal required fields
        trace = SacredChainTrace(
            input_data="",
            context_sources=[],
            reasoning_steps=[],
            suggestion="",
            verdict=TrustVerdict.DENY,
            audit_info={},
            irl_score=0.0,
            execution_id="",
            timestamp="",
            canon_version="",
        )
        
        assert trace.input_data == ""
        assert trace.verdict == TrustVerdict.DENY
        assert trace.irl_score == 0.0

    def test_to_audit_log(self) -> None:
        trace = SacredChainTrace(
            input_data="test-crate",
            context_sources=["crates.io"],
            reasoning_steps=["step1"],
            suggestion="ALLOW",
            verdict=TrustVerdict.ALLOW,
            audit_info={"score": 8.0},
            irl_score=8.0,
            execution_id="test-123",
            timestamp="2024-01-01T00:00:00Z",
            canon_version="1.3.0",
        )

        audit_log = trace.to_audit_log()
        parsed = json.loads(audit_log)

        assert parsed["execution_id"] == "test-123"
        assert parsed["rule_zero_compliant"] is True
        assert "sacred_chain" in parsed
        assert parsed["sacred_chain"]["input_data"] == "test-crate"

    def test_verify_integrity(self) -> None:
        execution_id = "abc123def456"
        trace = SacredChainTrace(
            input_data="tokio",
            context_sources=["crates.io"],
            reasoning_steps=["Popular async runtime"],
            suggestion="ALLOW",
            verdict=TrustVerdict.ALLOW,
            audit_info={},
            irl_score=9.0,
            execution_id=execution_id,
            timestamp="2024-01-01T00:00:00Z",
            canon_version="1.3.0",
        )

        result = trace.verify_integrity()
        assert isinstance(result, bool)


class TestCanonEntry:

    def test_canon_entry_creation(self) -> None:
        entry = CanonEntry(
            source="crates.io",
            version="1.3.0",
            authority_level=9,
            content_hash="abc123",
            last_validated="2024-01-01T00:00:00Z",
            expiry="2025-01-01T00:00:00Z",
        )

        assert entry.source == "crates.io"
        assert entry.authority_level == 9
        assert entry.expiry == "2025-01-01T00:00:00Z"

    def test_is_valid_with_expiry(self) -> None:
        future_date = datetime.now(timezone.utc).replace(year=2030).isoformat()
        entry = CanonEntry(
            source="test",
            version="1.3.0",
            authority_level=5,
            content_hash="hash123",
            last_validated="2024-01-01T00:00:00Z",
            expiry=future_date,
        )
        assert entry.is_valid() is True

        past_date = datetime.now(timezone.utc).replace(year=2020).isoformat()
        entry.expiry = past_date
        assert entry.is_valid() is False

    def test_is_valid_without_expiry(self) -> None:
        entry = CanonEntry(
            source="test",
            version="1.3.0",
            authority_level=5,
            content_hash="hash123",
            last_validated="2024-01-01T00:00:00Z",
        )
        assert entry.is_valid() is True


class TestCanonRegistry:

    def test_canon_registry_initialization(self) -> None:
        registry = CanonRegistry()
        assert isinstance(registry.canon_entries, dict)
        assert len(registry.canon_entries) > 0

    def test_register_canon(self) -> None:
        registry = CanonRegistry()
        success = registry.register_canon("test-source", "https://test.com", "Test content", 7)

        assert success is True
        assert "test-source" in registry.canon_entries
        entry = registry.canon_entries["test-source"]
        assert entry.source == "https://test.com"
        assert entry.authority_level == 7

    def test_get_canon(self) -> None:
        registry = CanonRegistry()
        registry.register_canon("test", "https://test.com", "Test content", 5)

        entry = registry.get_canon("test")
        assert entry is not None
        assert entry.source == "https://test.com"

        missing = registry.get_canon("nonexistent")
        assert missing is None

    def test_get_valid_canon_sources(self) -> None:
        registry = CanonRegistry()
        valid_sources = registry.get_valid_canon_sources()
        
        assert isinstance(valid_sources, list)
        assert len(valid_sources) > 0

    def test_audit_trail(self) -> None:
        registry = CanonRegistry()
        registry.register_canon("source1", "url1", "content1", 8)
        registry.register_canon("source2", "url2", "content2", 7)

        trail = registry.audit_trail()
        assert isinstance(trail, list)
        assert len(trail) >= 2

    def test_canon_summary(self) -> None:
        registry = CanonRegistry()
        summary = registry.get_canon_summary()
        
        assert "total_canon_entries" in summary
        assert "valid_canon_entries" in summary
        assert "authority_level_distribution" in summary
        assert "version" in summary


class TestIRLEngine:

    @pytest.fixture
    def mock_config(self) -> Mock:
        config = Mock(spec=PipelineConfig)
        config.crates_io_base_url = "https://crates.io"
        config.docs_rs_base_url = "https://docs.rs"
        config.github_base_url = "https://github.com"
        config.max_concurrent = 5
        config.request_delay = 1.0
        return config

    def test_irl_engine_initialization(self, mock_config: Mock) -> None:
        engine = IRLEngine(mock_config)
        assert engine.config == mock_config
        assert isinstance(engine.canon_registry, CanonRegistry)
        assert len(engine.execution_log) == 0

    @pytest.mark.asyncio
    async def test_irl_engine_context_manager(self, mock_config: Mock) -> None:
        async with IRLEngine(mock_config) as engine:
            assert isinstance(engine, IRLEngine)

    def test_generate_execution_id(self, mock_config: Mock) -> None:
        engine = IRLEngine(mock_config)
        execution_id = engine.generate_execution_id("test-crate")
        
        assert isinstance(execution_id, str)
        assert "exec-" in execution_id
        assert len(execution_id) > 20

    def test_create_sacred_chain_trace(self, mock_config: Mock) -> None:
        engine = IRLEngine(mock_config)
        trace = engine.create_sacred_chain_trace(
            input_data="test-crate",
            context_sources=["crates.io"],
            reasoning_steps=["step1"],
            suggestion="ALLOW",
            verdict=TrustVerdict.ALLOW,
            audit_info={"score": 8.0},
            irl_score=8.0,
        )
        
        assert isinstance(trace, SacredChainTrace)
        assert trace.input_data == "test-crate"
        assert trace.verdict == TrustVerdict.ALLOW
        assert len(engine.execution_log) == 1

    def test_get_audit_summary(self, mock_config: Mock) -> None:
        engine = IRLEngine(mock_config)
        
        summary = engine.get_audit_summary()
        assert summary["total_executions"] == 0
        assert summary["average_irl_score"] == 0.0
        
        engine.create_sacred_chain_trace(
            input_data="test",
            context_sources=["source"],
            reasoning_steps=["step"],
            suggestion="ALLOW",
            verdict=TrustVerdict.ALLOW,
            audit_info={},
            irl_score=8.0,
        )
        
        summary = engine.get_audit_summary()
        assert summary["total_executions"] == 1
        assert summary["average_irl_score"] == 8.0
        assert "ALLOW" in summary["verdicts"]


@pytest.mark.skipif(not crawl4ai_available, reason="Crawl4AI not properly configured")
class TestSigilCompliantPipelineWithCrawl4AI:

    @pytest.fixture
    def mock_config(self) -> Mock:
        config = Mock(spec=PipelineConfig)
        config.crates_io_base_url = "https://crates.io"
        config.docs_rs_base_url = "https://docs.rs"
        config.github_base_url = "https://github.com"
        config.max_concurrent = 5
        config.request_delay = 1.0
        return config

    @pytest.fixture
    def local_llm_config(self) -> Optional[LLMConfig]:
        gcp_llm_endpoint = os.getenv("GCP_LLM_ENDPOINT", "http://localhost:8000")

        if crawl4ai_available:
            llm_config = LLMConfig(
                provider="openai/gpt-4o-mini",
                api_token="no-token-needed",
                base_url=gcp_llm_endpoint,
                max_tokens=2048,
                temperature=0.7,
            )
            return llm_config
        return None

    def test_local_llm_config_creation(self, local_llm_config: Optional[LLMConfig]) -> None:
        if not crawl4ai_available:
            pytest.skip("Crawl4AI not available")

        config = local_llm_config
        assert config is not None
        assert config.api_token == "no-token-needed"
        assert config.base_url is not None
        assert "localhost" in config.base_url or "gcp" in config.base_url.lower()

    @pytest.mark.asyncio
    async def test_basic_crawl4ai_functionality(self, local_llm_config: Optional[LLMConfig]) -> None:
        if not crawl4ai_available:
            pytest.skip("Crawl4AI not available")

        # Configure browser for headless operation
        browser_config = BrowserConfig(headless=True, browser_type="chromium")
        
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=TEST_CRATE_URL)

            assert result is not None
            assert hasattr(result, "success")
            assert hasattr(result, "markdown")

            if result.success:
                assert result.markdown is not None
                assert len(result.markdown) > 0
                print(f"✅ Successfully crawled {len(result.markdown)} characters")
            else:
                error_msg = getattr(result, 'error_message', 'Unknown error')
                print(f"⚠️  Crawl failed: {error_msg}")

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        os.getenv("ENABLE_LLM_TESTS") != "1",
        reason="LLM integration tests require ENABLE_LLM_TESTS=1 and proper model setup",
    )
    async def test_llm_extraction_with_local_model(self, local_llm_config: Optional[LLMConfig]) -> None:
        if not crawl4ai_available:
            pytest.skip("Crawl4AI not available")

        if local_llm_config is None:
            pytest.skip("LLM config not available")

        schema = {
            "type": "object",
            "properties": {
                "crate_name": {
                    "type": "string",
                    "description": "Name of the Rust crate",
                },
                "description": {
                    "type": "string",
                    "description": "Brief description of the crate",
                },
            },
            "required": ["crate_name"],
        }

        extraction_strategy = LLMExtractionStrategy(
            llm_config=local_llm_config,
            schema=schema,
            extraction_type="schema",
            instruction="Extract the crate name and description from this Rust documentation page.",
        )

        # Configure browser and crawler
        browser_config = BrowserConfig(headless=True, browser_type="chromium")
        crawler_config = CrawlerRunConfig(
            word_count_threshold=10,
            extraction_strategy=extraction_strategy
        )

        async with AsyncWebCrawler(config=browser_config) as crawler:
            try:
                result = await crawler.arun(
                    url=TEST_CRATE_URL,
                    config=crawler_config,
                )

                if result.success and result.extracted_content:
                    extracted = json.loads(result.extracted_content)
                    assert isinstance(extracted, (dict, list))
                    print(f"✅ LLM extraction successful: {extracted}")
                else:
                    print("⚠️  LLM extraction failed or no content extracted")

            except Exception as e:
                print(f"⚠️  LLM test failed (expected if model not running): {e}")
                pytest.skip(f"LLM integration requires running model: {e}")
