"""
Firejail sandbox runner for executing untrusted code safely.

Uses Firejail to isolate filesystem access and disable networking when
running cargo commands that compile or execute crate code.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from . import utils

logger = logging.getLogger(__name__)


@dataclass
class SandboxOptions:
    mode: str = "auto"  # auto, firejail, none
    network_enabled: bool = False
    private_home: bool = True
    keep_home_dirs: list[str] = field(default_factory=lambda: [".cargo", ".rustup"])
    extra_read_only: list[Path] = field(default_factory=list)
    extra_whitelist: list[Path] = field(default_factory=list)


def is_firejail_available() -> bool:
    return shutil.which("firejail") is not None


def resolve_mode(mode: str | None) -> str:
    if not mode:
        mode = "auto"
    mode = mode.strip().lower()
    if mode not in ("auto", "firejail", "none"):
        return "auto"
    if mode == "auto":
        return "firejail" if is_firejail_available() else "none"
    if mode == "firejail" and not is_firejail_available():
        raise RuntimeError("firejail not available but sandbox_mode=firejail")
    return mode


def _format_paths(paths: Iterable[Path]) -> list[str]:
    items: list[str] = []
    for path in paths:
        if not path:
            continue
        items.append(str(path))
    return items


def build_firejail_command(
    cmd: list[str],
    *,
    cwd: Path | None,
    options: SandboxOptions,
) -> list[str]:
    args = ["firejail", "--quiet"]
    if not options.network_enabled:
        args.extend(["--net=none", "--netlock"])
    args.extend(["--private-tmp", "--private-dev", "--caps.drop=all", "--seccomp"])

    if options.private_home:
        home = Path.home()
        keep_dirs = [
            entry for entry in options.keep_home_dirs if (home / entry).exists()
        ]
        if keep_dirs:
            keep = ",".join(keep_dirs)
            args.append(f"--private-home={keep}")
        else:
            logger.debug("No home directories to keep; skipping --private-home")

    if cwd:
        args.append(f"--private-cwd={cwd}")

    for path in _format_paths(options.extra_whitelist):
        args.append(f"--whitelist={path}")
    for path in _format_paths(options.extra_read_only):
        args.append(f"--read-only={path}")

    return args + cmd


async def run_sandboxed_command_async(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    timeout: int | None = None,
    env: dict[str, str] | None = None,
    options: SandboxOptions | None = None,
) -> subprocess.CompletedProcess:
    opts = options or SandboxOptions()
    mode = resolve_mode(opts.mode)
    if mode == "none":
        return await utils.run_command_async(cmd, cwd=cwd, timeout=timeout, env=env)

    firejail_cmd = build_firejail_command(cmd, cwd=cwd, options=opts)
    return await utils.run_command_async(
        firejail_cmd, cwd=cwd, timeout=timeout, env=env
    )


__all__ = [
    "SandboxOptions",
    "is_firejail_available",
    "resolve_mode",
    "build_firejail_command",
    "run_sandboxed_command_async",
]
