# Runbook: Troubleshooting

## Overview

This runbook covers diagnosing and resolving common issues with the Sigil Pipeline.

## Quick Diagnostics

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
pip install -e ".[datasets,parsing,dev]"
```

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

