"""
Local RAG Manager for Agent Knowledge Base

This module provides a comprehensive local knowledge base system that allows
agents to store and retrieve hardware data, code index, documentation, and
change history without external dependencies.
"""

import sqlite3
import json
import hashlib
import os
import psutil
import platform
import subprocess
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import ast


class LocalRAGManager:
    """Comprehensive local knowledge base manager for agent use"""

    def __init__(self, db_path: str = "sigil_rag_cache.db") -> None:
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self.logger = logging.getLogger(__name__)
        self._ensure_database()

    def _ensure_database(self) -> None:
        """Ensure database exists with proper schema"""
        if not os.path.exists(self.db_path):
            self._create_database()
        else:
            self._migrate_database()

    def _create_database(self) -> None:
        """Create new database with schema"""
        with open("sigil_rag_cache.sql", "r") as f:
            schema = f.read()

        self.conn = sqlite3.connect(self.db_path)
        self.conn.executescript(schema)
        self.conn.commit()
        self.logger.info(f"Created new RAG database: {self.db_path}")

    def _migrate_database(self) -> None:
        """Migrate existing database if needed. Ensures all required tables exist."""
        self.conn = sqlite3.connect(self.db_path)
        cursor = self.conn.cursor()
        required_tables = [
            "hardware_profiles",
            "code_index",
            "documentation_cache",
            "code_changes",
            "project_context",
            "search_index",
            "architectural_patterns",
        ]
        missing_tables = []
        for table in required_tables:
            cursor.execute(
                """
                SELECT name FROM sqlite_master WHERE type='table' AND name=?
            """,
                (table,),
            )
            if not cursor.fetchone():
                missing_tables.append(table)
        if missing_tables:
            with open("sigil_rag_cache.sql", "r") as f:
                schema = f.read()
            self.conn.executescript(schema)
            self.conn.commit()
            self.logger.info(
                f"Migrated RAG database: created missing tables {missing_tables}"
            )
        else:
            self.logger.info(f"Connected to existing RAG database: {self.db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with proper configuration"""
        if not self.conn:
            self.conn = sqlite3.connect(self.db_path)
        return self.conn

    def store_hardware_profile(self, profile_name: str = "current") -> Dict[str, Any]:
        """Store comprehensive hardware profile"""
        try:
            # Gather hardware information
            cpu_info = self._gather_cpu_info()
            memory_info = self._gather_memory_info()
            gpu_info = self._gather_gpu_info()
            storage_info = self._gather_storage_info()
            network_info = self._gather_network_info()
            os_info = self._gather_os_info()
            python_info = self._gather_python_info()
            models_info = self._gather_available_models()

            profile_data = {
                "profile_name": profile_name,
                "cpu_model": cpu_info.get("model"),
                "cpu_cores": cpu_info.get("cores"),
                "cpu_threads": cpu_info.get("threads"),
                "ram_total_gb": memory_info.get("total_gb"),
                "gpu_model": gpu_info.get("model"),
                "gpu_vram_gb": gpu_info.get("vram_gb"),
                "storage_type": storage_info.get("type"),
                "storage_capacity_gb": storage_info.get("capacity_gb"),
                "network_speed_mbps": network_info.get("speed_mbps"),
                "os_platform": os_info.get("platform"),
                "os_version": os_info.get("version"),
                "python_version": python_info.get("version"),
                "available_models": json.dumps(models_info),
                "performance_benchmarks": json.dumps(self._run_benchmarks()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            conn = self._get_connection()
            cursor = conn.cursor()

            # Insert or update hardware profile
            cursor.execute(
                """
                INSERT OR REPLACE INTO hardware_profiles
                (profile_name, cpu_model, cpu_cores, cpu_threads, ram_total_gb,
                 gpu_model, gpu_vram_gb, storage_type, storage_capacity_gb,
                 network_speed_mbps, os_platform, os_version, python_version,
                 available_models, performance_benchmarks, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    profile_data["profile_name"],
                    profile_data["cpu_model"],
                    profile_data["cpu_cores"],
                    profile_data["cpu_threads"],
                    profile_data["ram_total_gb"],
                    profile_data["gpu_model"],
                    profile_data["gpu_vram_gb"],
                    profile_data["storage_type"],
                    profile_data["storage_capacity_gb"],
                    profile_data["network_speed_mbps"],
                    profile_data["os_platform"],
                    profile_data["os_version"],
                    profile_data["python_version"],
                    profile_data["available_models"],
                    profile_data["performance_benchmarks"],
                    profile_data["timestamp"],
                ),
            )

            conn.commit()
            self.logger.info(f"Stored hardware profile: {profile_name}")
            return profile_data

        except Exception as e:
            self.logger.error(f"Failed to store hardware profile: {e}")
            return {}

    def index_codebase(self, root_path: Union[str, Path], file_patterns: Optional[List[str]] = None) -> int:
        """Index entire codebase for fast lookup"""
        if file_patterns is None:
            file_patterns = ["*.py", "*.rs", "*.js", "*.ts", "*.java", "*.cpp", "*.c"]
        if not isinstance(root_path, Path):
            root_path = Path(root_path)
        indexed_count = 0
        for pattern in file_patterns:
            for file_path in root_path.rglob(pattern):
                try:
                    if self._index_file(file_path):
                        indexed_count += 1
                except Exception as e:
                    self.logger.warning(f"Failed to index {file_path}: {e}")
        self.logger.info(f"Indexed {indexed_count} files")
        return indexed_count

    def _index_file(self, file_path: Path) -> bool:
        """Index a single file"""
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            content_hash = hashlib.sha256(content.encode()).hexdigest()

            # Parse file structure
            file_info = self._parse_file_structure(content, file_path)

            conn = self._get_connection()
            cursor = conn.cursor()

            # Check if file already indexed with same hash
            cursor.execute(
                "SELECT id FROM code_index WHERE file_path = ? AND content_hash = ?",
                (str(file_path), content_hash),
            )
            if cursor.fetchone():
                return False  # Already indexed with same content

            # Store file information
            cursor.execute(
                """
                INSERT INTO code_index
                (file_path, file_name, file_extension, function_name, class_name,
                 module_name, code_snippet, docstring, imports, dependencies,
                 complexity_score, lines_of_code, last_modified, git_hash, tags,
                 content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(file_path),
                    file_path.name,
                    file_path.suffix,
                    file_info.get("function_name"),
                    file_info.get("class_name"),
                    file_info.get("module_name"),
                    file_info.get("code_snippet"),
                    file_info.get("docstring"),
                    json.dumps(file_info.get("imports", [])),
                    json.dumps(file_info.get("dependencies", [])),
                    file_info.get("complexity_score", 0.0),
                    file_info.get("lines_of_code", 0),
                    datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
                    self._get_git_hash(file_path),
                    file_info.get("tags", ""),
                    content_hash,
                ),
            )

            conn.commit()
            return True

        except Exception as e:
            self.logger.error(f"Failed to index file {file_path}: {e}")
            return False

    def cache_documentation(
        self,
        doc_type: str,
        title: str,
        content: str,
        source_url: Optional[str] = None,
        package_name: Optional[str] = None,
        language: Optional[str] = None,
        tags: Optional[str] = None,
    ) -> bool:
        """Cache documentation for local retrieval"""
        try:
            content_hash = hashlib.sha256(content.encode()).hexdigest()

            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT OR REPLACE INTO documentation_cache
                (doc_type, title, content, source_url, package_name, language, tags,
                 relevance_score, content_hash, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    doc_type,
                    title,
                    content,
                    source_url,
                    package_name,
                    language,
                    tags,
                    1.0,
                    content_hash,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

            # Update search index
            cursor.execute(
                """
                INSERT OR REPLACE INTO search_index
                (content, title, tags, doc_type, file_path, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    content,
                    title,
                    tags or "",
                    doc_type,
                    source_url or "",
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

            conn.commit()
            self.logger.info(f"Cached documentation: {title}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to cache documentation: {e}")
            return False

    def record_code_change(
        self,
        file_path: str,
        change_type: str,
        old_content: Optional[str] = None,
        new_content: Optional[str] = None,
        commit_hash: Optional[str] = None,
        commit_message: Optional[str] = None,
        author: Optional[str] = None,
    ) -> bool:
        """Record code changes for history tracking"""
        try:
            diff_summary = self._generate_diff_summary(
                old_content if old_content is not None else "",
                new_content if new_content is not None else ""
            )
            impact_score = self._calculate_impact_score(
                old_content if old_content is not None else "",
                new_content if new_content is not None else ""
            )
            affected_functions = self._identify_affected_functions(
                old_content if old_content is not None else "",
                new_content if new_content is not None else ""
            )
            breaking_change = self._detect_breaking_changes(
                old_content if old_content is not None else "",
                new_content if new_content is not None else ""
            )
            tags = self._generate_change_tags(change_type, impact_score)

            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO code_changes
                (file_path, change_type, old_content, new_content, diff_summary,
                 commit_hash, commit_message, author, timestamp, impact_score,
                 affected_functions, breaking_changes, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    file_path,
                    change_type,
                    old_content,
                    new_content,
                    diff_summary,
                    commit_hash,
                    commit_message,
                    author,
                    datetime.now(timezone.utc).isoformat(),
                    impact_score,
                    json.dumps(affected_functions),
                    breaking_change,
                    tags,
                ),
            )

            conn.commit()
            self.logger.info(f"Recorded code change: {file_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to record code change: {e}")
            return False

    def search_knowledge(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search across all knowledge bases"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Search in documentation cache
            cursor.execute(
                """
                SELECT 'documentation' as source, title, content, relevance_score,
                       timestamp
                FROM documentation_cache
                WHERE content LIKE ? OR title LIKE ?
                ORDER BY relevance_score DESC, last_accessed DESC
                LIMIT ?
                """,
                (f"%{query}%", f"%{query}%", limit),
            )

            docs_results = cursor.fetchall()

            # Search in code index
            cursor.execute(
                """
                SELECT 'code' as source, function_name as title, code_snippet as
                       content, complexity_score as relevance_score, timestamp
                FROM code_index
                WHERE function_name LIKE ? OR class_name LIKE ? OR code_snippet
                      LIKE ?
                ORDER BY complexity_score DESC, timestamp DESC
                LIMIT ?
                """,
                (f"%{query}%", f"%{query}%", f"%{query}%", limit),
            )

            code_results = cursor.fetchall()

            # Search in architectural patterns
            cursor.execute(
                """
                SELECT 'pattern' as source, pattern_name as title,
                       solution_description as content, 1.0 as relevance_score,
                       timestamp
                FROM architectural_patterns
                WHERE pattern_name LIKE ? OR problem_description LIKE ? OR
                      solution_description LIKE ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (f"%{query}%", f"%{query}%", f"%{query}%", limit),
            )

            pattern_results = cursor.fetchall()

            # Combine and rank results
            all_results = []
            for result in docs_results + code_results + pattern_results:
                all_results.append(
                    {
                        "source": result[0],
                        "title": result[1],
                        "content": result[2],
                        "relevance_score": result[3],
                        "timestamp": result[4],
                    }
                )

            # Sort by relevance and recency
            all_results.sort(
                key=lambda x: (x["relevance_score"], x["timestamp"]), reverse=True
            )

            return all_results[:limit]

        except Exception as e:
            self.logger.error(f"Search failed: {e}")
            return []

    def get_hardware_profile(self, profile_name: str = "current") -> Dict[str, Any]:
        """Retrieve hardware profile"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT * FROM hardware_profiles WHERE profile_name = ?
                ORDER BY timestamp DESC LIMIT 1
            """,
                (profile_name,),
            )

            row = cursor.fetchone()
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
            return {}

        except Exception as e:
            self.logger.error(f"Failed to get hardware profile: {e}")
            return {}

    def get_file_history(self, file_path: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get change history for a file"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT * FROM code_changes
                WHERE file_path = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                (file_path, limit),
            )

            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]

            return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            self.logger.error(f"Failed to get file history: {e}")
            return []

    def get_project_context(self, project_path: str) -> Dict[str, Any]:
        """Get project context and configuration"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT * FROM project_context
                WHERE project_path = ? AND active = TRUE
                ORDER BY last_updated DESC LIMIT 1
            """,
                (project_path,),
            )

            row = cursor.fetchone()
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
            return {}

        except Exception as e:
            self.logger.error(f"Failed to get project context: {e}")
            return {}

    # Helper methods for hardware information gathering
    def _gather_cpu_info(self) -> Dict[str, Any]:
        """Gather CPU information"""
        try:
            cpu_info = {
                "model": platform.processor(),
                "cores": psutil.cpu_count(logical=False),
                "threads": psutil.cpu_count(logical=True),
            }
            return cpu_info
        except Exception:
            return {"model": "Unknown", "cores": 0, "threads": 0}

    def _gather_memory_info(self) -> Dict[str, Any]:
        """Gather memory information"""
        try:
            memory = psutil.virtual_memory()
            return {"total_gb": memory.total / (1024**3)}
        except Exception:
            return {"total_gb": 0}

    def _gather_gpu_info(self) -> Dict[str, Any]:
        """Gather GPU information"""
        try:
            # This is a simplified version - could be enhanced with GPU libraries
            return {"model": "Unknown", "vram_gb": 0}
        except Exception:
            return {"model": "Unknown", "vram_gb": 0}

    def _gather_storage_info(self) -> Dict[str, Any]:
        """Gather storage information"""
        try:
            disk = psutil.disk_usage("/")
            return {"type": "Unknown", "capacity_gb": disk.total / (1024**3)}
        except Exception:
            return {"type": "Unknown", "capacity_gb": 0}

    def _gather_network_info(self) -> Dict[str, Any]:
        """Gather network information"""
        try:
            return {"speed_mbps": 1000}  # Default assumption
        except Exception:
            return {"speed_mbps": 0}

    def _gather_os_info(self) -> Dict[str, Any]:
        """Gather OS information"""
        try:
            return {"platform": platform.system(), "version": platform.version()}
        except Exception:
            return {"platform": "Unknown", "version": "Unknown"}

    def _gather_python_info(self) -> Dict[str, Any]:
        """Gather Python information"""
        try:
            return {"version": platform.python_version()}
        except Exception:
            return {"version": "Unknown"}

    def _gather_available_models(self) -> List[str]:
        """Gather available model paths"""
        try:
            models = []
            # Check common model directories
            model_dirs = ["~/models", "~/.cache/huggingface", "/usr/local/models"]
            for model_dir in model_dirs:
                expanded_dir = os.path.expanduser(model_dir)
                if os.path.exists(expanded_dir):
                    for root, dirs, files in os.walk(expanded_dir):
                        for file in files:
                            if file.endswith((".gguf", ".bin", ".safetensors")):
                                models.append(os.path.join(root, file))
            return models
        except Exception:
            return []

    def _run_benchmarks(self) -> Dict[str, Any]:
        """Run basic performance benchmarks"""
        try:
            import time

            start_time = time.time()

            # Simple benchmark: count to 1 million
            for i in range(1000000):
                pass

            end_time = time.time()
            cpu_benchmark = end_time - start_time

            return {
                "cpu_benchmark_seconds": cpu_benchmark,
                "memory_available_gb": psutil.virtual_memory().available / (1024**3),
            }
        except Exception:
            return {}

    def _parse_file_structure(self, content: str, file_path: Path) -> Dict[str, Any]:
        """Parse file structure for indexing"""
        try:
            file_info: Dict[str, Any] = {
                "function_name": None,
                "class_name": None,
                "module_name": file_path.stem,
                "code_snippet": content[:1000],  # First 1000 chars
                "docstring": "",
                "imports": [],
                "dependencies": [],
                "complexity_score": 0.0,
                "lines_of_code": len(content.splitlines()),
                "tags": "",
            }

            # Try to parse as Python
            if file_path.suffix == ".py":
                try:
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef):
                            file_info["function_name"] = node.name
                            if ast.get_docstring(node):
                                file_info["docstring"] = ast.get_docstring(node)
                            break
                        elif isinstance(node, ast.ClassDef):
                            file_info["class_name"] = node.name
                            break

                    # Extract imports
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            if isinstance(file_info["imports"], list):
                                for alias in node.names:
                                    file_info["imports"].append(alias.name)
                        elif isinstance(node, ast.ImportFrom):
                            if node.module and isinstance(file_info["imports"], list):
                                file_info["imports"].append(node.module)

                except SyntaxError:
                    pass  # Not valid Python, skip parsing

            return file_info

        except Exception:
            return {
                "function_name": None,
                "class_name": None,
                "module_name": file_path.stem,
                "code_snippet": content[:1000],
                "docstring": "",
                "imports": [],
                "dependencies": [],
                "complexity_score": 0.0,
                "lines_of_code": len(content.splitlines()),
                "tags": "",
            }

    def _get_git_hash(self, file_path: Path) -> str:
        """Get git hash for file"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=file_path.parent,
                capture_output=True,
                text=True,
            )
            return result.stdout.strip() if result.returncode == 0 else ""
        except Exception:
            return ""

    def _generate_diff_summary(self, old_content: str, new_content: str) -> str:
        """Generate summary of changes"""
        if not old_content and not new_content:
            return "No content"
        elif not old_content:
            return "File added"
        elif not new_content:
            return "File deleted"
        else:
            old_lines = old_content.splitlines()
            new_lines = new_content.splitlines()
            return f"Modified: {len(old_lines)} -> {len(new_lines)} lines"

    def _calculate_impact_score(self, old_content: str, new_content: str) -> float:
        """Calculate impact score of changes"""
        if not old_content or not new_content:
            return 1.0  # High impact for additions/deletions

        # Simple heuristic: more changes = higher impact
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()

        changed_lines = abs(len(new_lines) - len(old_lines))
        total_lines = max(len(old_lines), len(new_lines))

        if total_lines == 0:
            return 0.0

        return min(1.0, changed_lines / total_lines)

    def _identify_affected_functions(
        self, old_content: str, new_content: str
    ) -> List[str]:
        """Identify functions affected by changes"""
        # This is a simplified version - could be enhanced with AST analysis
        return []

    def _detect_breaking_changes(self, old_content: str, new_content: str) -> bool:
        """Detect if changes are breaking"""
        # This is a simplified version - could be enhanced with semantic analysis
        return False

    def _generate_change_tags(self, change_type: str, impact_score: float) -> str:
        """Generate tags for change tracking"""
        tags = [change_type]
        if impact_score > 0.5:
            tags.append("high-impact")
        elif impact_score > 0.2:
            tags.append("medium-impact")
        else:
            tags.append("low-impact")
        return ",".join(tags)

    def close(self) -> None:
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
