# Crawl4AI Integration Guide

## Overview

Version 1.5.0 introduces comprehensive Crawl4AI integration for enhanced web scraping capabilities. This document provides detailed information about the integration, configuration, and usage.

## Features

### Advanced Web Scraping
- **JavaScript Rendering**: Full Playwright browser automation for dynamic content
- **LLM-Enhanced Content Analysis**: AI-powered parsing of README files and documentation
- **Structured Data Extraction**: Intelligent extraction from docs.rs and technical documentation
- **Quality Scoring**: Automated assessment of content quality and relevance
- **Async Processing**: High-performance concurrent scraping with proper resource management

### Graceful Fallbacks
- **Automatic Degradation**: Falls back to basic scraping when Crawl4AI is unavailable
- **Error Handling**: Comprehensive exception management for web scraping failures
- **Configuration Flexibility**: Easy switching between enhanced and basic modes

## Configuration

### CLI Options

```bash
# Enable enhanced scraping (default)
python -m rust_crate_pipeline --enable-crawl4ai

# Disable enhanced scraping
python -m rust_crate_pipeline --disable-crawl4ai

# Custom LLM model for content analysis
python -m rust_crate_pipeline --crawl4ai-model "~/models/llama/llama-2-7b-chat.Q4_K_M.gguf"

# Combined with other options
python -m rust_crate_pipeline \
    --enable-crawl4ai \
    --crawl4ai-model "~/models/deepseek/deepseek-coder-6.7b-instruct.Q4_K_M.gguf" \
    --limit 10
```

### Configuration File

```json
{
    "enable_crawl4ai": true,
    "crawl4ai_model": "~/models/deepseek/deepseek-coder-6.7b-instruct.Q4_K_M.gguf",
    "crawl4ai_timeout": 30
}
```

### Programmatic Configuration

```python
from rust_crate_pipeline.config import PipelineConfig

# Enable Crawl4AI with custom settings
config = PipelineConfig(
    enable_crawl4ai=True,
    crawl4ai_model="~/models/deepseek/deepseek-coder-6.7b-instruct.Q4_K_M.gguf",
    crawl4ai_timeout=30
)
```

## Usage Examples

### Standard Pipeline

```python
from rust_crate_pipeline import CrateDataPipeline
from rust_crate_pipeline.config import PipelineConfig

# Configure with Crawl4AI
config = PipelineConfig(enable_crawl4ai=True)
pipeline = CrateDataPipeline(config)

# Enhanced scraper is automatically initialized
print(f"Enhanced scraping available: {pipeline.enhanced_scraper is not None}")
```

### Sigil Protocol Pipeline

```python
from sigil_enhanced_pipeline import SigilCompliantPipeline
from rust_crate_pipeline.config import PipelineConfig

# Rule Zero compliant with enhanced scraping
config = PipelineConfig(
    enable_crawl4ai=True,
    crawl4ai_model="~/models/deepseek/deepseek-coder-6.7b-instruct.Q4_K_M.gguf"
)

pipeline = SigilCompliantPipeline(config, skip_ai=True, limit=5)
```

### Direct Enhanced Scraping

```python
from enhanced_scraping import EnhancedScraper, CrateDocumentationScraper
import asyncio

# Basic enhanced scraper
scraper = EnhancedScraper(enable_crawl4ai=True)

# Specialized crate documentation scraper
crate_scraper = CrateDocumentationScraper(enable_crawl4ai=True)

# Async scraping example
async def scrape_example():
    result = await scraper.scrape_documentation(
        "https://docs.rs/serde/latest/serde/", 
        "api"
    )
    print(f"Quality Score: {result.quality_score}")
    print(f"Extraction Method: {result.extraction_method}")
    return result

# Run the example
result = asyncio.run(scrape_example())
```

## Technical Details

### Architecture

```
┌─────────────────────┐
│   Pipeline Entry    │
│  (main.py/CLI)      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Configuration      │
│  (PipelineConfig)   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Enhanced Scraper   │
│  (EnhancedScraper)  │
└──────────┬──────────┘
           │
     ┌─────┴─────┐
     ▼           ▼
┌─────────┐ ┌─────────────┐
│Crawl4AI │ │Basic Scraper│
│ (AI)    │ │ (Fallback)  │
└─────────┘ └─────────────┘
```

### Dependencies

- **crawl4ai>=0.6.0**: Core enhanced scraping functionality
- **playwright>=1.49.0**: Browser automation for JavaScript rendering
- **asyncio**: Async processing support
- **aiohttp**: HTTP client for async requests

### Quality Scoring Algorithm

The quality scoring system evaluates scraped content based on:

1. **Content Length**: Adequate amount of text content
2. **Structure**: Presence of headings, lists, and formatted content
3. **Code Examples**: Availability of code snippets and examples
4. **Documentation Completeness**: API documentation, usage examples
5. **Metadata Quality**: Proper titles, descriptions, and structured data

Scores range from 0.0 to 1.0, with higher scores indicating better content quality.

## Error Handling

### Graceful Degradation

```python
# The system automatically falls back to basic scraping
try:
    # Attempt Crawl4AI scraping
    result = await enhanced_scraper.scrape_documentation(url, doc_type)
    if result.extraction_method == "crawl4ai":
        print("✅ Enhanced scraping successful")
    else:
        print("⚠️ Fell back to basic scraping")
except Exception as e:
    print(f"❌ Scraping failed: {e}")
```

### Common Issues and Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| `ModuleNotFoundError: crawl4ai` | Crawl4AI not installed | `pip install crawl4ai` |
| Browser automation fails | Playwright browsers not installed | `python -m playwright install chromium` |
| Timeout errors | Network or site issues | Increase `crawl4ai_timeout` setting |
| Memory issues | Large pages or many concurrent requests | Reduce batch size or limit concurrent requests |

## Performance Optimization

### Best Practices

1. **Batch Processing**: Process crates in small batches (5-10) to avoid overwhelming target sites
2. **Timeout Management**: Set appropriate timeouts (30s default) for slow-loading pages
3. **Resource Limits**: Monitor memory usage when processing large documentation sites
4. **Rate Limiting**: Respect target site rate limits and robots.txt

### Monitoring

```python
import logging

# Enable debug logging for Crawl4AI operations
logging.basicConfig(level=logging.DEBUG)

# Monitor quality scores
results = []
async def monitor_scraping():
    result = await scraper.scrape_documentation(url, doc_type)
    results.append(result.quality_score)
    avg_quality = sum(results) / len(results)
    print(f"Average quality score: {avg_quality:.2f}")
```

## Rule Zero Compliance

The Crawl4AI integration maintains full Rule Zero compliance:

- **Transparency**: All scraping operations are logged with full audit trails
- **Validation**: Quality scores provide objective measures of content reliability
- **Alignment**: Integration follows established architecture patterns
- **Adaptability**: Graceful fallbacks ensure system resilience

### Audit Trail Example

```
2025-06-20 10:30:15 - INFO - ✅ Crawl4AI crawler initialized successfully
2025-06-20 10:30:16 - INFO - Scraping: https://docs.rs/serde/latest/serde/
2025-06-20 10:30:18 - INFO - Crawl4AI extraction successful (Quality: 0.85)
2025-06-20 10:30:18 - DEBUG - Extracted 2,345 chars, 15 code examples, 8 sections
```

## Testing

### Integration Tests

```bash
# Run Crawl4AI integration tests
python tests/test_crawl4ai_integration.py

# Run demo and validation
python tests/test_crawl4ai_demo.py
```

### Unit Tests

```python
import pytest
from enhanced_scraping import EnhancedScraper

@pytest.mark.asyncio
async def test_crawl4ai_integration():
    scraper = EnhancedScraper(enable_crawl4ai=True)
    result = await scraper.scrape_documentation(
        "https://httpbin.org/html", 
        "test"
    )
    assert result is not None
    assert result.quality_score > 0
```

## Troubleshooting

### Debug Mode

```bash
# Enable verbose logging
python -m rust_crate_pipeline \
    --enable-crawl4ai \
    --log-level DEBUG \
    --limit 1
```

### Disable Crawl4AI

If you encounter issues, you can always disable enhanced scraping:

```bash
# Use basic scraping only
python -m rust_crate_pipeline --disable-crawl4ai
```

### Browser Setup Issues

```bash
# Install Playwright browsers manually
python -m playwright install chromium
python -m playwright install-deps chromium
```

## Future Enhancements

Planned improvements for future releases:

- **Multi-browser Support**: Firefox and Safari browser engines
- **Custom Extraction Rules**: User-defined content extraction patterns  
- **Caching Strategy**: Intelligent caching of scraped content
- **Performance Metrics**: Detailed timing and resource usage analytics
- **Site-specific Optimizations**: Specialized extractors for popular documentation sites

---

For more information, see the main [README.md](../README.md) and [CHANGELOG.md](../CHANGELOG.md).
