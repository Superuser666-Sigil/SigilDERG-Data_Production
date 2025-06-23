"""
Enhanced Web Scraping Module with Crawl4AI Integration

This module provides intelligent web scraping capabilities for both
the standard pipeline and the Sigil enhanced pipeline.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig


# Define a custom exception for scraping failures
class ScrapingError(Exception):
    """Custom exception for scraping failures."""


@dataclass
class EnhancedScrapingResult:
    """Result from enhanced scraping with both basic and AI-powered data"""

    url: str
    title: str
    content: str
    structured_data: Dict[str, Any]
    quality_score: float
    extraction_method: str
    error: Optional[str] = None


class EnhancedScraper:
    """Enhanced web scraper with Crawl4AI integration"""

    def __init__(self, llm_model: Optional[str] = None):
        self.llm_model = (
            llm_model
            or "~/models/deepseek/deepseek-coder-6.7b-instruct.Q4_K_M.gguf"
        )
        self.logger = logging.getLogger(__name__)
        try:
            self.crawler = AsyncWebCrawler()
            self.logger.info("✅ Crawl4AI crawler initialized successfully")
        except Exception as e:
            self.logger.error(
                f"❌ Failed to initialize Crawl4AI: {e}", exc_info=True
            )
            # Raise a specific error to signal that the scraper is non-operational
            raise ScrapingError("Failed to initialize Crawl4AI crawler") from e

    async def scrape_documentation(
        self, url: str, doc_type: str = "general"
    ) -> EnhancedScrapingResult:
        """
        Scrape documentation with intelligent extraction using Crawl4AI.

        Args:
            url: URL to scrape
            doc_type: Type of documentation (readme, docs, api, etc.)

        Returns:
            An EnhancedScrapingResult object.

        Raises:
            ScrapingError: If Crawl4AI is not available or fails during execution.
        """
        if not self.crawler:
            # This should not be reached if the constructor raises an exception,
            # but it's a good safeguard.
            raise ScrapingError("Crawl4AI crawler is not initialized.")

        try:
            # Configure crawl settings
            config_params: Dict[str, Any] = {"word_count_threshold": 10}
            if doc_type == "docs":
                config_params["css_selector"] = "main"

            config = CrawlerRunConfig(**config_params)

            # Perform the crawl
            result_container = await self.crawler.arun(
                url=url, config=config
            )  # type: ignore

            if not result_container or not result_container.results:
                error_message = "Crawl returned no results"
                self.logger.error(
                    f"Crawl4AI failed for {url}: {error_message}"
                )
                raise ScrapingError(
                    f"Crawl4AI failed for {url}: {error_message}"
                )

            result = result_container.results[0]

            if not result.success:
                error_message = (
                    result.error_message or "Crawl was not successful"
                )
                self.logger.error(
                    f"Crawl4AI failed for {url}: {error_message}"
                )
                raise ScrapingError(
                    f"Crawl4AI failed for {url}: {error_message}"
                )

            markdown_content = result.markdown or ""

            # Extract structured data
            structured_data = self._process_extracted_content(
                result.extracted_content
            )

            # Calculate quality score
            quality_score = self._calculate_quality_score(
                markdown_content, structured_data
            )

            return EnhancedScrapingResult(
                url=url,
                title=self._extract_title(markdown_content),
                content=markdown_content,
                structured_data=structured_data,
                quality_score=quality_score,
                extraction_method="crawl4ai",
            )

        except Exception as e:
            self.logger.error(f"Crawl4AI error for {url}: {e}", exc_info=True)
            raise ScrapingError(
                f"An unexpected error occurred during scraping for {url}"
            ) from e

    def _process_extracted_content(
        self, content: Optional[Union[str, Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Safely process the extracted content from Crawl4AI result."""
        if not content:
            return {}
        if isinstance(content, dict):
            return content
        if isinstance(content, str):
            try:
                # Attempt to parse the string as JSON
                return json.loads(content)
            except json.JSONDecodeError:
                # If it's not valid JSON, return it as raw content
                self.logger.warning(
                    "Crawl4AI returned a string that is not valid JSON."
                )
                return {"raw_content": content}

        self.logger.warning(
            f"Unexpected content type from Crawl4AI: {type(content)}"
        )
        return {"raw_content": str(content)}

    def _calculate_quality_score(
        self, content: str, structured_data: Dict[str, Any]
    ) -> float:
        """Calculate quality score based on content richness"""
        score = 0.0

        # Content length factor
        word_count = len(content.split())
        if word_count > 100:
            score += 0.3
        if word_count > 500:
            score += 0.2

        # Structured data factor
        if structured_data:
            score += 0.3
            if len(structured_data) > 3:
                score += 0.1

        # Code examples factor
        if "```" in content or "<code>" in content:
            score += 0.1

        return min(score, 1.0)

    def _extract_title(self, markdown: str) -> str:
        """Extract title from markdown content"""
        lines = markdown.split("\n")
        for line in lines:
            if line.startswith("# "):
                return line[2:].strip()
        return "Untitled"

    async def close(self):
        """Close the crawler"""
        pass


class CrateDocumentationScraper:
    """Specialized scraper for Rust crate documentation"""

    def __init__(self):
        try:
            self.scraper = EnhancedScraper()
        except ScrapingError as e:
            logging.error(
                f"Failed to initialize CrateDocumentationScraper: {e}"
            )
            # Propagate the error to prevent usage of a non-functional scraper
            raise

    async def scrape_crate_info(
        self, crate_name: str
    ) -> Dict[str, EnhancedScrapingResult]:
        """Scrape comprehensive information about a crate"""
        results: Dict[str, EnhancedScrapingResult] = {}

        # Define URLs to scrape
        urls: Dict[str, Optional[str]] = {
            "docs_rs": f"https://docs.rs/{crate_name}",
            "lib_rs": f"https://lib.rs/crates/{crate_name}",
            "github_readme": None,  # Will be determined from crates.io API
        }

        # Scrape each source
        for source, url in urls.items():
            if url:
                try:
                    result = await self.scraper.scrape_documentation(
                        url, source
                    )
                    results[source] = result
                except ScrapingError as e:
                    logging.error(
                        f"Failed to scrape {source} for {crate_name}: {e}"
                    )
                    # Create an error result to indicate failure for this source
                    results[source] = EnhancedScrapingResult(
                        url=url,
                        title="Scraping Failed",
                        content="",
                        structured_data={},
                        quality_score=0.0,
                        extraction_method="crawl4ai",
                        error=str(e),
                    )
                except Exception as e:
                    logging.error(
                        (
                            "An unexpected error occurred while scraping "
                            f"{source} for {crate_name}: {e}"
                        ),
                        exc_info=True,
                    )
                    # Create an error result for unexpected failures
                    results[source] = EnhancedScrapingResult(
                        url=url,
                        title="Unexpected Scraping Error",
                        content="",
                        structured_data={},
                        quality_score=0.0,
                        extraction_method="crawl4ai",
                        error=str(e),
                    )

        return results

    async def close(self):
        """Close the scraper"""
        await self.scraper.close()


async def test_enhanced_scraping():
    """Test the enhanced scraping functionality"""
    try:
        scraper = CrateDocumentationScraper()
    except ScrapingError:
        logging.error("Could not start test, scraper initialization failed.")
        return

    try:
        print("🧪 Testing enhanced scraping with serde...")
        results = await scraper.scrape_crate_info("serde")

        for source, result in results.items():
            print(f"\n📄 {source.upper()}:")
            print(f"   Method: {result.extraction_method}")
            print(f"   Quality: {result.quality_score:.2f}")
            print(f"   Title: {result.title[:50]}...")
            print(f"   Content: {len(result.content)} chars")
            print(f"   Structured: {len(result.structured_data)} fields")
            if result.error:
                print(f"   Error: {result.error}")

    finally:
        await scraper.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_enhanced_scraping())
