"""
GitHub integration specific exception hierarchy.

This module defines comprehensive exception classes for GitHub integration
operations, providing specific error types for different failure scenarios
with detailed context, retry logic, and user-friendly messages.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from .base_exceptions import BaseApplicationError


class GitHubError(BaseApplicationError):
    """
    Base exception for GitHub integration operations.

    All GitHub related exceptions inherit from this base class.
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
        retry_after: Optional[int] = None,
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
        self.retry_after = retry_after
        if retry_after:
            self.details.update({"retry_after": retry_after})


class GitHubAuthenticationError(GitHubError):
    """
    Exception raised when GitHub authentication fails.
    """

    def __init__(
        self,
        message: str = "GitHub authentication failed",
        auth_step: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="GITHUB_AUTH_FAILED",
            user_message="GitHub authentication failed. Please reconnect your GitHub account.",
            troubleshooting_guide="Go to your profile settings and reconnect your GitHub account.",
            **kwargs,
        )
        self.auth_step = auth_step
        self.details.update({"auth_step": auth_step})


class GitHubTokenExpiredError(GitHubError):
    """
    Exception raised when GitHub access token has expired.
    """

    def __init__(
        self,
        message: str = "GitHub access token has expired",
        token_type: Optional[str] = None,
        expired_at: Optional[datetime] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="GITHUB_TOKEN_EXPIRED",
            user_message="Your GitHub access has expired. Please reconnect your account.",
            troubleshooting_guide="Go to your profile settings and reconnect your GitHub account to refresh your access token.",
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


class GitHubPermissionError(GitHubError):
    """
    Exception raised when insufficient permissions for GitHub operation.
    """

    def __init__(
        self,
        message: str = "Insufficient GitHub permissions",
        required_permission: Optional[str] = None,
        repository: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="GITHUB_PERMISSION_DENIED",
            user_message="You don't have permission to perform this action on the GitHub repository.",
            troubleshooting_guide="Ensure you have the necessary permissions for the repository, or contact the repository owner.",
            **kwargs,
        )
        self.required_permission = required_permission
        self.repository = repository
        self.details.update(
            {"required_permission": required_permission, "repository": repository}
        )


class GitHubRepositoryNotFoundError(GitHubError):
    """
    Exception raised when GitHub repository is not found.
    """

    def __init__(
        self,
        message: str = "GitHub repository not found",
        repository: Optional[str] = None,
        owner: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="GITHUB_REPOSITORY_NOT_FOUND",
            user_message="The specified GitHub repository could not be found.",
            troubleshooting_guide="Verify the repository name and ensure you have access to it.",
            **kwargs,
        )
        self.repository = repository
        self.owner = owner
        self.details.update({"repository": repository, "owner": owner})


class GitHubRateLimitError(GitHubError):
    """
    Exception raised when GitHub API rate limit is exceeded.
    """

    def __init__(
        self,
        message: str = "GitHub API rate limit exceeded",
        limit_type: Optional[str] = None,
        retry_after: Optional[int] = None,
        remaining_requests: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="GITHUB_RATE_LIMIT_EXCEEDED",
            user_message="GitHub API rate limit exceeded. Please wait before trying again.",
            troubleshooting_guide="Wait for the specified time before making another request.",
            retryable=True,
            retry_after=retry_after,
            **kwargs,
        )
        self.limit_type = limit_type
        self.remaining_requests = remaining_requests
        self.details.update(
            {
                "limit_type": limit_type,
                "remaining_requests": remaining_requests,
            }
        )


class GitHubSyncConflictError(GitHubError):
    """
    Exception raised when sync operation conflicts with existing repository state.
    """

    def __init__(
        self,
        message: str = "Sync conflict with GitHub repository",
        repository: Optional[str] = None,
        conflicting_files: Optional[List[str]] = None,
        conflict_type: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="GITHUB_SYNC_CONFLICT",
            user_message="Sync conflict detected. Some files have been modified in the repository.",
            troubleshooting_guide="Review the conflicting files and resolve conflicts manually, or force sync to overwrite changes.",
            **kwargs,
        )
        self.repository = repository
        self.conflicting_files = conflicting_files or []
        self.conflict_type = conflict_type
        self.details.update(
            {
                "repository": repository,
                "conflicting_files": conflicting_files,
                "conflict_type": conflict_type,
            }
        )


class GitHubSyncError(GitHubError):
    """
    Exception raised when GitHub sync operation fails.
    """

    def __init__(
        self,
        message: str = "GitHub sync operation failed",
        repository: Optional[str] = None,
        sync_operation: Optional[str] = None,
        failed_files: Optional[List[str]] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="GITHUB_SYNC_FAILED",
            user_message="Failed to sync files to GitHub repository.",
            troubleshooting_guide="Check your internet connection and repository permissions, then try again.",
            retryable=True,
            **kwargs,
        )
        self.repository = repository
        self.sync_operation = sync_operation
        self.failed_files = failed_files or []
        self.details.update(
            {
                "repository": repository,
                "sync_operation": sync_operation,
                "failed_files": failed_files,
            }
        )


class GitHubFileNotFoundError(GitHubError):
    """
    Exception raised when a file is not found in GitHub repository.
    """

    def __init__(
        self,
        message: str = "File not found in GitHub repository",
        repository: Optional[str] = None,
        file_path: Optional[str] = None,
        branch: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="GITHUB_FILE_NOT_FOUND",
            user_message="The specified file could not be found in the repository.",
            troubleshooting_guide="Verify the file path and branch name are correct.",
            **kwargs,
        )
        self.repository = repository
        self.file_path = file_path
        self.branch = branch
        self.details.update(
            {"repository": repository, "file_path": file_path, "branch": branch}
        )


class GitHubCommitError(GitHubError):
    """
    Exception raised when GitHub commit operation fails.
    """

    def __init__(
        self,
        message: str = "GitHub commit operation failed",
        repository: Optional[str] = None,
        commit_message: Optional[str] = None,
        files_to_commit: Optional[List[str]] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="GITHUB_COMMIT_FAILED",
            user_message="Failed to commit changes to GitHub repository.",
            troubleshooting_guide="Check repository permissions and try again. Ensure the repository is not locked.",
            retryable=True,
            **kwargs,
        )
        self.repository = repository
        self.commit_message = commit_message
        self.files_to_commit = files_to_commit or []
        self.details.update(
            {
                "repository": repository,
                "commit_message": commit_message,
                "files_to_commit": files_to_commit,
            }
        )


class GitHubBranchError(GitHubError):
    """
    Exception raised when GitHub branch operations fail.
    """

    def __init__(
        self,
        message: str = "GitHub branch operation failed",
        repository: Optional[str] = None,
        branch_name: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="GITHUB_BRANCH_ERROR",
            user_message="Branch operation failed on GitHub repository.",
            troubleshooting_guide="Verify the branch name and your permissions to modify branches.",
            **kwargs,
        )
        self.repository = repository
        self.branch_name = branch_name
        self.operation = operation
        self.details.update(
            {
                "repository": repository,
                "branch_name": branch_name,
                "operation": operation,
            }
        )


class GitHubServiceUnavailableError(GitHubError):
    """
    Exception raised when GitHub service is unavailable.
    """

    def __init__(
        self,
        message: str = "GitHub service is temporarily unavailable",
        service_status: Optional[str] = None,
        retry_after: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="GITHUB_SERVICE_UNAVAILABLE",
            user_message="GitHub service is temporarily unavailable. Please try again later.",
            troubleshooting_guide="Wait a few minutes and try again. Check GitHub status page for service updates.",
            retryable=True,
            retry_after=retry_after,
            **kwargs,
        )
        self.service_status = service_status
        self.details.update({"service_status": service_status})


class GitHubWebhookError(GitHubError):
    """
    Exception raised when GitHub webhook operations fail.
    """

    def __init__(
        self,
        message: str = "GitHub webhook operation failed",
        repository: Optional[str] = None,
        webhook_url: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="GITHUB_WEBHOOK_ERROR",
            user_message="GitHub webhook configuration failed.",
            troubleshooting_guide="Check webhook URL and repository permissions for webhook management.",
            **kwargs,
        )
        self.repository = repository
        self.webhook_url = webhook_url
        self.operation = operation
        self.details.update(
            {
                "repository": repository,
                "webhook_url": webhook_url,
                "operation": operation,
            }
        )


class GitHubAppError(GitHubError):
    """
    Exception raised when GitHub App operations fail.
    """

    def __init__(
        self,
        message: str = "GitHub App operation failed",
        app_id: Optional[str] = None,
        installation_id: Optional[int] = None,
        operation: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="GITHUB_APP_ERROR",
            user_message="GitHub App integration failed.",
            troubleshooting_guide="Check GitHub App configuration and permissions.",
            **kwargs,
        )
        self.app_id = app_id
        self.installation_id = installation_id
        self.operation = operation
        self.details.update(
            {
                "app_id": app_id,
                "installation_id": installation_id,
                "operation": operation,
            }
        )


class GitHubAppAuthenticationError(GitHubAppError):
    """
    Exception raised when GitHub App authentication fails.
    """

    def __init__(
        self,
        message: str = "GitHub App authentication failed",
        auth_step: Optional[str] = None,
        **kwargs,
    ):
        # Remove conflicting parameters
        kwargs.pop('error_code', None)
        kwargs.pop('operation', None)
        super().__init__(
            message=message,
            error_code="GITHUB_APP_AUTH_FAILED",
            user_message="GitHub App authentication failed. Please check the app configuration.",
            troubleshooting_guide="Verify GitHub App ID, private key, and installation permissions.",
            operation="authentication",
            **kwargs,
        )
        self.auth_step = auth_step
        self.details.update({
            "auth_step": auth_step,
        })


class GitHubAppJWTError(GitHubAppAuthenticationError):
    """
    Exception raised when GitHub App JWT token generation fails.
    """

    def __init__(
        self,
        message: str = "GitHub App JWT generation failed",
        jwt_issue: Optional[str] = None,
        **kwargs,
    ):
        # Remove conflicting parameters
        kwargs.pop('error_code', None)
        kwargs.pop('auth_step', None)
        super().__init__(
            message=message,
            error_code="GITHUB_APP_JWT_FAILED",
            user_message="GitHub App JWT token generation failed.",
            troubleshooting_guide="Check GitHub App private key and configuration.",
            auth_step="jwt_generation",
            **kwargs,
        )
        self.jwt_issue = jwt_issue
        self.details.update({
            "jwt_issue": jwt_issue,
        })


class GitHubAppInstallationError(GitHubAppError):
    """
    Exception raised when GitHub App installation operations fail.
    """

    def __init__(
        self,
        message: str = "GitHub App installation operation failed",
        installation_id: Optional[int] = None,
        installation_operation: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="GITHUB_APP_INSTALLATION_ERROR",
            user_message="GitHub App installation operation failed.",
            troubleshooting_guide="Check GitHub App installation permissions and status.",
            installation_id=installation_id,
            operation=installation_operation,
            **kwargs,
        )
        self.installation_operation = installation_operation
        self.details.update({
            "installation_operation": installation_operation,
        })


class GitHubAppInstallationTokenError(GitHubAppInstallationError):
    """
    Exception raised when GitHub App installation token operations fail.
    """

    def __init__(
        self,
        message: str = "GitHub App installation token failed",
        installation_id: Optional[int] = None,
        token_operation: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="GITHUB_APP_INSTALLATION_TOKEN_FAILED",
            user_message="Failed to get GitHub App installation token.",
            troubleshooting_guide="Check GitHub App installation permissions and try again.",
            installation_id=installation_id,
            installation_operation="token_generation",
            **kwargs,
        )
        self.token_operation = token_operation
        self.details.update({
            "token_operation": token_operation,
        })


class GitHubAppWebhookValidationError(GitHubWebhookError):
    """
    Exception raised when GitHub App webhook validation fails.
    """

    def __init__(
        self,
        message: str = "GitHub App webhook validation failed",
        validation_issue: Optional[str] = None,
        webhook_signature: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="GITHUB_APP_WEBHOOK_VALIDATION_FAILED",
            user_message="GitHub webhook validation failed.",
            troubleshooting_guide="Check webhook secret and signature validation.",
            operation="webhook_validation",
            **kwargs,
        )
        self.validation_issue = validation_issue
        self.webhook_signature = webhook_signature
        self.details.update({
            "validation_issue": validation_issue,
            "webhook_signature": webhook_signature[:20] + "..." if webhook_signature else None,  # Truncate for security
        })


class GitHubAppRateLimitError(GitHubRateLimitError):
    """
    Exception raised when GitHub App API rate limits are exceeded.
    """

    def __init__(
        self,
        message: str = "GitHub App API rate limit exceeded",
        app_id: Optional[str] = None,
        installation_id: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="GITHUB_APP_RATE_LIMIT_EXCEEDED",
            user_message="GitHub App API rate limit exceeded. Please wait before trying again.",
            troubleshooting_guide="Wait for the rate limit to reset or consider upgrading your GitHub plan.",
            **kwargs,
        )
        self.app_id = app_id
        self.installation_id = installation_id
        self.details.update({
            "app_id": app_id,
            "installation_id": installation_id,
        })


def map_github_exception(
    github_exception: Exception,
    operation: Optional[str] = None,
    repository: Optional[str] = None,
    user_context: Optional[Dict[str, Any]] = None,
) -> GitHubError:
    """
    Map GitHub API exception to our custom GitHub exception hierarchy.

    Args:
        github_exception: Original GitHub API exception
        operation: Optional operation that was being performed
        repository: Optional repository context
        user_context: Optional user context information

    Returns:
        Mapped custom exception
    """
    exception_name = github_exception.__class__.__name__
    error_message = str(github_exception)

    # Extract common details
    details = {
        "operation": operation,
        "repository": repository,
        "user_context": user_context or {},
    }

    # Map GitHub App specific exceptions first
    if "github app" in error_message.lower() or "app" in operation.lower() if operation else False:
        if "jwt" in error_message.lower() or "token generation" in error_message.lower():
            return GitHubAppJWTError(
                message=error_message,
                details=details,
                original_exception=github_exception,
            )
        elif "installation" in error_message.lower():
            if "token" in error_message.lower():
                return GitHubAppInstallationTokenError(
                    message=error_message,
                    details=details,
                    original_exception=github_exception,
                )
            else:
                return GitHubAppInstallationError(
                    message=error_message,
                    details=details,
                    original_exception=github_exception,
                )
        elif "webhook" in error_message.lower():
            if "validation" in error_message.lower() or "signature" in error_message.lower():
                return GitHubAppWebhookValidationError(
                    message=error_message,
                    details=details,
                    original_exception=github_exception,
                )
            else:
                return GitHubWebhookError(
                    message=error_message,
                    details=details,
                    original_exception=github_exception,
                )
        elif "rate limit" in error_message.lower():
            return GitHubAppRateLimitError(
                message=error_message,
                details=details,
                original_exception=github_exception,
            )
        else:
            return GitHubAppError(
                message=error_message,
                details=details,
                original_exception=github_exception,
            )

    # Map specific GitHub exceptions based on error message patterns
    if "401" in error_message or "unauthorized" in error_message.lower():
        return GitHubAuthenticationError(
            message=error_message, details=details, original_exception=github_exception
        )
    elif "403" in error_message and "rate limit" in error_message.lower():
        return GitHubRateLimitError(
            message=error_message, details=details, original_exception=github_exception
        )
    elif "403" in error_message or "permission" in error_message.lower():
        return GitHubPermissionError(
            message=error_message,
            repository=repository,
            details=details,
            original_exception=github_exception,
        )
    elif "404" in error_message and "repository" in error_message.lower():
        return GitHubRepositoryNotFoundError(
            message=error_message,
            repository=repository,
            details=details,
            original_exception=github_exception,
        )
    elif "404" in error_message:
        return GitHubFileNotFoundError(
            message=error_message,
            repository=repository,
            details=details,
            original_exception=github_exception,
        )
    elif "conflict" in error_message.lower() or "409" in error_message:
        return GitHubSyncConflictError(
            message=error_message,
            repository=repository,
            details=details,
            original_exception=github_exception,
        )
    elif "commit" in error_message.lower() and "failed" in error_message.lower():
        return GitHubCommitError(
            message=error_message,
            repository=repository,
            details=details,
            original_exception=github_exception,
        )
    elif "branch" in error_message.lower():
        return GitHubBranchError(
            message=error_message,
            repository=repository,
            details=details,
            original_exception=github_exception,
        )
    elif "webhook" in error_message.lower():
        return GitHubWebhookError(
            message=error_message,
            repository=repository,
            details=details,
            original_exception=github_exception,
        )
    elif (
        "service unavailable" in error_message.lower()
        or "timeout" in error_message.lower()
        or "502" in error_message
        or "503" in error_message
    ):
        return GitHubServiceUnavailableError(
            message=error_message, details=details, original_exception=github_exception
        )
    else:
        # Generic GitHub error
        return GitHubError(
            message=error_message, details=details, original_exception=github_exception
        )


def is_retryable_github_error(exception: Exception) -> bool:
    """
    Determine if a GitHub exception is retryable.

    Args:
        exception: Exception to check

    Returns:
        True if the exception is retryable, False otherwise
    """
    retryable_types = (
        GitHubRateLimitError,
        GitHubServiceUnavailableError,
        GitHubSyncError,
        GitHubCommitError,
        GitHubAppRateLimitError,
        GitHubAppInstallationTokenError,
    )

    return isinstance(exception, retryable_types)


def get_github_error_severity(exception: Exception) -> str:
    """
    Get the severity level of a GitHub error.

    Args:
        exception: Exception to evaluate

    Returns:
        Severity level: 'low', 'medium', 'high', or 'critical'
    """
    if isinstance(exception, (
        GitHubAuthenticationError, 
        GitHubTokenExpiredError,
        GitHubAppAuthenticationError,
        GitHubAppJWTError,
    )):
        return "high"
    elif isinstance(exception, (
        GitHubPermissionError, 
        GitHubRepositoryNotFoundError,
        GitHubSyncConflictError,
        GitHubCommitError,
        GitHubAppInstallationError,
        GitHubAppWebhookValidationError,
    )):
        return "medium"
    elif isinstance(exception, (
        GitHubRateLimitError, 
        GitHubServiceUnavailableError,
        GitHubAppRateLimitError,
        GitHubAppInstallationTokenError,
    )):
        return "low"
    else:
        return "medium"


def get_github_retry_delay(exception: Exception, attempt: int = 1) -> int:
    """
    Calculate retry delay for GitHub operations based on exception type and attempt number.

    Args:
        exception: Exception that occurred
        attempt: Current retry attempt number (1-based)

    Returns:
        Delay in seconds before retry
    """
    base_delay = 1

    if isinstance(exception, GitHubRateLimitError):
        # Use retry_after if provided, otherwise exponential backoff
        if hasattr(exception, "retry_after") and exception.retry_after:
            return exception.retry_after
        return min(60 * attempt, 300)  # Max 5 minutes

    elif isinstance(exception, GitHubServiceUnavailableError):
        # Exponential backoff for service unavailable
        return min(base_delay * (2**attempt), 60)  # Max 1 minute

    elif isinstance(exception, (GitHubSyncError, GitHubCommitError)):
        # Linear backoff for sync/commit errors
        return min(base_delay * attempt, 30)  # Max 30 seconds

    else:
        # Default exponential backoff
        return min(base_delay * (2**attempt), 30)  # Max 30 seconds
