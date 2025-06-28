# Changelog v1.4.4

## [1.4.4] - {today}

### Security
- Implemented a robust PII and secret sanitization system using `presidio-analyzer` to prevent sensitive data from being stored in the RAG or sent to LLMs.
- Added comprehensive tests to verify the effectiveness of the sanitization logic.

--- 