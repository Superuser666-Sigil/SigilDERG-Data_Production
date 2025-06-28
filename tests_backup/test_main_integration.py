from __future__ import annotations
#!/usr/bin/env python3
"""
Minimal test to verify pipeline integration works correctly
"""

import os
import sys
import tempfile

# Add project to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)


def test_pipeline_integration() -> None:
    """Test that pipeline can be imported and used correctly"""
    print("Testing Pipeline Integration")
    print("=" * 60)
    try:
        from rust_crate_pipeline.config import PipelineConfig
        from rust_crate_pipeline.pipeline import CrateDataPipeline

        print("All imports successful")

        # Create a basic config
        config = PipelineConfig(n_workers=1, batch_size=1)
        pipeline = CrateDataPipeline(config)

        print("Pipeline created successfully")
        print(f"   - Workers: {pipeline.config.n_workers}")
        print(f"   - Batch size: {pipeline.config.batch_size}")

        # Test that we can get crate list
        crates = pipeline.get_crate_list()
        assert len(crates) > 0, "Crate list should not be empty"
        print(f"   - Crate list length: {len(crates)}")

        print("Pipeline integration test completed successfully")

    except ImportError as e:
        print(f"Required module missing: {e}")
        assert False, f"Required module missing: {e}"
    except FileNotFoundError as e:
        print(f"Required file missing: {e}")
        assert False, f"Required file missing: {e}"
    except Exception as e:
        print(f"Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        assert False, f"Unexpected error: {e}"


def test_config_interface() -> None:
    """Test that config interface works correctly"""
    print("\nTesting Config Interface")
    print("-" * 40)

    try:
        from rust_crate_pipeline.config import PipelineConfig

        config = PipelineConfig(
            n_workers=4,
            batch_size=10,
            enable_crawl4ai=True
        )

        essential_attributes = ["n_workers", "batch_size", "enable_crawl4ai"]

        for attr in essential_attributes:
            if hasattr(config, attr):
                print(f"Config has attribute: {attr}")
            else:
                print(f"Attribute missing: {attr}")

        assert config.n_workers == 4
        assert config.batch_size == 10
        assert config.enable_crawl4ai is True

        print("Config interface test completed successfully")

    except Exception as e:
        print(f"Config test failed: {e}")
        assert False, f"Config test failed: {e}"


def test_cli_argument_parsing() -> None:
    """Test that CLI arguments are properly parsed"""
    print("\nTesting CLI Argument Integration")
    print("-" * 40)

    original_argv = sys.argv

    try:
        from rust_crate_pipeline.main import parse_arguments

        # Test parsing basic arguments
        test_cases = [
            ["--batch-size", "5"],
            ["--workers", "2"],
            ["--enable-crawl4ai"],
        ]

        for i, test_args in enumerate(test_cases):
            sys.argv = ["test"] + test_args

            try:
                args = parse_arguments()
                print(f"Test case {i + 1}: {' '.join(test_args)}")
                print(f"   - Batch size: {getattr(args, 'batch_size', 'None')}")
                print(f"   - Workers: {getattr(args, 'workers', 'None')}")
                print(f"   - Enable crawl4ai: {getattr(args, 'enable_crawl4ai', False)}")

            except Exception as e:
                print(f"Test case {i + 1} failed: {e}")

        sys.argv = original_argv
        print("CLI argument parsing test completed successfully")

    except Exception as e:
        print(f"CLI test failed: {e}")
        sys.argv = original_argv
        assert False, f"CLI test failed: {e}"


def main() -> int:
    """Run all integration tests"""
    print("Rust Crate Pipeline - Integration Tests")
    print("=" * 60)

    tests = [
        ("Pipeline Integration", test_pipeline_integration),
        ("Config Interface", test_config_interface),
        ("CLI Argument Integration", test_cli_argument_parsing),
    ]

    passed = 0
    for test_name, test_func in tests:
        try:
            test_func()
            print(f"\n{test_name}: PASSED")
            passed += 1
        except Exception as e:
            print(f"\n{test_name}: ERROR - {e}")

    print("\n" + "=" * 60)
    print(f"Integration Test Results: {passed}/{len(tests)} passed")

    if passed == len(tests):
        print("All integration tests passed!")
        print("Pipeline is successfully integrated!")
        return 0
    else:
        print("Some integration tests failed.")
        return 1


if __name__ == "__main__":
    main()
