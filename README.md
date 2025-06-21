# Rust Crate Pipeline

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI Package](https://img.shields.io/badge/PyPI-v1.5.1-green.svg)](https://pypi.org/project/rust-crate-pipeline/)
[![Docker Ready](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://docker.com/)
[![Rule Zero Compliant](https://img.shields.io/badge/Rule%20Zero-Compliant-gold.svg)](https://github.com/Superuser666-Sigil/SigilDERG-Data_Production/blob/main/SYSTEM_AUDIT_REPORT.md)

A production-ready, Rule Zero-compliant pipeline for comprehensive Rust crate analysis, featuring **AI-powered insights**, **enhanced web scraping with Crawl4AI**, dependency mapping, and automated data enrichment. Designed for researchers, developers, and data scientists studying the Rust ecosystem.

**🆕 New in v1.5.1**: Model path standardization, improved GGUF configuration consistency, and enhanced Rule Zero alignment.

📦 **Available on PyPI:** [rust-crate-pipeline](https://pypi.org/project/rust-crate-pipeline/)

## 🚀 Quick Start

### 1. Installation

#### From PyPI (Recommended)

```bash
pip install rust-crate-pipeline
```

For the latest version, visit: [rust-crate-pipeline on PyPI](https://pypi.org/project/rust-crate-pipeline/)

#### From Source

```bash
git clone https://github.com/Superuser666-Sigil/SigilDERG-Data_Production.git
cd SigilDERG-Data_Production
pip install -e .
```

#### Development Installation

```bash
git clone https://github.com/Superuser666-Sigil/SigilDERG-Data_Production.git
cd SigilDERG-Data_Production
pip install -e ".[dev]"
```

### 2. GitHub Token Setup

The pipeline requires a GitHub Personal Access Token for optimal performance:

```bash
# Interactive setup (Linux/Unix)
chmod +x setup_github_token.sh
./setup_github_token.sh

# Manual setup
export GITHUB_TOKEN="your_token_here"
echo 'export GITHUB_TOKEN="your_token_here"' >> ~/.bashrc

# Verify setup
python3 check_github_token.py
```

**Get your token at**: [GitHub Settings](https://github.com/settings/tokens)  
**Required scopes**: `public_repo`, `read:user`

### 3. Basic Usage

```bash
# Standard mode
python3 -m rust_crate_pipeline

# Production mode (reduced warnings, optimized settings)
python3 run_production.py

# Process only 20 crates for testing
python3 -m rust_crate_pipeline --limit 20

# Skip AI processing for faster metadata-only collection
python3 -m rust_crate_pipeline --skip-ai --limit 50
```

### 4. Advanced Usage

```bash
# Enhanced web scraping with Crawl4AI (default in v1.5.0)
python3 -m rust_crate_pipeline --enable-crawl4ai --limit 20

# Disable Crawl4AI for basic scraping only
python3 -m rust_crate_pipeline --disable-crawl4ai --limit 20

# Custom Crawl4AI model configuration
python3 -m rust_crate_pipeline \
    --enable-crawl4ai \
    --crawl4ai-model "~/models/deepseek/deepseek-coder-6.7b-instruct.Q4_K_M.gguf" \
    --limit 10

# Sigil Protocol with enhanced scraping
python3 -m rust_crate_pipeline \
    --enable-sigil-protocol \
    --enable-crawl4ai \
    --skip-ai \
    --limit 5

# Custom configuration
python3 -m rust_crate_pipeline \
    --limit 100 \
    --batch-size 5 \
    --workers 2 \
    --log-level DEBUG \
    --output-dir ./results

# Process specific crates
python3 -m rust_crate_pipeline \
    --crate-list serde tokio actix-web reqwest \
    --output-dir ./specific_crates

# Use custom model and config
python3 -m rust_crate_pipeline \
    --model-path ./my-model.gguf \
    --config-file ./custom_config.json
```

## 🎯 Features

*Available in the latest version: [rust-crate-pipeline v1.5.1](https://pypi.org/project/rust-crate-pipeline/)*

### 🌐 Enhanced Web Scraping (New in v1.5.0)

- **Crawl4AI Integration**: Advanced web scraping with AI-powered content extraction
- **JavaScript Rendering**: Playwright-powered browser automation for dynamic content
- **Smart Content Analysis**: LLM-enhanced README and documentation parsing
- **Structured Data Extraction**: Intelligent parsing of docs.rs and technical documentation
- **Quality Scoring**: Automated content quality assessment and validation
- **Graceful Fallbacks**: Automatic degradation to basic scraping when needed

### 📊 Data Collection & Analysis

- **Multi-source metadata**: crates.io, GitHub, lib.rs integration
- **Dependency mapping**: Complete dependency graphs and analysis
- **Code extraction**: Automatic Rust code example extraction
- **Security scanning**: Vulnerability and security pattern analysis
- **Performance metrics**: Lines of code, complexity, API surface analysis

### 🤖 AI-Powered Enrichment

- **Smart categorization**: Automatic crate classification (Web, ML, Database, etc.)
- **Feature summarization**: AI-generated explanations and insights
- **Content optimization**: Intelligent README section preservation
- **Factual pairs**: Training data generation for fact verification

### ⚡ Production Features

- **Automatic GitHub token detection**: Seamless setup and validation
- **Smart rate limiting**: Respects GitHub API limits with intelligent backoff
- **Robust error handling**: Graceful degradation and comprehensive logging
- **Progress checkpointing**: Automatic saving for long-running processes
- **Docker ready**: Full container support with optimized configurations
- **Rule Zero Compliance**: Full transparency and audit trail support

## � Recent Updates

### Version 1.5.1 - Configuration Standardization (Latest)
- 🔧 **Model Path Consistency**: Standardized all configuration to use GGUF model paths (`~/models/deepseek/deepseek-coder-6.7b-instruct.Q4_K_M.gguf`)
- ⚖️ **Rule Zero Alignment**: Enhanced compliance with Rule Zero principles for transparency and validation
- 📝 **Documentation Updates**: Comprehensive updates to reflect proper model configuration practices
- 🧪 **Test Standardization**: Updated all test files to use consistent GGUF model paths
- 🚀 **CLI Consistency**: Ensured all CLI defaults and help text reflect correct model paths

### Version 1.5.0 - Enhanced Web Scraping
- 🚀 **Crawl4AI Integration**: Advanced web scraping with AI-powered content extraction
- 🌐 **JavaScript Rendering**: Playwright-powered browser automation for dynamic content
- 🧠 **LLM-Enhanced Parsing**: AI-powered README and documentation analysis
- 📊 **Structured Data Extraction**: Intelligent parsing of docs.rs and technical documentation
- ⚡ **Async Processing**: High-performance concurrent web scraping
- 🛡️ **Graceful Fallbacks**: Automatic degradation to basic scraping when needed

### Version 1.4.0 - Rule Zero Compliance
- 🏆 **Rule Zero Certification**: Complete alignment audit and compliance verification
- 🧪 **100% Test Coverage**: All 22 tests passing with comprehensive validation
- 🔄 **Thread-Free Architecture**: Pure asyncio implementation for better performance
- 📦 **PyPI Integration**: Official package availability with easy installation
- 🐳 **Docker Support**: Full containerization with production-ready configurations

*For complete version history, see [CHANGELOG.md](CHANGELOG.md)*

## �💻 System Requirements

### Minimum Requirements

- **Python**: 3.8+
- **Memory**: 4GB RAM
- **Storage**: 2GB free space
- **Network**: Stable internet connection

### Recommended Setup

- **Python**: 3.10+
- **Memory**: 8GB+ RAM
- **Storage**: 10GB+ free space (SSD preferred)
- **GitHub Token**: For enhanced API access (5000 vs 60 requests/hour)

### Dependencies

Core dependencies are automatically installed:

```bash
# Core functionality
requests>=2.28.0
requests-cache>=0.9.0
beautifulsoup4>=4.11.0
tqdm>=4.64.0

# AI and LLM processing
llama-cpp-python>=0.2.0
tiktoken>=0.4.0

# Enhanced web scraping (New in v1.5.0)
crawl4ai>=0.6.0
playwright>=1.49.0

# System utilities
psutil>=5.9.0
python-dateutil>=2.8.0
```

## ⚙️ Configuration & Usage

### Command Line Options

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--limit` | int | None | Limit number of crates to process |
| `--batch-size` | int | 10 | Crates processed per batch |
| `--workers` | int | 4 | Parallel workers for API requests |
| `--output-dir` | str | auto | Custom output directory |
| `--model-path` | str | default | Path to LLM model file |
| `--max-tokens` | int | 256 | Maximum tokens for LLM generation |
| `--checkpoint-interval` | int | 10 | Save progress every N crates |
| `--log-level` | str | INFO | Logging verbosity |
| `--skip-ai` | flag | False | Skip AI enrichment |
| `--skip-source-analysis` | flag | False | Skip source code analysis |
| `--enable-crawl4ai` | flag | True | Enable enhanced web scraping (default) |
| `--disable-crawl4ai` | flag | False | Disable Crawl4AI, use basic scraping |
| `--crawl4ai-model` | str | ~/models/deepseek/deepseek-coder-6.7b-instruct.Q4_K_M.gguf | GGUF model path for content analysis |
| `--enable-sigil-protocol` | flag | False | Enable Rule Zero compliance mode |
| `--sigil-mode` | str | enhanced | Sigil processing mode |
| `--crate-list` | list | None | Specific crates to process |
| `--config-file` | str | None | JSON configuration file |

### Production Mode

Production mode provides optimized settings with reduced warnings:

```bash
# Using production launcher
python3 run_production.py [OPTIONS]

# Using environment variable
PRODUCTION=true python3 -m rust_crate_pipeline

# Docker production mode
docker run -e PRODUCTION=true -e GITHUB_TOKEN="token" your-image
```

**Production optimizations:**

- Reduced retry attempts (3→2) to minimize warnings
- Smart GitHub API rate limiting with proactive pausing
- Enhanced logging with appropriate levels
- Optimized timeout and backoff strategies

### Configuration Files

Create a JSON configuration file for custom settings:

```json
{
    "max_retries": 2,
    "batch_size": 10,
    "github_min_remaining": 500,
    "cache_ttl": 7200,
    "model_path": "~/models/your-model.gguf",    "enable_crawl4ai": true,
    "crawl4ai_model": "~/models/deepseek/deepseek-coder-6.7b-instruct.Q4_K_M.gguf",
    "crawl4ai_timeout": 30
}
```

Use with: `python3 -m rust_crate_pipeline --config-file config.json`

## 🐳 Docker Deployment

### Using Docker Compose (Recommended)

```bash
# Set up environment
echo "GITHUB_TOKEN=your_token_here" > .env

# Run with compose
docker-compose up -d

# Monitor logs
docker-compose logs -f
```

### Manual Docker Commands

```bash
# Build image
docker build -t rust-crate-pipeline .

# Run container
docker run -e GITHUB_TOKEN="your_token" \
           -e PRODUCTION=true \
           -v $(pwd)/output:/app/output \
           rust-crate-pipeline

# Background execution
docker run -d --name pipeline \
           -e GITHUB_TOKEN="your_token" \
           rust-crate-pipeline
```

### Docker Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GITHUB_TOKEN` | GitHub Personal Access Token | Required |
| `PRODUCTION` | Enable production mode | `false` |
| `PYTHONUNBUFFERED` | Force unbuffered output | `1` |

## 📊 Output & Data Format

### Output Structure

```text
output/
├── enriched_crates_YYYYMMDD_HHMMSS.json    # Main results
├── metadata_YYYYMMDD_HHMMSS.json           # Raw metadata
├── errors_YYYYMMDD_HHMMSS.log              # Error log
└── checkpoints/
    └── checkpoint_N.json                    # Progress saves
```

### Data Schema

Each processed crate includes:

```json
{
    "name": "serde",
    "version": "1.0.193",
    "description": "A generic serialization/deserialization framework",
    "repository": "https://github.com/serde-rs/serde",
    "downloads": 50000000,
    "github_stars": 8500,
    "category": "Serialization",
    "use_case": "Data serialization and deserialization",
    "feature_summary": "Compile-time serialization framework...",
    "dependencies": [...],
    "security_analysis": {...},
    "source_metrics": {...}
}
```

## 🔍 Monitoring & Troubleshooting

### Common Issues & Solutions

#### GitHub Token Problems

```bash
# Check token status
python3 check_github_token.py

# Common error: Rate limit warnings
[WARNING] GitHub API rate limit low: 60 remaining
# Solution: Set GITHUB_TOKEN environment variable

# Common error: Invalid token
[ERROR] GitHub token is invalid or expired
# Solution: Generate new token at https://github.com/settings/tokens
```

#### LLM Validation Retries

```bash
# Common warning: Validation failures
[WARNING] Validation failed on attempt 1/3. Retrying...
# Solution: Use production mode to reduce retry warnings
PRODUCTION=true python3 -m rust_crate_pipeline
```

#### Resource Issues

```bash
# Memory usage optimization
python3 -m rust_crate_pipeline --batch-size 3

# Disk space monitoring
df -h .  # Check available space

# Network timeout handling
python3 -m rust_crate_pipeline --log-level DEBUG
```

### Performance Monitoring

#### Processing Times (Typical)

- **Metadata only**: 2-3 seconds per crate
- **With AI enrichment**: 15-30 seconds per crate  
- **Full analysis**: 45-60 seconds per crate

#### Resource Usage

- **Memory**: 2-4GB during processing
- **Storage**: 10-50MB per crate (temporary files)
- **Network**: 1-5MB per crate (API calls)

#### Monitoring Commands

```bash
# Check process status
ps aux | grep rust_crate_pipeline

# Monitor resource usage
top -p $(pgrep -f rust_crate_pipeline)

# Check logs
tail -f pipeline.log

# Docker monitoring
docker stats pipeline
```

## 🚀 Deployment Guide

### SSH/Remote Server Deployment

```bash
# Background execution with logging
nohup python3 run_production.py > pipeline.log 2>&1 &

# Monitor progress
tail -f pipeline.log

# Check process
jobs
ps aux | grep rust_crate_pipeline
```

### Systemd Service (Linux)

Create `/etc/systemd/system/rust-crate-pipeline.service`:

```ini
[Unit]
Description=Rust Crate Data Pipeline
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/pipeline
Environment=GITHUB_TOKEN=your_token_here
Environment=PRODUCTION=true
ExecStart=/usr/bin/python3 run_production.py
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable rust-crate-pipeline
sudo systemctl start rust-crate-pipeline
sudo systemctl status rust-crate-pipeline
```

## 🏗️ Architecture

### Core Components

1. **CrateDataPipeline**: Main orchestration class that coordinates all processing
2. **LLMEnricher**: Handles AI-powered enrichment using local LLM models
3. **CrateAPIClient**: Manages API interactions with crates.io and fallback sources
4. **GitHubBatchClient**: Optimized GitHub API client with rate limiting
5. **SourceAnalyzer**: Analyzes source code metrics and complexity
6. **SecurityAnalyzer**: Checks for security vulnerabilities and patterns
7. **UserBehaviorAnalyzer**: Tracks community engagement and version adoption
8. **DependencyAnalyzer**: Builds and analyzes dependency relationships

### Processing Flow

```text
1. Crate Discovery → 2. Metadata Fetching → 3. AI Enrichment
        ↓                      ↓                    ↓
4. Source Analysis → 5. Security Scanning → 6. Community Analysis
        ↓                      ↓                    ↓
7. Dependency Mapping → 8. Data Aggregation → 9. Report Generation
```

### Project Structure

```text
rust_crate_pipeline/
├── __init__.py              # Package initialization
├── __main__.py              # Entry point for python -m execution
├── main.py                  # CLI interface and main execution logic
├── config.py                # Configuration classes and data models
├── pipeline.py              # Main orchestration and workflow management
├── ai_processing.py         # LLM integration and AI-powered enrichment
├── network.py               # API clients and HTTP request handling
├── analysis.py              # Source code, security, and dependency analysis
├── github_token_checker.py  # Token validation and setup
├── production_config.py     # Production optimizations
└── utils/                   # Utility functions
    ├── logging_utils.py     # Logging configuration and decorators
    └── file_utils.py        # File operations and disk management
```

## 🧪 API Usage

### Programmatic Usage

```python
from rust_crate_pipeline import CrateDataPipeline, PipelineConfig

# Create custom configuration
config = PipelineConfig(
    batch_size=5,
    max_tokens=512,
    model_path="/path/to/model.gguf"
)

# Initialize and run pipeline
pipeline = CrateDataPipeline(config)
pipeline.run()

# Or use individual components
from rust_crate_pipeline import LLMEnricher, SourceAnalyzer

enricher = LLMEnricher(config)
analyzer = SourceAnalyzer()
```

### Custom Processing

```python
# Process specific crates with custom options
pipeline = CrateDataPipeline(
    config,
    limit=50,
    crate_list=["serde", "tokio", "actix-web"],
    skip_ai=False,
    output_dir="./custom_analysis"
)
```

## 🔧 Development & Contributing

### Development Setup

```bash
# Clone and install
git clone https://github.com/Superuser666-Sigil/SigilDERG-Data_Production.git
cd SigilDERG-Data_Production
pip install -r requirements.txt

# Run tests
python3 test_optimizations.py
python3 test_token_integration.py

# Verify installation
python3 check_github_token.py
```

### Adding Features

1. Implement new analyzer in `analysis.py`
2. Add configuration options to `config.py`
3. Integrate with pipeline in `pipeline.py`
4. Add CLI arguments in `main.py`
5. Update tests and documentation

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Rust Community** for the excellent crates ecosystem
- **crates.io** for comprehensive API access
- **GitHub** for repository metadata and community data
- **Deepseek** for powerful code-focused language models
- **llama.cpp** team for efficient local inference

## 📞 Support

- **Issues**: Report bugs and request features
- **Documentation**: Complete guides and API reference
- **Community**: Join discussions and get help

---

## Ready to analyze the Rust ecosystem! 🦀✨

📦 **Get started today:** [Install from PyPI](https://pypi.org/project/rust-crate-pipeline/)

## 🛡️ Rule Zero Validation & Checkpointing (2025-06-21)

This project enforces Rule Zero rigor for all code and data changes. The following validation and checkpointing process was performed on **2025-06-21**:

- **DB Hash Validation:**
  - The canonical SQLite DB (`sigil_rag_cache.db`) was validated against its SHA256 hash (`sigil_rag_cache.hash`) using the script:
    ```bash
    python scripts/validate_db_hash.py --db sigil_rag_cache.db --expected-hash $(cat sigil_rag_cache.hash)
    ```
  - The pre-commit hook automatically reads the hash value and validates the DB before every commit.
- **Environment Metadata:**
  - Metadata was cached to the DB using `scripts/cache_env_metadata.py` for traceability.
- **Rule Zero Lookup Table:**
  - The Rule Zero quick lookup table was generated with `scripts/generate_rule_zero_lookup.py`.
- **Checkpoint Commit:**
  - All code, config, and uncommitted changes were committed with the message:
    > Rule Zero checkpoint: full codebase and config state as of 2025-06-21, including all dev branch uncommitted and untracked changes. Patch saved as rule_zero_checkpoint_devbranch_20250621.patch for traceability.
  - Patch file: `rule_zero_checkpoint_devbranch_20250621.patch`
  - Tag: `rule_zero_checkpoint_2025-06-21`
  - Branch: `dev` (pushed to remote)

**To repeat this process:**
1. Ensure all changes are staged.
2. Validate the DB hash:
   ```bash
   python scripts/validate_db_hash.py --db sigil_rag_cache.db --expected-hash $(cat sigil_rag_cache.hash)
   ```
3. Run environment and lookup scripts:
   ```bash
   python scripts/cache_env_metadata.py
   python scripts/generate_rule_zero_lookup.py
   ```
4. Commit and tag:
   ```bash
   git commit -am "Rule Zero checkpoint: ..."
   git tag rule_zero_checkpoint_YYYY-MM-DD
   git push origin dev --tags
   ```

This ensures full transparency, traceability, and repeatability in line with Rule Zero principles.
