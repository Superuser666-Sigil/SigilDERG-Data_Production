from typing import Dict, List, Tuple, Optional, Any
"""Version information for rust-crate-pipeline."""

__version__ = "1.4.1"
__version_info__ = tuple(int(x) for x in __version__.split("-")[0].split("."))
__author__ = "SigilDERG Team"
__email__ = "sigilderg@example.com"

# Version history
# 1.2.5-dev.20250621 - Dev branch: experimental, not a formal
# release. Originated from v1.2.5.
# 1.2.5 - Last official release.
# 1.5.1 - Configuration Standardization Release: Model Path Consistency
#         - Standardized all configuration to use GGUF model paths
#         - Updated CLI defaults for --crawl4ai-model to
#           ~/models/deepseek/deepseek-coder-6.7b-instruct.Q4_K_M.gguf
#         - Enhanced Rule Zero alignment with transparent configuration practices
#         - Updated all test files to use consistent GGUF model path references
#         - Comprehensive documentation updates for proper model configuration
#         - Removed inconsistent Ollama references in favor of llama-cpp-python
#         - Ensured CLI help text and JSON examples reflect correct model paths
# 1.5.0 - Major Release: Enhanced Web Scraping with Crawl4AI Integration
#         - Integrated Crawl4AI for advanced web scraping capabilities
#         - Added JavaScript-rendered content extraction via Playwright
#         - Enhanced README parsing with LLM-powered content analysis
#         - New CLI options: --enable-crawl4ai, --disable-crawl4ai, --crawl4ai-model
#         - Enhanced configuration with local GGUF model paths and crawl4ai_timeout
#         - Comprehensive test coverage for all Crawl4AI features
#         - Rule Zero compliant with full transparency and audit trails
# 1.4.0 - Major Release: Rule Zero Compliance Audit Complete
#         - Completed comprehensive Rule Zero alignment audit
#         - Eliminated all code redundancy and dead code
#         - Achieved 100% test coverage (22/22 tests passing)
#         - Refactored to pure asyncio architecture (thread-free)
#         - Suppressed Pydantic deprecation warnings
#         - Full production readiness with Docker support
#         - Enhanced documentation with PyPI cross-references
#         - Certified Rule Zero compliance across all four principles
# 1.3.1 - Bug Fix Release: Crawl4AI Integration Cleanup
#         - Fixed CSS selector syntax errors in Crawl4AI integration
#         - Cleaned up duplicate and obsolete test files
#         - Resolved import conflicts between workspace and integration configs
#         - Improved error handling in enhanced scraping module
#         - Standardized on direct llama.cpp approach (removed Ollama dependencies)
#         - Enhanced Rule Zero compliance with transparent cleanup process
#         - Fixed type annotation compatibility issues
#         - Fixed Python 3.9 compatibility for type annotations
#         - Updated dict[str, Any] to "dict[str, Any]" format
#         - Fixed Union type expressions in conditional imports
#         - Resolved IDE linter errors in network.py, pipeline.py, and production_config.py
#         - Improved code quality and maintainability
# 1.3.0 - Quality & Integration Release: Comprehensive code quality improvements
#         - Fixed all critical PEP 8 violations (F821, F811, E114)
#         - Enhanced error handling with graceful dependency fallbacks
#         - Improved module integration and import path resolution
#         - Added comprehensive test validation (21/21 tests passing)
#         - Enhanced async support and Unicode handling
#         - Production-ready CLI interfaces with robust error handling
#         - Full Rule Zero compliance validation
# 1.2.0 - Major release: Production-ready, cleaned codebase
#         - Unified documentation into single comprehensive README
#         - Removed all non-essential development and test files
#         - Optimized for PyPI distribution and Docker deployment
#         - Enhanced GitHub token integration and setup
# 1.1.2 - Production release: Cleaned up non-essential files
#         - Unified documentation into single README
#         - Optimized for PyPI distribution
# 1.1.1 - Bug fix: Added missing python-dateutil dependency
#         - Fixed relativedelta import error
# 1.1.0 - Updated author and contact information
#         - Enhanced package configuration
# 0.1.0 - Initial release
#         - Core pipeline functionality
#         - AI-powered metadata enrichment
#         - Dependency analysis
#         - PyPI package setup
