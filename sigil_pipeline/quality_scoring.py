"""
Quality scoring utilities for dataset samples.

Assigns quality scores based on multiple factors including hallucinations,
length appropriateness, and semantic markers.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.6.0
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Import hallucination patterns from output_validator
try:
    from .output_validator import detect_hallucinations
except ImportError:
    logger.warning("Could not import detect_hallucinations, using fallback")

    def detect_hallucinations(code: str) -> list[str]:
        """Fallback hallucination detection."""
        patterns = ["todo!", "unimplemented!", "TODO", "FIXME"]
        return [p for p in patterns if p in code]


# Quality tiers
QUALITY_TIERS = {
    "premium": (90, 100),
    "good": (70, 90),
    "acceptable": (50, 70),
    "suspect": (0, 50),
}

# Healthy pass rate thresholds by task type
HEALTHY_PASS_RATES = {
    "code_generation": (0.30, 0.50),
    "error_fixing": (0.20, 0.40),
    "transformations": (0.20, 0.40),
    "fill_in_middle": (0.30, 0.50),
    "explanations": (0.80, 0.95),
}


class QualityScorer:
    """Assigns quality scores to dataset samples."""

    def __init__(self):
        """Initialize quality scorer."""
        pass

    def score_sample(self, sample: dict[str, Any]) -> dict[str, Any]:
        """
        Score a single sample for quality.

        Args:
            sample: Sample dictionary

        Returns:
            Dictionary with score, tier, and issues
        """
        score = 100.0
        issues = []

        # Extract content
        prompt = sample.get("prompt", sample.get("instruction", ""))
        gen = sample.get("gen", sample.get("output", ""))
        task_type = sample.get("task_type", "unknown")

        # Check for hallucinations
        hallucinations = detect_hallucinations(gen)
        if hallucinations:
            score -= 20.0
            issues.append(f"hallucinations: {', '.join(hallucinations)}")

        # Check length appropriateness
        gen_length = len(gen)
        if gen_length < 50:
            score -= 15.0
            issues.append("very_short_output")
        elif gen_length > 10000:
            score -= 5.0
            issues.append("very_long_output")

        # Check for empty/missing fields
        if not prompt.strip():
            score -= 20.0
            issues.append("missing_prompt")
        if not gen.strip():
            score -= 30.0
            issues.append("missing_output")

        # Check for code markers (for code tasks)
        if task_type not in ["explanations"]:
            if not self._has_code_markers(gen):
                score -= 10.0
                issues.append("lacks_code_markers")

        # Check for explanation markers (for explanation tasks)
        if task_type == "explanations":
            if not self._has_explanation_markers(gen):
                score -= 10.0
                issues.append("lacks_explanation_markers")

        # Ensure score is within bounds
        score = max(0.0, min(100.0, score))

        return {
            "score": score,
            "tier": self._classify_tier(score),
            "issues": issues,
            "task_type": task_type,
        }

    def score_all_samples(
        self, samples: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Score all samples and provide aggregate statistics.

        Args:
            samples: List of sample dictionaries

        Returns:
            Dictionary with scores and statistics
        """
        logger.info(f"Scoring {len(samples)} samples...")

        scored_samples = []
        for idx, sample in enumerate(samples):
            score_result = self.score_sample(sample)
            score_result["sample_idx"] = idx
            scored_samples.append(score_result)

        # Calculate statistics
        scores = [s["score"] for s in scored_samples]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        # Count by tier
        tier_counts = {tier: 0 for tier in QUALITY_TIERS}
        for s in scored_samples:
            tier_counts[s["tier"]] += 1

        # Identify low-quality samples
        low_quality = [
            s for s in scored_samples if s["tier"] in ["suspect", "acceptable"]
        ]

        return {
            "scored_samples": scored_samples,
            "statistics": {
                "average_score": avg_score,
                "min_score": min(scores) if scores else 0.0,
                "max_score": max(scores) if scores else 0.0,
                "median_score": sorted(scores)[len(scores) // 2] if scores else 0.0,
            },
            "tier_distribution": tier_counts,
            "low_quality_samples": low_quality,
            "recommendations": self._generate_recommendations(
                tier_counts, len(samples)
            ),
        }

    def _classify_tier(self, score: float) -> str:
        """Classify score into quality tier."""
        for tier, (min_score, max_score) in QUALITY_TIERS.items():
            if min_score <= score <= max_score:
                return tier
        return "suspect"

    def _has_code_markers(self, text: str) -> bool:
        """Check if text has Rust code markers."""
        code_markers = [
            r"\bfn\s+\w+",
            r"\bstruct\s+\w+",
            r"\benum\s+\w+",
            r"\bimpl\s+",
            r"\blet\s+",
            r"\->",
            r"\{[\s\S]*\}",
        ]
        return any(re.search(pattern, text) for pattern in code_markers)

    def _has_explanation_markers(self, text: str) -> bool:
        """Check if text has explanation markers."""
        explanation_markers = [
            "function",
            "method",
            "struct",
            "enum",
            "implements",
            "returns",
            "parameter",
            "argument",
        ]
        text_lower = text.lower()
        return any(marker in text_lower for marker in explanation_markers)

    def _generate_recommendations(
        self, tier_counts: dict[str, int], total: int
    ) -> list[str]:
        """Generate recommendations based on quality distribution."""
        recommendations = []

        suspect_ratio = tier_counts.get("suspect", 0) / total if total > 0 else 0
        acceptable_ratio = tier_counts.get("acceptable", 0) / total if total > 0 else 0

        if suspect_ratio > 0.05:
            recommendations.append(
                f"⚠️  High suspect sample ratio ({suspect_ratio:.1%}). "
                "Consider reviewing low-quality samples."
            )

        if suspect_ratio + acceptable_ratio > 0.25:
            recommendations.append(
                f"⚠️  Over 25% of samples are below 'good' quality. "
                "Consider stricter filtering or improved prompts."
            )

        if tier_counts.get("premium", 0) / total > 0.30 if total > 0 else False:
            recommendations.append(
                "✓ Good distribution of high-quality samples (>30% premium)."
            )

        if not recommendations:
            recommendations.append("✓ Overall quality distribution looks healthy.")

        return recommendations
