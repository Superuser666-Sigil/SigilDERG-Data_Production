#!/usr/bin/env python3
"""
Comprehensive dataset quality analysis tool.

Analyzes dataset samples for statistical distributions, duplicates, and quality issues.
Provides detailed reports with recommendations for dataset improvement.

Usage:
    python tools/dataset_quality_analyzer.py --dataset output/train.jsonl
    python tools/dataset_quality_analyzer.py --dataset output/train.jsonl --output-json reports/quality.json

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.6.0
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

# Import from sigil_pipeline
try:
    from sigil_pipeline.duplicate_detection import DuplicateDetector
    from sigil_pipeline.quality_scoring import QualityScorer, HEALTHY_PASS_RATES
except ImportError as e:
    print(f"Error: Could not import sigil_pipeline modules: {e}")
    print("Make sure you're running from the project root directory.")
    sys.exit(1)

logger = logging.getLogger(__name__)


class StatisticalProfiler:
    """Analyzes statistical properties of dataset samples."""

    def analyze_dataset(self, samples: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Analyze dataset for statistical properties.

        Args:
            samples: List of sample dictionaries

        Returns:
            Dictionary with analysis results
        """
        logger.info(f"Analyzing statistical properties of {len(samples)} samples...")

        return {
            "total_samples": len(samples),
            "task_distribution": self._analyze_task_distribution(samples),
            "length_statistics": self._analyze_lengths(samples),
            "field_completeness": self._analyze_completeness(samples),
        }

    def _analyze_task_distribution(
        self, samples: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Analyze distribution of task types."""
        task_counts = Counter(
            sample.get("task_type", "unknown") for sample in samples
        )

        total = len(samples)
        distribution = {}

        for task_type, count in task_counts.most_common():
            ratio = count / total if total > 0 else 0
            healthy_range = HEALTHY_PASS_RATES.get(task_type)

            health_status = "✓ Healthy"
            if healthy_range:
                min_healthy, max_healthy = healthy_range
                if ratio < min_healthy:
                    health_status = "⚠️  Low (below healthy range)"
                elif ratio > max_healthy:
                    health_status = "⚠️  High (above healthy range)"

            distribution[task_type] = {
                "count": count,
                "ratio": ratio,
                "health_status": health_status,
            }

        return distribution

    def _analyze_lengths(self, samples: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze length distributions."""
        prompt_lengths = []
        gen_lengths = []

        for sample in samples:
            prompt = sample.get("prompt", sample.get("instruction", ""))
            gen = sample.get("gen", sample.get("output", ""))

            prompt_lengths.append(len(prompt))
            gen_lengths.append(len(gen))

        return {
            "prompt_lengths": self._calculate_stats(prompt_lengths),
            "gen_lengths": self._calculate_stats(gen_lengths),
        }

    def _analyze_completeness(self, samples: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze field completeness."""
        missing_prompt = sum(
            1
            for s in samples
            if not s.get("prompt", s.get("instruction", "")).strip()
        )
        missing_gen = sum(
            1 for s in samples if not s.get("gen", s.get("output", "")).strip()
        )
        missing_task_type = sum(1 for s in samples if "task_type" not in s)

        return {
            "missing_prompt": missing_prompt,
            "missing_gen": missing_gen,
            "missing_task_type": missing_task_type,
            "complete_samples": len(samples)
            - max(missing_prompt, missing_gen, missing_task_type),
        }

    def _calculate_stats(self, values: list[int | float]) -> dict[str, float]:
        """Calculate basic statistics for a list of values."""
        if not values:
            return {
                "min": 0,
                "max": 0,
                "mean": 0,
                "median": 0,
            }

        sorted_values = sorted(values)
        return {
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "mean": sum(values) / len(values),
            "median": sorted_values[len(sorted_values) // 2],
        }


class QualityReportGenerator:
    """Generates comprehensive quality reports."""

    def generate_console_report(self, analysis_results: dict[str, Any]) -> str:
        """Generate formatted console report."""
        lines = []

        lines.append("=" * 70)
        lines.append("Dataset Quality Analysis Report")
        lines.append("=" * 70)
        lines.append(f"Dataset: {analysis_results['dataset_path']}")
        lines.append(
            f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        lines.append(f"Total Samples: {analysis_results['stats']['total_samples']}")
        lines.append("")

        # Task Distribution
        lines.append("Task Distribution:")
        lines.append("-" * 70)
        dist = analysis_results["stats"]["task_distribution"]
        for task_type, info in dist.items():
            lines.append(
                f"  {task_type:20} {info['count']:6} ({info['ratio']:6.1%})  {info['health_status']}"
            )
        lines.append("")

        # Quality Metrics
        lines.append("Quality Metrics:")
        lines.append("-" * 70)
        quality = analysis_results["quality"]
        stats = quality["statistics"]
        lines.append(f"  Average Quality Score: {stats['average_score']:.1f}/100")
        lines.append(
            f"  Score Range: {stats['min_score']:.1f} - {stats['max_score']:.1f}"
        )
        lines.append(f"  Median Score: {stats['median_score']:.1f}")
        lines.append("")

        tier_dist = quality["tier_distribution"]
        total = sum(tier_dist.values())
        lines.append("  Quality Tier Distribution:")
        for tier in ["premium", "good", "acceptable", "suspect"]:
            count = tier_dist.get(tier, 0)
            ratio = count / total if total > 0 else 0
            icon = "✓" if tier in ["premium", "good"] else "⚠️"
            lines.append(f"    {icon} {tier:12} {count:6} ({ratio:6.1%})")
        lines.append("")

        # Length Statistics
        lines.append("Length Statistics:")
        lines.append("-" * 70)
        length_stats = analysis_results["stats"]["length_statistics"]
        for field_name, stats in length_stats.items():
            lines.append(f"  {field_name}:")
            lines.append(
                f"    Min: {stats['min']:.0f}, Max: {stats['max']:.0f}, "
                f"Mean: {stats['mean']:.0f}, Median: {stats['median']:.0f}"
            )
        lines.append("")

        # Duplicates
        lines.append("Duplicate Analysis:")
        lines.append("-" * 70)
        dupes = analysis_results["duplicates"]
        exact = dupes["exact_duplicates"]
        near = dupes["near_duplicates"]
        lines.append(
            f"  Exact Duplicates: {exact['total_groups']} groups "
            f"({exact['total_duplicates']} duplicate samples)"
        )
        lines.append(
            f"  Near-Duplicates: {near['total_pairs']} pairs "
            f"(threshold: {near['threshold']:.0%})"
        )
        summary = dupes["summary"]
        lines.append(
            f"  Duplicate Ratio: {summary['exact_duplicate_ratio']:.1%} exact, "
            f"{summary['near_duplicate_ratio']:.1%} near"
        )
        lines.append("")

        # Recommendations
        lines.append("Recommendations:")
        lines.append("-" * 70)
        for rec in quality["recommendations"]:
            lines.append(f"  {rec}")
        lines.append("")

        lines.append("=" * 70)

        return "\n".join(lines)

    def generate_json_report(
        self, analysis_results: dict[str, Any], output_path: Path
    ):
        """Generate JSON report file."""
        logger.info(f"Writing JSON report to {output_path}")

        report = {
            "metadata": {
                "analysis_date": datetime.now().isoformat(),
                "dataset_path": str(analysis_results["dataset_path"]),
                "total_samples": analysis_results["stats"]["total_samples"],
            },
            "statistics": analysis_results["stats"],
            "quality": analysis_results["quality"],
            "duplicates": analysis_results["duplicates"],
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)


def load_samples(dataset_path: Path, max_samples: int | None = None) -> list[dict]:
    """Load samples from JSONL file."""
    logger.info(f"Loading samples from {dataset_path}...")

    samples = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                sample = json.loads(line)
                samples.append(sample)

                if max_samples and len(samples) >= max_samples:
                    logger.info(f"Reached max_samples limit ({max_samples})")
                    break

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse line {line_num}: {e}")
                continue

    logger.info(f"Loaded {len(samples)} samples")
    return samples


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze dataset quality with comprehensive metrics and duplicate detection"
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        required=True,
        help="Path to dataset JSONL file",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="Optional: Write JSON report to file",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="Maximum number of samples to analyze (default: all)",
    )
    parser.add_argument(
        "--similarity-threshold",
        type=float,
        default=0.90,
        help="Similarity threshold for near-duplicate detection (default: 0.90)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Validate input
    if not args.dataset.exists():
        logger.error(f"Dataset file not found: {args.dataset}")
        return 1

    # Load samples
    samples = load_samples(args.dataset, args.max_samples)
    if not samples:
        logger.error("No samples loaded!")
        return 1

    # Initialize analyzers
    profiler = StatisticalProfiler()
    detector = DuplicateDetector(similarity_threshold=args.similarity_threshold)
    scorer = QualityScorer()

    # Run analyses
    logger.info("Running statistical analysis...")
    stats = profiler.analyze_dataset(samples)

    logger.info("Running duplicate detection...")
    duplicates = detector.find_duplicates(samples)

    logger.info("Running quality scoring...")
    quality = scorer.score_all_samples(samples)

    # Compile results
    analysis_results = {
        "dataset_path": args.dataset,
        "stats": stats,
        "duplicates": duplicates,
        "quality": quality,
    }

    # Generate reports
    reporter = QualityReportGenerator()

    # Console report
    console_report = reporter.generate_console_report(analysis_results)
    print(console_report)

    # JSON report (optional)
    if args.output_json:
        reporter.generate_json_report(analysis_results, args.output_json)
        print(f"\nJSON report written to: {args.output_json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
