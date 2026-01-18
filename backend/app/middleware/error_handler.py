"""
Comprehensive error handling middleware for FastAPI application.

This middleware provides centralized error handling with specialized processing
for Azure Entra, GitHub, WebSocket, and security-related exceptions.
"""

import json
import time
import traceback
from typing import Any, Dict, Optional
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from logconfig.logger import get_logger
from ..exceptions.base_exceptions import (
    BaseApplicationError,
    ValidationError,
    AuthenticationError,
    AuthorizationError,
    ResourceNotFoundError,
    ResourceConflictError,
    ServiceUnavailableError,
    RateLimitError,
    ConfigurationError,
    ExternalServiceError,
)
from ..exceptions.azure_entra_exceptions import AzureEntraError
from ..exceptions.supabase_exceptions import SupabaseError
from ..exceptions.project_exceptions import ProjectError
from ..exceptions.github_exceptions import GitHubError
from ..exceptions.websocket_exceptions import WebSocketError
from ..exceptions.security_exceptions import SecurityError, get_security_error_context
from ..services.error_handling_service import ComprehensiveErrorHandlingService

logger = get_logger()


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    Comprehensive error handling middleware with specialized processing
    for different types of exceptions.
    """

    def __init__(
        self,
        app: ASGIApp,
        error_handler: Optional[ComprehensiveErrorHandlingService] = None,
        include_debug_info: bool = False,
    ):
        super().__init__(app)
        self.error_handler = error_handler or ComprehensiveErrorHandlingService()
        self.include_debug_info = include_debug_info

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request with comprehensive error handling."""
        start_time = time.time()
        request_id = self._generate_request_id()

        # Add request ID to context
        request.state.request_id = request_id

        try:
            # Process the request
            response = await call_next(request)

            # Log successful requests
            duration = time.time() - start_time
            logger.info(
                f"Request completed successfully",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": str(request.url.path),
                    "status_code": response.status_code,
                    "duration": duration,
                },
            )

            return response

        except Exception as e:
            # Handle the exception
            return await self._handle_exception(request, e, request_id, start_time)

    async def _handle_exception(
        self, request: Request, exception: Exception, request_id: str, start_time: float
    ) -> JSONResponse:
        """Handle exceptions with specialized processing."""
        duration = time.time() - start_time

        # Extract request context
        request_context = self._extract_request_context(request)
        request_context["request_id"] = request_id
        request_context["duration"] = duration

        # Handle different exception types
        if isinstance(exception, SecurityError):
            return await self._handle_security_error(exception, request_context)
        elif isinstance(exception, SupabaseError):
            return await self._handle_supabase_error(exception, request_context)
        elif isinstance(exception, ProjectError):
            return await self._handle_project_error(exception, request_context)
        elif isinstance(exception, AzureEntraError):
            return await self._handle_azure_entra_error(exception, request_context)
        elif isinstance(exception, GitHubError):
            return await self._handle_github_error(exception, request_context)
        elif isinstance(exception, WebSocketError):
            return await self._handle_websocket_error(exception, request_context)
        elif isinstance(exception, BaseApplicationError):
            return await self._handle_application_error(exception, request_context)
        elif isinstance(exception, HTTPException):
            return await self._handle_http_exception(exception, request_context)
        else:
            return await self._handle_unexpected_error(exception, request_context)

    async def _handle_security_error(
        self, exception: SecurityError, request_context: Dict[str, Any]
    ) -> JSONResponse:
        """Handle security-related errors with comprehensive logging."""
        # Process security incident
        incident_response = await self.error_handler.handle_security_incident(
            exception, request_context
        )

        # Determine HTTP status code
        status_code = self._get_security_status_code(exception)

        # Create response
        response_data = {
            "error": "Security violation detected",
            "error_code": exception.error_code,
            "message": exception.user_message,
            "incident_id": incident_response["incident_id"],
            "timestamp": exception.timestamp.isoformat(),
            "request_id": request_context["request_id"],
        }

        # Add troubleshooting guide if available
        if exception.troubleshooting_guide:
            response_data["troubleshooting"] = exception.troubleshooting_guide

        # Add debug info if enabled
        if self.include_debug_info:
            response_data["debug"] = {
                "security_level": exception.security_level,
                "details": exception.details,
                "response_actions": incident_response["response"],
            }

        return JSONResponse(
            status_code=status_code,
            content=response_data,
            headers={"X-Request-ID": request_context["request_id"]},
        )

    async def _handle_supabase_error(
        self, exception: SupabaseError, request_context: Dict[str, Any]
    ) -> JSONResponse:
        """Handle Supabase authentication errors."""
        # Process the error
        processed_error = await self.error_handler.handle_supabase_error(
            exception, "supabase_operation", request_context
        )

        # Determine HTTP status code
        status_code = self._get_supabase_status_code(exception)

        # Create response
        response_data = {
            "error": "Supabase authentication error",
            "error_code": exception.error_code,
            "message": exception.user_message,
            "timestamp": exception.timestamp.isoformat(),
            "request_id": request_context["request_id"],
        }

        # Add troubleshooting guide
        if exception.troubleshooting_guide:
            response_data["troubleshooting"] = exception.troubleshooting_guide

        # Add retry information if applicable
        if exception.retryable:
            response_data["retryable"] = True
            response_data["retry_after"] = 5  # Default retry delay

        # Add debug info if enabled
        if self.include_debug_info:
            response_data["debug"] = {
                "severity": exception.severity,
                "details": exception.details,
            }

        return JSONResponse(
            status_code=status_code,
            content=response_data,
            headers={"X-Request-ID": request_context["request_id"]},
        )

    async def _handle_project_error(
        self, exception: ProjectError, request_context: Dict[str, Any]
    ) -> JSONResponse:
        """Handle project management errors."""
        # Process the error
        processed_error = await self.error_handler.handle_project_error(
            exception, "project_operation", request_context
        )

        # Determine HTTP status code
        status_code = self._get_project_status_code(exception)

        # Create response
        response_data = {
            "error": "Project management error",
            "error_code": exception.error_code,
            "message": exception.user_message,
            "timestamp": exception.timestamp.isoformat(),
            "request_id": request_context["request_id"],
        }

        # Add troubleshooting guide
        if exception.troubleshooting_guide:
            response_data["troubleshooting"] = exception.troubleshooting_guide

        # Add retry information if applicable
        if exception.retryable:
            response_data["retryable"] = True
            response_data["retry_after"] = 5  # Default retry delay

        # Add debug info if enabled
        if self.include_debug_info:
            response_data["debug"] = {
                "severity": exception.severity,
                "details": exception.details,
            }

        return JSONResponse(
            status_code=status_code,
            content=response_data,
            headers={"X-Request-ID": request_context["request_id"]},
        )

    async def _handle_azure_entra_error(
        self, exception: AzureEntraError, request_context: Dict[str, Any]
    ) -> JSONResponse:
        """Handle Azure Entra authentication errors."""
        # Process the error
        processed_error = await self.error_handler.handle_azure_entra_error(
            exception, "authentication", request_context
        )

        # Determine HTTP status code
        status_code = self._get_azure_entra_status_code(exception)

        # Create response
        response_data = {
            "error": "Authentication error",
            "error_code": exception.error_code,
            "message": exception.user_message,
            "timestamp": exception.timestamp.isoformat(),
            "request_id": request_context["request_id"],
        }

        # Add troubleshooting guide
        if exception.troubleshooting_guide:
            response_data["troubleshooting"] = exception.troubleshooting_guide

        # Add retry information if applicable
        if exception.retryable:
            response_data["retryable"] = True
            response_data["retry_after"] = 5  # Default retry delay

        # Add debug info if enabled
        if self.include_debug_info:
            response_data["debug"] = {
                "severity": exception.severity,
                "details": exception.details,
            }

        return JSONResponse(
            status_code=status_code,
            content=response_data,
            headers={"X-Request-ID": request_context["request_id"]},
        )

    async def _handle_github_error(
        self, exception: GitHubError, request_context: Dict[str, Any]
    ) -> JSONResponse:
        """Handle GitHub integration errors."""
        # Process the error
        processed_error = await self.error_handler.handle_github_error(
            exception, "github_operation", None, request_context
        )

        # Determine HTTP status code
        status_code = self._get_github_status_code(exception)

        # Create response
        response_data = {
            "error": "GitHub integration error",
            "error_code": exception.error_code,
            "message": exception.user_message,
            "timestamp": exception.timestamp.isoformat(),
            "request_id": request_context["request_id"],
        }

        # Add troubleshooting guide
        if exception.troubleshooting_guide:
            response_data["troubleshooting"] = exception.troubleshooting_guide

        # Add retry information if applicable
        if exception.retryable:
            response_data["retryable"] = True
            if hasattr(exception, "retry_after") and exception.retry_after:
                response_data["retry_after"] = exception.retry_after

        # Add debug info if enabled
        if self.include_debug_info:
            response_data["debug"] = {
                "severity": exception.severity,
                "details": exception.details,
            }

        return JSONResponse(
            status_code=status_code,
            content=response_data,
            headers={"X-Request-ID": request_context["request_id"]},
        )

    async def _handle_websocket_error(
        self, exception: WebSocketError, request_context: Dict[str, Any]
    ) -> JSONResponse:
        """Handle WebSocket errors."""
        # Process the error
        processed_error = await self.error_handler.handle_websocket_error(
            exception, None, None, "websocket_operation"
        )

        # Create response
        response_data = {
            "error": "WebSocket error",
            "error_code": exception.error_code,
            "message": exception.user_message,
            "timestamp": exception.timestamp.isoformat(),
            "request_id": request_context["request_id"],
        }

        # Add troubleshooting guide
        if exception.troubleshooting_guide:
            response_data["troubleshooting"] = exception.troubleshooting_guide

        # Add debug info if enabled
        if self.include_debug_info:
            response_data["debug"] = {
                "severity": exception.severity,
                "details": exception.details,
            }

        return JSONResponse(
            status_code=500,  # WebSocket errors are typically server errors
            content=response_data,
            headers={"X-Request-ID": request_context["request_id"]},
        )

    async def _handle_application_error(
        self, exception: BaseApplicationError, request_context: Dict[str, Any]
    ) -> JSONResponse:
        """Handle general application errors."""
        # Log the error
        logger.error(
            f"Application error: {exception.message}",
            extra={
                "error_code": exception.error_code,
                "severity": exception.severity,
                "request_context": request_context,
                "details": exception.details,
            },
        )

        # Determine HTTP status code
        status_code = self._get_application_status_code(exception)

        # Create response
        response_data = {
            "error": "Application error",
            "error_code": exception.error_code,
            "message": exception.user_message,
            "timestamp": exception.timestamp.isoformat(),
            "request_id": request_context["request_id"],
        }

        # Add troubleshooting guide
        if exception.troubleshooting_guide:
            response_data["troubleshooting"] = exception.troubleshooting_guide

        # Add retry information if applicable
        if exception.retryable:
            response_data["retryable"] = True

        # Add debug info if enabled
        if self.include_debug_info:
            response_data["debug"] = {
                "severity": exception.severity,
                "details": exception.details,
            }

        return JSONResponse(
            status_code=status_code,
            content=response_data,
            headers={"X-Request-ID": request_context["request_id"]},
        )

    async def _handle_http_exception(
        self, exception: HTTPException, request_context: Dict[str, Any]
    ) -> JSONResponse:
        """Handle FastAPI HTTP exceptions."""
        # Log the error
        logger.warning(
            f"HTTP exception: {exception.detail}",
            extra={
                "status_code": exception.status_code,
                "request_context": request_context,
            },
        )

        # Create response
        response_data = {
            "error": "HTTP error",
            "message": exception.detail,
            "status_code": exception.status_code,
            "request_id": request_context["request_id"],
        }

        return JSONResponse(
            status_code=exception.status_code,
            content=response_data,
            headers={"X-Request-ID": request_context["request_id"]},
        )

    async def _handle_unexpected_error(
        self, exception: Exception, request_context: Dict[str, Any]
    ) -> JSONResponse:
        """Handle unexpected errors."""
        # Log the error with full traceback
        logger.critical(
            f"Unexpected error: {str(exception)}",
            extra={
                "exception_type": type(exception).__name__,
                "request_context": request_context,
                "traceback": traceback.format_exc(),
            },
        )

        # Create response (don't expose internal details)
        response_data = {
            "error": "Internal server error",
            "message": "An unexpected error occurred. Please try again later.",
            "request_id": request_context["request_id"],
        }

        # Add debug info if enabled
        if self.include_debug_info:
            response_data["debug"] = {
                "exception_type": type(exception).__name__,
                "exception_message": str(exception),
                "traceback": traceback.format_exc(),
            }

        return JSONResponse(
            status_code=500,
            content=response_data,
            headers={"X-Request-ID": request_context["request_id"]},
        )

    def _extract_request_context(self, request: Request) -> Dict[str, Any]:
        """Extract relevant context from the request."""
        return {
            "method": request.method,
            "path": str(request.url.path),
            "query_params": dict(request.query_params),
            "headers": {
                k: v
                for k, v in request.headers.items()
                if k.lower() not in ["authorization", "cookie", "x-api-key"]
            },
            "client_ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        }

    def _generate_request_id(self) -> str:
        """Generate a unique request ID."""
        import uuid

        return str(uuid.uuid4())[:8]

    def _get_security_status_code(self, exception: SecurityError) -> int:
        """Get HTTP status code for security errors."""
        from ..exceptions.security_exceptions import (
            BruteForceAttemptError,
            UnauthorizedAccessError,
            TokenManipulationError,
            SessionHijackingError,
            PrivilegeEscalationError,
        )

        if isinstance(exception, (UnauthorizedAccessError, PrivilegeEscalationError)):
            return 403
        elif isinstance(exception, (TokenManipulationError, SessionHijackingError)):
            return 401
        elif isinstance(exception, BruteForceAttemptError):
            return 429
        else:
            return 400

    def _get_azure_entra_status_code(self, exception: AzureEntraError) -> int:
        """Get HTTP status code for Azure Entra errors."""
        from ..exceptions.azure_entra_exceptions import (
            TokenExpiredError,
            InvalidTokenError,
            AuthorizationError,
            TenantNotAllowedError,
            UserNotFoundError,
            UserInactiveError,
            ConsentRequiredError,
            AzureServiceUnavailableError,
            AzureRateLimitError,
        )

        if isinstance(exception, (TokenExpiredError, InvalidTokenError)):
            return 401
        elif isinstance(
            exception, (AuthorizationError, TenantNotAllowedError, UserInactiveError)
        ):
            return 403
        elif isinstance(exception, (UserNotFoundError,)):
            return 404
        elif isinstance(exception, ConsentRequiredError):
            return 400
        elif isinstance(exception, AzureServiceUnavailableError):
            return 503
        elif isinstance(exception, AzureRateLimitError):
            return 429
        else:
            return 400

    def _get_github_status_code(self, exception: GitHubError) -> int:
        """Get HTTP status code for GitHub errors."""
        from ..exceptions.github_exceptions import (
            GitHubAuthenticationError,
            GitHubTokenExpiredError,
            GitHubPermissionError,
            GitHubRepositoryNotFoundError,
            GitHubRateLimitError,
            GitHubServiceUnavailableError,
        )

        if isinstance(exception, (GitHubAuthenticationError, GitHubTokenExpiredError)):
            return 401
        elif isinstance(exception, GitHubPermissionError):
            return 403
        elif isinstance(exception, GitHubRepositoryNotFoundError):
            return 404
        elif isinstance(exception, GitHubRateLimitError):
            return 429
        elif isinstance(exception, GitHubServiceUnavailableError):
            return 503
        else:
            return 400

    def _get_supabase_status_code(self, exception: SupabaseError) -> int:
        """Get HTTP status code for Supabase errors."""
        from ..exceptions.supabase_exceptions import (
            SupabaseTokenExpiredError,
            SupabaseTokenInvalidError,
            SupabaseTokenMissingError,
            SupabaseAuthenticationError,
            SupabaseUserNotFoundError,
            SupabaseUserValidationError,
            SupabaseServiceError,
            SupabaseConnectionError,
            SupabaseRateLimitError,
            SupabaseConfigurationError,
        )

        if isinstance(exception, (SupabaseTokenExpiredError, SupabaseTokenInvalidError, SupabaseTokenMissingError, SupabaseAuthenticationError)):
            return 401
        elif isinstance(exception, (SupabaseUserValidationError,)):
            return 403
        elif isinstance(exception, (SupabaseUserNotFoundError,)):
            return 404
        elif isinstance(exception, SupabaseRateLimitError):
            return 429
        elif isinstance(exception, (SupabaseServiceError, SupabaseConnectionError)):
            return 503
        elif isinstance(exception, SupabaseConfigurationError):
            return 500
        else:
            return 400

    def _get_project_status_code(self, exception: ProjectError) -> int:
        """Get HTTP status code for project errors."""
        from ..exceptions.project_exceptions import (
            ProjectNotFoundError,
            ProjectAccessDeniedError,
            ProjectValidationError,
            ProjectConflictError,
            ProjectQuotaExceededError,
        )

        if isinstance(exception, ProjectAccessDeniedError):
            return 403
        elif isinstance(exception, ProjectNotFoundError):
            return 404
        elif isinstance(exception, ProjectConflictError):
            return 409
        elif isinstance(exception, ProjectQuotaExceededError):
            return 429
        elif isinstance(exception, ProjectValidationError):
            return 400
        else:
            return 500

    def _get_application_status_code(self, exception: BaseApplicationError) -> int:
        """Get HTTP status code for application errors."""
        if isinstance(exception, ValidationError):
            return 400
        elif isinstance(exception, AuthenticationError):
            return 401
        elif isinstance(exception, AuthorizationError):
            return 403
        elif isinstance(exception, ResourceNotFoundError):
            return 404
        elif isinstance(exception, ResourceConflictError):
            return 409
        elif isinstance(exception, RateLimitError):
            return 429
        elif isinstance(exception, ServiceUnavailableError):
            return 503
        elif isinstance(exception, (ConfigurationError, ExternalServiceError)):
            return 500
        else:
            return 500
