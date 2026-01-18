"""
Project management specific exception hierarchy.

This module defines comprehensive exception classes for project management
operations, providing specific error types for different failure scenarios
with detailed context and user-friendly messages.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from .base_exceptions import BaseApplicationError


class ProjectError(BaseApplicationError):
    """
    Base exception for project management operations.

    All project management related exceptions inherit from this base class.
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
        project_id: Optional[str] = None,
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
        self.project_id = project_id
        self.user_id = user_id
        if project_id:
            self.details.update({"project_id": project_id})
        if user_id:
            self.details.update({"user_id": user_id})


class ProjectNotFoundError(ProjectError):
    """
    Exception raised when a project is not found.
    """

    def __init__(
        self,
        message: str = "Project not found",
        project_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="PROJECT_NOT_FOUND",
            user_message="The requested project could not be found.",
            troubleshooting_guide="Verify the project ID and ensure you have access to it.",
            project_id=project_id,
            user_id=user_id,
            **kwargs,
        )
        self.severity = "medium"


class ProjectAccessDeniedError(ProjectError):
    """
    Exception raised when user doesn't have access to a project.
    """

    def __init__(
        self,
        message: str = "Access denied to project",
        project_id: Optional[str] = None,
        user_id: Optional[str] = None,
        required_permission: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="PROJECT_ACCESS_DENIED",
            user_message="You don't have permission to access this project.",
            troubleshooting_guide="Contact the project owner or administrator for access.",
            project_id=project_id,
            user_id=user_id,
            **kwargs,
        )
        self.severity = "high"
        self.required_permission = required_permission
        self.details.update({
            "required_permission": required_permission,
        })


class ProjectCreationError(ProjectError):
    """
    Exception raised when project creation fails.
    """

    def __init__(
        self,
        message: str = "Failed to create project",
        project_name: Optional[str] = None,
        user_id: Optional[str] = None,
        creation_step: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="PROJECT_CREATION_FAILED",
            user_message="Failed to create project. Please try again.",
            troubleshooting_guide="Check your input and try again. If the problem persists, contact support.",
            retryable=True,
            user_id=user_id,
            **kwargs,
        )
        self.severity = "medium"
        self.project_name = project_name
        self.creation_step = creation_step
        self.details.update({
            "project_name": project_name,
            "creation_step": creation_step,
        })


class ProjectUpdateError(ProjectError):
    """
    Exception raised when project update fails.
    """

    def __init__(
        self,
        message: str = "Failed to update project",
        project_id: Optional[str] = None,
        user_id: Optional[str] = None,
        update_fields: Optional[List[str]] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="PROJECT_UPDATE_FAILED",
            user_message="Failed to update project. Please try again.",
            troubleshooting_guide="Check your changes and try again. If the problem persists, contact support.",
            retryable=True,
            project_id=project_id,
            user_id=user_id,
            **kwargs,
        )
        self.severity = "medium"
        self.update_fields = update_fields or []
        self.details.update({
            "update_fields": update_fields,
        })


class ProjectDeletionError(ProjectError):
    """
    Exception raised when project deletion fails.
    """

    def __init__(
        self,
        message: str = "Failed to delete project",
        project_id: Optional[str] = None,
        user_id: Optional[str] = None,
        deletion_step: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="PROJECT_DELETION_FAILED",
            user_message="Failed to delete project. Please try again.",
            troubleshooting_guide="Try again later. If the problem persists, contact support.",
            retryable=True,
            project_id=project_id,
            user_id=user_id,
            **kwargs,
        )
        self.severity = "medium"
        self.deletion_step = deletion_step
        self.details.update({
            "deletion_step": deletion_step,
        })


class ProjectValidationError(ProjectError):
    """
    Exception raised when project validation fails.
    """

    def __init__(
        self,
        message: str = "Project validation failed",
        project_id: Optional[str] = None,
        user_id: Optional[str] = None,
        validation_errors: Optional[Dict[str, str]] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="PROJECT_VALIDATION_FAILED",
            user_message="Project data is invalid. Please check your input.",
            troubleshooting_guide="Review the validation errors and correct the invalid fields.",
            project_id=project_id,
            user_id=user_id,
            **kwargs,
        )
        self.severity = "medium"
        self.validation_errors = validation_errors or {}
        self.details.update({
            "validation_errors": validation_errors,
        })


class ProjectConflictError(ProjectError):
    """
    Exception raised when project operation conflicts with existing state.
    """

    def __init__(
        self,
        message: str = "Project operation conflict",
        project_id: Optional[str] = None,
        user_id: Optional[str] = None,
        conflict_type: Optional[str] = None,
        conflicting_resource: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="PROJECT_CONFLICT",
            user_message="Operation conflicts with current project state.",
            troubleshooting_guide="Refresh the project and try again, or resolve the conflict manually.",
            project_id=project_id,
            user_id=user_id,
            **kwargs,
        )
        self.severity = "medium"
        self.conflict_type = conflict_type
        self.conflicting_resource = conflicting_resource
        self.details.update({
            "conflict_type": conflict_type,
            "conflicting_resource": conflicting_resource,
        })


class ProjectStorageError(ProjectError):
    """
    Exception raised when project storage operations fail.
    """

    def __init__(
        self,
        message: str = "Project storage error",
        project_id: Optional[str] = None,
        user_id: Optional[str] = None,
        storage_operation: Optional[str] = None,
        storage_path: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="PROJECT_STORAGE_ERROR",
            user_message="Failed to access project storage. Please try again.",
            troubleshooting_guide="Try again later. If the problem persists, contact support.",
            retryable=True,
            project_id=project_id,
            user_id=user_id,
            **kwargs,
        )
        self.severity = "medium"
        self.storage_operation = storage_operation
        self.storage_path = storage_path
        self.details.update({
            "storage_operation": storage_operation,
            "storage_path": storage_path,
        })


class ProjectFileError(ProjectError):
    """
    Exception raised when project file operations fail.
    """

    def __init__(
        self,
        message: str = "Project file operation failed",
        project_id: Optional[str] = None,
        user_id: Optional[str] = None,
        file_path: Optional[str] = None,
        file_operation: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="PROJECT_FILE_ERROR",
            user_message="Failed to process project file. Please try again.",
            troubleshooting_guide="Check the file and try again. If the problem persists, contact support.",
            retryable=True,
            project_id=project_id,
            user_id=user_id,
            **kwargs,
        )
        self.severity = "medium"
        self.file_path = file_path
        self.file_operation = file_operation
        self.details.update({
            "file_path": file_path,
            "file_operation": file_operation,
        })


class ProjectGitHubLinkError(ProjectError):
    """
    Exception raised when GitHub linking operations fail.
    """

    def __init__(
        self,
        message: str = "GitHub linking failed",
        project_id: Optional[str] = None,
        user_id: Optional[str] = None,
        github_operation: Optional[str] = None,
        repository_name: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="PROJECT_GITHUB_LINK_FAILED",
            user_message="Failed to link project to GitHub. Please try again.",
            troubleshooting_guide="Check your GitHub permissions and try again.",
            retryable=True,
            project_id=project_id,
            user_id=user_id,
            **kwargs,
        )
        self.severity = "medium"
        self.github_operation = github_operation
        self.repository_name = repository_name
        self.details.update({
            "github_operation": github_operation,
            "repository_name": repository_name,
        })


class ProjectSyncError(ProjectError):
    """
    Exception raised when project synchronization fails.
    """

    def __init__(
        self,
        message: str = "Project synchronization failed",
        project_id: Optional[str] = None,
        user_id: Optional[str] = None,
        sync_target: Optional[str] = None,
        sync_operation: Optional[str] = None,
        failed_files: Optional[List[str]] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="PROJECT_SYNC_FAILED",
            user_message="Failed to synchronize project. Please try again.",
            troubleshooting_guide="Check your connection and permissions, then try again.",
            retryable=True,
            project_id=project_id,
            user_id=user_id,
            **kwargs,
        )
        self.severity = "medium"
        self.sync_target = sync_target
        self.sync_operation = sync_operation
        self.failed_files = failed_files or []
        self.details.update({
            "sync_target": sync_target,
            "sync_operation": sync_operation,
            "failed_files": failed_files,
        })


class ProjectQuotaExceededError(ProjectError):
    """
    Exception raised when project quotas are exceeded.
    """

    def __init__(
        self,
        message: str = "Project quota exceeded",
        project_id: Optional[str] = None,
        user_id: Optional[str] = None,
        quota_type: Optional[str] = None,
        current_usage: Optional[int] = None,
        quota_limit: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="PROJECT_QUOTA_EXCEEDED",
            user_message="Project quota exceeded. Please upgrade your plan or clean up resources.",
            troubleshooting_guide="Delete unused files or upgrade your plan to increase quotas.",
            project_id=project_id,
            user_id=user_id,
            **kwargs,
        )
        self.severity = "medium"
        self.quota_type = quota_type
        self.current_usage = current_usage
        self.quota_limit = quota_limit
        self.details.update({
            "quota_type": quota_type,
            "current_usage": current_usage,
            "quota_limit": quota_limit,
        })


def map_project_exception(
    project_exception: Exception,
    operation: Optional[str] = None,
    project_id: Optional[str] = None,
    user_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> ProjectError:
    """
    Map project-related exception to our custom exception hierarchy.

    Args:
        project_exception: Original project exception
        operation: Optional operation that was being performed
        project_id: Optional project ID context
        user_id: Optional user ID context
        context: Optional additional context

    Returns:
        Mapped custom exception
    """
    exception_name = project_exception.__class__.__name__
    error_message = str(project_exception)
    
    # Create details dictionary
    details = {
        "operation": operation,
        "context": context or {},
    }

    # Map specific project exceptions based on error message patterns
    if "not found" in error_message.lower() or "404" in error_message:
        return ProjectNotFoundError(
            message=error_message,
            details=details,
            original_exception=project_exception,
            project_id=project_id,
            user_id=user_id,
        )
    elif "access denied" in error_message.lower() or "permission" in error_message.lower() or "403" in error_message:
        return ProjectAccessDeniedError(
            message=error_message,
            details=details,
            original_exception=project_exception,
            project_id=project_id,
            user_id=user_id,
        )
    elif "validation" in error_message.lower() or "invalid" in error_message.lower():
        return ProjectValidationError(
            message=error_message,
            details=details,
            original_exception=project_exception,
            project_id=project_id,
            user_id=user_id,
        )
    elif "conflict" in error_message.lower() or "409" in error_message:
        return ProjectConflictError(
            message=error_message,
            details=details,
            original_exception=project_exception,
            project_id=project_id,
            user_id=user_id,
        )
    elif "storage" in error_message.lower() or "file" in error_message.lower():
        return ProjectStorageError(
            message=error_message,
            details=details,
            original_exception=project_exception,
            project_id=project_id,
            user_id=user_id,
        )
    elif "github" in error_message.lower():
        return ProjectGitHubLinkError(
            message=error_message,
            details=details,
            original_exception=project_exception,
            project_id=project_id,
            user_id=user_id,
        )
    elif "sync" in error_message.lower():
        return ProjectSyncError(
            message=error_message,
            details=details,
            original_exception=project_exception,
            project_id=project_id,
            user_id=user_id,
        )
    elif "quota" in error_message.lower() or "limit" in error_message.lower():
        return ProjectQuotaExceededError(
            message=error_message,
            details=details,
            original_exception=project_exception,
            project_id=project_id,
            user_id=user_id,
        )
    else:
        # Generic project error
        return ProjectError(
            message=error_message,
            details=details,
            original_exception=project_exception,
            project_id=project_id,
            user_id=user_id,
        )


def is_retryable_project_error(exception: Exception) -> bool:
    """
    Determine if a project exception is retryable.

    Args:
        exception: Exception to check

    Returns:
        True if the exception is retryable, False otherwise
    """
    retryable_types = (
        ProjectCreationError,
        ProjectUpdateError,
        ProjectDeletionError,
        ProjectStorageError,
        ProjectFileError,
        ProjectGitHubLinkError,
        ProjectSyncError,
    )

    return isinstance(exception, retryable_types)


def get_project_error_severity(exception: Exception) -> str:
    """
    Get the severity level of a project error.

    Args:
        exception: Exception to evaluate

    Returns:
        Severity level: 'low', 'medium', 'high', or 'critical'
    """
    if isinstance(exception, (ProjectAccessDeniedError,)):
        return "high"
    elif isinstance(exception, (
        ProjectNotFoundError,
        ProjectValidationError,
        ProjectConflictError,
        ProjectCreationError,
        ProjectUpdateError,
        ProjectDeletionError,
        ProjectStorageError,
        ProjectFileError,
        ProjectGitHubLinkError,
        ProjectSyncError,
        ProjectQuotaExceededError,
    )):
        return "medium"
    else:
        return "medium"


def get_project_retry_delay(exception: Exception, attempt: int = 1) -> int:
    """
    Calculate retry delay for project operations based on exception type and attempt number.

    Args:
        exception: Exception that occurred
        attempt: Current retry attempt number (1-based)

    Returns:
        Delay in seconds before retry
    """
    base_delay = 1

    if isinstance(exception, (ProjectStorageError, ProjectFileError)):
        # Linear backoff for storage/file errors
        return min(base_delay * attempt, 30)  # Max 30 seconds

    elif isinstance(exception, (ProjectGitHubLinkError, ProjectSyncError)):
        # Exponential backoff for GitHub/sync errors
        return min(base_delay * (2**attempt), 60)  # Max 1 minute

    elif isinstance(exception, (ProjectCreationError, ProjectUpdateError, ProjectDeletionError)):
        # Linear backoff for CRUD operations
        return min(base_delay * attempt, 20)  # Max 20 seconds

    else:
        # Default exponential backoff
        return min(base_delay * (2**attempt), 30)  # Max 30 seconds