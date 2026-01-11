"""
GPU Setup and Driver Management for Sigil Pipeline.

Provides automated detection, validation, and installation of NVIDIA
GPU drivers and CUDA dependencies for multi-GPU inference.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.6.1
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Minimum driver versions for CUDA support
MIN_DRIVER_VERSION = 535  # For CUDA 12.x
RECOMMENDED_DRIVER_VERSION = 550


@dataclass
class GPUInfo:
    """Information about a detected GPU."""

    index: int
    name: str
    uuid: str
    memory_total_mb: int
    driver_version: str
    cuda_version: str


@dataclass
class DriverStatus:
    """Status of NVIDIA driver installation."""

    installed: bool
    version: Optional[str]
    cuda_version: Optional[str]
    needs_update: bool
    update_available: Optional[str]
    gpus: list[GPUInfo]


def run_command(
    cmd: list[str],
    timeout: int = 30,
    capture: bool = True,
    check: bool = False,
) -> subprocess.CompletedProcess:
    """Run a command with timeout."""
    try:
        return subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            timeout=timeout,
            check=check,
        )
    except subprocess.TimeoutExpired:
        logger.warning(f"Command timed out: {' '.join(cmd)}")
        return subprocess.CompletedProcess(
            cmd, returncode=-1, stdout="", stderr="timeout"
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(
            cmd, returncode=-1, stdout="", stderr="not found"
        )
    except subprocess.CalledProcessError as e:
        return subprocess.CompletedProcess(
            cmd, returncode=e.returncode, stdout="", stderr=str(e)
        )


def check_nvidia_smi() -> bool:
    """Check if nvidia-smi is available."""
    return shutil.which("nvidia-smi") is not None


def get_driver_version() -> Optional[str]:
    """Get installed NVIDIA driver version."""
    result = run_command(
        ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"]
    )
    if result.returncode == 0 and result.stdout.strip():
        # Return first line (all GPUs should have same driver)
        return result.stdout.strip().split("\n")[0].strip()
    return None


def get_cuda_version() -> Optional[str]:
    """Get CUDA version from nvidia-smi."""
    result = run_command(
        ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"]
    )
    if result.returncode != 0:
        return None

    # Parse CUDA version from nvidia-smi output header
    result = run_command(["nvidia-smi"])
    if result.returncode == 0:
        match = re.search(r"CUDA Version:\s*(\d+\.\d+)", result.stdout)
        if match:
            return match.group(1)
    return None


def detect_gpus() -> list[GPUInfo]:
    """Detect all NVIDIA GPUs in the system."""
    gpus = []

    result = run_command(
        [
            "nvidia-smi",
            "--query-gpu=index,name,uuid,memory.total,driver_version",
            "--format=csv,noheader,nounits",
        ]
    )

    if result.returncode != 0:
        return gpus

    cuda_version = get_cuda_version() or "unknown"

    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 5:
            try:
                gpus.append(
                    GPUInfo(
                        index=int(parts[0]),
                        name=parts[1],
                        uuid=parts[2],
                        memory_total_mb=int(float(parts[3])),
                        driver_version=parts[4],
                        cuda_version=cuda_version,
                    )
                )
            except (ValueError, IndexError) as e:
                logger.debug(f"Failed to parse GPU info: {e}")

    return gpus


def check_driver_status() -> DriverStatus:
    """Check comprehensive driver status."""
    if not check_nvidia_smi():
        return DriverStatus(
            installed=False,
            version=None,
            cuda_version=None,
            needs_update=True,
            update_available=None,
            gpus=[],
        )

    version = get_driver_version()
    cuda_version = get_cuda_version()
    gpus = detect_gpus()

    needs_update = False
    if version:
        try:
            major_version = int(version.split(".")[0])
            needs_update = major_version < MIN_DRIVER_VERSION
        except (ValueError, IndexError):
            needs_update = True

    # Check for available updates (Ubuntu/Debian)
    update_available = None
    if shutil.which("apt"):
        result = run_command(
            ["apt-cache", "policy", "nvidia-driver-" + str(RECOMMENDED_DRIVER_VERSION)]
        )
        if result.returncode == 0 and "Candidate:" in result.stdout:
            match = re.search(r"Candidate:\s*(\S+)", result.stdout)
            if match and match.group(1) != "(none)":
                update_available = str(RECOMMENDED_DRIVER_VERSION)

    return DriverStatus(
        installed=version is not None,
        version=version,
        cuda_version=cuda_version,
        needs_update=needs_update,
        update_available=update_available,
        gpus=gpus,
    )


def run_apt_update(timeout: int = 15) -> bool:
    """Run apt update with sudo, with timeout for password input.

    Args:
        timeout: Seconds to wait for sudo password input

    Returns:
        True if successful, False otherwise
    """
    print("\n[GPU Setup] Running system package update...")
    print(f"[GPU Setup] You may need to enter your sudo password (timeout: {timeout}s)")

    try:
        # Use subprocess.Popen for interactive sudo
        process = subprocess.Popen(
            ["sudo", "-S", "apt", "update"],
            stdin=sys.stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            stdout, stderr = process.communicate(timeout=60)  # 60s for actual update
            if process.returncode == 0:
                print("[GPU Setup] ✓ Package lists updated successfully")
                return True
            else:
                print(f"[GPU Setup] ✗ apt update failed: {stderr}")
                return False
        except subprocess.TimeoutExpired:
            process.kill()
            print("[GPU Setup] ✗ apt update timed out")
            return False

    except Exception as e:
        print(f"[GPU Setup] ✗ Failed to run apt update: {e}")
        return False


def install_nvidia_driver(version: int = RECOMMENDED_DRIVER_VERSION) -> bool:
    """Install NVIDIA driver via apt.

    Args:
        version: Driver version to install (e.g., 550)

    Returns:
        True if successful, False otherwise
    """
    package = f"nvidia-driver-{version}"
    print(f"\n[GPU Setup] Installing {package}...")
    print("[GPU Setup] This may take several minutes...")

    try:
        process = subprocess.Popen(
            ["sudo", "-S", "apt", "install", "-y", package],
            stdin=sys.stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        # Stream output
        if process.stdout:
            for line in process.stdout:
                print(f"  {line.rstrip()}")

        process.wait()

        if process.returncode == 0:
            print(f"[GPU Setup] ✓ {package} installed successfully")
            print("[GPU Setup] ⚠ A system reboot is required to load the new driver")
            return True
        else:
            print(f"[GPU Setup] ✗ Failed to install {package}")
            return False

    except Exception as e:
        print(f"[GPU Setup] ✗ Installation failed: {e}")
        return False


def check_llama_cpp_cuda() -> bool:
    """Check if llama-cpp-python has CUDA support."""
    try:
        # Try to import and check for CUDA
        result = run_command(
            [
                sys.executable,
                "-c",
                "from llama_cpp import Llama; import llama_cpp; "
                "print('cuda' if hasattr(llama_cpp, 'GGML_CUDA') or 'cuda' in str(dir(llama_cpp)).lower() else 'cpu')",
            ]
        )
        return "cuda" in result.stdout.lower()
    except Exception:
        return False


def install_llama_cpp_cuda() -> bool:
    """Install llama-cpp-python with CUDA support."""
    print("\n[GPU Setup] Installing llama-cpp-python with CUDA support...")
    print("[GPU Setup] This may take several minutes to compile...")

    env = os.environ.copy()
    env["CMAKE_ARGS"] = "-DGGML_CUDA=on"

    try:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "llama-cpp-python",
                "--force-reinstall",
                "--no-cache-dir",
            ],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        if process.stdout:
            for line in process.stdout:
                # Only print important lines
                if any(
                    x in line.lower()
                    for x in [
                        "error",
                        "warning",
                        "building",
                        "installing",
                        "successfully",
                    ]
                ):
                    print(f"  {line.rstrip()}")

        process.wait()

        if process.returncode == 0:
            print("[GPU Setup] ✓ llama-cpp-python installed with CUDA support")
            return True
        else:
            print("[GPU Setup] ✗ Failed to install llama-cpp-python with CUDA")
            return False

    except Exception as e:
        print(f"[GPU Setup] ✗ Installation failed: {e}")
        return False


def prompt_yes_no(message: str, default: bool = True) -> bool:
    """Prompt user for yes/no input."""
    default_str = "[Y/n]" if default else "[y/N]"
    try:
        response = input(f"{message} {default_str}: ").strip().lower()
        if not response:
            return default
        return response in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        print()
        return False


def run_gpu_setup(
    auto_update: bool = False,
    skip_driver: bool = False,
    skip_llama_cpp: bool = False,
) -> bool:
    """Run comprehensive GPU setup.

    Args:
        auto_update: Automatically install updates without prompting
        skip_driver: Skip driver installation/update
        skip_llama_cpp: Skip llama-cpp-python CUDA installation

    Returns:
        True if setup completed successfully
    """
    print("\n" + "=" * 60)
    print("  NVIDIA GPU Setup for Sigil Pipeline")
    print("=" * 60)

    # Step 1: Check current status
    print("\n[Step 1/4] Checking GPU hardware and drivers...")
    status = check_driver_status()

    if not status.gpus and not status.installed:
        print("\n[GPU Setup] No NVIDIA GPUs detected or drivers not installed.")

        # Check if hardware exists but driver missing
        result = run_command(["lspci"])
        if "NVIDIA" in result.stdout.upper():
            print("[GPU Setup] NVIDIA hardware detected but drivers not installed.")

            if not skip_driver:
                if auto_update or prompt_yes_no("Install NVIDIA drivers?"):
                    # Run apt update first
                    if run_apt_update():
                        install_nvidia_driver()
                        print("\n[GPU Setup] Please reboot and run setup again.")
                        return False
        else:
            print("[GPU Setup] No NVIDIA GPU hardware found in system.")
            return False

    # Display detected GPUs
    if status.gpus:
        print(f"\n[GPU Setup] Detected {len(status.gpus)} NVIDIA GPU(s):")
        for gpu in status.gpus:
            print(f"  GPU {gpu.index}: {gpu.name} ({gpu.memory_total_mb} MB)")
        print(f"\n  Driver Version: {status.version}")
        print(f"  CUDA Version: {status.cuda_version}")

    # Step 2: Check if driver update needed
    print("\n[Step 2/4] Checking driver version...")

    if status.needs_update and not skip_driver:
        print(
            f"[GPU Setup] ⚠ Driver version {status.version} is below minimum ({MIN_DRIVER_VERSION})"
        )

        if status.update_available:
            print(f"[GPU Setup] Driver version {status.update_available} is available")

            if auto_update or prompt_yes_no("Update NVIDIA driver?"):
                print("\n[GPU Setup] Running apt update first...")
                if run_apt_update():
                    if install_nvidia_driver(int(status.update_available)):
                        print("\n[GPU Setup] ⚠ Please reboot to complete driver update")
                        return False
    else:
        print(f"[GPU Setup] ✓ Driver version {status.version} is sufficient")

    # Step 3: Check CUDA toolkit
    print("\n[Step 3/4] Checking CUDA support...")

    if status.cuda_version:
        print(f"[GPU Setup] ✓ CUDA {status.cuda_version} available via driver")
    else:
        print("[GPU Setup] ⚠ CUDA version not detected")

    # Step 4: Check llama-cpp-python CUDA support
    print("\n[Step 4/4] Checking llama-cpp-python CUDA support...")

    if not skip_llama_cpp:
        has_cuda = check_llama_cpp_cuda()
        if has_cuda:
            print("[GPU Setup] ✓ llama-cpp-python has CUDA support")
        else:
            print("[GPU Setup] ⚠ llama-cpp-python does not have CUDA support")

            if auto_update or prompt_yes_no(
                "Install llama-cpp-python with CUDA support?"
            ):
                install_llama_cpp_cuda()

    # Summary
    print("\n" + "=" * 60)
    print("  GPU Setup Complete")
    print("=" * 60)

    final_status = check_driver_status()
    if final_status.gpus:
        print(f"\n  GPUs: {len(final_status.gpus)}")
        print(f"  Driver: {final_status.version}")
        print(f"  CUDA: {final_status.cuda_version}")
        print(
            f"  Ready for multi-GPU inference: {'✓ Yes' if not final_status.needs_update else '✗ No'}"
        )

    return True


def setup_cli():
    """CLI entry point for GPU setup."""
    import argparse

    parser = argparse.ArgumentParser(description="NVIDIA GPU Setup for Sigil Pipeline")
    parser.add_argument(
        "--auto",
        "-y",
        action="store_true",
        help="Automatically install updates without prompting",
    )
    parser.add_argument(
        "--skip-driver",
        action="store_true",
        help="Skip driver installation/update",
    )
    parser.add_argument(
        "--skip-llama-cpp",
        action="store_true",
        help="Skip llama-cpp-python CUDA installation",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check status, don't install anything",
    )

    args = parser.parse_args()

    if args.check_only:
        status = check_driver_status()
        print("\nNVIDIA GPU Status:")
        print(f"  Installed: {status.installed}")
        print(f"  Version: {status.version}")
        print(f"  CUDA: {status.cuda_version}")
        print(f"  Needs Update: {status.needs_update}")
        print(f"  GPUs: {len(status.gpus)}")
        for gpu in status.gpus:
            print(f"    {gpu.index}: {gpu.name} ({gpu.memory_total_mb} MB)")
        return

    success = run_gpu_setup(
        auto_update=args.auto,
        skip_driver=args.skip_driver,
        skip_llama_cpp=args.skip_llama_cpp,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    setup_cli()
