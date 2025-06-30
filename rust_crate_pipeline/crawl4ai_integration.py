"""Crawl4AI Integration Module for Rust Crate Pipeline.

This module provides enterprise-grade web crawling capabilities using Crawl4AI,
optimized for extracting structured data from Rust crate documentation,
GitHub repositories, and related web resources.

Features:
- Asynchronous crawling with rate limiting and retry logic
- Structured data extraction using CSS selectors and LLM strategies
- Comprehensive error handling and logging
- Cache management and session persistence
- Browser pooling and resource optimization

Example:
    Basic usage for crawling Rust crate documentation:

    ```python
    async with CrawlAIManager() as crawler:
        result = await crawler.crawl_crate_docs("serde")
        if result.success:
            print(f"Extracted: {result.structured_data}")
    ```
"""
import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict, List, Optional
from urllib.parse import urlparse

try:
    from crawl4ai import (
        AsyncWebCrawler,
        BrowserConfig,
        CacheMode,
        CrawlerRunConfig,
        DefaultMarkdownGenerator,
        JsonCssExtractionStrategy,
        LLMConfig,
        LLMExtractionStrategy,
        PruningContentFilter,
    )
    CRAWL4AI_AVAILABLE = True
except ImportError:
    CRAWL4AI_AVAILABLE = False
    # Create placeholder classes for type hints
    AsyncWebCrawler = Any
    BrowserConfig = Any
    CrawlerRunConfig = Any
    CacheMode = Any
    LLMConfig = Any
    LLMExtractionStrategy = Any
    JsonCssExtractionStrategy = Any
    DefaultMarkdownGenerator = Any
    PruningContentFilter = Any

from .exceptions import ConfigurationError
from .observability import ObservabilityManager, operation_timer


@dataclass
class CrawlResult:
    """Standardized crawl result container.

    Attributes:
        url: The crawled URL
        success: Whether the crawl was successful
        structured_data: Extracted structured data as dict
        markdown: Clean markdown content
        html: Raw HTML content (optional)
        metadata: Page metadata (title, description, etc.)
        error_message: Error details if crawl failed
        timestamp: When the crawl was performed
        response_time: Time taken for the crawl in seconds
        status_code: HTTP status code
    """
    url: str
    success: bool
    structured_data: Optional[Dict[str, Any]] = None
    markdown: Optional[str] = None
    html: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    timestamp: Optional[str] = None
    response_time: Optional[float] = None
    status_code: Optional[int] = None


@dataclass
class CrawlConfig:
    """Configuration for crawling operations.

    Attributes:
        use_cache: Whether to use caching
        wait_timeout: Timeout for page loads in milliseconds
        extract_links: Whether to extract page links
        extract_images: Whether to extract images
        screenshot: Whether to capture screenshots
        use_llm_extraction: Whether to use LLM for data extraction
        llm_provider: LLM provider (e.g., "openai/gpt-4o")
        max_retries: Maximum number of retry attempts
        request_delay: Delay between requests in seconds
        user_agent: Custom user agent string
        proxy_config: Proxy configuration if needed
    """
    use_cache: bool = True
    wait_timeout: int = 10000  # 10 seconds
    extract_links: bool = True
    extract_images: bool = False
    screenshot: bool = False
    use_llm_extraction: bool = False
    llm_provider: str = "openai/gpt-4o"
    max_retries: int = 3
    request_delay: float = 1.0
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    )
    proxy_config: Optional[Dict[str, str]] = None


class CrawlAIManager:
    """Enterprise-grade Crawl4AI manager for the Rust Crate Pipeline.

    This class provides a high-level interface for web crawling operations
    with built-in error handling, rate limiting, caching, and observability.

    Example:
        ```python
        config = CrawlConfig(use_llm_extraction=True)
        async with CrawlAIManager(config) as crawler:
            # Crawl crate documentation
            result = await crawler.crawl_crate_docs("tokio")

            # Crawl GitHub repository
            github_result = await crawler.crawl_github_repo(
                "tokio-rs/tokio"
            )

            # Custom crawl with schema
            schema = {"title": "h1", "description": ".description"}
            custom_result = await crawler.crawl_with_schema(
                "https://example.com", schema
            )
        ```
    """

    def __init__(
        self,
        config: Optional[CrawlConfig] = None,
        logger: Optional[logging.Logger] = None
    ):
        """Initialize the CrawlAI manager.

        Args:
            config: Crawling configuration
            logger: Logger instance for observability

        Raises:
            ConfigurationError: If Crawl4AI is not available
        """
        if not CRAWL4AI_AVAILABLE:
            raise ConfigurationError(
                "Crawl4AI is not installed. Install with: "
                "pip install crawl4ai[all]"
            )

        self.config = config or CrawlConfig()
        self.logger = logger or logging.getLogger(__name__)
        self.observability = ObservabilityManager(logger=self.logger)
        self._crawler: Optional[AsyncWebCrawler] = None
        self._session_active = False

        # Initialize browser configuration
        self._browser_config = BrowserConfig(
            headless=True,
            verbose=False,
            user_agent=self.config.user_agent,
            proxy=self.config.proxy_config,
            viewport={"width": 1920, "height": 1080},
        )

        # Rust crate specific extraction schemas
        self._crate_schemas = {
            "crates_io": {
                "name": "crate_name",
                "baseSelector": ".crate-header",
                "fields": [
                    {
                        "name": "name",
                        "selector": "h1",
                        "type": "text"
                    },
                    {
                        "name": "version",
                        "selector": ".version",
                        "type": "text"
                    },
                    {
                        "name": "description",
                        "selector": ".description",
                        "type": "text"
                    },
                    {
                        "name": "downloads",
                        "selector": ".downloads",
                        "type": "text"
                    },
                    {
                        "name": "repository",
                        "selector": ".repository a",
                        "type": "attribute",
                        "attribute": "href"
                    }
                ]
            },
            "docs_rs": {
                "name": "documentation",
                "baseSelector": ".rustdoc",
                "fields": [
                    {
                        "name": "title",
                        "selector": ".fqn",
                        "type": "text"
                    },
                    {
                        "name": "content",
                        "selector": ".docblock",
                        "type": "html"
                    },
                    {
                        "name": "modules",
                        "selector": ".module-item",
                        "type": "list",
                        "fields": [
                            {
                                "name": "name",
                                "selector": ".name",
                                "type": "text"
                            },
                            {
                                "name": "link",
                                "selector": "a",
                                "type": "attribute",
                                "attribute": "href"
                            }
                        ]
                    }
                ]
            },
            "github": {
                "name": "repository",
                "fields": [
                    {
                        "name": "title",
                        "selector": ".repository-content h1",
                        "type": "text"
                    },
                    {
                        "name": "description",
                        "selector": ".repository-content .f4",
                        "type": "text"
                    },
                    {
                        "name": "stars",
                        "selector": "#repo-stars-counter-star",
                        "type": "text"
                    },
                    {
                        "name": "language",
                        "selector": ".BorderGrid-cell .text-bold",
                        "type": "text"
                    },
                    {
                        "name": "readme",
                        "selector": "#readme .Box-body",
                        "type": "html"
                    }
                ]
            }
        }

    async def __aenter__(self) -> "CrawlAIManager":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()

    async def start(self) -> None:
        """Initialize the crawler and start the session."""
        try:
            self._crawler = AsyncWebCrawler(config=self._browser_config)
            await self._crawler.start()
            self._session_active = True
            self.logger.info("CrawlAI session started successfully")
        except Exception as e:
            raise ConfigurationError(
                f"Failed to start CrawlAI session: {str(e)}"
            ) from e

    async def stop(self) -> None:
        """Stop the crawler and clean up resources."""
        if self._crawler and self._session_active:
            try:
                await self._crawler.stop()
                self._session_active = False
                self.logger.info("CrawlAI session stopped successfully")
            except Exception as e:
                self.logger.error(f"Error stopping CrawlAI session: {e}")

    @operation_timer("crawl_operation")
    async def crawl_url(
        self,
        url: str,
        schema: Optional[Dict[str, Any]] = None,
        custom_config: Optional[CrawlConfig] = None
    ) -> CrawlResult:
        """Crawl a single URL with optional structured extraction.

        Args:
            url: URL to crawl
            schema: Optional extraction schema for structured data
            custom_config: Override default crawl configuration

        Returns:
            CrawlResult containing extracted data

        Raises:
            NetworkError: If crawling fails
            DataExtractionError: If data extraction fails
        """
        if not self._session_active:
            raise ConfigurationError("CrawlAI session not active")

        config = custom_config or self.config

        try:
            # Prepare extraction strategy
            extraction_strategy = None
            if schema:
                extraction_strategy = JsonCssExtractionStrategy(
                    schema=schema,
                    verbose=True
                )
            elif config.use_llm_extraction and self._has_llm_config():
                extraction_strategy = self._create_llm_strategy()

            # Configure crawl run
            crawl_config = CrawlerRunConfig(
                cache_mode=(
                    CacheMode.ENABLED if config.use_cache
                    else CacheMode.BYPASS
                ),
                wait_for_timeout=config.wait_timeout,
                extraction_strategy=extraction_strategy,
                output_formats=[
                    'markdown', 'extracted_content', 'metadata'
                ],
                markdown_generator=DefaultMarkdownGenerator(
                    content_filter=PruningContentFilter(
                        threshold=0.3,
                        threshold_type="fixed",
                        min_word_threshold=10
                    )
                )
            )

            # Perform crawl with retry logic
            for attempt in range(config.max_retries):
                try:
                    with self.observability.operation_context(
                        "crawl_attempt",
                        {"url": url, "attempt": attempt + 1}
                    ):
                        if attempt > 0:
                            delay = config.request_delay * (2 ** attempt)
                            await asyncio.sleep(delay)

                        result = await self._crawler.arun(
                            url=url,
                            config=crawl_config
                        )

                        return self._process_crawl_result(result, url)

                except Exception as e:
                    if attempt == config.max_retries - 1:
                        raise
                    self.logger.warning(
                        f"Crawl attempt {attempt + 1} failed for {url}: {e}"
                    )

        except Exception as e:
            error_msg = f"Failed to crawl {url}: {str(e)}"
            self.logger.error(error_msg)
            return CrawlResult(
                url=url,
                success=False,
                error_message=error_msg
            )

    async def crawl_crate_docs(self, crate_name: str) -> CrawlResult:
        """Crawl Rust crate documentation from docs.rs.

        Args:
            crate_name: Name of the Rust crate

        Returns:
            CrawlResult with structured crate documentation data
        """
        docs_url = f"https://docs.rs/{crate_name}/latest/{crate_name}/"
        return await self.crawl_url(
            docs_url,
            schema=self._crate_schemas["docs_rs"]
        )

    async def crawl_crates_io(self, crate_name: str) -> CrawlResult:
        """Crawl crate information from crates.io.

        Args:
            crate_name: Name of the Rust crate

        Returns:
            CrawlResult with crate metadata from crates.io
        """
        crates_url = f"https://crates.io/crates/{crate_name}"
        return await self.crawl_url(
            crates_url,
            schema=self._crate_schemas["crates_io"]
        )

    async def crawl_github_repo(self, repo_path: str) -> CrawlResult:
        """Crawl GitHub repository information.

        Args:
            repo_path: GitHub repository path (e.g., "rust-lang/rust")

        Returns:
            CrawlResult with repository information
        """
        github_url = f"https://github.com/{repo_path}"
        return await self.crawl_url(
            github_url,
            schema=self._crate_schemas["github"]
        )

    async def crawl_multiple_urls(
        self,
        urls: List[str],
        max_concurrent: int = 5
    ) -> List[CrawlResult]:
        """Crawl multiple URLs concurrently.

        Args:
            urls: List of URLs to crawl
            max_concurrent: Maximum concurrent crawls

        Returns:
            List of CrawlResult objects
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def crawl_with_semaphore(url: str) -> CrawlResult:
            async with semaphore:
                return await self.crawl_url(url)

        tasks = [crawl_with_semaphore(url) for url in urls]
        return await asyncio.gather(*tasks, return_exceptions=True)

    def _process_crawl_result(
        self,
        raw_result: Any,
        url: str
    ) -> CrawlResult:
        """Process raw Crawl4AI result into standardized format.

        Args:
            raw_result: Raw result from Crawl4AI
            url: Original URL

        Returns:
            Processed CrawlResult
        """
        try:
            structured_data = None
            if (hasattr(raw_result, 'extracted_content') and
                    raw_result.extracted_content):
                try:
                    structured_data = json.loads(raw_result.extracted_content)
                except json.JSONDecodeError:
                    structured_data = {"raw": raw_result.extracted_content}

            metadata = {}
            if hasattr(raw_result, 'metadata') and raw_result.metadata:
                metadata = raw_result.metadata

            return CrawlResult(
                url=getattr(raw_result, 'url', url),
                success=getattr(raw_result, 'success', False),
                structured_data=structured_data,
                markdown=(
                    raw_result.markdown.fit_markdown
                    if hasattr(raw_result, 'markdown')
                    else None
                ),
                html=getattr(raw_result, 'html', None),
                metadata=metadata,
                status_code=getattr(raw_result, 'status_code', None),
                timestamp=getattr(raw_result, 'timestamp', None)
            )

        except Exception as e:
            self.logger.error(f"Error processing crawl result: {e}")
            return CrawlResult(
                url=url,
                success=False,
                error_message=f"Result processing error: {str(e)}"
            )

    def _has_llm_config(self) -> bool:
        """Check if LLM configuration is available."""
        return (
            os.getenv("OPENAI_API_KEY") or
            os.getenv("ANTHROPIC_API_KEY") or
            os.getenv("OLLAMA_BASE_URL")
        )

    def _create_llm_strategy(self) -> LLMExtractionStrategy:
        """Create LLM extraction strategy based on available config."""
        # Determine provider and API key
        if os.getenv("OPENAI_API_KEY"):
            provider = self.config.llm_provider
            api_key = os.getenv("OPENAI_API_KEY")
        elif os.getenv("ANTHROPIC_API_KEY"):
            provider = "anthropic/claude-3-haiku-20240307"
            api_key = os.getenv("ANTHROPIC_API_KEY")
        elif os.getenv("OLLAMA_BASE_URL"):
            provider = "ollama/llama3"
            api_key = "ollama"  # Placeholder for local Ollama
        else:
            raise ConfigurationError("No LLM API keys found")

        llm_config = LLMConfig(
            provider=provider,
            api_token=api_key
        )

        # Basic schema for general content extraction
        schema = {
            "title": "Page title",
            "content": "Main content summary",
            "links": "Important links mentioned",
            "metadata": "Key metadata or facts"
        }

        return LLMExtractionStrategy(
            llm_config=llm_config,
            schema=schema,
            instruction=(
                "Extract the main content, title, important links, "
                "and key metadata from this page. Focus on technical "
                "information, documentation, and actionable content."
            )
        )


# Utility functions for common crawling patterns
async def crawl_rust_ecosystem(
    crate_names: List[str],
    include_github: bool = True,
    max_concurrent: int = 3
) -> Dict[str, Dict[str, CrawlResult]]:
    """Crawl multiple Rust crates across the ecosystem.

    Args:
        crate_names: List of crate names to crawl
        include_github: Whether to also crawl GitHub repositories
        max_concurrent: Maximum concurrent crawls

    Returns:
        Dictionary with crate data organized by source

    Example:
        ```python
        results = await crawl_rust_ecosystem([
            "serde", "tokio", "clap", "reqwest"
        ])

        for crate_name, sources in results.items():
            print(f"Crate: {crate_name}")
            print(f"  Docs: {sources['docs'].success}")
            print(f"  Crates.io: {sources['crates_io'].success}")
            if 'github' in sources:
                print(f"  GitHub: {sources['github'].success}")
        ```
    """
    results = {}

    async with CrawlAIManager() as crawler:
        for crate_name in crate_names:
            crate_results = {}

            # Crawl docs.rs
            crate_results['docs'] = await crawler.crawl_crate_docs(
                crate_name
            )

            # Crawl crates.io
            crate_results['crates_io'] = await crawler.crawl_crates_io(
                crate_name
            )

            # Optionally crawl GitHub if we can determine the repo
            if include_github:
                # Try to extract GitHub URL from crates.io result
                if (crate_results['crates_io'].structured_data and
                        'repository' in crate_results['crates_io'].structured_data):
                    repo_url = crate_results['crates_io'].structured_data[
                        'repository'
                    ]
                    if 'github.com' in repo_url:
                        # Extract owner/repo from URL
                        try:
                            parsed = urlparse(repo_url)
                            path_parts = parsed.path.strip('/').split('/')
                            if len(path_parts) >= 2:
                                github_path = f"{
                                    path_parts[0]}/{
                                    path_parts[1]}"
                                crate_results['github'] = (
                                    await crawler.crawl_github_repo(github_path)
                                )
                        except Exception as e:
                            logging.getLogger(__name__).warning(
                                f"Failed to parse GitHub URL for {crate_name}: {e}")

            results[crate_name] = crate_results

    return results


@asynccontextmanager
async def managed_crawler(
    config: Optional[CrawlConfig] = None
) -> AsyncGenerator[CrawlAIManager, None]:
    """Context manager for CrawlAI operations.

    Args:
        config: Optional crawl configuration

    Yields:
        Configured CrawlAIManager instance

    Example:
        ```python
        async with managed_crawler() as crawler:
            result = await crawler.crawl_url("https://example.com")
        ```
    """
    crawler = CrawlAIManager(config)
    try:
        await crawler.start()
        yield crawler
    finally:
        await crawler.stop()
