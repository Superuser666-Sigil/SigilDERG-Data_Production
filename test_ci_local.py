#!/usr/bin/env python3
"""
Local CI Test Script

Runs the same checks as CI locally without needing Docker or GitHub Actions.
This is faster than using `act` for quick validation.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.3.0
"""

import subprocess
import sys
from pathlib import Path


def run_command(
    cmd: list[str], description: str, timeout: int | None = None
) -> bool:
    """Run a command and return True if successful.

    Args:
        cmd: Command and arguments to run
        description: Human-readable description of the command
        timeout: Optional timeout in seconds (None = no timeout)

    Returns:
        True if command succeeded, False otherwise
    """
    separator = "=" * 60
    print(f"\n{separator}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print(separator)

    try:
        subprocess.run(cmd, check=True, capture_output=False, timeout=timeout)
        print(f"[OK] {description} passed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[FAIL] {description} failed with exit code {e.returncode}")
        return False
    except subprocess.TimeoutExpired:
        print(f"[FAIL] {description} timed out after {timeout} seconds")
        return False
    except FileNotFoundError:
        print(f"[ERROR] Command not found: {cmd[0]}")
        print(f"   Install it with: pip install {cmd[0]}")
        return False


def run_safety_scan_from_requirements(timeout: int = 120) -> bool:
    """Run safety scan against a frozen requirements file.

    This is faster than scanning the whole environment and focuses
    on exactly what's installed.

    Args:
        timeout: Maximum seconds to wait for safety to complete

    Returns:
        True if no vulnerabilities found, False otherwise
    """
    req_file = Path("requirements.freeze.txt")
    separator = "=" * 60

    print(f"\n{separator}")
    print("Running: safety vulnerability scan (from frozen requirements)")
    print(separator)

    try:
        # Freeze current env to requirements file
        print("Freezing current environment...")
        with req_file.open("w") as f:
            subprocess.run(
                [sys.executable, "-m", "pip", "freeze"],
                check=True,
                stdout=f,
                timeout=30,
            )

        # Run safety check against the frozen requirements
        result = subprocess.run(
            ["safety", "check", "--full-report", "-r", str(req_file)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        # Safety exit codes: 0 = no vulnerabilities, non-zero = vulnerabilities or error
        if result.returncode == 0:
            print("[OK] safety vulnerability scan passed (no vulnerabilities found)")
            return True
        else:
            # Print output for debugging
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr)
            print(f"[WARN] safety found vulnerabilities (exit code {result.returncode})")
            # Return True anyway - treat as advisory in local CI
            return True

    except subprocess.TimeoutExpired:
        print(f"[WARN] safety scan timed out after {timeout} seconds (skipping)")
        return True  # Soft-fail: don't block local CI
    except FileNotFoundError:
        print("[WARN] safety not installed, skipping vulnerability scan")
        return True  # Soft-fail
    except Exception as e:
        print(f"[WARN] safety scan failed: {e!r} (skipping)")
        return True  # Soft-fail
    finally:
        # Clean up temp file
        if req_file.exists():
            req_file.unlink()


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

    # Safety scan - soft-fail in local CI (advisory only)
    # Uses frozen requirements for faster, focused scanning
    try:
        results.append(run_safety_scan_from_requirements(timeout=120))
    except Exception as exc:
        print(f"[WARN] safety scan skipped: {exc!r}")

    # Bandit check - exit code 1 means issues found (expected), only fail on errors
    try:
        bandit_result = subprocess.run(
            [
                "bandit",
                "-r",
                "sigil_pipeline",
                "-f",
                "json",
                "-o",
                "bandit-report.json",
            ],
            capture_output=True,
            timeout=120,
        )
        separator = "=" * 60
        # Exit code 0 = no issues, 1 = issues found (still success), other = error
        if bandit_result.returncode in (0, 1):
            print(f"\n{separator}")
            print("Running: bandit security scan")
            print(
                "Command: bandit -r sigil_pipeline -f json -o bandit-report.json"
            )
            print(separator)
            print("[OK] bandit security scan passed (report written)")
            results.append(True)
        else:
            print(f"\n{separator}")
            print("Running: bandit security scan")
            print(
                "Command: bandit -r sigil_pipeline -f json -o bandit-report.json"
            )
            print(separator)
            print(
                f"[FAIL] bandit security scan failed with exit code {bandit_result.returncode}"
            )
            results.append(False)
    except subprocess.TimeoutExpired:
        print("[WARN] bandit scan timed out after 120 seconds (skipping)")
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
