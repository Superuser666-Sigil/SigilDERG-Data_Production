import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Union

try:
    from crawl4ai import (
        AsyncWebCrawler,
        BrowserConfig,
        CrawlerRunConfig,
        LLMConfig,
        LLMExtractionStrategy,
    )
    CRAWL4AI_AVAILABLE = True
except ImportError:
    CRAWL4AI_AVAILABLE = False
    AsyncWebCrawler = None
    CrawlerRunConfig = None
    LLMExtractionStrategy = None
    BrowserConfig = None
    LLMConfig = None


class ScrapingError(Exception):
    pass


@dataclass
class ScrapingResult:
    url: str
    title: str
    content: str
    structured_data: Dict[str, Any] = field(default_factory=dict)
    quality_score: float = 0.0
    extraction_method: str = "unknown"
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: str(asyncio.get_event_loop(
    ).time() if asyncio.get_event_loop().is_running() else time.time()))

    def __post_init__(self) -> None:
        if self.timestamp == "0":
            import time
            self.timestamp = str(time.time())


class UnifiedScraper:

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        self.crawler: Optional[Any] = None
        self.browser_config: Optional[Any] = None
        self._initialize_crawler()

    def _initialize_crawler(self) -> None:
        if not CRAWL4AI_AVAILABLE:
            self.logger.warning(
                "Crawl4AI not available - using basic scraping mode")
            return

        try:
            # Configure browser for headless operation
            self.browser_config = BrowserConfig(
                headless=self.config.get("headless", True),
                browser_type=self.config.get("browser_type", "chromium"),
                verbose=self.config.get("verbose", False)
            )

            self.crawler = AsyncWebCrawler(config=self.browser_config)
            self.logger.info("✅ Crawl4AI crawler initialized successfully")
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize Crawl4AI: {e}")
            self.crawler = None

    async def __aenter__(self) -> "UnifiedScraper":
        if self.crawler and hasattr(self.crawler, 'start'):
            try:
                await self.crawler.start()
            except Exception as e:
                self.logger.warning(f"Failed to start crawler: {e}")
        return self

    async def __aexit__(
            self,
            exc_type: Optional[type],
            exc_val: Optional[Exception],
            exc_tb: Optional[Any]) -> None:
        if self.crawler and hasattr(self.crawler, 'stop'):
            try:
                await self.crawler.stop()
            except Exception as e:
                self.logger.warning(f"Error stopping crawler: {e}")

    async def scrape_url(
        self,
        url: str,
        doc_type: str = "general",
        extraction_schema: Optional[Dict[str, Any]] = None
    ) -> ScrapingResult:
        if not self.crawler:
            raise ScrapingError("No crawler backend available")

        try:
            # Configure crawler run parameters
            config_params: Dict[str, Any] = {
                "word_count_threshold": self.config.get("word_count_threshold", 10),
                "screenshot": self.config.get("screenshot", False),
            }

            # Add CSS selectors based on document type
            if doc_type == "docs":
                config_params["css_selector"] = "main"
            elif doc_type == "readme":
                config_params["css_selector"] = "article, .readme, main"

            # Update with any additional crawl config
            config_params.update(self.config.get("crawl_config", {}))

            # Ensure max_retries is not passed to CrawlerRunConfig
            config_params.pop("max_retries", None)

            crawl_config = CrawlerRunConfig(**config_params)

            # Set up extraction strategy if schema provided
            extraction_strategy = None
            if extraction_schema and CRAWL4AI_AVAILABLE:
                # Get LLM configuration from config or use defaults
                llm_provider = self.config.get("llm_provider", "ollama")
                llm_api_base = self.config.get(
                    "llm_api_base", "http://localhost:11434")
                llm_model = self.config.get("llm_model", "deepseek-coder:6.7b")
                llm_api_token = self.config.get(
                    "llm_api_token", "no-token-needed")

                # Create LLM config
                llm_config = LLMConfig(
                    provider=llm_provider,
                    api_token=llm_api_token,
                    api_base=llm_api_base,
                    model=llm_model,
                    max_tokens=self.config.get("max_tokens", 2048),
                    temperature=self.config.get("temperature", 0.7)
                )

                extraction_strategy = LLMExtractionStrategy(
                    llm_config=llm_config,
                    schema=extraction_schema,
                    extraction_type="schema",
                    instruction=f"Extract structured data from this {doc_type} content according to the provided schema."
                )

            # Run the crawl
            result = await self.crawler.arun(
                url=url,
                config=crawl_config,
                extraction_strategy=extraction_strategy
            )

            # Handle result (Crawl4AI returns direct result, not container)
            if not result:
                raise ScrapingError("Crawl returned no result")

            if not result.success:
                error_message = getattr(
                    result, 'error_message', 'Crawl was not successful')
                raise ScrapingError(f"Crawl failed: {error_message}")

            markdown_content = getattr(result, 'markdown', '') or ""
            extracted_content = getattr(result, 'extracted_content', None)

            structured_data = self._process_extracted_content(
                extracted_content)
            quality_score = self._calculate_quality_score(
                markdown_content, structured_data)

            return ScrapingResult(
                url=url,
                title=self._extract_title(markdown_content),
                content=markdown_content,
                structured_data=structured_data,
                quality_score=quality_score,
                extraction_method="crawl4ai",
                metadata={
                    "doc_type": doc_type,
                    "content_length": len(markdown_content),
                    "has_structured_data": bool(structured_data),
                    "crawl_success": result.success,
                }
            )

        except Exception as e:
            self.logger.error(f"Scraping error for {url}: {e}")
            raise ScrapingError(f"Failed to scrape {url}: {str(e)}")

    async def scrape_crate_documentation(
            self, crate_name: str) -> Dict[str, ScrapingResult]:
        results: Dict[str, ScrapingResult] = {}

        urls = {
            "crates_io": f"https://crates.io/crates/{crate_name}",
            "docs_rs": f"https://docs.rs/{crate_name}",
            "lib_rs": f"https://lib.rs/crates/{crate_name}",
        }

        for source, url in urls.items():
            try:
                result = await self.scrape_url(url, doc_type="docs")
                results[source] = result
            except ScrapingError as e:
                self.logger.warning(
                    f"Failed to scrape {source} for {crate_name}: {e}")
                results[source] = ScrapingResult(
                    url=url,
                    title=f"{crate_name} - {source}",
                    content="",
                    error=str(e),
                    extraction_method="failed"
                )

        return results

    def _process_extracted_content(
        self, content: Optional[Union[str, Dict[str, Any]]]
    ) -> Dict[str, Any]:
        if not content:
            return {}

        if isinstance(content, str):
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return {"raw_content": content}

        return content if isinstance(content, dict) else {}

    def _calculate_quality_score(
        self, content: str, structured_data: Dict[str, Any]
    ) -> float:
        if not content:
            return 0.0

        score = 0.0

        content_length = len(content)
        if content_length > 1000:
            score += 3.0
        elif content_length > 500:
            score += 2.0
        elif content_length > 100:
            score += 1.0

        if structured_data:
            score += 2.0

        if "title" in content.lower() or "description" in content.lower():
            score += 1.0

        return min(score, 10.0)

    def _extract_title(self, markdown: str) -> str:
        lines = markdown.split('\n')
        for line in lines[:5]:
            if line.startswith('# '):
                return line[2:].strip()
        return "Untitled"

    async def close(self) -> None:
        if self.crawler and hasattr(self.crawler, 'stop'):
            try:
                await self.crawler.stop()
            except Exception as e:
                self.logger.warning(f"Error closing crawler: {e}")


async def quick_scrape(url: str, **kwargs: Any) -> ScrapingResult:
    async with UnifiedScraper() as scraper:
        return await scraper.scrape_url(url, **kwargs)
