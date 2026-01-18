"""
Azure Entra ID specific exception hierarchy.

This module defines comprehensive exception classes for Azure Entra ID
authentication operations, providing specific error types for different
failure scenarios with detailed context and user-friendly messages.
"""

from typing import Optional, Dict, Any
from datetime import datetime
from .base_exceptions import BaseApplicationError


class AzureEntraError(BaseApplicationError):
    """
    Base exception for Azure Entra ID operations.

    All Azure Entra ID related exceptions inherit from this base class.
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
        user_message: Optional[str] = None,
        troubleshooting_guide: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            original_exception=original_exception,
            user_message=user_message,
            troubleshooting_guide=troubleshooting_guide,
        )


class TokenExpiredError(AzureEntraError):
    """
    Exception raised when Azure Entra token has expired.
    """

    def __init__(
        self,
        message: str = "Azure Entra token has expired",
        token_type: Optional[str] = None,
        expired_at: Optional[datetime] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="AZURE_TOKEN_EXPIRED",
            user_message="Your session has expired. Please sign in again.",
            troubleshooting_guide="Click the sign-in button to authenticate with Azure Entra ID again.",
            **kwargs,
        )
        self.token_type = token_type
        self.expired_at = expired_at
        self.details.update(
            {
                "token_type": token_type,
                "expired_at": expired_at.isoformat() if expired_at else None,
            }
        )


class InvalidTokenError(AzureEntraError):
    """
    Exception raised when Azure Entra token is invalid or malformed.
    """

    def __init__(
        self,
        message: str = "Azure Entra token is invalid",
        token_type: Optional[str] = None,
        validation_error: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="AZURE_TOKEN_INVALID",
            user_message="Authentication failed. Please sign in again.",
            troubleshooting_guide="Try signing out and signing back in. If the problem persists, contact your administrator.",
            **kwargs,
        )
        self.token_type = token_type
        self.validation_error = validation_error
        self.details.update(
            {"token_type": token_type, "validation_error": validation_error}
        )


class AuthorizationError(AzureEntraError):
    """
    Exception raised when Azure Entra authorization fails.
    """

    def __init__(
        self,
        message: str = "Azure Entra authorization failed",
        authorization_code: Optional[str] = None,
        state_mismatch: bool = False,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="AZURE_AUTHORIZATION_FAILED",
            user_message="Authorization failed. Please try signing in again.",
            troubleshooting_guide="Ensure you're using the correct Azure Entra ID account and have the necessary permissions.",
            **kwargs,
        )
        self.authorization_code = authorization_code
        self.state_mismatch = state_mismatch
        self.details.update(
            {"authorization_code": authorization_code, "state_mismatch": state_mismatch}
        )


class TenantNotAllowedError(AzureEntraError):
    """
    Exception raised when user's tenant is not allowed to access the application.
    """

    def __init__(
        self,
        message: str = "Your organization is not authorized to access this application",
        tenant_id: Optional[str] = None,
        tenant_name: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="AZURE_TENANT_NOT_ALLOWED",
            user_message="Your organization doesn't have access to this application.",
            troubleshooting_guide="Contact your administrator to request access for your organization.",
            **kwargs,
        )
        self.tenant_id = tenant_id
        self.tenant_name = tenant_name
        self.details.update({"tenant_id": tenant_id, "tenant_name": tenant_name})


class UserNotFoundError(AzureEntraError):
    """
    Exception raised when Azure Entra user is not found or doesn't exist.
    """

    def __init__(
        self,
        message: str = "User not found in Azure Entra ID",
        user_id: Optional[str] = None,
        email: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="AZURE_USER_NOT_FOUND",
            user_message="User account not found. Please contact your administrator.",
            troubleshooting_guide="Verify that your account exists in Azure Entra ID and has the necessary permissions.",
            **kwargs,
        )
        self.user_id = user_id
        self.email = email
        self.details.update({"user_id": user_id, "email": email})


class UserInactiveError(AzureEntraError):
    """
    Exception raised when Azure Entra user account is inactive or disabled.
    """

    def __init__(
        self,
        message: str = "User account is inactive or disabled",
        user_id: Optional[str] = None,
        email: Optional[str] = None,
        disabled_reason: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="AZURE_USER_INACTIVE",
            user_message="Your account is currently disabled. Please contact your administrator.",
            troubleshooting_guide="Contact your IT administrator to reactivate your account.",
            **kwargs,
        )
        self.user_id = user_id
        self.email = email
        self.disabled_reason = disabled_reason
        self.details.update(
            {"user_id": user_id, "email": email, "disabled_reason": disabled_reason}
        )


class ConsentRequiredError(AzureEntraError):
    """
    Exception raised when user consent is required for application permissions.
    """

    def __init__(
        self,
        message: str = "User consent required for application permissions",
        required_scopes: Optional[list] = None,
        consent_url: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="AZURE_CONSENT_REQUIRED",
            user_message="Additional permissions are required. Please grant consent to continue.",
            troubleshooting_guide="Click the consent link to grant the necessary permissions, or contact your administrator.",
            **kwargs,
        )
        self.required_scopes = required_scopes or []
        self.consent_url = consent_url
        self.details.update(
            {"required_scopes": required_scopes, "consent_url": consent_url}
        )


class TokenRefreshError(AzureEntraError):
    """
    Exception raised when Azure Entra token refresh fails.
    """

    def __init__(
        self,
        message: str = "Failed to refresh Azure Entra token",
        refresh_token_expired: bool = False,
        refresh_token_invalid: bool = False,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="AZURE_TOKEN_REFRESH_FAILED",
            user_message="Session refresh failed. Please sign in again.",
            troubleshooting_guide="Try signing out and signing back in to establish a new session.",
            **kwargs,
        )
        self.refresh_token_expired = refresh_token_expired
        self.refresh_token_invalid = refresh_token_invalid
        self.details.update(
            {
                "refresh_token_expired": refresh_token_expired,
                "refresh_token_invalid": refresh_token_invalid,
            }
        )


class ProfileSyncError(AzureEntraError):
    """
    Exception raised when Azure Entra profile synchronization fails.
    """

    def __init__(
        self,
        message: str = "Failed to synchronize user profile from Azure Entra",
        user_id: Optional[str] = None,
        sync_fields: Optional[list] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="AZURE_PROFILE_SYNC_FAILED",
            user_message="Profile synchronization failed. Some information may be outdated.",
            troubleshooting_guide="Try signing out and signing back in to refresh your profile information.",
            **kwargs,
        )
        self.user_id = user_id
        self.sync_fields = sync_fields or []
        self.details.update({"user_id": user_id, "sync_fields": sync_fields})


class AzureServiceUnavailableError(AzureEntraError):
    """
    Exception raised when Azure Entra service is unavailable.
    """

    def __init__(
        self,
        message: str = "Azure Entra service is temporarily unavailable",
        service_status: Optional[str] = None,
        retry_after: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="AZURE_SERVICE_UNAVAILABLE",
            user_message="Authentication service is temporarily unavailable. Please try again later.",
            troubleshooting_guide="Wait a few minutes and try again. If the problem persists, check Azure service status.",
            **kwargs,
        )
        self.service_status = service_status
        self.retry_after = retry_after
        self.details.update(
            {"service_status": service_status, "retry_after": retry_after}
        )


class AzureRateLimitError(AzureEntraError):
    """
    Exception raised when Azure Entra API rate limit is exceeded.
    """

    def __init__(
        self,
        message: str = "Azure Entra API rate limit exceeded",
        retry_after: Optional[int] = None,
        limit_type: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="AZURE_RATE_LIMIT_EXCEEDED",
            user_message="Too many requests. Please wait a moment and try again.",
            troubleshooting_guide="Wait for the specified time before making another request.",
            **kwargs,
        )
        self.retry_after = retry_after
        self.limit_type = limit_type
        self.details.update({"retry_after": retry_after, "limit_type": limit_type})


class AzureConfigurationError(AzureEntraError):
    """
    Exception raised when Azure Entra configuration is invalid or missing.
    """

    def __init__(
        self,
        message: str = "Azure Entra configuration error",
        config_key: Optional[str] = None,
        config_value: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="AZURE_CONFIGURATION_ERROR",
            user_message="Authentication service configuration error. Please contact support.",
            troubleshooting_guide="Contact your system administrator to check the Azure Entra ID configuration.",
            **kwargs,
        )
        self.config_key = config_key
        self.config_value = config_value
        self.details.update({"config_key": config_key, "config_value": config_value})


def map_azure_entra_exception(
    azure_exception: Exception,
    operation: Optional[str] = None,
    user_context: Optional[Dict[str, Any]] = None,
) -> AzureEntraError:
    """
    Map Azure SDK exception to our custom Azure Entra exception hierarchy.

    Args:
        azure_exception: Original Azure SDK exception
        operation: Optional operation that was being performed
        user_context: Optional user context information

    Returns:
        Mapped custom exception
    """
    exception_name = azure_exception.__class__.__name__
    error_message = str(azure_exception)

    # Extract common details
    details = {"operation": operation, "user_context": user_context or {}}

    # Map specific Azure exceptions
    if "token" in error_message.lower() and "expired" in error_message.lower():
        return TokenExpiredError(
            message=error_message, details=details, original_exception=azure_exception
        )
    elif "invalid" in error_message.lower() and "token" in error_message.lower():
        return InvalidTokenError(
            message=error_message, details=details, original_exception=azure_exception
        )
    elif "consent" in error_message.lower() or "permission" in error_message.lower():
        return ConsentRequiredError(
            message=error_message, details=details, original_exception=azure_exception
        )
    elif "tenant" in error_message.lower() and (
        "not found" in error_message.lower() or "invalid" in error_message.lower()
    ):
        return TenantNotAllowedError(
            message=error_message, details=details, original_exception=azure_exception
        )
    elif "user not found" in error_message.lower():
        return UserNotFoundError(
            message=error_message, details=details, original_exception=azure_exception
        )
    elif "disabled" in error_message.lower() or "inactive" in error_message.lower():
        return UserInactiveError(
            message=error_message, details=details, original_exception=azure_exception
        )
    elif "rate limit" in error_message.lower() or "throttled" in error_message.lower():
        return AzureRateLimitError(
            message=error_message, details=details, original_exception=azure_exception
        )
    elif (
        "service unavailable" in error_message.lower()
        or "timeout" in error_message.lower()
    ):
        return AzureServiceUnavailableError(
            message=error_message, details=details, original_exception=azure_exception
        )
    else:
        # Generic Azure Entra error
        return AzureEntraError(
            message=error_message, details=details, original_exception=azure_exception
        )


def is_retryable_azure_entra_error(exception: Exception) -> bool:
    """
    Determine if an Azure Entra exception is retryable.

    Args:
        exception: Exception to check

    Returns:
        True if the exception is retryable, False otherwise
    """
    retryable_types = (
        AzureServiceUnavailableError,
        AzureRateLimitError,
        TokenRefreshError,  # Can retry with re-authentication
    )

    return isinstance(exception, retryable_types)


def get_azure_entra_error_severity(exception: Exception) -> str:
    """
    Get the severity level of an Azure Entra error.

    Args:
        exception: Exception to evaluate

    Returns:
        Severity level: 'low', 'medium', 'high', or 'critical'
    """
    if isinstance(exception, (AzureConfigurationError, TenantNotAllowedError)):
        return "critical"
    elif isinstance(exception, (UserInactiveError, ConsentRequiredError)):
        return "high"
    elif isinstance(
        exception, (TokenExpiredError, InvalidTokenError, UserNotFoundError)
    ):
        return "medium"
    elif isinstance(
        exception, (AzureServiceUnavailableError, AzureRateLimitError, ProfileSyncError)
    ):
        return "low"
    else:
        return "medium"
