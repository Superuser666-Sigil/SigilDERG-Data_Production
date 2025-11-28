# Load Testing

This directory contains load tests for the Sigil Pipeline.

## Prerequisites

```bash
pip install locust
```

## Running Load Tests

### Web UI Mode (Interactive)

```bash
locust -f tests/load/locustfile.py
```

Then open http://localhost:8089 in your browser.

### Headless Mode (CI/Automated)

```bash
# 10 users, spawn 1/second, run for 60 seconds
locust -f tests/load/locustfile.py --headless -u 10 -r 1 -t 60s

# With HTML report
locust -f tests/load/locustfile.py --headless -u 10 -r 1 -t 60s --html=report.html
```

### Quick Validation

Run without locust to validate test components:

```bash
python tests/load/locustfile.py
```

## Test Scenarios

| Scenario | Weight | Description |
|----------|--------|-------------|
| size_sanity | 10 | Filter by size/content ratio |
| doc_comments | 10 | Detect documentation comments |
| chunk_file | 5 | Semantic code chunking |
| create_prompt | 5 | Prompt generation |
| metrics | 3 | Metrics collection/export |
| jsonl_write | 2 | JSONL file writing |

## Metrics

- **Request Type**: Component being tested (FILTER, CHUNKER, BUILDER, METRICS, EXPORTER)
- **Response Time**: Time to complete operation (ms)
- **Response Length**: Size of result (chars, chunks, or samples)

## Interpreting Results

### Healthy Metrics

| Metric | Target |
|--------|--------|
| Median response time | < 10ms |
| 95th percentile | < 50ms |
| Error rate | 0% |
| Throughput | > 100 req/s |

### Warning Signs

- Response times increasing over test duration (memory leak)
- Error rate > 0% (bugs)
- Throughput decreasing (resource exhaustion)

## Integration with CI

Add to GitHub Actions:

```yaml
- name: Run load tests
  run: |
    pip install locust
    locust -f tests/load/locustfile.py --headless -u 5 -r 1 -t 30s
```

