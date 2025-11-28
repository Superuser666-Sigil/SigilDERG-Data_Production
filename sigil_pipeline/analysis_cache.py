"""
Analysis result caching module.

Caches cargo tool results (clippy, geiger, outdated, etc.) to avoid
re-running expensive analysis on unchanged crates.

Uses content-based hashing of Cargo.toml, Cargo.lock, and source files
to detect when a crate has changed and needs re-analysis.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.2.0
"""

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

# Type variable for cached result types
T = TypeVar("T")


@dataclass
class CacheEntry:
    """Represents a cached analysis result."""

    crate_hash: str
    """Hash of the crate content."""

    tool_name: str
    """Name of the analysis tool (clippy, geiger, etc.)."""

    result: dict[str, Any]
    """Serialized analysis result."""

    timestamp: str
    """ISO timestamp when the result was cached."""


class AnalysisCache:
    """
    Cache for cargo analysis tool results.

    Stores results keyed by content hash + tool name.
    Results are stored as JSON files in the cache directory.
    """

    def __init__(self, cache_dir: str | Path = ".cache/analysis"):
        """
        Initialize the analysis cache.

        Args:
            cache_dir: Directory for cache files.
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._hit_count = 0
        self._miss_count = 0

    def compute_crate_hash(self, crate_dir: Path) -> str:
        """
        Compute a content-based hash for a crate.

        Includes:
        - Cargo.toml
        - Cargo.lock (if exists)
        - All .rs files in src/

        Args:
            crate_dir: Path to the crate directory.

        Returns:
            SHA256 hash string of the crate content.
        """
        hasher = hashlib.sha256()

        # Hash Cargo.toml
        cargo_toml = crate_dir / "Cargo.toml"
        if cargo_toml.exists():
            hasher.update(cargo_toml.read_bytes())

        # Hash Cargo.lock if present
        cargo_lock = crate_dir / "Cargo.lock"
        if cargo_lock.exists():
            hasher.update(cargo_lock.read_bytes())

        # Hash all .rs files in src/
        src_dir = crate_dir / "src"
        if src_dir.exists():
            # Sort files for deterministic ordering
            rs_files = sorted(src_dir.rglob("*.rs"))
            for rs_file in rs_files:
                try:
                    # Include relative path in hash for structural changes
                    rel_path = rs_file.relative_to(crate_dir)
                    hasher.update(str(rel_path).encode("utf-8"))
                    hasher.update(rs_file.read_bytes())
                except Exception as e:
                    logger.debug(f"Error hashing {rs_file}: {e}")
                    continue

        return hasher.hexdigest()

    def _get_cache_path(self, crate_hash: str, tool_name: str) -> Path:
        """Get the cache file path for a hash + tool combination."""
        # Use first 2 chars as subdirectory to avoid too many files in one dir
        subdir = crate_hash[:2]
        filename = f"{crate_hash}_{tool_name}.json"
        cache_path = self.cache_dir / subdir / filename
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        return cache_path

    def get(self, crate_hash: str, tool_name: str) -> dict[str, Any] | None:
        """
        Get a cached result.

        Args:
            crate_hash: Hash of the crate content.
            tool_name: Name of the analysis tool.

        Returns:
            Cached result dict, or None if not found.
        """
        cache_path = self._get_cache_path(crate_hash, tool_name)

        if not cache_path.exists():
            self._miss_count += 1
            return None

        try:
            with cache_path.open("r", encoding="utf-8") as f:
                entry = json.load(f)
                self._hit_count += 1
                logger.debug(f"Cache hit for {tool_name} ({crate_hash[:8]}...)")
                return entry.get("result")
        except (json.JSONDecodeError, IOError) as e:
            logger.debug(f"Cache read error for {cache_path}: {e}")
            self._miss_count += 1
            return None

    def put(
        self,
        crate_hash: str,
        tool_name: str,
        result: dict[str, Any],
        timestamp: str | None = None,
    ) -> None:
        """
        Store a result in the cache.

        Args:
            crate_hash: Hash of the crate content.
            tool_name: Name of the analysis tool.
            result: Analysis result to cache (must be JSON-serializable).
            timestamp: Optional ISO timestamp; uses current time if not provided.
        """
        from datetime import datetime, timezone

        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()

        entry = CacheEntry(
            crate_hash=crate_hash,
            tool_name=tool_name,
            result=result,
            timestamp=timestamp,
        )

        cache_path = self._get_cache_path(crate_hash, tool_name)

        try:
            with cache_path.open("w", encoding="utf-8") as f:
                json.dump(asdict(entry), f, indent=2)
            logger.debug(f"Cached {tool_name} result ({crate_hash[:8]}...)")
        except IOError as e:
            logger.warning(f"Failed to write cache file {cache_path}: {e}")

    def invalidate(self, crate_dir: Path) -> int:
        """
        Invalidate all cached results for a crate.

        Args:
            crate_dir: Path to the crate directory.

        Returns:
            Number of cache entries deleted.
        """
        crate_hash = self.compute_crate_hash(crate_dir)
        return self.invalidate_by_hash(crate_hash)

    def invalidate_by_hash(self, crate_hash: str) -> int:
        """
        Invalidate all cached results for a hash.

        Args:
            crate_hash: Hash of the crate content.

        Returns:
            Number of cache entries deleted.
        """
        subdir = self.cache_dir / crate_hash[:2]
        if not subdir.exists():
            return 0

        deleted = 0
        for cache_file in subdir.glob(f"{crate_hash}_*.json"):
            try:
                cache_file.unlink()
                deleted += 1
            except IOError as e:
                logger.warning(f"Failed to delete cache file {cache_file}: {e}")

        return deleted

    def clear(self) -> int:
        """
        Clear all cached results.

        Returns:
            Number of cache entries deleted.
        """
        deleted = 0
        for subdir in self.cache_dir.iterdir():
            if subdir.is_dir():
                for cache_file in subdir.glob("*.json"):
                    try:
                        cache_file.unlink()
                        deleted += 1
                    except IOError:
                        pass
                try:
                    subdir.rmdir()
                except IOError:
                    pass

        return deleted

    @property
    def stats(self) -> dict[str, int | float]:
        """Get cache hit/miss statistics."""
        total = self._hit_count + self._miss_count
        return {
            "hits": self._hit_count,
            "misses": self._miss_count,
            "total": total,
            "hit_rate": round(self._hit_count / total, 4) if total > 0 else 0.0,
        }

    def reset_stats(self) -> None:
        """Reset cache statistics."""
        self._hit_count = 0
        self._miss_count = 0


# Global cache instance (lazily initialized)
_global_cache: AnalysisCache | None = None


def get_cache(cache_dir: str | Path = ".cache/analysis") -> AnalysisCache:
    """
    Get the global analysis cache instance.

    Args:
        cache_dir: Directory for cache files.

    Returns:
        The global AnalysisCache instance.
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = AnalysisCache(cache_dir)
    return _global_cache


def set_cache(cache: AnalysisCache | None) -> None:
    """
    Set the global analysis cache instance.

    Args:
        cache: AnalysisCache instance, or None to reset.
    """
    global _global_cache
    _global_cache = cache
