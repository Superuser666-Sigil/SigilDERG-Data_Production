# Testing CI Locally

You have **three options** to test the CI workflow locally:

## Option 1: Local Test Script (Fastest - Recommended)

Run `test_ci_local.py` which executes the same commands as CI:

```bash
# Make sure dev dependencies are installed
pip install -e ".[dev]"

# Run the test script
python test_ci_local.py
```

**Pros:**
- Fast (no Docker needed)
- No setup required
- Immediate feedback

**Cons:**
- Doesn't test exact GitHub Actions environment
- Some steps (like codecov upload) are skipped

---

## Option 2: Using `act` (GitHub Actions Runner)

`act` runs GitHub Actions workflows locally using Docker.

### Installation

**Windows:**
```powershell
choco install act-cli
```

**macOS:**
```bash
brew install act
```

**Linux:**
Download from https://github.com/nektos/act/releases

### Prerequisites

- Docker Desktop must be installed and running
- Verify Docker: `docker ps`

### Usage

```bash
# List all workflows and jobs
act -l

# Run all workflows
act

# Run a specific job
act -j lint          # Run lint job only
act -j test          # Run test job only  
act -j security      # Run security job only

# Run with a specific event
act push              # Simulate push event
act pull_request      # Simulate PR event

# Use a larger Docker image (if needed)
act -P ubuntu-latest=catthehacker/ubuntu:act-latest
```

**Pros:**
- Closest match to actual GitHub Actions
- Tests the exact workflow file

**Cons:**
- Requires Docker
- Slower than local script
- Some actions may not work perfectly locally
- Matrix builds run sequentially

---

## Option 3: Manual Step-by-Step

Run each CI step manually:

```bash
# 1. Lint checks
black --check sigil_pipeline tests benches tools scripts
isort --check-only sigil_pipeline tests benches tools scripts
flake8 sigil_pipeline tests benches tools scripts
pyright sigil_pipeline

# 2. Tests
pytest tests/ -v --cov=sigil_pipeline --cov-report=xml

# 3. Security
pip freeze > requirements.freeze.txt
safety check --full-report -r requirements.freeze.txt
bandit -r sigil_pipeline tools scripts benches -f json -o bandit-report.json
```

> **Note:** The `safety check` command scans a frozen requirements file for known 
> vulnerabilities. In `test_ci_local.py`, this is treated as advisory (soft-fail) 
> to avoid blocking local development on transient vulnerability database issues.

---

## Recommended Workflow

1. **Quick checks**: Use `test_ci_local.py` for fast feedback during development
2. **Before pushing**: Use `act` to verify GitHub Actions compatibility
3. **Final verification**: Push to a branch and check actual GitHub Actions run

---

## Troubleshooting

### `act` Issues

**Docker not running:**
- Start Docker Desktop
- Verify: `docker ps`

**Permission errors (Linux):**
```bash
sudo usermod -aG docker $USER
# Then log out and back in
```

**Large image downloads:**
- First run downloads Docker images (~1GB)
- Subsequent runs are faster

### Local Script Issues

**Missing dependencies:**
```bash
pip install -e ".[dev,test]"
pip install safety bandit
```

**Python version:**
- Ensure Python 3.12+ is installed
- Check: `python --version`

---

## Current CI Status

After running the test script, fix any issues found:
- Formatting issues: Run `black sigil_pipeline tests` and `isort sigil_pipeline tests`
- Type checking issues: Fix pyright errors reported
- Test failures: Fix failing tests

Run `python test_ci_local.py` again after fixing these issues.

---

## Test File Reference

### New Test Files (v2.2.0)

The following test files were added to improve coverage from 52% to 75%:

| Test File | Lines | Description |
|-----------|-------|-------------|
| `test_api_tracker.py` | ~550 | Tests for API evolution tracking, change detection |
| `test_usage_analyzer.py` | ~300 | Tests for static API usage analysis |
| `test_telemetry.py` | ~280 | Tests for OpenTelemetry tracing integration |
| `test_dataset_splitter.py` | ~490 | Tests for train/val splitting by source |
| `test_cli_ecosystem.py` | ~370 | Tests for CLI pipeline orchestrator |
| `test_converters.py` | ~280 | Tests for format conversion utilities |

### Expanded Test Files (v2.2.0)

| Test File | New Tests | Description |
|-----------|-----------|-------------|
| `test_ast_patterns.py` | ~40 | Added tests for `APIEntity`, `extract_all_api_entities`, `check_function_in_code` |
| `test_utils.py` | ~22 | Added tests for `get_installed_toolchains`, `find_best_toolchain`, `parse_crate_info` |
| `test_filter.py` | ~30 | Added tests for `is_api_properly_used`, `static_analysis_rust_code` |
| `test_task_generator.py` | ~28 | Added tests for explanation tasks, task type selection |

### Running Specific Test Categories

```bash
# Run only the new test files
pytest tests/test_api_tracker.py tests/test_usage_analyzer.py tests/test_telemetry.py \
       tests/test_dataset_splitter.py tests/test_cli_ecosystem.py tests/test_converters.py -v

# Run API-related tests
pytest tests/test_api_tracker.py tests/test_usage_analyzer.py -v

# Run AST and pattern tests
pytest tests/test_ast_patterns.py tests/test_filter.py -v

# Run task generation tests
pytest tests/test_task_generator.py -v

# Run with verbose coverage for specific module
pytest tests/test_telemetry.py --cov=sigil_pipeline.telemetry --cov-report=term-missing -v
```

### Test Fixtures

Common fixtures are defined in `tests/conftest.py`:

- `sample_crate_dir` - Creates a temporary crate directory with Cargo.toml
- `sample_rust_code` - Provides sample Rust code for AST testing
- `sample_config` - Returns a PipelineConfig with test defaults

Example usage:
```python
def test_my_function(sample_crate_dir, sample_config):
    """Test using shared fixtures."""
    result = analyze_crate(sample_crate_dir, sample_config)
    assert result is not None
```
