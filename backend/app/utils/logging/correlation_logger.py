"""
Correlation Logger for Azure File Share operations.

Provides structured logging with correlation IDs for tracking
operations across the system, especially for Azure File Share
operations and project management workflows.
"""

import uuid
import contextvars
from typing import Dict, Any, Optional, Union
from datetime import datetime
import json
from loguru import logger
from enum import Enum


class LogLevel(str, Enum):
    """Log levels for structured logging."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class OperationType(str, Enum):
    """Types of operations for Azure File Share logging."""
    AZURE_UPLOAD = "azure_upload"
    AZURE_DOWNLOAD = "azure_download"
    AZURE_DELETE = "azure_delete"
    AZURE_LIST = "azure_list"
    AZURE_CREATE_FOLDER = "azure_create_folder"
    PROJECT_CREATE = "project_create"
    PROJECT_UPDATE = "project_update"
    PROJECT_DELETE = "project_delete"
    FILE_SYNC = "file_sync"
    DATABASE_OPERATION = "database_operation"
    API_REQUEST = "api_request"


# Context variables for correlation tracking
correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    'correlation_id', default=None
)
user_id_var: contextvars.ContextVar[int] = contextvars.ContextVar(
    'user_id', default=None
)
project_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    'project_id', default=None
)
operation_type_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    'operation_type', default=None
)


class CorrelationLogger:
    """
    Structured logger with correlation ID support for Azure File Share operations.
    
    This logger automatically includes correlation IDs, user context, and operation
    metadata in all log entries to enable tracing across distributed operations.
    """
    
    def __init__(self, name: str = "azure_operations"):
        self.name = name
        self._logger = logger.bind(logger_name=name)
    
    def _get_context(self) -> Dict[str, Any]:
        """Get current context variables for logging."""
        return {
            "correlation_id": correlation_id_var.get(),
            "user_id": user_id_var.get(),
            "project_id": project_id_var.get(),
            "operation_type": operation_type_var.get(),
            "timestamp": datetime.utcnow().isoformat(),
            "logger_name": self.name
        }
    
    def _log_with_context(
        self,
        level: LogLevel,
        message: str,
        operation_type: Optional[OperationType] = None,
        extra_data: Optional[Dict[str, Any]] = None,
        exception: Optional[Exception] = None
    ) -> None:
        """Log message with full context and structured data."""
        context = self._get_context()
        
        if operation_type:
            context["operation_type"] = operation_type.value
        
        if extra_data:
            context.update(extra_data)
        
        # Create structured log entry
        log_entry = {
            "message": message,
            "context": context,
            "level": level.value
        }
        
        if exception:
            log_entry["exception"] = {
                "type": type(exception).__name__,
                "message": str(exception),
                "traceback": None  # Will be added by loguru if needed
            }
        
        # Log with appropriate level
        bound_logger = self._logger.bind(**context)
        
        if exception:
            bound_logger = bound_logger.opt(exception=exception)
        
        getattr(bound_logger, level.value.lower())(json.dumps(log_entry, default=str))
    
    def debug(
        self,
        message: str,
        operation_type: Optional[OperationType] = None,
        **extra_data
    ) -> None:
        """Log debug message with context."""
        self._log_with_context(LogLevel.DEBUG, message, operation_type, extra_data)
    
    def info(
        self,
        message: str,
        operation_type: Optional[OperationType] = None,
        **extra_data
    ) -> None:
        """Log info message with context."""
        self._log_with_context(LogLevel.INFO, message, operation_type, extra_data)
    
    def warning(
        self,
        message: str,
        operation_type: Optional[OperationType] = None,
        **extra_data
    ) -> None:
        """Log warning message with context."""
        self._log_with_context(LogLevel.WARNING, message, operation_type, extra_data)
    
    def error(
        self,
        message: str,
        operation_type: Optional[OperationType] = None,
        exception: Optional[Exception] = None,
        **extra_data
    ) -> None:
        """Log error message with context and optional exception."""
        self._log_with_context(LogLevel.ERROR, message, operation_type, extra_data, exception)
    
    def critical(
        self,
        message: str,
        operation_type: Optional[OperationType] = None,
        exception: Optional[Exception] = None,
        **extra_data
    ) -> None:
        """Log critical message with context and optional exception."""
        self._log_with_context(LogLevel.CRITICAL, message, operation_type, extra_data, exception)
    
    def azure_operation_start(
        self,
        operation_type: OperationType,
        operation_details: Dict[str, Any]
    ) -> str:
        """
        Log the start of an Azure File Share operation.
        
        Args:
            operation_type: Type of Azure operation
            operation_details: Details about the operation (file_path, size, etc.)
            
        Returns:
            Operation ID for tracking
        """
        operation_id = str(uuid.uuid4())
        
        self.info(
            f"Starting Azure operation: {operation_type.value}",
            operation_type=operation_type,
            operation_id=operation_id,
            operation_details=operation_details,
            phase="start"
        )
        
        return operation_id
    
    def azure_operation_success(
        self,
        operation_type: OperationType,
        operation_id: str,
        result_details: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[float] = None
    ) -> None:
        """
        Log successful completion of an Azure File Share operation.
        
        Args:
            operation_type: Type of Azure operation
            operation_id: Operation ID from start
            result_details: Details about the operation result
            duration_ms: Operation duration in milliseconds
        """
        extra_data = {
            "operation_id": operation_id,
            "phase": "success",
            "success": True
        }
        
        if result_details:
            extra_data["result_details"] = result_details
        
        if duration_ms is not None:
            extra_data["duration_ms"] = duration_ms
        
        self.info(
            f"Azure operation completed successfully: {operation_type.value}",
            operation_type=operation_type,
            **extra_data
        )
    
    def azure_operation_failure(
        self,
        operation_type: OperationType,
        operation_id: str,
        error: Exception,
        duration_ms: Optional[float] = None,
        retry_count: Optional[int] = None
    ) -> None:
        """
        Log failed Azure File Share operation.
        
        Args:
            operation_type: Type of Azure operation
            operation_id: Operation ID from start
            error: Exception that caused the failure
            duration_ms: Operation duration in milliseconds
            retry_count: Number of retries attempted
        """
        extra_data = {
            "operation_id": operation_id,
            "phase": "failure",
            "success": False,
            "error_type": type(error).__name__,
            "error_message": str(error)
        }
        
        if duration_ms is not None:
            extra_data["duration_ms"] = duration_ms
        
        if retry_count is not None:
            extra_data["retry_count"] = retry_count
        
        self.error(
            f"Azure operation failed: {operation_type.value}",
            operation_type=operation_type,
            exception=error,
            **extra_data
        )
    
    def project_operation(
        self,
        operation: str,
        project_id: str,
        user_id: int,
        success: bool = True,
        details: Optional[Dict[str, Any]] = None,
        error: Optional[Exception] = None
    ) -> None:
        """
        Log project management operations.
        
        Args:
            operation: Description of the operation
            project_id: Project ID
            user_id: User ID performing the operation
            success: Whether operation was successful
            details: Additional operation details
            error: Exception if operation failed
        """
        extra_data = {
            "project_id": project_id,
            "user_id": user_id,
            "success": success
        }
        
        if details:
            extra_data.update(details)
        
        if success:
            self.info(
                f"Project operation: {operation}",
                operation_type=OperationType.PROJECT_UPDATE,
                **extra_data
            )
        else:
            self.error(
                f"Project operation failed: {operation}",
                operation_type=OperationType.PROJECT_UPDATE,
                exception=error,
                **extra_data
            )


class CorrelationContext:
    """Context manager for setting correlation context."""
    
    def __init__(
        self,
        correlation_id: Optional[str] = None,
        user_id: Optional[int] = None,
        project_id: Optional[str] = None,
        operation_type: Optional[OperationType] = None
    ):
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.user_id = user_id
        self.project_id = project_id
        self.operation_type = operation_type
        
        # Store previous values for restoration
        self._prev_correlation_id = None
        self._prev_user_id = None
        self._prev_project_id = None
        self._prev_operation_type = None
    
    def __enter__(self):
        # Store previous values
        self._prev_correlation_id = correlation_id_var.get()
        self._prev_user_id = user_id_var.get()
        self._prev_project_id = project_id_var.get()
        self._prev_operation_type = operation_type_var.get()
        
        # Set new values
        correlation_id_var.set(self.correlation_id)
        if self.user_id is not None:
            user_id_var.set(self.user_id)
        if self.project_id is not None:
            project_id_var.set(self.project_id)
        if self.operation_type is not None:
            operation_type_var.set(self.operation_type.value)
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore previous values
        correlation_id_var.set(self._prev_correlation_id)
        user_id_var.set(self._prev_user_id)
        project_id_var.set(self._prev_project_id)
        operation_type_var.set(self._prev_operation_type)


# Global logger instance
_correlation_logger = CorrelationLogger()


def get_correlation_logger(name: str = "azure_operations") -> CorrelationLogger:
    """Get a correlation logger instance."""
    if name == "azure_operations":
        return _correlation_logger
    return CorrelationLogger(name)


def set_correlation_context(
    correlation_id: Optional[str] = None,
    user_id: Optional[int] = None,
    project_id: Optional[str] = None,
    operation_type: Optional[OperationType] = None
) -> None:
    """Set correlation context variables."""
    if correlation_id:
        correlation_id_var.set(correlation_id)
    if user_id is not None:
        user_id_var.set(user_id)
    if project_id:
        project_id_var.set(project_id)
    if operation_type:
        operation_type_var.set(operation_type.value)


def get_current_correlation_id() -> Optional[str]:
    """Get current correlation ID."""
    return correlation_id_var.get()


def generate_correlation_id() -> str:
    """Generate a new correlation ID."""
    return str(uuid.uuid4())