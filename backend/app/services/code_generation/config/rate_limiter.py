import time
import asyncio
from typing import Optional
from redis.asyncio import Redis, ConnectionError as RedisConnectionError
from logconfig.logger import logger


class RateLimiter:
    """Redis-backed rate limiter using token bucket algorithm."""

    def __init__(self, redis_url: str, requests: int, window: int, key_prefix: str = "llm_rate_limit"):
        self.redis_url = redis_url
        self.requests = requests
        self.window = window
        self.key_prefix = key_prefix
        self._redis: Optional[Redis] = None

    async def _get_redis(self) -> Redis:
        """Get Redis connection with lazy initialization."""
        if self._redis is None:
            self._redis = Redis.from_url(self.redis_url)
        return self._redis

    async def is_allowed(self, key: str) -> bool:
        """Check if request is allowed under rate limit."""
        try:
            redis = await self._get_redis()
            full_key = f"{self.key_prefix}:{key}"
            now = time.time()

            # Remove expired entries
            await redis.zremrangebyscore(full_key, 0, now - self.window)

            # Count current requests in window
            count = await redis.zcard(full_key)

            if count < self.requests:
                # Add current request
                await redis.zadd(full_key, {str(now): now})
                # Set expiration for the key
                await redis.expire(full_key, self.window)
                logger.debug(f"Rate limit allowed for key: {key}, count: {count + 1}/{self.requests}")
                return True
            else:
                logger.warning(f"Rate limit exceeded for key: {key}, count: {count}/{self.requests}")
                return False

        except RedisConnectionError as e:
            logger.error(f"Redis connection error in rate limiter: {e}")
            # Allow request if Redis is down (fail-open)
            return True
        except Exception as e:
            logger.error(f"Unexpected error in rate limiter: {e}")
            return True

    async def get_remaining_requests(self, key: str) -> int:
        """Get remaining requests allowed in current window."""
        try:
            redis = await self._get_redis()
            full_key = f"{self.key_prefix}:{key}"
            now = time.time()

            # Clean up expired entries
            await redis.zremrangebyscore(full_key, 0, now - self.window)

            count = await redis.zcard(full_key)
            remaining = max(0, self.requests - count)
            return remaining

        except Exception as e:
            logger.error(f"Error getting remaining requests: {e}")
            return self.requests  # Return max if error

    async def reset(self, key: str):
        """Reset rate limit for a key."""
        try:
            redis = await self._get_redis()
            full_key = f"{self.key_prefix}:{key}"
            await redis.delete(full_key)
            logger.info(f"Rate limit reset for key: {key}")
        except Exception as e:
            logger.error(f"Error resetting rate limit: {e}")

    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None


class GlobalRateLimiter(RateLimiter):
    """Global rate limiter for all requests."""

    def __init__(self, redis_url: str, requests: int, window: int):
        super().__init__(redis_url, requests, window, "global_rate_limit")


class ProviderRateLimiter(RateLimiter):
    """Per-provider rate limiter."""

    def __init__(self, redis_url: str, requests: int, window: int, provider_name: str):
        super().__init__(redis_url, requests, window, f"provider_{provider_name}_rate_limit")