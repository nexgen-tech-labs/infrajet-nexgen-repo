"""
Azure operation logging middleware.

Provides middleware for automatically logging Azure File Share operations
and API requests with correlation IDs and structured data.
"""

import time
import uuid
from typing import Callable, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .correlation_logger import (
    CorrelationLogger,
    CorrelationContext,
    OperationType,
    get_correlation_logger,
    set_correlation_context
)


class AzureLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for logging API requests with correlation IDs.
    
    Automatically sets correlation context for each request and logs
    request/response information for Azure File Share operations.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        logger_name: str = "api_requests",
        log_requests: bool = True,
        log_responses: bool = True,
        exclude_paths: Optional[list] = None
    ):
        super().__init__(app)
        self.logger = get_correlation_logger(logger_name)
        self.log_requests = log_requests
        self.log_responses = log_responses
        self.exclude_paths = exclude_paths or ["/health", "/metrics", "/docs", "/openapi.json"]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with correlation logging."""
        # Skip logging for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        # Generate correlation ID
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        
        # Extract user context if available
        user_id = getattr(request.state, "user_id", None)
        
        # Set correlation context
        with CorrelationContext(
            correlation_id=correlation_id,
            user_id=user_id,
            operation_type=OperationType.API_REQUEST
        ):
            start_time = time.time()
            
            # Log request
            if self.log_requests:
                await self._log_request(request, correlation_id)
            
            # Process request
            try:
                response = await call_next(request)
                
                # Log successful response
                if self.log_responses:
                    duration_ms = (time.time() - start_time) * 1000
                    await self._log_response(request, response, correlation_id, duration_ms)
                
                # Add correlation ID to response headers
                response.headers["X-Correlation-ID"] = correlation_id
                
                return response
                
            except Exception as e:
                # Log error response
                duration_ms = (time.time() - start_time) * 1000
                await self._log_error_response(request, e, correlation_id, duration_ms)
                raise
    
    async def _log_request(self, request: Request, correlation_id: str) -> None:
        """Log incoming request details."""
        # Extract request details
        request_data = {
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "headers": dict(request.headers),
            "client_ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "content_type": request.headers.get("content-type")
        }
        
        # Remove sensitive headers
        sensitive_headers = ["authorization", "cookie", "x-api-key"]
        for header in sensitive_headers:
            if header in request_data["headers"]:
                request_data["headers"][header] = "[REDACTED]"
        
        self.logger.info(
            f"API Request: {request.method} {request.url.path}",
            operation_type=OperationType.API_REQUEST,
            request_data=request_data,
            phase="request"
        )
    
    async def _log_response(
        self,
        request: Request,
        response: Response,
        correlation_id: str,
        duration_ms: float
    ) -> None:
        """Log successful response details."""
        response_data = {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "duration_ms": duration_ms
        }
        
        self.logger.info(
            f"API Response: {request.method} {request.url.path} - {response.status_code}",
            operation_type=OperationType.API_REQUEST,
            response_data=response_data,
            phase="response",
            success=True
        )
    
    async def _log_error_response(
        self,
        request: Request,
        error: Exception,
        correlation_id: str,
        duration_ms: float
    ) -> None:
        """Log error response details."""
        error_data = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "duration_ms": duration_ms
        }
        
        self.logger.error(
            f"API Error: {request.method} {request.url.path}",
            operation_type=OperationType.API_REQUEST,
            exception=error,
            error_data=error_data,
            phase="error",
            success=False
        )


class AzureOperationLogger:
    """
    Decorator and context manager for logging Azure File Share operations.
    
    Provides automatic logging of Azure operations with timing,
    error handling, and structured data.
    """
    
    def __init__(
        self,
        operation_type: OperationType,
        logger_name: str = "azure_operations"
    ):
        self.operation_type = operation_type
        self.logger = get_correlation_logger(logger_name)
        self.operation_id = None
        self.start_time = None
    
    def __enter__(self):
        """Start logging Azure operation."""
        self.operation_id = str(uuid.uuid4())
        self.start_time = time.time()
        
        self.logger.info(
            f"Starting Azure operation: {self.operation_type.value}",
            operation_type=self.operation_type,
            operation_id=self.operation_id,
            phase="start"
        )
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Complete logging Azure operation."""
        duration_ms = (time.time() - self.start_time) * 1000 if self.start_time else None
        
        if exc_type is None:
            # Success
            self.logger.azure_operation_success(
                self.operation_type,
                self.operation_id,
                duration_ms=duration_ms
            )
        else:
            # Failure
            self.logger.azure_operation_failure(
                self.operation_type,
                self.operation_id,
                exc_val,
                duration_ms=duration_ms
            )
    
    def log_details(self, **details):
        """Log additional operation details."""
        self.logger.info(
            f"Azure operation details: {self.operation_type.value}",
            operation_type=self.operation_type,
            operation_id=self.operation_id,
            operation_details=details,
            phase="details"
        )
    
    def __call__(self, func):
        """Use as decorator for Azure operations."""
        async def async_wrapper(*args, **kwargs):
            with self:
                return await func(*args, **kwargs)
        
        def sync_wrapper(*args, **kwargs):
            with self:
                return func(*args, **kwargs)
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper


def azure_operation(operation_type: OperationType):
    """
    Decorator for automatically logging Azure File Share operations.
    
    Usage:
        @azure_operation(OperationType.AZURE_UPLOAD)
        async def upload_file(self, file_path: str, content: str):
            # Implementation
            pass
    """
    def decorator(func):
        return AzureOperationLogger(operation_type)(func)
    return decorator


def log_azure_operation(
    operation_type: OperationType,
    operation_details: Optional[dict] = None
) -> AzureOperationLogger:
    """
    Context manager for logging Azure operations.
    
    Usage:
        with log_azure_operation(OperationType.AZURE_UPLOAD, {"file_path": "test.txt"}):
            # Perform Azure operation
            pass
    """
    logger_instance = AzureOperationLogger(operation_type)
    if operation_details:
        # Store details to log when entering context
        logger_instance._operation_details = operation_details
    return logger_instance