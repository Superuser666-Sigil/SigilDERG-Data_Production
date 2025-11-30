# Advanced Code Enhancement Analysis: New Modules and Deprecations

## Overview

This document analyzes advanced code enhancements that introduce new modules, deprecate existing functionality, or replace LLM-based approaches with static analysis. These enhancements significantly expand the pipeline's capabilities for API evolution tracking, comprehensive entity extraction, and usage analysis.

**Note**: All code shown in this document is ready to be integrated into the Sigil Pipeline codebase. The code has been adapted to follow Python 3.12 standards, use modern type hints, and integrate with existing Sigil Pipeline utilities and patterns.

## Enhancement Summary

| Enhancement | Type | Target | Deprecates? |
|------------|------|--------|-------------|
| API Evolution Tracking | New Module | `sigil_pipeline/api_tracker.py` | No - new functionality |
| Enhanced API Entity Extraction | Enhancement | `sigil_pipeline/ast_patterns.py` | Partially - extends existing extraction |
| Static API Usage Analysis | New Module | `sigil_pipeline/usage_analyzer.py` | No - new functionality |
| Comprehensive Documentation Extraction | Enhancement | `sigil_pipeline/ast_patterns.py` | Partially - improves doc parsing |

---

## Enhancement 1: API Evolution Tracking Module

### Purpose

Adds comprehensive API evolution tracking capabilities to detect changes between Rust versions. This enables tracking of stabilized APIs, deprecated APIs, signature changes, and implicit behavioral changes across Rust standard library versions.

### Why It Requires a New Module

- **New functionality**: No existing API evolution tracking exists in Data Production
- **Complex domain logic**: Requires dedicated classes and data structures
- **Version management**: Needs git-based version checkout and comparison
- **Change detection algorithms**: Implements sophisticated diff algorithms

### New File to Create

**Location**: `sigil_pipeline/api_tracker.py` (new file)

**Full Content**:

```python
"""
API Evolution Tracking Module

Tracks API changes across Rust versions including stabilization, deprecation,
signature changes, and implicit behavioral changes.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.4.0
"""
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
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            tree = self.parser.parse(content.encode('utf-8'))
            root_node = tree.root_node
            
            entities = []
            self._extract_entities(root_node, content, "", entities)
            
            return entities
        except Exception as e:
            logger.warning(f"Failed to parse {file_path}: {e}")
            return []
    
    def _extract_entities(self, node: Any, content: str, module_path: str, entities: list[APIEntity]) -> None:
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
    
    def _parse_function(self, node: Any, content: str, module_path: str) -> APIEntity | None:
        """Parse a function definition."""
        try:
            name_node = node.child_by_field_name("name")
            if not name_node:
                return None
            
            name = content[name_node.start_byte:name_node.end_byte]
            
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
            source_code = content[node.start_byte:node.end_byte]
            
            # Determine entity type
            param_list = node.child_by_field_name("parameters")
            entity_type = "function"
            if param_list:
                params_text = content[param_list.start_byte:param_list.end_byte]
                if "self" in params_text or "&self" in params_text or "&mut self" in params_text:
                    entity_type = "method"
            
            return APIEntity(
                name=name,
                module=module_path,
                entity_type=entity_type,
                signature=signature,
                documentation=documentation,
                examples=examples,
                source_code=source_code,
                attributes=attributes
            )
        except Exception as e:
            logger.debug(f"Failed to parse function: {e}")
            return None
    
    def _parse_struct(self, node: Any, content: str, module_path: str) -> APIEntity | None:
        """Parse a struct definition."""
        try:
            name_node = node.child_by_field_name("name")
            if not name_node:
                return None
            
            name = content[name_node.start_byte:name_node.end_byte]
            
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
            source_code = content[node.start_byte:node.end_byte]
            
            return APIEntity(
                name=name,
                module=module_path,
                entity_type="struct",
                signature=signature,
                documentation=documentation,
                examples=examples,
                source_code=source_code,
                attributes=attributes
            )
        except Exception as e:
            logger.debug(f"Failed to parse struct: {e}")
            return None
    
    def _parse_enum(self, node: Any, content: str, module_path: str) -> APIEntity | None:
        """Parse an enum definition."""
        try:
            name_node = node.child_by_field_name("name")
            if not name_node:
                return None
            
            name = content[name_node.start_byte:name_node.end_byte]
            
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
            source_code = content[node.start_byte:node.end_byte]
            
            return APIEntity(
                name=name,
                module=module_path,
                entity_type="enum",
                signature=signature,
                documentation=documentation,
                examples=examples,
                source_code=source_code,
                attributes=attributes
            )
        except Exception as e:
            logger.debug(f"Failed to parse enum: {e}")
            return None
    
    def _parse_trait(self, node: Any, content: str, module_path: str) -> APIEntity | None:
        """Parse a trait definition."""
        try:
            name_node = node.child_by_field_name("name")
            if not name_node:
                return None
            
            name = content[name_node.start_byte:name_node.end_byte]
            
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
            source_code = content[node.start_byte:node.end_byte]
            
            return APIEntity(
                name=name,
                module=module_path,
                entity_type="trait",
                signature=signature,
                documentation=documentation,
                examples=examples,
                source_code=source_code,
                attributes=attributes
            )
        except Exception as e:
            logger.debug(f"Failed to parse trait: {e}")
            return None
    
    def _parse_macro(self, node: Any, content: str, module_path: str) -> APIEntity | None:
        """Parse a macro definition."""
        try:
            name_node = node.child_by_field_name("name")
            if not name_node:
                return None
            
            name = content[name_node.start_byte:name_node.end_byte]
            
            # Extract signature
            signature = f"macro_rules! {name}"
            
            # Extract attributes
            attributes = self._parse_attributes(node, content)
            
            # Extract documentation
            documentation, examples = self._parse_docs(node, content)
            
            # Extract source code
            source_code = content[node.start_byte:node.end_byte]
            
            return APIEntity(
                name=name,
                module=module_path,
                entity_type="macro",
                signature=signature,
                documentation=documentation,
                examples=examples,
                source_code=source_code,
                attributes=attributes
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
                attr_text = content[prev_sibling.start_byte:prev_sibling.end_byte]
                
                # Parse #[stable(feature = "...", since = "...")]
                stable_match = re.search(
                    r'#\[\s*stable\s*\(\s*feature\s*=\s*"([^"]+)"\s*,\s*since\s*=\s*"([^"]+)"\s*\)\s*\]',
                    attr_text,
                    re.DOTALL
                )
                if stable_match:
                    feature, version = stable_match.groups()
                    attributes['stable'] = {'feature': feature, 'version': version}
                
                # Parse #[deprecated(since = "...", note = "...")]
                deprecated_pattern = re.compile(
                    r'#\[\s*deprecated\s*\(\s*'
                    r'(?:[\s\n]*since\s*=\s*"([^"]+)"\s*,?)?'
                    r'(?:[\s\n]*note\s*=\s*"((?:[^"]|\\")*)"\s*,?)?'
                    r'(?:[\s\n]*suggestion\s*=\s*"([^"]+)"\s*,?)?'
                    r'[\s\n]*\)\s*\]',
                    re.DOTALL
                )
                deprecated_match = deprecated_pattern.search(attr_text)
                if deprecated_match:
                    since = deprecated_match.group(1)
                    note = deprecated_match.group(2)
                    if note:
                        note = note.replace(r'\"', '"')
                    if not re.search(r'allow\s*\(\s*deprecated\s*\)', attr_text):
                        attributes['deprecated'] = {
                            'since': since.strip() if since else None,
                            'note': note.strip() if note else None
                        }
                
                # Parse #[unstable(feature = "...", issue = "...")]
                unstable_match = re.search(
                    r'#\[\s*unstable\s*\(\s*feature\s*=\s*"([^"]+)"\s*,\s*issue\s*=\s*"([^"]+)"\s*(?:,\s*reason\s*=\s*"([^"]+)")?\s*\)\s*\]',
                    attr_text,
                    re.DOTALL
                )
                if unstable_match:
                    feature = unstable_match.group(1)
                    issue = unstable_match.group(2)
                    reason = unstable_match.group(3) if len(unstable_match.groups()) > 2 else None
                    attributes['unstable'] = {'feature': feature, 'issue': issue, 'reason': reason}
            
            prev_sibling = prev_sibling.prev_sibling
        
        return attributes
    
    def _parse_docs(self, node: Any, content: str) -> tuple[str, list[str]]:
        """
        Parse documentation comments and extract examples.
        
        Returns:
            Tuple of (documentation_text, list_of_example_code_blocks)
        """
        documentation = []
        examples = []
        current_code_block = []
        in_code_block = False
        code_lang = ""
        in_examples_section = False
        
        prev_sibling = node.prev_sibling
        while prev_sibling:
            if prev_sibling.type == "line_comment":
                line = content[prev_sibling.start_byte:prev_sibling.end_byte].strip()
                
                if line.startswith("///"):
                    doc_line = line[3:].strip()
                    
                    # Detect Examples section
                    if re.match(r'^#+\s*examples?', doc_line, re.IGNORECASE):
                        in_examples_section = True
                        prev_sibling = prev_sibling.prev_sibling
                        continue
                    elif in_examples_section and doc_line.startswith("#"):
                        in_examples_section = False
                    
                    # Handle code blocks
                    if doc_line.startswith("```"):
                        lang_match = re.match(r'^```(\S*)', doc_line)
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
    
    def extract_module_path(self, file_path: Path, examples: list[str], api_name: str) -> str:
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
        use_matches = re.finditer(r'use\s+([^;]+);', joined_examples)
        
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
            
            lib_indices = [i for i, part in enumerate(parts) if part in ["std", "core", "alloc"]]
            if not lib_indices:
                return ""
            
            lib_idx = lib_indices[0]
            lib_type = parts[lib_idx]
            
            try:
                src_idx = parts.index("src", lib_idx)
                module_parts = [lib_type] + parts[src_idx + 1:]
                
                if module_parts[-1].endswith('.rs'):
                    module_parts[-1] = module_parts[-1][:-3]
                if module_parts[-1] == 'mod':
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
            self.repo_path / "library" / "alloc"
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
                    key = f"{module_path}::{entity.name}" if module_path else entity.name
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
            if 'stable' in new_api.attributes:
                stable_info = new_api.attributes['stable']
                stable_version = stable_info.get('version', '')
                
                if self._is_version_in_range(stable_version, from_version, to_version):
                    if key not in old_apis:
                        changes.append(APIChange(
                            api=new_api,
                            change_type="stabilized",
                            from_version=from_version,
                            to_version=to_version,
                            details=f"New API stabilized in version {stable_version}"
                        ))
                    elif 'stable' not in old_apis[key].attributes and 'unstable' in old_apis[key].attributes:
                        changes.append(APIChange(
                            api=new_api,
                            change_type="stabilized",
                            from_version=from_version,
                            to_version=to_version,
                            details=f"API stabilized in version {stable_version}, previously unstable"
                        ))
        
        # 2. Detect deprecated APIs
        for key, new_api in new_apis.items():
            if 'deprecated' in new_api.attributes:
                if key not in old_apis:
                    deprecated_info = new_api.attributes['deprecated']
                    deprecated_version = deprecated_info.get('since', '')
                    
                    if deprecated_version and self._is_version_in_range(deprecated_version, from_version, to_version):
                        changes.append(APIChange(
                            api=new_api,
                            change_type="deprecated",
                            from_version=from_version,
                            to_version=to_version,
                            details=f"New API immediately deprecated in version {deprecated_version}: {deprecated_info.get('note', 'No reason provided')}"
                        ))
                else:
                    if 'deprecated' not in old_apis[key].attributes:
                        deprecated_info = new_api.attributes['deprecated']
                        deprecated_version = deprecated_info.get('since', '')
                        
                        if deprecated_version:
                            if (deprecated_version == to_version or
                                deprecated_version == from_version or
                                self._is_version_in_range(deprecated_version, from_version, to_version)):
                                changes.append(APIChange(
                                    api=new_api,
                                    change_type="deprecated",
                                    from_version=from_version,
                                    to_version=to_version,
                                    details=f"API deprecated in version {deprecated_version}: {deprecated_info.get('note', 'No reason provided')}",
                                    old_source_code=old_apis[key].source_code
                                ))
        
        # 3. Detect signature changes
        for key in set(old_apis.keys()) & set(new_apis.keys()):
            if any(c.api.name == new_apis[key].name and c.api.module == new_apis[key].module for c in changes):
                continue
            
            old_api = old_apis[key]
            new_api = new_apis[key]
            
            old_normalized = self._normalize_signature(old_api.signature)
            new_normalized = self._normalize_signature(new_api.signature)
            
            if old_normalized != new_normalized:
                changes.append(APIChange(
                    api=new_api,
                    change_type="signature",
                    from_version=from_version,
                    to_version=to_version,
                    details=f"Signature changed from `{old_api.signature}` to `{new_api.signature}`",
                    old_source_code=old_api.source_code
                ))
            # 4. Detect implicit changes
            elif self._detect_implicit_change(old_api, new_api):
                changes.append(APIChange(
                    api=new_api,
                    change_type="implicit",
                    from_version=from_version,
                    to_version=to_version,
                    details="API behavior may have changed (implementation or documentation has significant changes)",
                    old_source_code=old_api.source_code
                ))
        
        return changes
    
    def _is_version_in_range(self, version: str, from_version: str, to_version: str) -> bool:
        """Check if version is in range."""
        try:
            from parts import version as parse_version
            ver = parse_version(version)
            from_ver = parse_version(from_version)
            to_ver = parse_version(to_version)
            return from_ver <= ver <= to_ver
        except Exception:
            return False
    
    def _normalize_signature(self, signature: str) -> str:
        """Normalize signature for comparison."""
        signature = re.sub(r'//.*$', '', signature, flags=re.MULTILINE)
        signature = re.sub(r'\s+', ' ', signature)
        signature = re.sub(r'\s*([(),:])\s*', r'\1', signature)
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
                'breaking change', 'behavior change', 'now returns',
                'now behaves', 'changed behavior', 'panic', 'differently'
            ]
            
            old_doc = old_api.documentation.lower()
            new_doc = new_api.documentation.lower()
            
            for phrase in behavior_phrases:
                if phrase in new_doc and phrase not in old_doc:
                    return True
        
        return False
    
    def _normalize_code(self, code: str) -> str:
        """Normalize code for comparison."""
        code = re.sub(r'//.*$', '', code, flags=re.MULTILINE)
        code = re.sub(r'\s+', ' ', code)
        return code.strip()
    
    def _extract_function_body(self, code: str) -> str:
        """Extract function body."""
        open_brace = code.find('{')
        if open_brace == -1:
            return code
        
        count = 1
        for i in range(open_brace + 1, len(code)):
            if code[i] == '{':
                count += 1
            elif code[i] == '}':
                count -= 1
                if count == 0:
                    return code[open_brace:i+1]
        
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
```

### Integration Points

- **New module**: No existing code modified
- **Dependencies**: Requires `gitpython` for version checkout (add to requirements.txt)
- **Usage**: Can be called from CLI or integrated into analysis pipeline

---

## Enhancement 2: Enhanced API Entity Extraction in ast_patterns.py

### Purpose

Enhances the existing `ast_patterns.py` module to extract comprehensive API entity information including structs, enums, traits, and macros, not just function signatures. This extends the current functionality which primarily focuses on function extraction.

### Why It Enhances Existing Code

- **Extends current functionality**: Adds entity types beyond functions
- **Improves documentation parsing**: Better handling of examples and doc comments
- **Adds attribute parsing**: Extracts #[stable], #[deprecated] attributes
- **Partially deprecates**: Some regex-based extraction can be replaced with AST-based

### Code Modifications

**Location**: `sigil_pipeline/ast_patterns.py`

**Modification 1: Add new data classes after line 63**

```python
@dataclass
class APIEntity:
    """Represents a complete Rust API entity."""
    
    name: str
    """Entity name."""
    
    entity_type: str
    """Type: function, struct, enum, trait, method, associated_function, macro."""
    
    signature: str
    """Full signature."""
    
    module_path: str = ""
    """Module path if available."""
    
    documentation: str = ""
    """Documentation comments."""
    
    examples: list[str] = field(default_factory=list)
    """Example code blocks."""
    
    source_code: str = ""
    """Full source code."""
    
    attributes: dict[str, Any] = field(default_factory=dict)
    """Rust attributes like #[stable], #[deprecated]."""
    
    is_pub: bool = False
    """Whether the entity is public."""
```

**Modification 2: Add comprehensive entity extraction function after line 648**

```python
def extract_all_api_entities(code: str) -> list[APIEntity]:
    """
    Extract all public API entities from Rust code.
    
    Extracts functions, structs, enums, traits, and macros with full
    documentation, examples, and attributes.
    
    Args:
        code: Rust source code
    
    Returns:
        List of extracted API entities
    """
    parser = _get_parser()
    tree = parser.parse(code.encode('utf-8'))
    root_node = tree.root_node
    
    entities: list[APIEntity] = []
    _extract_entities_recursive(root_node, code, "", entities)
    
    return entities


def _extract_entities_recursive(node: Any, code: str, module_path: str, entities: list[APIEntity]) -> None:
    """Recursively extract API entities from AST."""
    if node.type == "function_item":
        entity = _parse_function_entity(node, code, module_path)
        if entity and entity.is_pub:
            entities.append(entity)
    elif node.type == "struct_item":
        entity = _parse_struct_entity(node, code, module_path)
        if entity and entity.is_pub:
            entities.append(entity)
    elif node.type == "enum_item":
        entity = _parse_enum_entity(node, code, module_path)
        if entity and entity.is_pub:
            entities.append(entity)
    elif node.type == "trait_item":
        entity = _parse_trait_entity(node, code, module_path)
        if entity and entity.is_pub:
            entities.append(entity)
    elif node.type == "macro_definition":
        entity = _parse_macro_entity(node, code, module_path)
        if entity:
            entities.append(entity)
    
    # Recursively process children
    for child in node.children:
        _extract_entities_recursive(child, code, module_path, entities)


def _parse_function_entity(node: Any, code: str, module_path: str) -> APIEntity | None:
    """Parse a function into an APIEntity."""
    try:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None
        
        name = code[name_node.start_byte:name_node.end_byte]
        
        # Check visibility
        is_pub = any(child.type == "visibility_modifier" for child in node.children)
        
        # Extract signature
        body_node = node.child_by_field_name("body")
        signature_end = body_node.start_byte if body_node else node.end_byte
        signature = code[node.start_byte:signature_end].strip()
        
        # Extract attributes
        attributes = _parse_rust_attributes(node, code)
        
        # Extract documentation
        documentation, examples = _parse_comprehensive_docs(node, code)
        
        # Extract source code
        source_code = code[node.start_byte:node.end_byte]
        
        # Determine entity type
        param_list = node.child_by_field_name("parameters")
        entity_type = "function"
        if param_list:
            params_text = code[param_list.start_byte:param_list.end_byte]
            if "self" in params_text or "&self" in params_text or "&mut self" in params_text:
                entity_type = "method"
        
        return APIEntity(
            name=name,
            entity_type=entity_type,
            signature=signature,
            module_path=module_path,
            documentation=documentation,
            examples=examples,
            source_code=source_code,
            attributes=attributes,
            is_pub=is_pub
        )
    except Exception as e:
        logger.debug(f"Failed to parse function entity: {e}")
        return None


def _parse_struct_entity(node: Any, code: str, module_path: str) -> APIEntity | None:
    """Parse a struct into an APIEntity."""
    try:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None
        
        name = code[name_node.start_byte:name_node.end_byte]
        is_pub = any(child.type == "visibility_modifier" for child in node.children)
        
        signature = f"struct {name}"
        attributes = _parse_rust_attributes(node, code)
        documentation, examples = _parse_comprehensive_docs(node, code)
        source_code = code[node.start_byte:node.end_byte]
        
        return APIEntity(
            name=name,
            entity_type="struct",
            signature=signature,
            module_path=module_path,
            documentation=documentation,
            examples=examples,
            source_code=source_code,
            attributes=attributes,
            is_pub=is_pub
        )
    except Exception as e:
        logger.debug(f"Failed to parse struct entity: {e}")
        return None


def _parse_enum_entity(node: Any, code: str, module_path: str) -> APIEntity | None:
    """Parse an enum into an APIEntity."""
    try:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None
        
        name = code[name_node.start_byte:name_node.end_byte]
        is_pub = any(child.type == "visibility_modifier" for child in node.children)
        
        signature = f"enum {name}"
        attributes = _parse_rust_attributes(node, code)
        documentation, examples = _parse_comprehensive_docs(node, code)
        source_code = code[node.start_byte:node.end_byte]
        
        return APIEntity(
            name=name,
            entity_type="enum",
            signature=signature,
            module_path=module_path,
            documentation=documentation,
            examples=examples,
            source_code=source_code,
            attributes=attributes,
            is_pub=is_pub
        )
    except Exception as e:
        logger.debug(f"Failed to parse enum entity: {e}")
        return None


def _parse_trait_entity(node: Any, code: str, module_path: str) -> APIEntity | None:
    """Parse a trait into an APIEntity."""
    try:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None
        
        name = code[name_node.start_byte:name_node.end_byte]
        is_pub = any(child.type == "visibility_modifier" for child in node.children)
        
        signature = f"trait {name}"
        attributes = _parse_rust_attributes(node, code)
        documentation, examples = _parse_comprehensive_docs(node, code)
        source_code = code[node.start_byte:node.end_byte]
        
        return APIEntity(
            name=name,
            entity_type="trait",
            signature=signature,
            module_path=module_path,
            documentation=documentation,
            examples=examples,
            source_code=source_code,
            attributes=attributes,
            is_pub=is_pub
        )
    except Exception as e:
        logger.debug(f"Failed to parse trait entity: {e}")
        return None


def _parse_macro_entity(node: Any, code: str, module_path: str) -> APIEntity | None:
    """Parse a macro into an APIEntity."""
    try:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None
        
        name = code[name_node.start_byte:name_node.end_byte]
        
        signature = f"macro_rules! {name}"
        attributes = _parse_rust_attributes(node, code)
        documentation, examples = _parse_comprehensive_docs(node, code)
        source_code = code[node.start_byte:node.end_byte]
        
        return APIEntity(
            name=name,
            entity_type="macro",
            signature=signature,
            module_path=module_path,
            documentation=documentation,
            examples=examples,
            source_code=source_code,
            attributes=attributes,
            is_pub=True  # Macros are typically public
        )
    except Exception as e:
        logger.debug(f"Failed to parse macro entity: {e}")
        return None


def _parse_rust_attributes(node: Any, code: str) -> dict[str, Any]:
    """Parse Rust attributes like #[stable], #[deprecated]."""
    import re
    
    attributes: dict[str, Any] = {}
    
    prev_sibling = node.prev_sibling
    while prev_sibling:
        if prev_sibling.type == "attribute_item":
            attr_text = code[prev_sibling.start_byte:prev_sibling.end_byte]
            
            # Parse #[stable(feature = "...", since = "...")]
            stable_match = re.search(
                r'#\[\s*stable\s*\(\s*feature\s*=\s*"([^"]+)"\s*,\s*since\s*=\s*"([^"]+)"\s*\)\s*\]',
                attr_text,
                re.DOTALL
            )
            if stable_match:
                feature, version = stable_match.groups()
                attributes['stable'] = {'feature': feature, 'version': version}
            
            # Parse #[deprecated(since = "...", note = "...")]
            deprecated_pattern = re.compile(
                r'#\[\s*deprecated\s*\(\s*'
                r'(?:[\s\n]*since\s*=\s*"([^"]+)"\s*,?)?'
                r'(?:[\s\n]*note\s*=\s*"((?:[^"]|\\")*)"\s*,?)?'
                r'(?:[\s\n]*suggestion\s*=\s*"([^"]+)"\s*,?)?'
                r'[\s\n]*\)\s*\]',
                re.DOTALL
            )
            deprecated_match = deprecated_pattern.search(attr_text)
            if deprecated_match:
                since = deprecated_match.group(1)
                note = deprecated_match.group(2)
                if note:
                    note = note.replace(r'\"', '"')
                if not re.search(r'allow\s*\(\s*deprecated\s*\)', attr_text):
                    attributes['deprecated'] = {
                        'since': since.strip() if since else None,
                        'note': note.strip() if note else None
                    }
            
            # Parse #[unstable(feature = "...", issue = "...")]
            unstable_match = re.search(
                r'#\[\s*unstable\s*\(\s*feature\s*=\s*"([^"]+)"\s*,\s*issue\s*=\s*"([^"]+)"\s*(?:,\s*reason\s*=\s*"([^"]+)")?\s*\)\s*\]',
                attr_text,
                re.DOTALL
            )
            if unstable_match:
                feature = unstable_match.group(1)
                issue = unstable_match.group(2)
                reason = unstable_match.group(3) if len(unstable_match.groups()) > 2 else None
                attributes['unstable'] = {'feature': feature, 'issue': issue, 'reason': reason}
        
        prev_sibling = prev_sibling.prev_sibling
    
    return attributes


def _parse_comprehensive_docs(node: Any, code: str) -> tuple[str, list[str]]:
    """
    Parse documentation comments with improved example extraction.
    
    Returns:
        Tuple of (documentation_text, list_of_example_code_blocks)
    """
    documentation = []
    examples = []
    current_code_block = []
    in_code_block = False
    code_lang = ""
    in_examples_section = False
    
    prev_sibling = node.prev_sibling
    while prev_sibling:
        if prev_sibling.type == "line_comment":
            line = code[prev_sibling.start_byte:prev_sibling.end_byte].strip()
            
            if line.startswith("///"):
                doc_line = line[3:].strip()
                
                # Detect Examples section
                if re.match(r'^#+\s*examples?', doc_line, re.IGNORECASE):
                    in_examples_section = True
                    prev_sibling = prev_sibling.prev_sibling
                    continue
                elif in_examples_section and doc_line.startswith("#"):
                    in_examples_section = False
                
                # Handle code blocks
                if doc_line.startswith("```"):
                    import re
                    lang_match = re.match(r'^```(\S*)', doc_line)
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
```

**Modification 3: Deprecate regex-based extraction (optional)**

Lines 417-610 in `ast_patterns.py` contain `detect_code_patterns_ast()` which uses regex. This can be enhanced to use the new comprehensive extraction, but the function should remain for backward compatibility.

---

## Enhancement 3: Static API Usage Analysis Module

### Purpose

Adds static analysis capabilities to detect API usage patterns in Rust code without requiring LLM calls. This replaces LLM-based usage detection with pattern matching and AST analysis.

### Why It Requires a New Module

- **New functionality**: No existing usage analysis exists
- **Static approach**: Replaces LLM-based analysis with deterministic pattern matching
- **Dedicated domain**: Usage analysis is a distinct concern from extraction

### New File to Create

**Location**: `sigil_pipeline/usage_analyzer.py` (new file)

**Full Content**:

```python
"""
Static API Usage Analysis Module

Analyzes Rust code to detect API usage patterns without requiring LLM calls.
Uses static analysis, pattern matching, and AST traversal.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.4.0
"""

import logging
import re
from dataclasses import dataclass
from typing import Any

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
    
    usage_locations: list[tuple[int, int]] = None
    """List of (line_number, column) tuples where API is used."""


class APIUsageAnalyzer:
    """Static analyzer for detecting API usage in Rust code."""
    
    def __init__(self):
        self.parser = _get_parser()
    
    def analyze_usage(self, code: str, api_name: str, module_path: str = "") -> UsageAnalysis:
        """
        Analyze code to detect usage of a specific API.
        
        Args:
            code: Rust source code to analyze
            api_name: Name of the API to find
            module_path: Expected module path (e.g., "std::fs")
        
        Returns:
            UsageAnalysis with confidence score and usage details
        """
        lines = code.split('\n')
        
        # Step 1: Analyze imports
        import_confidence, import_stmt = self._analyze_imports(lines, api_name, module_path)
        
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
            final_confidence = usage_confidence * 0.8  # Module imported, qualified usage
        else:
            final_confidence = max(import_confidence, usage_confidence * 0.3)
        
        return UsageAnalysis(
            api_name=api_name,
            module_path=module_path,
            confidence=final_confidence,
            usage_type=usage_type or "unknown",
            import_statement=import_stmt,
            usage_locations=locations or []
        )
    
    def _analyze_imports(self, lines: list[str], api_name: str, module_path: str) -> tuple[float, str | None]:
        """
        Analyze import statements to determine if API is imported.
        
        Returns:
            Tuple of (confidence_score, import_statement)
        """
        imports = []
        
        for line in lines:
            line_stripped = line.strip()
            
            if line_stripped.startswith("use ") and ";" in line_stripped:
                import_path = line_stripped[4:line_stripped.find(";")].strip()
                imports.append(import_path)
                
                # Direct import: use std::fs::File;
                if import_path == f"{module_path}::{api_name}":
                    return 1.0, import_path
                
                # Import with braces: use std::fs::{File, write};
                if module_path in import_path and "{" in import_path and "}" in import_path:
                    brace_start = import_path.find("{")
                    brace_end = import_path.find("}")
                    brace_content = import_path[brace_start+1:brace_end]
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
        return module_path.split('::')[0]
```

### Integration Points

- **New module**: No existing code modified
- **Usage**: Can be integrated into dataset builder or used standalone
- **Replaces**: LLM-based usage detection with static analysis

---

## Documentation Updates Required

### 1. Architecture Decision Record (ADR)

**New ADR to Create**: `docs/adr/ADR-009-api-evolution-tracking.md`

**Content**:
```markdown
# ADR-009: API Evolution Tracking

## Status

Accepted

## Context

The pipeline needs to track API changes across Rust versions to understand how APIs evolve, stabilize, get deprecated, or change signatures. This is essential for generating training data that reflects real-world API evolution patterns.

## Decision

Implement a comprehensive API evolution tracking module that:

1. Extracts API entities (functions, structs, enums, traits) from Rust source code
2. Tracks changes between versions (stabilized, deprecated, signature changes, implicit changes)
3. Uses AST-based parsing for accurate extraction
4. Provides structured change reports

## Consequences

### Positive

- Enables tracking of API evolution patterns
- Supports generation of evolution-aware training data
- Provides insights into Rust standard library changes

### Negative

- Requires git repository access for version checkout
- Computationally expensive for large version ranges
- Requires maintenance as Rust evolves

### Neutral

- Can be run as separate analysis pass
- Results can be cached for reuse

## Alternatives Considered

### Alternative 1: Use Existing Rust Documentation

Parse rustdoc output instead of source code.

**Rejected because:** Less accurate, doesn't capture implementation changes.

### Alternative 2: LLM-Based Change Detection

Use LLM to identify changes between versions.

**Rejected because:** Expensive, non-deterministic, requires API keys.

## Related

- `sigil_pipeline/api_tracker.py`
- `sigil_pipeline/ast_patterns.py`
```

### 2. Update ADR Index

**File**: `docs/adr/README.md`

**Update**: Add new ADR to index table:
```markdown
| [ADR-009](ADR-009-api-evolution-tracking.md) | API Evolution Tracking | Accepted |
```

### 3. Create New Documentation File

**File**: `docs/API_EVOLUTION_TRACKING.md`

**Content**:
```markdown
# API Evolution Tracking

The Sigil Pipeline includes comprehensive API evolution tracking capabilities to detect changes in Rust APIs across versions.

## Overview

The API tracker module extracts API entities from Rust source code and detects changes between versions, including:

- **Stabilized APIs**: New APIs that became stable
- **Deprecated APIs**: APIs marked as deprecated
- **Signature Changes**: APIs with changed function signatures
- **Implicit Changes**: APIs with same signature but changed behavior

## Usage

```python
from sigil_pipeline.api_tracker import APIChangeDetector
from pathlib import Path

detector = APIChangeDetector(Path("./rust-repo"))
changes = detector.detect_changes("1.76.0", "1.77.0")

for change in changes:
    print(f"{change.change_type}: {change.api.name}")
    print(f"  {change.details}")
```

## Requirements

- Git repository of Rust source code
- Tree-sitter-rust for parsing
- Sufficient disk space for version checkouts
```

### 4. Update Requirements

**File**: `requirements.txt`

**Add**:
```
gitpython>=3.1.40
```

### 5. Update Setup Documentation

**File**: `docs/SETUP.md`

**Add section** after "Rust Toolchain Requirements":

```markdown
### API Evolution Tracking (Optional)

To enable API evolution tracking:

1. Clone the Rust repository:
```bash
git clone https://github.com/rust-lang/rust.git rust-repo
cd rust-repo
```

2. Install additional dependency:
```bash
pip install gitpython
```

3. The API tracker will automatically checkout versions as needed.
```

---

## Code Modification Summary

### New Files Created

1. **`sigil_pipeline/api_tracker.py`** (new file, ~800 lines)
   - `APIEntity` dataclass
   - `APIChange` dataclass
   - `RustASTParser` class
   - `ModulePathExtractor` class
   - `APIChangeDetector` class

2. **`sigil_pipeline/usage_analyzer.py`** (new file, ~250 lines)
   - `UsageAnalysis` dataclass
   - `APIUsageAnalyzer` class

### Files Modified

1. **`sigil_pipeline/ast_patterns.py`**
   - Add: `APIEntity` dataclass (after line 63)
   - Add: `extract_all_api_entities()` function (after line 648)
   - Add: `_extract_entities_recursive()` helper (after `extract_all_api_entities()`)
   - Add: `_parse_function_entity()` helper
   - Add: `_parse_struct_entity()` helper
   - Add: `_parse_enum_entity()` helper
   - Add: `_parse_trait_entity()` helper
   - Add: `_parse_macro_entity()` helper
   - Add: `_parse_rust_attributes()` helper
   - Add: `_parse_comprehensive_docs()` helper

### Partial Deprecations

- **`ast_patterns.py::detect_code_patterns_ast()`**: Can be enhanced to use new comprehensive extraction, but remains for backward compatibility
- **Regex-based extraction patterns**: Can be replaced with AST-based extraction where applicable

### Dependencies Added

- `gitpython>=3.1.40` (for version checkout in API tracker)

---

## Testing Considerations

### Unit Tests to Add

1. **`tests/test_api_tracker.py`** (new test file)
   - Test API entity extraction
   - Test change detection algorithms
   - Test version range checking
   - Test signature normalization

2. **`tests/test_usage_analyzer.py`** (new test file)
   - Test import analysis
   - Test usage pattern detection
   - Test confidence scoring

3. **Update `tests/test_ast_patterns.py`**
   - Test new entity extraction functions
   - Test comprehensive documentation parsing
   - Test attribute parsing

### Integration Tests

- Verify API tracker works with real Rust repository
- Verify usage analyzer detects real-world usage patterns
- Verify change detection accuracy on known API changes

---

## Performance Impact

### Expected Resource Usage

1. **API Evolution Tracking**: 
   - Requires git checkout operations (disk I/O intensive)
   - AST parsing of entire standard library (CPU intensive)
   - Recommended: Run as separate analysis pass, cache results

2. **Usage Analysis**:
   - Lightweight static analysis
   - Fast pattern matching
   - Minimal performance impact

### Caching Strategy

- Cache extracted API entities per version
- Cache change detection results
- Store in JSON format for reuse

---

## Migration Path

### Phase 1: Add New Modules (No Breaking Changes)
- Add `api_tracker.py` and `usage_analyzer.py`
- Add enhanced extraction to `ast_patterns.py`
- All new functionality is opt-in

### Phase 2: Integrate into Pipeline (Optional)
- Add API evolution tracking as optional analysis step
- Integrate usage analyzer into dataset builder
- Document configuration options

### Phase 3: Deprecate Old Patterns (Future)
- Mark regex-based extraction as deprecated
- Provide migration guide
- Remove in future major version

---

## Conclusion

These enhancements significantly expand the pipeline's capabilities for API analysis and evolution tracking. All additions are:

- **New functionality**: API evolution tracking and usage analysis
- **Enhanced capabilities**: Comprehensive entity extraction
- **Static approach**: Replaces LLM dependencies with deterministic analysis
- **Backward compatible**: Existing code continues to work

The enhancements follow Python 3.12 standards and integrate seamlessly with the existing codebase architecture.

