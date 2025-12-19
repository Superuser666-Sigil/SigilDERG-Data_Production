import tree_sitter_rust as tst_rust
from tree_sitter import Language, Parser


def _get_parser() -> Parser:
    rust_language = Language(tst_rust.language())
    return Parser(rust_language)


def _extract_node_text(code: str, node) -> str:
    return code[node.start_byte : node.end_byte]


def extract_context_header(code: str) -> str:
    """
    Extracts imports and type definitions to provide context for a function.

    This creates the 'code_context' field seen in high-quality datasets by
    isolating dependencies and data structures without including implementation
    logic (impl blocks) or unrelated functions.

    Args:
        code: Full Rust source code

    Returns:
        String containing all use statements, structs, enums, constants, and macros.
    """
    # Local helpers for tree-sitter parsing are provided in this module.
    # Import here to avoid heavy dependency at module import time in tests.
    import tree_sitter_rust as tst_rust
    from tree_sitter import Language, Parser

    def _get_parser() -> Parser:
        """Create and return a Rust parser instance."""
        rust_language = Language(tst_rust.language())
        return Parser(rust_language)

    def _extract_node_text(code_str: str, node) -> str:
        """Extract the source text for a given AST node."""
        return code_str[node.start_byte : node.end_byte]

    parser = _get_parser()
    tree = parser.parse(bytes(code, "utf8"))
    root = tree.root_node

    context_parts = []

    # Iterate over top-level items
    for child in root.children:
        # We want to capture imports and type definitions
        if child.type == "use_declaration":
            context_parts.append(_extract_node_text(code, child))

        # Capture data structures (structs, enums, unions, type aliases)
        elif child.type in ("struct_item", "enum_item", "union_item", "type_item"):
            context_parts.append(_extract_node_text(code, child))

        # Capture constants and statics as they often define magic numbers/config
        elif child.type in ("const_item", "static_item"):
            context_parts.append(_extract_node_text(code, child))

        # Capture macro definitions (rules) but not necessarily invocations
        elif child.type == "macro_definition":
            context_parts.append(_extract_node_text(code, child))

    # Join with double newlines for readability in the LLM context window
    return "\n\n".join(context_parts)
