from __future__ import annotations
#!/usr/bin/env python3
"""
Comprehensive Crawl4AI Integration Test Suite
Tests all aspects of Crawl4AI integration with the Rust Crate Pipeline
"""

import asyncio
import os
import sys

# Add the workspace root to Python path for module imports
workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, workspace_root)


def test_unified_scraper_initialization() -> bool:
    """Test the unified scraper module initialization."""
    print("Testing Unified Scraper Module Initialization...")
    try:
        from rust_crate_pipeline.scraping.unified_scraper import UnifiedScraper

        print("Unified scraper imports successful")

        # Initialization should succeed if Crawl4AI is installed
        scraper = UnifiedScraper()
        print("UnifiedScraper initialized successfully.")
        assert scraper is not None

        return True
    except Exception as e:
        print(f"Unified Scraper Module initialization failed: {e}")
        return False


def test_pipeline_config_integration() -> bool:
    """Test Crawl4AI integration in pipeline configuration."""
    print("\nTesting Pipeline Configuration Integration...")
    try:
        from rust_crate_pipeline.config import PipelineConfig

        # Default config should have Crawl4AI enabled
        config = PipelineConfig()
        assert config.enable_crawl4ai is True
        print("Default PipelineConfig has Crawl4AI enabled.")

        # Config with specific model
        model_path = "/fake/path/to/model.gguf"
        config = PipelineConfig(crawl4ai_model=model_path)
        assert config.crawl4ai_model == model_path
        print("PipelineConfig with custom Crawl4AI model created.")

        return True
    except Exception as e:
        print(f"Pipeline Configuration Integration failed: {e}")
        return False


def test_cli_integration() -> bool:
    """Test CLI integration with Crawl4AI options."""
    print("\nTesting CLI Integration...")
    try:
        from rust_crate_pipeline.main import parse_arguments

        # Test --disable-crawl4ai flag
        test_args_disable = ["--disable-crawl4ai", "--limit", "1"]
        original_argv = sys.argv
        sys.argv = ["main.py"] + test_args_disable
        try:
            args = parse_arguments()
            assert args.disable_crawl4ai is True
            print("CLI parsing for --disable-crawl4ai successful.")
        finally:
            sys.argv = original_argv

        # Test --crawl4ai-model argument
        model_path = "/another/fake/model.gguf"
        test_args_model = ["--crawl4ai-model", model_path, "--limit", "1"]
        sys.argv = ["main.py"] + test_args_model
        try:
            args = parse_arguments()
            assert args.crawl4ai_model == model_path
            print("CLI parsing for --crawl4ai-model successful.")
        finally:
            sys.argv = original_argv

        return True
    except Exception as e:
        print(f"CLI Integration failed: {e}")
        return False


async def test_async_scraping_functionality() -> bool:
    """Test async scraping functionality with a live URL."""
    print("\nTesting Async Scraping Functionality...")
    # This test requires a network connection and a valid GGUF model path.
    # It may be skipped in certain CI environments.
    model_path = os.path.expanduser(
        "~/models/deepseek/deepseek-coder-6.7b-instruct.Q4_K_M.gguf"
    )
    if not os.path.exists(model_path):
        print("SKIPPING: GGUF model not found at", model_path)
        return True  # Skip test if model is not present

    try:
        from rust_crate_pipeline.scraping.unified_scraper import UnifiedScraper

        # Use a well-known, stable URL for testing
        url = "https://docs.rs/serde/latest/serde/"
        print(f"Scraping URL: {url}")

        scraper = UnifiedScraper()
        result = await scraper.scrape_url(url, doc_type="docs")
        await scraper.close()

        assert result is not None
        assert result.error is None
        assert result.extraction_method == "crawl4ai"
        assert len(result.content) > 100
        assert result.quality_score > 0.5
        assert "serde" in result.title.lower()

        print("Async scraping successful:")
        print(f"   - Title: {result.title}")
        print(f"   - Quality Score: {result.quality_score:.2f}")
        print(f"   - Content Length: {len(result.content)}")
        return True
    except Exception as e:
        print(f"Async Scraping Functionality failed: {e}")
        return False


def main() -> bool:
    """Run all integration tests."""
    print("Crawl4AI Integration Test Suite")
    print("=" * 50)

    # Define synchronous tests
    sync_tests = [
        (
            "Unified Scraper Initialization",
            test_unified_scraper_initialization,
        ),
        (
            "Pipeline Configuration Integration",
            test_pipeline_config_integration,
        ),
        ("CLI Integration", test_cli_integration),
    ]

    results = {}
    all_passed = True

    # Run synchronous tests
    for test_name, test_func in sync_tests:
        try:
            result = test_func()
            results[test_name] = result
            if not result:
                all_passed = False
        except Exception as e:
            print(f"{test_name} crashed with exception: {e}")
            results[test_name] = False
            all_passed = False

    # Run asynchronous test
    print("\n" + "-" * 50)
    try:
        async_result = asyncio.run(test_async_scraping_functionality())
        results["Async Scraping Functionality"] = async_result
        if not async_result:
            all_passed = False
    except Exception as e:
        print(f"Async Scraping Functionality crashed with exception: {e}")
        results["Async Scraping Functionality"] = False
        all_passed = False

    # Print results summary
    print("\n" + "=" * 50)
    print("Test Results Summary:")
    for test_name, result in results.items():
        status = "PASSED" if result else "FAILED"
        print(f"   {status}: {test_name}")

    passed_count = sum(1 for result in results.values() if result)
    total_count = len(results)
    print(f"\nOverall: {passed_count}/{total_count} tests passed")

    if all_passed:
        print("\nAll tests passed! Crawl4AI integration is robust.")
    else:
        print("\nSome tests failed. Please review the errors above.")

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
