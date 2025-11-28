"""
Load testing suite for Sigil Pipeline.

Run with:
    locust -f tests/load/locustfile.py --headless -u 10 -r 1 -t 60s

Requires locust:
    pip install locust

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
"""

import json
import random
import tempfile
import time
from pathlib import Path

# Try to import locust, provide stub if not available
try:
    from locust import User, between, events, task

    LOCUST_AVAILABLE = True
except ImportError:
    LOCUST_AVAILABLE = False

    # Stub classes for when locust is not installed
    class User:  # type: ignore[no-redef]
        """Stub User class."""

        wait_time = None

    def task(weight: int = 1):  # type: ignore[no-redef]
        """Stub task decorator."""

        def decorator(func):  # type: ignore[no-untyped-def]
            return func

        return decorator

    def between(min_wait: float, max_wait: float):  # type: ignore[no-redef]
        """Stub between function."""
        return None


if LOCUST_AVAILABLE:

    class PipelineComponentUser(User):
        """
        Load test user for pipeline components.

        Tests various pipeline components under load without making
        actual network requests to crates.io.
        """

        wait_time = between(0.1, 0.5)

        def on_start(self) -> None:
            """Set up test fixtures."""
            self.temp_dir = Path(tempfile.mkdtemp())
            self._create_sample_data()

        def on_stop(self) -> None:
            """Clean up test fixtures."""
            import shutil

            if hasattr(self, "temp_dir") and self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)

        def _create_sample_data(self) -> None:
            """Create sample Rust code files for testing."""
            self.sample_codes = []
            for i in range(10):
                code = f"""
/// Function {i} documentation
///
/// # Examples
///
/// ```
/// let x = function_{i}(1, 2);
/// ```
pub fn function_{i}(a: i32, b: i32) -> i32 {{
    let mut result = 0;
    for j in 0..a {{
        result += j * b;
    }}
    result
}}

impl SomeStruct {{
    /// Method documentation
    pub fn method_{i}(&self) -> String {{
        format!("Method {i}")
    }}
}}
"""
                self.sample_codes.append(code)

        @task(10)
        def test_filter_size_sanity(self) -> None:
            """Load test size sanity filtering."""
            from sigil_pipeline.config import PipelineConfig
            from sigil_pipeline.filter import meets_size_sanity_criteria

            code = random.choice(self.sample_codes)
            config = PipelineConfig()

            start_time = time.perf_counter()
            try:
                _ = meets_size_sanity_criteria("test.rs", code, config)
                duration = time.perf_counter() - start_time

                events.request.fire(
                    request_type="FILTER",
                    name="size_sanity",
                    response_time=duration * 1000,
                    response_length=len(code),
                    exception=None,
                    context=None,
                )
            except Exception as e:
                duration = time.perf_counter() - start_time
                events.request.fire(
                    request_type="FILTER",
                    name="size_sanity",
                    response_time=duration * 1000,
                    response_length=0,
                    exception=e,
                    context=None,
                )

        @task(10)
        def test_filter_doc_comments(self) -> None:
            """Load test doc comment detection."""
            from sigil_pipeline.filter import has_doc_comments

            code = random.choice(self.sample_codes)

            start_time = time.perf_counter()
            try:
                _ = has_doc_comments(code)
                duration = time.perf_counter() - start_time

                events.request.fire(
                    request_type="FILTER",
                    name="doc_comments",
                    response_time=duration * 1000,
                    response_length=len(code),
                    exception=None,
                    context=None,
                )
            except Exception as e:
                duration = time.perf_counter() - start_time
                events.request.fire(
                    request_type="FILTER",
                    name="doc_comments",
                    response_time=duration * 1000,
                    response_length=0,
                    exception=e,
                    context=None,
                )

        @task(5)
        def test_chunker(self) -> None:
            """Load test semantic chunking."""
            from sigil_pipeline.chunker import chunk_rust_file

            code = random.choice(self.sample_codes)

            start_time = time.perf_counter()
            try:
                chunks = chunk_rust_file(code, max_lines=200, max_chars=8000)
                duration = time.perf_counter() - start_time

                events.request.fire(
                    request_type="CHUNKER",
                    name="chunk_file",
                    response_time=duration * 1000,
                    response_length=len(chunks),
                    exception=None,
                    context=None,
                )
            except Exception as e:
                duration = time.perf_counter() - start_time
                events.request.fire(
                    request_type="CHUNKER",
                    name="chunk_file",
                    response_time=duration * 1000,
                    response_length=0,
                    exception=e,
                    context=None,
                )

        @task(5)
        def test_prompt_generation(self) -> None:
            """Load test prompt generation."""
            from sigil_pipeline.dataset_builder import create_prompt_from_code

            code = random.choice(self.sample_codes)

            start_time = time.perf_counter()
            try:
                prompt = create_prompt_from_code(code)
                duration = time.perf_counter() - start_time

                events.request.fire(
                    request_type="BUILDER",
                    name="create_prompt",
                    response_time=duration * 1000,
                    response_length=len(prompt),
                    exception=None,
                    context=None,
                )
            except Exception as e:
                duration = time.perf_counter() - start_time
                events.request.fire(
                    request_type="BUILDER",
                    name="create_prompt",
                    response_time=duration * 1000,
                    response_length=0,
                    exception=e,
                    context=None,
                )

        @task(3)
        def test_metrics_collection(self) -> None:
            """Load test metrics collection."""
            from sigil_pipeline.observability import MetricsCollector

            collector = MetricsCollector()

            start_time = time.perf_counter()
            try:
                # Simulate typical metrics operations
                for _ in range(100):
                    collector.increment("test_counter")
                    collector.gauge("test_gauge", random.random())
                    collector.histogram("test_histogram", random.random())

                output = collector.export_prometheus()
                duration = time.perf_counter() - start_time

                events.request.fire(
                    request_type="METRICS",
                    name="collect_and_export",
                    response_time=duration * 1000,
                    response_length=len(output),
                    exception=None,
                    context=None,
                )
            except Exception as e:
                duration = time.perf_counter() - start_time
                events.request.fire(
                    request_type="METRICS",
                    name="collect_and_export",
                    response_time=duration * 1000,
                    response_length=0,
                    exception=e,
                    context=None,
                )

        @task(2)
        def test_jsonl_write(self) -> None:
            """Load test JSONL writing."""
            output_path = self.temp_dir / f"test_{random.randint(0, 1000)}.jsonl"

            samples = [
                {"prompt": f"Prompt {i}", "gen": random.choice(self.sample_codes)}
                for i in range(50)
            ]

            start_time = time.perf_counter()
            try:
                with open(output_path, "w", encoding="utf-8") as f:
                    for sample in samples:
                        f.write(json.dumps(sample) + "\n")
                duration = time.perf_counter() - start_time

                events.request.fire(
                    request_type="EXPORTER",
                    name="jsonl_write",
                    response_time=duration * 1000,
                    response_length=len(samples),
                    exception=None,
                    context=None,
                )

                # Clean up
                output_path.unlink()
            except Exception as e:
                duration = time.perf_counter() - start_time
                events.request.fire(
                    request_type="EXPORTER",
                    name="jsonl_write",
                    response_time=duration * 1000,
                    response_length=0,
                    exception=e,
                    context=None,
                )


# Quick test function for running without locust
def run_quick_test() -> None:
    """Run a quick local test of load test components."""
    print("Running quick load test validation...")

    from sigil_pipeline.chunker import chunk_rust_file
    from sigil_pipeline.config import PipelineConfig
    from sigil_pipeline.dataset_builder import create_prompt_from_code
    from sigil_pipeline.filter import has_doc_comments, meets_size_sanity_criteria
    from sigil_pipeline.observability import MetricsCollector

    sample_code = """
/// A sample function
pub fn sample() -> i32 {
    42
}
"""

    config = PipelineConfig()

    # Test each component
    assert meets_size_sanity_criteria("test.rs", sample_code, config)
    print("✓ size_sanity filter works")

    assert has_doc_comments(sample_code)
    print("✓ doc_comments filter works")

    chunks = chunk_rust_file(sample_code, 200, 8000)
    assert len(chunks) > 0
    print("✓ chunker works")

    prompt = create_prompt_from_code(sample_code)
    assert len(prompt) > 0
    print("✓ prompt generation works")

    collector = MetricsCollector()
    collector.increment("test")
    assert collector.get_counter("test") == 1
    print("✓ metrics collection works")

    print("\nAll load test components validated successfully!")


if __name__ == "__main__":
    run_quick_test()
