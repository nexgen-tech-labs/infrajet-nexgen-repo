from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, AsyncGenerator
from dataclasses import dataclass
from logconfig.logger import logger


class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""
    pass


class RateLimitError(LLMProviderError):
    """Exception raised when rate limit is exceeded."""
    pass


class AuthenticationError(LLMProviderError):
    """Exception raised for authentication failures."""
    pass


class ConnectionError(LLMProviderError):
    """Exception raised for connection issues."""
    pass


@dataclass
class LLMConfig:
    """Configuration for LLM provider."""
    api_key: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 1000
    timeout: int = 30
    rate_limit_requests: int = 60
    rate_limit_window: int = 60  # seconds


@dataclass
class LLMRequest:
    """Request data for LLM generation."""
    prompt: str
    config: LLMConfig
    system_message: Optional[str] = None


@dataclass
class LLMResponse:
    """Response data from LLM generation."""
    content: str
    usage: Dict[str, Any]
    metadata: Dict[str, Any]


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.logger = logger
        self._request_count = 0

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate text using the LLM provider."""
        pass

    @abstractmethod
    async def stream_generate(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        """Stream generate text using the LLM provider."""
        pass

    @abstractmethod
    async def validate_connection(self) -> bool:
        """Validate connection to the LLM provider."""
        pass

    @abstractmethod
    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the provider."""
        pass

    def _log_request(self, method: str, **kwargs):
        """Log request details for monitoring."""
        self._request_count += 1
        self.logger.info(f"LLM Request: {method}, Count: {self._request_count}", **kwargs)