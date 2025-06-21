#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Rust Crate Pipeline Container...${NC}"

# Create directories if they don't exist
mkdir -p /app/output /app/logs /app/cache /app/models

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
python -c "import rust_crate_pipeline; print(f'Package version: {rust_crate_pipeline.__version__}')" || {
    echo -e "${RED}Failed to import rust_crate_pipeline${NC}"
    exit 1
}

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
import rust_crate_pipeline
print(f'Package: {rust_crate_pipeline.__name__}')
print(f'Version: {rust_crate_pipeline.__version__}')
print(f'Author: {rust_crate_pipeline.__author__}')
print('✅ Container test successful!')
"
elif [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    # Show help
    echo -e "${GREEN}Rust Crate Pipeline Docker Container${NC}"
    echo ""
    echo "Usage:"
    echo "  docker run rust-crate-pipeline [OPTIONS]"
    echo ""
    echo "Special commands:"
    echo "  bash    - Start interactive bash shell"
    echo "  test    - Run container test"
    echo "  --help  - Show this help"
    echo ""
    echo "Pipeline options (passed to rust-crate-pipeline):"
    exec rust-crate-pipeline --help
else
    # Normal pipeline execution
    echo -e "${GREEN}Starting rust-crate-pipeline with arguments: $@${NC}"
    
    # Build the command with output directory
    ARGS="$@"
    
    # Add output directory if not already specified
    if [[ "$ARGS" != *"--output-dir"* ]]; then
        ARGS="$ARGS --output-dir=$OUTPUT_DIR"
    fi
    
    # Add cache directory if not already specified
    if [[ "$ARGS" != *"--cache-dir"* ]] && [[ "$ARGS" == *"--cache-dir"* ]]; then
        ARGS="$ARGS --cache-dir=$CACHE_DIR"
    fi
    
    echo -e "${YELLOW}Executing: rust-crate-pipeline $ARGS${NC}"
    exec rust-crate-pipeline $ARGS
fi
