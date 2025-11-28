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
black --check sigil_pipeline tests
isort --check-only sigil_pipeline tests
flake8 sigil_pipeline tests
pyright sigil_pipeline

# 2. Tests
pytest tests/ -v --cov=sigil_pipeline --cov-report=xml

# 3. Security
safety check --json
bandit -r sigil_pipeline -f json -o bandit-report.json
```

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
