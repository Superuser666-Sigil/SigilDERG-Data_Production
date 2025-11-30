# Runbook: Incident Response

## Overview

This runbook covers handling incidents and failures in production pipeline runs.

## Severity Levels

| Severity | Definition | Response Time |
|----------|------------|---------------|
| P1 | Pipeline completely down, data loss risk | < 1 hour |
| P2 | Major functionality impacted, degraded output | < 4 hours |
| P3 | Minor issues, workaround available | < 24 hours |
| P4 | Low impact, scheduled fix | Next sprint |

## Incident Response Steps

### 1. Assessment (First 5 Minutes)

```bash
# Check if pipeline is running
ps aux | grep sigil_pipeline

# Check latest logs
tail -100 logs/pipeline_*.log

# Check error count
grep -c "ERROR" logs/pipeline_*.log
```

**Determine:**
- Is the pipeline running or crashed?
- Is output still being produced?
- When did the issue start?

### 2. Triage (Next 10 Minutes)

#### If Pipeline Crashed

```bash
# Check crash reason
grep -A5 "Traceback" logs/pipeline_*.log | tail -20

# Check system resources
free -h
df -h
uptime
```

#### If Pipeline Stalled

```bash
# Check for deadlocks
strace -p <PID> 2>&1 | head -5

# Check network
netstat -an | grep ESTABLISHED
ping crates.io
```

#### If Output Quality Degraded

```bash
# Check recent samples
tail -100 output/dataset.jsonl | python -c "
import json, sys
for line in sys.stdin:
    s = json.loads(line)
    if len(s['gen']) < 50:
        print(f'Short gen: {len(s[\"gen\"])} chars')
"
```

### 3. Containment

#### For P1 Incidents

1. **Stop the pipeline** (if not already stopped):
   ```bash
   pkill -f sigil_pipeline
   ```

2. **Preserve evidence**:
   ```bash
   mkdir incident_$(date +%Y%m%d_%H%M%S)
   cp logs/pipeline_*.log incident_*/
   cp output/*.json incident_*/
   ```

3. **Notify stakeholders** (if applicable)

#### For P2-P3 Incidents

1. Check if checkpoint exists for resume
2. Attempt restart with reduced scope
3. Document issue for investigation

### 4. Resolution

#### Restart from Checkpoint

```bash
python -m sigil_pipeline.main \
    --checkpoint-path output/checkpoint.json \
    --output output/dataset.jsonl \
    --log-level DEBUG
```

#### Clean Restart

```bash
# Backup existing output
mv output/dataset.jsonl output/dataset.jsonl.bak

# Clean temp files
rm -rf /tmp/sigil_*

# Restart
python -m sigil_pipeline.main \
    --crate-list data/crate_list.txt \
    --output output/dataset.jsonl
```

### 5. Verification

```bash
# Check pipeline is running
ps aux | grep sigil_pipeline

# Watch for new output
watch -n 5 "wc -l output/dataset.jsonl"

# Check for new errors
tail -f logs/pipeline_*.log | grep -i error
```

## Common Incident Scenarios

### Scenario: crates.io Outage

**Detection:** Connection errors, 503 responses

**Response:**
1. Verify outage: `curl -I https://crates.io`
2. Check status: https://status.crates.io
3. Wait for restoration
4. Resume from checkpoint

### Scenario: Disk Full

**Detection:** OSError in logs, no new output

**Response:**
1. Check: `df -h`
2. Clear temp files: `rm -rf /tmp/sigil_*`
3. Clear old logs: `find logs/ -mtime +7 -delete`
4. Resume

### Scenario: Memory Exhaustion

**Detection:** OOM killer, process killed

**Response:**
1. Check: `dmesg | tail -20`
2. Reduce concurrency
3. Add swap if possible
4. Restart with `--max-threads 2`

## Post-Incident

### 1. Documentation

Create incident report:

```markdown
## Incident: [Brief Title]
Date: YYYY-MM-DD
Severity: P1/P2/P3/P4

### Timeline
- HH:MM - Issue detected
- HH:MM - Investigation started
- HH:MM - Root cause identified
- HH:MM - Fix applied
- HH:MM - Resolved

### Root Cause
[Description]

### Impact
[What was affected]

### Resolution
[How it was fixed]

### Prevention
[How to prevent recurrence]
```

### 2. Action Items

- [ ] File bug if code fix needed
- [ ] Update runbooks if new scenario
- [ ] Add monitoring if detection was slow
- [ ] Schedule post-mortem if P1/P2

## Emergency Contacts

- Pipeline Owner: [Contact]
- On-Call: [Contact]
- Escalation: [Contact]





