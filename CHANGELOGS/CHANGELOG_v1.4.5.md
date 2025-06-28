# Changelog v1.4.5 – 2025-06-28

### Added / Changed

* **Sanitization Toggle** – `Sanitizer` is now disabled by default (`enabled=False`).
  * No automatic PII stripping for crate data; full fidelity retained.
  * Projects that require redaction can opt-in by instantiating `Sanitizer(enabled=True)`.
* **Robust JSON Serialization** – All pipeline and CLI writers use `to_serializable` ensuring complex objects like `MarkdownGenerationResult` serialize cleanly.
* **Documentation** – README updated to describe the new sanitization behaviour and serialization utilities.
* **Version Bump** – Project version incremented to `1.4.5`; Dockerfile and `pyproject.toml` reflect the change.

### Fixed

* Residual "Object of type MarkdownGenerationResult is not JSON serializable" error during CLI file generation.

### Removed

* Automatic default PII removal from crate metadata (now opt-in). 