# config.py
import os
import warnings
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List

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


@dataclass
class CrateMetadata:
    name: str
    version: str
    description: str
    repository: str
    keywords: List[str]
    categories: List[str]
    readme: str
    downloads: int
    github_stars: int = 0
    dependencies: List[Dict[str, Any]] = field(default_factory=list)
    features: Dict[str, List[str]] = field(default_factory=dict)
    code_snippets: List[str] = field(default_factory=list)
    readme_sections: Dict[str, str] = field(default_factory=dict)
    librs_downloads: Optional[int] = None
    source: str = "crates.io"
    # Enhanced scraping fields
    enhanced_scraping: Dict[str, Any] = field(default_factory=dict)
    enhanced_features: List[str] = field(default_factory=list)
    enhanced_dependencies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EnrichedCrate(CrateMetadata):
    readme_summary: Optional[str] = None
    feature_summary: Optional[str] = None
    use_case: Optional[str] = None
    score: Optional[float] = None
    factual_counterfactual: Optional[str] = None
    source_analysis: Optional[Dict[str, Any]] = None
    user_behavior: Optional[Dict[str, Any]] = None
    security: Optional[Dict[str, Any]] = None
