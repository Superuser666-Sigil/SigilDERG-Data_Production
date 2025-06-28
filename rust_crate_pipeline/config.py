# config.py
import os
import warnings
from dataclasses import dataclass, field, asdict
from typing import Any, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Dict, List

# Filter Pydantic deprecation warnings from dependencies
# Rule Zero Compliance: Suppress third-party warnings while maintaining awareness
warnings.filterwarnings(
    "ignore",
    message=".*Support for class-based `config` is deprecated.*",
    category=DeprecationWarning,
    module="pydantic._internal._config",
)


@dataclass
class PipelineConfig:
    model_path: str = os.path.expanduser(
        "~/models/deepseek/deepseek-coder-6.7b-instruct.Q4_K_M.gguf"
    )
    max_tokens: int = 256
    model_token_limit: int = 4096
    prompt_token_margin: int = 3000
    checkpoint_interval: int = 10
    max_retries: int = 3
    github_token: str = os.getenv("GITHUB_TOKEN", "")
    cache_ttl: int = 3600  # 1 hour
    batch_size: int = 10
    n_workers: int = 4  # Enhanced scraping configuration
    enable_crawl4ai: bool = True
    crawl4ai_model: str = os.path.expanduser(
        "~/models/deepseek/deepseek-coder-6.7b-instruct.Q4_K_M.gguf"
    )
    crawl4ai_timeout: int = 30
    output_path: str = "output"
    
    # Azure OpenAI Configuration
    use_azure_openai: bool = True
    azure_openai_endpoint: str = "https://david-mc08tirc-eastus2.services.ai.azure.com/"
    azure_openai_api_key: str = "2hw0jjqwjtKke7DMGiJSPtlj6GhuLCNdQWPXoDGN2I3JMvzp4PmGJQQJ99BFACHYHv6XJ3w3AAAAACOGFPYA"
    azure_openai_deployment_name: str = "gpt-4o"  # or your specific deployment name
    azure_openai_api_version: str = "2024-02-15-preview"


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
        return asdict(self)


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
