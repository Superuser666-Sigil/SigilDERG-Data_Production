# Runbook: Troubleshooting

## Overview

This runbook covers diagnosing and resolving common issues with the Sigil Pipeline.

## Quick Diagnostics

### 0. Run Test Suite First

Before investigating complex issues, verify the pipeline components work correctly:

```bash
# Quick smoke test (fast)
pytest tests/test_config.py tests/test_filter.py -v --tb=short

# Full test suite with coverage
pytest --cov=sigil_pipeline --cov-report=term-missing

# Test specific components
pytest tests/test_ast_patterns.py -v      # AST extraction issues
pytest tests/test_utils.py -v             # Toolchain/crate utilities
pytest tests/test_api_tracker.py -v       # API evolution tracking
pytest tests/test_cli_ecosystem.py -v     # CLI orchestration
```

**Note:** The test suite has 672 tests covering 75% of the codebase. If tests pass but the pipeline still fails, the issue is likely environmental (network, permissions, disk space) rather than a code bug.

### 1. Check System Status

```bash
# Python environment
python --version
pip list | grep sigil

# Rust toolchain
rustup show
cargo --version

# Network connectivity
curl -I https://crates.io 2>/dev/null | head -1
```

### 2. Check Logs

```bash
# Recent errors
grep -i "error" logs/pipeline_*.log | tail -50

# Recent warnings
grep -i "warning" logs/pipeline_*.log | tail -50

# Analysis results
ls -la logs/analysis_*/
```

## Common Issues

### Issue: Pipeline Hangs

**Symptoms:**
- No progress for extended period
- CPU at 0%

**Diagnosis:**

```bash
# Check for deadlocks
ps aux | grep python
strace -p <PID> -e trace=write 2>&1 | head

# Check network connections
netstat -an | grep ESTABLISHED
```

**Resolution:**

1. Check if waiting on network:
   - Verify crates.io is accessible
   - Check for rate limiting

2. Check if waiting on cargo:
   - Some crates take long to compile
   - Increase timeout or skip crate

3. Force restart from checkpoint

### Issue: Rate Limiting (429 Errors)

**Symptoms:**
- Repeated "429 Too Many Requests" in logs
- Slow progress

**Diagnosis:**

```bash
grep "429" logs/pipeline_*.log
```

**Resolution:**

1. Rate limiting is already built in (1 req/sec)
2. If still hitting limits, reduce concurrency:
   ```bash
   python -m sigil_pipeline.main --max-threads 1 ...
   ```
3. Wait 1-2 hours before retrying

### Issue: Out of Memory

**Symptoms:**
- Process killed by OOM killer
- "MemoryError" in logs

**Diagnosis:**

```bash
# Check memory usage
dmesg | grep -i oom
free -h
```

**Resolution:**

1. Reduce max_threads
2. Process fewer crates at once
3. Increase system swap
4. Use Docker with memory limits

### Issue: Cargo Compilation Failures

**Symptoms:**
- Many crates failing analysis
- "error[E0xxx]" in analysis logs

**Diagnosis:**

```bash
ls -la logs/analysis_*/
cat logs/analysis_*/serde_clippy.log
```

**Resolution:**

1. Check Rust toolchain version:
   ```bash
   rustup update stable
   ```

2. Check for missing system dependencies:
   ```bash
   # On Ubuntu/Debian
   apt install build-essential pkg-config libssl-dev
   ```

3. Some crates are platform-specific - skip them

### Issue: Toolchain Selection Issues

**Symptoms:**
- Pipeline fails with "toolchain not found" errors.

**Diagnosis:**

```bash
# Check installed toolchains
rustup toolchain list

# Verify requested version exists
rustup toolchain list | grep "1.76.0"
```

**Resolution:**

```bash
# Install missing toolchain
rustup install 1.76.0

# Or use stable as fallback
# The pipeline automatically falls back to stable if requested version not found
```

### Issue: Pre-Filter Rejections

**Symptoms:**
- Code rejected with "Static analysis failed" before Clippy runs.

**Diagnosis:**
- Check for syntax errors: mismatched brackets, unclosed quotes
- Verify function signatures match expected format
- Check if required APIs are used (not just in comments)

**Resolution:**
- Pre-filters catch obvious errors early
- Review rejection logs for specific validation failures
- Pre-filters can be disabled if causing false positives

### Issue: Files Filtered as "Test Files" Despite Being Library Code

**Symptoms:**
- Crate shows "0/N files passed filters"
- Files contain inline unit tests with `#[cfg(test)]`
- Production code is being filtered out

**Diagnosis:**

```bash
# Run with debug logging to see filter decisions
python -m sigil_pipeline.main --crates <crate_name> --log-level DEBUG

# Check the test ratio (should be <50% for library files)
python -c "
content = open('path/to/lib.rs').read()
lines = content.split('\n')
test_lines = sum(1 for i, line in enumerate(lines) 
                 if '#[cfg(test)]' in line or i > lines.index('#[cfg(test)]') 
                 if '#[cfg(test)]' in content else 0)
print(f'Test ratio: {test_lines/len(lines):.1%}')
"
```

**Root Cause:**
- Rust idiomatically includes unit tests inline with `#[cfg(test)]` modules
- As of v2.5.0, the pipeline uses a 50% threshold - files are only filtered if more than half the code is tests

**Resolution:**
1. **Verify pipeline version is 2.5.0+** (includes ADR-012 fix):
   ```bash
   python -c "import sigil_pipeline; print(sigil_pipeline.__version__)"
   ```

2. **If on older version**, update:
   ```bash
   pip install -e .
   ```

3. **Check debug logs** for test ratio:
   ```bash
   grep "test code" logs/pipeline_*.log
   # Shows: "Filtering file.rs: 60.0% test code (120/200 lines)"
   ```

**Related:**
- [ADR-012: Inline Test Detection Threshold](../adr/ADR-012-inline-test-detection-threshold.md)

### Issue: Checkpoint Corruption

**Symptoms:**
- "JSONDecodeError" when resuming
- Invalid checkpoint state

**Diagnosis:**

```bash
cat output/checkpoint.json | python -m json.tool
```

**Resolution:**

1. Delete corrupt checkpoint and restart:
   ```bash
   rm output/checkpoint.json
   ```

2. Or restore from backup (if available)

### Issue: Low Quality Output

**Symptoms:**
- Many samples with short/empty code
- High filter rejection rate

**Diagnosis:**

```bash
# Check filter breakdown
cat output/metrics.json | python -m json.tool

# Sample some outputs
head -10 output/dataset.jsonl | python -c "
import json, sys
for line in sys.stdin:
    s = json.loads(line)
    print(f'Prompt len: {len(s[\"prompt\"])}, Gen len: {len(s[\"gen\"])}')
"
```

**Resolution:**

1. Adjust filter thresholds:
   - Increase max_bad_code_warnings
   - Disable strict license checking

2. Use more lenient config for exploration

### Issue: Missing Dependencies

**Symptoms:**
- ImportError on startup
- "Module not found" errors

**Diagnosis:**

```bash
pip check
pip list | grep -E "(sigil|hypothesis|structlog)"
```

**Resolution:**

```bash
# Reinstall with all dependencies
pip install -e ".[all]"

# Or specific extras
pip install -e ".[datasets,dev]"
```

### Issue: Stale Analysis Cache

**Symptoms:**
- Analysis results don't reflect recent code changes
- Unexpected cached results from previous runs

**Diagnosis:**

```bash
# Check cache directory
ls -la .cache/analysis/
```

**Resolution:**

1. Clear the analysis cache:
   ```bash
   rm -rf .cache/analysis/
   ```

2. Or disable caching in config:
   ```python
   enable_analysis_cache = False
   ```

### Issue: Reproducibility Audit Failure

**Symptoms:**
- Cannot reproduce previous results
- Toolchain version mismatch suspected

**Diagnosis:**

```bash
# Check environment fingerprint from previous run
cat output/environment.json | python -m json.tool

# Compare with current environment
python -c "
from sigil_pipeline.environment import capture_environment
import json
fp = capture_environment()
print(json.dumps(fp.to_dict(), indent=2))
"
```

**Resolution:**

1. Compare `environment.json` from original run with current:
   - `rustc_version` should match exactly
   - `cargo_version` should match
   - Key dependencies (tree-sitter, etc.) should match

2. If toolchain differs:
   ```bash
   rustup install 1.XX.0
   rustup default 1.XX.0
   ```

3. Ensure prompt seed is set explicitly in config:
   ```python
   prompt_seed = 12345  # Use seed from original run
   ```

### Issue: Prometheus Metrics Not Exported

**Symptoms:**
- `metrics.prom` file not created
- Grafana/monitoring can't scrape metrics

**Diagnosis:**

```bash
# Check config
grep "prometheus" config.json

# Check output directory
ls -la output/*.prom
```

**Resolution:**

1. Enable Prometheus output in config:
   ```python
   enable_prometheus_output = True
   prometheus_output_path = "output/metrics.prom"
   ```

2. Verify output path is writable:
   ```bash
   touch output/metrics.prom
   ```

### Issue: Structured Logging Not Working

**Symptoms:**
- Logs are plain text, not JSON
- structlog features not available

**Diagnosis:**

```bash
# Check if structlog is installed
pip show structlog
```

**Resolution:**

1. Install observability dependencies:
   ```bash
   pip install -e ".[observability]"
   ```

2. Enable structured logging in config:
   ```python
   enable_structured_logging = True
   json_logs = True  # For production JSON output
   ```

### Issue: Crate Rejected "No Documentation" Despite Having Docs

**Symptoms:**
- Legitimate crate rejected with "no documentation found"
- Crate has documented public API on docs.rs
- Examples: tree-sitter, similar binding crates

**Diagnosis:**

```bash
# Check the crate's Cargo.toml for custom source paths
cat crates/<crate_name>/Cargo.toml | grep -A2 "\[lib\]"

# Look for non-standard paths like:
# [lib]
# path = "binding_rust/lib.rs"
```

**Root Cause:**
- The crate uses a non-standard source layout specified in `Cargo.toml`
- Source code is not in `src/` but in a custom directory (e.g., `binding_rust/`)
- As of v2.5.0, the pipeline correctly parses `Cargo.toml` to find these paths

**Resolution:**

1. **Verify pipeline version is 2.5.0+**:
   ```bash
   python -c "import sigil_pipeline; print(sigil_pipeline.__version__)"
   ```

2. **If on older version**, update the pipeline:
   ```bash
   pip install -e .
   ```

3. **Check debug logs** for source path discovery:
   ```bash
   grep "Found .* .rs files in" logs/pipeline_*.log
   # Should show: "Found X .rs files in ['src', 'binding_rust', ...]"
   ```

4. **Manual verification**:
   ```python
   from pathlib import Path
   from sigil_pipeline.analyzer import get_crate_source_paths
   
   crate_dir = Path("crates/tree-sitter")
   paths = get_crate_source_paths(crate_dir)
   print(f"Source directories: {paths}")
   ```

**Related:**
- [ADR-011: Non-Standard Cargo Source Path Detection](../adr/ADR-011-non-standard-cargo-source-paths.md)

## Log Analysis

### Extract Error Summary

```bash
grep -E "ERROR|CRITICAL" logs/pipeline_*.log | \
  sed 's/.*ERROR/ERROR/' | \
  sort | uniq -c | sort -rn | head -20
```

### Find Slowest Crates

```bash
grep "processing completed" logs/pipeline_*.log | \
  sed 's/.*crate=\([^ ]*\).*duration=\([^ ]*\).*/\2 \1/' | \
  sort -rn | head -10
```

### Check Success Rate

```bash
python -c "
import re
import sys

total = 0
success = 0
with open('logs/pipeline_latest.log') as f:
    for line in f:
        if 'crate processing' in line:
            total += 1
            if 'success' in line.lower():
                success += 1

print(f'Success rate: {success}/{total} ({100*success/total:.1f}%)')
"
```

## When to Escalate

Escalate to senior engineer if:

- Issue persists after trying all solutions
- Data corruption suspected
- Security issue discovered
- New issue type not documented

## Post-Resolution

1. Document the issue and solution
2. Consider if runbook needs updating
3. Check if automated prevention is possible
4. Add regression test if applicable


