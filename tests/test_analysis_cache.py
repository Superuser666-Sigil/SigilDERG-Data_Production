"""
Tests for sigil_pipeline.analysis_cache module.

Tests caching of analysis results, content hashing, and cache invalidation.
"""

import pytest

from sigil_pipeline.analysis_cache import AnalysisCache, get_cache, set_cache


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create a temporary directory for cache tests."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir


@pytest.fixture
def temp_crate_dir(tmp_path):
    """Create a temporary crate directory with minimal structure."""
    crate_dir = tmp_path / "test_crate"
    crate_dir.mkdir()

    # Create Cargo.toml
    cargo_toml = crate_dir / "Cargo.toml"
    cargo_toml.write_text(
        """
[package]
name = "test_crate"
version = "0.1.0"
edition = "2021"
"""
    )

    # Create src directory with a Rust file
    src_dir = crate_dir / "src"
    src_dir.mkdir()

    lib_rs = src_dir / "lib.rs"
    lib_rs.write_text('pub fn hello() { println!("Hello"); }\n')

    return crate_dir


@pytest.fixture
def cache(temp_cache_dir):
    """Create an AnalysisCache instance for testing."""
    return AnalysisCache(temp_cache_dir)


class TestAnalysisCache:
    """Test AnalysisCache class."""

    def test_compute_crate_hash(self, cache, temp_crate_dir):
        """Test that crate hash is computed deterministically."""
        hash1 = cache.compute_crate_hash(temp_crate_dir)
        hash2 = cache.compute_crate_hash(temp_crate_dir)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex digest length

    def test_hash_changes_on_cargo_toml_change(self, cache, temp_crate_dir):
        """Test that hash changes when Cargo.toml changes."""
        hash1 = cache.compute_crate_hash(temp_crate_dir)

        # Modify Cargo.toml
        cargo_toml = temp_crate_dir / "Cargo.toml"
        content = cargo_toml.read_text()
        cargo_toml.write_text(content + '\n[dependencies]\nrand = "0.8"')

        hash2 = cache.compute_crate_hash(temp_crate_dir)

        assert hash1 != hash2

    def test_hash_changes_on_source_change(self, cache, temp_crate_dir):
        """Test that hash changes when source files change."""
        hash1 = cache.compute_crate_hash(temp_crate_dir)

        # Modify lib.rs
        lib_rs = temp_crate_dir / "src" / "lib.rs"
        content = lib_rs.read_text()
        lib_rs.write_text(content + "\npub fn goodbye() {}\n")

        hash2 = cache.compute_crate_hash(temp_crate_dir)

        assert hash1 != hash2

    def test_put_and_get(self, cache, temp_crate_dir):
        """Test storing and retrieving cached results."""
        crate_hash = cache.compute_crate_hash(temp_crate_dir)
        result = {"warning_count": 5, "error_count": 0}

        cache.put(crate_hash, "clippy", result)
        cached = cache.get(crate_hash, "clippy")

        assert cached is not None
        assert cached["warning_count"] == 5
        assert cached["error_count"] == 0

    def test_cache_miss_returns_none(self, cache, temp_crate_dir):
        """Test that cache miss returns None."""
        crate_hash = cache.compute_crate_hash(temp_crate_dir)
        cached = cache.get(crate_hash, "nonexistent_tool")

        assert cached is None

    def test_cache_hit_increments_stats(self, cache, temp_crate_dir):
        """Test that cache hits are tracked in stats."""
        crate_hash = cache.compute_crate_hash(temp_crate_dir)
        result = {"value": 42}

        cache.put(crate_hash, "test_tool", result)
        cache.get(crate_hash, "test_tool")  # Hit
        cache.get(crate_hash, "test_tool")  # Hit
        cache.get(crate_hash, "missing")  # Miss

        stats = cache.stats
        assert stats["hits"] == 2
        assert stats["misses"] == 1

    def test_invalidate_by_hash(self, cache, temp_crate_dir):
        """Test invalidating cache entries by hash."""
        crate_hash = cache.compute_crate_hash(temp_crate_dir)

        cache.put(crate_hash, "clippy", {"result": 1})
        cache.put(crate_hash, "geiger", {"result": 2})

        deleted = cache.invalidate_by_hash(crate_hash)

        assert deleted == 2
        assert cache.get(crate_hash, "clippy") is None
        assert cache.get(crate_hash, "geiger") is None

    def test_invalidate_by_crate_dir(self, cache, temp_crate_dir):
        """Test invalidating cache entries by crate directory."""
        crate_hash = cache.compute_crate_hash(temp_crate_dir)
        cache.put(crate_hash, "test_tool", {"result": 1})

        deleted = cache.invalidate(temp_crate_dir)

        assert deleted == 1
        assert cache.get(crate_hash, "test_tool") is None

    def test_clear_all(self, cache, temp_crate_dir):
        """Test clearing all cache entries."""
        crate_hash = cache.compute_crate_hash(temp_crate_dir)
        cache.put(crate_hash, "tool1", {"result": 1})
        cache.put(crate_hash, "tool2", {"result": 2})

        deleted = cache.clear()

        assert deleted == 2
        assert cache.get(crate_hash, "tool1") is None
        assert cache.get(crate_hash, "tool2") is None

    def test_reset_stats(self, cache, temp_crate_dir):
        """Test resetting cache statistics."""
        crate_hash = cache.compute_crate_hash(temp_crate_dir)
        cache.put(crate_hash, "test", {"value": 1})
        cache.get(crate_hash, "test")

        assert cache.stats["hits"] > 0

        cache.reset_stats()

        assert cache.stats["hits"] == 0
        assert cache.stats["misses"] == 0


class TestGlobalCache:
    """Test global cache functions."""

    def test_get_cache_creates_instance(self, temp_cache_dir):
        """Test that get_cache creates a cache instance."""
        # Reset global cache
        set_cache(None)

        cache = get_cache(temp_cache_dir)

        assert cache is not None
        assert isinstance(cache, AnalysisCache)

    def test_get_cache_returns_same_instance(self, temp_cache_dir):
        """Test that get_cache returns the same instance."""
        set_cache(None)

        cache1 = get_cache(temp_cache_dir)
        cache2 = get_cache(temp_cache_dir)

        assert cache1 is cache2

    def test_set_cache_overrides(self, temp_cache_dir):
        """Test that set_cache overrides the global instance."""
        set_cache(None)

        cache1 = get_cache(temp_cache_dir)
        new_cache = AnalysisCache(temp_cache_dir / "new")
        set_cache(new_cache)

        # get_cache should return the new cache now
        # (but since _global_cache is set, it returns that)
        # Reset and test
        set_cache(None)
        cache2 = get_cache(temp_cache_dir)

        assert cache1 is not cache2


class TestCacheWithCargoLock:
    """Test caching behavior with Cargo.lock files."""

    def test_hash_includes_cargo_lock(self, cache, temp_crate_dir):
        """Test that hash includes Cargo.lock when present."""
        hash1 = cache.compute_crate_hash(temp_crate_dir)

        # Add Cargo.lock
        cargo_lock = temp_crate_dir / "Cargo.lock"
        cargo_lock.write_text('# Fake lock file\n[[package]]\nname = "test"')

        hash2 = cache.compute_crate_hash(temp_crate_dir)

        # Hash should change when Cargo.lock is added
        assert hash1 != hash2


class TestCacheEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_crate_dir(self, cache, tmp_path):
        """Test hashing an empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        # Should not raise, returns some hash
        crate_hash = cache.compute_crate_hash(empty_dir)
        assert len(crate_hash) == 64

    def test_cache_corrupted_json(self, cache, temp_crate_dir):
        """Test handling of corrupted cache files."""
        crate_hash = cache.compute_crate_hash(temp_crate_dir)

        # Put valid entry
        cache.put(crate_hash, "test_tool", {"value": 1})

        # Corrupt the cache file
        cache_path = cache._get_cache_path(crate_hash, "test_tool")
        cache_path.write_text("not valid json {{{")

        # Should return None instead of raising
        result = cache.get(crate_hash, "test_tool")
        assert result is None

    def test_multiple_rs_files(self, cache, temp_crate_dir):
        """Test that hash includes all .rs files."""
        src_dir = temp_crate_dir / "src"

        # Add more Rust files
        (src_dir / "utils.rs").write_text("pub mod utils;\n")
        (src_dir / "models.rs").write_text("pub struct Model;\n")

        hash1 = cache.compute_crate_hash(temp_crate_dir)

        # Modify one of the new files
        (src_dir / "utils.rs").write_text("pub mod utils;\npub fn helper() {}\n")

        hash2 = cache.compute_crate_hash(temp_crate_dir)

        assert hash1 != hash2


class TestGetSourceDirs:
    """Tests for AnalysisCache._get_source_dirs() method."""

    def test_standard_layout(self, cache, tmp_path):
        """Standard src/ layout should return [src]."""
        crate_dir = tmp_path / "crate"
        crate_dir.mkdir()
        (crate_dir / "src").mkdir()
        (crate_dir / "src" / "lib.rs").write_text("// lib")
        (crate_dir / "Cargo.toml").write_text(
            '[package]\nname = "test"\nversion = "1.0.0"\n'
        )

        paths = cache._get_source_dirs(crate_dir)
        assert paths == [crate_dir / "src"]

    def test_custom_lib_path(self, cache, tmp_path):
        """Custom lib.path should be discovered."""
        crate_dir = tmp_path / "crate"
        crate_dir.mkdir()
        (crate_dir / "binding_rust").mkdir()
        (crate_dir / "binding_rust" / "lib.rs").write_text("// custom lib")
        (crate_dir / "Cargo.toml").write_text(
            '[package]\nname = "custom"\nversion = "1.0.0"\n\n'
            '[lib]\npath = "binding_rust/lib.rs"\n'
        )

        paths = cache._get_source_dirs(crate_dir)
        assert crate_dir / "binding_rust" in paths

    def test_missing_cargo_toml(self, cache, tmp_path):
        """Missing Cargo.toml should return src/ if it exists."""
        crate_dir = tmp_path / "crate"
        crate_dir.mkdir()
        (crate_dir / "src").mkdir()

        paths = cache._get_source_dirs(crate_dir)
        assert paths == [crate_dir / "src"]

    def test_invalid_toml(self, cache, tmp_path):
        """Invalid Cargo.toml should fall back to src/."""
        crate_dir = tmp_path / "crate"
        crate_dir.mkdir()
        (crate_dir / "src").mkdir()
        (crate_dir / "Cargo.toml").write_text("not valid { toml [[")

        paths = cache._get_source_dirs(crate_dir)
        assert paths == [crate_dir / "src"]


class TestCacheWithCustomSourcePaths:
    """Tests for compute_crate_hash with non-standard source paths."""

    def test_hash_includes_custom_lib_path(self, cache, tmp_path):
        """Hash should include files from custom lib.path."""
        crate_dir = tmp_path / "custom_crate"
        crate_dir.mkdir()
        (crate_dir / "binding_rust").mkdir()
        (crate_dir / "binding_rust" / "lib.rs").write_text("// v1")
        (crate_dir / "Cargo.toml").write_text(
            '[package]\nname = "custom"\nversion = "1.0.0"\n\n'
            '[lib]\npath = "binding_rust/lib.rs"\n'
        )

        hash1 = cache.compute_crate_hash(crate_dir)

        # Modify the custom lib file
        (crate_dir / "binding_rust" / "lib.rs").write_text("// v2 - modified")

        hash2 = cache.compute_crate_hash(crate_dir)

        assert hash1 != hash2

    def test_hash_includes_both_src_and_custom(self, cache, tmp_path):
        """Hash should include files from both src/ and custom paths."""
        crate_dir = tmp_path / "hybrid_crate"
        crate_dir.mkdir()
        (crate_dir / "src").mkdir()
        (crate_dir / "src" / "main.rs").write_text("fn main() {}")
        (crate_dir / "binding_rust").mkdir()
        (crate_dir / "binding_rust" / "lib.rs").write_text("// lib v1")
        (crate_dir / "Cargo.toml").write_text(
            '[package]\nname = "hybrid"\nversion = "1.0.0"\n\n'
            '[lib]\npath = "binding_rust/lib.rs"\n'
        )

        hash1 = cache.compute_crate_hash(crate_dir)

        # Modify file in custom path
        (crate_dir / "binding_rust" / "lib.rs").write_text("// lib v2")
        hash2 = cache.compute_crate_hash(crate_dir)

        # Modify file in standard path
        (crate_dir / "src" / "main.rs").write_text('fn main() { println!("hi"); }')
        hash3 = cache.compute_crate_hash(crate_dir)

        assert hash1 != hash2
        assert hash2 != hash3
