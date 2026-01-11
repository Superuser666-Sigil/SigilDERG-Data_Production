"""
Static API Usage Analysis Module

Analyzes Rust code to detect API usage patterns without requiring LLM calls.
Uses static analysis, pattern matching, and AST traversal.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.6.0
"""

import logging
from dataclasses import dataclass, field

from .ast_patterns import _get_parser

logger = logging.getLogger(__name__)


@dataclass
class UsageAnalysis:
    """Results of API usage analysis."""

    api_name: str
    """Name of the API being analyzed."""

    module_path: str
    """Expected module path of the API."""

    confidence: float
    """Confidence score (0.0 to 1.0)."""

    usage_type: str
    """Type of usage: direct_call, qualified_call, import_only, struct_init, method_call."""

    import_statement: str | None = None
    """Import statement if found."""

    usage_locations: list[tuple[int, int]] = field(default_factory=list)
    """List of (line_number, column) tuples where API is used."""


class APIUsageAnalyzer:
    """Static analyzer for detecting API usage in Rust code."""

    def __init__(self):
        self.parser = _get_parser()

    def analyze_usage(
        self, code: str, api_name: str, module_path: str = ""
    ) -> UsageAnalysis:
        """
        Analyze code to detect usage of a specific API.

        Args:
            code: Rust source code to analyze
            api_name: Name of the API to find
            module_path: Expected module path (e.g., "std::fs")

        Returns:
            UsageAnalysis with confidence score and usage details
        """
        lines = code.split("\n")

        # Step 1: Analyze imports
        import_confidence, import_stmt = self._analyze_imports(
            lines, api_name, module_path
        )

        # Step 2: Analyze actual usage
        usage_confidence, usage_type, locations = self._analyze_usage_patterns(
            lines, api_name, module_path, import_stmt
        )

        # Combine confidences
        if import_confidence == 1.0 and usage_confidence > 0:
            final_confidence = min(0.9, usage_confidence)
        elif import_confidence == 1.0:
            final_confidence = 0.5  # Imported but not clearly used
        elif import_confidence == 0.7:
            final_confidence = (
                usage_confidence * 0.8
            )  # Module imported, qualified usage
        else:
            final_confidence = max(import_confidence, usage_confidence * 0.3)

        return UsageAnalysis(
            api_name=api_name,
            module_path=module_path,
            confidence=final_confidence,
            usage_type=usage_type or "unknown",
            import_statement=import_stmt,
            usage_locations=locations or [],
        )

    def _analyze_imports(
        self, lines: list[str], api_name: str, module_path: str
    ) -> tuple[float, str | None]:
        """
        Analyze import statements to determine if API is imported.

        Returns:
            Tuple of (confidence_score, import_statement)
        """
        imports: list[str] = []

        for line in lines:
            line_stripped = line.strip()

            if line_stripped.startswith("use ") and ";" in line_stripped:
                import_path = line_stripped[4 : line_stripped.find(";")].strip()
                imports.append(import_path)

                # Direct import: use std::fs::File;
                if import_path == f"{module_path}::{api_name}":
                    return 1.0, import_path

                # Import with braces: use std::fs::{File, write};
                if (
                    module_path in import_path
                    and "{" in import_path
                    and "}" in import_path
                ):
                    brace_start = import_path.find("{")
                    brace_end = import_path.find("}")
                    brace_content = import_path[brace_start + 1 : brace_end]
                    items = [item.strip() for item in brace_content.split(",")]
                    if api_name in items:
                        return 1.0, import_path

                # Import with alias: use std::fs::File as StdFile;
                if f"{module_path}::{api_name} as " in import_path:
                    return 1.0, import_path

                # Import the entire module: use std::fs;
                if import_path == module_path:
                    return 0.7, import_path

        # Check for crate-level imports
        if module_path:
            crate_name = module_path.split("::")[0]
            for imp in imports:
                if imp.startswith(crate_name):
                    return 0.3, imp

        return 0.0, None

    def _analyze_usage_patterns(
        self, lines: list[str], api_name: str, module_path: str, import_stmt: str | None
    ) -> tuple[float, str, list[tuple[int, int]]]:
        """
        Analyze code for actual API usage patterns.

        Returns:
            Tuple of (confidence, usage_type, locations)
        """
        locations: list[tuple[int, int]] = []
        usage_type = "unknown"
        confidence = 0.0

        for line_num, line in enumerate(lines, 1):
            line_stripped = line.strip()

            # Skip comments
            if line_stripped.startswith("//"):
                continue

            # Direct function call: api_name(...)
            if f"{api_name}(" in line_stripped:
                col = line_stripped.find(f"{api_name}(")
                locations.append((line_num, col))
                usage_type = "direct_call"
                confidence = 0.9
                continue

            # Struct initialization: api_name { ... } or api_name(...)
            if f"{api_name} {{" in line_stripped or f"{api_name}(" in line_stripped:
                col = line_stripped.find(api_name)
                locations.append((line_num, col))
                usage_type = "struct_init"
                confidence = 0.9
                continue

            # Method call: something.api_name(...)
            if f".{api_name}(" in line_stripped:
                col = line_stripped.find(f".{api_name}(")
                locations.append((line_num, col))
                usage_type = "method_call"
                confidence = 0.9
                continue

            # Qualified call: module::api_name
            if module_path and f"{module_path}::{api_name}" in line_stripped:
                col = line_stripped.find(f"{module_path}::{api_name}")
                locations.append((line_num, col))
                usage_type = "qualified_call"
                confidence = 0.8
                continue

            # Type annotation: let x: api_name = ...
            if f": {api_name}" in line_stripped or f":{api_name}" in line_stripped:
                col = line_stripped.find(api_name)
                locations.append((line_num, col))
                usage_type = "type_annotation"
                confidence = 0.7
                continue

        return confidence, usage_type, locations

    def extract_crate_name(self, module_path: str) -> str | None:
        """Extract crate name from module path."""
        if not module_path:
            return None
        return module_path.split("::")[0]
