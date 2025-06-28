# production_config.py
"""
Production configuration to reduce runtime warnings and optimize performance.
This file contains settings that can be imported to minimize verbose logging
and improve the user experience in production environments.
"""

import logging
import os
from typing import Any

# Production logging configuration


def configure_production_logging() -> None:
    """Configure logging for production to reduce verbose warnings"""

    # Don't use basicConfig here - let main.py handle it
    # Just set specific loggers to less verbose levels
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests_cache").setLevel(logging.WARNING)

    # If PRODUCTION environment variable is set, be even quieter
    if os.getenv("PRODUCTION", "false").lower() == "true":
        logging.getLogger().setLevel(logging.WARNING)
        logging.getLogger("rust_crate_pipeline").setLevel(logging.INFO)


# Production-optimized settings
PRODUCTION_SETTINGS: "dict[str, Any]" = {
    # Reduced retries to minimize warnings
    "max_retries": 2,
    "validation_retries": 2,
    # GitHub API management
    "github_rate_limit_threshold": 100,
    "github_critical_threshold": 50,
    # LLM settings
    "llm_timeout": 30,
    "llm_max_attempts": 2,
    # Logging preferences
    "quiet_mode": True,
    "log_level": "INFO",
    # Performance settings
    "batch_size": 10,
    "checkpoint_interval": 10,
    "cache_ttl": 3600,
}


def get_production_config() -> "dict[str, Any]":
    """Get production configuration dictionary"""
    return PRODUCTION_SETTINGS.copy()


def is_production() -> bool:
    """Check if running in production mode"""
    return os.getenv("PRODUCTION", "false").lower() == "true"


def setup_production_environment() -> "dict[str, Any]":
    """Set up the complete production environment"""
    configure_production_logging()

    # Set environment variables for quieter operation
    os.environ.setdefault("PYTHONWARNINGS", "ignore::UserWarning")

    if is_production():
        print("🚀 Production mode enabled - optimized for minimal warnings")
        return get_production_config()
    else:
        print("🔧 Development mode - full logging enabled")
        return {}
