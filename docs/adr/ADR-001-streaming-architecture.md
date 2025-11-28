# ADR-001: Generator-Based Streaming Architecture

## Status

Accepted

## Context

Processing large datasets of Rust crates requires memory-efficient handling. The initial implementation loaded all data into memory, which caused:

1. Out-of-memory errors on typical development machines when processing many crates
2. Long delays before any output was produced
3. Inability to resume from interruptions

We needed an architecture that could:
- Process datasets of any size without memory constraints
- Produce output incrementally
- Support resumption from failures

## Decision

Implement a generator-based streaming architecture where:

1. **File iterators** yield one file at a time from each crate
2. **Filter functions** accept iterables and yield filtered items
3. **Dataset builders** yield samples without materializing all data
4. **JSONL export** writes line-by-line directly to disk

Key implementation patterns:
- Use Python generators (`yield`) throughout the pipeline
- Chain generators together with `yield from`
- Process items lazily, only when consumed by downstream stages
- Use `asyncio.as_completed` for concurrent crate processing while maintaining streaming

## Consequences

### Positive

- Memory usage stays constant regardless of dataset size
- Can process TB-scale datasets on modest hardware
- Output begins immediately as crates are processed
- Natural integration with checkpoint/resume system
- Easier to debug pipeline stages in isolation

### Negative

- Cannot easily shuffle or random-access during generation
- Debugging generators is harder than debugging lists
- Some operations (counting, shuffling) require materialization
- More complex control flow in pipeline orchestration

### Neutral

- Shuffling must be done as a post-processing step if needed
- Metrics collection happens at the exporter stage
- Progress reporting requires explicit tracking

## Alternatives Considered

### Alternative 1: Batch Processing

Process crates in fixed-size batches, writing results after each batch.

**Rejected because:**
- Still requires loading batch-sized data into memory
- Complexity of managing batch boundaries
- Suboptimal for varying crate sizes

### Alternative 2: Database-Backed Processing

Write intermediate results to SQLite and query for export.

**Rejected because:**
- Added dependency and complexity
- Slower for simple sequential processing
- Overkill for the primary use case

## Related

- Python Generator documentation: https://docs.python.org/3.12/howto/functional.html#generators
- Priority 2.1 in the refactoring plan


