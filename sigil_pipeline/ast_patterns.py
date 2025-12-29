"""AST-like pattern utilities for Rust source used in tests.

This module prefers tree-sitter parsing when available for stricter extraction,
falling back to regex-based heuristics when parsing is unavailable or fails.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, List


_TREE_SITTER_PARSER: Any | None = None


def _get_ts_parser() -> Any | None:
    """Return a cached tree-sitter Parser when available."""
    global _TREE_SITTER_PARSER
    if _TREE_SITTER_PARSER is not None:
        return _TREE_SITTER_PARSER
    try:
        import tree_sitter_rust as tst_rust
        from tree_sitter import Language, Parser
    except Exception:
        return None
    try:
        rust_language = Language(tst_rust.language())
        try:
            parser = Parser(rust_language)
        except TypeError:
            parser = Parser()
            parser.set_language(rust_language)  # type: ignore[attr-defined]
        _TREE_SITTER_PARSER = parser
        return _TREE_SITTER_PARSER
    except Exception:
        return None


def _get_parser() -> object:
    """Return a parser object (tree-sitter when available)."""
    parser = _get_ts_parser()
    return parser if parser is not None else object()


def _extract_node_text(code_str: str, node: Any) -> str:
    """Fallback node text extractor for compatibility; when real
    tree-sitter nodes are not used, this behaves as a simple slice
    helper (node must have start_byte/end_byte attributes).
    """
    try:
        code_bytes = code_str.encode("utf-8")
        chunk = code_bytes[node.start_byte : node.end_byte]
        try:
            return chunk.decode("utf-8")
        except UnicodeDecodeError:
            return chunk.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _iter_nodes(node: Any) -> Any:
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        children = getattr(current, "children", None)
        if children:
            stack.extend(reversed(children))


def _parse_params_text(params_text: str) -> list[tuple]:
    params: list[tuple] = []
    inner = params_text.strip()
    if inner.startswith("(") and inner.endswith(")"):
        inner = inner[1:-1]
    if not inner:
        return params
    for p in _split_top_level(inner, ","):
        p = p.strip()
        if not p:
            continue
        if ":" in p:
            n, t = p.split(":", 1)
            params.append((n.strip(), t.strip()))
        else:
            params.append((p, ""))
    return params


def _find_child_by_type(node: Any, node_type: str) -> Any | None:
    for child in getattr(node, "children", []):
        if child.type == node_type:
            return child
    return None


def _find_return_type_node(node: Any) -> Any | None:
    arrow_seen = False
    for child in getattr(node, "children", []):
        if child.type == "->":
            arrow_seen = True
            continue
        if arrow_seen and getattr(child, "is_named", True):
            return child
    return None


def _extract_function_signature_ts(code: str) -> tuple[FunctionSignature | None, bool]:
    parser = _get_ts_parser()
    if not parser or not code:
        return None, False
    try:
        tree = parser.parse(code.encode("utf-8"))
    except Exception:
        return None, False
    if getattr(tree.root_node, "has_error", False):
        return None, False
    for node in _iter_nodes(tree.root_node):
        if node.type == "function_item":
            return _function_signature_from_node(code, node), True
    return None, True


def _function_signature_from_node(code: str, node: Any) -> FunctionSignature | None:
    name_node = node.child_by_field_name("name") if hasattr(node, "child_by_field_name") else None
    if not name_node:
        name_node = _find_child_by_type(node, "identifier")
    if not name_node:
        return None
    name = _extract_node_text(code, name_node).strip()
    if not name:
        return None

    is_pub = any(child.type == "visibility_modifier" for child in node.children)
    is_async = any(child.type == "async" for child in node.children)
    if not is_async:
        signature_text = _extract_node_text(code, node)
        is_async = bool(re.search(r"\basync\s+fn\b", signature_text))

    generics_node = (
        node.child_by_field_name("type_parameters") if hasattr(node, "child_by_field_name") else None
    )
    if not generics_node:
        generics_node = _find_child_by_type(node, "type_parameters")
    generics = _extract_node_text(code, generics_node).strip() if generics_node else None

    params_node = node.child_by_field_name("parameters") if hasattr(node, "child_by_field_name") else None
    if not params_node:
        params_node = _find_child_by_type(node, "parameters")
    params_text = _extract_node_text(code, params_node) if params_node else ""
    params = _parse_params_text(params_text)

    return_type_node = (
        node.child_by_field_name("return_type") if hasattr(node, "child_by_field_name") else None
    )
    if not return_type_node:
        return_type_node = _find_return_type_node(node)
    return_type = _extract_node_text(code, return_type_node).strip() if return_type_node else None

    where_node = node.child_by_field_name("where_clause") if hasattr(node, "child_by_field_name") else None
    if not where_node:
        where_node = _find_child_by_type(node, "where_clause")
    where_clause = _extract_node_text(code, where_node).strip() if where_node else None

    lifetime_source = " ".join(
        part
        for part in (generics or "", params_text, return_type or "", where_clause or "")
        if part
    )
    lifetimes = re.findall(r"'[A-Za-z_][A-Za-z0-9_]*", lifetime_source)

    return FunctionSignature(
        name=name,
        is_pub=is_pub,
        is_async=is_async,
        params=params,
        return_type=return_type,
        generics=generics,
        lifetimes=lifetimes,
        where_clause=where_clause,
    )


@dataclass
class APIEntity:
    name: str
    entity_type: str
    signature: str
    module_path: str = ""
    documentation: str = ""
    examples: List[str] = field(default_factory=list)
    source_code: str = ""
    attributes: dict = field(default_factory=dict)
    is_pub: bool = False


@dataclass
class FunctionSignature:
    name: str
    is_pub: bool = False
    is_async: bool = False
    params: List[tuple] = field(default_factory=list)
    return_type: str | None = None
    generics: str | None = None
    lifetimes: List[str] = field(default_factory=list)
    where_clause: str | None = None


@dataclass
class StructField:
    name: str
    field_type: str
    is_pub: bool = False


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
    # A lightweight implementation: collect use statements and top-level
    # type declarations by simple regexes. This is sufficient for tests.
    parts: List[str] = []

    # Collect `use ...;` statements
    for m in re.finditer(r"^\s*use\s+[^;]+;", code, flags=re.MULTILINE):
        parts.append(m.group(0).strip())

    # Collect pub struct/enum/type definitions header (first line)
    for m in re.finditer(r"^\s*(pub\s+)?(struct|enum|type)\s+\w+[^{;]*\{?", code, flags=re.MULTILINE):
        parts.append(m.group(0).strip())

    return "\n\n".join(parts)


def extract_function_signature(code: str) -> FunctionSignature | None:
    """Extract the first function signature found in code.

    This is a forgiving regex-based extractor used for tests.
    """
    if not code or "fn" not in code:
        return None

    ts_sig, parsed_clean = _extract_function_signature_ts(code)
    if parsed_clean:
        return ts_sig

    # Remove comments and string literals to reduce false positives
    cleaned = _strip_comments_and_strings(code)

    # Match optional pub, optional async, fn name, optional generics, params, optional return
    m = re.search(
        r"\b(pub\s+)?(async\s+)?fn\s+([A-Za-z_][A-Za-z0-9_]*)\s*(<[^>]+>)?\s*\(([^)]*)\)\s*(->\s*([^\s{]+))?",
        cleaned,
    )
    if not m:
        return None

    is_pub = bool(m.group(1))
    is_async = bool(m.group(2))
    name = m.group(3)
    generics = m.group(4)
    params_raw = m.group(5).strip()
    return_type = m.group(7)

    params = []
    if params_raw:
        params = _parse_params_text(f"({params_raw})")

    # lifetimes: find occurrences like '"'a'' in generics or params
    lifetimes = re.findall(r"'\w+", cleaned)

    return FunctionSignature(
        name=name,
        is_pub=is_pub,
        is_async=is_async,
        params=params,
        return_type=return_type,
        generics=generics,
        lifetimes=lifetimes,
    )


def extract_all_function_signatures(code: str) -> list[FunctionSignature]:
    parser = _get_ts_parser()
    if parser and code:
        try:
            tree = parser.parse(code.encode("utf-8"))
        except Exception:
            tree = None
        if tree and not getattr(tree.root_node, "has_error", False):
            results: list[FunctionSignature] = []
            for node in _iter_nodes(tree.root_node):
                if node.type == "function_item":
                    sig = _function_signature_from_node(code, node)
                    if sig:
                        results.append(sig)
            return results

    cleaned = _strip_comments_and_strings(code)
    results = []
    for m in re.finditer(
        r"\b(pub\s+)?(async\s+)?fn\s+([A-Za-z_][A-Za-z0-9_]*)\s*(<[^>]+>)?\s*\(([^)]*)\)\s*(->\s*([^\s{]+))?",
        cleaned,
    ):
        is_pub = bool(m.group(1))
        is_async = bool(m.group(2))
        name = m.group(3)
        generics = m.group(4)
        params_raw = m.group(5).strip()
        return_type = m.group(7)
        params = []
        if params_raw:
            params = _parse_params_text(f"({params_raw})")
        results.append(
            FunctionSignature(
                name=name,
                is_pub=is_pub,
                is_async=is_async,
                params=params,
                return_type=return_type,
                generics=generics,
            )
        )
    return results


def extract_struct_fields(code: str) -> list[StructField]:
    parser = _get_ts_parser()
    if parser and code:
        try:
            tree = parser.parse(code.encode("utf-8"))
        except Exception:
            tree = None
        if tree and not getattr(tree.root_node, "has_error", False):
            for node in _iter_nodes(tree.root_node):
                if node.type == "struct_item":
                    fields_node = _find_child_by_type(node, "field_declaration_list")
                    if not fields_node:
                        return []
                    fields: list[StructField] = []
                    for child in getattr(fields_node, "children", []):
                        if child.type != "field_declaration":
                            continue
                        is_pub = any(
                            field_child.type == "visibility_modifier"
                            for field_child in child.children
                        )
                        name_node = (
                            child.child_by_field_name("name")
                            if hasattr(child, "child_by_field_name")
                            else None
                        )
                        if not name_node:
                            name_node = _find_child_by_type(child, "field_identifier")
                        type_node = (
                            child.child_by_field_name("type")
                            if hasattr(child, "child_by_field_name")
                            else None
                        )
                        name = _extract_node_text(code, name_node).strip() if name_node else ""
                        field_type = _extract_node_text(code, type_node).strip() if type_node else ""
                        if not (name and field_type):
                            field_text = _extract_node_text(code, child).strip().rstrip(",")
                            if ":" in field_text:
                                left, right = field_text.split(":", 1)
                                left = re.sub(r"^pub(\([^)]*\))?\s+", "", left.strip())
                                name = name or left.strip()
                                field_type = field_type or right.strip()
                        if name and field_type:
                            fields.append(
                                StructField(name=name, field_type=field_type, is_pub=is_pub)
                            )
                    return fields
            return []

    cleaned = _strip_comments_and_strings(code)
    m = re.search(r"struct\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{([^}]*)\}", cleaned, flags=re.DOTALL)
    if not m:
        return []
    body = m.group(2)
    fields = []
    for line in body.splitlines():
        line = line.strip().rstrip(',')
        if not line:
            continue
        is_pub = line.startswith('pub ')
        if is_pub:
            line = line[4:]
        if ':' in line:
            name, typ = line.split(':', 1)
            fields.append(StructField(name=name.strip(), field_type=typ.strip(), is_pub=is_pub))
    return fields


def extract_struct_name(code: str) -> str | None:
    parser = _get_ts_parser()
    if parser and code:
        try:
            tree = parser.parse(code.encode("utf-8"))
        except Exception:
            tree = None
        if tree and not getattr(tree.root_node, "has_error", False):
            for node in _iter_nodes(tree.root_node):
                if node.type == "struct_item":
                    name_node = (
                        node.child_by_field_name("name")
                        if hasattr(node, "child_by_field_name")
                        else None
                    )
                    if not name_node:
                        name_node = _find_child_by_type(node, "type_identifier")
                    if name_node:
                        name = _extract_node_text(code, name_node).strip()
                        if name:
                            return name
                    return None
            return None

    m = re.search(r"struct\s+([A-Za-z_][A-Za-z0-9_]*)", code)
    if not m:
        return None
    return m.group(1)


def detect_code_patterns_ast(code: str) -> dict:
    """Detect simple code patterns using regex heuristics.

    Returns a dict with boolean flags and list of function names.
    """
    cleaned = _strip_comments_and_strings(code)
    patterns = {}
    function_names: list[str] = []
    has_async = None
    parsed_clean = False
    parser = _get_ts_parser()
    if parser and code:
        try:
            tree = parser.parse(code.encode("utf-8"))
        except Exception:
            tree = None
        if tree and not getattr(tree.root_node, "has_error", False):
            parsed_clean = True
            has_async = False
            for node in _iter_nodes(tree.root_node):
                if node.type == "function_item":
                    name_node = (
                        node.child_by_field_name("name")
                        if hasattr(node, "child_by_field_name")
                        else None
                    )
                    if not name_node:
                        name_node = _find_child_by_type(node, "identifier")
                    if name_node:
                        name = _extract_node_text(code, name_node).strip()
                        if name:
                            function_names.append(name)
                    if any(child.type == "async" for child in node.children):
                        has_async = True
                    else:
                        node_text = _extract_node_text(code, node)
                        if re.search(r"\basync\s+fn\b", node_text):
                            has_async = True
    if not function_names and not parsed_clean:
        function_names = re.findall(r"\bfn\s+([A-Za-z_][A-Za-z0-9_]*)", cleaned)
    patterns['function_names'] = function_names
    patterns['has_main'] = 'main' in patterns['function_names']
    if has_async is None:
        has_async = bool(re.search(r"\basync\s+fn\b", cleaned))
    patterns['has_async'] = has_async
    patterns['has_serde'] = bool(re.search(r"Serialize|Deserialize|derive\s*\(.*Serialize|Deserialize", code))
    patterns['has_error_handling'] = bool(re.search(r"\bResult\b|\?", cleaned))
    patterns['has_iterators'] = bool(re.search(r"\.iter\(|\.map\(|\.filter\(|\.collect\(", cleaned))
    patterns['has_collections'] = bool(re.search(r"\bHashMap\b|\bVec\b", cleaned))
    patterns['has_io'] = bool(re.search(r"std::fs|File::open|use\s+std::fs", cleaned))
    patterns['has_concurrency'] = bool(re.search(r"\bArc\b|\bMutex\b|\bRwLock\b", cleaned))
    patterns['has_traits'] = bool(re.search(r"\btrait\s+", cleaned))
    patterns['has_impl_blocks'] = bool(re.search(r"\bimpl\s+", cleaned))
    patterns['has_unsafe'] = bool(re.search(r"\bunsafe\b", cleaned))
    patterns['has_closures'] = bool(re.search(r"\|[^|]+\|", cleaned))
    patterns['has_macros'] = bool(re.search(r"macro_rules!|!\w+", code))
    return patterns


def get_detected_pattern_descriptions(patterns: dict) -> list[str]:
    desc = []
    if patterns.get('has_async'):
        desc.append('asynchronous operations')
    if patterns.get('has_serde'):
        desc.append('Serde serialization/deserialization')
    if patterns.get('has_error_handling'):
        desc.append('error handling with Result types')
    if patterns.get('has_iterators'):
        desc.append('iterator and functional-style processing')
    return desc


def check_function_in_code(code: str, signature: str) -> bool:
    """Check whether a function matching the signature exists.

    This implements a permissive match: it requires the 'fn name' and
    basic parameter pattern to appear in the code. If signature lacks
    the 'fn' keyword, return False.
    """
    if 'fn' not in signature:
        return False
    # extract name from signature
    m = re.search(r"fn\s+([A-Za-z_][A-Za-z0-9_]*)", signature)
    if not m:
        return False
    name = m.group(1)

    parser = _get_ts_parser()
    if parser and code:
        try:
            tree = parser.parse(code.encode("utf-8"))
        except Exception:
            tree = None
        if tree and not getattr(tree.root_node, "has_error", False):
            for node in _iter_nodes(tree.root_node):
                if node.type == "function_item":
                    name_node = (
                        node.child_by_field_name("name")
                        if hasattr(node, "child_by_field_name")
                        else None
                    )
                    if not name_node:
                        name_node = _find_child_by_type(node, "identifier")
                    if name_node:
                        fn_name = _extract_node_text(code, name_node).strip()
                        if fn_name == name:
                            return True
            return False

    return bool(re.search(rf"\bfn\s+{re.escape(name)}\b", _strip_comments_and_strings(code)))


def extract_all_api_entities(code: str) -> list[APIEntity]:
    cleaned = _strip_comments_and_strings(code)
    entities: list[APIEntity] = []
    # pub fn
    for m in re.finditer(r"pub\s+fn\s+([A-Za-z_][A-Za-z0-9_]*)", cleaned):
        name = m.group(1)
        sig = _extract_surrounding_signature(cleaned, name)
        doc = _extract_doc_before(code, m.start())
        entities.append(APIEntity(name=name, entity_type='function', signature=sig, documentation=doc, is_pub=True))

    # pub struct
    for m in re.finditer(r"pub\s+struct\s+([A-Za-z_][A-Za-z0-9_]*)", cleaned):
        name = m.group(1)
        sig = f"struct {name}"
        doc = _extract_doc_before(code, m.start())
        entities.append(APIEntity(name=name, entity_type='struct', signature=sig, documentation=doc, is_pub=True))

    # pub enum
    for m in re.finditer(r"pub\s+enum\s+([A-Za-z_][A-Za-z0-9_]*)", cleaned):
        name = m.group(1)
        sig = f"enum {name}"
        doc = _extract_doc_before(code, m.start())
        entities.append(APIEntity(name=name, entity_type='enum', signature=sig, documentation=doc, is_pub=True))

    # pub trait
    for m in re.finditer(r"pub\s+trait\s+([A-Za-z_][A-Za-z0-9_]*)", cleaned):
        name = m.group(1)
        sig = f"trait {name}"
        doc = _extract_doc_before(code, m.start())
        entities.append(APIEntity(name=name, entity_type='trait', signature=sig, documentation=doc, is_pub=True))

    return entities


def _strip_comments_and_strings(code: str) -> str:
    # remove block comments
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
    # remove line comments
    code = re.sub(r"//.*?$", "", code, flags=re.MULTILINE)
    # remove string literals
    code = re.sub(r'"(?:\\.|[^"\\])*"', '""', code)
    return code


def _split_top_level(s: str, sep: str) -> list[str]:
    """Split on sep but ignore separators inside angle brackets or parentheses."""
    parts = []
    buf = []
    depth_angle = 0
    depth_paren = 0
    for ch in s:
        if ch == '<':
            depth_angle += 1
        elif ch == '>':
            if depth_angle > 0:
                depth_angle -= 1
        elif ch == '(':
            depth_paren += 1
        elif ch == ')':
            if depth_paren > 0:
                depth_paren -= 1
        if ch == sep and depth_angle == 0 and depth_paren == 0:
            parts.append(''.join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append(''.join(buf))
    return parts


def _extract_surrounding_signature(code: str, name: str) -> str:
    m = re.search(rf"(pub\s+fn\s+{re.escape(name)}[^{{;\n]*)", code)
    return m.group(1).strip() if m else f"fn {name}"


def _extract_doc_before(code: str, pos: int) -> str:
    # find preceding lines of /// or //! comments
    lines = code[:pos].rstrip('\n').splitlines()
    docs = []
    for line in reversed(lines[-10:]):
        if line.strip().startswith('///') or line.strip().startswith('//!'):
            docs.append(re.sub(r"^\s*(///|//!\s*)", "", line).strip())
        elif line.strip() == '':
            continue
        else:
            break
    return '\n'.join(reversed(docs)).strip()
