# Sigil Pipeline Dockerfile
#
# Docker image for the Sigil Pipeline - a static analysis pipeline for generating
# high-quality Rust code datasets for model fine-tuning.
#
# Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
# Version: 2.0.0
#
# Features:
# - Python 3.12 base image
# - Rust toolchain (stable) with clippy and rustfmt
# - All required system dependencies for cargo subcommands
# - Pre-configured environment for pipeline execution
#
# Build:
#   docker build -t sigil-pipeline:2.0.0 .
#
# Run:
#   docker run -v $(pwd)/output:/app/output sigil-pipeline:1.1.0 --help
#

FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV RUSTUP_HOME=/usr/local/rustup
ENV CARGO_HOME=/usr/local/cargo
ENV PATH=/usr/local/cargo/bin:$PATH

# Install system dependencies and Rust toolchain
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    wget \
    gnupg \
    ca-certificates \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Rust toolchain (required for cargo commands)
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y \
    && rustup default stable \
    && rustup component add rustfmt clippy \
    && chmod -R a+w $RUSTUP_HOME $CARGO_HOME

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install build tools for building the package
RUN pip install --no-cache-dir build wheel

# Copy application code
COPY . .

# Build and install the package from source
RUN python -m build && \
    pip install --no-cache-dir dist/*.whl

# Install cargo subcommands that the pipeline uses (optional, can be installed at runtime)
# These are installed via cargo install, but we'll let the pipeline handle it
# to avoid bloating the image if not all are needed

# Create output directory
RUN mkdir -p /app/output /app/logs /app/cache /app/models /app/data

# Copy entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Set default command
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["--help"]
