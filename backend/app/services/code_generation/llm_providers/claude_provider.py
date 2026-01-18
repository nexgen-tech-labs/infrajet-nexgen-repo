import asyncio
from typing import Any, Dict, AsyncGenerator
from anthropic import AsyncAnthropic, APIError, AuthenticationError as AnthropicAuthError, RateLimitError as AnthropicRateLimitError

from .base import (
    BaseLLMProvider,
    LLMRequest,
    LLMResponse,
    LLMConfig,
    RateLimitError,
    AuthenticationError,
    ConnectionError
)


class ClaudeProvider(BaseLLMProvider):
    """Claude LLM provider implementation using Anthropic SDK."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.client = AsyncAnthropic(api_key=config.api_key)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate text using Claude."""
        try:
            messages = [{"role": "user", "content": request.prompt}]
            system = request.system_message if request.system_message else None

            kwargs = {
                "model": request.config.model,
                "messages": messages,
                "temperature": request.config.temperature,
                "max_tokens": request.config.max_tokens,
                "timeout": request.config.timeout
            }
            if system:
                kwargs["system"] = system

            response = await self.client.messages.create(**kwargs)

            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens
            }

            self._log_request("generate", model=request.config.model, **usage)

            return LLMResponse(
                content=response.content[0].text,
                usage=usage,
                metadata={
                    "model": response.model,
                    "stop_reason": response.stop_reason
                }
            )

        except AnthropicRateLimitError:
            self.logger.warning("Claude rate limit exceeded")
            raise RateLimitError("Rate limit exceeded")
        except AnthropicAuthError:
            self.logger.error("Claude authentication failed")
            raise AuthenticationError("Invalid API key")
        except APIError as e:
            self.logger.error(f"Claude API error: {e}")
            raise ConnectionError(f"API error: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error in Claude generate: {e}")
            raise ConnectionError(f"Unexpected error: {e}")

    async def stream_generate(self, request: LLMRequest) -> AsyncGenerator[str, None]:
        """Stream generate text using Claude."""
        try:
            messages = [{"role": "user", "content": request.prompt}]
            system = request.system_message if request.system_message else None

            kwargs = {
                "model": request.config.model,
                "messages": messages,
                "temperature": request.config.temperature,
                "max_tokens": request.config.max_tokens,
                "timeout": request.config.timeout
            }
            if system:
                kwargs["system"] = system

            async with self.client.messages.stream(**kwargs) as stream:
                async for chunk in stream:
                    if chunk.type == "content_block_delta" and hasattr(chunk.delta, 'text'):
                        yield chunk.delta.text

        except AnthropicRateLimitError:
            self.logger.warning("Claude rate limit exceeded during streaming")
            raise RateLimitError("Rate limit exceeded")
        except AnthropicAuthError:
            self.logger.error("Claude authentication failed during streaming")
            raise AuthenticationError("Invalid API key")
        except APIError as e:
            self.logger.error(f"Claude API error during streaming: {e}")
            raise ConnectionError(f"API error: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error in Claude stream: {e}")
            raise ConnectionError(f"Unexpected error: {e}")

    async def validate_connection(self) -> bool:
        """Validate connection to Claude API."""
        try:
            # Test with a minimal request
            await self.client.messages.create(
                model="claude-3-haiku-20240307",
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=1,
                timeout=10
            )
            self.logger.info("Claude connection validated successfully")
            return True
        except Exception as e:
            self.logger.error(f"Claude connection validation failed: {e}")
            return False

    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of Claude provider."""
        is_connected = await self.validate_connection()
        return {
            "provider": "claude",
            "connected": is_connected,
            "model": self.config.model,
            "request_count": self._request_count,
            "rate_limit_requests": self.config.rate_limit_requests,
            "rate_limit_window": self.config.rate_limit_window
        }