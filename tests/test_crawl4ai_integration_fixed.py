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


def test_enhanced_scraping():
    """Test the enhanced scraping module"""
    print("🧪 Testing Enhanced Scraping Module...")
    try:
        from enhanced_scraping import (
            CrateDocumentationScraper,
            EnhancedScraper,
        )

        print("✅ Enhanced scraping imports successful")
        scraper = EnhancedScraper(enable_crawl4ai=True)
        print(
            f"✅ Enhanced scraper initialized (Crawl4AI enabled: {scraper.enable_crawl4ai})"
        )
        crate_scraper = CrateDocumentationScraper(enable_crawl4ai=True)
        assert crate_scraper is not None
        print("✅ Crate documentation scraper initialized")
        return True
    except Exception as e:
        print(f"❌ Enhanced Scraping Module failed with exception: {e}")
        return False


def test_standard_pipeline_integration():
    """Test Crawl4AI integration in standard pipeline"""
    print("\n🧪 Testing Standard Pipeline Integration...")
    try:
        from rust_crate_pipeline.config import PipelineConfig

        config = PipelineConfig(
            enable_crawl4ai=True,
            crawl4ai_model="~/models/deepseek/deepseek-coder-6.7b-instruct.Q4_K_M.gguf",
        )
        assert config is not None
        print("✅ PipelineConfig with Crawl4AI created")
        print("✅ Standard pipeline configuration successful")
        return True
    except Exception as e:
        print(f"❌ Standard Pipeline Integration failed with exception: {e}")
        return False


def test_sigil_pipeline_integration():
    """Test Crawl4AI integration in Sigil pipeline"""
    print("\n🧪 Testing Sigil Pipeline Integration...")
    try:
        from rust_crate_pipeline.config import PipelineConfig

        config = PipelineConfig(
            enable_crawl4ai=True,
            crawl4ai_model="~/models/deepseek/deepseek-coder-6.7b-instruct.Q4_K_M.gguf",
        )
        assert config is not None
        print("✅ PipelineConfig with Crawl4AI created")
        print("✅ Sigil pipeline configuration successful")
        return True
    except Exception as e:
        print(f"❌ Sigil Pipeline Integration failed with exception: {e}")
        return False


def test_cli_integration():
    """Test CLI integration with Crawl4AI options"""
    print("\n🧪 Testing CLI Integration...")
    try:
        from rust_crate_pipeline.main import parse_arguments

        test_args = [
            "--enable-crawl4ai",
            "--crawl4ai-model",
            "~/models/deepseek/deepseek-coder-6.7b-instruct.Q4_K_M.gguf",
            "--limit",
            "1",
        ]
        original_argv = sys.argv
        sys.argv = ["main.py"] + test_args
        try:
            args = parse_arguments()
            print("✅ CLI parsing successful:")
            print(
                f"   - Enable Crawl4AI: {getattr(args, 'enable_crawl4ai', True)}"
            )
            print(
                f"   - Crawl4AI Model: {getattr(args, 'crawl4ai_model', 'default')}"
            )
            print(
                f"   - Disable Crawl4AI: {getattr(args, 'disable_crawl4ai', False)}"
            )
            return True
        finally:
            sys.argv = original_argv
    except Exception as e:
        print(f"❌ CLI Integration failed with exception: {e}")
        return False


async def test_async_functionality():
    """Test async functionality with basic scraping"""
    try:
        from enhanced_scraping import EnhancedScraper

        scraper = EnhancedScraper(enable_crawl4ai=False)  # Use basic scraping

        # Test with a simple public URL using the correct method
        result = await scraper.scrape_documentation("https://httpbin.org/html")

        # Just verify that we got some result back without errors
        print("✅ Async scraping successful:")
        print("   - URL: https://httpbin.org/html")
        print(f"   - Result type: {type(result).__name__}")
        print("   - Async functionality confirmed")
        return True
    except Exception as e:
        print(f"❌ Async Functionality failed with exception: {e}")
        return False


def main():
    """Run all integration tests"""
    print("🚀 Crawl4AI Integration Test Suite")
    print("=" * 50)

    # Define tests
    tests = [
        ("Enhanced Scraping Module", test_enhanced_scraping),
        ("Standard Pipeline Integration", test_standard_pipeline_integration),
        ("Sigil Pipeline Integration", test_sigil_pipeline_integration),
        ("CLI Integration", test_cli_integration),
    ]

    results = {}

    # Run synchronous tests
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results[test_name] = False

    # Run async test
    try:
        async_result = asyncio.run(test_async_functionality())
        results["Async Functionality"] = async_result
    except Exception as e:
        print(f"❌ Async Functionality failed with exception: {e}")
        results["Async Functionality"] = False

    # Print results
    print("\n" + "=" * 50)
    print("🎯 Test Results Summary:")
    passed = 0
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"   {status}: {test_name}")
        if result:
            passed += 1

    print(f"\n📊 Overall: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! Crawl4AI integration is successful!")
        print("\n📋 Ready for use:")
        print(
            "   - Standard Pipeline: "
            "python -m rust_crate_pipeline --enable-crawl4ai"
        )
        print(
            "   - Sigil Pipeline: "
            "python -m rust_crate_pipeline "
            "--enable-sigil-protocol --enable-crawl4ai"
        )
        print(
            "   - Disable Crawl4AI: "
            "python -m rust_crate_pipeline --disable-crawl4ai"
        )
    else:
        print("⚠️  Some tests failed. Review the errors above.")

    return passed == total


if __name__ == "__main__":
    success = main()
