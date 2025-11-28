"""
AST-based pattern extraction module for Rust code.

Uses tree-sitter-rust for robust parsing of function signatures, struct fields,
and code patterns. This replaces fragile regex-based extraction that fails on
nested generics, macros, and comments.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.2.0
"""

import logging
from dataclasses import dataclass, field
from typing import Any

import tree_sitter_rust as tst_rust
from tree_sitter import Language, Parser

logger = logging.getLogger(__name__)


@dataclass
class FunctionSignature:
    """Represents a parsed Rust function signature."""

    name: str
    """Function name."""

    params: list[tuple[str, str]]
    """List of (param_name, param_type) tuples."""

    return_type: str | None
    """Return type string, or None if unit type."""

    is_async: bool = False
    """Whether the function is async."""

    is_pub: bool = False
    """Whether the function is public."""

    generics: str | None = None
    """Generic parameters string (e.g., '<T: Clone, U>')."""

    where_clause: str | None = None
    """Where clause string, if present."""

    lifetimes: list[str] = field(default_factory=list)
    """List of lifetime parameters."""


@dataclass
class StructField:
    """Represents a parsed Rust struct field."""

    name: str
    """Field name."""

    field_type: str
    """Field type string."""

    is_pub: bool = False
    """Whether the field is public."""


def _get_parser() -> Parser:
    """Create and configure a tree-sitter parser for Rust."""
    # tree-sitter 0.22+ API: wrap PyCapsule with Language, then pass to Parser
    rust_language = Language(tst_rust.language())
    return Parser(rust_language)


def _extract_node_text(code: str, node: Any) -> str:
    """Extract text for a tree-sitter node."""
    return code[node.start_byte : node.end_byte]


def extract_function_signature(code: str) -> FunctionSignature | None:
    """
    Extract function signature from Rust code using tree-sitter AST.

    Handles complex signatures including:
    - Generics with trait bounds
    - Lifetimes
    - Where clauses
    - Async functions
    - Nested generic types in parameters

    Args:
        code: Rust source code containing a function

    Returns:
        FunctionSignature if a function is found, None otherwise
    """
    parser = _get_parser()
    tree = parser.parse(bytes(code, "utf8"))
    root = tree.root_node

    # Find first function_item in the AST
    fn_node = _find_first_node_of_type(root, "function_item")
    if fn_node is None:
        return None

    return _parse_function_node(code, fn_node)


def extract_all_function_signatures(code: str) -> list[FunctionSignature]:
    """
    Extract all function signatures from Rust code.

    Args:
        code: Rust source code

    Returns:
        List of FunctionSignature objects
    """
    parser = _get_parser()
    tree = parser.parse(bytes(code, "utf8"))
    root = tree.root_node

    signatures = []
    for node in _find_all_nodes_of_type(root, "function_item"):
        sig = _parse_function_node(code, node)
        if sig:
            signatures.append(sig)

    return signatures


def _find_first_node_of_type(node: Any, node_type: str) -> Any | None:
    """Recursively find first node of given type."""
    if node.type == node_type:
        return node
    for child in node.children:
        result = _find_first_node_of_type(child, node_type)
        if result is not None:
            return result


def _find_all_lifetimes(node: Any, code: str) -> list[str]:
    """Recursively find all lifetime nodes and extract their text."""
    lifetimes = []
    if node.type == "lifetime":
        lifetimes.append(_extract_node_text(code, node))
    for child in node.children:
        lifetimes.extend(_find_all_lifetimes(child, code))
    return lifetimes
    return None


def _find_all_nodes_of_type(node: Any, node_type: str) -> list[Any]:
    """Recursively find all nodes of given type."""
    results = []
    if node.type == node_type:
        results.append(node)
    for child in node.children:
        results.extend(_find_all_nodes_of_type(child, node_type))
    return results


def _parse_function_node(code: str, fn_node: Any) -> FunctionSignature | None:
    """Parse a function_item node into a FunctionSignature."""
    name = None
    params: list[tuple[str, str]] = []
    return_type = None
    is_async = False
    is_pub = False
    generics = None
    where_clause = None
    lifetimes: list[str] = []

    # Track if we've seen "->" to capture return type
    saw_arrow = False

    for child in fn_node.children:
        if child.type == "visibility_modifier":
            is_pub = "pub" in _extract_node_text(code, child)
        elif child.type == "function_modifiers":
            modifier_text = _extract_node_text(code, child)
            is_async = "async" in modifier_text
        elif child.type == "identifier" and name is None:
            name = _extract_node_text(code, child)
        elif child.type == "type_parameters":
            generics = _extract_node_text(code, child)
            # Extract lifetimes from generics (recursively, as they're nested)
            lifetimes = _find_all_lifetimes(child, code)
        elif child.type == "parameters":
            params = _parse_parameters(code, child)
        elif child.type == "->":
            saw_arrow = True
        elif (
            saw_arrow
            and return_type is None
            and child.type not in ("block", "where_clause")
        ):
            # The node after "->" is the return type (before block/where_clause)
            return_type = _extract_node_text(code, child)
        elif child.type == "where_clause":
            where_clause = _extract_node_text(code, child)

    if name is None:
        return None

    return FunctionSignature(
        name=name,
        params=params,
        return_type=return_type,
        is_async=is_async,
        is_pub=is_pub,
        generics=generics,
        where_clause=where_clause,
        lifetimes=lifetimes,
    )


def _parse_parameters(code: str, params_node: Any) -> list[tuple[str, str]]:
    """Parse function parameters node into list of (name, type) tuples."""
    params: list[tuple[str, str]] = []

    for child in params_node.children:
        if child.type == "parameter":
            param_name = None
            param_type = None

            for pchild in child.children:
                if pchild.type == "identifier":
                    param_name = _extract_node_text(code, pchild)
                elif pchild.type in (
                    "type_identifier",
                    "generic_type",
                    "reference_type",
                    "primitive_type",
                    "tuple_type",
                    "array_type",
                    "pointer_type",
                    "function_type",
                    "scoped_type_identifier",
                ):
                    param_type = _extract_node_text(code, pchild)

            # Handle pattern parameters (e.g., `(a, b): (i32, i32)`)
            if param_name is None:
                pattern_node = _find_first_node_of_type(child, "tuple_pattern")
                if pattern_node:
                    param_name = _extract_node_text(code, pattern_node)

            if param_name and param_type:
                params.append((param_name, param_type))
            elif param_name:
                # Try to extract type from the full parameter text
                full_text = _extract_node_text(code, child)
                if ":" in full_text:
                    parts = full_text.split(":", 1)
                    param_type = parts[1].strip()
                    params.append((param_name, param_type))

        elif child.type == "self_parameter":
            self_text = _extract_node_text(code, child)
            params.append(("self", self_text))

    return params


def extract_struct_fields(code: str) -> list[StructField]:
    """
    Extract struct fields from Rust code using tree-sitter AST.

    Handles complex types including:
    - Nested generics (HashMap<String, Vec<i32>>)
    - Lifetimes in types
    - Visibility modifiers

    Args:
        code: Rust source code containing a struct

    Returns:
        List of StructField objects
    """
    parser = _get_parser()
    tree = parser.parse(bytes(code, "utf8"))
    root = tree.root_node

    # Find first struct_item
    struct_node = _find_first_node_of_type(root, "struct_item")
    if struct_node is None:
        return []

    # Find field_declaration_list
    field_list = _find_first_node_of_type(struct_node, "field_declaration_list")
    if field_list is None:
        return []

    fields: list[StructField] = []

    for child in field_list.children:
        if child.type == "field_declaration":
            field = _parse_field_declaration(code, child)
            if field:
                fields.append(field)

    return fields


def _parse_field_declaration(code: str, field_node: Any) -> StructField | None:
    """Parse a field_declaration node into a StructField."""
    name = None
    field_type = None
    is_pub = False

    for child in field_node.children:
        if child.type == "visibility_modifier":
            is_pub = "pub" in _extract_node_text(code, child)
        elif child.type == "field_identifier":
            name = _extract_node_text(code, child)
        elif child.type in (
            "type_identifier",
            "generic_type",
            "reference_type",
            "primitive_type",
            "tuple_type",
            "array_type",
            "pointer_type",
            "scoped_type_identifier",
        ):
            field_type = _extract_node_text(code, child)

    if name is None:
        return None

    # Fallback: extract type from full field text
    if field_type is None:
        full_text = _extract_node_text(code, field_node)
        if ":" in full_text:
            parts = full_text.split(":", 1)
            field_type = parts[1].strip().rstrip(",")

    if field_type is None:
        field_type = "Unknown"

    return StructField(name=name, field_type=field_type, is_pub=is_pub)


def extract_struct_name(code: str) -> str | None:
    """
    Extract the struct name from Rust code.

    Args:
        code: Rust source code containing a struct

    Returns:
        Struct name or None if not found
    """
    parser = _get_parser()
    tree = parser.parse(bytes(code, "utf8"))
    root = tree.root_node

    struct_node = _find_first_node_of_type(root, "struct_item")
    if struct_node is None:
        return None

    for child in struct_node.children:
        if child.type == "type_identifier":
            return _extract_node_text(code, child)

    return None


def detect_code_patterns_ast(code: str) -> dict[str, Any]:
    """
    Detect code patterns using tree-sitter AST analysis.

    This replaces regex-based pattern detection with more accurate AST-based
    detection that correctly handles:
    - Async functions and blocks
    - Serde derives (including in attribute macros)
    - Error handling (Result types, ? operator)
    - Iterator usage
    - Collection types
    - I/O operations
    - Networking
    - Concurrency primitives

    Args:
        code: Rust source code

    Returns:
        Dictionary of detected patterns
    """
    parser = _get_parser()
    tree = parser.parse(bytes(code, "utf8"))
    root = tree.root_node

    # Collect pattern flags
    patterns: dict[str, Any] = {
        "has_main": False,
        "has_async": False,
        "has_error_handling": False,
        "has_serde": False,
        "has_iterators": False,
        "has_collections": False,
        "has_strings": False,
        "has_io": False,
        "has_networking": False,
        "has_concurrency": False,
        "function_names": [],
        # Extended patterns
        "has_traits": False,
        "has_impl_blocks": False,
        "has_unsafe": False,
        "has_macros": False,
        "has_lifetimes": False,
        "has_closures": False,
    }

    # Walk the AST to detect patterns
    _detect_patterns_recursive(code, root, patterns)

    return patterns


def _detect_patterns_recursive(code: str, node: Any, patterns: dict[str, Any]) -> None:
    """Recursively walk AST to detect patterns."""
    node_type = node.type
    node_text = _extract_node_text(code, node)

    # Function detection
    if node_type == "function_item":
        # Extract function name
        for child in node.children:
            if child.type == "identifier":
                fn_name = _extract_node_text(code, child)
                patterns["function_names"].append(fn_name)
                if fn_name == "main":
                    patterns["has_main"] = True
                break

        # Check for async modifier
        for child in node.children:
            if child.type == "function_modifiers":
                if "async" in _extract_node_text(code, child):
                    patterns["has_async"] = True
                    break

    # Async blocks
    elif node_type == "async_block":
        patterns["has_async"] = True

    # Await expressions
    elif node_type == "await_expression":
        patterns["has_async"] = True

    # Attribute detection (for serde, tokio, etc.)
    elif node_type == "attribute_item" or node_type == "attribute":
        attr_text = node_text.lower()
        if "derive" in attr_text:
            if "serialize" in attr_text or "deserialize" in attr_text:
                patterns["has_serde"] = True
        if "tokio" in attr_text:
            patterns["has_async"] = True

    # Return type detection for error handling
    # Check generic_type, type_identifier nodes for Result/Option
    elif node_type in ("generic_type", "type_identifier", "scoped_type_identifier"):
        if "Result<" in node_text or node_text.startswith("Result"):
            patterns["has_error_handling"] = True
        if "Option<" in node_text or node_text.startswith("Option"):
            patterns["has_error_handling"] = True

    # Try expression (? operator)
    elif node_type == "try_expression":
        patterns["has_error_handling"] = True

    # Method calls for iterators
    elif node_type == "call_expression" or node_type == "method_call_expression":
        method_text = node_text
        # Iterator methods
        if any(
            m in method_text
            for m in [".iter()", ".map(", ".filter(", ".collect()", ".fold("]
        ):
            patterns["has_iterators"] = True
        # I/O methods
        if any(
            m in method_text
            for m in ["File::", "read_to_string", "write_all", "BufReader", "BufWriter"]
        ):
            patterns["has_io"] = True

    # Type detection for collections
    elif node_type == "generic_type" or node_type == "type_identifier":
        type_text = node_text
        # Collections
        if any(c in type_text for c in ["Vec<", "HashMap<", "HashSet<", "BTreeMap<"]):
            patterns["has_collections"] = True
        # Strings
        if "String" in type_text:
            patterns["has_strings"] = True
        # Concurrency
        if any(c in type_text for c in ["Arc<", "Mutex<", "RwLock<", "Rc<"]):
            patterns["has_concurrency"] = True
        # Networking types
        if any(
            n in type_text for n in ["TcpStream", "TcpListener", "UdpSocket", "Client"]
        ):
            patterns["has_networking"] = True

    # Use statements for imports
    elif node_type == "use_declaration":
        use_text = node_text
        if "std::io" in use_text or "std::fs" in use_text:
            patterns["has_io"] = True
        if "std::thread" in use_text or "std::sync" in use_text:
            patterns["has_concurrency"] = True
        if "std::collections" in use_text:
            patterns["has_collections"] = True
        if any(n in use_text for n in ["reqwest", "hyper", "tokio::net"]):
            patterns["has_networking"] = True
        if "serde" in use_text.lower():
            patterns["has_serde"] = True

    # Trait definitions
    elif node_type == "trait_item":
        patterns["has_traits"] = True

    # Impl blocks
    elif node_type == "impl_item":
        patterns["has_impl_blocks"] = True

    # Unsafe blocks/functions
    elif node_type == "unsafe_block":
        patterns["has_unsafe"] = True

    # Macro invocations and definitions
    elif node_type in ("macro_invocation", "macro_definition"):
        patterns["has_macros"] = True
        macro_text = node_text.lower()
        if "tokio::" in macro_text:
            patterns["has_async"] = True

    # Lifetime parameters
    elif node_type == "lifetime":
        patterns["has_lifetimes"] = True

    # Closures
    elif node_type == "closure_expression":
        patterns["has_closures"] = True

    # String literals and references
    elif node_type == "string_literal":
        patterns["has_strings"] = True

    elif node_type == "reference_type":
        if "&str" in node_text:
            patterns["has_strings"] = True

    # Recurse into children
    for child in node.children:
        _detect_patterns_recursive(code, child, patterns)


def get_detected_pattern_descriptions(patterns: dict[str, Any]) -> list[str]:
    """
    Convert detected patterns into human-readable descriptions.

    Args:
        patterns: Dictionary from detect_code_patterns_ast()

    Returns:
        List of description strings for detected patterns
    """
    descriptions = []

    if patterns.get("has_async"):
        descriptions.append("asynchronous operations")
    if patterns.get("has_serde"):
        descriptions.append("Serde serialization/deserialization")
    if patterns.get("has_error_handling"):
        descriptions.append("error handling with Result types")
    if patterns.get("has_iterators"):
        descriptions.append("iterator methods")
    if patterns.get("has_collections"):
        descriptions.append("collection types")
    if patterns.get("has_io"):
        descriptions.append("file I/O operations")
    if patterns.get("has_networking"):
        descriptions.append("networking")
    if patterns.get("has_concurrency"):
        descriptions.append("concurrency primitives")
    if patterns.get("has_traits"):
        descriptions.append("trait definitions")
    if patterns.get("has_unsafe"):
        descriptions.append("unsafe code")
    if patterns.get("has_lifetimes"):
        descriptions.append("lifetime annotations")
    if patterns.get("has_closures"):
        descriptions.append("closures")

    return descriptions
