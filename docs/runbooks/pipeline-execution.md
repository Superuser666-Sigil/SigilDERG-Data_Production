# Runbook: Pipeline Execution

## Overview

This runbook covers running the Sigil Pipeline for dataset generation.

## Prerequisites

- [ ] Python 3.12+ installed
- [ ] Rust toolchain installed with required components
- [ ] Virtual environment activated
- [ ] Dependencies installed (`pip install -e ".[all]"`)
- [ ] Sufficient disk space (10GB+ recommended)
- [ ] Network access to crates.io

## Pre-Execution Checklist

### 1. Verify Environment

```bash
# Check Python version
python --version  # Should be 3.12+

# Check Rust toolchain
cargo --version
rustup show

# Check cargo subcommands
cargo clippy --version
cargo geiger --version

# Full environment fingerprint (recommended before large runs)
python -c "
from sigil_pipeline.environment import capture_environment, log_environment_summary
fp = capture_environment()
log_environment_summary(fp)
"
```

**Note:** The pipeline automatically captures an environment fingerprint at startup
and writes it to `output/environment.json`. This is critical for reproducibility
audits - keep this file alongside your dataset.

### 2. Prepare Input Data

```bash
# Option A: Use specific crates
python -m sigil_pipeline.main --crates serde tokio actix-web

# Option B: Use crate list file
cat data/crate_list.txt  # Verify crates to process
wc -l data/crate_list.txt  # Count crates
```

### 3. Verify Toolchain Availability

```bash
# Check installed toolchains
rustup toolchain list

# Verify pipeline can discover toolchains
python -c "
from sigil_pipeline.utils import get_installed_toolchains, find_best_toolchain
installed = get_installed_toolchains()
print(f'Installed: {installed}')
best = find_best_toolchain('1.76.0', installed)
print(f'Best match for 1.76.0: {best}')
"
```

**Note:** The pipeline automatically selects appropriate toolchains. Multiple versions can be installed for crates requiring specific Rust versions.

### 4. Check Disk Space

```bash
# Check available space
df -h .

# Estimate needed space: ~50MB per crate (temp files)
```

## Execution Steps

### Basic Execution

```bash
# Phase-1 compatible mode
python -m sigil_pipeline.main \
    --crate-list data/crate_list.txt \
    --output output/dataset.jsonl \
    --log-level INFO

# Phase-2 instruct mode
python -m sigil_pipeline.main \
    --crate-list data/crate_list.txt \
    --prompt-mode instruct \
    --max-sft-lines 200 \
    --output output/phase2_dataset.jsonl
```

### With Checkpointing (Recommended for Large Runs)

```bash
python -m sigil_pipeline.main \
    --crate-list data/crate_list.txt \
    --checkpoint-path output/checkpoint.json \
    --checkpoint-interval 10 \
    --output output/dataset.jsonl
```

### Docker Execution

```bash
# Build image
docker-compose build

# Run pipeline
docker-compose run --rm pipeline \
    python -m sigil_pipeline.main \
    --crate-list /app/data/crate_list.txt \
    --output /app/output/dataset.jsonl
```

## Monitoring

### Check Progress

```bash
# Watch log output
tail -f logs/pipeline_*.log

# Count processed samples
wc -l output/dataset.jsonl

# Check metrics
cat output/metrics.json
```

### Resource Usage

```bash
# CPU and memory
top -p $(pgrep -f sigil_pipeline)

# Disk I/O
iotop -p $(pgrep -f sigil_pipeline)
```

## Verification

### 1. Check Output

```bash
# Verify JSONL format
head -1 output/dataset.jsonl | python -m json.tool

# Count samples
wc -l output/dataset.jsonl

# Check for errors
grep -i error logs/pipeline_*.log | tail -20
```

### 2. Validate Dataset

```bash
# Run validation script
python -c "
import json
with open('output/dataset.jsonl') as f:
    for i, line in enumerate(f):
        sample = json.loads(line)
        assert 'prompt' in sample and 'gen' in sample, f'Invalid sample {i}'
print('Validation passed')
"
```

### 3. Review Metrics

```bash
# Check filter breakdown
cat output/metrics.json | python -c "
import json, sys
metrics = json.load(sys.stdin)
print('Filter breakdown:')
for k, v in metrics.get('filter_breakdown', {}).items():
    print(f'  {k}: {v}')
"
```

## Common Issues

| Issue | Solution |
|-------|----------|
| Rate limited by crates.io | Wait and retry, check rate limit settings |
| Cargo timeout | Increase timeout in config |
| Out of disk space | Clean temp dirs, use smaller batch |
| Memory pressure | Reduce max_threads |

## Rollback

If execution fails:

1. Check checkpoint file for resume capability
2. Review logs for error cause
3. Fix configuration and restart from checkpoint

```bash
# Resume from checkpoint
python -m sigil_pipeline.main \
    --checkpoint-path output/checkpoint.json \
    --output output/dataset.jsonl
```

## Post-Execution

1. **Verify reproducibility artifacts exist:**
   ```bash
   ls -la output/environment.json output/metrics.json output/dataset.jsonl
   ```

2. **Archive all artifacts together:**
   ```bash
   tar -czvf run_$(date +%Y%m%d).tar.gz \
       output/dataset.jsonl \
       output/metrics.json \
       output/environment.json \
       output/metrics.prom  # If Prometheus enabled
   ```

3. Upload dataset if applicable

4. Clean temp files: `rm -rf /tmp/sigil_*`

5. Document any issues encountered

### Reproducibility Checklist

For auditable runs, verify:

- [ ] `environment.json` contains rustc/cargo versions
- [ ] `metrics.json` contains `prompt_seed` value
- [ ] All environment fingerprint fields are populated
- [ ] Config settings are stored in metrics.json


