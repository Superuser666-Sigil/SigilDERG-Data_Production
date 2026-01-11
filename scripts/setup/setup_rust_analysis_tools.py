#!/usr/bin/env python3
"""
Setup script for Rust toolchain and analysis tools.

This script handles the complete Rust environment setup:
- Installing Rust via rustup (if not present)
- Installing required rustup components (clippy, rustfmt)
- Installing cargo-audit for security scanning
- Installing additional analysis tools (geiger, outdated, license, deny)

Copyright (c) 2025-2026 Dave Tofflemire, SigilDERG Project
Version: 2.6.2
"""

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


def run_command(
    cmd: list | str,
    description: str,
    env: Optional[dict] = None,
    shell: bool = False,
) -> bool:
    """Run a command and return success status."""
    print(f"🔧 {description}...")
    try:
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)

        if shell:
            result = subprocess.run(
                cmd if isinstance(cmd, str) else " ".join(cmd),
                shell=True,
                capture_output=True,
                text=True,
                env=merged_env,
            )
        else:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=merged_env,
            )

        if result.returncode == 0:
        print(f"✅ {description} completed successfully")
        return True
        else:
            print(f"❌ {description} failed (exit code {result.returncode})")
            if result.stdout:
                print(f"stdout: {result.stdout}")
            if result.stderr:
                print(f"stderr: {result.stderr}")
        return False
    except FileNotFoundError:
        print(f"❌ Command not found: {cmd[0] if isinstance(cmd, list) else cmd}")
        return False
    except Exception as e:
        print(f"❌ {description} failed with exception: {e}")
        return False


def get_cargo_home() -> Path:
    """Get the cargo home directory."""
    cargo_home = os.environ.get("CARGO_HOME")
    if cargo_home:
        return Path(cargo_home)
    return Path.home() / ".cargo"


def get_cargo_bin() -> Path:
    """Get the cargo bin directory."""
    return get_cargo_home() / "bin"


def update_path_for_cargo() -> dict:
    """Return environment dict with cargo bin in PATH."""
    cargo_bin = str(get_cargo_bin())
    current_path = os.environ.get("PATH", "")
    if cargo_bin not in current_path:
        new_path = f"{cargo_bin}{os.pathsep}{current_path}"
    else:
        new_path = current_path
    return {"PATH": new_path}


def check_rust_installed() -> bool:
    """Check if Rust is installed and accessible."""
    env = update_path_for_cargo()
    try:
        result = subprocess.run(
            ["rustc", "--version"],
            capture_output=True,
            text=True,
            env={**os.environ, **env},
        )
        if result.returncode == 0:
            print(f"✅ Rust is installed: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass
    return False


def install_rust() -> bool:
    """Install Rust via rustup."""
    print("🦀 Installing Rust via rustup...")

    system = platform.system().lower()

    if system == "windows":
        # Windows: download and run rustup-init.exe
        print("📥 Downloading rustup-init.exe...")
        rustup_url = "https://win.rustup.rs/x86_64"
        rustup_init = Path.home() / "rustup-init.exe"

        try:
            import urllib.request
            urllib.request.urlretrieve(rustup_url, rustup_init)
        except Exception as e:
            print(f"❌ Failed to download rustup: {e}")
            return False

        # Run rustup-init with -y for non-interactive
        success = run_command(
            [str(rustup_init), "-y", "--default-toolchain", "stable"],
            "Installing Rust (this may take a few minutes)",
        )

        # Clean up installer
        if rustup_init.exists():
            rustup_init.unlink()

        return success

    else:
        # Linux/macOS: use shell installer
        install_cmd = (
            "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | "
            "sh -s -- -y --default-toolchain stable"
        )
        return run_command(
            install_cmd,
            "Installing Rust (this may take a few minutes)",
            shell=True,
        )


def install_rustup_components() -> bool:
    """Install required rustup components."""
    env = update_path_for_cargo()
    merged_env = {**os.environ, **env}

    components = [
        ("clippy", "Clippy linter"),
        ("rustfmt", "Rustfmt formatter"),
    ]

    print("📦 Installing rustup components...")
    all_success = True

    for component, description in components:
        success = run_command(
            ["rustup", "component", "add", component],
            f"Installing {description}",
            env=merged_env,
        )
        if not success:
            all_success = False

    return all_success


def install_cargo_tools() -> bool:
    """Install cargo tools for analysis."""
    env = update_path_for_cargo()
    merged_env = {**os.environ, **env}

    system = platform.system().lower()

    # Required tools (pipeline depends on these)
    required_tools = [
        (["cargo", "install", "cargo-audit"], "cargo-audit (security scanning)"),
    ]

    # Optional but recommended tools
    optional_tools = [
        (["cargo", "install", "cargo-geiger"], "cargo-geiger (unsafe code detection)"),
        (
            ["cargo", "install", "cargo-outdated"],
            "cargo-outdated (dependency updates)",
        ),
        (["cargo", "install", "cargo-license"], "cargo-license (license analysis)"),
        (
            ["cargo", "install", "cargo-deny"],
            "cargo-deny (comprehensive dependency checking)",
        ),
    ]

    # Platform-specific tools
    if system == "linux":
        optional_tools.append(
            (
                ["cargo", "install", "cargo-tarpaulin"],
                "cargo-tarpaulin (code coverage - Linux only)",
            )
        )
    else:
        print(
            f"⚠️  Skipping cargo-tarpaulin (Linux only, current: {platform.system()})"
        )

    print("📦 Installing required cargo tools...")
    all_required_success = True

    for cmd, description in required_tools:
        success = run_command(cmd, f"Installing {description}", env=merged_env)
        if not success:
            all_required_success = False
            print(f"⚠️  Required tool failed: {description}")

    print("📦 Installing optional cargo tools...")

    for cmd, description in optional_tools:
        # Don't fail on optional tools
        run_command(cmd, f"Installing {description}", env=merged_env)

    return all_required_success


def test_tools() -> None:
    """Test that the installed tools work correctly."""
    print("🧪 Testing installed tools...")

    env = update_path_for_cargo()
    merged_env = {**os.environ, **env}

    # Create a simple test crate
    test_dir = Path("test_crate_analysis")
    test_dir.mkdir(exist_ok=True)

    try:
        # Create a simple Cargo.toml
        cargo_toml = test_dir / "Cargo.toml"
        cargo_toml.write_text(
            """
[package]
name = "test_crate"
version = "0.1.0"
edition = "2021"

[dependencies]
serde = "1.0"
"""
        )

        # Create a simple lib.rs
        src_dir = test_dir / "src"
        src_dir.mkdir(exist_ok=True)
        lib_rs = src_dir / "lib.rs"
        lib_rs.write_text(
            """
use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize)]
pub struct TestStruct {
    pub field: String,
}

impl TestStruct {
    pub fn new(field: String) -> Self {
        Self { field }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_new() {
        let test = TestStruct::new("test".to_string());
        assert_eq!(test.field, "test");
    }
}
"""
        )

        # Change to test directory for cargo commands
        original_cwd = os.getcwd()
        os.chdir(test_dir)

        try:
            # Test basic cargo commands (required)
            print("🔍 Testing core Rust tools...")
            run_command(["cargo", "check"], "cargo check", env=merged_env)
            run_command(
                ["cargo", "clippy", "--", "-D", "warnings"],
                "cargo clippy",
                env=merged_env,
            )
            run_command(["cargo", "fmt", "--check"], "cargo fmt", env=merged_env)

            # Test cargo-audit (required)
            print("🔍 Testing security tools...")
            run_command(["cargo", "audit"], "cargo audit", env=merged_env)

            # Test optional tools (don't fail if missing)
            print("🔍 Testing optional analysis tools...")

            # cargo tree is built-in
            run_command(["cargo", "tree", "--depth", "1"], "cargo tree", env=merged_env)

            # Optional tools - just check if they work
            for tool_cmd, tool_name in [
                (["cargo", "geiger", "--forbid-only"], "cargo geiger"),
                (["cargo", "outdated", "--depth", "1"], "cargo outdated"),
                (["cargo", "license"], "cargo license"),
            ]:
        try:
                    run_command(tool_cmd, tool_name, env=merged_env)
        except Exception:
                    print(f"⚠️  {tool_name} not available (optional)")

        finally:
            os.chdir(original_cwd)

        print("✅ Tool testing completed")

    finally:
        # Clean up test directory
        if test_dir.exists():
            shutil.rmtree(test_dir)


def print_summary() -> None:
    """Print summary of available tools."""
    system = platform.system().lower()

    print("\n" + "=" * 60)
    print("🎉 Rust environment setup completed!")
    print("=" * 60)
    print("\n📋 Available tools:")
    print("   Core (required):")
    print("   • rustc        - Rust compiler")
    print("   • cargo        - Package manager")
    print("   • clippy       - Linting and code quality")
    print("   • rustfmt      - Code formatting")
    print("   • cargo audit  - Security vulnerability scanning")
    print("\n   Analysis (optional):")
    print("   • cargo tree     - Dependency tree visualization")
    print("   • cargo geiger   - Unsafe code detection")
    print("   • cargo outdated - Dependency update checking")
    print("   • cargo license  - License analysis")
    print("   • cargo deny     - Comprehensive dependency checking")
    if system == "linux":
        print("   • cargo tarpaulin - Code coverage (Linux only)")

    print("\n📝 To use these tools in a new terminal, run:")
    print('   source "$HOME/.cargo/env"')
    print("\n   Or add to your shell profile (~/.bashrc, ~/.zshrc, etc.):")
    print('   echo \'source "$HOME/.cargo/env"\' >> ~/.bashrc')


def main() -> int:
    """Main setup function."""
    print("=" * 60)
    print("🚀 SigilDERG Rust Environment Setup")
    print("=" * 60)
    print()

    # Check if Rust is already installed
    rust_installed = check_rust_installed()

    if not rust_installed:
        print("🦀 Rust not found. Installing via rustup...")
        if not install_rust():
            print("❌ Failed to install Rust. Please install manually:")
            print("   https://rustup.rs/")
            return 1

        # Verify installation
        if not check_rust_installed():
            print("❌ Rust installation verification failed.")
            print("   Try opening a new terminal and running this script again.")
            return 1

    # Install rustup components
    print()
    if not install_rustup_components():
        print("⚠️  Some rustup components failed to install")

    # Install cargo tools
    print()
    if not install_cargo_tools():
        print("⚠️  Some required cargo tools failed to install")
        print("   The pipeline may not function correctly.")

    # Test the installation
    print()
    test_tools()

    # Print summary
    print_summary()

    return 0


if __name__ == "__main__":
    sys.exit(main())
