"""
Type stubs for Crawl4AI library.

This file provides type annotations for Crawl4AI classes and functions
to resolve Pyright/mypy type checking issues.
"""

from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass


@dataclass
class LLMConfig:
    """Configuration for LLM integration in Crawl4AI."""
    provider: str
    api_token: str
    base_url: Optional[str] = None
    api_base: Optional[str] = None
    model: Optional[str] = None
    max_tokens: int = 2048
    temperature: float = 0.7


@dataclass
class CrawlerRunConfig:
    """Configuration for crawler runs."""
    word_count_threshold: int = 10
    screenshot: bool = False
    css_selector: Optional[str] = None
    extraction_strategy: Optional["LLMExtractionStrategy"] = None


@dataclass
class BrowserConfig:
    """Configuration for browser settings."""
    headless: bool = True
    browser_type: str = "chromium"
    verbose: bool = False


class CrawlResult:
    """Result from a crawl operation."""
    success: bool
    markdown: Optional[str]
    error_message: Optional[str]
    extracted_content: Optional[str]
    metadata: Dict[str, Any]


class CrawlResultContainer:
    """Container for crawl results."""
    results: List[CrawlResult]


class LLMExtractionStrategy:
    """Strategy for LLM-based content extraction."""
    
    def __init__(
        self,
        llm_config: LLMConfig,
        schema: Dict[str, Any],
        extraction_type: str = "schema",
        instruction: Optional[str] = None,
    ) -> None: ...


class AsyncWebCrawler:
    """Asynchronous web crawler for Crawl4AI."""
    
    def __init__(self, config: Optional[BrowserConfig] = None) -> None: ...
    
    async def start(self) -> None: ...
    
    async def stop(self) -> None: ...
    
    async def arun(
        self,
        url: str,
        config: Optional[CrawlerRunConfig] = None,
        extraction_strategy: Optional[LLMExtractionStrategy] = None,
    ) -> CrawlResult: ...
    
    async def __aenter__(self) -> "AsyncWebCrawler": ...
    
    async def __aexit__(self, exc_type: Optional[type], exc_val: Optional[Exception], exc_tb: Optional[Any]) -> None: ... 