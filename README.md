# Rust Crate Pipeline

A comprehensive system for gathering, enriching, and analyzing metadata for Rust crates using AI-powered insights, web scraping, and dependency analysis.

## Overview

The Rust Crate Pipeline is designed to collect, process, and enrich metadata from Rust crates available on crates.io. It combines web scraping, AI-powered analysis, and cargo testing to provide comprehensive insights into Rust ecosystem packages.

## Features

- **Enhanced Web Scraping**: Automated collection of crate metadata from crates.io using Crawl4AI with Playwright
- **AI Enrichment**: Local and Azure OpenAI-powered analysis of crate descriptions, features, and documentation
- **Multi-Provider LLM Support**: Unified LLM processor supporting OpenAI, Azure OpenAI, Ollama, LM Studio, and LiteLLM
- **Cargo Testing**: Automated cargo build, test, and audit execution for comprehensive crate analysis
- **Dependency Analysis**: Deep analysis of crate dependencies and their relationships
- **Batch Processing**: Efficient processing of multiple crates with configurable batch sizes
- **Data Export**: Structured output in JSON format for further analysis
- **RAG Cache**: Intelligent caching with Rule Zero policies and architectural patterns
- **Docker Support**: Containerized deployment with optimized Docker configurations
- **Real-time Progress Monitoring**: CLI-based progress tracking with ASCII status indicators
- **Cross-platform Compatibility**: Full Unicode symbol replacement for better encoding support

## Requirements

- **Python 3.12+**: Required for modern type annotations and language features
- **Git**: For cloning repositories during analysis
- **Cargo**: For Rust crate testing and analysis
- **Playwright**: Automatically installed for enhanced web scraping

## Installation

```bash
# Clone the repository
git clone https://github.com/Superuser666-Sigil/SigilDERG-Data_Production.git
cd SigilDERG-Data_Production

# Install in development mode (includes all dependencies)
pip install -e .

# Install Playwright browsers for enhanced scraping
playwright install
```

### Automatic Dependency Installation

The package automatically installs all required dependencies including:
- `crawl4ai` for web scraping
- `playwright` for enhanced browser automation
- `requests` for HTTP requests
- `aiohttp` for async operations
- And all other required packages

## Configuration

### Environment Variables

Set the following environment variables for full functionality:

```bash
# GitHub Personal Access Token (required for API access)
export GITHUB_TOKEN="your_github_token_here"

# Azure OpenAI (optional, for cloud AI processing)
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
export AZURE_OPENAI_API_KEY="your_azure_openai_key"
export AZURE_OPENAI_DEPLOYMENT_NAME="your_deployment_name"
export AZURE_OPENAI_API_VERSION="2024-02-15-preview"

# PyPI API Token (optional, for publishing)
export PYPI_API_TOKEN="your_pypi_token"

# LiteLLM Configuration (optional, for multi-provider LLM support)
export LITELLM_MODEL="deepseek-coder:33b"
export LITELLM_BASE_URL="http://localhost:11434"  # For Ollama
```

### Configuration File

Create a `config.json` file for custom settings:

```json
{
    "batch_size": 10,
    "n_workers": 4,
    "max_retries": 3,
    "checkpoint_interval": 10,
    "use_azure_openai": true,
    "crawl4ai_config": {
        "max_pages": 5,
        "concurrency": 2
    }
}
```

## Usage

### Command Line Interface

#### Basic Usage

```bash
# Run with default settings
python -m rust_crate_pipeline

# Run with custom batch size
python -m rust_crate_pipeline --batch-size 20

# Run with specific workers
python -m rust_crate_pipeline --workers 8

# Use configuration file
python -m rust_crate_pipeline --config-file config.json
```

#### Advanced Options

```bash
# Enable Azure OpenAI processing
python -m rust_crate_pipeline --enable-azure-openai

# Set custom model path for local AI
python -m rust_crate_pipeline --model-path /path/to/model.gguf

# Configure token limits
python -m rust_crate_pipeline --max-tokens 2048

# Set checkpoint interval
python -m rust_crate_pipeline --checkpoint-interval 5

# Enable verbose logging
python -m rust_crate_pipeline --log-level DEBUG

# Enable enhanced scraping with Playwright
python -m rust_crate_pipeline --enable-enhanced-scraping

# Set output directory for results
python -m rust_crate_pipeline --output-path ./results
```

#### Enhanced Scraping

The pipeline now supports enhanced web scraping using Playwright for better data extraction:

```bash
# Enable enhanced scraping (default)
python -m rust_crate_pipeline --enable-enhanced-scraping

# Use basic scraping only
python -m rust_crate_pipeline --disable-enhanced-scraping

# Configure scraping options
python -m rust_crate_pipeline --scraping-config '{"max_pages": 10, "concurrency": 3}'
```

#### Multi-Provider LLM Support

```bash
# Use OpenAI
python -m rust_crate_pipeline.unified_llm_processor --provider openai --model-name gpt-4

# Use Azure OpenAI
python -m rust_crate_pipeline.unified_llm_processor --provider azure --model-name gpt-4

# Use Ollama (local)
python -m rust_crate_pipeline.unified_llm_processor --provider ollama --model-name deepseek-coder:33b

# Use LM Studio
python -m rust_crate_pipeline.unified_llm_processor --provider openai --base-url http://localhost:1234/v1 --model-name local-model

# Use LiteLLM
python -m rust_crate_pipeline.unified_llm_processor --provider litellm --model-name deepseek-coder:33b
```

#### Production Mode

```bash
# Run production pipeline with optimizations
python run_production.py

# Run with Sigil Protocol integration
python -m rust_crate_pipeline --enable-sigil-protocol
```

### Programmatic Usage

```python
from rust_crate_pipeline import CrateDataPipeline
from rust_crate_pipeline.config import PipelineConfig

# Create configuration
config = PipelineConfig(
    batch_size=10,
    n_workers=4,
    use_azure_openai=True
)

# Initialize pipeline
pipeline = CrateDataPipeline(config)

# Run pipeline
import asyncio
result = asyncio.run(pipeline.run())
```

## Sample Data

### Input: Crate List

The pipeline processes crates from `rust_crate_pipeline/crate_list.txt`:

```
tokio
serde
reqwest
actix-web
clap
```

### Output: Enriched Crate Data

```json
{
    "name": "tokio",
    "version": "1.35.1",
    "description": "An asynchronous runtime for Rust",
    "downloads": 125000000,
    "github_stars": 21500,
    "keywords": ["async", "runtime", "tokio", "futures"],
    "categories": ["asynchronous", "network-programming"],
    "features": {
        "full": ["all features enabled"],
        "rt": ["runtime features"],
        "macros": ["macro support"]
    },
    "readme_summary": "Tokio is an asynchronous runtime for Rust that provides the building blocks for writing network applications.",
    "use_case": "Networking",
    "factual_counterfactual": "✅ Factual: Tokio provides async I/O primitives\n❌ Counterfactual: Tokio is a synchronous runtime",
    "score": 9.5,
    "cargo_test_results": {
        "build_success": true,
        "test_success": true,
        "audit_clean": true,
        "dependencies": 45
    },
    "ai_insights": {
        "complexity": "High",
        "maturity": "Production Ready",
        "community_health": "Excellent"
    }
}
```

## Architecture

### Core Components

- **Pipeline Orchestrator**: Manages the overall data processing workflow
- **Web Scraper**: Collects crate metadata using Crawl4AI
- **AI Enricher**: Enhances data with local or cloud AI analysis
- **Cargo Analyzer**: Executes cargo commands for comprehensive testing
- **Data Exporter**: Outputs structured results in various formats

### Data Flow

1. **Input**: Crate names from `crate_list.txt`
2. **Scraping**: Web scraping of crates.io for metadata
3. **Enrichment**: AI-powered analysis and insights
4. **Testing**: Cargo build, test, and audit execution
5. **Output**: Structured JSON with comprehensive crate analysis

## Development

### Prerequisites

- Python 3.12+ (required for modern type annotations)
- Git for version control
- Cargo for Rust crate testing

### Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test module
pytest tests/test_main_integration.py

# Run with coverage
pytest --cov=rust_crate_pipeline tests/

# Run type checking
pyright rust_crate_pipeline/

# Run linting
flake8 rust_crate_pipeline/
```

### Code Quality

```bash
# Format code
black rust_crate_pipeline/

# Sort imports
isort rust_crate_pipeline/

# Type checking
pyright rust_crate_pipeline/

# Lint code
flake8 rust_crate_pipeline/
```

### Building and Publishing

```bash
# Build package
python -m build

# Upload to PyPI (requires PYPI_API_TOKEN)
python -m twine upload dist/*

# Create release
python scripts/create_release.py
```

### Docker Development

```bash
# Build Docker image
docker build -t rust-crate-pipeline .

# Run in Docker
docker run -it rust-crate-pipeline

# Run with volume mount for development
docker run -it -v $(pwd):/app rust-crate-pipeline
```

## Recent Improvements

### Version 1.4.0
- **Security**: Robust Ed25519/RSA cryptographic signing and provenance
- **Automation**: Automated RAG and provenance workflows
- **CI/CD**: Improved GitHub Actions for validation and publishing
- **Docker**: Updated Docker image and compose for new version
- **Bug Fixes**: Workflow and validation fixes for Ed25519

### Version 1.3.6
- **Python 3.12+ Requirement**: Updated to use modern type annotations and language features
- **Type Safety**: Enhanced type annotations throughout the codebase with modern syntax
- **Build System**: Updated pyproject.toml and setup.py for better compatibility

### Version 1.3.5
- **Enhanced Web Scraping**: Added Playwright-based scraping for better data extraction
- **Unicode Compatibility**: Replaced all Unicode symbols with ASCII equivalents for better cross-platform support
- **Automatic Dependencies**: All required packages are now automatically installed
- **Real-time Progress**: Added CLI-based progress monitoring with ASCII status indicators
- **Docker Optimization**: Updated Dockerfile to include Playwright browser installation

### Version 1.3.4
- **PEP8 Compliance**: Fixed all Unicode emoji and symbols for better encoding support
- **Cross-platform Compatibility**: Improved compatibility across different operating systems
- **Type Safety**: Enhanced type annotations throughout the codebase

### Version 1.3.3
- **Real-time Progress Monitoring**: Added CLI-only progress tracking feature
- **Enhanced Logging**: Improved status reporting and error handling

### Version 1.3.2
- **Multi-Provider LLM Support**: Added support for OpenAI, Azure OpenAI, Ollama, LM Studio, and LiteLLM
- **Unified LLM Processor**: Centralized LLM processing with provider abstraction
- **Enhanced Error Handling**: Better error recovery and retry mechanisms

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## Support

For issues and questions:
- GitHub Issues: https://github.com/Superuser666-Sigil/SigilDERG-Data_Production/issues
- Documentation: https://github.com/Superuser666-Sigil/SigilDERG-Data_Production#readme 

## API Compliance & Attribution

### crates.io and GitHub API Usage
- This project accesses crates.io and GitHub APIs for data gathering and verification.
- **User-Agent:** All requests use:
  
  `SigilDERG-Data-Production (Superuser666-Sigil; miragemodularframework@gmail.com; https://github.com/Superuser666-Sigil/SigilDERG-Data_Production)`
- **Contact:** miragemodularframework@gmail.com
- **GitHub:** [Superuser666-Sigil/SigilDERG-Data_Production](https://github.com/Superuser666-Sigil/SigilDERG-Data_Production)
- The project respects all rate limits and crawler policies. If you have questions or concerns, please contact us.

### Crawl4AI Attribution
This project uses [Crawl4AI](https://github.com/unclecode/crawl4ai) for web data extraction.

<!-- Badge Attribution (Disco Theme) -->
<a href="https://github.com/unclecode/crawl4ai">
  <img src="https://raw.githubusercontent.com/unclecode/crawl4ai/main/docs/assets/powered-by-disco.svg" alt="Powered by Crawl4AI" width="200"/>
</a>

Or, text attribution:

```
This project uses Crawl4AI (https://github.com/unclecode/crawl4ai) for web data extraction.
```

## 🚀 Unified, Cross-Platform, Multi-Provider LLM Support

This project supports **all major LLM providers** (cloud and local) on **Mac, Linux, and Windows** using a single, unified interface. All LLM calls are routed through the `UnifiedLLMProcessor` and `LLMConfig` abstractions, ensuring:

- **One code path for all providers:** Azure OpenAI, OpenAI, Anthropic, Google, Cohere, HuggingFace, Ollama, LM Studio, and any OpenAI-compatible endpoint.
- **Cross-platform compatibility:** Works out of the box on Mac, Linux, and Windows.
- **Configurable via CLI and config files:** Select provider, model, API key, endpoint, and provider-specific options at runtime.
- **Easy extensibility:** Add new providers by updating your config or CLI arguments—no code changes needed.

### 📖 Provider Setup & Usage
- See [`README_LLM_PROVIDERS.md`](./README_LLM_PROVIDERS.md) for full details, setup instructions, and usage examples for every supported provider.
- Run `python run_pipeline_with_llm.py --help` for CLI options and provider-specific arguments.

### 🧩 Example Usage
```bash
# Azure OpenAI
python run_pipeline_with_llm.py --llm-provider azure --llm-model gpt-4o --crates tokio

# Ollama (local)
python run_pipeline_with_llm.py --llm-provider ollama --llm-model llama2 --crates serde

# OpenAI API
python run_pipeline_with_llm.py --llm-provider openai --llm-model gpt-4 --llm-api-key YOUR_KEY --crates tokio

# Anthropic Claude
python run_pipeline_with_llm.py --llm-provider anthropic --llm-model claude-3-sonnet --llm-api-key YOUR_KEY --crates serde
```

### 🔒 Security & Best Practices
- Store API keys as environment variables.
- Use local providers (Ollama, LM Studio) for full privacy—no data leaves your machine.
- All LLM calls are routed through a single, auditable interface for maximum maintainability and security.

### 🧪 Testing
- Run `python test_unified_llm.py` to verify provider support and configuration.

For more, see [`README_LLM_PROVIDERS.md`](./README_LLM_PROVIDERS.md) and the CLI help output. 
