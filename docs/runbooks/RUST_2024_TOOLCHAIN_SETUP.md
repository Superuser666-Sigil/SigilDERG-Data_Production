# Rust 2024 Toolchain Setup for Dataset Hardening

This runbook provides instructions for setting up the Rust 2024 toolchain required for the `--dataset-hardening` mode in sigil-pipeline.

## Prerequisites

The dataset hardening feature requires:
- **Rust 1.85+** (for Edition 2024 support)
- **rustfmt** with Edition 2024 style support
- **clippy** with pedantic and nursery lints

## Quick Check

Verify your current Rust version:

```bash
rustc --version
# Expected: rustc 1.85.0 or higher
```

If you see a version lower than 1.85, follow the installation steps below.

## Installation Options

### Option 1: Stable Channel (Recommended for Production)

As of early 2025, Rust 1.85 may still be in beta. Once stable:

```bash
# Update rustup to latest
rustup self update

# Update to latest stable
rustup update stable

# Set stable as default
rustup default stable

# Verify installation
rustc --version
```

### Option 2: Nightly Channel (For Early Access)

If stable Rust 1.85+ is not yet available:

```bash
# Install nightly toolchain
rustup install nightly

# Set nightly as default (optional)
rustup default nightly

# Or use nightly for specific project
rustup override set nightly

# Verify installation
rustc +nightly --version
```

### Option 3: Specific Version

Install a specific Rust version:

```bash
# Install specific version
rustup install 1.85.0

# Use for this session
rustup override set 1.85.0

# Or set as default
rustup default 1.85.0
```

## Verify Components

Ensure required components are installed:

```bash
# Install clippy
rustup component add clippy

# Install rustfmt
rustup component add rustfmt

# Verify clippy
cargo clippy --version

# Verify rustfmt
cargo fmt --version
```

## Edition 2024 Configuration

For the hardening mode, crates should declare Edition 2024 in their `Cargo.toml`:

```toml
[package]
name = "your-crate"
version = "0.1.0"
edition = "2024"
```

Note: The pipeline automatically checks crate editions and filters accordingly.

## Using the Hardening Mode

Once your toolchain is set up:

```bash
# Run pipeline with hardening enabled
python -m sigil_pipeline \
    --dataset-hardening \
    --output output/hardened_dataset.jsonl \
    --crate-list data/crate_list.txt

# With specific hardening options disabled
python -m sigil_pipeline \
    --dataset-hardening \
    --no-hardening-strict-clippy \   # Skip pedantic clippy (faster)
    --output output/hardened_dataset.jsonl
```

## Troubleshooting

### "Toolchain Not Found" Error

If you see:
```
ERROR: Dataset hardening requires Rust 1.85+ for Edition 2024 support.
```

**Solution**: Follow the installation steps above to install Rust 1.85+.

### Clippy Errors on CI

Strict clippy can produce many warnings on existing codebases. Options:
1. Fix the warnings in your code
2. Use `--no-hardening-strict-clippy` to skip strict clippy checks
3. Run without hardening: remove `--dataset-hardening` flag

### Rustfmt Style Differences

Edition 2024 rustfmt uses different defaults. If crates fail:
1. Update the crate's `rustfmt.toml` if you control it
2. Use `--no-hardening-rustfmt` to skip format checks

### Performance Considerations

Strict clippy adds significant overhead (~2-5x analysis time per crate). Mitigations:
- **Hardware**: Use fast NVMe storage and 8+ CPU cores
- **Selective checks**: Use `--no-hardening-*` flags to disable slower checks
- **Incremental runs**: Use checkpoint files with `--checkpoint-dir`
- **Parallel processing**: Ensure `--max-threads` is set appropriately

## Additional Resources

- [Rust Edition Guide](https://doc.rust-lang.org/edition-guide/)
- [Rust 2024 Edition Announcement](https://blog.rust-lang.org/)
- [Clippy Lints](https://rust-lang.github.io/rust-clippy/master/)
- [Rustfmt Configuration](https://rust-lang.github.io/rustfmt/)

## External Reference

For comprehensive Rust 2024 benchmark hardening standards, see:
- [openrustscience/rust2024-benchmark-hardening-pipeline](https://github.com/openrustscience/rust2024-benchmark-hardening-pipeline)

---

*Last updated: 2025*
