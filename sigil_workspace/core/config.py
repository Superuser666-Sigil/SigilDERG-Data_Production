"""
Configuration Management for Sigil Data Workspace

Rule Zero compliant configuration with Sacred Chain integration
and comprehensive validation.
"""

import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from pydantic import BaseModel, Field, field_validator


class WorkspaceConfig(BaseModel):
    """Main workspace configuration with Rule Zero compliance"""

    # Rule Zero Settings
    enable_sacred_chain: bool = Field(
        default=True, description="Enable Sacred Chain traceability for all operations"
    )
    audit_level: str = Field(
        default="FULL", description="Audit level: MINIMAL, STANDARD, FULL"
    )
    confidence_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum confidence score for operations",
    )
    require_reasoning_trace: bool = Field(
        default=True, description="Require explicit reasoning for all decisions"
    )

    # Processing Settings
    batch_size: int = Field(
        default=100, gt=0, description="Default batch size for data processing"
    )
    parallel_workers: int = Field(
        default=4, gt=0, description="Number of parallel processing workers"
    )
    timeout_seconds: int = Field(
        default=300, gt=0, description="Default timeout for operations"
    )
    max_retries: int = Field(
        default=3, ge=0, description="Maximum retry attempts for failed operations"
    )

    # AI Settings
    ai_provider: str = Field(
        default="openai", description="AI provider: openai, anthropic, local"
    )
    model_name: str = Field(default="gpt-4", description="AI model name")
    max_tokens: int = Field(
        default=2000, gt=0, description="Maximum tokens for AI responses"
    )
    temperature: float = Field(
        default=0.1, ge=0.0, le=2.0, description="AI temperature setting"
    )

    # Storage Settings
    output_directory: str = Field(
        default="./output", description="Directory for output files"
    )
    log_directory: str = Field(default="./logs", description="Directory for log files")
    cache_enabled: bool = Field(default=True, description="Enable request caching")
    cache_ttl: int = Field(
        default=3600, ge=0, description="Cache time-to-live in seconds"
    )

    # Network Settings
    request_timeout: int = Field(
        default=30, gt=0, description="HTTP request timeout in seconds"
    )
    rate_limit_calls: int = Field(
        default=100, gt=0, description="Rate limit calls per period"
    )
    rate_limit_period: int = Field(
        default=60, gt=0, description="Rate limit period in seconds"
    )

    @field_validator("audit_level")
    @classmethod
    def validate_audit_level(cls, v: str) -> str:
        if v not in ["MINIMAL", "STANDARD", "FULL"]:
            raise ValueError("audit_level must be MINIMAL, STANDARD, or FULL")
        return v

    @field_validator("ai_provider")
    @classmethod
    def validate_ai_provider(cls, v: str) -> str:
        if v not in ["openai", "anthropic", "local"]:
            raise ValueError("ai_provider must be openai, anthropic, or local")
        return v

    @classmethod
    def from_env(cls) -> "WorkspaceConfig":
        """Create configuration from environment variables"""
        config_data: Dict[str, Any] = {}

        # Map environment variables to config fields
        env_mapping = {
            "SIGIL_ENABLE_SACRED_CHAIN": "enable_sacred_chain",
            "SIGIL_AUDIT_LEVEL": "audit_level",
            "SIGIL_CONFIDENCE_THRESHOLD": "confidence_threshold",
            "SIGIL_BATCH_SIZE": "batch_size",
            "SIGIL_PARALLEL_WORKERS": "parallel_workers",
            "SIGIL_AI_PROVIDER": "ai_provider",
            "SIGIL_MODEL_NAME": "model_name",
            "SIGIL_OUTPUT_DIR": "output_directory",
            "SIGIL_LOG_DIR": "log_directory",
        }

        for env_var, config_key in env_mapping.items():
            value = os.getenv(env_var)
            if value is not None:
                # Convert string values to appropriate types
                field_type = cls.model_fields[config_key].annotation
                if field_type is bool:
                    config_data[config_key] = value.lower() in ("true", "1", "yes")
                elif field_type is int:
                    config_data[config_key] = int(value)
                elif field_type is float:
                    config_data[config_key] = float(value)
                else:
                    config_data[config_key] = value

        return cls(**config_data)


@dataclass
class SacredChainConfig:
    """Configuration for Sacred Chain implementation"""

    enable_cryptographic_signing: bool = True
    hash_algorithm: str = "sha256"
    chain_verification_interval: int = 100  # Verify every N operations
    store_full_reasoning_trace: bool = True
    compress_chain_data: bool = False
    max_chain_length: int = 10000
    audit_log_format: str = "json"  # json, csv, structured
    confidence_score_precision: int = 4

    # IRL (Integrity Reasoning Layer) Settings
    irl_enabled: bool = True
    irl_confidence_weights: Dict[str, float] = field(
        default_factory=lambda: {
            "canon_alignment": 0.3,
            "context_consistency": 0.25,
            "memory_integrity": 0.2,
            "llm_volatility": -0.15,  # Negative weight for volatility
            "validation_success": 0.4,
        }
    )

    # Trust thresholds
    trust_threshold_allow: float = 0.8
    trust_threshold_defer: float = 0.5
    trust_threshold_deny: float = 0.3

    def validate_config(self) -> List[str]:
        """Validate configuration and return any errors"""
        errors: List[str] = []

        if self.hash_algorithm not in ["sha256", "sha512", "blake2b"]:
            errors.append("hash_algorithm must be sha256, sha512, or blake2b")

        if self.confidence_score_precision < 1 or self.confidence_score_precision > 10:
            errors.append("confidence_score_precision must be between 1 and 10")

        if not (
            0
            <= self.trust_threshold_deny
            <= self.trust_threshold_defer
            <= self.trust_threshold_allow
            <= 1
        ):
            errors.append(
                "Trust thresholds must be in order: "
                "deny <= defer <= allow, all between 0 and 1"
            )

        weight_sum = sum(abs(w) for w in self.irl_confidence_weights.values())
        if abs(weight_sum - 1.0) > 0.01:  # Allow small floating point errors
            errors.append(
                f"IRL confidence weights should sum to approximately 1.0, "
                f"got {weight_sum}"
            )

        return errors


class ProductionConfig:
    """Production environment configuration"""

    @staticmethod
    def setup_production_environment():
        """Configure environment for production use"""
        # Set production-optimized defaults
        os.environ.setdefault("SIGIL_AUDIT_LEVEL", "STANDARD")
        os.environ.setdefault("SIGIL_ENABLE_SACRED_CHAIN", "true")
        os.environ.setdefault("SIGIL_CONFIDENCE_THRESHOLD", "0.8")
        os.environ.setdefault("SIGIL_BATCH_SIZE", "50")
        os.environ.setdefault("SIGIL_PARALLEL_WORKERS", "2")

        # Ensure directories exist
        for dir_name in ["./output", "./logs", "./cache"]:
            os.makedirs(dir_name, exist_ok=True)

    @staticmethod
    def get_production_config() -> WorkspaceConfig:
        """Get production-optimized configuration"""
        ProductionConfig.setup_production_environment()
        return WorkspaceConfig.from_env()


def load_config(config_path: Optional[str] = None) -> WorkspaceConfig:
    """Load configuration from file or environment"""
    if config_path and os.path.exists(config_path):
        # Load from JSON file if provided
        import json

        with open(config_path, "r") as f:
            config_data = json.load(f)
        return WorkspaceConfig(**config_data)
    else:
        # Load from environment
        return WorkspaceConfig.from_env()
