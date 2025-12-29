"""
Property-based tests using Hypothesis.

Tests invariants and properties that should hold for all inputs,
helping find edge cases that traditional tests might miss.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
"""

import pytest

# Try to import hypothesis, skip tests if not available
try:
    from hypothesis import assume, given, settings
    from hypothesis import strategies as st

    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False

    # Create dummy decorators for when hypothesis is not installed
    def given(*args, **kwargs):  # type: ignore[no-redef]
        def decorator(func):  # type: ignore[no-untyped-def]
            return pytest.mark.skip(reason="hypothesis not installed")(func)

        return decorator

    def settings(*args, **kwargs):  # type: ignore[no-redef]
        def decorator(func):  # type: ignore[no-untyped-def]
            return func

        return decorator

    class st:  # type: ignore[no-redef]
        @staticmethod
        def text(*args, **kwargs):  # type: ignore[no-untyped-def]
            return None

        @staticmethod
        def lists(*args, **kwargs):  # type: ignore[no-untyped-def]
            return None

        @staticmethod
        def integers(*args, **kwargs):  # type: ignore[no-untyped-def]
            return None

        @staticmethod
        def floats(*args, **kwargs):  # type: ignore[no-untyped-def]
            return None

        @staticmethod
        def booleans():  # type: ignore[no-untyped-def]
            return None

        @staticmethod
        def dictionaries(*args, **kwargs):  # type: ignore[no-untyped-def]
            return None

    def assume(condition):  # type: ignore[no-redef]
        pass


from sigil_pipeline.config import PipelineConfig
from sigil_pipeline.filter import (
    has_doc_comments,
    looks_like_test,
    meets_size_sanity_criteria,
)


@pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
class TestFilterProperties:
    """Property-based tests for filter functions."""

    @given(st.text(min_size=0, max_size=10000))
    @settings(max_examples=200)
    def test_meets_size_sanity_criteria_never_crashes(self, content: str) -> None:
        """Filter should never crash on any input string."""
        config = PipelineConfig()
        # Should not raise any exception
        result = meets_size_sanity_criteria("test.rs", content, config)
        assert isinstance(result, bool)

    @given(st.text(min_size=0, max_size=1000))
    @settings(max_examples=100)
    def test_filter_is_deterministic(self, content: str) -> None:
        """Same input should always produce same output."""
        config = PipelineConfig()
        result1 = meets_size_sanity_criteria("test.rs", content, config)
        result2 = meets_size_sanity_criteria("test.rs", content, config)
        assert result1 == result2

    @given(st.text(min_size=0, max_size=1000))
    @settings(max_examples=100)
    def test_has_doc_comments_never_crashes(self, content: str) -> None:
        """has_doc_comments should never crash on any input."""
        result = has_doc_comments(content)
        assert isinstance(result, bool)

    @given(st.text(min_size=0, max_size=1000), st.text(min_size=0, max_size=1000))
    @settings(max_examples=100)
    def test_looks_like_test_never_crashes(self, file_path: str, content: str) -> None:
        """looks_like_test should never crash on any input."""
        result = looks_like_test(file_path, content)
        assert isinstance(result, bool)

    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=50)
    def test_doc_comments_detected_correctly(self, prefix: str) -> None:
        """Content with /// or //! should be detected as having doc comments."""
        # If content contains doc comment markers, should return True
        content_with_triple = f"{prefix}/// This is a doc comment\n{prefix}"
        assert has_doc_comments(content_with_triple) is True

        content_with_inner = f"{prefix}//! This is an inner doc comment\n{prefix}"
        assert has_doc_comments(content_with_inner) is True


@pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
class TestConfigProperties:
    """Property-based tests for configuration."""

    @given(
        st.integers(min_value=1, max_value=100),
        st.integers(min_value=0, max_value=1000),
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    )
    @settings(max_examples=50)
    def test_config_accepts_valid_values(
        self,
        max_threads: int,
        max_clippy_warnings: int,
        min_alphabetic_ratio: float,
    ) -> None:
        """Config should accept any reasonable values."""
        config = PipelineConfig(
            max_threads=max_threads,
            max_clippy_warnings=max_clippy_warnings,
            min_alphabetic_ratio=min_alphabetic_ratio,
        )
        assert config.max_threads == max_threads
        assert config.max_clippy_warnings == max_clippy_warnings
        assert config.min_alphabetic_ratio == min_alphabetic_ratio

    @given(st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=20))
    @settings(max_examples=30)
    def test_config_to_dict_roundtrip(self, crates: list[str]) -> None:
        """Config should survive to_dict conversion."""
        config = PipelineConfig(crates=crates)
        config_dict = config.to_dict()
        assert "crates" in config_dict
        assert config_dict["crates"] == crates


@pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
class TestMetricsProperties:
    """Property-based tests for metrics collection."""

    @given(
        st.text(min_size=1, max_size=50),
        st.floats(min_value=0.0, max_value=1e10, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_counter_increment_is_monotonic(self, name: str, value: float) -> None:
        """Counter increments should always increase the value."""
        from sigil_pipeline.observability import MetricsCollector

        collector = MetricsCollector()
        assume(value >= 0)  # Counters should only be incremented positively

        initial = collector.get_counter(name)
        collector.increment(name, value)
        after = collector.get_counter(name)

        assert after >= initial
        assert after == initial + value

    @given(
        st.text(min_size=1, max_size=50),
        st.floats(
            min_value=-1e10, max_value=1e10, allow_nan=False, allow_infinity=False
        ),
    )
    @settings(max_examples=100)
    def test_gauge_set_is_exact(self, name: str, value: float) -> None:
        """Gauge sets should store the exact value."""
        from sigil_pipeline.observability import MetricsCollector

        collector = MetricsCollector()
        collector.gauge(name, value)

        assert collector.get_gauge(name) == value

    @given(
        st.text(min_size=1, max_size=50),
        st.lists(
            st.floats(
                min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False
            ),
            min_size=1,
            max_size=100,
        ),
    )
    @settings(max_examples=50)
    def test_histogram_stats_are_correct(self, name: str, values: list[float]) -> None:
        """Histogram statistics should be mathematically correct."""
        from sigil_pipeline.observability import MetricsCollector

        collector = MetricsCollector()

        for v in values:
            collector.histogram(name, v)

        stats = collector.get_histogram_stats(name)

        assert stats["count"] == len(values)
        assert abs(stats["sum"] - sum(values)) < 1e-6
        assert stats["min"] == min(values)
        assert stats["max"] == max(values)
        expected_avg = sum(values) / len(values)
        assert abs(stats["avg"] - expected_avg) < 1e-6


@pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
class TestLicenseProperties:
    """Property-based tests for license checking."""

    @given(st.text(min_size=0, max_size=100))
    @settings(max_examples=100)
    def test_license_check_never_crashes(self, license_str: str) -> None:
        """License checking should never crash on any input."""
        from sigil_pipeline.utils import check_license_compliance

        allowed = ["MIT", "Apache-2.0", "BSD-3-Clause"]
        # Should not raise any exception
        result = check_license_compliance(license_str, allowed)
        assert isinstance(result, bool)

    @given(
        st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=10),
        st.text(min_size=1, max_size=20),
    )
    @settings(max_examples=50)
    def test_exact_match_always_works(
        self, allowed: list[str], license_to_check: str
    ) -> None:
        """If license is in allowed list, it should always pass."""
        from sigil_pipeline.utils import check_license_compliance

        # Add the license to the allowed list
        allowed_with_license = allowed + [license_to_check]

        # Should always return True when license is in list
        result = check_license_compliance(license_to_check, allowed_with_license)
        assert result is True


@pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
class TestChunkerProperties:
    """Property-based tests for code chunking."""

    @given(st.text(min_size=0, max_size=5000))
    @settings(max_examples=50)
    def test_chunker_never_crashes(self, code: str) -> None:
        """Chunker should never crash on any input."""
        from sigil_pipeline.chunker import chunk_rust_file

        # Should not raise any exception
        result = chunk_rust_file(code, max_lines=200, max_chars=8000)
        assert isinstance(result, list)

    @given(
        st.integers(min_value=1, max_value=1000),
        st.integers(min_value=100, max_value=50000),
    )
    @settings(max_examples=30)
    def test_chunk_size_limits_respected(self, max_lines: int, max_chars: int) -> None:
        """Chunk size limits should be respected."""
        from sigil_pipeline.chunker import chunk_rust_file

        # Create some sample Rust code
        code = """
/// A test function
pub fn test_function() {
    println!("Hello, world!");
}

/// Another function
fn another_function() -> i32 {
    42
}
"""
        result = chunk_rust_file(code, max_lines=max_lines, max_chars=max_chars)

        for chunk in result:
            chunk_code = chunk["code"]
            chunk_lines = chunk_code.count("\n") + 1

            # Each chunk should respect the limits
            assert len(chunk_code) <= max_chars
            assert chunk_lines <= max_lines


@pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="hypothesis not installed")
class TestDatasetBuilderProperties:
    """Property-based tests for dataset building."""

    @given(st.text(min_size=1, max_size=2000))
    @settings(max_examples=50)
    def test_prompt_generation_never_crashes(self, code: str) -> None:
        """Prompt generation should never crash on any input."""
        from sigil_pipeline.ast_patterns import (
            detect_code_patterns_ast,
            extract_function_signature,
        )
        from sigil_pipeline.prompt_templates import build_async_prompt, build_combined_prompt

        # Should not raise any exception
        sig = extract_function_signature(code)
        fn_name = sig.name if sig else None
        return_type = sig.return_type if sig else None
        patterns = detect_code_patterns_ast(code)
        prompt = build_combined_prompt(
            fn_name=fn_name,
            params_str=None,
            return_type=return_type,
            patterns=patterns,
        )
        assert isinstance(prompt, str)
        assert len(prompt) > 0

        async_prompt, _ = build_async_prompt(
            fn_name=fn_name,
            patterns=patterns,
            code=code,
        )
        assert isinstance(async_prompt, str)
        assert len(async_prompt) > 0

    @given(st.text(min_size=1, max_size=2000))
    @settings(max_examples=50)
    def test_code_formatting_never_crashes(self, code: str) -> None:
        """Static analysis should never crash on any input."""
        from sigil_pipeline.filter import static_analysis_rust_code

        # Should not raise any exception
        is_valid, message = static_analysis_rust_code(code)
        assert isinstance(is_valid, bool)
        assert isinstance(message, str)

    @given(st.text(min_size=1, max_size=1000))
    @settings(max_examples=30)
    def test_pattern_detection_never_crashes(self, code: str) -> None:
        """Pattern detection should never crash on any input."""
        from sigil_pipeline.ast_patterns import detect_code_patterns_ast

        # Should not raise any exception
        patterns = detect_code_patterns_ast(code)
        assert isinstance(patterns, dict)
        # Should always have expected keys
        assert "has_main" in patterns
        assert "has_async" in patterns
        assert "has_error_handling" in patterns
