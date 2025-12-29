"""
GitHub bug-fix miner for producing high-quality error-fixing samples.

Mines merged bug/fix PRs for accepted crates, validates base/head commits
via cargo test/check, and emits function-level bug-fix examples.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import shutil
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator

from . import output_validator, sandbox, utils

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"
_REPO_LOCKS: dict[str, asyncio.Lock] = {}
_COMMIT_CHECK_CACHE: dict[tuple[str, str, bool], bool] = {}


@dataclass
class CrateInfo:
    name: str
    crate_dir: Path


def _repo_lock(repo_path: Path) -> asyncio.Lock:
    key = str(repo_path)
    lock = _REPO_LOCKS.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _REPO_LOCKS[key] = lock
    return lock


def _github_headers(token: str | None) -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _http_get_json(url: str, token: str | None, timeout: int) -> Any:
    request = urllib.request.Request(url, headers=_github_headers(token))
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


async def _github_get_json(url: str, token: str | None, timeout: int) -> Any:
    return await asyncio.to_thread(_http_get_json, url, token, timeout)


def _parse_github_repo_url(url: str) -> tuple[str, str] | None:
    if not url:
        return None
    url = url.strip()
    if url.startswith("git@github.com:"):
        url = url.replace("git@github.com:", "https://github.com/")
    if not url.startswith("http"):
        return None
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc.lower() != "github.com":
        return None
    parts = parsed.path.strip("/").split("/")
    if len(parts) < 2:
        return None
    owner, repo = parts[0], parts[1].removesuffix(".git")
    return owner, repo


def _load_repository_url(crate_dir: Path) -> str | None:
    cargo_toml = crate_dir / "Cargo.toml"
    if not cargo_toml.exists():
        return None
    try:
        import tomllib
    except ModuleNotFoundError:
        return None
    try:
        data = tomllib.loads(cargo_toml.read_text(encoding="utf-8"))
    except Exception:
        return None
    package = data.get("package") if isinstance(data, dict) else None
    if not isinstance(package, dict):
        return None
    repo = package.get("repository")
    if isinstance(repo, str):
        return repo
    return None


def _extract_functions(code: str) -> dict[str, str]:
    if not code:
        return {}
    functions: dict[str, str | None] = {}
    code_bytes = code.encode("utf-8")
    try:
        import tree_sitter_rust as ts_rust
        from tree_sitter import Language, Parser

        rust_language = Language(ts_rust.language())
        try:
            parser = Parser(rust_language)
        except TypeError:
            parser = Parser()
            parser.set_language(rust_language)
        tree = parser.parse(code.encode("utf-8"))
        root = tree.root_node
        if getattr(root, "has_error", False):
            return {}

        stack = [root]
        while stack:
            node = stack.pop()
            if node.type == "function_item":
                name_node = node.child_by_field_name("name")
                if name_node is None:
                    continue
                name_bytes = code_bytes[name_node.start_byte : name_node.end_byte]
                try:
                    name = name_bytes.decode("utf-8").strip()
                except UnicodeDecodeError:
                    name = name_bytes.decode("utf-8", errors="ignore").strip()
                if not name:
                    continue
                fn_bytes = code_bytes[node.start_byte : node.end_byte]
                try:
                    fn_code = fn_bytes.decode("utf-8").strip()
                except UnicodeDecodeError:
                    fn_code = fn_bytes.decode("utf-8", errors="ignore").strip()
                if name in functions:
                    functions[name] = None
                else:
                    functions[name] = fn_code
                continue
            children = getattr(node, "children", [])
            if children:
                stack.extend(reversed(children))
    except Exception:
        return {}

    return {k: v for k, v in functions.items() if v}


def _tests_exist(repo_path: Path) -> bool:
    if (repo_path / "tests").exists():
        return True
    src_dir = repo_path / "src"
    if not src_dir.exists():
        return False
    for path in src_dir.rglob("*.rs"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if "#[test]" in text or "#[cfg(test)]" in text:
            return True
    return False


async def _prefetch_dependencies(
    repo_path: Path,
    *,
    timeout: int,
    cargo_env: dict[str, str] | None,
    sandbox_mode: str,
) -> None:
    cmd = utils.build_cargo_command("fetch")
    options = sandbox.SandboxOptions(
        mode=sandbox_mode,
        network_enabled=True,
        extra_whitelist=[repo_path],
    )
    if cargo_env:
        target_dir = cargo_env.get("CARGO_TARGET_DIR")
        if target_dir:
            options.extra_whitelist.append(Path(target_dir))
    try:
        await sandbox.run_sandboxed_command_async(
            cmd,
            cwd=repo_path,
            timeout=timeout,
            env=cargo_env,
            options=options,
        )
    except Exception:
        pass


async def _run_cargo(
    repo_path: Path,
    cmd: list[str],
    timeout: int,
    cargo_env: dict[str, str] | None,
    sandbox_mode: str,
) -> bool:
    try:
        options = sandbox.SandboxOptions(
            mode=sandbox_mode,
            network_enabled=False,
            extra_whitelist=[repo_path],
        )
        if cargo_env:
            target_dir = cargo_env.get("CARGO_TARGET_DIR")
            if target_dir:
                options.extra_whitelist.append(Path(target_dir))
        result = await sandbox.run_sandboxed_command_async(
            cmd,
            cwd=repo_path,
            timeout=timeout,
            env=cargo_env,
            options=options,
        )
        return result.returncode == 0
    except Exception:
        return False


async def _validate_commit(
    repo_path: Path,
    sha: str,
    *,
    require_tests: bool,
    timeout: int,
    cargo_env: dict[str, str] | None,
    sandbox_mode: str,
) -> tuple[bool, bool]:
    """Return (tests_exist, success) for a commit checkout."""
    cache_key = (str(repo_path), sha, require_tests)
    cached = _COMMIT_CHECK_CACHE.get(cache_key)
    if cached is not None:
        return require_tests, cached

    lock = _repo_lock(repo_path)
    async with lock:
        if not await _git_has_commit(repo_path, sha, timeout):
            fetched = await _fetch_commit(repo_path, sha, timeout)
            if not fetched:
                _COMMIT_CHECK_CACHE[cache_key] = False
                return require_tests, False
        try:
            await utils.run_command_async(
                ["git", "checkout", "--quiet", sha], cwd=repo_path, timeout=timeout
            )
        except Exception:
            _COMMIT_CHECK_CACHE[cache_key] = False
            return require_tests, False

        await _prefetch_dependencies(
            repo_path, timeout=timeout, cargo_env=cargo_env, sandbox_mode=sandbox_mode
        )

        has_tests = _tests_exist(repo_path)
        success = True
        if has_tests and require_tests:
            success = await _run_cargo(
                repo_path,
                utils.build_cargo_command("test", "--quiet"),
                timeout,
                cargo_env,
                sandbox_mode,
            )
        if success:
            success = await _run_cargo(
                repo_path,
                utils.build_cargo_command("check", "--quiet"),
                timeout,
                cargo_env,
                sandbox_mode,
            )

        _COMMIT_CHECK_CACHE[cache_key] = success
        return has_tests, success


async def _ensure_repo_clone(repo_url: str, dest: Path, timeout: int) -> bool:
    if dest.exists():
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        await utils.run_command_async(
            ["git", "clone", "--quiet", "--depth", "1", "--no-tags", repo_url, str(dest)],
            cwd=dest.parent,
            timeout=timeout,
        )
        return True
    except Exception:
        return False


async def _git_has_commit(repo_path: Path, sha: str, timeout: int) -> bool:
    try:
        result = await utils.run_command_async(
            ["git", "rev-parse", "--verify", f"{sha}^{{commit}}"],
            cwd=repo_path,
            timeout=timeout,
        )
        return result.returncode == 0
    except Exception:
        return False


async def _fetch_commit(repo_path: Path, sha: str, timeout: int) -> bool:
    try:
        result = await utils.run_command_async(
            ["git", "fetch", "--quiet", "--no-tags", "--depth", "1", "origin", sha],
            cwd=repo_path,
            timeout=timeout,
        )
        if result.returncode == 0:
            return True
    except Exception:
        pass
    try:
        result = await utils.run_command_async(
            ["git", "fetch", "--quiet", "--no-tags", "origin", sha],
            cwd=repo_path,
            timeout=timeout,
        )
        return result.returncode == 0
    except Exception:
        return False


async def _fetch_prs(
    owner: str,
    repo: str,
    labels: list[str],
    max_prs: int,
    token: str | None,
    timeout: int,
) -> list[int]:
    pr_numbers: list[int] = []
    seen: set[int] = set()
    for label in labels:
        params = urllib.parse.urlencode(
            {"state": "closed", "labels": label, "per_page": 50}
        )
        url = f"{_GITHUB_API}/repos/{owner}/{repo}/issues?{params}"
        try:
            data = await _github_get_json(url, token, timeout)
        except Exception:
            continue
        if not isinstance(data, list):
            continue
        for item in data:
            if not isinstance(item, dict):
                continue
            if "pull_request" not in item:
                continue
            number = item.get("number")
            if not isinstance(number, int):
                continue
            if number in seen:
                continue
            seen.add(number)
            pr_numbers.append(number)
            if len(pr_numbers) >= max_prs:
                return pr_numbers
    return pr_numbers


async def _fetch_pr_details(
    owner: str,
    repo: str,
    number: int,
    token: str | None,
    timeout: int,
) -> dict[str, Any] | None:
    url = f"{_GITHUB_API}/repos/{owner}/{repo}/pulls/{number}"
    try:
        data = await _github_get_json(url, token, timeout)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    if not data.get("merged_at"):
        return None
    return data


async def _fetch_pr_files(
    owner: str,
    repo: str,
    number: int,
    token: str | None,
    timeout: int,
) -> list[str]:
    url = f"{_GITHUB_API}/repos/{owner}/{repo}/pulls/{number}/files?per_page=100"
    try:
        data = await _github_get_json(url, token, timeout)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    paths: list[str] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        filename = item.get("filename")
        if isinstance(filename, str) and filename.endswith(".rs"):
            paths.append(filename)
    return paths


async def _fetch_file_content(
    owner: str,
    repo: str,
    path: str,
    ref: str,
    token: str | None,
    timeout: int,
) -> str | None:
    url = f"{_GITHUB_API}/repos/{owner}/{repo}/contents/{path}?ref={ref}"
    try:
        data = await _github_get_json(url, token, timeout)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    content = data.get("content")
    if not isinstance(content, str):
        return None
    try:
        decoded = base64.b64decode(content).decode("utf-8", errors="ignore")
        return decoded
    except Exception:
        return None


def _within_limits(code: str, max_lines: int, max_chars: int) -> bool:
    if not code:
        return False
    if code.count("\n") > max_lines:
        return False
    if len(code) > max_chars:
        return False
    return True


async def iter_bugfix_samples_async(
    crate_infos: list[CrateInfo],
    *,
    allowed_labels: list[str],
    max_prs_per_crate: int,
    max_samples_per_pr: int,
    timeout: int,
    require_tests: bool,
    max_lines: int,
    max_chars: int,
    cargo_env: dict[str, str] | None = None,
    sandbox_mode: str = "auto",
) -> AsyncIterator[dict[str, Any]]:
    token = os.getenv("GITHUB_PAT")
    if not token:
        logger.warning("GITHUB_PAT not set; skipping GitHub mining.")
        return

    if not shutil.which("git"):
        logger.warning("git not available; skipping GitHub mining.")
        return

    for info in crate_infos:
        repo_url = _load_repository_url(info.crate_dir)
        if not repo_url:
            continue
        repo_spec = _parse_github_repo_url(repo_url)
        if not repo_spec:
            continue
        owner, repo = repo_spec

        repo_clone = info.crate_dir.parent / f"sigil_repo_{owner}_{repo}"
        if not await _ensure_repo_clone(
            f"https://github.com/{owner}/{repo}.git", repo_clone, timeout
        ):
            continue

        pr_numbers = await _fetch_prs(
            owner, repo, allowed_labels, max_prs_per_crate, token, timeout
        )
        for pr_number in pr_numbers:
            pr_details = await _fetch_pr_details(
                owner, repo, pr_number, token, timeout
            )
            if not pr_details:
                continue
            base_sha = pr_details.get("base", {}).get("sha")
            head_sha = pr_details.get("merge_commit_sha") or pr_details.get(
                "head", {}
            ).get("sha")
            if not base_sha or not head_sha:
                continue

            # Validate base/head commits with cargo test/check
            tests_exist, base_ok = await _validate_commit(
                repo_clone,
                base_sha,
                require_tests=require_tests,
                timeout=timeout,
                cargo_env=cargo_env,
                sandbox_mode=sandbox_mode,
            )
            if base_ok:
                # Base should fail for a bug-fix PR
                continue
            _tests_exist, head_ok = await _validate_commit(
                repo_clone,
                head_sha,
                require_tests=require_tests,
                timeout=timeout,
                cargo_env=cargo_env,
                sandbox_mode=sandbox_mode,
            )
            if not head_ok:
                continue

            paths = await _fetch_pr_files(owner, repo, pr_number, token, timeout)
            samples_emitted = 0
            for path in paths:
                base_content = await _fetch_file_content(
                    owner, repo, path, base_sha, token, timeout
                )
                head_content = await _fetch_file_content(
                    owner, repo, path, head_sha, token, timeout
                )
                if not base_content or not head_content:
                    continue

                base_funcs = _extract_functions(base_content)
                head_funcs = _extract_functions(head_content)
                common = set(base_funcs.keys()) & set(head_funcs.keys())
                for name in common:
                    broken = base_funcs[name]
                    fixed = head_funcs[name]
                    if broken == fixed:
                        continue
                    if not _within_limits(broken, max_lines, max_chars):
                        continue
                    if not _within_limits(fixed, max_lines, max_chars):
                        continue
                    if not output_validator.has_single_top_level_item(
                        broken, expected="function"
                    ):
                        continue
                    if not output_validator.has_single_top_level_item(
                        fixed, expected="function"
                    ):
                        continue

                    prompt = (
                        "The following Rust code contains a bug or will not compile. "
                        "Identify and fix the problem. Return only the corrected Rust code.\n\n"
                        + broken
                    )
                    yield {
                        "prompt": prompt,
                        "gen": fixed,
                        "_task_type": "error_fixing",
                        "_source_crate": info.name,
                        "_github_repo": f"{owner}/{repo}",
                        "_github_pr": pr_number,
                        "_github_base": base_sha,
                        "_github_head": head_sha,
                        "_tests_required": tests_exist,
                    }
                    samples_emitted += 1
                    if samples_emitted >= max_samples_per_pr:
                        break
                if samples_emitted >= max_samples_per_pr:
                    break


__all__ = ["CrateInfo", "iter_bugfix_samples_async"]
