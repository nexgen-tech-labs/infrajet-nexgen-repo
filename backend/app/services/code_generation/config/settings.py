from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, Field


class CodeGenerationSettings(BaseSettings):
    """Settings for code generation LLM providers."""

    # LLM Provider Settings
    LLM_PROVIDER_TYPE: str = "claude"
    LLM_API_KEY: Optional[str] = Field(None, env="LLM_API_KEY")
    LLM_MODEL: str = Field("claude-3-haiku-20240307", env="LLM_MODEL")
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 2000
    LLM_TIMEOUT: int = 30

    # Rate Limiting Settings
    RATE_LIMIT_REQUESTS: int = 60
    RATE_LIMIT_WINDOW: int = 60  # seconds
    REDIS_URL: str = "redis://localhost:6379/0"
    ENABLE_RATE_LIMITING: bool = True

    # Security Settings
    API_KEY_MIN_LENGTH: int = 20
    VALIDATE_API_KEY_ON_STARTUP: bool = True

    @field_validator("LLM_API_KEY")
    @classmethod
    def validate_api_key(cls, v: Optional[str]) -> Optional[str]:
        """Validate API key format and length if provided."""
        if v is None:
            return None
        min_length = 20  # Use constant instead of class attribute
        if not v or len(v.strip()) < min_length:
            raise ValueError(f"API key must be at least {min_length} characters long")
        return v.strip()

    @field_validator("LLM_TEMPERATURE")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        """Validate temperature is between 0 and 2."""
        if not 0 <= v <= 2:
            raise ValueError("Temperature must be between 0 and 2")
        return v

    @field_validator("LLM_MAX_TOKENS")
    @classmethod
    def validate_max_tokens(cls, v: int) -> int:
        """Validate max tokens is reasonable."""
        if v < 1 or v > 100000:
            raise ValueError("Max tokens must be between 1 and 100000")
        return v

    @field_validator("RATE_LIMIT_REQUESTS")
    @classmethod
    def validate_rate_limit(cls, v: int) -> int:
        """Validate rate limit is positive."""
        if v < 1:
            raise ValueError("Rate limit requests must be positive")
        return v

    def ensure_api_key_available(self):
        """Ensure API key is available when required."""
        if self.LLM_API_KEY is None:
            raise ValueError("LLM_API_KEY is required but not provided. Please set the LLM_API_KEY environment variable for production use.")

    def get_llm_config_dict(self) -> dict:
        """Get LLM configuration as dictionary for provider factory."""
        return {
            "provider_type": self.LLM_PROVIDER_TYPE,
            "api_key": self.LLM_API_KEY,
            "model": self.LLM_MODEL,
            "temperature": self.LLM_TEMPERATURE,
            "max_tokens": self.LLM_MAX_TOKENS,
            "timeout": self.LLM_TIMEOUT,
            "rate_limit_requests": self.RATE_LIMIT_REQUESTS,
            "rate_limit_window": self.RATE_LIMIT_WINDOW
        }

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_code_generation_settings() -> CodeGenerationSettings:
    """Get cached code generation settings instance."""
    return CodeGenerationSettings()