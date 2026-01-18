"""
WebSocket specific exception hierarchy.

This module defines comprehensive exception classes for WebSocket operations,
providing specific error types for connection management, real-time updates,
and error recovery scenarios.
"""

from typing import Optional, Dict, Any
from datetime import datetime
from .base_exceptions import BaseApplicationError


class WebSocketError(BaseApplicationError):
    """
    Base exception for WebSocket operations.

    All WebSocket related exceptions inherit from this base class.
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
        user_message: Optional[str] = None,
        troubleshooting_guide: Optional[str] = None,
        connection_id: Optional[str] = None,
        user_id: Optional[int] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            original_exception=original_exception,
            user_message=user_message,
            troubleshooting_guide=troubleshooting_guide,
        )
        self.connection_id = connection_id
        self.user_id = user_id
        if connection_id or user_id:
            self.details.update({"connection_id": connection_id, "user_id": user_id})


class WebSocketConnectionError(WebSocketError):
    """
    Exception raised when WebSocket connection fails.
    """

    def __init__(
        self,
        message: str = "WebSocket connection failed",
        connection_stage: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="WEBSOCKET_CONNECTION_FAILED",
            user_message="Failed to establish real-time connection. Some features may not work properly.",
            troubleshooting_guide="Check your internet connection and try refreshing the page.",
            **kwargs,
        )
        self.connection_stage = connection_stage
        self.details.update({"connection_stage": connection_stage})


class WebSocketAuthenticationError(WebSocketError):
    """
    Exception raised when WebSocket authentication fails.
    """

    def __init__(
        self,
        message: str = "WebSocket authentication failed",
        auth_token: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="WEBSOCKET_AUTH_FAILED",
            user_message="Real-time connection authentication failed. Please sign in again.",
            troubleshooting_guide="Sign out and sign back in to refresh your authentication.",
            **kwargs,
        )
        # Don't store the actual token in details for security
        self.details.update({"auth_token_provided": bool(auth_token)})


class WebSocketDisconnectionError(WebSocketError):
    """
    Exception raised when WebSocket disconnection occurs unexpectedly.
    """

    def __init__(
        self,
        message: str = "WebSocket connection lost",
        disconnect_reason: Optional[str] = None,
        was_clean: bool = False,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="WEBSOCKET_DISCONNECTED",
            user_message="Real-time connection lost. Attempting to reconnect...",
            troubleshooting_guide="The connection will automatically retry. If problems persist, refresh the page.",
            **kwargs,
        )
        self.disconnect_reason = disconnect_reason
        self.was_clean = was_clean
        self.details.update(
            {"disconnect_reason": disconnect_reason, "was_clean": was_clean}
        )


class WebSocketMessageError(WebSocketError):
    """
    Exception raised when WebSocket message processing fails.
    """

    def __init__(
        self,
        message: str = "WebSocket message processing failed",
        message_type: Optional[str] = None,
        message_data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="WEBSOCKET_MESSAGE_ERROR",
            user_message="Failed to process real-time update.",
            troubleshooting_guide="This is usually temporary. The system will continue to work normally.",
            **kwargs,
        )
        self.message_type = message_type
        # Store sanitized message data (remove sensitive info)
        sanitized_data = {}
        if message_data:
            for key, value in message_data.items():
                if key.lower() not in ["token", "password", "secret", "key"]:
                    sanitized_data[key] = str(value)[:100]  # Truncate long values
        self.details.update(
            {"message_type": message_type, "message_data": sanitized_data}
        )


class WebSocketBroadcastError(WebSocketError):
    """
    Exception raised when WebSocket broadcast fails.
    """

    def __init__(
        self,
        message: str = "WebSocket broadcast failed",
        event_type: Optional[str] = None,
        target_users: Optional[list] = None,
        failed_connections: Optional[list] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="WEBSOCKET_BROADCAST_FAILED",
            user_message="Failed to send real-time updates to some users.",
            troubleshooting_guide="Affected users may need to refresh their page to see the latest updates.",
            **kwargs,
        )
        self.event_type = event_type
        self.target_users = target_users or []
        self.failed_connections = failed_connections or []
        self.details.update(
            {
                "event_type": event_type,
                "target_user_count": len(self.target_users),
                "failed_connection_count": len(self.failed_connections),
            }
        )


class WebSocketRateLimitError(WebSocketError):
    """
    Exception raised when WebSocket rate limit is exceeded.
    """

    def __init__(
        self,
        message: str = "WebSocket rate limit exceeded",
        rate_limit_type: Optional[str] = None,
        current_rate: Optional[int] = None,
        limit: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="WEBSOCKET_RATE_LIMIT_EXCEEDED",
            user_message="Too many real-time requests. Please slow down.",
            troubleshooting_guide="Wait a moment before sending more requests through the real-time connection.",
            **kwargs,
        )
        self.rate_limit_type = rate_limit_type
        self.current_rate = current_rate
        self.limit = limit
        self.details.update(
            {
                "rate_limit_type": rate_limit_type,
                "current_rate": current_rate,
                "limit": limit,
            }
        )


class WebSocketSessionError(WebSocketError):
    """
    Exception raised when WebSocket session management fails.
    """

    def __init__(
        self,
        message: str = "WebSocket session error",
        session_id: Optional[str] = None,
        session_operation: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="WEBSOCKET_SESSION_ERROR",
            user_message="Real-time session error occurred.",
            troubleshooting_guide="Try refreshing the page to establish a new session.",
            **kwargs,
        )
        self.session_id = session_id
        self.session_operation = session_operation
        self.details.update(
            {"session_id": session_id, "session_operation": session_operation}
        )


class WebSocketHeartbeatError(WebSocketError):
    """
    Exception raised when WebSocket heartbeat/ping fails.
    """

    def __init__(
        self,
        message: str = "WebSocket heartbeat failed",
        last_heartbeat: Optional[datetime] = None,
        missed_heartbeats: int = 0,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="WEBSOCKET_HEARTBEAT_FAILED",
            user_message="Connection health check failed. Reconnecting...",
            troubleshooting_guide="The system will automatically attempt to reconnect.",
            **kwargs,
        )
        self.last_heartbeat = last_heartbeat
        self.missed_heartbeats = missed_heartbeats
        self.details.update(
            {
                "last_heartbeat": (
                    last_heartbeat.isoformat() if last_heartbeat else None
                ),
                "missed_heartbeats": missed_heartbeats,
            }
        )


def map_websocket_exception(
    websocket_exception: Exception,
    connection_id: Optional[str] = None,
    user_id: Optional[int] = None,
    operation: Optional[str] = None,
) -> WebSocketError:
    """
    Map WebSocket exception to our custom WebSocket exception hierarchy.

    Args:
        websocket_exception: Original WebSocket exception
        connection_id: Optional connection identifier
        user_id: Optional user identifier
        operation: Optional operation that was being performed

    Returns:
        Mapped custom exception
    """
    exception_name = websocket_exception.__class__.__name__
    error_message = str(websocket_exception)

    # Extract common details
    details = {
        "operation": operation,
        "original_exception_type": exception_name,
    }

    # Map specific WebSocket exceptions based on error message patterns
    if "connection" in error_message.lower() and "failed" in error_message.lower():
        return WebSocketConnectionError(
            message=error_message,
            connection_id=connection_id,
            user_id=user_id,
            details=details,
            original_exception=websocket_exception,
        )
    elif "auth" in error_message.lower() or "unauthorized" in error_message.lower():
        return WebSocketAuthenticationError(
            message=error_message,
            connection_id=connection_id,
            user_id=user_id,
            details=details,
            original_exception=websocket_exception,
        )
    elif "disconnect" in error_message.lower() or "closed" in error_message.lower():
        return WebSocketDisconnectionError(
            message=error_message,
            connection_id=connection_id,
            user_id=user_id,
            details=details,
            original_exception=websocket_exception,
        )
    elif "message" in error_message.lower():
        return WebSocketMessageError(
            message=error_message,
            connection_id=connection_id,
            user_id=user_id,
            details=details,
            original_exception=websocket_exception,
        )
    elif "rate limit" in error_message.lower() or "throttle" in error_message.lower():
        return WebSocketRateLimitError(
            message=error_message,
            connection_id=connection_id,
            user_id=user_id,
            details=details,
            original_exception=websocket_exception,
        )
    elif "heartbeat" in error_message.lower() or "ping" in error_message.lower():
        return WebSocketHeartbeatError(
            message=error_message,
            connection_id=connection_id,
            user_id=user_id,
            details=details,
            original_exception=websocket_exception,
        )
    else:
        # Generic WebSocket error
        return WebSocketError(
            message=error_message,
            connection_id=connection_id,
            user_id=user_id,
            details=details,
            original_exception=websocket_exception,
        )


def is_retryable_websocket_error(exception: Exception) -> bool:
    """
    Determine if a WebSocket exception is retryable.

    Args:
        exception: Exception to check

    Returns:
        True if the exception is retryable, False otherwise
    """
    retryable_types = (
        WebSocketConnectionError,
        WebSocketDisconnectionError,
        WebSocketHeartbeatError,
        WebSocketSessionError,
    )

    return isinstance(exception, retryable_types)


def get_websocket_error_severity(exception: Exception) -> str:
    """
    Get the severity level of a WebSocket error.

    Args:
        exception: Exception to evaluate

    Returns:
        Severity level: 'low', 'medium', 'high', or 'critical'
    """
    if isinstance(exception, WebSocketAuthenticationError):
        return "high"
    elif isinstance(exception, (WebSocketConnectionError, WebSocketDisconnectionError)):
        return "medium"
    elif isinstance(exception, (WebSocketRateLimitError, WebSocketHeartbeatError)):
        return "low"
    elif isinstance(exception, (WebSocketMessageError, WebSocketBroadcastError)):
        return "medium"
    else:
        return "medium"


def get_websocket_reconnect_delay(exception: Exception, attempt: int = 1) -> int:
    """
    Calculate reconnection delay for WebSocket based on exception type and attempt number.

    Args:
        exception: Exception that occurred
        attempt: Current reconnection attempt number (1-based)

    Returns:
        Delay in seconds before reconnection attempt
    """
    base_delay = 1

    if isinstance(exception, WebSocketAuthenticationError):
        # Don't retry auth errors automatically
        return 0

    elif isinstance(exception, WebSocketRateLimitError):
        # Longer delay for rate limit errors
        return min(base_delay * (3**attempt), 60)  # Max 1 minute

    elif isinstance(exception, WebSocketConnectionError):
        # Exponential backoff for connection errors
        return min(base_delay * (2**attempt), 30)  # Max 30 seconds

    elif isinstance(exception, WebSocketDisconnectionError):
        # Quick retry for unexpected disconnections
        return min(base_delay * attempt, 10)  # Max 10 seconds

    else:
        # Default exponential backoff
        return min(base_delay * (2**attempt), 20)  # Max 20 seconds
