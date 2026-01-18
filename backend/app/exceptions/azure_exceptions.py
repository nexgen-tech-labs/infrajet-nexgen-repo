"""
Azure-specific exception hierarchy.

This module defines a comprehensive exception hierarchy for Azure File Share
operations, providing specific error types for different failure scenarios.
"""

from typing import Optional, Dict, Any
from datetime import datetime


class AzureFileShareError(Exception):
    """
    Base exception for Azure File Share operations.
    
    All Azure File Share related exceptions inherit from this base class.
    """
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        """
        Initialize Azure File Share error.
        
        Args:
            message: Human-readable error message.
            error_code: Optional error code for programmatic handling.
            details: Optional dictionary with additional error details.
            original_exception: Optional original exception that caused this error.
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.original_exception = original_exception
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert exception to dictionary for serialization.
        
        Returns:
            Dictionary representation of the exception.
        """
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "original_exception": str(self.original_exception) if self.original_exception else None
        }
    
    def __str__(self) -> str:
        """String representation of the exception."""
        parts = [self.message]
        if self.error_code:
            parts.append(f"Code: {self.error_code}")
        if self.details:
            parts.append(f"Details: {self.details}")
        return " | ".join(parts)


class AzureConnectionError(AzureFileShareError):
    """
    Exception raised when Azure connection fails.
    
    This includes authentication failures, network issues, and service unavailability.
    """
    
    def __init__(
        self,
        message: str = "Failed to connect to Azure File Share",
        connection_string_provided: bool = False,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.connection_string_provided = connection_string_provided
        self.details.update({
            "connection_string_provided": connection_string_provided
        })


class AzureAuthenticationError(AzureConnectionError):
    """
    Exception raised when Azure authentication fails.
    
    This includes invalid credentials, expired tokens, and permission issues.
    """
    
    def __init__(
        self,
        message: str = "Azure authentication failed",
        auth_method: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.auth_method = auth_method
        self.details.update({
            "auth_method": auth_method
        })


class AzureResourceNotFoundError(AzureFileShareError):
    """
    Exception raised when Azure resource is not found.
    
    This includes missing file shares, directories, or files.
    """
    
    def __init__(
        self,
        message: str = "Azure resource not found",
        resource_type: Optional[str] = None,
        resource_path: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.resource_type = resource_type
        self.resource_path = resource_path
        self.details.update({
            "resource_type": resource_type,
            "resource_path": resource_path
        })


class AzureResourceExistsError(AzureFileShareError):
    """
    Exception raised when trying to create a resource that already exists.
    
    This includes duplicate file shares, directories, or files when overwrite is disabled.
    """
    
    def __init__(
        self,
        message: str = "Azure resource already exists",
        resource_type: Optional[str] = None,
        resource_path: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.resource_type = resource_type
        self.resource_path = resource_path
        self.details.update({
            "resource_type": resource_type,
            "resource_path": resource_path
        })


class AzureQuotaExceededError(AzureFileShareError):
    """
    Exception raised when Azure storage quota is exceeded.
    
    This includes file share quota limits and account storage limits.
    """
    
    def __init__(
        self,
        message: str = "Azure storage quota exceeded",
        quota_type: Optional[str] = None,
        current_usage: Optional[int] = None,
        quota_limit: Optional[int] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.quota_type = quota_type
        self.current_usage = current_usage
        self.quota_limit = quota_limit
        self.details.update({
            "quota_type": quota_type,
            "current_usage": current_usage,
            "quota_limit": quota_limit
        })


class AzurePermissionError(AzureFileShareError):
    """
    Exception raised when Azure operation is not permitted.
    
    This includes insufficient permissions for file operations.
    """
    
    def __init__(
        self,
        message: str = "Azure operation not permitted",
        operation: Optional[str] = None,
        required_permission: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.operation = operation
        self.required_permission = required_permission
        self.details.update({
            "operation": operation,
            "required_permission": required_permission
        })


class AzureTimeoutError(AzureFileShareError):
    """
    Exception raised when Azure operation times out.
    
    This includes network timeouts and service response timeouts.
    """
    
    def __init__(
        self,
        message: str = "Azure operation timed out",
        timeout_seconds: Optional[float] = None,
        operation: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.timeout_seconds = timeout_seconds
        self.operation = operation
        self.details.update({
            "timeout_seconds": timeout_seconds,
            "operation": operation
        })


class AzureServiceError(AzureFileShareError):
    """
    Exception raised when Azure service returns an error.
    
    This includes HTTP errors, service unavailability, and internal server errors.
    """
    
    def __init__(
        self,
        message: str = "Azure service error",
        status_code: Optional[int] = None,
        service_error_code: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.status_code = status_code
        self.service_error_code = service_error_code
        self.details.update({
            "status_code": status_code,
            "service_error_code": service_error_code
        })


class AzureValidationError(AzureFileShareError):
    """
    Exception raised when Azure operation validation fails.
    
    This includes invalid file paths, file sizes, and configuration errors.
    """
    
    def __init__(
        self,
        message: str = "Azure operation validation failed",
        validation_type: Optional[str] = None,
        invalid_value: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.validation_type = validation_type
        self.invalid_value = invalid_value
        self.details.update({
            "validation_type": validation_type,
            "invalid_value": invalid_value
        })


class AzureConfigurationError(AzureFileShareError):
    """
    Exception raised when Azure configuration is invalid.
    
    This includes missing configuration values and invalid settings.
    """
    
    def __init__(
        self,
        message: str = "Azure configuration error",
        config_key: Optional[str] = None,
        config_value: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.config_key = config_key
        self.config_value = config_value
        self.details.update({
            "config_key": config_key,
            "config_value": config_value
        })


class AzureRetryExhaustedError(AzureFileShareError):
    """
    Exception raised when retry attempts are exhausted.
    
    This is raised when an operation fails after all retry attempts.
    """
    
    def __init__(
        self,
        message: str = "Azure retry attempts exhausted",
        max_attempts: Optional[int] = None,
        last_error: Optional[Exception] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.max_attempts = max_attempts
        self.last_error = last_error
        self.details.update({
            "max_attempts": max_attempts,
            "last_error": str(last_error) if last_error else None
        })


class AzureFileShareUserIsolationError(AzureFileShareError):
    """
    Exception raised when user isolation is violated in Azure File Share operations.
    """
    
    def __init__(
        self,
        message: str = "User isolation violation in Azure File Share",
        user_id: Optional[str] = None,
        attempted_path: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.user_id = user_id
        self.attempted_path = attempted_path
        self.details.update({
            "user_id": user_id,
            "attempted_path": attempted_path
        })


class AzureFileShareProjectError(AzureFileShareError):
    """
    Exception raised when project-specific Azure File Share operations fail.
    """
    
    def __init__(
        self,
        message: str = "Azure File Share project operation failed",
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.user_id = user_id
        self.project_id = project_id
        self.operation = operation
        self.details.update({
            "user_id": user_id,
            "project_id": project_id,
            "operation": operation
        })


class AzureFileShareGenerationError(AzureFileShareError):
    """
    Exception raised when generation-specific Azure File Share operations fail.
    """
    
    def __init__(
        self,
        message: str = "Azure File Share generation operation failed",
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        generation_id: Optional[str] = None,
        failed_files: Optional[list] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.user_id = user_id
        self.project_id = project_id
        self.generation_id = generation_id
        self.failed_files = failed_files or []
        self.details.update({
            "user_id": user_id,
            "project_id": project_id,
            "generation_id": generation_id,
            "failed_files": failed_files
        })


class ConcurrencyError(AzureFileShareError):
    """
    Exception raised when concurrency control operations fail.
    
    This includes lock acquisition failures and concurrent access conflicts.
    """
    
    def __init__(
        self,
        message: str = "Concurrency control error",
        resource_id: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.resource_id = resource_id
        self.operation = operation
        self.details.update({
            "resource_id": resource_id,
            "operation": operation
        })


class LockTimeoutError(ConcurrencyError):
    """
    Exception raised when lock acquisition times out.
    
    This is raised when a lock cannot be acquired within the specified timeout.
    """
    
    def __init__(
        self,
        message: str = "Lock acquisition timed out",
        timeout_seconds: Optional[float] = None,
        lock_type: Optional[str] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.timeout_seconds = timeout_seconds
        self.lock_type = lock_type
        self.details.update({
            "timeout_seconds": timeout_seconds,
            "lock_type": lock_type
        })


# Exception mapping from Azure SDK exceptions to our custom exceptions
AZURE_EXCEPTION_MAPPING = {
    "ClientAuthenticationError": AzureAuthenticationError,
    "ResourceNotFoundError": AzureResourceNotFoundError,
    "ResourceExistsError": AzureResourceExistsError,
    "HttpResponseError": AzureServiceError,
    "ServiceRequestError": AzureServiceError,
    "AzureError": AzureFileShareError,
}


def map_azure_exception(
    azure_exception: Exception,
    operation: Optional[str] = None,
    resource_path: Optional[str] = None
) -> AzureFileShareError:
    """
    Map Azure SDK exception to our custom exception hierarchy.
    
    Args:
        azure_exception: Original Azure SDK exception.
        operation: Optional operation that was being performed.
        resource_path: Optional resource path involved in the operation.
        
    Returns:
        Mapped custom exception.
    """
    exception_name = azure_exception.__class__.__name__
    exception_class = AZURE_EXCEPTION_MAPPING.get(exception_name, AzureFileShareError)
    
    # Extract error details from Azure exception
    error_code = getattr(azure_exception, 'error_code', None)
    status_code = getattr(azure_exception, 'status_code', None)
    
    # Create details dictionary
    details = {
        "operation": operation,
        "resource_path": resource_path
    }
    
    if status_code:
        details["status_code"] = status_code
    
    # Handle specific exception types
    if exception_name == "ResourceNotFoundError":
        return AzureResourceNotFoundError(
            message=str(azure_exception),
            resource_path=resource_path,
            error_code=error_code,
            details=details,
            original_exception=azure_exception
        )
    elif exception_name == "ResourceExistsError":
        return AzureResourceExistsError(
            message=str(azure_exception),
            resource_path=resource_path,
            error_code=error_code,
            details=details,
            original_exception=azure_exception
        )
    elif exception_name == "ClientAuthenticationError":
        return AzureAuthenticationError(
            message=str(azure_exception),
            error_code=error_code,
            details=details,
            original_exception=azure_exception
        )
    elif exception_name in ["HttpResponseError", "ServiceRequestError"]:
        return AzureServiceError(
            message=str(azure_exception),
            status_code=status_code,
            service_error_code=error_code,
            details=details,
            original_exception=azure_exception
        )
    else:
        return exception_class(
            message=str(azure_exception),
            error_code=error_code,
            details=details,
            original_exception=azure_exception
        )


def is_retryable_error(exception: Exception) -> bool:
    """
    Determine if an exception is retryable.
    
    Args:
        exception: Exception to check.
        
    Returns:
        True if the exception is retryable, False otherwise.
    """
    # Retryable Azure File Share errors
    retryable_types = (
        AzureConnectionError,
        AzureTimeoutError,
        AzureServiceError,
    )
    
    if isinstance(exception, retryable_types):
        return True
    
    # Check for specific Azure SDK exceptions that are retryable
    if hasattr(exception, 'status_code'):
        # HTTP status codes that are typically retryable
        retryable_status_codes = {429, 500, 502, 503, 504}
        return exception.status_code in retryable_status_codes
    
    # Check for specific error messages that indicate transient issues
    error_message = str(exception).lower()
    transient_indicators = [
        "timeout",
        "connection",
        "network",
        "temporary",
        "throttled",
        "rate limit",
        "service unavailable"
    ]
    
    return any(indicator in error_message for indicator in transient_indicators)


def get_error_severity(exception: Exception) -> str:
    """
    Get the severity level of an error.
    
    Args:
        exception: Exception to evaluate.
        
    Returns:
        Severity level: 'low', 'medium', 'high', or 'critical'.
    """
    if isinstance(exception, (AzureAuthenticationError, AzureConfigurationError)):
        return "critical"
    elif isinstance(exception, (AzureQuotaExceededError, AzurePermissionError)):
        return "high"
    elif isinstance(exception, (AzureResourceNotFoundError, AzureValidationError)):
        return "medium"
    elif isinstance(exception, (AzureTimeoutError, AzureConnectionError)):
        return "low"
    else:
        return "medium"