from typing import Dict, Type, Any
from .base import BaseLLMProvider, LLMConfig
from .claude_provider import ClaudeProvider


class ProviderFactory:
    """Factory for creating LLM providers with dependency injection support."""

    _providers: Dict[str, Type[BaseLLMProvider]] = {
        "claude": ClaudeProvider,
    }

    @classmethod
    def register_provider(cls, name: str, provider_class: Type[BaseLLMProvider]):
        """Register a new provider type."""
        cls._providers[name] = provider_class

    @classmethod
    def create_provider(cls, provider_type: str, config: LLMConfig, **kwargs) -> BaseLLMProvider:
        """Create a provider instance based on type."""
        if provider_type not in cls._providers:
            raise ValueError(f"Unknown provider type: {provider_type}. Available: {list(cls._providers.keys())}")

        provider_class = cls._providers[provider_type]
        return provider_class(config, **kwargs)

    @classmethod
    def get_available_providers(cls) -> list[str]:
        """Get list of available provider types."""
        return list(cls._providers.keys())

    @classmethod
    def create_from_config(cls, config_dict: Dict[str, Any]) -> BaseLLMProvider:
        """Create provider from configuration dictionary."""
        provider_type = config_dict.get("provider_type", "claude")
        llm_config = LLMConfig(
            api_key=config_dict["api_key"],
            model=config_dict.get("model", "claude-3-5-sonnet-20240620"),
            temperature=config_dict.get("temperature", 0.7),
            max_tokens=config_dict.get("max_tokens", 1000),
            timeout=config_dict.get("timeout", 30),
            rate_limit_requests=config_dict.get("rate_limit_requests", 60),
            rate_limit_window=config_dict.get("rate_limit_window", 60)
        )
        return cls.create_provider(provider_type, llm_config)