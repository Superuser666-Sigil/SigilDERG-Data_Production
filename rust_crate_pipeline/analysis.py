# analysis.py
from __future__ import annotations

import io
import re
import tarfile
import requests
import logging
import tempfile
from typing import Any, Dict, List, Optional, Union
import os
import sys
import time
import subprocess
from dataclasses import dataclass

from .config import EnrichedCrate

# Create a fallback RustCodeAnalyzer that doesn't depend on external utils
class RustCodeAnalyzer:
    """Fallback Rust code analyzer for when the full analyzer is not available."""
    
    def __init__(self, code_content: str) -> None:
        self.code_content = code_content

    def analyze(self) -> dict[str, Any]:
        """Basic analysis of Rust code content."""
        lines = self.code_content.split('\n')
        return {
            "functions": self._count_functions(),
            "structs": self._count_structs(),
            "enums": self._count_enums(),
            "traits": self._count_traits(),
            "complexity": self._calculate_complexity(),
            "lines_of_code": len(lines),
        }

    def _count_functions(self) -> int:
        """Count function definitions."""
        return len(re.findall(r'fn\s+\w+\s*\(', self.code_content))

    def _count_structs(self) -> int:
        """Count struct definitions."""
        return len(re.findall(r'struct\s+\w+', self.code_content))

    def _count_enums(self) -> int:
        """Count enum definitions."""
        return len(re.findall(r'enum\s+\w+', self.code_content))

    def _count_traits(self) -> int:
        """Count trait definitions."""
        return len(re.findall(r'trait\s+\w+', self.code_content))

    def _calculate_complexity(self) -> int:
        """Calculate basic cyclomatic complexity."""
        complexity = 0
        complexity += len(re.findall(r'\bif\b', self.code_content))
        complexity += len(re.findall(r'\bfor\b', self.code_content))
        complexity += len(re.findall(r'\bwhile\b', self.code_content))
        complexity += len(re.findall(r'\bmatch\b', self.code_content))
        return complexity

    @staticmethod
    def create_empty_metrics() -> dict[str, Any]:
        """Create empty metrics structure."""
        return {
            "functions": 0,
            "structs": 0,
            "enums": 0,
            "traits": 0,
            "complexity": 0,
            "lines_of_code": 0,
            "file_count": 0,
        }

    @staticmethod
    def detect_project_structure(files: list[str]) -> dict[str, bool]:
        """Detect basic project structure."""
        return {
            "has_cargo_toml": any("Cargo.toml" in f for f in files),
            "has_src": any("/src/" in f for f in files),
            "has_tests": any("/tests/" in f for f in files),
            "has_examples": any("/examples/" in f for f in files),
        }

    @staticmethod
    def analyze_rust_content(content: str) -> dict[str, Any]:
        """Analyze Rust content."""
        analyzer = RustCodeAnalyzer(content)
        return analyzer.analyze()

    @staticmethod
    def aggregate_metrics(
        metrics: dict[str, Any],
        content_analysis: dict[str, Any],
        structure: dict[str, bool],
    ) -> dict[str, Any]:
        """Aggregate metrics from multiple sources."""
        for key, value in content_analysis.items():
            if isinstance(value, (int, float)):
                metrics[key] = metrics.get(key, 0) + value
            elif isinstance(value, list):
                if key not in metrics:
                    metrics[key] = []
                metrics[key].extend(value)
        
        # Add structure information
        metrics.update(structure)
        return metrics


# Constants for URLs and paths
CRATES_IO_API_URL = "https://crates.io/api/v1/crates"
GITHUB_API_URL = "https://api.github.com/repos"
LIB_RS_URL = "https://lib.rs/crates"


class SourceAnalyzer:
    @staticmethod
    def analyze_crate_source(crate: EnrichedCrate) -> dict[str, Any]:
        """Orchestrate source analysis from multiple sources."""
        repo_url = crate.repository

        # Method 1: Try to download from crates.io
        try:
            url = f"{CRATES_IO_API_URL}/{crate.name}/{crate.version}/download"
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            logging.info(f"Successfully downloaded {crate.name} from crates.io")
            return SourceAnalyzer.analyze_crate_tarball(response.content)
        except requests.RequestException as e:
            logging.warning(f"Failed to download from crates.io: {e}")

        # Method 2: Try GitHub if we have a GitHub URL
        if repo_url and "github.com" in repo_url:
            match = re.search(r"github\.com/([^/]+)/([^/]+)", repo_url)
            if match:
                owner, repo_name = match.groups()
                repo_name = repo_name.replace(".git", "")
                try:
                    github_url = f"{GITHUB_API_URL}/{owner}/{repo_name}/tarball"
                    response = requests.get(github_url, timeout=30)
                    response.raise_for_status()
                    logging.info(f"Successfully downloaded {crate.name} from GitHub")
                    return SourceAnalyzer.analyze_github_tarball(response.content)
                except requests.RequestException as e:
                    logging.warning(f"Failed to analyze from GitHub: {e}")

        # Method 3: Fallback to cloning from the repository directly
        if repo_url:
            try:
                logging.info(f"Attempting to clone repository for {crate.name}")
                return SourceAnalyzer.analyze_crate_source_from_repo(repo_url)
            except Exception as e:
                logging.error(f"Failed to clone and analyze repository {repo_url}: {e}")

        return {
            "error": "Could not analyze crate from any available source.",
            "attempted_sources": ["crates.io", "github", "git_clone"],
            "file_count": 0,
            "loc": 0,
        }

    @staticmethod
    def _analyze_tarball_content(content: bytes) -> dict[str, Any]:
        """Shared logic to analyze tarball content from any source."""
        metrics = RustCodeAnalyzer.create_empty_metrics()
        try:
            with io.BytesIO(content) as tar_content, tarfile.open(
                fileobj=tar_content, mode="r:gz"
            ) as tar:
                rust_files = [f for f in tar.getnames() if f.endswith(".rs")]
                metrics["file_count"] = len(rust_files)
                structure = RustCodeAnalyzer.detect_project_structure(tar.getnames())

                for member in tar.getmembers():
                    if member.isfile() and member.name.endswith(".rs"):
                        file_content = tar.extractfile(member)
                        if file_content:
                            try:
                                content_str = file_content.read().decode("utf-8")
                                analysis = RustCodeAnalyzer.analyze_rust_content(
                                    content_str
                                )
                                metrics = RustCodeAnalyzer.aggregate_metrics(
                                    metrics, analysis, structure
                                )
                            except UnicodeDecodeError:
                                logging.warning(
                                    f"Skipping non-UTF-8 file: {member.name}"
                                )
        except tarfile.TarError as e:
            metrics["error"] = f"Failed to read tarball: {e}"
            logging.error(metrics["error"])
        return metrics

    @staticmethod
    def analyze_crate_tarball(content: bytes) -> dict[str, Any]:
        """Analyze a .crate tarball from crates.io."""
        return SourceAnalyzer._analyze_tarball_content(content)

    @staticmethod
    def analyze_github_tarball(content: bytes) -> dict[str, Any]:
        """Analyze a GitHub tarball."""
        return SourceAnalyzer._analyze_tarball_content(content)

    @staticmethod
    def analyze_local_directory(directory: str) -> dict[str, Any]:
        """Analyze source code from a local directory."""
        metrics = RustCodeAnalyzer.create_empty_metrics()
        try:
            rust_files: list[str] = []
            all_paths: list[str] = []
            for root, dirs, files in os.walk(directory):
                # Exclude target and .git directories
                dirs[:] = [d for d in dirs if d not in ["target", ".git"]]
                for file in files:
                    full_path = os.path.join(root, file)
                    all_paths.append(full_path)
                    if file.endswith(".rs"):
                        rust_files.append(full_path)

            metrics["file_count"] = len(rust_files)
            structure = RustCodeAnalyzer.detect_project_structure(all_paths)

            for file_path in rust_files:
                try:
                    with open(file_path, encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    analysis = RustCodeAnalyzer.analyze_rust_content(content)
                    metrics = RustCodeAnalyzer.aggregate_metrics(
                        metrics, analysis, structure
                    )
                except Exception as e:
                    logging.warning(f"Error analyzing file {file_path}: {e}")
        except Exception as e:
            metrics["error"] = f"Failed to analyze local directory {directory}: {e}"
            logging.error(metrics["error"])
        return metrics

    @staticmethod
    def analyze_crate_source_from_repo(repo_url: str) -> dict[str, Any]:
        """Clone and analyze a crate's source code from a repository."""
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                logging.info(f"Cloning {repo_url} into {temp_dir}")
                subprocess.run(
                    ["git", "clone", "--depth=1", repo_url, temp_dir],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=120,
                )
                return SourceAnalyzer.analyze_local_directory(temp_dir)
            except (
                subprocess.CalledProcessError,
                subprocess.TimeoutExpired,
            ) as e:
                error_output = ""
                if hasattr(e, "stderr") and e.stderr:
                    error_output = e.stderr.decode("utf-8", "ignore")
                else:
                    error_output = str(e)
                logging.error(f"Failed to clone repository {repo_url}: {error_output}")
                return {
                    "error": f"Failed to clone repository: {error_output}",
                    "file_count": 0,
                    "loc": 0,
                }


class SecurityAnalyzer:
    @staticmethod
    def check_security_metrics(crate: EnrichedCrate) -> dict[str, Any]:
        """Check security metrics for a crate (placeholder)."""
        security_data: dict[str, Any] = {
            "advisories": [],
            "vulnerability_count": 0,
            "cargo_audit": None,
            "unsafe_blocks": 0,
        }
        # In a real implementation, this would run tools like `cargo-audit`
        # and parse the output. For now, it remains a placeholder.
        logging.info(f"Running placeholder security check for {crate.name}")
        return security_data


class UserBehaviorAnalyzer:
    @staticmethod
    def _get_github_headers() -> dict[str, str]:
        """Get headers for GitHub API requests, including auth if available."""
        headers = {"Accept": "application/vnd.github.v3+json"}
        if token := os.environ.get("GITHUB_TOKEN"):
            headers["Authorization"] = f"token {token}"
        return headers

    @staticmethod
    def fetch_user_behavior_data(crate: EnrichedCrate) -> dict[str, Any]:
        """Fetch user behavior data from GitHub and crates.io."""
        result: dict[str, Any] = {
            "issues": [],
            "pull_requests": [],
            "version_adoption": {},
            "community_metrics": {},
        }
        repo_url = crate.repository
        if not repo_url or "github.com" not in repo_url:
            return result

        match = re.search(r"github\.com/([^/]+)/([^/]+)", repo_url)
        if not match:
            return result
        owner, repo = match.groups()
        repo = repo.replace(".git", "")

        headers = UserBehaviorAnalyzer._get_github_headers()
        UserBehaviorAnalyzer._fetch_github_activity(owner, repo, headers, result)
        UserBehaviorAnalyzer._fetch_crates_io_versions(crate.name, result)

        return result

    @staticmethod
    def _fetch_github_activity(
        owner: str, repo: str, headers: dict[str, str], result: dict[str, Any]
    ) -> None:
        """Fetch issues, PRs, and commit activity from GitHub."""
        try:
            issues_url = f"{GITHUB_API_URL}/{owner}/{repo}/issues?state=all&per_page=30"
            issues_resp = requests.get(issues_url, headers=headers, timeout=30)
            issues_resp.raise_for_status()

            for item in issues_resp.json():
                is_pr = "pull_request" in item
                data_list = result["pull_requests"] if is_pr else result["issues"]
                data_list.append(
                    {
                        "number": item["number"],
                        "title": item["title"],
                        "state": item["state"],
                        "created_at": item["created_at"],
                        "closed_at": item["closed_at"],
                        "url": item["html_url"],
                    }
                )

            # Fetch commit activity (retries on 202)
            activity_url = f"{GITHUB_API_URL}/{owner}/{repo}/stats/commit_activity"
            for _ in range(3):  # Retry up to 3 times
                activity_resp = requests.get(activity_url, headers=headers, timeout=60)
                if activity_resp.status_code == 200:
                    result["community_metrics"][
                        "commit_activity"
                    ] = activity_resp.json()
                    break
                elif activity_resp.status_code == 202:
                    logging.info(
                        f"GitHub is calculating stats for {owner}/{repo}, waiting..."
                    )
                    time.sleep(2)
                else:
                    activity_resp.raise_for_status()

        except requests.RequestException as e:
            logging.warning(f"Error fetching GitHub data for {owner}/{repo}: {e}")

    @staticmethod
    def _fetch_crates_io_versions(crate_name: str, result: dict[str, Any]) -> None:
        """Fetch version adoption data from crates.io."""
        try:
            versions_url = f"{CRATES_IO_API_URL}/{crate_name}/versions"
            versions_resp = requests.get(versions_url, timeout=30)
            versions_resp.raise_for_status()
            versions_data = versions_resp.json().get("versions", [])

            for version in versions_data[:10]:  # Top 10 versions
                result["version_adoption"][version["num"]] = {
                    "downloads": version["downloads"],
                    "created_at": version["created_at"],
                }
        except requests.RequestException as e:
            logging.warning(
                f"Error fetching crates.io version data for {crate_name}: {e}"
            )


class DependencyAnalyzer:
    @staticmethod
    def analyze_dependencies(crates: list[EnrichedCrate]) -> dict[str, Any]:
        """Analyze dependencies within a given list of crates."""
        crate_names = {crate.name for crate in crates}
        dependency_graph: dict[str, list[str]] = {
            crate.name: [
                dep_id
                for dep in crate.dependencies
                if (dep_id := dep.get("crate_id")) and dep_id in crate_names
            ]
            for crate in crates
        }

        reverse_deps: dict[str, list[str]] = {}
        for crate_name, deps in dependency_graph.items():
            for dep in deps:
                if dep:  # Ensure dep is not None
                    reverse_deps.setdefault(dep, []).append(crate_name)

        most_depended = sorted(
            reverse_deps.items(), key=lambda item: len(item[1]), reverse=True
        )[:10]

        return {
            "dependency_graph": dependency_graph,
            "reverse_dependencies": reverse_deps,
            "most_depended": most_depended,
        }
