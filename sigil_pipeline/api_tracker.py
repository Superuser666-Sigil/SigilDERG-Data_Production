"""
API Evolution Tracking Module

Tracks API changes across Rust versions including stabilization, deprecation,
signature changes, and implicit behavioral changes.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.6.0
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tree_sitter_rust as tst_rust
from tree_sitter import Language, Parser

logger = logging.getLogger(__name__)


@dataclass
class APIEntity:
    """Represents a Rust API entity (function, struct, enum, trait, etc.)."""

    name: str
    """API name."""

    module: str
    """Module path (e.g., 'std::fs')."""

    entity_type: str
    """Type: function, struct, enum, trait, method, associated_function, macro."""

    signature: str
    """Full signature string."""

    documentation: str = ""
    """Documentation comments."""

    examples: list[str] = field(default_factory=list)
    """Example code blocks from documentation."""

    source_code: str = ""
    """Full source code of the entity."""

    attributes: dict[str, Any] = field(default_factory=dict)
    """Attributes like #[stable], #[deprecated], etc."""

    version: str = ""
    """Rust version where this entity was found."""


@dataclass
class APIChange:
    """Represents a detected API change between versions."""

    api: APIEntity
    """The changed API entity."""

    change_type: str
    """Type: stabilized, deprecated, signature, implicit."""

    from_version: str
    """Source version."""

    to_version: str
    """Target version."""

    details: str
    """Human-readable description of the change."""

    old_source_code: str = ""
    """Source code from the old version (if applicable)."""


class RustASTParser:
    """Tree-sitter based Rust AST parser for API extraction."""

    def __init__(self):
        """Initialize Tree-sitter parser."""
        try:
            rust_language = Language(tst_rust.language())
            self.parser = Parser(rust_language)
        except Exception as e:
            logger.error(f"Failed to initialize Rust parser: {e}")
            raise

    def parse_file(self, file_path: Path) -> list[APIEntity]:
        """
        Parse a Rust file and extract all public API entities.

        Args:
            file_path: Path to Rust source file

        Returns:
            List of extracted API entities
        """
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            tree = self.parser.parse(content.encode("utf-8"))
            root_node = tree.root_node

            entities: list[APIEntity] = []
            self._extract_entities(root_node, content, "", entities)

            return entities
        except Exception as e:
            logger.warning(f"Failed to parse {file_path}: {e}")
            return []

    def _extract_entities(
        self, node: Any, content: str, module_path: str, entities: list[APIEntity]
    ) -> None:
        """Recursively extract API entities from AST."""
        if node.type == "function_item":
            entity = self._parse_function(node, content, module_path)
            if entity:
                entities.append(entity)
        elif node.type == "struct_item":
            entity = self._parse_struct(node, content, module_path)
            if entity:
                entities.append(entity)
        elif node.type == "enum_item":
            entity = self._parse_enum(node, content, module_path)
            if entity:
                entities.append(entity)
        elif node.type == "trait_item":
            entity = self._parse_trait(node, content, module_path)
            if entity:
                entities.append(entity)
        elif node.type == "macro_definition":
            entity = self._parse_macro(node, content, module_path)
            if entity:
                entities.append(entity)

        # Recursively process children
        for child in node.children:
            self._extract_entities(child, content, module_path, entities)

    def _parse_function(
        self, node: Any, content: str, module_path: str
    ) -> APIEntity | None:
        """Parse a function definition."""
        try:
            name_node = node.child_by_field_name("name")
            if not name_node:
                return None

            name = content[name_node.start_byte : name_node.end_byte]

            # Check visibility
            is_pub = False
            for child in node.children:
                if child.type == "visibility_modifier":
                    is_pub = True
                    break

            if not is_pub:
                return None  # Only extract public APIs

            # Extract signature
            signature_start = node.start_byte
            body_node = node.child_by_field_name("body")
            signature_end = body_node.start_byte if body_node else node.end_byte
            signature = content[signature_start:signature_end].strip()

            # Extract attributes
            attributes = self._parse_attributes(node, content)

            # Extract documentation
            documentation, examples = self._parse_docs(node, content)

            # Extract source code
            source_code = content[node.start_byte : node.end_byte]

            # Determine entity type
            param_list = node.child_by_field_name("parameters")
            entity_type = "function"
            if param_list:
                params_text = content[param_list.start_byte : param_list.end_byte]
                if (
                    "self" in params_text
                    or "&self" in params_text
                    or "&mut self" in params_text
                ):
                    entity_type = "method"

            return APIEntity(
                name=name,
                module=module_path,
                entity_type=entity_type,
                signature=signature,
                documentation=documentation,
                examples=examples,
                source_code=source_code,
                attributes=attributes,
            )
        except Exception as e:
            logger.debug(f"Failed to parse function: {e}")
            return None

    def _parse_struct(
        self, node: Any, content: str, module_path: str
    ) -> APIEntity | None:
        """Parse a struct definition."""
        try:
            name_node = node.child_by_field_name("name")
            if not name_node:
                return None

            name = content[name_node.start_byte : name_node.end_byte]

            # Check visibility
            is_pub = False
            for child in node.children:
                if child.type == "visibility_modifier":
                    is_pub = True
                    break

            if not is_pub:
                return None

            # Extract signature
            signature = f"struct {name}"

            # Extract attributes
            attributes = self._parse_attributes(node, content)

            # Extract documentation
            documentation, examples = self._parse_docs(node, content)

            # Extract source code
            source_code = content[node.start_byte : node.end_byte]

            return APIEntity(
                name=name,
                module=module_path,
                entity_type="struct",
                signature=signature,
                documentation=documentation,
                examples=examples,
                source_code=source_code,
                attributes=attributes,
            )
        except Exception as e:
            logger.debug(f"Failed to parse struct: {e}")
            return None

    def _parse_enum(
        self, node: Any, content: str, module_path: str
    ) -> APIEntity | None:
        """Parse an enum definition."""
        try:
            name_node = node.child_by_field_name("name")
            if not name_node:
                return None

            name = content[name_node.start_byte : name_node.end_byte]

            # Check visibility
            is_pub = False
            for child in node.children:
                if child.type == "visibility_modifier":
                    is_pub = True
                    break

            if not is_pub:
                return None

            # Extract signature
            signature = f"enum {name}"

            # Extract attributes
            attributes = self._parse_attributes(node, content)

            # Extract documentation
            documentation, examples = self._parse_docs(node, content)

            # Extract source code
            source_code = content[node.start_byte : node.end_byte]

            return APIEntity(
                name=name,
                module=module_path,
                entity_type="enum",
                signature=signature,
                documentation=documentation,
                examples=examples,
                source_code=source_code,
                attributes=attributes,
            )
        except Exception as e:
            logger.debug(f"Failed to parse enum: {e}")
            return None

    def _parse_trait(
        self, node: Any, content: str, module_path: str
    ) -> APIEntity | None:
        """Parse a trait definition."""
        try:
            name_node = node.child_by_field_name("name")
            if not name_node:
                return None

            name = content[name_node.start_byte : name_node.end_byte]

            # Check visibility
            is_pub = False
            for child in node.children:
                if child.type == "visibility_modifier":
                    is_pub = True
                    break

            if not is_pub:
                return None

            # Extract signature
            signature = f"trait {name}"

            # Extract attributes
            attributes = self._parse_attributes(node, content)

            # Extract documentation
            documentation, examples = self._parse_docs(node, content)

            # Extract source code
            source_code = content[node.start_byte : node.end_byte]

            return APIEntity(
                name=name,
                module=module_path,
                entity_type="trait",
                signature=signature,
                documentation=documentation,
                examples=examples,
                source_code=source_code,
                attributes=attributes,
            )
        except Exception as e:
            logger.debug(f"Failed to parse trait: {e}")
            return None

    def _parse_macro(
        self, node: Any, content: str, module_path: str
    ) -> APIEntity | None:
        """Parse a macro definition."""
        try:
            name_node = node.child_by_field_name("name")
            if not name_node:
                return None

            name = content[name_node.start_byte : name_node.end_byte]

            # Extract signature
            signature = f"macro_rules! {name}"

            # Extract attributes
            attributes = self._parse_attributes(node, content)

            # Extract documentation
            documentation, examples = self._parse_docs(node, content)

            # Extract source code
            source_code = content[node.start_byte : node.end_byte]

            return APIEntity(
                name=name,
                module=module_path,
                entity_type="macro",
                signature=signature,
                documentation=documentation,
                examples=examples,
                source_code=source_code,
                attributes=attributes,
            )
        except Exception as e:
            logger.debug(f"Failed to parse macro: {e}")
            return None

    def _parse_attributes(self, node: Any, content: str) -> dict[str, Any]:
        """Parse Rust attributes like #[stable], #[deprecated]."""
        attributes: dict[str, Any] = {}

        # Check preceding siblings for attributes
        prev_sibling = node.prev_sibling
        while prev_sibling:
            if prev_sibling.type == "attribute_item":
                attr_text = content[prev_sibling.start_byte : prev_sibling.end_byte]

                # Parse #[stable(feature = "...", since = "...")]
                stable_match = re.search(
                    r'#\[\s*stable\s*\(\s*feature\s*=\s*"([^"]+)"\s*,\s*since\s*=\s*"([^"]+)"\s*\)\s*\]',
                    attr_text,
                    re.DOTALL,
                )
                if stable_match:
                    feature, version = stable_match.groups()
                    attributes["stable"] = {"feature": feature, "version": version}

                # Parse #[deprecated(since = "...", note = "...")]
                deprecated_pattern = re.compile(
                    r"#\[\s*deprecated\s*\(\s*"
                    r'(?:[\s\n]*since\s*=\s*"([^"]+)"\s*,?)?'
                    r'(?:[\s\n]*note\s*=\s*"((?:[^"]|\\")*)"\s*,?)?'
                    r'(?:[\s\n]*suggestion\s*=\s*"([^"]+)"\s*,?)?'
                    r"[\s\n]*\)\s*\]",
                    re.DOTALL,
                )
                deprecated_match = deprecated_pattern.search(attr_text)
                if deprecated_match:
                    since = deprecated_match.group(1)
                    note = deprecated_match.group(2)
                    if note:
                        note = note.replace(r"\"", '"')
                    if not re.search(r"allow\s*\(\s*deprecated\s*\)", attr_text):
                        attributes["deprecated"] = {
                            "since": since.strip() if since else None,
                            "note": note.strip() if note else None,
                        }

                # Parse #[unstable(feature = "...", issue = "...")]
                unstable_match = re.search(
                    r'#\[\s*unstable\s*\(\s*feature\s*=\s*"([^"]+)"\s*,\s*issue\s*=\s*"([^"]+)"'
                    r'\s*(?:,\s*reason\s*=\s*"([^"]+)")?\s*\)\s*\]',
                    attr_text,
                    re.DOTALL,
                )
                if unstable_match:
                    feature = unstable_match.group(1)
                    issue = unstable_match.group(2)
                    reason = (
                        unstable_match.group(3)
                        if len(unstable_match.groups()) > 2
                        else None
                    )
                    attributes["unstable"] = {
                        "feature": feature,
                        "issue": issue,
                        "reason": reason,
                    }

            prev_sibling = prev_sibling.prev_sibling

        return attributes

    def _parse_docs(self, node: Any, content: str) -> tuple[str, list[str]]:
        """
        Parse documentation comments and extract examples.

        Returns:
            Tuple of (documentation_text, list_of_example_code_blocks)
        """
        documentation: list[str] = []
        examples: list[str] = []
        current_code_block: list[str] = []
        in_code_block = False
        code_lang = ""
        in_examples_section = False

        prev_sibling = node.prev_sibling
        while prev_sibling:
            if prev_sibling.type == "line_comment":
                line = content[prev_sibling.start_byte : prev_sibling.end_byte].strip()

                if line.startswith("///"):
                    doc_line = line[3:].strip()

                    # Detect Examples section
                    if re.match(r"^#+\s*examples?", doc_line, re.IGNORECASE):
                        in_examples_section = True
                        prev_sibling = prev_sibling.prev_sibling
                        continue
                    elif in_examples_section and doc_line.startswith("#"):
                        in_examples_section = False

                    # Handle code blocks
                    if doc_line.startswith("```"):
                        lang_match = re.match(r"^```(\S*)", doc_line)
                        code_lang = lang_match.group(1) if lang_match else ""

                        if in_code_block:
                            in_code_block = False
                            if current_code_block:
                                current_code_block.append("```")
                                full_code = "\n".join(current_code_block)
                                if in_examples_section:
                                    examples.append(full_code)
                                else:
                                    documentation.append(full_code)
                                current_code_block = []
                        else:
                            in_code_block = True
                            current_code_block.append(f"```{code_lang}")
                    elif in_code_block:
                        current_code_block.append(doc_line)
                    else:
                        if not in_examples_section:
                            documentation.append(doc_line)

            prev_sibling = prev_sibling.prev_sibling

        # Handle unclosed code block
        if in_code_block and current_code_block:
            current_code_block.append("```")
            examples.append("\n".join(current_code_block))

        return "\n".join(documentation), examples


class ModulePathExtractor:
    """Extracts module paths from file paths and documentation."""

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path

    def extract_module_path(
        self, file_path: Path, examples: list[str], api_name: str
    ) -> str:
        """
        Extract module path for an API.

        Args:
            file_path: Path to source file
            examples: List of example code blocks
            api_name: Name of the API

        Returns:
            Module path string (e.g., "std::fs")
        """
        # Try extracting from examples
        module_from_examples = self._extract_from_examples(examples, api_name)
        if module_from_examples:
            return module_from_examples

        # Try extracting from file path
        return self._extract_from_file_path(file_path)

    def _extract_from_examples(self, examples: list[str], api_name: str) -> str:
        """Extract module path from example code."""
        if not examples:
            return ""

        joined_examples = "\n".join(examples)
        use_matches = re.finditer(r"use\s+([^;]+);", joined_examples)

        for match in use_matches:
            module_path = match.group(1).strip()
            if api_name in module_path.split("::"):
                parts = module_path.split("::")
                if api_name in parts:
                    idx = parts.index(api_name)
                    return "::".join(parts[:idx])
            if module_path.startswith(("std::", "core::", "alloc::")):
                return module_path

        return ""

    def _extract_from_file_path(self, file_path: Path) -> str:
        """Extract module path from file path."""
        try:
            rel_path = file_path.relative_to(self.repo_path)
            parts = list(rel_path.parts)

            lib_indices = [
                i for i, part in enumerate(parts) if part in ["std", "core", "alloc"]
            ]
            if not lib_indices:
                return ""

            lib_idx = lib_indices[0]
            lib_type = parts[lib_idx]

            try:
                src_idx = parts.index("src", lib_idx)
                module_parts = [lib_type] + list(parts[src_idx + 1 :])

                if module_parts[-1].endswith(".rs"):
                    module_parts[-1] = module_parts[-1][:-3]
                if module_parts[-1] == "mod":
                    module_parts.pop()

                return "::".join(module_parts)
            except ValueError:
                return lib_type
        except Exception:
            return ""


class APIChangeDetector:
    """Detects API changes between Rust versions."""

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.ast_parser = RustASTParser()
        self.module_extractor = ModulePathExtractor(repo_path)

    def extract_apis_from_version(self, version: str) -> dict[str, APIEntity]:
        """
        Extract all APIs from a specific Rust version.

        Args:
            version: Rust version tag (e.g., "1.76.0")

        Returns:
            Dictionary mapping "module::name" to APIEntity
        """
        # Note: This requires git checkout functionality
        # Implementation would checkout version and scan library/std, library/core, library/alloc
        # For now, this is a placeholder structure

        apis: dict[str, APIEntity] = {}

        # Find API files
        std_paths = [
            self.repo_path / "library" / "std",
            self.repo_path / "library" / "core",
            self.repo_path / "library" / "alloc",
        ]

        for std_path in std_paths:
            if not std_path.exists():
                continue

            for file_path in std_path.rglob("*.rs"):
                file_entities = self.ast_parser.parse_file(file_path)

                for entity in file_entities:
                    # Extract module path
                    module_path = self.module_extractor.extract_module_path(
                        file_path, entity.examples, entity.name
                    )
                    entity.module = module_path
                    entity.version = version

                    # Create key
                    key = (
                        f"{module_path}::{entity.name}" if module_path else entity.name
                    )
                    apis[key] = entity

        return apis

    def detect_changes(self, from_version: str, to_version: str) -> list[APIChange]:
        """
        Detect API changes between two versions.

        Args:
            from_version: Source version
            to_version: Target version

        Returns:
            List of detected API changes
        """
        old_apis = self.extract_apis_from_version(from_version)
        new_apis = self.extract_apis_from_version(to_version)

        changes: list[APIChange] = []

        # 1. Detect stabilized APIs
        for key, new_api in new_apis.items():
            if "stable" in new_api.attributes:
                stable_info = new_api.attributes["stable"]
                stable_version = stable_info.get("version", "")

                if self._is_version_in_range(stable_version, from_version, to_version):
                    if key not in old_apis:
                        changes.append(
                            APIChange(
                                api=new_api,
                                change_type="stabilized",
                                from_version=from_version,
                                to_version=to_version,
                                details=f"New API stabilized in version {stable_version}",
                            )
                        )
                    elif (
                        "stable" not in old_apis[key].attributes
                        and "unstable" in old_apis[key].attributes
                    ):
                        changes.append(
                            APIChange(
                                api=new_api,
                                change_type="stabilized",
                                from_version=from_version,
                                to_version=to_version,
                                details=f"API stabilized in version {stable_version}, previously unstable",
                            )
                        )

        # 2. Detect deprecated APIs
        for key, new_api in new_apis.items():
            if "deprecated" in new_api.attributes:
                if key not in old_apis:
                    deprecated_info = new_api.attributes["deprecated"]
                    deprecated_version = deprecated_info.get("since", "")

                    if deprecated_version and self._is_version_in_range(
                        deprecated_version, from_version, to_version
                    ):
                        changes.append(
                            APIChange(
                                api=new_api,
                                change_type="deprecated",
                                from_version=from_version,
                                to_version=to_version,
                                details=f"New API immediately deprecated in version {deprecated_version}: "
                                f"{deprecated_info.get('note', 'No reason provided')}",
                            )
                        )
                else:
                    if "deprecated" not in old_apis[key].attributes:
                        deprecated_info = new_api.attributes["deprecated"]
                        deprecated_version = deprecated_info.get("since", "")

                        if deprecated_version:
                            if (
                                deprecated_version == to_version
                                or deprecated_version == from_version
                                or self._is_version_in_range(
                                    deprecated_version, from_version, to_version
                                )
                            ):
                                changes.append(
                                    APIChange(
                                        api=new_api,
                                        change_type="deprecated",
                                        from_version=from_version,
                                        to_version=to_version,
                                        details=f"API deprecated in version {deprecated_version}: "
                                        f"{deprecated_info.get('note', 'No reason provided')}",
                                    )
                                )

        # 3. Detect signature changes
        for key in set(old_apis.keys()) & set(new_apis.keys()):
            if any(
                c.api.name == new_apis[key].name
                and c.api.module == new_apis[key].module
                for c in changes
            ):
                continue

            old_api = old_apis[key]
            new_api = new_apis[key]

            old_normalized = self._normalize_signature(old_api.signature)
            new_normalized = self._normalize_signature(new_api.signature)

            if old_normalized != new_normalized:
                changes.append(
                    APIChange(
                        api=new_api,
                        change_type="signature",
                        from_version=from_version,
                        to_version=to_version,
                        details=f"Signature changed from `{old_api.signature}` to `{new_api.signature}`",
                        old_source_code=old_api.source_code,
                    )
                )
            # 4. Detect implicit changes
            elif self._detect_implicit_change(old_api, new_api):
                changes.append(
                    APIChange(
                        api=new_api,
                        change_type="implicit",
                        from_version=from_version,
                        to_version=to_version,
                        details="API behavior may have changed (implementation or documentation has "
                        "significant changes)",
                        old_source_code=old_api.source_code,
                    )
                )

        return changes

    def _is_version_in_range(
        self, version: str, from_version: str, to_version: str
    ) -> bool:
        """Check if version is in range."""
        try:

            def parse_version(v: str) -> tuple[int, ...]:
                """Parse version string into tuple of integers."""
                parts = v.split(".")
                return tuple(int(p) for p in parts if p.isdigit())

            ver = parse_version(version)
            from_ver = parse_version(from_version)
            to_ver = parse_version(to_version)
            return from_ver <= ver <= to_ver
        except Exception:
            return False

    def _normalize_signature(self, signature: str) -> str:
        """Normalize signature for comparison."""
        signature = re.sub(r"//.*$", "", signature, flags=re.MULTILINE)
        signature = re.sub(r"\s+", " ", signature)
        signature = re.sub(r"\s*([(),:])\s*", r"\1", signature)
        return signature.strip()

    def _detect_implicit_change(self, old_api: APIEntity, new_api: APIEntity) -> bool:
        """Detect implicit behavioral changes."""
        old_body = self._extract_function_body(old_api.source_code)
        new_body = self._extract_function_body(new_api.source_code)

        if old_body != new_body:
            old_normalized = self._normalize_code(old_body)
            new_normalized = self._normalize_code(new_body)

            if old_normalized != new_normalized:
                similarity = self._code_similarity(old_normalized, new_normalized)
                if similarity < 0.85:
                    return True

        # Check documentation for behavior change keywords
        if old_api.documentation != new_api.documentation:
            behavior_phrases = [
                "breaking change",
                "behavior change",
                "now returns",
                "now behaves",
                "changed behavior",
                "panic",
                "differently",
            ]

            old_doc = old_api.documentation.lower()
            new_doc = new_api.documentation.lower()

            for phrase in behavior_phrases:
                if phrase in new_doc and phrase not in old_doc:
                    return True

        return False

    def _normalize_code(self, code: str) -> str:
        """Normalize code for comparison."""
        code = re.sub(r"//.*$", "", code, flags=re.MULTILINE)
        code = re.sub(r"\s+", " ", code)
        return code.strip()

    def _extract_function_body(self, code: str) -> str:
        """Extract function body."""
        open_brace = code.find("{")
        if open_brace == -1:
            return code

        count = 1
        for i in range(open_brace + 1, len(code)):
            if code[i] == "{":
                count += 1
            elif code[i] == "}":
                count -= 1
                if count == 0:
                    return code[open_brace : i + 1]

        return code[open_brace:]

    def _code_similarity(self, code1: str, code2: str) -> float:
        """Calculate code similarity (simplified)."""
        if not code1 or not code2:
            return 0.0

        # Simple token-based similarity
        tokens1 = set(code1.split())
        tokens2 = set(code2.split())

        intersection = tokens1 & tokens2
        union = tokens1 | tokens2

        if not union:
            return 1.0

        return len(intersection) / len(union)
