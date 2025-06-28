from __future__ import annotations
#!/usr/bin/env python3
"""
Simple test to verify Crawl4AI is working correctly.
Rule Zero compliant validation before proceeding with complex tests.
"""

import sys
from pathlib import Path

import pytest

# Add the project root to Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Test basic Crawl4AI functionality


def test_crawl4ai_import() -> None:
    """Test that Crawl4AI can be imported without errors"""
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

        assert AsyncWebCrawler is not None
        assert BrowserConfig is not None
        assert CrawlerRunConfig is not None
    except ImportError as e:
        pytest.fail(f"Failed to import Crawl4AI: {e}")


@pytest.mark.asyncio
async def test_crawl4ai_basic_functionality() -> None:
    """Test basic Crawl4AI crawling functionality"""
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

        # Configure browser for headless operation
        browser_config = BrowserConfig(headless=True, browser_type="chromium")

        # Configure crawler
        crawler_config = CrawlerRunConfig(
            word_count_threshold=10,
            screenshot=False,  # Disable screenshot for faster test
        )

        # Test actual crawling
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(
                url="https://example.com", config=crawler_config
            )

            # Validate results
            assert result is not None
            assert result.success is True
            assert result.markdown is not None
            assert len(result.markdown) > 0
            domain_check = (
                "Example Domain" in result.markdown
                or "example" in result.markdown.lower()
            )
            assert domain_check

    except Exception as e:
        pytest.fail(f"Crawl4AI basic functionality test failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
