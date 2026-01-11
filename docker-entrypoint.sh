#!/bin/bash
#
# Docker entrypoint script for Sigil Pipeline container.
#
# Handles container initialization, environment setup, and command routing.
# Supports multiple execution modes: bash shell, test mode, help, and normal pipeline execution.
#
# Copyright (c) 2025 Dave Tofflemire, SigilDERG Project
# Version: 2.6.0
#
# Usage:
#   docker run sigil-pipeline [OPTIONS]     # Run pipeline with options
#   docker run sigil-pipeline bash          # Interactive shell
#   docker run sigil-pipeline test          # Test container setup
#   docker run sigil-pipeline --help        # Show help
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Sigil Pipeline Container...${NC}"

# Create directories if they don't exist
mkdir -p /app/output /app/logs /app/cache /app/models /app/data

# Set default values
OUTPUT_DIR=${OUTPUT_DIR:-/app/output}
LOG_LEVEL=${LOG_LEVEL:-INFO}
CACHE_DIR=${CACHE_DIR:-/app/cache}

echo -e "${YELLOW}Configuration:${NC}"
echo "  Output Directory: $OUTPUT_DIR"
echo "  Log Level: $LOG_LEVEL"
echo "  Cache Directory: $CACHE_DIR"

# Check if GitHub token is provided
if [ -n "$GITHUB_TOKEN" ]; then
    echo -e "${GREEN}GitHub token provided${NC}"
else
    echo -e "${YELLOW}Warning: No GitHub token provided. Rate limiting may occur.${NC}"
fi

# Verify package installation
echo -e "${YELLOW}Verifying package installation...${NC}"
python -c "import sigil_pipeline; print(f'Package version: {sigil_pipeline.__version__}')" || {
    echo -e "${RED}Failed to import sigil_pipeline${NC}"
    exit 1
}

# Check Rust/cargo availability
echo -e "${YELLOW}Checking Rust toolchain...${NC}"
if command -v cargo &> /dev/null; then
    cargo_version=$(cargo --version || echo "unknown")
    echo -e "${GREEN}Rust toolchain available: $cargo_version${NC}"
else
    echo -e "${YELLOW}Warning: cargo not found in PATH. Some features may not work.${NC}"
fi

echo -e "${GREEN}Package verification successful${NC}"

# Handle different execution modes
if [ "$1" = "bash" ]; then
    # Interactive bash shell
    echo -e "${GREEN}Starting interactive bash shell...${NC}"
    exec /bin/bash
elif [ "$1" = "test" ]; then
    # Test mode
    echo -e "${GREEN}Running in test mode...${NC}"
    exec python -c "
import sigil_pipeline
print(f'Package: {sigil_pipeline.__name__}')
print(f'Version: {sigil_pipeline.__version__}')
print('Container test successful!')
"
elif [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    # Show help
    echo -e "${GREEN}Sigil Pipeline Docker Container${NC}"
    echo ""
    echo "Usage:"
    echo "  docker run sigil-pipeline [OPTIONS]"
    echo ""
    echo "Special commands:"
    echo "  bash    - Start interactive bash shell"
    echo "  test    - Run container test"
    echo "  --help  - Show this help"
    echo ""
    echo "Pipeline options (passed to sigil_pipeline.main):"
    exec python -m sigil_pipeline.main --help
else
    # Normal pipeline execution
    echo -e "${GREEN}Starting sigil_pipeline.main with arguments: $@${NC}"
    
    # Build the command with output path
    ARGS="$@"
    
    # Add output path if not already specified
    if [[ "$ARGS" != *"--output"* ]]; then
        ARGS="$ARGS --output=$OUTPUT_DIR/sigil_phase2_dataset.jsonl"
    fi
    
    echo -e "${YELLOW}Executing: python -m sigil_pipeline.main $ARGS${NC}"
    exec python -m sigil_pipeline.main $ARGS
fi
