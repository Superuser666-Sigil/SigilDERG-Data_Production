# Contributing to SigilDERG-Data_Production

Thank you for your interest in contributing to Sigil Pipeline! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Code Standards](#code-standards)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Commit Message Format](#commit-message-format)
- [Reporting Issues](#reporting-issues)

---

## Code of Conduct

This project adheres to a code of conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior to the maintainer.

---

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally
3. Set up the development environment (see below)
4. Create a feature branch from `main`
5. Make your changes
6. Run tests and quality checks
7. Submit a pull request

---

## Development Setup

### Prerequisites

- **Python 3.12+** (required - we use modern syntax)
- **Rust toolchain** (for testing cargo integrations)
- **Git**

### Installation

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/SigilDERG-Data_Production.git
cd SigilDERG-Data_Production

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install in development mode with all dependencies
pip install -e ".[dev,test,datasets]"

# Install pre-commit hooks (recommended)
pre-commit install

# Verify installation
python -c "from sigil_pipeline import config; print('Installation successful!')"
```

### IDE Setup

We recommend using **VS Code** or **PyCharm** with the following extensions:

- **Python** (for IntelliSense)
- **Pylance** (for type checking)
- **Black Formatter** (for auto-formatting)
- **isort** (for import sorting)

---

## Code Standards

### Python Version

**Python 3.12+ is required.** We use modern Python syntax:

```python
# ✅ GOOD - Modern Python 3.12 syntax
def process(items: list[str], config: dict[str, int] | None = None) -> dict[str, str]:
    ...

# ❌ BAD - Legacy typing module syntax
from typing import List, Dict, Optional
def process(items: List[str], config: Optional[Dict[str, int]] = None) -> Dict[str, str]:
    ...
```

### Code Formatting

- **Formatter**: `black` (line length 88)
- **Import Sorting**: `isort` (black profile)
- **Linting**: `flake8` (max-line-length 120)
- **Type Checking**: `pyright` (standard mode)

Run all checks:

```bash
# Run the local CI script
python test_ci_local.py

# Or run individually:
black --check sigil_pipeline tests
isort --check-only sigil_pipeline tests
flake8 sigil_pipeline tests
pyright sigil_pipeline
```

### Docstrings

All public functions, classes, and modules must have docstrings:

```python
def analyze_crate(crate_dir: Path, config: PipelineConfig) -> CrateAnalysisReport:
    """
    Run all static analysis tools on a crate.

    Args:
        crate_dir: Path to the extracted crate directory
        config: Pipeline configuration with analysis settings

    Returns:
        CrateAnalysisReport containing all analysis results

    Raises:
        ValueError: If crate_dir does not exist
        RuntimeError: If cargo is not available
    """
    ...
```

### Type Hints

- All function parameters and return types must be annotated
- Use `| None` instead of `Optional[T]`
- Use built-in generics (`list`, `dict`, `tuple`) instead of `typing` module versions

---

## Testing

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=sigil_pipeline --cov-report=term --cov-report=html

# Run specific test file
pytest tests/test_analyzer.py -v

# Run tests matching a pattern
pytest tests/ -v -k "test_clippy"
```

### Writing Tests

- Place tests in the `tests/` directory
- Name test files `test_<module>.py`
- Name test functions `test_<functionality>`
- Use pytest fixtures for common setup
- Mock external dependencies (cargo, network)

```python
# Example test structure
import pytest
from unittest.mock import patch, AsyncMock

from sigil_pipeline.analyzer import run_clippy

@pytest.mark.asyncio
async def test_run_clippy_returns_results(sample_crate_dir):
    """Test that run_clippy returns valid ClippyResult."""
    with patch("sigil_pipeline.analyzer.run_command_async", new_callable=AsyncMock) as mock:
        mock.return_value = MockResult(stdout="...", returncode=0)
        result = await run_clippy(sample_crate_dir)
    
    assert result.success is True
    assert result.warning_count >= 0
```

### Test Coverage

We aim for **90%+ test coverage**. Current coverage: **75%** (as of v2.2.0). Check coverage with:

```bash
pytest tests/ --cov=sigil_pipeline --cov-report=html
# Open htmlcov/index.html in browser
```

### Test Module Coverage

The test suite comprehensively covers all major modules:

| Module | Test File | Description | Coverage |
|--------|-----------|-------------|----------|
| `api_tracker.py` | `test_api_tracker.py` | API evolution tracking | 79% |
| `usage_analyzer.py` | `test_usage_analyzer.py` | Static usage analysis | 89% |
| `telemetry.py` | `test_telemetry.py` | OpenTelemetry tracing | 77% |
| `dataset_splitter.py` | `test_dataset_splitter.py` | Train/val splitting | 98% |
| `cli/ecosystem.py` | `test_cli_ecosystem.py` | CLI orchestrator | 93% |
| `converters.py` | `test_converters.py` | Format conversion | 63% |
| `ast_patterns.py` | `test_ast_patterns.py` | AST extraction | 78% |
| `utils.py` | `test_utils.py` | Utility functions | 82% |
| `filter.py` | `test_filter.py` | Quality filtering | 89% |
| `task_generator.py` | `test_task_generator.py` | Task generation | 80% |
| `analyzer.py` | `test_analyzer.py` | Crate analysis | 81% |
| `config.py` | `test_config.py` | Configuration | 99% |
| `environment.py` | `test_environment.py` | Environment detection | 91% |
| `format_validator.py` | `test_format_validator.py` | Format validation | 83% |
| `prompt_templates.py` | `test_prompt_templates.py` | Prompt generation | 92% |

#### Running Specific Test Categories

```bash
# API and tracking tests
pytest tests/test_api_tracker.py tests/test_usage_analyzer.py -v

# AST and pattern tests
pytest tests/test_ast_patterns.py tests/test_filter.py -v

# Task generation tests
pytest tests/test_task_generator.py -v

# Telemetry and observability tests
pytest tests/test_telemetry.py -v

# Integration tests
pytest tests/test_ecosystem_integration.py -v

# Property-based tests
pytest tests/test_properties.py -v --hypothesis-show-statistics
```

---

## Pull Request Process

### Before Submitting

1. **Update your branch** with the latest `main`:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run all quality checks**:
   ```bash
   python test_ci_local.py
   ```

3. **Update documentation** if you changed functionality

4. **Add tests** for new features or bug fixes

### PR Requirements

- [ ] All CI checks pass
- [ ] Test coverage maintained or improved
- [ ] Code follows project style guidelines
- [ ] Documentation updated (if applicable)
- [ ] Commit messages follow format (see below)
- [ ] PR description explains changes

### Review Process

1. Submit PR against `main` branch
2. Automated CI runs (tests, lint, security scans)
3. Maintainer reviews code
4. Address feedback (if any)
5. Maintainer approves and merges

---

## Commit Message Format

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types

| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Formatting, no code change |
| `refactor` | Code restructuring |
| `test` | Adding/updating tests |
| `chore` | Maintenance tasks |
| `perf` | Performance improvement |
| `security` | Security fix |

### Examples

```bash
feat(analyzer): add cargo-deny integration for security auditing

fix(crawler): handle rate limiting from crates.io API

docs(readme): add Phase-2 instruct mode examples

test(filter): add property-based tests for size filters

security(crawler): add symlink attack protection in tarfile extraction
```

---

## Reporting Issues

### Bug Reports

Please include:

1. **Description**: Clear summary of the bug
2. **Steps to Reproduce**: Minimal steps to trigger the bug
3. **Expected Behavior**: What should happen
4. **Actual Behavior**: What actually happens
5. **Environment**: Python version, OS, package version
6. **Logs/Errors**: Relevant error messages or logs

### Feature Requests

Please include:

1. **Use Case**: Why is this feature needed?
2. **Proposed Solution**: How should it work?
3. **Alternatives**: Other approaches considered
4. **Additional Context**: Examples, mockups, etc.

---

## Security Vulnerabilities

**Do NOT create public issues for security vulnerabilities.**

Please see [SECURITY.md](SECURITY.md) for responsible disclosure instructions.

---

## Questions?

- Open a [Discussion](https://github.com/Superuser666-Sigil/SigilDERG-Data_Production/discussions)
- Check existing issues for similar questions
- Review the [documentation](docs/)

---

Thank you for contributing to Sigil Pipeline! 🚀


