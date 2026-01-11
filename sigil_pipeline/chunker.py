"""
Semantic chunking module for Rust source files.

Splits Rust files into semantic units (functions, impl blocks, modules) for Phase-2 dataset.
Uses tree-sitter-rust for accurate parsing.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.6.0
"""

import logging
from typing import Any

import tree_sitter_rust as tst_rust
from tree_sitter import Language, Parser

logger = logging.getLogger(__name__)


def chunk_rust_file(
    code: str, max_lines: int = 200, max_chars: int = 8000
) -> list[dict[str, Any]]:
    """
    Chunk a Rust file into semantic units using tree-sitter AST.

    Args:
        code: Rust source code
        max_lines: Maximum lines per chunk
        max_chars: Maximum characters per chunk

    Returns:
        List of chunk dictionaries with keys:
        - code: Chunk content
        - type: "function", "impl_block", "module", "struct", "enum", "trait", etc.
        - start_line: Starting line number (1-indexed)
        - end_line: Ending line number (1-indexed)
    """
    # tree-sitter 0.22+ API: wrap PyCapsule with Language, then pass to Parser
    rust_language = Language(tst_rust.language())
    parser = Parser(rust_language)

    tree = parser.parse(bytes(code, "utf8"))
    root_node = tree.root_node

    chunks: list[dict[str, Any]] = []
    code_bytes = code.encode("utf-8")

    def extract_node_text(node: Any) -> str:
        """Extract text for a node."""
        start_byte = node.start_byte
        end_byte = node.end_byte
        if start_byte < 0:
            start_byte = 0
        if end_byte < start_byte:
            end_byte = start_byte
        if end_byte > len(code_bytes):
            end_byte = len(code_bytes)
        chunk = code_bytes[start_byte:end_byte]
        try:
            return chunk.decode("utf-8")
        except UnicodeDecodeError:
            return chunk.decode("utf-8", errors="ignore")

    def get_line_range(node: Any) -> tuple[int, int]:
        """Get line range for a node (1-indexed)."""
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        return start_line, end_line

    def should_include_chunk(chunk_code: str, chunk_lines: int) -> bool:
        """Check if chunk meets size requirements."""
        if len(chunk_code) > max_chars:
            return False
        if chunk_lines > max_lines:
            return False
        return True

    def process_node(node: Any, depth: int = 0) -> None:
        """Recursively process AST nodes."""
        node_type = node.type

        # Extract semantic units
        if node_type == "function_item":
            chunk_code = extract_node_text(node)
            start_line, end_line = get_line_range(node)
            chunk_lines = end_line - start_line + 1

            if should_include_chunk(chunk_code, chunk_lines):
                chunks.append(
                    {
                        "code": chunk_code.strip(),
                        "type": "function",
                        "start_line": start_line,
                        "end_line": end_line,
                    }
                )
            # Don't recurse into function body

        elif node_type == "impl_item":
            chunk_code = extract_node_text(node)
            start_line, end_line = get_line_range(node)
            chunk_lines = end_line - start_line + 1

            # Count methods in impl block
            method_count = len(
                [child for child in node.children if child.type == "function_item"]
            )

            # Only include small impl blocks (max 5 methods)
            if method_count <= 5 and should_include_chunk(chunk_code, chunk_lines):
                chunks.append(
                    {
                        "code": chunk_code.strip(),
                        "type": "impl_block",
                        "start_line": start_line,
                        "end_line": end_line,
                    }
                )
            # Recurse to extract individual methods if impl is too large
            else:
                for child in node.children:
                    if child.type == "function_item":
                        process_node(child, depth + 1)

        elif node_type in ("struct_item", "enum_item", "trait_item", "type_item"):
            chunk_code = extract_node_text(node)
            start_line, end_line = get_line_range(node)
            chunk_lines = end_line - start_line + 1

            if should_include_chunk(chunk_code, chunk_lines):
                type_name = node_type.replace("_item", "")
                chunks.append(
                    {
                        "code": chunk_code.strip(),
                        "type": type_name,
                        "start_line": start_line,
                        "end_line": end_line,
                    }
                )

        elif node_type == "mod_item":
            # For modules, extract top-level items
            # Only include small modules (max 10 items)
            item_count = len(
                [
                    child
                    for child in node.children
                    if child.type
                    in (
                        "function_item",
                        "struct_item",
                        "enum_item",
                        "trait_item",
                        "impl_item",
                    )
                ]
            )

            if item_count <= 10:
                chunk_code = extract_node_text(node)
                start_line, end_line = get_line_range(node)
                chunk_lines = end_line - start_line + 1

                if should_include_chunk(chunk_code, chunk_lines):
                    chunks.append(
                        {
                            "code": chunk_code.strip(),
                            "type": "module",
                            "start_line": start_line,
                            "end_line": end_line,
                        }
                    )
            else:
                # Recurse into module to extract individual items
                for child in node.children:
                    process_node(child, depth + 1)

        else:
            # Recurse into other node types
            for child in node.children:
                process_node(child, depth + 1)

    # Process the root node
    process_node(root_node)

    return chunks
