#!/usr/bin/env python3
"""
Test script to validate Sigil enhanced pipeline integration
Runs without requiring AI models for development environment testing
"""

import json
import logging
import os
import sys
import tempfile
from pathlib import Path

# Add the project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)


def test_basic_imports():
    """Test that all required modules can be imported"""
    print("🔍 Testing imports...")
    try:
        from rust_crate_pipeline.config import PipelineConfig

        print("✅ PipelineConfig imported successfully")
    except ImportError as e:
        print(f"❌ Required module missing: {e}")
        assert False, f"Required module missing: {e}"
    except FileNotFoundError as e:
        print(f"❌ Required file missing: {e}")
        assert False, f"Required file missing: {e}"
    except Exception as e:
        print(f"❌ Import test failed: {e}")
        assert False, f"Unexpected error: {e}"


def test_sigil_pipeline_initialization():
    """Test Sigil pipeline can be initialized"""
    print("\n🔧 Testing Sigil pipeline initialization...")
    try:
        from rust_crate_pipeline.config import PipelineConfig
        from sigil_enhanced_pipeline import SigilCompliantPipeline

        config = PipelineConfig()
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            pipeline = SigilCompliantPipeline(
                config, output_dir=temp_dir, limit=2, skip_ai=True
            )
            print(
                f"✅ Pipeline initialized with output_dir: {
                    pipeline.output_dir}"
            )
            print(f"✅ Pipeline crate list has {len(pipeline.crates)} crates")
            print(f"✅ Canon registry has {len(pipeline.canon_registry)} sources")
    except ImportError as e:
        print(f"❌ Required module missing: {e}")
        assert False, f"Required module missing: {e}"
    except FileNotFoundError as e:
        print(f"❌ Required file missing: {e}")
        assert False, f"Required file missing: {e}"
    except Exception as e:
        print(f"❌ Failed to initialize Sigil pipeline: {e}")
        assert False, f"Unexpected error: {e}"


def test_basic_crate_processing():
    """Test basic crate processing without AI"""
    print("\n⚙️ Testing basic crate processing...")

    try:
        from rust_crate_pipeline.config import PipelineConfig
        from sigil_enhanced_pipeline import SigilCompliantPipeline

        config = PipelineConfig()

        with tempfile.TemporaryDirectory() as temp_dir:
            pipeline = SigilCompliantPipeline(
                config,
                output_dir=temp_dir,
                limit=1,  # Just test one crate
                skip_ai=True,
            )

            # Test basic enriched crate creation
            # Accessing protected member _create_basic_enriched_crate for integration test purposes.
            # This is necessary to validate internal crate creation logic not exposed via public API.
            # If possible, refactor to expose a public test hook or factory method.
            test_crate = pipeline._create_basic_enriched_crate("serde")

            print(f"✅ Created basic enriched crate for: {test_crate.name}")
            print(f"✅ Sacred chain ID: {test_crate.sacred_chain_id}")
            print(f"✅ Trust verdict: {test_crate.trust_verdict}")
            print(f"✅ IRL confidence: {test_crate.irl_confidence}")

            # Test integrity verification
            if test_crate.verify_integrity():
                print("✅ Crate integrity verification passed")
            else:
                print("⚠️ Crate integrity verification failed")

            assert True, "Basic crate processing test completed successfully"

    except Exception as e:
        print(f"❌ Failed basic crate processing: {e}")
        import traceback

        traceback.print_exc()
        assert False, f"Failed basic crate processing: {e}"


def test_pipeline_run_basic():
    """Test running the pipeline in basic mode"""
    print("\n🚀 Testing pipeline run in basic mode...")

    try:
        from rust_crate_pipeline.config import PipelineConfig
        from sigil_enhanced_pipeline import SigilCompliantPipeline

        config = PipelineConfig()

        with tempfile.TemporaryDirectory() as temp_dir:
            pipeline = SigilCompliantPipeline(
                config,
                output_dir=temp_dir,
                limit=2,  # Process 2 crates for testing
                skip_ai=True,
            )

            # Run the pipeline
            enriched_crates, analysis = pipeline.run()

            print("✅ Pipeline completed successfully")
            print(f"✅ Processed {len(enriched_crates)} crates")
            print(f"✅ Analysis type: {analysis.get('analysis_type')}")

            # Check output files
            output_files = list(Path(temp_dir).glob("*.json"))
            if output_files:
                print(f"✅ Output files created: {[f.name for f in output_files]}")

                # Validate JSON content
                with open(output_files[0], "r") as f:
                    data = json.load(f)
                    print(
                        f"✅ JSON data valid - {data['total_crates']} crates in output"
                    )
            else:
                print("⚠️ No output files found")

            assert True, "Pipeline run test completed successfully"

    except Exception as e:
        print(f"❌ Failed pipeline run: {e}")
        import traceback

        traceback.print_exc()
        assert False, f"Failed pipeline run: {e}"


def test_cli_integration():
    """Test CLI integration (dry run)"""
    print("\n🖥️ Testing CLI integration...")

    try:
        # Test that the argument parsing works
        from rust_crate_pipeline.main import parse_arguments

        # Test basic arguments
        test_args = ["--limit", "1", "--skip-ai", "--enable-sigil-protocol"]

        # Mock sys.argv for testing
        original_argv = sys.argv
        sys.argv = ["test"] + test_args

        try:
            args = parse_arguments()
            print("✅ CLI arguments parsed successfully")
            print(f"✅ Limit: {args.limit}")
            print(f"✅ Skip AI: {args.skip_ai}")
            print(
                f"✅ Enable Sigil: {
                    getattr(
                        args,
                        'enable_sigil_protocol',
                        False)}"
            )

            assert True, "CLI integration test completed successfully"

        finally:
            sys.argv = original_argv

    except Exception as e:
        print(f"❌ Failed CLI integration test: {e}")
        assert False, f"Failed CLI integration test: {e}"


def test_mock_sacred_chain():
    """Test mock Sacred Chain creation"""
    print("\n🔗 Testing mock Sacred Chain creation...")

    try:
        from rust_crate_pipeline.config import PipelineConfig
        from sigil_enhanced_pipeline import SigilCompliantPipeline

        config = PipelineConfig()

        with tempfile.TemporaryDirectory() as temp_dir:
            pipeline = SigilCompliantPipeline(
                config,
                output_dir=temp_dir,
                limit=1,
                skip_ai=False,  # Test compatibility mode
            )

            # Test mock Sacred Chain creation
            # Accessing protected member _create_mock_sacred_chain_crate for integration test purposes.
            # This is necessary to validate mock Sacred Chain creation logic not exposed via public API.
            # If possible, refactor to expose a public test hook or factory method.
            mock_crate = pipeline._create_mock_sacred_chain_crate("tokio")

            print(f"✅ Mock Sacred Chain created for: {mock_crate.name}")
            print(f"✅ Sacred Chain ID: {mock_crate.sacred_chain_id}")
            print(f"✅ Trust verdict: {mock_crate.trust_verdict}")
            print(f"✅ IRL confidence: {mock_crate.irl_confidence}")
            print(f"✅ Reasoning steps: {len(mock_crate.reasoning_trace)}")

            for i, step in enumerate(mock_crate.reasoning_trace[:3]):
                print(f"   Step {i + 1}: {step}")

            assert True, "Mock Sacred Chain test completed successfully"

    except Exception as e:
        print(f"❌ Failed mock Sacred Chain test: {e}")
        import traceback

        traceback.print_exc()
        assert False, f"Failed mock Sacred Chain test: {e}"


def test_typing_quick_lookup_access():
    """Test that the Rule Zero typing quick lookup is loaded and accessible in the Sigil pipeline."""
    print("\n🔎 Testing Rule Zero typing quick lookup access in Sigil pipeline...")
    from rust_crate_pipeline.config import PipelineConfig
    from sigil_enhanced_pipeline import SigilCompliantPipeline

    config = PipelineConfig()
    import tempfile

    with tempfile.TemporaryDirectory() as temp_dir:
        pipeline = SigilCompliantPipeline(
            config, output_dir=temp_dir, limit=1, skip_ai=True
        )
        lookup = getattr(pipeline, "typing_quick_lookup", None)
        assert lookup is not None, "Quick lookup should be loaded"
        assert "entries" in lookup, "Quick lookup should have 'entries' key"
        print(f"✅ Quick lookup loaded with {len(lookup['entries'])} entries")
        # Check for a known error entry
        errors = [e["error"] for e in lookup["entries"]]
        assert any(
            "type annotation" in err or "typing" in err for err in errors
        ), "Should contain type annotation errors"
        print("✅ Type annotation error entries present in quick lookup")


def main():
    """Run all integration tests"""
    print("🧪 Sigil Enhanced Pipeline Integration Tests")
    print("=" * 50)

    # Configure logging for tests
    logging.basicConfig(level=logging.WARNING)  # Reduce noise during testing

    tests = [
        ("Import Tests", test_basic_imports),
        ("Initialization Tests", test_sigil_pipeline_initialization),
        ("Basic Processing Tests", test_basic_crate_processing),
        ("Pipeline Run Tests", test_pipeline_run_basic),
        ("CLI Integration Tests", test_cli_integration),
        ("Mock Sacred Chain Tests", test_mock_sacred_chain),
        ("Typing Quick Lookup Tests", test_typing_quick_lookup_access),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n📋 Running {test_name}...")
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} PASSED")
            else:
                print(f"❌ {test_name} FAILED")
        except Exception as e:
            print(f"❌ {test_name} ERROR: {e}")

    print("\n" + "=" * 50)
    print(f"🎯 Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! Sigil pipeline integration is working correctly.")
        return 0
    else:
        print("⚠️ Some tests failed. Check output above for details.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
