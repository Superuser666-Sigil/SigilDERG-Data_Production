Changelog
=========

Version 2.2.0
-------------

* **Ecosystem Integration**: Full integration with SigilDERG-Finetuner, human-eval-Rust, and lambda-package
* **Architecture Documentation**: Comprehensive ADR index and system architecture documentation
* **Version Synchronization**: All ecosystem components synchronized to compatible versions

Version 2.0.0
-------------

* **Checkpoint/Resume System**: Automatic checkpointing allows resuming long-running pipeline executions
* **Improved Error Injection**: Enhanced error-fixing task generation with fallback to simulated errors
* **Enhanced Logging**: Geiger and License checks now always write logs
* **Tool Execution Tracking**: Rejection summaries now include flags for executed tools

Version 1.2.0
-------------

* **Phase-2 Instruct Mode**: Natural language instruction generation
* **Semantic Chunking**: Tree-sitter based code parsing
* **Task Type Diversity**: Code generation, transformations, error fixing, explanations
* **License Pre-checking**: Validates licenses from crates.io API before downloading

Version 1.1.0
-------------

* **Streaming Architecture**: Generator-based pipeline for memory efficiency
* **Granular Filter Metrics**: Detailed filter reason breakdown
* **Platform Compatibility Detection**: Automatically skips platform-specific crates

Version 1.0.0
-------------

* Initial release
* Static analysis with Clippy, Geiger, Outdated, License checks
* Quality filtering for Rust 2021+ edition
* JSONL dataset generation

