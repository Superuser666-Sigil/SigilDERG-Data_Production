# Architecture Decision Records (ADRs)

This directory contains Architecture Decision Records (ADRs) for the Sigil Pipeline project.

## What is an ADR?

An Architecture Decision Record (ADR) is a document that captures an important architectural decision made along with its context and consequences.

## ADR Format

Each ADR follows this template:

```markdown
# ADR-NNN: Title

## Status
[Proposed | Accepted | Deprecated | Superseded by ADR-XXX]

## Context
What is the issue that we're seeing that is motivating this decision?

## Decision
What is the change that we're proposing/implementing?

## Consequences
What becomes easier or more difficult as a result of this decision?
```

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [ADR-001](ADR-001-streaming-architecture.md) | Generator-Based Streaming Architecture | Accepted |
| [ADR-002](ADR-002-category-based-clippy-filtering.md) | Category-Based Clippy Filtering | Accepted |
| [ADR-003](ADR-003-tree-sitter-semantic-chunking.md) | Tree-Sitter for Semantic Chunking | Accepted |
| [ADR-004](ADR-004-observability-infrastructure.md) | Observability Infrastructure | Accepted |
| [ADR-005](ADR-005-rate-limiting-strategy.md) | Rate Limiting Strategy | Accepted |

## Creating a New ADR

1. Copy the template from `template.md`
2. Name the file `ADR-NNN-short-title.md`
3. Fill in all sections
4. Add to the index above
5. Submit a PR for review


