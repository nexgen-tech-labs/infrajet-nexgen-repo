"""
Supabase authentication specific exception hierarchy.

This module defines comprehensive exception classes for Supabase authentication
operations, providing specific error types for different failure scenarios
with detailed context, retry logic, and user-friendly messages.
"""

from typing import Optional, Dict, Any
from datetime import datetime
from .base_exceptions import BaseApplicationError


class SupabaseError(BaseApplicationError):
    """
    Base exception for Supabase operations.

    All Supabase related exceptions inherit from this base class.
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
        user_message: Optional[str] = None,
        troubleshooting_guide: Optional[str] = None,
        retryable: bool = False,
        user_id: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            original_exception=original_exception,
            user_message=user_message,
            troubleshooting_guide=troubleshooting_guide,
            retryable=retryable,
        )
        self.user_id = user_id
        if user_id:
            self.details.update({"user_id": user_id})


class SupabaseAuthenticationError(SupabaseError):
    """
    Exception raised when Supabase authentication fails.
    """

    def __init__(
        self,
        message: str = "Supabase authentication failed",
        auth_step: Optional[str] = None,
        token_type: Optional[str] = None,
        **kwargs,
    ):
        # Remove conflicting parameters
        kwargs.pop('error_code', None)
        kwargs.pop('user_message', None)
        kwargs.pop('troubleshooting_guide', None)
        super().__init__(
            message=message,
            error_code="SUPABASE_AUTH_FAILED",
            user_message="Authentication failed. Please sign in again.",
            troubleshooting_guide="Sign out and sign back in. If problems persist, contact support.",
            **kwargs,
        )
        self.severity = "high"
        self.auth_step = auth_step
        self.token_type = token_type
        self.details.update({
            "auth_step": auth_step,
            "token_type": token_type,
        })


class SupabaseTokenError(SupabaseError):
    """
    Exception raised when Supabase token operations fail.
    """

    def __init__(
        self,
        message: str = "Supabase token error",
        token_type: Optional[str] = None,
        token_issue: Optional[str] = None,
        **kwargs,
    ):
        # Remove conflicting parameters
        kwargs.pop('error_code', None)
        kwargs.pop('user_message', None)
        kwargs.pop('troubleshooting_guide', None)
        super().__init__(
            message=message,
            error_code="SUPABASE_TOKEN_ERROR",
            user_message="Authentication token error. Please sign in again.",
            troubleshooting_guide="Sign out and sign back in to refresh your authentication token.",
            **kwargs,
        )
        self.severity = "high"
        self.token_type = token_type
        self.token_issue = token_issue
        self.details.update({
            "token_type": token_type,
            "token_issue": token_issue,
        })


class SupabaseTokenExpiredError(SupabaseTokenError):
    """
    Exception raised when Supabase token has expired.
    """

    def __init__(
        self,
        message: str = "Supabase token has expired",
        expired_at: Optional[datetime] = None,
        **kwargs,
    ):
        # Remove conflicting parameters
        kwargs.pop('error_code', None)
        kwargs.pop('user_message', None)
        kwargs.pop('troubleshooting_guide', None)
        kwargs.pop('token_issue', None)
        super().__init__(
            message=message,
            error_code="SUPABASE_TOKEN_EXPIRED",
            user_message="Your session has expired. Please sign in again.",
            troubleshooting_guide="Sign in again to get a new authentication token.",
            token_issue="expired",
            **kwargs,
        )
        self.expired_at = expired_at
        self.details.update({
            "expired_at": expired_at.isoformat() if expired_at else None,
        })


class SupabaseTokenInvalidError(SupabaseTokenError):
    """
    Exception raised when Supabase token is invalid or malformed.
    """

    def __init__(
        self,
        message: str = "Supabase token is invalid",
        validation_error: Optional[str] = None,
        **kwargs,
    ):
        # Remove conflicting parameters
        kwargs.pop('error_code', None)
        kwargs.pop('user_message', None)
        kwargs.pop('troubleshooting_guide', None)
        kwargs.pop('token_issue', None)
        super().__init__(
            message=message,
            error_code="SUPABASE_TOKEN_INVALID",
            user_message="Invalid authentication token. Please sign in again.",
            troubleshooting_guide="Sign out and sign back in to get a valid authentication token.",
            token_issue="invalid",
            **kwargs,
        )
        self.validation_error = validation_error
        self.details.update({
            "validation_error": validation_error,
        })


class SupabaseTokenMissingError(SupabaseTokenError):
    """
    Exception raised when Supabase token is missing.
    """

    def __init__(
        self,
        message: str = "Supabase token is missing",
        **kwargs,
    ):
        # Remove conflicting parameters
        kwargs.pop('error_code', None)
        kwargs.pop('user_message', None)
        kwargs.pop('troubleshooting_guide', None)
        kwargs.pop('token_issue', None)
        super().__init__(
            message=message,
            error_code="SUPABASE_TOKEN_MISSING",
            user_message="Authentication required. Please sign in.",
            troubleshooting_guide="Sign in to access this resource.",
            token_issue="missing",
            **kwargs,
        )


class SupabaseUserValidationError(SupabaseError):
    """
    Exception raised when Supabase user validation fails.
    """

    def __init__(
        self,
        message: str = "Supabase user validation failed",
        validation_step: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs,
    ):
        # Remove conflicting parameters
        kwargs.pop('error_code', None)
        kwargs.pop('user_message', None)
        kwargs.pop('troubleshooting_guide', None)
        super().__init__(
            message=message,
            error_code="SUPABASE_USER_VALIDATION_FAILED",
            user_message="User validation failed. Please try signing in again.",
            troubleshooting_guide="Sign out and sign back in. If problems persist, contact support.",
            user_id=user_id,
            **kwargs,
        )
        self.severity = "high"
        self.validation_step = validation_step
        self.details.update({
            "validation_step": validation_step,
        })


class SupabaseUserNotFoundError(SupabaseUserValidationError):
    """
    Exception raised when user is not found in Supabase users table.
    """

    def __init__(
        self,
        message: str = "User not found in Supabase",
        user_id: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="SUPABASE_USER_NOT_FOUND",
            user_message="User account not found. Please contact support.",
            troubleshooting_guide="Contact support if you believe your account should exist.",
            validation_step="user_lookup",
            user_id=user_id,
            **kwargs,
        )


class SupabaseServiceError(SupabaseError):
    """
    Exception raised when Supabase service operations fail.
    """

    def __init__(
        self,
        message: str = "Supabase service error",
        service_operation: Optional[str] = None,
        status_code: Optional[int] = None,
        **kwargs,
    ):
        # Remove conflicting parameters
        kwargs.pop('error_code', None)
        kwargs.pop('user_message', None)
        kwargs.pop('troubleshooting_guide', None)
        kwargs.pop('retryable', None)
        super().__init__(
            message=message,
            error_code="SUPABASE_SERVICE_ERROR",
            user_message="Service temporarily unavailable. Please try again later.",
            troubleshooting_guide="Wait a few minutes and try again. If the problem persists, contact support.",
            retryable=True,
            **kwargs,
        )
        self.severity = "medium"
        self.service_operation = service_operation
        self.status_code = status_code
        self.details.update({
            "service_operation": service_operation,
            "status_code": status_code,
        })


class SupabaseConnectionError(SupabaseServiceError):
    """
    Exception raised when connection to Supabase fails.
    """

    def __init__(
        self,
        message: str = "Failed to connect to Supabase",
        connection_type: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="SUPABASE_CONNECTION_ERROR",
            user_message="Unable to connect to authentication service. Please try again.",
            troubleshooting_guide="Check your internet connection and try again.",
            service_operation="connection",
            **kwargs,
        )
        self.connection_type = connection_type
        self.details.update({
            "connection_type": connection_type,
        })


class SupabaseRateLimitError(SupabaseError):
    """
    Exception raised when Supabase rate limits are exceeded.
    """

    def __init__(
        self,
        message: str = "Supabase rate limit exceeded",
        limit_type: Optional[str] = None,
        retry_after: Optional[int] = None,
        **kwargs,
    ):
        # Remove conflicting parameters
        kwargs.pop('error_code', None)
        kwargs.pop('user_message', None)
        kwargs.pop('troubleshooting_guide', None)
        kwargs.pop('retryable', None)
        super().__init__(
            message=message,
            error_code="SUPABASE_RATE_LIMIT_EXCEEDED",
            user_message="Too many requests. Please wait before trying again.",
            troubleshooting_guide="Wait for the specified time before making another request.",
            retryable=True,
            **kwargs,
        )
        self.severity = "low"
        self.limit_type = limit_type
        self.retry_after = retry_after
        self.details.update({
            "limit_type": limit_type,
            "retry_after": retry_after,
        })


class SupabaseConfigurationError(SupabaseError):
    """
    Exception raised when Supabase configuration is invalid.
    """

    def __init__(
        self,
        message: str = "Supabase configuration error",
        config_key: Optional[str] = None,
        config_issue: Optional[str] = None,
        **kwargs,
    ):
        # Remove conflicting parameters
        kwargs.pop('error_code', None)
        kwargs.pop('user_message', None)
        kwargs.pop('troubleshooting_guide', None)
        super().__init__(
            message=message,
            error_code="SUPABASE_CONFIGURATION_ERROR",
            user_message="System configuration error. Please contact support.",
            troubleshooting_guide="Contact your system administrator to check the Supabase configuration.",
            **kwargs,
        )
        self.severity = "critical"
        self.config_key = config_key
        self.config_issue = config_issue
        self.details.update({
            "config_key": config_key,
            "config_issue": config_issue,
        })


def map_supabase_exception(
    supabase_exception: Exception,
    operation: Optional[str] = None,
    user_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> SupabaseError:
    """
    Map Supabase client exception to our custom exception hierarchy.

    Args:
        supabase_exception: Original Supabase exception
        operation: Optional operation that was being performed
        user_id: Optional user ID context
        context: Optional additional context

    Returns:
        Mapped custom exception
    """
    exception_name = supabase_exception.__class__.__name__
    error_message = str(supabase_exception)
    
    # Create details dictionary
    details = {
        "operation": operation,
        "context": context or {},
    }

    # Map specific Supabase exceptions based on error message patterns
    if "token" in error_message.lower():
        if "expired" in error_message.lower():
            return SupabaseTokenExpiredError(
                message=error_message,
                details=details,
                original_exception=supabase_exception,
                user_id=user_id,
            )
        elif "invalid" in error_message.lower() or "malformed" in error_message.lower():
            return SupabaseTokenInvalidError(
                message=error_message,
                details=details,
                original_exception=supabase_exception,
                user_id=user_id,
            )
        else:
            return SupabaseTokenError(
                message=error_message,
                details=details,
                original_exception=supabase_exception,
                user_id=user_id,
            )
    elif "auth" in error_message.lower() or "authentication" in error_message.lower():
        return SupabaseAuthenticationError(
            message=error_message,
            details=details,
            original_exception=supabase_exception,
            user_id=user_id,
        )
    elif "user not found" in error_message.lower() or "not found" in error_message.lower():
        return SupabaseUserNotFoundError(
            message=error_message,
            details=details,
            original_exception=supabase_exception,
            user_id=user_id,
        )
    elif "rate limit" in error_message.lower() or "429" in error_message:
        return SupabaseRateLimitError(
            message=error_message,
            details=details,
            original_exception=supabase_exception,
            user_id=user_id,
        )
    elif "connection" in error_message.lower() or "network" in error_message.lower():
        return SupabaseConnectionError(
            message=error_message,
            details=details,
            original_exception=supabase_exception,
            user_id=user_id,
        )
    elif "config" in error_message.lower():
        return SupabaseConfigurationError(
            message=error_message,
            details=details,
            original_exception=supabase_exception,
            user_id=user_id,
        )
    else:
        # Generic Supabase error
        return SupabaseError(
            message=error_message,
            details=details,
            original_exception=supabase_exception,
            user_id=user_id,
        )


def is_retryable_supabase_error(exception: Exception) -> bool:
    """
    Determine if a Supabase exception is retryable.

    Args:
        exception: Exception to check

    Returns:
        True if the exception is retryable, False otherwise
    """
    retryable_types = (
        SupabaseServiceError,
        SupabaseConnectionError,
        SupabaseRateLimitError,
    )

    return isinstance(exception, retryable_types)


def get_supabase_error_severity(exception: Exception) -> str:
    """
    Get the severity level of a Supabase error.

    Args:
        exception: Exception to evaluate

    Returns:
        Severity level: 'low', 'medium', 'high', or 'critical'
    """
    if isinstance(exception, (SupabaseConfigurationError,)):
        return "critical"
    elif isinstance(exception, (SupabaseAuthenticationError, SupabaseTokenError, SupabaseUserValidationError)):
        return "high"
    elif isinstance(exception, (SupabaseServiceError, SupabaseUserNotFoundError)):
        return "medium"
    elif isinstance(exception, (SupabaseRateLimitError, SupabaseConnectionError)):
        return "low"
    else:
        return "medium"


def get_supabase_retry_delay(exception: Exception, attempt: int = 1) -> int:
    """
    Calculate retry delay for Supabase operations based on exception type and attempt number.

    Args:
        exception: Exception that occurred
        attempt: Current retry attempt number (1-based)

    Returns:
        Delay in seconds before retry
    """
    base_delay = 1

    if isinstance(exception, SupabaseRateLimitError):
        # Use retry_after if provided, otherwise exponential backoff
        if hasattr(exception, "retry_after") and exception.retry_after:
            return exception.retry_after
        return min(60 * attempt, 300)  # Max 5 minutes

    elif isinstance(exception, SupabaseConnectionError):
        # Exponential backoff for connection errors
        return min(base_delay * (2**attempt), 60)  # Max 1 minute

    elif isinstance(exception, SupabaseServiceError):
        # Linear backoff for service errors
        return min(base_delay * attempt, 30)  # Max 30 seconds

    else:
        # Default exponential backoff
        return min(base_delay * (2**attempt), 30)  # Max 30 seconds