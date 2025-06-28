# Use a more specific version with better security posture
FROM python:3.11.9-slim-bookworm

# Security and maintainer information
LABEL author="SuperUser666-Sigil"
LABEL email="miragemodularframework@gmail.com"
LABEL version="1.3.1"
LABEL description="Rust Crate Data Processing Pipeline with Crawl4AI Integration"
LABEL org.opencontainers.image.source="https://github.com/Superuser666-Sigil/SigilDERG-Data_Production"
LABEL org.opencontainers.image.documentation="https://github.com/Superuser666-Sigil/SigilDERG-Data_Production/blob/main/README.md"
LABEL org.opencontainers.image.licenses="MIT"

# Set working directory
WORKDIR /app

# Install system dependencies with Crawl4AI support
RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    build-essential \
    # Crawl4AI dependencies for web browser automation
    chromium \
    chromium-driver \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libc6 \
    libcairo-gobject2 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libfontconfig1 \
    libgbm1 \
    libgcc1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libstdc++6 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    # Security updates
    && apt-get upgrade -y \
    # Clean up to reduce image size and attack surface
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && apt-get autoremove -y

# Create non-root user first
RUN useradd -m -u 1000 pipelineuser \
    && mkdir -p /app/output /app/logs /app/cache /app/models \
    && chown -R pipelineuser:pipelineuser /app

# Copy requirements and install dependencies with security updates
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --upgrade setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt \
    # Install Playwright browsers for Crawl4AI
    && python -m playwright install chromium \
    && python -m playwright install-deps chromium \
    # Verify no known vulnerabilities in installed packages
    && pip check

# Copy the package files and integration modules
COPY rust_crate_pipeline/ ./rust_crate_pipeline/
COPY utils/ ./utils/
COPY pyproject.toml setup.py README.md ./

# Install the package in development mode
RUN pip install --no-cache-dir -e .

# Switch to non-root user
USER pipelineuser

# Set environment variables for security and performance
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV OUTPUT_DIR=/app/output
ENV LOG_LEVEL=INFO
ENV CACHE_DIR=/app/cache
# Security: Prevent Python from loading user site-packages
ENV PYTHONNOUSERSITE=1
# Security: Enable hash randomization
ENV PYTHONHASHSEED=random
# Crawl4AI configuration for headless operation
ENV CRAWL4AI_HEADLESS=true
ENV CRAWL4AI_BROWSER_PATH=/usr/bin/chromium
ENV DISPLAY=:99
# LLM model configuration for direct llama.cpp inference
ENV MODEL_PATH=/app/models/deepseek-coder-6.7b-instruct.Q4_K_M.gguf
ENV LLM_MODEL_PATH=/app/models/deepseek-coder-6.7b-instruct.Q4_K_M.gguf
ENV LLM_CONTEXT_SIZE=4096
ENV LLM_MAX_TOKENS=512
ENV LLM_TEMPERATURE=0.1

# Create an entrypoint script
COPY --chown=pipelineuser:pipelineuser docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

# Health check with updated config validation
HEALTHCHECK --interval=60s --timeout=15s --start-period=120s --retries=3 \
    CMD python -c "import rust_crate_pipeline; from rust_crate_pipeline.config import PipelineConfig; PipelineConfig(); print('OK')" || exit 1

# Expose any ports if needed (for monitoring/logs)
EXPOSE 8080

# Use entrypoint script
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Default command - can be overridden
CMD ["--limit", "1000", "--batch-size", "10", "--log-level", "INFO"]
