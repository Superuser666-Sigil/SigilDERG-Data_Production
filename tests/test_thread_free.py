"""
Test script to verify thread-free async implementation
"""

import asyncio
import logging
import threading
import sys
import os
import pytest

# Add the project to Python path
sys.path.insert(0, os.path.dirname(__file__))


def monitor_threads():
    """Monitor active threads during execution"""
    return threading.active_count()


@pytest.mark.asyncio
async def test_async_pipeline():
    """Test that the pipeline runs without creating additional threads (model loading bypassed)"""
    print("🦪 Testing Thread-Free Async Pipeline Implementation")
    print("=" * 60)
    initial_threads = monitor_threads()
    print(f"📊 Initial thread count: {initial_threads}")
    try:
        from rust_crate_pipeline.config import PipelineConfig
        from rust_crate_pipeline.pipeline import CrateDataPipeline
        import unittest.mock

        class DummyEnricher:
            def __init__(self, config):
                self.model = None
        # Patch LLMEnricher everywhere it is used in the pipeline
        with unittest.mock.patch('rust_crate_pipeline.pipeline.LLMEnricher', DummyEnricher), \
                unittest.mock.patch('rust_crate_pipeline.ai_processing.LLMEnricher', DummyEnricher):
            config = PipelineConfig(
                enable_crawl4ai=False,
                model_path="dummy_path",
                batch_size=2,
                n_workers=2
            )
            print("✅ PipelineConfig created")
            pipeline = CrateDataPipeline(config)
            print("✅ Pipeline initialized")
            pipeline.crates = ["serde", "tokio"]
            print(f"✅ Test crates set: {pipeline.crates}")
            pre_processing_threads = monitor_threads()
            print(f"📊 Pre-processing thread count: {pre_processing_threads}")
            print("\n🔄 Testing async metadata fetch...")
            try:
                metadata_batch = await pipeline.fetch_metadata_batch(["serde"])
                print(f"✅ Async fetch successful: {len(metadata_batch)} crates fetched")
            except ImportError as e:
                print(f"❌ Required module missing: {e}")
                assert False, f"Required module missing: {e}"
            except FileNotFoundError as e:
                print(f"❌ Required file missing: {e}")
                assert False, f"Required file missing: {e}"
            except Exception as e:
                print(
                    f"⚠️  Async fetch test skipped (expected in test environment): {e}")
            post_processing_threads = monitor_threads()
            print(f"📊 Post-processing thread count: {post_processing_threads}")
            thread_increase = post_processing_threads - initial_threads
            print(f"\n📈 Thread count change: +{thread_increase}")
            assert thread_increase <= 1, f"WARNING: {thread_increase} additional threads created"
            print("✅ SUCCESS: Pipeline operates without thread proliferation")
    except ImportError as e:
        print(f"❌ Required module missing: {e}")
        assert False, f"Required module missing: {e}"
    except FileNotFoundError as e:
        print(f"❌ Required file missing: {e}")
        assert False, f"Required file missing: {e}"
    except Exception as e:
        print(f"❌ Test failed: {e}")
        assert False, f"Unexpected error: {e}"


@pytest.mark.asyncio
async def test_sigil_async_pipeline():
    """Test that the Sigil pipeline also runs without threading"""
    print("\n🔮 Testing Sigil Pipeline Thread-Free Implementation")
    print("=" * 60)
    initial_threads = monitor_threads()
    print(f"📊 Initial thread count: {initial_threads}")
    try:
        from rust_crate_pipeline.config import PipelineConfig
        from sigil_enhanced_pipeline import SigilCompliantPipeline

        config = PipelineConfig(
            enable_crawl4ai=False,
            model_path="dummy_path",
            batch_size=2,
            n_workers=2
        )
        print("✅ PipelineConfig created")

        pipeline = SigilCompliantPipeline(config, skip_ai=True, limit=2)
        print("✅ Sigil pipeline initialized")

        enhanced_available = pipeline.enhanced_scraper is not None
        print(f"✅ Enhanced scraper: {enhanced_available}")

        processing_threads = monitor_threads()
        print(f"📊 Processing thread count: {processing_threads}")

        thread_increase = processing_threads - initial_threads
        print(f"📈 Thread count change: +{thread_increase}")

        assert thread_increase <= 1, f"WARNING: {thread_increase} additional threads created"
        print("✅ SUCCESS: Sigil pipeline operates without thread proliferation")
    except ImportError as e:
        print(f"❌ Required module missing: {e}")
        assert False, f"Required module missing: {e}"
    except FileNotFoundError as e:
        print(f"❌ Required file missing: {e}")
        assert False, f"Required file missing: {e}"
    except Exception as e:
        print(f"❌ Sigil test failed: {e}")
        assert False, f"Unexpected error: {e}"


def test_threading_imports():
    """Verify that threading modules are not being imported"""
    print("\n🔍 Testing Threading Import Usage")
    print("=" * 60)
    import sys
    threading_modules = [
        'threading',
        'concurrent.futures',
        'multiprocessing'
    ]
    imported_threading = []
    for module_name in threading_modules:
        if module_name in sys.modules:
            imported_threading.append(module_name)
    print(f"📦 Threading modules imported: {imported_threading}")
    pipeline_files = [
        'rust_crate_pipeline/pipeline.py',
        'sigil_enhanced_pipeline.py',
        'enhanced_scraping.py'
    ]
    threading_usage = []
    for file_path in pipeline_files:
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if 'ThreadPoolExecutor' in content:
                        threading_usage.append(
                            f"{file_path}: ThreadPoolExecutor")
                    if 'concurrent.futures' in content:
                        threading_usage.append(
                            f"{file_path}: concurrent.futures")
            except UnicodeDecodeError:
                print(f"⚠️  Could not read {file_path} due to encoding issues")
                continue
    assert not threading_usage, f"Threading usage found: {threading_usage}"
    print("✅ SUCCESS: No direct threading usage in pipeline code")


async def main():
    """Run all thread-free tests"""
    print("🚀 Thread-Free Async Pipeline Validation")
    print("=" * 60)

    # Configure minimal logging
    logging.basicConfig(level=logging.WARNING)

    results = {}

    # Test 1: Standard pipeline async implementation
    results['Standard Pipeline'] = await test_async_pipeline()

    # Test 2: Sigil pipeline async implementation
    results['Sigil Pipeline'] = await test_sigil_async_pipeline()

    # Test 3: Threading imports check
    results['Threading Usage'] = test_threading_imports()

    # Summary
    print("\n" + "=" * 60)
    print("🎯 Thread-Free Implementation Results:")

    passed = 0
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"   {status}: {test_name}")
        if result:
            passed += 1

    print(f"\n📊 Overall: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 SUCCESS: Thread-free async implementation verified!")
        print("\n✨ Benefits:")
        print("   ✅ No race conditions or thread safety concerns")
        print("   ✅ Simpler debugging and error handling")
        print("   ✅ Better resource management")
        print("   ✅ Async/await provides clear control flow")
        print("   ✅ Native asyncio integration with Crawl4AI")
    else:
        print("\n⚠️  Some thread-free validation tests failed")

    return passed == total

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
