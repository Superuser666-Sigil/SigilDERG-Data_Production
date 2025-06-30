"""
Resilient HTTP client with enterprise-grade reliability features.

Includes:
- Rate limiting
- Circuit breakers
- Exponential backoff with jitter
- Request retries
- Timeout management
- Connection pooling
"""

import random
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional, Tuple, Type

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Try to import async HTTP client
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    httpx = None  # type: ignore

from .exceptions import CircuitBreakerError, NetworkError, RateLimitError
from .observability import metrics_collector, tracer


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    calls: int = 100
    period: float = 60.0  # seconds
    burst: int = 10  # additional burst capacity


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5
    recovery_timeout: float = 30.0  # seconds
    expected_exception: Type[Exception] = NetworkError
    half_open_calls: int = 1


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    backoff_factor: float = 1.0
    max_backoff: float = 60.0
    jitter: float = 0.1
    retry_on_status: set = field(
        default_factory=lambda: {429, 500, 502, 503, 504}
    )


class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.tokens = config.calls
        self.max_tokens = config.calls + config.burst
        self.refill_rate = config.calls / config.period
        self.last_refill = time.time()
        self.lock = threading.Lock()

    def acquire(self, tokens: int = 1) -> Tuple[bool, float]:
        """
        Try to acquire tokens. Returns (success, wait_time).

        If successful, wait_time is 0.
        If rate limited, wait_time is seconds until tokens available.
        """
        with self.lock:
            now = time.time()
            self._refill(now)

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True, 0.0
            else:
                # Calculate wait time
                needed_tokens = tokens - self.tokens
                wait_time = needed_tokens / self.refill_rate
                return False, wait_time

    def _refill(self, now: float):
        """Refill tokens based on elapsed time."""
        elapsed = now - self.last_refill
        new_tokens = elapsed * self.refill_rate
        self.tokens = min(self.tokens + new_tokens, self.max_tokens)
        self.last_refill = now


class CircuitBreaker:
    """Circuit breaker pattern implementation."""

    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.half_open_calls = 0
        self.lock = threading.Lock()

    def call(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        """Execute a function with circuit breaker protection."""
        with self.lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_calls = 0
                else:
                    raise CircuitBreakerError(
                        f"Circuit breaker {self.name} is OPEN",
                        service=self.name,
                        failure_count=self.failure_count,
                        last_failure_time=self.last_failure_time
                    )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.config.expected_exception:
            self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return False
        return time.time() - self.last_failure_time >= self.config.recovery_timeout

    def _on_success(self):
        """Handle successful call."""
        with self.lock:
            if self.state == CircuitState.HALF_OPEN:
                self.half_open_calls += 1
                if self.half_open_calls >= self.config.half_open_calls:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    metrics_collector.increment(
                        "circuit_breaker_state_change",
                        tags={"service": self.name, "state": "closed"}
                    )

    def _on_failure(self):
        """Handle failed call."""
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                metrics_collector.increment(
                    "circuit_breaker_state_change",
                    tags={"service": self.name, "state": "open"}
                )
            elif (self.state == CircuitState.CLOSED and
                  self.failure_count >= self.config.failure_threshold):
                self.state = CircuitState.OPEN
                metrics_collector.increment(
                    "circuit_breaker_state_change",
                    tags={"service": self.name, "state": "open"}
                )


class ResilientHTTPClient:
    """Synchronous HTTP client with resilience features."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        rate_limit_config: Optional[RateLimitConfig] = None,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
        retry_config: Optional[RetryConfig] = None,
        timeout: float = 30.0,
        headers: Optional[Dict[str, str]] = None
    ):
        self.base_url = base_url
        self.timeout = timeout
        self.headers = headers or {}

        # Initialize components
        self.rate_limiter = RateLimiter(rate_limit_config or RateLimitConfig())
        self.circuit_breaker = CircuitBreaker(
            name=base_url or "default",
            config=circuit_breaker_config or CircuitBreakerConfig()
        )
        self.retry_config = retry_config or RetryConfig()

        # Setup session with connection pooling
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create a requests session with proper configuration."""
        session = requests.Session()

        # Configure retries at transport level
        retry_strategy = Retry(
            total=self.retry_config.max_retries,
            status_forcelist=list(self.retry_config.retry_on_status),
            backoff_factor=self.retry_config.backoff_factor
        )

        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=20,
            pool_maxsize=20
        )

        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers.update(self.headers)

        return session

    def _wait_with_backoff(self, attempt: int) -> float:
        """Calculate backoff time with jitter."""
        base_wait = min(
            self.retry_config.backoff_factor * (2 ** attempt),
            self.retry_config.max_backoff
        )
        jitter = base_wait * self.retry_config.jitter * random.random()
        return base_wait + jitter

    @tracer.trace("http_request")
    def request(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> requests.Response:
        """Make an HTTP request with full resilience features."""
        if self.base_url and not url.startswith(("http://", "https://")):
            url = f"{self.base_url.rstrip('/')}/{url.lstrip('/')}"

        # Set default timeout
        kwargs.setdefault("timeout", self.timeout)

        # Check rate limit
        acquired, wait_time = self.rate_limiter.acquire()
        if not acquired:
            metrics_collector.increment("rate_limit_hit", tags={"url": url})
            raise RateLimitError(
                f"Rate limit exceeded. Retry after {wait_time:.2f} seconds",
                retry_after=int(wait_time)
            )

        # Execute with circuit breaker
        def execute_request():
            with metrics_collector.timer("http_request_duration", {"method": method}):
                response = self.session.request(method, url, **kwargs)

                # Raise for status codes that should trigger circuit breaker
                if response.status_code >= 500:
                    response.raise_for_status()

                return response

        try:
            response = self.circuit_breaker.call(execute_request)

            # Check for rate limit headers
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", 60)
                raise RateLimitError(
                    f"API rate limit hit: {response.text}",
                    retry_after=int(retry_after)
                )

            metrics_collector.increment(
                "http_requests_total",
                tags={"method": method, "status": str(response.status_code)}
            )

            return response

        except requests.RequestException as e:
            metrics_collector.increment(
                "http_requests_total",
                tags={
                    "method": method,
                    "status": "error",
                    "error_type": type(e).__name__})
            raise NetworkError(f"Request failed: {e}") from e

    def get(self, url: str, **kwargs) -> requests.Response:
        """GET request."""
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response:
        """POST request."""
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs) -> requests.Response:
        """PUT request."""
        return self.request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs) -> requests.Response:
        """DELETE request."""
        return self.request("DELETE", url, **kwargs)

    def close(self):
        """Close the HTTP session."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Async version if httpx is available
if HTTPX_AVAILABLE and httpx is not None:
    class AsyncResilientHTTPClient:
        """Asynchronous HTTP client with resilience features."""

        def __init__(
            self,
            base_url: Optional[str] = None,
            rate_limit_config: Optional[RateLimitConfig] = None,
            circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
            retry_config: Optional[RetryConfig] = None,
            timeout: float = 30.0,
            headers: Optional[Dict[str, str]] = None
        ):
            self.base_url = base_url
            self.timeout = timeout
            self.headers = headers or {}

            # Initialize components
            rate_config = rate_limit_config or RateLimitConfig()
            self.rate_limiter = RateLimiter(rate_config)

            cb_config = circuit_breaker_config or CircuitBreakerConfig()
            self.circuit_breaker = CircuitBreaker(
                name=base_url or "default",
                config=cb_config
            )
            self.retry_config = retry_config or RetryConfig()

            # Create async client - only if httpx is available
            if httpx is not None:
                client_kwargs = {
                    "timeout": timeout,
                    "headers": headers
                }
                if base_url is not None:
                    client_kwargs["base_url"] = base_url
                self.client = httpx.AsyncClient(**client_kwargs)
            else:
                self.client = None

        async def request(
            self,
            method: str,
            url: str,
            **kwargs
        ):
            """Make an async HTTP request with full resilience features."""
            if self.client is None:
                raise RuntimeError("httpx not available for async requests")

            # Implementation would go here
            # For now, just a placeholder
            return await self.client.request(method, url, **kwargs)

        async def close(self):
            """Close the HTTP client."""
            if self.client is not None:
                await self.client.aclose()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            await self.close()
else:
    # httpx is not available - AsyncResilientHTTPClient will not be defined
    pass
