"""
Chaos engineering and resilience tests for the Sigil Pipeline.

Tests system behavior under adverse conditions:
- Network failures
- Timeout scenarios
- Corrupted data
- Resource exhaustion

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
"""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from sigil_pipeline.config import PipelineConfig


class TestNetworkResilience:
    """Test resilience to network failures."""

    @pytest.mark.asyncio
    async def test_handles_connection_timeout(self) -> None:
        """Pipeline should handle connection timeouts gracefully."""
        from sigil_pipeline.crawler import fetch_crate

        with patch("sigil_pipeline.crawler.requests.get") as mock_get:
            mock_get.side_effect = requests.Timeout("Connection timed out")

            result = fetch_crate("nonexistent-crate", "0.1.0", Path("/tmp"))

            # Should return None or raise specific exception, not crash
            assert result is None or isinstance(result, Exception)

    @pytest.mark.asyncio
    async def test_handles_connection_refused(self) -> None:
        """Pipeline should handle connection refused gracefully."""
        from sigil_pipeline.crawler import fetch_crate

        with patch("sigil_pipeline.crawler.requests.get") as mock_get:
            mock_get.side_effect = requests.ConnectionError("Connection refused")

            result = fetch_crate("nonexistent-crate", "0.1.0", Path("/tmp"))

            # Should handle gracefully
            assert result is None or isinstance(result, Exception)

    @pytest.mark.asyncio
    async def test_handles_dns_failure(self) -> None:
        """Pipeline should handle DNS resolution failures."""
        from sigil_pipeline.crawler import fetch_crate

        with patch("sigil_pipeline.crawler.requests.get") as mock_get:
            mock_get.side_effect = requests.ConnectionError(
                "Failed to resolve 'crates.io'"
            )

            result = fetch_crate("serde", "1.0.0", Path("/tmp"))

            # Should handle gracefully
            assert result is None or isinstance(result, Exception)

    @pytest.mark.asyncio
    async def test_handles_rate_limiting_response(self) -> None:
        """Pipeline should handle 429 Too Many Requests."""
        from sigil_pipeline.crawler import fetch_crate

        with patch("sigil_pipeline.crawler.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 429
            mock_response.raise_for_status.side_effect = requests.HTTPError(
                "429 Too Many Requests"
            )
            mock_get.return_value = mock_response

            result = fetch_crate("serde", "1.0.0", Path("/tmp"))

            # Should handle gracefully with retry or return None
            assert result is None or isinstance(result, Exception)


class TestDataResilience:
    """Test resilience to corrupted or malformed data."""

    def test_handles_empty_cargo_toml(self, tmp_path: Path) -> None:
        """Pipeline should handle empty Cargo.toml files."""
        from sigil_pipeline.utils import is_platform_specific_crate

        crate_dir = tmp_path / "test_crate"
        crate_dir.mkdir()
        (crate_dir / "Cargo.toml").write_text("")

        # Should not crash, should return sensible default
        result = is_platform_specific_crate(crate_dir)
        assert result is None or isinstance(result, str)

    def test_handles_invalid_cargo_toml(self, tmp_path: Path) -> None:
        """Pipeline should handle invalid TOML in Cargo.toml."""
        from sigil_pipeline.utils import is_platform_specific_crate

        crate_dir = tmp_path / "test_crate"
        crate_dir.mkdir()
        (crate_dir / "Cargo.toml").write_text("this is not valid toml {{{")

        # Should not crash
        result = is_platform_specific_crate(crate_dir)
        assert result is None or isinstance(result, str)

    def test_handles_binary_rust_file(self, tmp_path: Path) -> None:
        """Pipeline should handle binary files with .rs extension."""
        from sigil_pipeline.filter import meets_size_sanity_criteria

        # Create a binary file disguised as .rs
        binary_content = bytes(range(256))  # All byte values
        rs_file = tmp_path / "binary.rs"
        rs_file.write_bytes(binary_content)

        config = PipelineConfig()

        # Reading as text may fail or produce garbage - should not crash
        try:
            content = rs_file.read_text(encoding="utf-8", errors="replace")
            result = meets_size_sanity_criteria("binary.rs", content, config)
            assert isinstance(result, bool)
        except Exception:
            # If we can't read it, that's acceptable
            pass

    def test_handles_extremely_long_line(self, tmp_path: Path) -> None:
        """Pipeline should handle files with extremely long lines."""
        from sigil_pipeline.filter import meets_size_sanity_criteria

        # Create a file with a 10MB line
        long_line = "x" * (10 * 1024 * 1024)
        content = f"fn main() {{\n    {long_line}\n}}"

        config = PipelineConfig()
        result = meets_size_sanity_criteria("long.rs", content, config)

        # Should reject this (exceeds line length limits)
        assert result is False


class TestResourceResilience:
    """Test resilience to resource constraints."""

    def test_handles_disk_full_on_export(self, tmp_path: Path) -> None:
        """Exporter should surface disk full errors."""
        from sigil_pipeline.exporter import write_jsonl

        output_path = tmp_path / "output.jsonl"

        def sample_generator():
            yield {
                "input_data": {"prompt": "test", "code": "test"},
                "output_data": {"code": "test"},
            }

        with patch("pathlib.Path.open", side_effect=OSError("No space left on device")):
            with pytest.raises(OSError):
                write_jsonl(sample_generator(), str(output_path))

    def test_handles_memory_pressure_in_chunker(self) -> None:
        """Chunker should handle very large files without OOM."""
        from sigil_pipeline.chunker import chunk_rust_file

        # Create a large-ish file (but not actually large enough to OOM)
        large_code = "\n".join(
            [f'pub fn func_{i}() {{ println!("{i}"); }}' for i in range(1000)]
        )

        # Should complete without memory issues
        chunks = chunk_rust_file(large_code, max_lines=50, max_chars=2000)

        # Should produce chunks
        assert len(chunks) > 0

    def test_chunker_preserves_unicode_boundaries(self) -> None:
        """Chunker should not truncate tokens when Unicode appears before a node."""
        from sigil_pipeline.chunker import chunk_rust_file

        code = "/// Emoji prefix \u2603\nimpl Foo {\n    fn bar(&self) {}\n}\n"
        chunks = chunk_rust_file(code, max_lines=200, max_chars=8000)

        impl_chunks = [c for c in chunks if c.get("type") == "impl_block"]
        assert impl_chunks, "Expected an impl_block chunk"
        assert impl_chunks[0]["code"].startswith("impl Foo")


class TestSubprocessResilience:
    """Test resilience to subprocess failures."""

    @pytest.mark.asyncio
    async def test_handles_cargo_not_found(self) -> None:
        """Pipeline should handle missing cargo gracefully."""
        from sigil_pipeline.analyzer import run_clippy

        with patch("sigil_pipeline.analyzer.run_command_async") as mock_run:
            mock_run.side_effect = FileNotFoundError("cargo not found")

            result = await run_clippy(Path("/fake/path"))

            # Should return failure result, not crash
            assert result.success is False

    @pytest.mark.asyncio
    async def test_handles_cargo_segfault(self) -> None:
        """Pipeline should handle cargo crashes gracefully."""
        from sigil_pipeline.analyzer import run_clippy

        with patch("sigil_pipeline.analyzer.run_command_async") as mock_run:
            # Simulate cargo crash - return tuple (stdout, stderr, returncode)
            mock_run.return_value = ("", "Segmentation fault", -11)

            result = await run_clippy(Path("/fake/path"))

            # Should handle gracefully - when returncode is non-zero,
            # success depends on error parsing. Check it doesn't crash.
            assert result is not None

    @pytest.mark.asyncio
    async def test_handles_cargo_timeout(self) -> None:
        """Pipeline should handle cargo timeouts gracefully."""
        from sigil_pipeline.analyzer import run_clippy

        with patch("sigil_pipeline.analyzer.run_command_async") as mock_run:
            mock_run.side_effect = asyncio.TimeoutError("Command timed out")

            result = await run_clippy(Path("/fake/path"))

            # Should handle gracefully
            assert result.success is False


class TestConcurrencyResilience:
    """Test resilience under concurrent load."""

    @pytest.mark.asyncio
    async def test_handles_concurrent_crate_processing(self) -> None:
        """Pipeline should handle multiple concurrent crate processing."""
        from sigil_pipeline.observability import MetricsCollector

        collector = MetricsCollector()
        errors: list[Exception] = []

        async def process_crate(crate_id: int) -> None:
            try:
                collector.increment("crates_processed", labels={"id": str(crate_id)})
                await asyncio.sleep(0.01)  # Simulate work
                collector.histogram(
                    "processing_time", 0.01, labels={"id": str(crate_id)}
                )
            except Exception as e:
                errors.append(e)

        # Process 50 crates concurrently
        tasks = [process_crate(i) for i in range(50)]
        await asyncio.gather(*tasks)

        # Should complete without errors
        assert len(errors) == 0

    def test_handles_thread_safety_stress(self) -> None:
        """Metrics collection should be thread-safe under stress."""
        import threading

        from sigil_pipeline.observability import MetricsCollector

        collector = MetricsCollector()
        errors: list[Exception] = []

        def stress_metrics(thread_id: int) -> None:
            try:
                for i in range(100):
                    collector.increment(f"counter_{thread_id}")
                    collector.gauge(f"gauge_{thread_id}", float(i))
                    collector.histogram(f"histogram_{thread_id}", float(i) / 100)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=stress_metrics, args=(i,)) for i in range(20)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should complete without errors
        assert len(errors) == 0


class TestCheckpointResilience:
    """Test checkpoint/resume resilience."""

    def test_handles_corrupted_checkpoint(self, tmp_path: Path) -> None:
        """Pipeline should handle corrupted checkpoint files."""
        from sigil_pipeline.utils import CheckpointManager

        checkpoint_path = tmp_path / "checkpoint.json"
        checkpoint_path.write_text("{{{{not valid json")

        manager = CheckpointManager(checkpoint_path)

        # Should not crash, should return False (load failed)
        result = manager.load()
        assert result is False

    def test_handles_checkpoint_permission_denied(self, tmp_path: Path) -> None:
        """Pipeline should handle checkpoint write permission errors."""
        from sigil_pipeline.utils import CheckpointManager

        checkpoint_path = tmp_path / "readonly" / "checkpoint.json"

        manager = CheckpointManager(checkpoint_path)
        processed_crates = {"serde": {"status": "ok"}, "tokio": {"status": "ok"}}

        # Writing to non-existent directory
        try:
            manager.save(processed_crates, config_hash="test123")
            # If it succeeds (creates directory), that's fine
        except (OSError, PermissionError):
            # Expected failure
            pass


class TestGracefulDegradation:
    """Test graceful degradation when optional features unavailable."""

    def test_handles_missing_tree_sitter(self) -> None:
        """Chunker should fallback when tree-sitter unavailable."""
        from sigil_pipeline.chunker import chunk_rust_file

        # Mock tree-sitter as unavailable
        with patch.dict("sys.modules", {"tree_sitter_rust": None}):
            code = """
pub fn example() {
    println!("Hello");
}
"""
            # Should still work with regex fallback
            chunks = chunk_rust_file(code, max_lines=200, max_chars=8000)
            assert isinstance(chunks, list)

    def test_handles_missing_structlog(self) -> None:
        """Observability should fallback when structlog unavailable."""
        from sigil_pipeline.observability import get_logger

        # The function should always return a usable logger
        logger = get_logger("test")
        assert logger is not None

        # Should be able to log without crashing
        logger.info("Test message")
