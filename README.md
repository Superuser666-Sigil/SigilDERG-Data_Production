# Rust Crate Pipeline

A comprehensive system for gathering, enriching, and analyzing metadata for Rust crates using AI-powered insights, web scraping, and dependency analysis.

## Overview

The Rust Crate Pipeline is designed to collect, process, and enrich metadata from Rust crates available on crates.io. It combines web scraping, AI-powered analysis, and cargo testing to provide comprehensive insights into Rust ecosystem packages.

## Features

- **Web Scraping**: Automated collection of crate metadata from crates.io using Crawl4AI
- **AI Enrichment**: Local and Azure OpenAI-powered analysis of crate descriptions, features, and documentation
- **Multi-Provider LLM Support**: Unified LLM processor supporting OpenAI, Azure OpenAI, Ollama, LM Studio, and LiteLLM
- **Cargo Testing**: Automated cargo build, test, and audit execution for comprehensive crate analysis
- **Dependency Analysis**: Deep analysis of crate dependencies and their relationships
- **Batch Processing**: Efficient processing of multiple crates with configurable batch sizes
- **Data Export**: Structured output in JSON format for further analysis
- **RAG Cache**: Intelligent caching with Rule Zero policies and architectural patterns
- **Docker Support**: Containerized deployment with optimized Docker configurations

## Installation

```bash
# Clone the repository
git clone https://github.com/Superuser666-Sigil/SigilDERG-Data_Production.git
cd SigilDERG-Data_Production

# Install in development mode
pip install -e .

# Install additional dependencies for AI processing
pip install -r requirements-crawl4ai.txt
```

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

### Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test module
pytest tests/test_main_integration.py

# Run with coverage
pytest --cov=rust_crate_pipeline tests/
```

### Code Quality

```bash
# Format code
black rust_crate_pipeline/

# Sort imports
isort rust_crate_pipeline/

# Type checking
pyright rust_crate_pipeline/
```

## Requirements

- Python 3.8+
- Rust toolchain (for cargo testing)
- Git (for GitHub API access)
- Internet connection (for web scraping and API calls)

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