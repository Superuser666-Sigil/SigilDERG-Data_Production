# config.py
"""Configuration module for the Rust Crate Pipeline.

This module provides configuration classes and utilities for managing
pipeline settings, credentials, and runtime parameters.

All configuration follows PEP 8 style guidelines and enterprise security
best practices.
"""
import os
import warnings
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, Optional, Union

if TYPE_CHECKING:
    from typing import Dict, List

# Import the centralized exception
from .exceptions import ConfigurationError

# Import the robust serialization utility
from utils.serialization_utils import to_serializable

# Filter Pydantic deprecation warnings from dependencies
# Rule Zero Compliance: Suppress third-party warnings while maintaining
# awareness
warnings.filterwarnings(
    "ignore",
    message=".*Support for class-based `config` is deprecated.*",
    category=DeprecationWarning,
    module="pydantic._internal._config",
)


@dataclass
class PipelineConfig:
    # Model configuration
    model_path: str = os.path.expanduser(
        "~/models/deepseek/deepseek-coder-6.7b-instruct.Q4_K_M.gguf"
    )
    max_tokens: int = 256
    model_token_limit: int = 4096
    prompt_token_margin: int = 3000

    # Pipeline configuration
    checkpoint_interval: int = 10
    max_retries: int = 3
    cache_ttl: int = 3600  # 1 hour
    batch_size: int = 10
    n_workers: int = 4

    # GitHub configuration
    github_token: str = field(
        default_factory=lambda: os.getenv(
            "GITHUB_TOKEN", ""))

    # Enhanced scraping configuration
    enable_crawl4ai: bool = True
    crawl4ai_model: str = os.path.expanduser(
        "~/models/deepseek/deepseek-coder-6.7b-instruct.Q4_K_M.gguf"
    )
    crawl4ai_timeout: int = 30

    # Output configuration
    output_path: str = "output"
    output_dir: str = "output"
    verbose: bool = False
    budget: Optional[float] = None
    llm_max_retries: int = 3

    # Azure OpenAI Configuration - NO DEFAULTS FOR SENSITIVE DATA
    use_azure_openai: bool = field(
        default_factory=lambda: os.getenv(
            "USE_AZURE_OPENAI",
            "false").lower() == "true")
    azure_openai_endpoint: str = field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_ENDPOINT", "")
    )
    azure_openai_api_key: str = field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_API_KEY", "")
    )
    azure_openai_deployment_name: str = field(
        default_factory=lambda: os.getenv(
            "AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o"))
    azure_openai_api_version: str = field(
        default_factory=lambda: os.getenv(
            "AZURE_OPENAI_API_VERSION",
            "2024-02-15-preview"))

    # Environment configuration
    environment: str = field(
        default_factory=lambda: os.getenv("ENVIRONMENT", "development")
    )

    def __post_init__(self):
        """Validate configuration after initialization."""
        self._validate_config()

    def _validate_config(self):
        """Validate configuration values."""
        # Validate Azure OpenAI configuration if enabled
        if self.use_azure_openai:
            if not self.azure_openai_endpoint:
                raise ConfigurationError(
                    "Azure OpenAI is enabled but AZURE_OPENAI_ENDPOINT is not set"
                )
            if not self.azure_openai_api_key:
                raise ConfigurationError(
                    "Azure OpenAI is enabled but AZURE_OPENAI_API_KEY is not set"
                )

        # Validate GitHub token if needed (can be optional for public repos)
        if not self.github_token and self.environment == "production":
            warnings.warn(
                "No GitHub token provided. API rate limits will be restricted.",
                RuntimeWarning)

        # Validate numeric configurations
        if self.batch_size <= 0:
            raise ConfigurationError(
                f"batch_size must be positive, got {
                    self.batch_size}")
        if self.n_workers <= 0:
            raise ConfigurationError(
                f"n_workers must be positive, got {
                    self.n_workers}")
        if self.max_retries < 0:
            raise ConfigurationError(
                f"max_retries must be non-negative, got {self.max_retries}")

    class Config:
        validate_assignment = True


@dataclass
class CrateMetadata:
    name: str
    version: str
    description: str
    repository: str
    keywords: "List[str]"
    categories: "List[str]"
    readme: str
    downloads: int
    github_stars: int = 0
    dependencies: "List[Dict[str, Any]]" = field(default_factory=list)
    features: "Dict[str, List[str]]" = field(default_factory=dict)
    code_snippets: "List[str]" = field(default_factory=list)
    readme_sections: "Dict[str, str]" = field(default_factory=dict)
    librs_downloads: Union[int, None] = None
    source: str = "crates.io"
    # Enhanced scraping fields
    enhanced_scraping: "Dict[str, Any]" = field(default_factory=dict)
    enhanced_features: "List[str]" = field(default_factory=list)
    enhanced_dependencies: "List[str]" = field(default_factory=list)

    def to_dict(self) -> "Dict[str, Any]":
        return to_serializable(asdict(self))


@dataclass
class EnrichedCrate(CrateMetadata):
    readme_summary: Union[str, None] = None
    feature_summary: Union[str, None] = None
    use_case: Union[str, None] = None
    score: Union[float, None] = None
    factual_counterfactual: Union[str, None] = None
    source_analysis: Union["Dict[str, Any]", None] = None
    user_behavior: Union["Dict[str, Any]", None] = None
    security: Union["Dict[str, Any]", None] = None
