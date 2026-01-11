"""
Duplicate detection utilities for dataset quality analysis.

Detects exact and near-duplicate samples using hash-based and similarity-based methods.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.6.0
"""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any

logger = logging.getLogger(__name__)


class DuplicateDetector:
    """Detects exact and near-duplicate samples in dataset."""

    def __init__(self, similarity_threshold: float = 0.90):
        """
        Initialize duplicate detector.

        Args:
            similarity_threshold: Minimum similarity ratio (0.0-1.0) to consider near-duplicate
        """
        self.similarity_threshold = similarity_threshold

    def find_duplicates(
        self, samples: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Find exact and near-duplicate samples.

        Args:
            samples: List of sample dictionaries

        Returns:
            Dictionary with duplicate analysis results
        """
        logger.info(f"Analyzing {len(samples)} samples for duplicates...")

        exact_dupes = self._find_exact_duplicates(samples)
        near_dupes = self._find_near_duplicates(samples)

        total_exact = sum(len(dupes) - 1 for dupes in exact_dupes.values())
        total_near = len(near_dupes)

        logger.info(
            f"Found {len(exact_dupes)} exact duplicate groups "
            f"({total_exact} duplicate samples)"
        )
        logger.info(f"Found {total_near} near-duplicate pairs")

        return {
            "exact_duplicates": {
                "groups": exact_dupes,
                "total_groups": len(exact_dupes),
                "total_duplicates": total_exact,
            },
            "near_duplicates": {
                "pairs": near_dupes,
                "total_pairs": total_near,
                "threshold": self.similarity_threshold,
            },
            "summary": {
                "total_samples": len(samples),
                "unique_samples": len(samples) - total_exact,
                "exact_duplicate_ratio": total_exact / len(samples) if samples else 0,
                "near_duplicate_ratio": total_near / len(samples) if samples else 0,
            },
        }

    def _find_exact_duplicates(
        self, samples: list[dict[str, Any]]
    ) -> dict[str, list[int]]:
        """
        Find exact duplicates using hash-based detection.

        Args:
            samples: List of sample dictionaries

        Returns:
            Dictionary mapping hash to list of sample indices
        """
        hash_map: dict[str, list[int]] = defaultdict(list)

        for idx, sample in enumerate(samples):
            # Use both prompt and gen for hashing (or output field)
            content = self._normalize_sample_content(sample)
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            hash_map[content_hash].append(idx)

        # Filter to only groups with duplicates
        duplicates = {h: indices for h, indices in hash_map.items() if len(indices) > 1}

        return duplicates

    def _find_near_duplicates(
        self, samples: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Find near-duplicates using similarity comparison.

        Args:
            samples: List of sample dictionaries

        Returns:
            List of near-duplicate pairs with similarity scores
        """
        near_dupes = []

        # Only check a reasonable sample size for performance
        max_comparisons = min(len(samples), 1000)
        if len(samples) > max_comparisons:
            logger.warning(
                f"Limiting near-duplicate detection to first {max_comparisons} samples "
                f"(found {len(samples)} total)"
            )

        # Compare pairs
        for i in range(max_comparisons):
            content_i = self._normalize_sample_content(samples[i])

            # Only compare with subsequent samples to avoid duplicates
            for j in range(i + 1, max_comparisons):
                content_j = self._normalize_sample_content(samples[j])

                # Calculate similarity
                similarity = self._calculate_similarity(content_i, content_j)

                if similarity >= self.similarity_threshold:
                    near_dupes.append(
                        {
                            "sample_1_idx": i,
                            "sample_2_idx": j,
                            "similarity": similarity,
                            "sample_1_preview": content_i[:100],
                            "sample_2_preview": content_j[:100],
                        }
                    )

        return near_dupes

    def _normalize_sample_content(self, sample: dict[str, Any]) -> str:
        """
        Extract and normalize sample content for comparison.

        Args:
            sample: Sample dictionary

        Returns:
            Normalized content string
        """
        # Support both prompt/gen and instruction/output formats
        if "gen" in sample:
            content = sample.get("gen", "")
        elif "output" in sample:
            content = sample.get("output", "")
        else:
            # Fallback to concatenating all string values
            content = " ".join(
                str(v) for v in sample.values() if isinstance(v, str)
            )

        # Normalize whitespace
        content = " ".join(content.split())

        return content

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity ratio between two texts.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity ratio (0.0-1.0)
        """
        matcher = SequenceMatcher(None, text1, text2)
        return matcher.ratio()
