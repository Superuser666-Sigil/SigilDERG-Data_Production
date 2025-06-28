# utils/http_client_utils.py
"""
Atomic HTTP client utilities - extracted from duplicate network patterns
"""
import time
import logging
import requests
from requests_cache import CachedSession
from typing import Dict, Union, Optional, Any
import re


class HTTPClientUtils:
    """Atomic unit for HTTP client operations"""

    @staticmethod
    def create_cached_session(cache_name: str, cache_ttl: int) -> CachedSession:
        """Create a standardized cached session - atomic unit"""
        return CachedSession(cache_name, expire_after=cache_ttl)

    @staticmethod
    def fetch_with_retry(
        session: requests.Session,
        url: str,
        max_retries: int = 3,
        headers: Optional[Dict[str, str]] = None,
    ) -> Optional[requests.Response]:
        """Fetch URL with exponential backoff retry - atomic unit"""
        for attempt in range(max_retries):
            try:
                response = session.get(url, headers=headers or {})
                if response.ok:
                    return response
                else:
                    logging.warning(
                        f"HTTP {
                            response.status_code} for {url} on attempt {
                            attempt + 1}"
                    )
            except Exception as e:
                logging.warning(
                    f"Attempt {
                        attempt +
                        1} failed for {url}: {
                        str(e)}"
                )

            if attempt < max_retries - 1:  # Don't sleep on the last attempt
                wait_time = 2**attempt
                time.sleep(wait_time)

        return None

    @staticmethod
    def extract_github_repo_info(repo_url: str) -> Optional[tuple[str, str]]:
        """Extract owner/repo from GitHub URL - atomic unit"""
        if not repo_url or "github.com" not in repo_url:
            return None

        match = re.search(r"github\.com/([^/]+)/([^/]+)", repo_url)
        if match:
            owner, repo_name = match.groups()
            # Handle .git extensions
            repo_name = repo_name.split(".")[0]
            return owner, repo_name

        return None

    @staticmethod
    def get_github_headers(token: Optional[str] = None) -> Dict[str, str]:
        """Get standardized GitHub API headers - atomic unit"""
        headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            headers["Authorization"] = f"token {token}"
        return headers


class MetadataExtractor:
    """Atomic unit for extracting metadata from different sources"""

    @staticmethod
    def extract_code_snippets(readme: str) -> list[str]:
        """Extract Rust code snippets from markdown README - atomic unit"""
        if not readme:
            return []  # Find Rust code blocks
        pattern = (
            r"```(?:rust|(?:Union[no_run, ignore]|Union[compile_fail, mdbook]-runnable)?)"
            r"\s*([\s\S]*?)```"
        )
        matches = re.findall(pattern, readme)

        snippets = []
        for code in matches:
            if len(code.strip()) > 10:  # Only include non-trivial snippets
                snippets.append(code.strip())

        return snippets[:5]  # Limit to 5 snippets

    @staticmethod
    def extract_readme_sections(readme: str) -> Dict[str, str]:
        """Extract sections from README based on markdown headers - atomic unit"""
        if not readme:
            return {}

        sections: Dict[str, str] = {}
        current_section = "intro"
        current_content: list[str] = []

        lines = readme.split("\n")
        for line in lines:
            if line.startswith("#"):
                # Save previous section
                if current_content:
                    sections[current_section] = "\n".join(current_content).strip()

                # Start new section
                current_section = line.strip("#").strip().lower().replace(" ", "_")
                current_content = []
            else:
                current_content.append(line)

        # Save final section
        if current_content:
            sections[current_section] = "\n".join(current_content).strip()

        return sections

    @staticmethod
    def create_empty_metadata() -> Dict[str, Any]:
        """Create standardized empty metadata structure - atomic unit"""
        return {
            "name": "",
            "version": "",
            "description": "",
            "repository": "",
            "keywords": [],
            "categories": [],
            "readme": "",
            "downloads": 0,
            "github_stars": 0,
            "dependencies": [],
            "code_snippets": [],
            "features": [],
            "readme_sections": {},
            "source": "unknown",
        }
