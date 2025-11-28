# Runbook: Scaling

## Overview

This runbook covers scaling the Sigil Pipeline for larger workloads.

## Scaling Dimensions

| Dimension | Current Limit | Bottleneck |
|-----------|---------------|------------|
| Crates/run | ~1000 | API rate limits |
| Concurrency | 4 threads | CPU/Memory |
| Dataset size | Unbounded | Disk space |

## Vertical Scaling (Single Machine)

### Increase Concurrency

```bash
# Check available cores
nproc

# Increase threads (default: 4)
python -m sigil_pipeline.main \
    --max-threads 8 \
    ...
```

**Memory requirements:** ~500MB per concurrent crate analysis

### Optimize Disk I/O

1. Use SSD for temp directory
2. Use ramdisk for very fast runs:
   ```bash
   mkdir /mnt/ramdisk
   mount -t tmpfs -o size=4g tmpfs /mnt/ramdisk
   export TMPDIR=/mnt/ramdisk
   ```

### Docker Resource Allocation

```yaml
# docker-compose.yml
services:
  pipeline:
    deploy:
      resources:
        limits:
          cpus: '8'
          memory: 16G
```

## Horizontal Scaling (Multiple Machines)

### Strategy: Partition by Crate

Split crate list and run on multiple machines:

```bash
# On machine 1
split -n l/4 data/crate_list.txt crate_part_
python -m sigil_pipeline.main --crate-list crate_part_aa --output output/part1.jsonl

# On machine 2
python -m sigil_pipeline.main --crate-list crate_part_ab --output output/part2.jsonl

# Merge results
cat output/part*.jsonl > output/full_dataset.jsonl
```

### Strategy: Separate Download from Analysis

```bash
# Phase 1: Download all crates (can parallelize)
python -m sigil_pipeline.main --download-only --output-dir crates/

# Phase 2: Analyze downloaded crates (can parallelize)
python -m sigil_pipeline.main --local-crates crates/ --output output/dataset.jsonl
```

## Batch Processing

### For Very Large Runs (10,000+ crates)

1. **Batch the crate list:**
   ```bash
   split -l 500 data/crate_list.txt batch_
   ```

2. **Process batches sequentially:**
   ```bash
   for batch in batch_*; do
       python -m sigil_pipeline.main \
           --crate-list "$batch" \
           --output "output/$(basename $batch).jsonl"
   done
   ```

3. **Merge results:**
   ```bash
   cat output/batch_*.jsonl > output/full_dataset.jsonl
   ```

## Resource Monitoring

### Real-time Monitoring

```bash
# Combined view
htop

# Just pipeline
watch -n 1 "ps aux | grep sigil_pipeline | grep -v grep"
```

### Logging Resource Usage

```bash
# Record resource usage every 5 seconds
while true; do
    echo "$(date) $(ps -o rss,pcpu,pid -p $(pgrep -f sigil_pipeline) 2>/dev/null)"
    sleep 5
done >> resource_log.txt
```

## Optimization Tips

### 1. Filter Early

Skip crates that will definitely fail:

```python
# Pre-filter by known issues
exclude_crates = {"problematic-crate-1", "platform-specific-crate"}
```

### 2. Cache Cargo Build Dependencies

```bash
# Set persistent cargo cache
export CARGO_HOME=/persistent/cargo
```

### 3. Skip Slow Analysis Tools

For faster runs, disable optional tools:

```python
config = PipelineConfig(
    enable_geiger=False,  # Slowest tool
    enable_outdated=False,
)
```

### 4. Use Streaming Exports

Already implemented - dataset is written line-by-line, not loaded into memory.

## Capacity Planning

### Estimate Time

```
Time = (num_crates / rate_limit) + (num_crates * avg_analysis_time / threads)

Example:
- 1000 crates
- 1 req/sec rate limit = 1000 seconds
- 30 sec avg analysis, 4 threads = 7500 seconds
- Total: ~140 minutes
```

### Estimate Disk Space

```
Space = num_crates * (avg_crate_size + temp_files)

Example:
- 1000 crates
- 10MB avg (downloaded + extracted)
- 10GB total temp space needed
```

### Estimate Memory

```
Memory = base + (threads * per_thread)

Example:
- 200MB base
- 500MB per thread
- 4 threads = 2.2GB
```

## Scaling Checklist

Before large runs:

- [ ] Sufficient disk space verified
- [ ] Memory limits configured
- [ ] Rate limiting respected
- [ ] Checkpointing enabled
- [ ] Monitoring set up
- [ ] Notification for completion/failure

## Limits and Constraints

| Resource | Limit | Reason |
|----------|-------|--------|
| crates.io requests | 1/sec | Rate limiting policy |
| Concurrent cargo runs | 4-8 | Memory/CPU |
| Temp directory size | 10GB+ | Extracted crates |
| Log file size | 100MB | Rotation needed |

