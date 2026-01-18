"""
Example integration showing how to use the comprehensive error handling system
with Azure Entra, GitHub, WebSocket, and security error handling.

This file demonstrates best practices for error handling across the application.
"""

import asyncio
from typing import Any, Dict, Optional
from fastapi import Request, HTTPException

from logconfig.logger import get_logger
from .error_handling_service import (
    ComprehensiveErrorHandlingService,
    create_default_error_handler,
)
from .security_logging_service import (
    SecurityLoggingService,
    SecurityEventType,
    SecuritySeverity,
)
from .troubleshooting_guide_service import TroubleshootingGuideService
from ..exceptions import (
    AzureEntraError,
    GitHubError,
    WebSocketError,
    SecurityError,
    BaseApplicationError,
)

logger = get_logger()


class IntegratedErrorHandler:
    """
    Integrated error handler that combines all error handling services
    for comprehensive error management across the application.
    """

    def __init__(self):
        self.error_handler = create_default_error_handler()
        self.security_logger = SecurityLoggingService()
        self.troubleshooting_service = TroubleshootingGuideService()

    async def handle_azure_entra_operation(
        self,
        operation_func,
        operation_name: str,
        user_context: Optional[Dict[str, Any]] = None,
        *args,
        **kwargs,
    ) -> Any:
        """
        Handle Azure Entra operations with comprehensive error handling.

        Example usage:
        ```python
        result = await error_handler.handle_azure_entra_operation(
            azure_service.authenticate_user,
            "user_authentication",
            {"user_id": 123, "ip_address": "192.168.1.1"},
            auth_code="abc123"
        )
        ```
        """
        try:
            return await self.error_handler.execute_with_retry(
                operation_name, operation_func, *args, **kwargs
            )
        except Exception as e:
            # Handle Azure Entra specific errors
            if isinstance(e, AzureEntraError):
                processed_error = await self.error_handler.handle_azure_entra_error(
                    e, operation_name, user_context
                )

                # Get troubleshooting guide
                guide = self.troubleshooting_service.get_troubleshooting_guide(
                    processed_error.error_code, user_context
                )

                # Add guide to error details
                if guide:
                    processed_error.details["troubleshooting_guide"] = {
                        "title": guide.title,
                        "quick_fixes": self.troubleshooting_service.get_quick_fix_suggestions(
                            processed_error.error_code
                        ),
                        "estimated_time": guide.estimated_time,
                    }

                raise processed_error
            else:
                # Map generic exception to Azure Entra error
                from ..exceptions.azure_entra_exceptions import (
                    map_azure_entra_exception,
                )

                azure_error = map_azure_entra_exception(e, operation_name, user_context)
                raise azure_error

    async def handle_github_operation(
        self,
        operation_func,
        operation_name: str,
        repository: Optional[str] = None,
        user_context: Optional[Dict[str, Any]] = None,
        *args,
        **kwargs,
    ) -> Any:
        """
        Handle GitHub operations with retry logic and error mapping.

        Example usage:
        ```python
        result = await error_handler.handle_github_operation(
            github_service.sync_repository,
            "repository_sync",
            "user/repo",
            {"user_id": 123},
            project_id="proj_123"
        )
        ```
        """
        try:
            return await self.error_handler.execute_with_retry(
                f"github_{operation_name}", operation_func, *args, **kwargs
            )
        except Exception as e:
            # Handle GitHub specific errors
            if isinstance(e, GitHubError):
                processed_error = await self.error_handler.handle_github_error(
                    e, operation_name, repository, user_context
                )

                # Get troubleshooting guide
                guide = self.troubleshooting_service.get_troubleshooting_guide(
                    processed_error.error_code, user_context
                )

                if guide:
                    processed_error.details["troubleshooting_guide"] = {
                        "title": guide.title,
                        "quick_fixes": self.troubleshooting_service.get_quick_fix_suggestions(
                            processed_error.error_code
                        ),
                    }

                raise processed_error
            else:
                # Map generic exception to GitHub error
                from ..exceptions.github_exceptions import map_github_exception

                github_error = map_github_exception(
                    e, operation_name, repository, user_context
                )
                raise github_error

    async def handle_websocket_operation(
        self,
        operation_func,
        operation_name: str,
        connection_id: Optional[str] = None,
        user_id: Optional[int] = None,
        *args,
        **kwargs,
    ) -> Any:
        """
        Handle WebSocket operations with connection recovery.

        Example usage:
        ```python
        await error_handler.handle_websocket_operation(
            websocket_manager.send_message,
            "send_message",
            "conn_123",
            456,
            message={"type": "update", "data": {...}}
        )
        ```
        """
        try:
            return await self.error_handler.execute_with_retry(
                f"websocket_{operation_name}", operation_func, *args, **kwargs
            )
        except Exception as e:
            # Handle WebSocket specific errors
            if isinstance(e, WebSocketError):
                processed_error = await self.error_handler.handle_websocket_error(
                    e, connection_id, user_id, operation_name
                )

                # Get troubleshooting guide
                guide = self.troubleshooting_service.get_troubleshooting_guide(
                    processed_error.error_code
                )

                if guide:
                    processed_error.details["troubleshooting_guide"] = {
                        "title": guide.title,
                        "quick_fixes": self.troubleshooting_service.get_quick_fix_suggestions(
                            processed_error.error_code
                        ),
                    }

                raise processed_error
            else:
                # Map generic exception to WebSocket error
                from ..exceptions.websocket_exceptions import map_websocket_exception

                ws_error = map_websocket_exception(
                    e, connection_id, user_id, operation_name
                )
                raise ws_error

    async def handle_security_violation(
        self,
        exception: SecurityError,
        request: Optional[Request] = None,
    ) -> Dict[str, Any]:
        """
        Handle security violations with comprehensive logging and response.

        Example usage:
        ```python
        try:
            # Some operation that might trigger security violation
            pass
        except SecurityError as e:
            response = await error_handler.handle_security_violation(e, request)
            # Apply security response (blocking, alerting, etc.)
        ```
        """
        # Extract request context
        request_context = {}
        if request:
            request_context = {
                "method": request.method,
                "path": str(request.url.path),
                "ip_address": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
                "headers": dict(request.headers),
            }

        # Log security event
        event_id = self.security_logger.log_security_exception(
            exception, request_context
        )

        # Handle security incident
        incident_response = await self.error_handler.handle_security_incident(
            exception, request_context
        )

        # Get troubleshooting guide for user
        guide = self.troubleshooting_service.get_troubleshooting_guide(
            exception.error_code
        )

        return {
            "event_id": event_id,
            "incident_response": incident_response,
            "troubleshooting_guide": guide,
            "user_message": exception.user_message,
            "troubleshooting_steps": (
                self.troubleshooting_service.get_quick_fix_suggestions(
                    exception.error_code
                )
                if guide
                else []
            ),
        }

    async def handle_general_error(
        self,
        exception: Exception,
        operation_name: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> BaseApplicationError:
        """
        Handle general application errors with appropriate mapping.

        Example usage:
        ```python
        try:
            # Some operation
            pass
        except Exception as e:
            app_error = await error_handler.handle_general_error(
                e, "file_processing", {"file_name": "example.tf"}
            )
            raise app_error
        ```
        """
        # If it's already an application error, just log and return
        if isinstance(exception, BaseApplicationError):
            logger.error(
                f"Application error in {operation_name}: {exception.message}",
                extra={
                    "error_code": exception.error_code,
                    "operation": operation_name,
                    "context": context,
                    "details": exception.details,
                },
            )
            return exception

        # Map generic exception to application error
        from ..exceptions.base_exceptions import ExternalServiceError

        app_error = ExternalServiceError(
            message=str(exception),
            details={"operation": operation_name, "context": context or {}},
            original_exception=exception,
        )

        logger.error(
            f"Unexpected error in {operation_name}: {str(exception)}",
            extra={
                "error_code": app_error.error_code,
                "operation": operation_name,
                "context": context,
                "exception_type": type(exception).__name__,
            },
        )

        return app_error

    def get_error_statistics(self) -> Dict[str, Any]:
        """Get comprehensive error statistics."""
        return {
            "error_handler_stats": self.error_handler.get_error_stats(),
            "security_patterns": self.error_handler.get_error_patterns(),
            "circuit_breakers": {
                name: breaker.get_status()
                for name, breaker in self.error_handler.circuit_breakers.items()
            },
        }

    def get_user_error_summary(self, user_id: int) -> Dict[str, Any]:
        """Get comprehensive error summary for a user."""
        return {
            "error_handler_summary": self.error_handler.get_user_error_summary(user_id),
            "security_summary": self.security_logger.get_user_security_summary(user_id),
        }

    async def cleanup_old_data(self):
        """Clean up old error data and logs."""
        self.security_logger.cleanup_old_events()
        self.error_handler.reset_error_counts()
        logger.info("Cleaned up old error handling data")


# Example usage in a FastAPI route
async def example_route_with_error_handling():
    """
    Example showing how to use the integrated error handler in a FastAPI route.
    """
    error_handler = IntegratedErrorHandler()

    try:
        # Azure Entra operation
        user_data = await error_handler.handle_azure_entra_operation(
            some_azure_function,
            "get_user_profile",
            {"user_id": 123, "ip_address": "192.168.1.1"},
            user_id="user123",
        )

        # GitHub operation
        sync_result = await error_handler.handle_github_operation(
            some_github_function,
            "sync_repository",
            "user/repo",
            {"user_id": 123},
            project_id="proj_123",
        )

        # WebSocket operation
        await error_handler.handle_websocket_operation(
            some_websocket_function,
            "broadcast_update",
            "conn_123",
            123,
            message={"type": "sync_complete", "data": sync_result},
        )

        return {"status": "success", "data": user_data}

    except SecurityError as e:
        # Handle security violations
        security_response = await error_handler.handle_security_violation(e)
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Security violation",
                "message": e.user_message,
                "troubleshooting": security_response["troubleshooting_steps"],
            },
        )

    except BaseApplicationError as e:
        # Handle application errors
        guide = error_handler.troubleshooting_service.get_troubleshooting_guide(
            e.error_code
        )

        raise HTTPException(
            status_code=500,
            detail={
                "error": e.error_code,
                "message": e.user_message,
                "troubleshooting": (
                    error_handler.troubleshooting_service.get_quick_fix_suggestions(
                        e.error_code
                    )
                    if guide
                    else []
                ),
            },
        )

    except Exception as e:
        # Handle unexpected errors
        app_error = await error_handler.handle_general_error(
            e, "example_route", {"route": "/example"}
        )

        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal server error",
                "message": "An unexpected error occurred",
            },
        )


# Placeholder functions for example
async def some_azure_function(user_id: str):
    """Placeholder Azure function."""
    pass


async def some_github_function(project_id: str):
    """Placeholder GitHub function."""
    pass


async def some_websocket_function(message: Dict[str, Any]):
    """Placeholder WebSocket function."""
    pass


# Global instance for use across the application
integrated_error_handler = IntegratedErrorHandler()
