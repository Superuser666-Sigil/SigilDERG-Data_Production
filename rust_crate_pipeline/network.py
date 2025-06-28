# network.py
import os
import re
import sys
import time
import logging
import requests
from typing import Any, Dict, List, Optional, Union
from bs4 import BeautifulSoup, Tag
from .config import PipelineConfig


class GitHubBatchClient:
    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        # Simple headers without dependency on HTTPClientUtils
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "SigilDERG-Data-Production/1.3.2",
        }
        if config.github_token:
            self.headers["Authorization"] = f"token {config.github_token}"

        # Simple session without dependency on HTTPClientUtils
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.remaining_calls = 5000
        self.reset_time = 0

    def check_rate_limit(self) -> None:
        """Check and update current rate limit status"""
        try:
            response = self.session.get(
                "https://api.github.com/rate_limit", headers=self.headers
            )
            if response.ok:
                data = response.json()
                self.remaining_calls = data["resources"]["core"]["remaining"]
                self.reset_time = data["resources"]["core"]["reset"]

                if self.remaining_calls < 100:
                    reset_in = self.reset_time - time.time()
                    logging.warning(
                        f"GitHub API rate limit low: {self.remaining_calls} remaining. Resets in {reset_in / 60:.1f} minutes"
                    )
        except Exception:
            pass

    def get_repo_stats(self, owner: str, repo: str) -> "dict[str, Any]":
        """Get repository statistics"""
        try:
            url = f"https://api.github.com/repos/{owner}/{repo}"
            response = self.session.get(url, headers=self.headers)
            if response.ok:
                return response.json()
            else:
                logging.warning(
                    f"Failed to get repo stats for {owner}/{repo}: {response.status_code}"
                )
                return {}
        except Exception as e:
            logging.error(f"Error fetching repo stats: {str(e)}")
            return {}

    def batch_get_repo_stats(self, repo_list: "list[str]") -> "dict[str, dict[str, Any]]":
        """Get statistics for multiple repositories in a batch"""
        self.check_rate_limit()

        results: "dict[str, dict[str, Any]]" = {}
        for repo_url in repo_list:
            # Extract owner/repo from URL
            match = re.search(r"github\.com/([^/]+)/([^/\.]+)", repo_url)
            if not match:
                continue

            owner, repo = match.groups()
            repo = repo.split(".")[0]  # Remove .git extension if present

            # Get stats
            stats = self.get_repo_stats(owner, repo)
            results[repo_url] = stats

            # Be nice to GitHub API
            time.sleep(0.1)
        return results


class CrateAPIClient:
    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        # Simple session without dependency on HTTPClientUtils
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "SigilDERG-Data-Production/1.3.2"})

    def fetch_crate_metadata(self, crate_name: str) -> "dict[str, Any] | None":
        """Fetch metadata with retry logic"""
        for attempt in range(self.config.max_retries):
            try:
                return self._fetch_metadata(crate_name)
            except Exception as e:
                logging.warning(
                    f"Attempt {attempt + 1} failed for {crate_name}: {str(e)}"
                )
                wait = 2**attempt
                time.sleep(wait)
        return None

    def _fetch_metadata(self, crate_name: str) -> "dict[str, Any] | None":
        """Enhanced metadata fetching that tries multiple sources"""
        # First try crates.io (primary source)
        try:
            r = self.session.get(f"https://crates.io/api/v1/crates/{crate_name}")
            if r.ok:
                data = r.json()
                crate_data = data["crate"]
                latest = crate_data["newest_version"]

                # Get readme
                readme_response = self.session.get(
                    f"https://crates.io/api/v1/crates/{crate_name}/readme"
                )
                readme = readme_response.text if readme_response.ok else ""

                # Get dependencies
                deps_url = (
                    f"https://crates.io/api/v1/crates/{crate_name}/"
                    f"{latest}/dependencies"
                )
                deps_response = self.session.get(deps_url)
                deps: list[dict[str, Any]] = (
                    deps_response.json().get("dependencies", [])
                    if deps_response.ok
                    else []
                )

                # Get features - using the versions endpoint
                features = []
                versions_response = self.session.get(
                    f"https://crates.io/api/v1/crates/{crate_name}/{latest}"
                )
                if versions_response.ok:
                    version_data = versions_response.json().get("version", {})
                    features_dict = version_data.get("features", {})
                    features = [
                        {"name": k, "dependencies": v} for k, v in features_dict.items()
                    ]

                # Repository info and GitHub stars
                repo = crate_data.get("repository", "")
                gh_stars = 0

                # Check if it's a GitHub repo
                if "github.com" in repo and self.config.github_token:
                    match = re.search(r"github.com/([^/]+)/([^/]+)", repo)
                    if match:
                        owner, repo_name = match.groups()
                        repo_name = repo_name.split(".")[0]  # Handle .git extensions
                        gh_url = f"https://api.github.com/repos/{owner}/{repo_name}"
                        gh_headers: dict[str, str] = {}
                        if self.config.github_token:
                            gh_headers["Authorization"] = (
                                f"token {self.config.github_token}"
                            )

                        gh = self.session.get(gh_url, headers=gh_headers)
                        if gh.ok:
                            gh_data = gh.json()
                            gh_stars = gh_data.get("stargazers_count", 0)

                # Check if it's hosted on lib.rs
                lib_rs_data = {}
                if "lib.rs" in repo:
                    lib_rs_url = f"https://lib.rs/crates/{crate_name}"
                    lib_rs_response = self.session.get(lib_rs_url)
                    if lib_rs_response.ok:
                        soup = BeautifulSoup(lib_rs_response.text, "html.parser")
                        # Get README from lib.rs if not already available
                        if not readme:
                            readme_div = soup.find("div", class_="readme")
                            if readme_div:
                                readme = readme_div.get_text(
                                    strip=True
                                )  # Get lib.rs specific stats
                        stats_div = soup.find("div", class_="crate-stats")
                        if isinstance(stats_div, Tag):
                            downloads_text = stats_div.find(
                                string=re.compile(r"[\d,]+ downloads")
                            )
                            if downloads_text:
                                lib_rs_data["librs_downloads"] = int(
                                    re.sub(r"[^\d]", "", str(downloads_text))
                                )

                # Extract code snippets and sections (simplified)
                code_snippets: list[str] = (
                    []
                )  # Simplified - would normally extract from readme
                readme_sections: dict[str, str] = (
                    {}
                )  # Simplified - would normally parse sections

                result: dict[str, Any] = {
                    "name": crate_name,
                    "version": latest,
                    "description": crate_data.get("description", ""),
                    "repository": repo,
                    "keywords": crate_data.get("keywords", []),
                    "categories": crate_data.get("categories", []),
                    "readme": readme,
                    "downloads": crate_data.get("downloads", 0),
                    "github_stars": gh_stars,
                    "dependencies": deps,
                    "code_snippets": code_snippets,
                    "features": features,
                    "readme_sections": readme_sections,
                    **lib_rs_data,
                }

                return result

        except Exception as e:
            logging.error(
                f"Failed fetching metadata for {crate_name}: {str(e)}"
            )
            raise

        # If crates.io fails, try lib.rs
        try:
            r = self.session.get(f"https://lib.rs/crates/{crate_name}")
            if r.ok:
                soup = BeautifulSoup(r.text, "html.parser")

                # Extract metadata from lib.rs page
                h1 = soup.select_one("h1")
                name = h1.text.strip() if h1 else crate_name

                # Find description
                desc_elem = soup.select_one(".description")
                description = desc_elem.text.strip() if desc_elem else ""

                # Find repository link
                repo_link: Union[str, None] = None
                for a in soup.select("a"):
                    href = a.get("href")
                    if href and isinstance(href, str) and "github.com" in href:
                        repo_link = href
                        break

                # Find keywords
                keywords_elem = soup.select_one(".keywords")
                keywords = (
                    [k.text.strip() for k in keywords_elem.find_all("a")]
                    if keywords_elem
                    else []
                )

                # Basic metadata from lib.rs
                return {
                    "name": name,
                    "version": "latest",  # lib.rs doesn't easily expose version
                    "description": description,
                    "repository": repo_link or "",
                    "keywords": keywords,
                    "categories": [],
                    "readme": "",
                    "downloads": 0,
                    "github_stars": 0,
                    "dependencies": [],
                    "code_snippets": [],
                    "features": [],
                    "readme_sections": {},
                    "source": "lib.rs",
                }
        except Exception:
            pass

        # Finally, try GitHub search
        try:
            # This is a simplification - GitHub's search API requires
            # authentication
            gh_search_headers: dict[str, str] = {}
            if self.config.github_token:
                gh_search_headers["Authorization"] = f"token {self.config.github_token}"

            search_url = (
                f"https://api.github.com/search/repositories?"
                f"q={crate_name}+language:rust"
            )
            r = requests.get(search_url, headers=gh_search_headers)

            if r.ok:
                results = r.json().get("items", [])
                if results:
                    repo = results[0]  # Take first match

                    # Basic metadata from GitHub
                    return {
                        "name": crate_name,
                        "version": "unknown",
                        "description": repo.get("description", ""),
                        "repository": repo.get("html_url", ""),
                        "keywords": [],
                        "categories": [],
                        "readme": "",
                        "downloads": 0,
                        "github_stars": repo.get("stargazers_count", 0),
                        "dependencies": [],
                        "code_snippets": [],
                        "features": [],
                        "readme_sections": {},
                        "source": "github",
                    }
        except Exception:
            pass

        # If all sources fail
        return None
