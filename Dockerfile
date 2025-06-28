# Rust Crate Pipeline Dockerfile
# Version: 1.3.1
# Updated: June 28, 2025
# Changes: Type annotation compatibility fixes for Python 3.9+

FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
COPY requirements-crawl4ai.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r requirements-crawl4ai.txt

# Copy application code
COPY . .

# Install the package in development mode
RUN pip install -e .

# Create output directory
RUN mkdir -p /app/output

# Set default command
CMD ["python", "-m", "rust_crate_pipeline"]
