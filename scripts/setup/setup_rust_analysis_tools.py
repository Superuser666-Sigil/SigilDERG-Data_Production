#!/usr/bin/env python3
"""
Setup script for additional Rust analysis tools.

Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
Version: 2.4.0
"""

import subprocess
import sys
from pathlib import Path


def run_command(cmd: list, description: str) -> bool:
    """Run a command and return success status."""
    print(f"🔧 {description}...")
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        if e.stdout:
            print(f"stdout: {e.stdout}")
        if e.stderr:
            print(f"stderr: {e.stderr}")
        return False
    except FileNotFoundError:
        print(f"❌ Command not found: {' '.join(cmd)}")
        return False


def check_rust_installed() -> bool:
    """Check if Rust is installed."""
    return run_command(["rustc", "--version"], "Checking Rust installation")


def install_cargo_tools() -> None:
    """Install additional cargo tools for enhanced analysis."""
    import platform

    # Core tools that work on all platforms
    tools = [
        (["cargo", "install", "cargo-geiger"], "cargo-geiger (unsafe code detection)"),
        (["cargo", "install", "cargo-outdated"], "cargo-outdated (dependency updates)"),
        (["cargo", "install", "cargo-license"], "cargo-license (license analysis)"),
        (
            ["cargo", "install", "cargo-deny"],
            "cargo-deny (comprehensive dependency checking)",
        ),
    ]

    # cargo-tarpaulin only works on Linux
    if platform.system().lower() == "linux":
        tools.append(
            (
                ["cargo", "install", "cargo-tarpaulin"],
                "cargo-tarpaulin (code coverage - Linux only)",
            )
        )
    else:
        print(
            f"⚠️  Skipping cargo-tarpaulin (Linux only, current platform: {platform.system()})"
        )

    print("📦 Installing additional Rust analysis tools...")

    for cmd, description in tools:
        run_command(cmd, f"Installing {description}")

    print("✅ Rust analysis tools installation completed")


def test_tools() -> None:
    """Test that the installed tools work correctly."""
    print("🧪 Testing installed tools...")

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
version = "2.0.0"
edition = "2021"

[dependencies]
serde = "1.0"
"""
        )

        # Create a simple lib.rs
        lib_rs = test_dir / "src" / "lib.rs"
        lib_rs.parent.mkdir(exist_ok=True)
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

        # Test basic cargo commands
        print("🔍 Testing basic cargo commands...")
        run_command(["cargo", "check"], "cargo check")
        run_command(["cargo", "test"], "cargo test")
        run_command(["cargo", "clippy"], "cargo clippy")

        # Test additional tools if available
        print("🔍 Testing additional analysis tools...")
        run_command(["cargo", "audit"], "cargo audit")
        run_command(["cargo", "tree"], "cargo tree")

        # Test enhanced tools (these might not be installed)
        try:
            run_command(["cargo", "geiger", "--format", "json"], "cargo geiger")
        except Exception:
            print("⚠️  cargo-geiger not available (optional)")

        try:
            run_command(["cargo", "outdated", "--format", "json"], "cargo outdated")
        except Exception:
            print("⚠️  cargo-outdated not available (optional)")

        try:
            run_command(["cargo", "license", "--json"], "cargo license")
        except Exception:
            print("⚠️  cargo-license not available (optional)")

        print("✅ Tool testing completed")

    finally:
        # Clean up test directory
        import shutil

        if test_dir.exists():
            shutil.rmtree(test_dir)


def main() -> None:
    """Main setup function."""
    print("🚀 Setting up enhanced Rust analysis tools...")

    # Check if Rust is installed
    if not check_rust_installed():
        print("❌ Rust is not installed. Please install Rust first:")
        print("   https://rustup.rs/")
        sys.exit(1)

    # Install additional tools
    install_cargo_tools()

    # Test the tools
    test_tools()

    import platform

    print("🎉 Enhanced Rust analysis setup completed!")
    print("\n📋 Available tools:")
    print("   • cargo check - Basic compilation check")
    print("   • cargo clippy - Linting and code quality")
    print("   • cargo audit - Security vulnerability scanning")
    print("   • cargo geiger - Unsafe code detection")
    print("   • cargo outdated - Dependency update checking")
    print("   • cargo license - License analysis")
    print("   • cargo deny - Comprehensive dependency checking")
    if platform.system().lower() == "linux":
        print("   • cargo tarpaulin - Code coverage (Linux only)")
    else:
        print("   ⚠️  cargo tarpaulin - Not available (Linux only)")


if __name__ == "__main__":
    main()
