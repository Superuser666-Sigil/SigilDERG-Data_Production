# utils/rust_code_analyzer.py
"""
Atomic Rust code analysis utilities - extracted from duplicate code patterns
"""
import re
from typing import Any


class RustCodeAnalyzer:
    """Atomic unit for analyzing Rust source code patterns"""

    @staticmethod
    def create_empty_metrics() -> dict[str, Any]:
        """Create standardized empty metrics structure"""
        return {
            "file_count": 0,
            "loc": 0,
            "complexity": [],
            "types": [],
            "traits": [],
            "functions": [],
            "has_tests": False,
            "has_examples": False,
            "has_benchmarks": False,
        }

    @staticmethod
    def analyze_rust_content(content: str) -> dict[str, Any]:
        """Analyze a single Rust file's content - atomic unit for content analysis"""
        if not content:
            return {"loc": 0, "functions": [], "types": [], "traits": []}

        # Count lines of code
        loc = len(content.splitlines())

        # Extract code elements using consistent patterns
        fn_matches = re.findall(r"fn\s+([a-zA-Z0-9_]+)", content)
        struct_matches = re.findall(r"struct\s+([a-zA-Z0-9_]+)", content)
        trait_matches = re.findall(r"trait\s+([a-zA-Z0-9_]+)", content)

        return {
            "loc": loc,
            "functions": fn_matches,
            "types": struct_matches,
            "traits": trait_matches,
        }

    @staticmethod
    def detect_project_structure(file_list: list[str]) -> dict[str, bool]:
        """Detect project structure patterns - atomic unit for structure detection"""
        structure = {
            "has_tests": False,
            "has_examples": False,
            "has_benchmarks": False,
        }

        # Convert to lowercase for case-insensitive checking
        files_lower = [f.lower() for f in file_list]

        # Detect common Rust project patterns
        structure["has_tests"] = any("test" in f for f in files_lower)
        structure["has_examples"] = any("example" in f for f in files_lower)
        structure["has_benchmarks"] = any("bench" in f for f in files_lower)

        return structure

    @staticmethod
    def aggregate_metrics(
        metrics: dict[str, Any],
        content_analysis: dict[str, Any],
        structure: dict[str, bool],
    ) -> dict[str, Any]:
        """Aggregate analysis results - atomic unit for combining results"""
        metrics["loc"] += content_analysis["loc"]
        metrics["functions"].extend(content_analysis["functions"])
        metrics["types"].extend(content_analysis["types"])
        metrics["traits"].extend(content_analysis["traits"])

        # Update structure flags (OR operation to preserve True values)
        metrics["has_tests"] = metrics["has_tests"] or structure["has_tests"]
        metrics["has_examples"] = metrics["has_examples"] or structure["has_examples"]
        metrics["has_benchmarks"] = (
            metrics["has_benchmarks"] or structure["has_benchmarks"]
        )

        return metrics
