# rust_crate_pipeline/__init__.py
"""
Rust Crate Data Processing Pipeline

A comprehensive system for gathering, enriching, and analyzing metadata for Rust crates.
Includes AI-powered enrichment using local LLMs and dependency analysis.

Example usage:
    from rust_crate_pipeline import CrateDataPipeline
    from rust_crate_pipeline.main import main

    # Run the main pipeline
    main()

    # Or use the pipeline class directly
    config = PipelineConfig()
    pipeline = CrateDataPipeline(config)
    pipeline.run()

Components:
    - CrateDataPipeline: Main orchestration class
    - PipelineConfig: Configuration management
    - Various analyzers for AI, security, and dependency analysis
"""

# The following imports are for making package-level metadata and components
# easily accessible to users of the library.
from .version import __version__  # noqa: F401

__author__ = "SuperUser666-Sigil"
__email__ = "miragemodularframework@gmail.com"
__license__ = "MIT"

# The main components are demonstrated in the docstring and are not directly
# exported here to avoid circular dependencies and to keep the namespace clean.
# Users should import them directly from the respective modules.

# Suppress specific warnings at the package initialization level
import warnings

# Rule Zero Compliance: Suppress third-party Pydantic deprecation warnings
warnings.filterwarnings(
    "ignore",
    message=".*Support for class-based.*config.*is deprecated.*",
    category=DeprecationWarning,
)
warnings.filterwarnings(
    "ignore", category=UserWarning, module=".*rust_crate_pipeline.*"
)
warnings.filterwarnings(
    "ignore", category=DeprecationWarning, module=".*rust_crate_pipeline.*"
)
