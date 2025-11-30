# ADR-010: Comprehensive Test Coverage Strategy

**Status:** Accepted
**Date:** 2025-11-30
**Authors:** SigilDERG Team

## Context

The SigilDERG pipeline had grown to include multiple new modules:

- `api_tracker.py` - API evolution tracking
- `usage_analyzer.py` - Static API usage analysis
- `telemetry.py` - OpenTelemetry distributed tracing
- `dataset_splitter.py` - Train/validation splitting
- `cli/ecosystem.py` - Pipeline orchestration CLI
- `converters.py` - Format conversion utilities

Additionally, existing modules had new functions added:

- `ast_patterns.py` - `APIEntity`, `extract_all_api_entities()`, `check_function_in_code()`
- `utils.py` - `get_installed_toolchains()`, `find_best_toolchain()`, `parse_crate_info()`
- `filter.py` - `is_api_properly_used()`, `static_analysis_rust_code()`
- `task_generator.py` - `generate_explanation_task()`, `select_task_type()`, `determine_task_capabilities()`

Test coverage had dropped to 52% as these modules were added without corresponding tests.

## Decision

We implemented a comprehensive testing strategy:

1. **Create dedicated test files** for each new module following the pattern `test_<module>.py`
2. **Expand existing test files** to cover new functions
3. **Use mocking** for external dependencies (subprocess, network, filesystem)
4. **Test both success and failure paths** for all public functions
5. **Include edge cases** like empty input, malformed data, and timeout handling

## Test Architecture

### Test Organization

```
tests/
├── conftest.py              # Shared fixtures
├── test_api_tracker.py      # API evolution tracking tests
├── test_usage_analyzer.py   # Usage analysis tests
├── test_telemetry.py        # OpenTelemetry tests (graceful degradation)
├── test_dataset_splitter.py # Train/val split tests
├── test_cli_ecosystem.py    # CLI orchestration tests
├── test_converters.py       # Format conversion tests
├── test_ast_patterns.py     # AST extraction tests (expanded)
├── test_utils.py            # Utility function tests (expanded)
├── test_filter.py           # Filtering tests (expanded)
└── test_task_generator.py   # Task generation tests (expanded)
```

### Testing Patterns

1. **No-Op Fallback Testing** (telemetry.py):
   - Test both with and without OpenTelemetry installed
   - Verify graceful degradation to no-op implementations

2. **Mocked Subprocess Testing** (utils.py, cli/ecosystem.py):
   - Mock `subprocess.run` for cargo/rustup commands
   - Test timeout handling and error conditions

3. **Temporary File Testing** (dataset_splitter.py, converters.py):
   - Use pytest's `tmp_path` fixture
   - Create/verify actual file I/O behavior

4. **Parameterized Testing** (task_generator.py):
   - Test multiple input variations
   - Verify task type selection distributions

## Consequences

### Positive

- Coverage improved from 52% to 75%
- 672 tests now passing (up from ~450)
- All new modules have comprehensive test coverage
- Easier to catch regressions during development

### Negative

- Test suite takes longer to run (~75 seconds)
- Some modules still have lower coverage due to I/O dependencies:
  - `main.py` (42%) - CLI entry point
  - `crawler.py` (55%) - Network operations
  - `observability.py` (52%) - Metrics system

### Neutral

- Test files add ~4000 lines of code
- Requires maintaining tests alongside code changes

## Coverage Summary

| Module | Coverage |
|--------|----------|
| `dataset_splitter.py` | 98% |
| `config.py` | 99% |
| `cli/ecosystem.py` | 93% |
| `prompt_templates.py` | 92% |
| `environment.py` | 91% |
| `analysis_cache.py` | 90% |
| `filter.py` | 89% |
| `usage_analyzer.py` | 89% |
| `format_validator.py` | 83% |
| `dataset_builder.py` | 82% |
| `utils.py` | 82% |
| `analyzer.py` | 81% |
| `task_generator.py` | 80% |
| `api_tracker.py` | 79% |
| `ast_patterns.py` | 78% |
| `telemetry.py` | 77% |
| `converters.py` | 63% |
| `chunker.py` | 61% |
| `exporter.py` | 60% |
| `crawler.py` | 55% |
| `observability.py` | 52% |
| `main.py` | 42% |

**Overall: 75% (4845 statements, 1205 missed)**

## Related ADRs

- [ADR-004](ADR-004-observability-infrastructure.md) - Observability Infrastructure (tested by `test_telemetry.py`)
- [ADR-006](ADR-006-ast-aware-prompt-generation.md) - AST-Aware Prompt Generation (tested by `test_ast_patterns.py`)
- [ADR-009](ADR-009-api-evolution-tracking.md) - API Evolution Tracking (tested by `test_api_tracker.py`, `test_usage_analyzer.py`)

## References

- [pytest documentation](https://docs.pytest.org/)
- [pytest-cov](https://pytest-cov.readthedocs.io/)
- [Hypothesis property-based testing](https://hypothesis.readthedocs.io/)
