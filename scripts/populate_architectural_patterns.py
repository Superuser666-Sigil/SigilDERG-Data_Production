#!/usr/bin/env python3
"""
Populate Architectural Patterns Table

This script analyzes the codebase and populates the architectural_patterns table
with patterns, design principles, and architectural decisions found in the project.
"""

import sqlite3
import json
import os
import re
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path

# Architectural patterns identified in the codebase
ARCHITECTURAL_PATTERNS = [
    {
        "pattern_name": "unified_pipeline_architecture",
        "problem_description": "Need for a scalable, modular pipeline to process Rust crates with multiple LLM providers",
        "solution_description": "Unified pipeline pattern with provider abstraction layer, async processing, and modular components",
        "code_snippet": """
# Core pipeline structure
class CrateDataPipeline:
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.llm_processor = UnifiedLLMProcessor(config)
        self.web_crawler = AsyncWebCrawler(config)
        self.analyzer = CrateAnalyzer()
    
    async def process_crate(self, crate_name: str):
        # 1. Fetch metadata
        metadata = await self.fetch_metadata(crate_name)
        # 2. Web scraping
        web_data = await self.web_crawler.scrape(crate_name)
        # 3. AI enrichment
        enriched = await self.llm_processor.enrich(metadata, web_data)
        # 4. Analysis
        analysis = self.analyzer.analyze(enriched)
        return analysis
        """,
        "source_of_truth": "rust_crate_pipeline/pipeline.py",
        "tags": "pipeline,architecture,async,modular",
        "timestamp": datetime.now().isoformat()
    },
    {
        "pattern_name": "provider_abstraction_layer",
        "problem_description": "Need to support multiple LLM providers (Azure, OpenAI, LiteLLM, Ollama) with consistent interface",
        "solution_description": "Abstract base class with provider-specific implementations and configuration management",
        "code_snippet": """
# Provider abstraction
class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str) -> str:
        pass

class AzureOpenAIProvider(BaseLLMProvider):
    async def generate(self, prompt: str) -> str:
        # Azure OpenAI implementation
        pass

class UnifiedLLMProcessor:
    def __init__(self, config: PipelineConfig):
        self.provider = self._get_provider(config)
    
    def _get_provider(self, config: PipelineConfig) -> BaseLLMProvider:
        if config.azure_endpoint:
            return AzureOpenAIProvider(config)
        elif config.openai_api_key:
            return OpenAIProvider(config)
        # ... other providers
        """,
        "source_of_truth": "rust_crate_pipeline/unified_llm_processor.py",
        "tags": "abstraction,llm,providers,configuration",
        "timestamp": datetime.now().isoformat()
    },
    {
        "pattern_name": "rag_cache_system",
        "problem_description": "Need for persistent knowledge storage and fast retrieval of project context and metadata",
        "solution_description": "SQLite-based RAG cache with structured tables for environment metadata, code indexing, and search",
        "code_snippet": """
# RAG cache schema
CREATE TABLE environment_metadata (
    id INTEGER PRIMARY KEY,
    label TEXT,
    os_name TEXT,
    os_version TEXT,
    system_type TEXT,
    processor TEXT,
    bios_version TEXT,
    enforcement_rank INTEGER,
    timestamp TEXT,
    commit_hash TEXT
);

CREATE TABLE code_index (
    id INTEGER PRIMARY KEY,
    file_path TEXT,
    function_name TEXT,
    code_snippet TEXT,
    complexity_score REAL,
    tags TEXT
);
        """,
        "source_of_truth": "sigil_rag_cache.db",
        "tags": "caching,database,sqlite,rag",
        "timestamp": datetime.now().isoformat()
    },
    {
        "pattern_name": "rule_zero_compliance",
        "problem_description": "Need for traceable, explainable, and defensible AI outputs following Rule Zero principles",
        "solution_description": "Comprehensive audit trail system with reasoning chains, trust scoring, and policy enforcement",
        "code_snippet": """
# Rule Zero compliance
class RuleZeroCompliance:
    def __init__(self):
        self.policies = self.load_policies()
        self.audit_trail = []
    
    def validate_output(self, output: str, reasoning: str) -> ComplianceResult:
        # Validate against Rule Zero policies
        score = self.calculate_trust_score(output, reasoning)
        return ComplianceResult(
            allowed=score > 0.7,
            score=score,
            reasoning=reasoning,
            timestamp=datetime.now()
        )
        """,
        "source_of_truth": "rule_zero_lookup.json",
        "tags": "compliance,audit,trust,rule_zero",
        "timestamp": datetime.now().isoformat()
    },
    {
        "pattern_name": "async_web_scraping",
        "problem_description": "Need for robust web scraping with JavaScript rendering and content extraction",
        "solution_description": "Crawl4AI integration with browser automation, content filtering, and fallback mechanisms",
        "code_snippet": """
# Async web scraping with Crawl4AI
from crawl4ai import AsyncWebCrawler, BrowserConfig

class WebScraper:
    def __init__(self, config: ScraperConfig):
        self.crawler = AsyncWebCrawler(
            config=BrowserConfig(headless=True, verbose=True)
        )
    
    async def scrape_crate(self, crate_name: str) -> ScrapedData:
        urls = [
            f"https://crates.io/crates/{crate_name}",
            f"https://docs.rs/{crate_name}",
            f"https://github.com/rust-lang/{crate_name}"
        ]
        
        results = []
        for url in urls:
            try:
                result = await self.crawler.arun(url)
                results.append(result)
            except Exception as e:
                logger.warning(f"Failed to scrape {url}: {e}")
        
        return self.merge_results(results)
        """,
        "source_of_truth": "rust_crate_pipeline/scraping/unified_scraper.py",
        "tags": "scraping,async,crawl4ai,browser",
        "timestamp": datetime.now().isoformat()
    },
    {
        "pattern_name": "modular_configuration",
        "problem_description": "Need for flexible configuration across different environments and deployment scenarios",
        "solution_description": "Environment variable-based configuration with validation and default values",
        "code_snippet": """
# Configuration management - CENTRALIZED APPROACH
from rust_crate_pipeline.config import PipelineConfig

# Proper usage - configuration is centralized
config = PipelineConfig()  # Automatically loads from environment variables

# All Azure configuration is handled in one place:
# - config.azure_openai_endpoint
# - config.azure_openai_api_key  
# - config.azure_openai_deployment_name
# - config.azure_openai_api_version

# Validation is automatic
if config.use_azure_openai:
    # Configuration is guaranteed to be valid here
    process_with_azure(config)
        """,
        "source_of_truth": "rust_crate_pipeline/config.py",
        "tags": "configuration,environment,validation",
        "timestamp": datetime.now().isoformat()
    },
    {
        "pattern_name": "comprehensive_testing",
        "problem_description": "Need for reliable testing across multiple components and integration points",
        "solution_description": "Multi-layered testing strategy with unit tests, integration tests, and validation scripts",
        "code_snippet": """
# Testing structure
tests/
├── conftest.py              # Test configuration
├── test_build.py           # Build system tests
├── test_config_coverage.py # Configuration tests
├── test_crawl4ai_basic.py  # Crawl4AI integration tests
├── test_main_integration.py # Main pipeline tests
├── test_optimization_validation.py # Performance tests
└── test_rule_zero_lookup.py # Rule Zero compliance tests

# Example test
def test_pipeline_integration():
    config = PipelineConfig()
    pipeline = CrateDataPipeline(config)
    result = pipeline.process_crate("serde")
    assert result.name == "serde"
    assert result.enriched_data is not None
        """,
        "source_of_truth": "tests/",
        "tags": "testing,integration,validation,coverage",
        "timestamp": datetime.now().isoformat()
    },
    {
        "pattern_name": "github_workflow_automation",
        "problem_description": "Need for automated CI/CD, testing, and deployment processes",
        "solution_description": "GitHub Actions workflows for testing, PyPI publishing, and pipeline validation",
        "code_snippet": """
# GitHub Actions workflow
name: CI/CD Pipeline

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      - name: Run tests
        run: |
          pytest tests/ -v --cov=rust_crate_pipeline
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        """,
        "source_of_truth": ".github/workflows/",
        "tags": "ci_cd,github_actions,automation,testing",
        "timestamp": datetime.now().isoformat()
    }
]

def analyze_codebase_patterns() -> List[Dict[str, Any]]:
    """Analyze the codebase to identify additional patterns"""
    patterns = []
    
    # Analyze directory structure
    if os.path.exists("rust_crate_pipeline"):
        patterns.append({
            "pattern_name": "package_structure",
            "problem_description": "Need for clear organization and separation of concerns in the codebase",
            "solution_description": "Well-organized package structure with logical module boundaries and clear responsibilities",
            "code_snippet": """
# Project structure
rust_crate_pipeline/
├── __init__.py              # Package initialization
├── main.py                  # CLI interface
├── config.py                # Configuration management
├── pipeline.py              # Main orchestration
├── ai_processing.py         # LLM integration
├── network.py               # API clients
├── analysis.py              # Data analysis
├── utils/                   # Utility functions
│   ├── logging_utils.py
│   └── file_utils.py
└── scraping/                # Web scraping
    └── unified_scraper.py
            """,
            "source_of_truth": "rust_crate_pipeline/",
            "tags": "organization,structure,modularity",
            "timestamp": datetime.now().isoformat()
        })
    
    # Analyze configuration patterns
    if os.path.exists("pyproject.toml"):
        patterns.append({
            "pattern_name": "modern_python_packaging",
            "problem_description": "Need for modern Python packaging with proper metadata and build system",
            "solution_description": "pyproject.toml-based packaging with proper dependencies and build configuration",
            "code_snippet": """
# pyproject.toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "rust-crate-pipeline"
version = "1.3.0"
description = "AI-powered Rust crate analysis pipeline"
requires-python = ">=3.8"
dependencies = [
    "requests>=2.28.0",
    "crawl4ai>=0.6.0",
    "llama-cpp-python>=0.2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "black>=23.0.0",
    "mypy>=1.5.0",
]
            """,
            "source_of_truth": "pyproject.toml",
            "tags": "packaging,python,modern,build",
            "timestamp": datetime.now().isoformat()
        })
    
    return patterns

def populate_architectural_patterns():
    """Populate the architectural_patterns table"""
    
    db_path = "sigil_rag_cache.db"
    
    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return
    
    # Combine predefined patterns with analyzed patterns
    all_patterns = ARCHITECTURAL_PATTERNS + analyze_codebase_patterns()
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Clear existing patterns
        cursor.execute("DELETE FROM architectural_patterns")
        
        # Insert patterns
        for pattern in all_patterns:
            cursor.execute("""
                INSERT INTO architectural_patterns 
                (pattern_name, problem_description, solution_description, 
                 code_snippet, source_of_truth, tags, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                pattern["pattern_name"],
                pattern["problem_description"],
                pattern["solution_description"],
                pattern["code_snippet"],
                pattern["source_of_truth"],
                pattern["tags"],
                pattern["timestamp"]
            ))
        
        conn.commit()
        print(f"Populated {len(all_patterns)} architectural patterns")
        
        # Verify insertion
        cursor.execute("SELECT COUNT(*) FROM architectural_patterns")
        count = cursor.fetchone()[0]
        print(f"Total patterns in database: {count}")
        
    except Exception as e:
        print(f"Error populating patterns: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    populate_architectural_patterns() 