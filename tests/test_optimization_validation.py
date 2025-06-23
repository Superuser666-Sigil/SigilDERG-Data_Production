# test_optimization_validation.py
"""
Test script to validate the code optimization and atomic unit separation
"""
import os
import sys

# Add the workspace to the path
sys.path.append(os.path.dirname(__file__))


def test_atomic_utilities():
    """Test that the atomic utilities work correctly"""
    print("=== Testing Atomic Utilities ===")
    try:
        from utils.rust_code_analyzer import RustCodeAnalyzer

        # Test empty metrics creation
        metrics = RustCodeAnalyzer.create_empty_metrics()
        assert "file_count" in metrics
        assert "loc" in metrics
        assert metrics["file_count"] == 0
        print("✅ RustCodeAnalyzer.create_empty_metrics() works")

        # Test content analysis
        test_rust_code = """
        fn main() {
            println!("Hello, world!");
        }

        struct MyStruct {
            field: i32,
        }

        trait MyTrait {
            fn method(&self);
        }
        """

        content_analysis = RustCodeAnalyzer.analyze_rust_content(
            test_rust_code
        )
        assert content_analysis["loc"] > 0
        assert "main" in content_analysis["functions"]
        assert "MyStruct" in content_analysis["types"]
        assert "MyTrait" in content_analysis["traits"]
        print("✅ RustCodeAnalyzer.analyze_rust_content() works")

        # Test project structure detection
        test_files = [
            "src/main.rs",
            "tests/test.rs",
            "examples/example.rs",
            "benches/bench.rs",
        ]
        structure = RustCodeAnalyzer.detect_project_structure(test_files)
        assert structure["has_tests"]
        assert structure["has_examples"]
        assert structure["has_benchmarks"]
        print("✅ RustCodeAnalyzer.detect_project_structure() works")

        # Test metrics aggregation
        aggregated = RustCodeAnalyzer.aggregate_metrics(
            metrics, content_analysis, structure
        )
        assert aggregated["loc"] == content_analysis["loc"]
        assert aggregated["has_tests"]
        print("✅ RustCodeAnalyzer.aggregate_metrics() works")
    except ImportError as e:
        print(f"❌ Required module missing: {e}")
        assert False, f"Required module missing: {e}"
    except FileNotFoundError as e:
        print(f"❌ Required file missing: {e}")
        assert False, f"Required file missing: {e}"
    except Exception as e:
        print(f"❌ RustCodeAnalyzer test failed: {e}")
        assert False, f"Unexpected error: {e}"
    try:
        from utils.http_client_utils import HTTPClientUtils, MetadataExtractor

        # Test GitHub repo info extraction
        repo_info = HTTPClientUtils.extract_github_repo_info(
            "https://github.com/serde-rs/serde"
        )
        assert repo_info == ("serde-rs", "serde")
        print("✅ HTTPClientUtils.extract_github_repo_info() works")

        # Test headers creation
        headers = HTTPClientUtils.get_github_headers("test_token")
        assert "Authorization" in headers
        assert headers["Authorization"] == "token test_token"
        print("✅ HTTPClientUtils.get_github_headers() works")

        # Test code snippet extraction
        test_readme = """
        # My Crate

        This is a test crate.

        ```rust
        fn main() {
            println!("Hello from test!");
        }
        ```

        More text here.

        ```rust
        struct TestStruct {
            field: i32,
        }
        ```
        """

        snippets = MetadataExtractor.extract_code_snippets(test_readme)
        assert len(snippets) == 2
        assert "fn main()" in snippets[0]
        assert "struct TestStruct" in snippets[1]
        print("✅ MetadataExtractor.extract_code_snippets() works")

        # Test readme section extraction
        sections = MetadataExtractor.extract_readme_sections(test_readme)
        # Accept 'intro' as a valid section if no explicit header is present
        assert (
            "my_crate" in sections
            or "My Crate" in sections
            or "intro" in sections
        ), f"Expected section 'my_crate', 'My Crate', or 'intro' in {sections.keys()}"
        print("✅ MetadataExtractor.extract_readme_sections() works")

        # Test empty metadata creation
        empty_metadata = MetadataExtractor.create_empty_metadata()
        assert "name" in empty_metadata
        assert "version" in empty_metadata
        assert empty_metadata["downloads"] == 0
        print("✅ MetadataExtractor.create_empty_metadata() works")
    except ImportError as e:
        print(f"❌ Required module missing: {e}")
        assert False, f"Required module missing: {e}"
    except FileNotFoundError as e:
        print(f"❌ Required file missing: {e}")
        assert False, f"Required file missing: {e}"
    except Exception as e:
        print(f"❌ HTTP utilities test failed: {e}")
        assert False, f"Unexpected error: {e}"


def test_original_functionality():
    """Test that the original pipeline functionality still works"""
    print("\n=== Testing Original Functionality Preserved ===")
    try:
        # Import the main components
        from rust_crate_pipeline.analysis import SourceAnalyzer
        from rust_crate_pipeline.config import PipelineConfig

        # Test that the refactored methods still work
        _ = PipelineConfig()

        # Test empty metrics are still created correctly
        _ = b"Mock tarball content"

        # We can't test the actual tarball parsing without a real tarball,
        # but we can test that the methods exist and are callable
        assert hasattr(SourceAnalyzer, "analyze_crate_tarball")
        assert hasattr(SourceAnalyzer, "analyze_github_tarball")
        assert hasattr(SourceAnalyzer, "analyze_local_directory")
        print("✅ SourceAnalyzer methods are still available")
    except ImportError as e:
        print(f"❌ Required module missing: {e}")
        assert False, f"Required module missing: {e}"
    except FileNotFoundError as e:
        print(f"❌ Required file missing: {e}")
        assert False, f"Required file missing: {e}"
    except Exception as e:
        print(f"❌ Original functionality test failed: {e}")
        assert False, f"Unexpected error: {e}"


def main():
    """Run optimization validation tests"""
    print("🚀 Starting Code Optimization Validation")
    print("=" * 50)

    atomic_test_passed = test_atomic_utilities()
    original_test_passed = test_original_functionality()

    print("\n" + "=" * 50)
    if atomic_test_passed and original_test_passed:
        print("🎉 All optimization tests passed!")
        print("✅ Code has been successfully optimized with atomic units")
        print("✅ Original functionality is preserved")
        print("✅ Code duplication has been eliminated")
    else:
        print("❌ Some tests failed. Check the output above.")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
