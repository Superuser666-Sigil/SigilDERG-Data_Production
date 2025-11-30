# ADR-005: Rate Limiting Strategy

## Status

Accepted

## Context

The pipeline makes HTTP requests to crates.io for:
- Fetching crate metadata (version, license)
- Downloading crate tarballs

crates.io has rate limiting guidelines:
- 1 request per second for bulk operations
- Risk of IP bans for aggressive crawling
- Need to be a good citizen of the Rust ecosystem

Initial implementation had no rate limiting, risking:
- Temporary or permanent IP bans
- Failed pipeline runs due to 429 responses
- Negative impact on crates.io infrastructure

## Decision

Implement synchronous rate limiting for crates.io requests:

1. **Global Rate Limiter**
   - Track last request time globally
   - Enforce minimum 1 second between requests
   - Apply to both API calls and downloads

2. **Implementation Pattern**
   - Simple time-based throttling with `time.sleep()`
   - Check elapsed time since last request
   - Wait if necessary before proceeding
   - Update last request time after wait

3. **Configuration**
   - `CRATES_IO_RATE_LIMIT_SECONDS = 1.0`
   - Configurable for different environments

4. **Integration with Retry Logic**
   - Rate limiting applied inside retry decorator
   - Each retry attempt respects rate limit
   - Exponential backoff complements rate limiting

## Consequences

### Positive

- Respectful use of crates.io infrastructure
- Avoids IP bans and 429 errors
- Predictable request patterns
- Simple, maintainable implementation

### Negative

- Slower pipeline execution (limited to 1 crate/second for API calls)
- Serial API requests (no parallel metadata fetching)
- Not optimal for burst-then-wait patterns

### Neutral

- Parallel crate processing still works (analysis runs concurrently)
- Rate limit only affects crates.io requests, not local operations
- Caching helps avoid repeated requests

## Alternatives Considered

### Alternative 1: Token Bucket Rate Limiter

Implement a token bucket allowing bursts with sustained rate limit.

**Rejected because:**
- More complex implementation
- crates.io guidance suggests steady rate, not bursts
- Overkill for current use case

### Alternative 2: Asyncio Throttler

Use asyncio-throttle for async rate limiting.

**Rejected because:**
- requests library is synchronous
- Would require significant refactoring
- Current sync approach is simpler and works

### Alternative 3: External Rate Limiter (Redis)

Use Redis-based distributed rate limiting.

**Rejected because:**
- Adds external dependency
- Pipeline is single-process
- Overkill for current architecture

## Related

- crates.io crawling policy: https://crates.io/policies
- tenacity retry library: https://tenacity.readthedocs.io/
- `sigil_pipeline/crawler.py::_rate_limit_sync()`





