"""
Redis client configuration and utilities.

This module provides Redis connection management for WebSocket session
persistence and caching.
"""

import json
import logging
from typing import Optional, Any, Dict, List
from functools import lru_cache

import redis.asyncio as redis
from redis.asyncio import Redis

from app.core.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class RedisClient:
    """
    Redis client wrapper for WebSocket session management.

    Provides methods for storing and retrieving WebSocket session data,
    with automatic JSON serialization/deserialization.
    """

    def __init__(self):
        self._client: Optional[Redis] = None
        self._connected = False

    async def connect(self) -> bool:
        """
        Connect to Redis server.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            if settings.REDIS_URL:
                self._client = redis.from_url(
                    settings.REDIS_URL, encoding="utf-8", decode_responses=True
                )
            else:
                self._client = redis.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    db=settings.REDIS_DB,
                    password=settings.REDIS_PASSWORD,
                    encoding="utf-8",
                    decode_responses=True,
                )

            # Test connection
            await self._client.ping()
            self._connected = True
            logger.info("Redis connection established")
            return True

        except Exception as e:
            logger.warning(f"Redis connection failed: {str(e)}")
            self._connected = False
            return False

    async def disconnect(self):
        """Disconnect from Redis server."""
        if self._client:
            await self._client.close()
            self._connected = False
            logger.info("Redis connection closed")

    @property
    def is_connected(self) -> bool:
        """Check if Redis is connected."""
        return self._connected and self._client is not None

    async def set_session(
        self, session_id: str, session_data: Dict[str, Any], ttl: int = 3600
    ) -> bool:
        """
        Store WebSocket session data in Redis.

        Args:
            session_id: Session identifier
            session_data: Session data to store
            ttl: Time to live in seconds

        Returns:
            True if stored successfully, False otherwise
        """
        if not self.is_connected:
            return False

        try:
            key = f"websocket_session:{session_id}"
            value = json.dumps(session_data, default=str)
            await self._client.setex(key, ttl, value)
            return True
        except Exception as e:
            logger.error(f"Failed to store session {session_id}: {str(e)}")
            return False

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve WebSocket session data from Redis.

        Args:
            session_id: Session identifier

        Returns:
            Session data if found, None otherwise
        """
        if not self.is_connected:
            return None

        try:
            key = f"websocket_session:{session_id}"
            value = await self._client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve session {session_id}: {str(e)}")
            return None

    async def delete_session(self, session_id: str) -> bool:
        """
        Delete WebSocket session data from Redis.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted successfully, False otherwise
        """
        if not self.is_connected:
            return False

        try:
            key = f"websocket_session:{session_id}"
            result = await self._client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {str(e)}")
            return False

    async def update_session_heartbeat(self, session_id: str, ttl: int = 3600) -> bool:
        """
        Update session heartbeat timestamp and extend TTL.

        Args:
            session_id: Session identifier
            ttl: New time to live in seconds

        Returns:
            True if updated successfully, False otherwise
        """
        if not self.is_connected:
            return False

        try:
            key = f"websocket_session:{session_id}"
            # Check if session exists
            if await self._client.exists(key):
                # Extend TTL
                await self._client.expire(key, ttl)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to update session heartbeat {session_id}: {str(e)}")
            return False

    async def get_user_sessions(self, user_id: int) -> List[str]:
        """
        Get all session IDs for a user.

        Args:
            user_id: User identifier

        Returns:
            List of session IDs
        """
        if not self.is_connected:
            return []

        try:
            pattern = "websocket_session:*"
            session_keys = await self._client.keys(pattern)
            user_sessions = []

            for key in session_keys:
                session_data = await self._client.get(key)
                if session_data:
                    data = json.loads(session_data)
                    if data.get("user_id") == user_id:
                        session_id = key.replace("websocket_session:", "")
                        user_sessions.append(session_id)

            return user_sessions
        except Exception as e:
            logger.error(f"Failed to get user sessions for user {user_id}: {str(e)}")
            return []

    async def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions (Redis handles this automatically with TTL).

        Returns:
            Number of sessions cleaned up (always 0 for Redis with TTL)
        """
        # Redis automatically handles TTL expiration
        # This method is kept for interface compatibility
        return 0

    async def get_connection_count(self) -> int:
        """
        Get total number of active WebSocket sessions.

        Returns:
            Number of active sessions
        """
        if not self.is_connected:
            return 0

        try:
            pattern = "websocket_session:*"
            keys = await self._client.keys(pattern)
            return len(keys)
        except Exception as e:
            logger.error(f"Failed to get connection count: {str(e)}")
            return 0


@lru_cache()
def get_redis_client() -> RedisClient:
    """Get Redis client instance."""
    return RedisClient()
