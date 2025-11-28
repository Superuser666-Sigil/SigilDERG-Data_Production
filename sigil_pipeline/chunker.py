"""
Semantic chunking module for Rust source files.

Splits Rust files into semantic units (functions, impl blocks, modules) for Phase-2 dataset.
Uses tree-sitter-rust for accurate parsing, with regex fallback.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.0.0
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Try to import tree-sitter-rust
try:
    import tree_sitter_rust as tst_rust
    from tree_sitter import Parser

    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    logger.warning(
        "tree-sitter-rust not available. Using regex-based chunking (less accurate). "
        "Install with: pip install tree-sitter-rust"
    )


def chunk_rust_file(
    code: str, max_lines: int = 200, max_chars: int = 8000
) -> list[dict[str, Any]]:
    """
    Chunk a Rust file into semantic units.

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
    if TREE_SITTER_AVAILABLE:
        return _chunk_with_tree_sitter(code, max_lines, max_chars)
    else:
        return _chunk_with_regex(code, max_lines, max_chars)


def _chunk_with_tree_sitter(
    code: str, max_lines: int, max_chars: int
) -> list[dict[str, Any]]:
    """Chunk using tree-sitter-rust parser."""
    try:
        parser = Parser()
        parser.set_language(tst_rust.language())  # type: ignore[attr-defined]

        tree = parser.parse(bytes(code, "utf8"))
        root_node = tree.root_node

        chunks = []

        def extract_node_text(node) -> str:
            """Extract text for a node."""
            start_byte = node.start_byte
            end_byte = node.end_byte
            return code[start_byte:end_byte]

        def get_line_range(node) -> tuple[int, int]:
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

        def process_node(node, depth: int = 0):
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

    except Exception as e:
        logger.warning(
            f"Tree-sitter parsing failed: {e}. Falling back to regex chunking."
        )
        return _chunk_with_regex(code, max_lines, max_chars)


def _chunk_with_regex(
    code: str, max_lines: int, max_chars: int
) -> list[dict[str, Any]]:
    """Fallback regex-based chunking (less accurate but works without tree-sitter)."""
    chunks = []

    # Pattern for function definitions
    fn_pattern = re.compile(
        r"^(?:pub\s+)?(?:async\s+)?fn\s+\w+\s*\([^)]*\)\s*(?:->\s*[^{]+)?\s*\{",
        re.MULTILINE,
    )

    # Pattern for struct/enum/trait definitions
    type_pattern = re.compile(
        r"^(?:pub\s+)?(?:struct|enum|trait|type)\s+\w+",
        re.MULTILINE,
    )

    # Pattern for impl blocks
    impl_pattern = re.compile(r"^(?:pub\s+)?impl\s+(?:\w+::)*\w+", re.MULTILINE)

    def find_matching_brace(start_pos: int) -> int:
        """Find matching closing brace for opening brace at start_pos."""
        depth = 0
        pos = start_pos
        while pos < len(code):
            if code[pos] == "{":
                depth += 1
            elif code[pos] == "}":
                depth -= 1
                if depth == 0:
                    return pos
            pos += 1
        return -1

    def get_line_number(pos: int) -> int:
        """Get 1-indexed line number for character position."""
        return code[:pos].count("\n") + 1

    # Extract functions
    for match in fn_pattern.finditer(code):
        start_pos = match.start()
        # Find the opening brace
        brace_pos = code.find("{", start_pos)
        if brace_pos == -1:
            continue

        end_pos = find_matching_brace(brace_pos)
        if end_pos == -1:
            continue

        chunk_code = code[start_pos : end_pos + 1]
        start_line = get_line_number(start_pos)
        end_line = get_line_number(end_pos)
        chunk_lines = end_line - start_line + 1

        if len(chunk_code) <= max_chars and chunk_lines <= max_lines:
            chunks.append(
                {
                    "code": chunk_code.strip(),
                    "type": "function",
                    "start_line": start_line,
                    "end_line": end_line,
                }
            )

    # Extract structs/enums/traits
    for match in type_pattern.finditer(code):
        start_pos = match.start()
        # Find the opening brace or semicolon
        brace_pos = code.find("{", start_pos)
        semicolon_pos = code.find(";", start_pos)

        if brace_pos != -1 and (semicolon_pos == -1 or brace_pos < semicolon_pos):
            end_pos = find_matching_brace(brace_pos)
            if end_pos == -1:
                continue
        elif semicolon_pos != -1:
            end_pos = semicolon_pos
        else:
            continue

        chunk_code = code[start_pos : end_pos + 1]
        start_line = get_line_number(start_pos)
        end_line = get_line_number(end_pos)
        chunk_lines = end_line - start_line + 1

        if len(chunk_code) <= max_chars and chunk_lines <= max_lines:
            type_name = (
                "struct"
                if "struct" in match.group()
                else (
                    "enum"
                    if "enum" in match.group()
                    else "trait" if "trait" in match.group() else "type"
                )
            )
            chunks.append(
                {
                    "code": chunk_code.strip(),
                    "type": type_name,
                    "start_line": start_line,
                    "end_line": end_line,
                }
            )

    # Extract impl blocks (simplified - just find impl keyword and matching brace)
    for match in impl_pattern.finditer(code):
        start_pos = match.start()
        brace_pos = code.find("{", start_pos)
        if brace_pos == -1:
            continue

        end_pos = find_matching_brace(brace_pos)
        if end_pos == -1:
            continue

        chunk_code = code[start_pos : end_pos + 1]
        start_line = get_line_number(start_pos)
        end_line = get_line_number(end_pos)
        chunk_lines = end_line - start_line + 1

        # Count methods (rough estimate)
        method_count = chunk_code.count("fn ")

        if (
            method_count <= 5
            and len(chunk_code) <= max_chars
            and chunk_lines <= max_lines
        ):
            chunks.append(
                {
                    "code": chunk_code.strip(),
                    "type": "impl_block",
                    "start_line": start_line,
                    "end_line": end_line,
                }
            )

    return chunks
