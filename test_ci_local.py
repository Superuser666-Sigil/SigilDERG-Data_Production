#!/usr/bin/env python3
"""
Local CI Test Script

Runs the same checks as CI locally without needing Docker or GitHub Actions.
This is faster than using `act` for quick validation.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.2.0
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], description: str) -> bool:
    """Run a command and return True if successful."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print("=" * 60)

    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print(f"[OK] {description} passed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[FAIL] {description} failed with exit code {e.returncode}")
        return False
    except FileNotFoundError:
        print(f"[ERROR] Command not found: {cmd[0]}")
        print(f"   Install it with: pip install {cmd[0]}")
        return False


def main():
    """Run all CI checks locally."""
    print("Running local CI checks...")
    print("This simulates the GitHub Actions CI workflow locally.\n")

    # Check if we're in the right directory
    if not Path("pyproject.toml").exists():
        print("[ERROR] pyproject.toml not found. Run this from the project root.")
        sys.exit(1)

    results = []

    # Lint checks
    print("\n" + "=" * 60)
    print("LINT CHECKS")
    print("=" * 60)

    results.append(
        run_command(
            ["black", "--check", "sigil_pipeline", "tests"],
            "Black formatting check",
        )
    )

    results.append(
        run_command(
            ["isort", "--check-only", "sigil_pipeline", "tests"],
            "isort import sorting check",
        )
    )

    results.append(run_command(["flake8", "sigil_pipeline", "tests"], "flake8 linting"))

    results.append(run_command(["pyright", "sigil_pipeline"], "pyright type checking"))

    # Test checks
    print("\n" + "=" * 60)
    print("TEST CHECKS")
    print("=" * 60)

    results.append(
        run_command(
            ["pytest", "tests/", "-v", "--cov=sigil_pipeline", "--cov-report=xml"],
            "pytest with coverage",
        )
    )

    # Security checks
    print("\n" + "=" * 60)
    print("SECURITY CHECKS")
    print("=" * 60)

    # Safety check (may fail, that's okay)
    try:
        results.append(
            run_command(["safety", "check", "--json"], "safety vulnerability check")
        )
    except Exception:
        print("[WARN] safety check skipped (may not be installed)")

    # Bandit check
    try:
        results.append(
            run_command(
                [
                    "bandit",
                    "-r",
                    "sigil_pipeline",
                    "-f",
                    "json",
                    "-o",
                    "bandit-report.json",
                ],
                "bandit security scan",
            )
        )
    except Exception:
        print("[WARN] bandit check skipped (may not be installed)")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = sum(results)
    total = len(results)

    print(f"\nPassed: {passed}/{total} checks")

    if passed == total:
        print("[OK] All checks passed! CI should pass.")
        return 0
    else:
        print(f"[FAIL] {total - passed} check(s) failed. Fix issues before pushing.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
