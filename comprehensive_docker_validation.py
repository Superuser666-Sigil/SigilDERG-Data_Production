#!/usr/bin/env python3
"""
Comprehensive Docker Build Validation Script

This script performs a complete validation of the Docker build process,
ensuring that the container can run our specific functionality.

This aligns with Rule Zero principles of thorough validation and transparency.
"""

import subprocess
import sys
from pathlib import Path
from typing import List, Union, Dict, Any

try:
    from rust_crate_pipeline import __version__ as PACKAGE_VERSION
except ImportError:
    PACKAGE_VERSION = "latest"


def run_command(
    cmd: Union[str, List[str]], description: str, check_return: bool = True
) -> str:
    """Run a command and handle output with Rule Zero transparency"""
    print(f"🔍 {description}")
    print(f"   Command: {' '.join(cmd) if isinstance(cmd, list) else cmd}")

    try:
        if isinstance(cmd, str):
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                check=check_return,
            )
        else:
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=check_return
            )

        print("   ✅ Success")
        if result.stdout.strip():
            print(f"   Output: {result.stdout.strip()[:200]}...")
        return result.stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"   ❌ Failed: {e}")
        if check_return:
            raise
        return ""


def validate_local_setup() -> bool:
    """Validate local package setup before Docker build"""
    print("\n" + "=" * 70)
    print("📦 LOCAL PACKAGE VALIDATION")
    print("=" * 70)

    # Check package version
    try:
        import rust_crate_pipeline

        version = rust_crate_pipeline.__version__
        print(f"✅ Local package version: {version}")
    except ImportError as e:
        print(f"❌ Failed to import local package: {e}")
        return False

    # Check critical modules
    modules_to_check = [
        "rust_crate_pipeline.config",
        "rust_crate_pipeline.pipeline",
        "rust_crate_pipeline.ai_processing",
    ]

    for module in modules_to_check:
        try:
            __import__(module)
            print(f"✅ Module {module} imports successfully")
        except ImportError as e:
            print(f"❌ Failed to import {module}: {e}")
            return False

    # Check integration files
    integration_files = [
        "crawl4ai_direct_llm_integration.py",
        "enhanced_scraping.py",
    ]

    for file in integration_files:
        if Path(file).exists():
            print(f"✅ Integration file {file} exists")
        else:
            print(f"❌ Integration file {file} missing")
            return False

    return True


def build_docker_image() -> bool:
    """Build the Docker image"""
    print("\n" + "=" * 70)
    print("🐳 DOCKER BUILD")
    print("=" * 70)

    # Check if Docker is running
    try:
        run_command(["docker", "version"], "Checking Docker availability")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"❌ Docker is not running or not found: {e}")
        print("Please start Docker Desktop.")
        return False

    # Build the image
    try:
        image_tag = f"rust-crate-pipeline:{PACKAGE_VERSION}"
        run_command(
            ["docker", "build", "-t", image_tag, "."],
            f"Building Docker image with version tag {PACKAGE_VERSION}",
        )

        # Also tag as latest
        run_command(
            [
                "docker",
                "tag",
                image_tag,
                "rust-crate-pipeline:latest",
            ],
            "Tagging as latest",
        )

        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"❌ Docker build failed: {e}")
        return False


def test_docker_container() -> bool:
    """Test the Docker container functionality"""
    print("\n" + "=" * 70)
    print("🧪 DOCKER CONTAINER TESTING")
    print("=" * 70)

    tests: List[Dict[str, Any]] = [
        {
            "name": "Container health test",
            "cmd": [
                "docker",
                "run",
                "--rm",
                "rust-crate-pipeline:latest",
                "python",
                "-m",
                "rust_crate_pipeline",
                "--help",
            ],
            "description": "Ensuring CLI help executes inside container",
        },
        {
            "name": "Package version check",
            "cmd": [
                "docker",
                "run",
                "--rm",
                "rust-crate-pipeline:latest",
                "python",
                "-c",
                (
                    "import rust_crate_pipeline; "
                    "print(f'Container version: {rust_crate_pipeline.__version__}')"
                ),
            ],
            "description": "Verifying package version in container",
        },
        {
            "name": "Crawl4AI availability",
            "cmd": [
                "docker",
                "run",
                "--rm",
                "rust-crate-pipeline:latest",
                "python",
                "-c",
                "import crawl4ai; print('Crawl4AI available')",
            ],
            "description": "Testing Crawl4AI import",
        },
        {
            "name": "Integration module test",
            "cmd": [
                "docker",
                "run",
                "--rm",
                "rust-crate-pipeline:latest",
                "python",
                "-c",
                (
                    "import sys; sys.path.append('.'); "
                    "import enhanced_scraping; "
                    "print('Enhanced scraping module available')"
                ),
            ],
            "description": "Testing our integration module",
        },
    ]

    all_passed = True
    for test in tests:
        try:
            run_command(test["cmd"], test["description"])
            print(f"✅ {test['name']} passed")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"❌ {test['name']} failed: {e}")
            all_passed = False

    return all_passed


def validate_image_contents() -> bool:
    """Validate that required Python modules are available inside the image"""
    print("\n" + "=" * 70)
    print("📋 IMAGE CONTENTS VALIDATION")
    print("=" * 70)

    modules_to_check = [
        "rust_crate_pipeline",
        "enhanced_scraping",
        "crawl4ai",
    ]

    all_passed = True
    for module in modules_to_check:
        try:
            run_command(
                [
                    "docker",
                    "run",
                    "--rm",
                    "rust-crate-pipeline:latest",
                    "python",
                    "-c",
                    f"import {module}; print('{module} import ✅')",
                ],
                f"Checking import of {module} inside container",
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"❌ Failed to import {module}: {e}")
            all_passed = False

    return all_passed


def cleanup_test_containers() -> None:
    """Clean up any test containers"""
    print("\n" + "=" * 70)
    print("🧹 CLEANUP")
    print("=" * 70)

    try:
        run_command(
            ["docker", "system", "prune", "-f"],
            "Cleaning up unused Docker resources",
            check_return=False,
        )
        print("✅ Cleanup completed")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  Cleanup skipped (optional)")


def main() -> None:
    """Main validation logic"""
    print("=" * 70)
    print("🚀 STARTING COMPREHENSIVE DOCKER VALIDATION 🚀")
    print("=" * 70)

    if not validate_local_setup():
        print("\n❌ Local setup validation failed. Aborting.")
        sys.exit(1)

    if not build_docker_image():
        print("\n❌ Docker build failed. Aborting.")
        sys.exit(1)

    if not test_docker_container():
        print("\n❌ Docker container tests failed.")
        # Do not exit here, try to validate contents anyway
    else:
        print("\n✅ All Docker container tests passed.")

    if not validate_image_contents():
        print("\n❌ Image content validation failed.")
    else:
        print("\n✅ Image content validation passed.")

    cleanup_test_containers()

    print("\n" + "=" * 70)
    print("🎉 VALIDATION COMPLETE 🎉")
    print("=" * 70)


if __name__ == "__main__":
    main()
