"""
Performance benchmarks for the Sigil Pipeline.

Run with:
    python -m pytest benches/benchmark_pipeline.py -v --benchmark-enable

Requires pytest-benchmark:
    pip install pytest-benchmark

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.6.0
"""

import json
from pathlib import Path

import pytest

# Try to import benchmark plugin
try:
    import pytest_benchmark

    BENCHMARK_AVAILABLE = True
except ImportError:
    BENCHMARK_AVAILABLE = False


# Skip all benchmarks if pytest-benchmark not installed
pytestmark = pytest.mark.skipif(
    not BENCHMARK_AVAILABLE,
    reason="pytest-benchmark not installed",
)


class BenchmarkFixtures:
    """Shared fixtures for benchmarks."""

    @staticmethod
    def create_sample_rust_code(num_functions: int = 10) -> str:
        """Generate sample Rust code with multiple functions."""
        functions = []
        for i in range(num_functions):
            functions.append(
                f"""
/// Function {i} that does something useful.
///
/// # Examples
///
/// ```
/// let result = function_{i}();
/// assert!(result > 0);
/// ```
pub fn function_{i}(x: i32, y: i32) -> i32 {{
    let mut result = 0;
    for j in 0..x {{
        result += j * y;
    }}
    result
}}
"""
            )
        return "\n".join(functions)

    @staticmethod
    def create_sample_crate(tmp_path: Path, num_files: int = 5) -> Path:
        """Create a sample crate directory with multiple files."""
        crate_dir = tmp_path / "test_crate"
        src_dir = crate_dir / "src"
        src_dir.mkdir(parents=True)

        # Create Cargo.toml
        (crate_dir / "Cargo.toml").write_text(
            """
[package]
name = "test_crate"
version = "2.0.0"
edition = "2021"

[dependencies]
serde = "1.0"
"""
        )

        # Create lib.rs
        (src_dir / "lib.rs").write_text(BenchmarkFixtures.create_sample_rust_code(10))

        # Create additional files
        for i in range(num_files - 1):
            (src_dir / f"module_{i}.rs").write_text(
                BenchmarkFixtures.create_sample_rust_code(5)
            )

        return crate_dir


@pytest.fixture
def sample_rust_code() -> str:
    """Generate sample Rust code for benchmarks."""
    return BenchmarkFixtures.create_sample_rust_code(20)


@pytest.fixture
def sample_crate(tmp_path: Path) -> Path:
    """Create a sample crate directory."""
    return BenchmarkFixtures.create_sample_crate(tmp_path)


class TestFilterBenchmarks:
    """Benchmarks for filter module functions."""

    def test_benchmark_has_doc_comments(
        self,
        benchmark: "pytest_benchmark.fixture.BenchmarkFixture",
        sample_rust_code: str,
    ) -> None:
        """Benchmark doc comment detection."""
        from sigil_pipeline.filter import has_doc_comments

        result = benchmark(has_doc_comments, sample_rust_code)
        assert result is True

    def test_benchmark_meets_size_sanity_criteria(
        self,
        benchmark: "pytest_benchmark.fixture.BenchmarkFixture",
        sample_rust_code: str,
    ) -> None:
        """Benchmark size sanity filtering."""
        from sigil_pipeline.config import PipelineConfig
        from sigil_pipeline.filter import meets_size_sanity_criteria

        config = PipelineConfig()
        result = benchmark(
            meets_size_sanity_criteria, "test.rs", sample_rust_code, config
        )
        assert isinstance(result, bool)

    def test_benchmark_looks_like_test(
        self,
        benchmark: "pytest_benchmark.fixture.BenchmarkFixture",
        sample_rust_code: str,
    ) -> None:
        """Benchmark test file detection."""
        from sigil_pipeline.filter import looks_like_test

        result = benchmark(looks_like_test, "src/lib.rs", sample_rust_code)
        assert result is False


class TestChunkerBenchmarks:
    """Benchmarks for chunker module functions."""

    def test_benchmark_chunk_rust_file_small(
        self, benchmark: "pytest_benchmark.fixture.BenchmarkFixture"
    ) -> None:
        """Benchmark chunking a small Rust file."""
        from sigil_pipeline.chunker import chunk_rust_file

        code = BenchmarkFixtures.create_sample_rust_code(5)
        result = benchmark(chunk_rust_file, code, max_lines=200, max_chars=8000)
        assert len(result) > 0

    def test_benchmark_chunk_rust_file_large(
        self, benchmark: "pytest_benchmark.fixture.BenchmarkFixture"
    ) -> None:
        """Benchmark chunking a large Rust file."""
        from sigil_pipeline.chunker import chunk_rust_file

        code = BenchmarkFixtures.create_sample_rust_code(50)
        result = benchmark(chunk_rust_file, code, max_lines=200, max_chars=8000)
        assert len(result) > 0


class TestDatasetBuilderBenchmarks:
    """Benchmarks for dataset builder functions."""

    def test_benchmark_create_prompt_from_code(
        self,
        benchmark: "pytest_benchmark.fixture.BenchmarkFixture",
        sample_rust_code: str,
    ) -> None:
        """Benchmark prompt generation."""
        from sigil_pipeline.dataset_builder import create_prompt_from_code

        result = benchmark(create_prompt_from_code, sample_rust_code)
        assert len(result) > 0

    def test_benchmark_extract_description(
        self,
        benchmark: "pytest_benchmark.fixture.BenchmarkFixture",
        sample_rust_code: str,
    ) -> None:
        """Benchmark doc comment extraction."""
        from sigil_pipeline.dataset_builder import extract_description_from_docs

        result = benchmark(extract_description_from_docs, sample_rust_code)
        # May or may not find description depending on code structure
        assert result is None or isinstance(result, str)


class TestMetricsBenchmarks:
    """Benchmarks for metrics collection."""

    def test_benchmark_counter_increment(
        self, benchmark: "pytest_benchmark.fixture.BenchmarkFixture"
    ) -> None:
        """Benchmark counter increment operations."""
        from sigil_pipeline.observability import MetricsCollector

        collector = MetricsCollector()

        def increment_many() -> None:
            for _ in range(1000):
                collector.increment("test_counter")

        benchmark(increment_many)
        assert collector.get_counter("test_counter") >= 1000

    def test_benchmark_histogram_record(
        self, benchmark: "pytest_benchmark.fixture.BenchmarkFixture"
    ) -> None:
        """Benchmark histogram recording."""
        from sigil_pipeline.observability import MetricsCollector

        collector = MetricsCollector()

        def record_many() -> None:
            for i in range(1000):
                collector.histogram("test_histogram", float(i) / 100.0)

        benchmark(record_many)
        stats = collector.get_histogram_stats("test_histogram")
        assert stats["count"] >= 1000

    def test_benchmark_prometheus_export(
        self, benchmark: "pytest_benchmark.fixture.BenchmarkFixture"
    ) -> None:
        """Benchmark Prometheus format export."""
        from sigil_pipeline.observability import MetricsCollector

        collector = MetricsCollector()

        # Pre-populate with metrics
        for i in range(100):
            collector.increment(f"counter_{i}")
            collector.gauge(f"gauge_{i}", float(i))
            collector.histogram(f"histogram_{i}", float(i))

        result = benchmark(collector.export_prometheus)
        assert len(result) > 0


class TestConfigBenchmarks:
    """Benchmarks for configuration operations."""

    def test_benchmark_config_to_dict(
        self, benchmark: "pytest_benchmark.fixture.BenchmarkFixture"
    ) -> None:
        """Benchmark config serialization."""
        from sigil_pipeline.config import PipelineConfig

        config = PipelineConfig(
            crates=["serde", "tokio", "actix-web", "diesel", "rocket"],
            allowed_licenses=["MIT", "Apache-2.0", "BSD-3-Clause"],
        )

        result = benchmark(config.to_dict)
        assert "crates" in result

    def test_benchmark_config_hash(
        self, benchmark: "pytest_benchmark.fixture.BenchmarkFixture"
    ) -> None:
        """Benchmark config hashing for checkpointing."""
        from sigil_pipeline.config import PipelineConfig

        config = PipelineConfig(
            crates=["serde", "tokio"],
        )

        result = benchmark(config.config_hash)
        assert len(result) > 0


class TestJSONLBenchmarks:
    """Benchmarks for JSONL operations."""

    def test_benchmark_jsonl_write(
        self, benchmark: "pytest_benchmark.fixture.BenchmarkFixture", tmp_path: Path
    ) -> None:
        """Benchmark JSONL writing."""
        output_path = tmp_path / "output.jsonl"

        samples = [
            {"prompt": f"Write function {i}", "gen": f"fn func_{i}() {{}}"}
            for i in range(100)
        ]

        def write_samples() -> None:
            with open(output_path, "w", encoding="utf-8") as f:
                for sample in samples:
                    f.write(json.dumps(sample) + "\n")

        benchmark(write_samples)
        assert output_path.exists()

    def test_benchmark_jsonl_read(
        self, benchmark: "pytest_benchmark.fixture.BenchmarkFixture", tmp_path: Path
    ) -> None:
        """Benchmark JSONL reading."""
        output_path = tmp_path / "output.jsonl"

        # Pre-create file
        with open(output_path, "w", encoding="utf-8") as f:
            for i in range(100):
                f.write(json.dumps({"prompt": f"p{i}", "gen": f"g{i}"}) + "\n")

        def read_samples() -> list[dict[str, str]]:
            samples = []
            with open(output_path, "r", encoding="utf-8") as f:
                for line in f:
                    samples.append(json.loads(line))
            return samples

        result = benchmark(read_samples)
        assert len(result) == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--benchmark-enable"])
