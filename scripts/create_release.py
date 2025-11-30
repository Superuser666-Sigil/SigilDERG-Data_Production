#!/usr/bin/env python3
"""
Release automation script for sigil-pipeline.

This script automates the release process including version updates,
changelog generation, git commits, and tag creation.

Usage:
    python scripts/create_release.py 1.3.0
    python scripts/create_release.py 1.3.0 --dry-run

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.4.0
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run_command(
    cmd: list[str] | str,
    check: bool = True,
    capture_output: bool = True,
    dry_run: bool = False,
) -> subprocess.CompletedProcess[str] | None:
    """Run a shell command and return the result."""
    if dry_run:
        cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
        print(f"  [DRY-RUN] Would run: {cmd_str}")
        return None

    try:
        shell = isinstance(cmd, str)
        result = subprocess.run(
            cmd,
            shell=shell,
            check=check,
            capture_output=capture_output,
            text=True,
            cwd=PROJECT_ROOT,
        )
        return result
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {cmd}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        if check:
            sys.exit(1)
        raise


def get_current_version() -> str:
    """Get the current version from pyproject.toml."""
    pyproject_path = PROJECT_ROOT / "pyproject.toml"
    content = pyproject_path.read_text(encoding="utf-8")

    match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
    if match:
        return match.group(1)

    raise ValueError("Could not find version in pyproject.toml")


def validate_version(version: str) -> bool:
    """Validate version string format (semver)."""
    pattern = r"^\d+\.\d+\.\d+(?:-[a-zA-Z0-9]+(?:\.[a-zA-Z0-9]+)*)?$"
    return bool(re.match(pattern, version))


def update_version_in_pyproject(new_version: str, dry_run: bool = False) -> None:
    """Update version in pyproject.toml."""
    pyproject_path = PROJECT_ROOT / "pyproject.toml"
    content = pyproject_path.read_text(encoding="utf-8")

    updated_content = re.sub(
        r'^(version\s*=\s*["\'])[^"\']+(["\'])',
        rf"\g<1>{new_version}\g<2>",
        content,
        flags=re.MULTILINE,
    )

    if dry_run:
        print(f"  [DRY-RUN] Would update version in {pyproject_path}")
        return

    pyproject_path.write_text(updated_content, encoding="utf-8")
    print("  ✓ Updated version in pyproject.toml")


def update_version_in_init(new_version: str, dry_run: bool = False) -> None:
    """Update __version__ in sigil_pipeline/__init__.py if present."""
    init_path = PROJECT_ROOT / "sigil_pipeline" / "__init__.py"
    if not init_path.exists():
        return

    content = init_path.read_text(encoding="utf-8")
    if "__version__" not in content:
        return

    updated_content = re.sub(
        r'^(__version__\s*=\s*["\'])[^"\']+(["\'])',
        rf"\g<1>{new_version}\g<2>",
        content,
        flags=re.MULTILINE,
    )

    if dry_run:
        print(f"  [DRY-RUN] Would update version in {init_path}")
        return

    init_path.write_text(updated_content, encoding="utf-8")
    print("  ✓ Updated version in sigil_pipeline/__init__.py")


def check_git_status(dry_run: bool = False) -> bool:
    """Check if git working directory is clean."""
    result = run_command(["git", "status", "--porcelain"], dry_run=False)
    if result and result.stdout.strip():
        print("⚠️  Git working directory has uncommitted changes:")
        print(result.stdout)
        return False
    return True


def check_on_main_branch(dry_run: bool = False) -> bool:
    """Check if we're on the main branch."""
    result = run_command(["git", "branch", "--show-current"], dry_run=False)
    if result:
        branch = result.stdout.strip()
        if branch != "main":
            print(f"⚠️  Not on main branch (current: {branch})")
            return False
    return True


def run_tests(dry_run: bool = False) -> bool:
    """Run the test suite before release."""
    print("  Running tests...")
    if dry_run:
        print("  [DRY-RUN] Would run: pytest tests/ --ignore=tests/load -q")
        return True

    result = run_command(
        ["pytest", "tests/", "--ignore=tests/load", "-q"],
        check=False,
        capture_output=True,
    )
    if result and result.returncode != 0:
        print(f"  ❌ Tests failed:\n{result.stdout}\n{result.stderr}")
        return False
    print("  ✓ All tests passed")
    return True


def run_linters(dry_run: bool = False) -> bool:
    """Run linters before release."""
    print("  Running linters...")
    if dry_run:
        print("  [DRY-RUN] Would run: black, isort, flake8, pyright")
        return True

    # Check formatting
    result = run_command(
        ["black", "--check", "sigil_pipeline", "tests"],
        check=False,
        capture_output=True,
    )
    if result and result.returncode != 0:
        print("  ❌ black formatting check failed")
        return False

    result = run_command(
        ["isort", "--check-only", "sigil_pipeline", "tests"],
        check=False,
        capture_output=True,
    )
    if result and result.returncode != 0:
        print("  ❌ isort check failed")
        return False

    result = run_command(
        [
            "flake8",
            "sigil_pipeline",
            "tests",
            "--exclude=vcpkg,.venv",
            "--max-line-length=120",
            "--extend-ignore=E501,E203,W503",
        ],
        check=False,
        capture_output=True,
    )
    if result and result.returncode != 0:
        print(f"  ❌ flake8 check failed:\n{result.stdout}")
        return False

    print("  ✓ All linters passed")
    return True


def build_package(dry_run: bool = False) -> bool:
    """Build the Python package."""
    print("  Building package...")
    run_command(["python", "-m", "build"], dry_run=dry_run)
    if not dry_run:
        print("  ✓ Package built successfully")

    # Verify with twine
    run_command(["twine", "check", "dist/*"], dry_run=dry_run)
    if not dry_run:
        print("  ✓ Package passed twine check")
    return True


def create_git_commit_and_tag(version: str, dry_run: bool = False) -> None:
    """Create git commit and tag for the release."""
    print("  Creating git commit and tag...")

    run_command(
        ["git", "add", "pyproject.toml", "sigil_pipeline/__init__.py"], dry_run=dry_run
    )
    run_command(
        ["git", "commit", "-m", f"Release v{version}"],
        dry_run=dry_run,
    )
    run_command(
        ["git", "tag", "-a", f"v{version}", "-m", f"Release v{version}"],
        dry_run=dry_run,
    )

    if not dry_run:
        print(f"  ✓ Created commit and tag v{version}")


def push_to_remote(version: str, dry_run: bool = False) -> None:
    """Push commits and tags to remote."""
    print("  Pushing to remote...")
    run_command(["git", "push", "origin", "main"], dry_run=dry_run)
    run_command(["git", "push", "origin", f"v{version}"], dry_run=dry_run)

    if not dry_run:
        print("  ✓ Pushed to remote")


def main() -> int:
    """Main release process."""
    parser = argparse.ArgumentParser(
        description="Create a new release for sigil-pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/create_release.py 1.3.0
    python scripts/create_release.py 1.3.0 --dry-run
    python scripts/create_release.py 1.3.0 --skip-tests
        """,
    )
    parser.add_argument("version", help="New version number (e.g., 1.3.0)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip running tests (not recommended)",
    )
    parser.add_argument(
        "--skip-push",
        action="store_true",
        help="Create commit and tag but don't push to remote",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt",
    )

    args = parser.parse_args()

    print("═" * 60)
    print("  sigil-pipeline Release Script")
    print("═" * 60)

    # Validate version format
    if not validate_version(args.version):
        print(f"❌ Invalid version format: {args.version}")
        print("   Expected format: MAJOR.MINOR.PATCH (e.g., 1.3.0)")
        return 1

    # Get current version
    try:
        current_version = get_current_version()
    except ValueError as e:
        print(f"❌ {e}")
        return 1

    print(f"\n📦 Current version: {current_version}")
    print(f"📦 New version:     {args.version}")

    if args.dry_run:
        print("\n🔍 DRY RUN MODE - No changes will be made\n")

    # Pre-flight checks
    print("\n🔍 Pre-flight checks...")

    if not check_on_main_branch(args.dry_run):
        if not args.force:
            return 1
        print("   Continuing anyway (--force)")

    if not check_git_status(args.dry_run):
        if not args.force:
            print("   Commit or stash changes before releasing")
            return 1
        print("   Continuing anyway (--force)")

    # Confirmation
    if not args.force and not args.dry_run:
        response = input(f"\n⚠️  Proceed with release v{args.version}? [y/N]: ")
        if response.lower() != "y":
            print("Release cancelled")
            return 0

    # Run tests
    if not args.skip_tests:
        print("\n🧪 Running quality checks...")
        if not run_tests(args.dry_run):
            return 1
        if not run_linters(args.dry_run):
            return 1
    else:
        print("\n⚠️  Skipping tests (--skip-tests)")

    # Update version
    print("\n📝 Updating version...")
    update_version_in_pyproject(args.version, args.dry_run)
    update_version_in_init(args.version, args.dry_run)

    # Build package
    print("\n📦 Building package...")
    if not build_package(args.dry_run):
        return 1

    # Git operations
    print("\n🔖 Git operations...")
    create_git_commit_and_tag(args.version, args.dry_run)

    if not args.skip_push:
        push_to_remote(args.version, args.dry_run)
    else:
        print("  ⚠️  Skipping push (--skip-push)")

    # Success
    print("\n" + "═" * 60)
    if args.dry_run:
        print("✅ DRY RUN COMPLETE - No changes were made")
    else:
        print(f"✅ Release v{args.version} created successfully!")
        print("\n📋 Next steps:")
        print("   1. Check GitHub Actions for build status")
        print("   2. Verify the release on GitHub Releases page")
        if args.skip_push:
            print(
                f"   3. Push when ready: git push origin main && git push origin v{args.version}"
            )
    print("═" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
