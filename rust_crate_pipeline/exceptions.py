"""
Exception hierarchy for the Rust Crate Pipeline.

Provides specific exception types for different failure scenarios,
enabling better error handling and debugging in production.
"""

from typing import Any, Dict, Optional


class PipelineError(Exception):
    """Base exception for all pipeline-related errors."""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.context = context or {}


class ConfigurationError(PipelineError):
    """Raised when configuration is invalid or missing required values."""


class NetworkError(PipelineError):
    """Base class for network-related errors."""


class APIError(NetworkError):
    """Raised when an API request fails."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, context)
        self.status_code = status_code
        self.response_body = response_body


class RateLimitError(APIError):
    """Raised when API rate limits are exceeded."""

    def __init__(
        self,
        message: str,
        retry_after: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, status_code=429, context=context)
        self.retry_after = retry_after


class EnrichmentError(PipelineError):
    """Raised when crate enrichment fails."""

    def __init__(
        self,
        message: str,
        crate_name: Optional[str] = None,
        stage: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, context)
        self.crate_name = crate_name
        self.stage = stage


class ScrapingError(PipelineError):
    """Raised when web scraping fails."""

    def __init__(
        self,
        message: str,
        url: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, context)
        self.url = url


class AIProcessingError(PipelineError):
    """Raised when AI/LLM processing fails."""

    def __init__(
        self,
        message: str,
        model: Optional[str] = None,
        prompt_tokens: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, context)
        self.model = model
        self.prompt_tokens = prompt_tokens


class ValidationError(PipelineError):
    """Raised when data validation fails."""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Any = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, context)
        self.field = field
        self.value = value


class CircuitBreakerError(NetworkError):
    """Raised when a circuit breaker is open."""

    def __init__(
        self,
        message: str,
        service: str,
        failure_count: int,
        last_failure_time: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, context)
        self.service = service
        self.failure_count = failure_count
        self.last_failure_time = last_failure_time
