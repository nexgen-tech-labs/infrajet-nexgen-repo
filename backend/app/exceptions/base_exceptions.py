"""
Base exception classes for the application.

This module defines the base exception hierarchy that all application-specific
exceptions inherit from, providing consistent error handling and logging.
"""

from typing import Optional, Dict, Any
from datetime import datetime
import traceback


class BaseApplicationError(Exception):
    """
    Base exception class for all application-specific errors.

    This class provides a consistent interface for error handling,
    logging, and user-friendly error messages across the application.
    """

    def __init__(
        self,
        message: str,
        **kwargs
    ):
        """
        Initialize base application error.

        Args:
            message: Technical error message for developers
            **kwargs: All other parameters (error_code, details, original_exception, etc.)
        """
        # Extract parameters from kwargs
        error_code = kwargs.pop('error_code', None)
        details = kwargs.pop('details', None) or {}
        original_exception = kwargs.pop('original_exception', None)
        user_message = kwargs.pop('user_message', None)
        troubleshooting_guide = kwargs.pop('troubleshooting_guide', None)
        severity = kwargs.pop('severity', 'medium')
        retryable = kwargs.pop('retryable', False)

        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details
        self.original_exception = original_exception
        self.user_message = user_message or message
        self.troubleshooting_guide = troubleshooting_guide
        self.severity = severity
        self.retryable = retryable
        self.timestamp = datetime.utcnow()

        # Add any remaining kwargs to details
        self.details.update(kwargs)

        # Add original exception details if available
        if original_exception:
            self.details.update(
                {
                    "original_exception_type": original_exception.__class__.__name__,
                    "original_exception_message": str(original_exception),
                    "traceback": (
                        traceback.format_exception(
                            type(original_exception),
                            original_exception,
                            original_exception.__traceback__,
                        )
                        if original_exception.__traceback__
                        else None
                    ),
                }
            )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert exception to dictionary for serialization.

        Returns:
            Dictionary representation of the exception
        """
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "user_message": self.user_message,
            "troubleshooting_guide": self.troubleshooting_guide,
            "severity": self.severity,
            "retryable": self.retryable,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }

    def to_user_dict(self) -> Dict[str, Any]:
        """
        Convert exception to user-safe dictionary (no sensitive details).

        Returns:
            User-safe dictionary representation
        """
        return {
            "error_code": self.error_code,
            "message": self.user_message,
            "troubleshooting_guide": self.troubleshooting_guide,
            "retryable": self.retryable,
            "timestamp": self.timestamp.isoformat(),
        }

    def __str__(self) -> str:
        """String representation of the exception."""
        parts = [self.message]
        if self.error_code:
            parts.append(f"Code: {self.error_code}")
        if self.severity:
            parts.append(f"Severity: {self.severity}")
        return " | ".join(parts)


class ValidationError(BaseApplicationError):
    """
    Exception raised when input validation fails.
    """

    def __init__(
        self,
        message: str = "Validation failed",
        field: Optional[str] = None,
        value: Optional[Any] = None,
        validation_rule: Optional[str] = None,
        **kwargs,
    ):
        kwargs.setdefault('error_code', 'VALIDATION_ERROR')
        kwargs.setdefault('user_message', 'The provided data is invalid. Please check your input and try again.')
        kwargs.setdefault('troubleshooting_guide', 'Verify that all required fields are provided and meet the specified format requirements.')
        kwargs.setdefault('severity', 'medium')
        
        super().__init__(message=message, **kwargs)
        self.field = field
        self.value = value
        self.validation_rule = validation_rule
        self.details.update(
            {
                "field": field,
                "value": str(value) if value is not None else None,
                "validation_rule": validation_rule,
            }
        )


class AuthenticationError(BaseApplicationError):
    """
    Exception raised when authentication fails.
    """

    def __init__(
        self,
        message: str = "Authentication failed",
        auth_method: Optional[str] = None,
        **kwargs,
    ):
        kwargs.setdefault('error_code', 'AUTHENTICATION_ERROR')
        kwargs.setdefault('user_message', 'Authentication failed. Please check your credentials and try again.')
        kwargs.setdefault('troubleshooting_guide', 'Verify your username and password, or contact support if the problem persists.')
        kwargs.setdefault('severity', 'high')
        
        super().__init__(message=message, **kwargs)
        self.auth_method = auth_method
        self.details.update({"auth_method": auth_method})


class AuthorizationError(BaseApplicationError):
    """
    Exception raised when authorization fails.
    """

    def __init__(
        self,
        message: str = "Access denied",
        required_permission: Optional[str] = None,
        user_role: Optional[str] = None,
        **kwargs,
    ):
        kwargs.setdefault('error_code', 'AUTHORIZATION_ERROR')
        kwargs.setdefault('user_message', "You don't have permission to perform this action.")
        kwargs.setdefault('troubleshooting_guide', 'Contact your administrator to request the necessary permissions.')
        kwargs.setdefault('severity', 'high')
        
        super().__init__(message=message, **kwargs)
        self.required_permission = required_permission
        self.user_role = user_role
        self.details.update(
            {"required_permission": required_permission, "user_role": user_role}
        )


class ResourceNotFoundError(BaseApplicationError):
    """
    Exception raised when a requested resource is not found.
    """

    def __init__(
        self,
        message: str = "Resource not found",
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        **kwargs,
    ):
        kwargs.setdefault('error_code', 'RESOURCE_NOT_FOUND')
        kwargs.setdefault('user_message', 'The requested resource could not be found.')
        kwargs.setdefault('troubleshooting_guide', 'Verify the resource identifier and ensure you have access to it.')
        kwargs.setdefault('severity', 'medium')
        
        super().__init__(message=message, **kwargs)
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.details.update(
            {"resource_type": resource_type, "resource_id": resource_id}
        )


class ResourceConflictError(BaseApplicationError):
    """
    Exception raised when a resource conflict occurs.
    """

    def __init__(
        self,
        message: str = "Resource conflict",
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        conflict_reason: Optional[str] = None,
        **kwargs,
    ):
        kwargs.setdefault('error_code', 'RESOURCE_CONFLICT')
        kwargs.setdefault('user_message', 'The operation conflicts with the current state of the resource.')
        kwargs.setdefault('troubleshooting_guide', 'Refresh the resource and try again, or resolve the conflict manually.')
        kwargs.setdefault('severity', 'medium')
        
        super().__init__(message=message, **kwargs)
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.conflict_reason = conflict_reason
        self.details.update(
            {
                "resource_type": resource_type,
                "resource_id": resource_id,
                "conflict_reason": conflict_reason,
            }
        )


class ServiceUnavailableError(BaseApplicationError):
    """
    Exception raised when a service is temporarily unavailable.
    """

    def __init__(
        self,
        message: str = "Service temporarily unavailable",
        service_name: Optional[str] = None,
        retry_after: Optional[int] = None,
        **kwargs,
    ):
        kwargs.setdefault('error_code', 'SERVICE_UNAVAILABLE')
        kwargs.setdefault('user_message', 'The service is temporarily unavailable. Please try again later.')
        kwargs.setdefault('troubleshooting_guide', 'Wait a few minutes and try again. If the problem persists, contact support.')
        kwargs.setdefault('severity', 'low')
        kwargs.setdefault('retryable', True)
        
        super().__init__(message=message, **kwargs)
        self.service_name = service_name
        self.retry_after = retry_after
        self.details.update({"service_name": service_name, "retry_after": retry_after})


class RateLimitError(BaseApplicationError):
    """
    Exception raised when rate limits are exceeded.
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        limit_type: Optional[str] = None,
        retry_after: Optional[int] = None,
        **kwargs,
    ):
        kwargs.setdefault('error_code', 'RATE_LIMIT_EXCEEDED')
        kwargs.setdefault('user_message', 'Too many requests. Please wait before trying again.')
        kwargs.setdefault('troubleshooting_guide', 'Wait for the specified time before making another request.')
        kwargs.setdefault('severity', 'low')
        kwargs.setdefault('retryable', True)
        
        super().__init__(message=message, **kwargs)
        self.limit_type = limit_type
        self.retry_after = retry_after
        self.details.update({"limit_type": limit_type, "retry_after": retry_after})


class ConfigurationError(BaseApplicationError):
    """
    Exception raised when configuration is invalid or missing.
    """

    def __init__(
        self,
        message: str = "Configuration error",
        config_key: Optional[str] = None,
        config_section: Optional[str] = None,
        **kwargs,
    ):
        kwargs.setdefault('error_code', 'CONFIGURATION_ERROR')
        kwargs.setdefault('user_message', 'System configuration error. Please contact support.')
        kwargs.setdefault('troubleshooting_guide', 'Contact your system administrator to check the application configuration.')
        kwargs.setdefault('severity', 'critical')
        
        super().__init__(message=message, **kwargs)
        self.config_key = config_key
        self.config_section = config_section
        self.details.update(
            {"config_key": config_key, "config_section": config_section}
        )


class ExternalServiceError(BaseApplicationError):
    """
    Exception raised when external service operations fail.
    """

    def __init__(
        self,
        message: str = "External service error",
        service_name: Optional[str] = None,
        status_code: Optional[int] = None,
        **kwargs,
    ):
        kwargs.setdefault('error_code', 'EXTERNAL_SERVICE_ERROR')
        kwargs.setdefault('user_message', 'An external service is experiencing issues. Please try again later.')
        kwargs.setdefault('troubleshooting_guide', 'Wait a few minutes and try again. If the problem persists, contact support.')
        kwargs.setdefault('severity', 'medium')
        kwargs.setdefault('retryable', True)
        
        super().__init__(message=message, **kwargs)
        self.service_name = service_name
        self.status_code = status_code
        self.details.update({"service_name": service_name, "status_code": status_code})
