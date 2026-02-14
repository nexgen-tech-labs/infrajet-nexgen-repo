"""
Comprehensive error handling service with retry logic, circuit breaker patterns,
and specialized handling for Azure Entra, GitHub, and WebSocket operations.
"""

import asyncio
import time
import json
from typing import Any, Callable, Dict, Optional, Tuple, Union, List
from dataclasses import dataclass, field
from enum import Enum
import random
from datetime import datetime, timedelta
from logconfig.logger import get_logger
from ..exceptions.base_exceptions import BaseApplicationError
from ..exceptions.azure_entra_exceptions import (
    AzureEntraError,
    is_retryable_azure_entra_error,
    get_azure_entra_error_severity,
    map_azure_entra_exception,
)
from ..exceptions.github_exceptions import (
    GitHubError,
    is_retryable_github_error,
    get_github_error_severity,
    get_github_retry_delay,
    map_github_exception,
)
from ..exceptions.websocket_exceptions import (
    WebSocketError,
    is_retryable_websocket_error,
    get_websocket_error_severity,
    get_websocket_reconnect_delay,
    map_websocket_exception,
)
from ..exceptions.security_exceptions import (
    SecurityError,
    create_security_audit_log,
    determine_security_response,
    is_security_exception_retryable,
    get_security_error_context,
)
    SupabaseError,
    is_retryable_supabase_error,
    get_supabase_error_severity,
    get_supabase_retry_delay,
    map_supabase_exception,
)
from ..exceptions.project_exceptions import (
    ProjectError,
    is_retryable_project_error,
    get_project_error_severity,
    get_project_retry_delay,
    map_project_exception,
)

logger = get_logger()


class CircuitBreakerState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, requests rejected
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    jitter: bool = True


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    expected_exception: Tuple[Exception, ...] = (Exception,)


@dataclass
class ErrorContext:
    """Context information for errors."""

    operation: str
    attempt: int
    max_attempts: int
    start_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    user_id: Optional[int] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


@dataclass
class SecurityIncident:
    """Security incident tracking."""

    incident_id: str
    timestamp: datetime
    severity: str
    error_type: str
    user_id: Optional[int]
    ip_address: Optional[str]
    details: Dict[str, Any]
    resolved: bool = False
    resolution_notes: Optional[str] = None


class CircuitBreaker:
    """Circuit breaker implementation."""

    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.next_attempt_time = 0.0

    def can_execute(self) -> bool:
        """Check if operation can be executed."""
        now = time.time()

        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.OPEN:
            if now >= self.next_attempt_time:
                self.state = CircuitBreakerState.HALF_OPEN
                return True
            return False
        elif self.state == CircuitBreakerState.HALF_OPEN:
            return True

        return False

    def record_success(self):
        """Record successful operation."""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.CLOSED
            self.failure_count = 0
            logger.info(f"Circuit breaker {self.name} recovered")

    def record_failure(self):
        """Record failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.OPEN
            self.next_attempt_time = time.time() + self.config.recovery_timeout
            logger.warning(
                f"Circuit breaker {self.name} opened due to failure in half-open state"
            )
        elif (
            self.state == CircuitBreakerState.CLOSED
            and self.failure_count >= self.config.failure_threshold
        ):
            self.state = CircuitBreakerState.OPEN
            self.next_attempt_time = time.time() + self.config.recovery_timeout
            logger.warning(
                f"Circuit breaker {self.name} opened after {self.failure_count} failures"
            )

    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time,
            "next_attempt_time": self.next_attempt_time,
        }


class ComprehensiveErrorHandlingService:
    """
    Comprehensive error handling service with specialized handling for Azure Entra,
    GitHub, WebSocket operations, and security incidents.
    """

    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.retry_configs: Dict[str, RetryConfig] = {}
        self.error_counts: Dict[str, int] = {}
        self.security_incidents: Dict[str, SecurityIncident] = {}
        self.error_patterns: Dict[str, List[datetime]] = {}
        self.user_error_tracking: Dict[int, Dict[str, int]] = {}

    def add_circuit_breaker(self, name: str, config: CircuitBreakerConfig):
        """Add a circuit breaker for a specific operation."""
        self.circuit_breakers[name] = CircuitBreaker(name, config)
        logger.info(f"Added circuit breaker for {name}")

    def add_retry_config(self, operation: str, config: RetryConfig):
        """Add retry configuration for an operation."""
        self.retry_configs[operation] = config

    async def execute_with_retry(
        self, operation: str, func: Callable, *args, **kwargs
    ) -> Any:
        """
        Execute a function with retry logic and circuit breaker protection.

        Args:
            operation: Name of the operation for tracking
            func: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Result of the function call

        Raises:
            Exception: Last exception if all retries fail
        """
        circuit_breaker = self.circuit_breakers.get(operation)
        retry_config = self.retry_configs.get(operation, RetryConfig())

        if circuit_breaker and not circuit_breaker.can_execute():
            raise CircuitBreakerOpenError(
                f"Circuit breaker {operation} is open", circuit_breaker.get_status()
            )

        last_exception = None
        context = ErrorContext(
            operation=operation,
            attempt=0,
            max_attempts=retry_config.max_attempts,
            start_time=time.time(),
        )

        for attempt in range(retry_config.max_attempts):
            context.attempt = attempt + 1

            try:
                # Execute the function
                result = await func(*args, **kwargs)

                # Record success
                if circuit_breaker:
                    circuit_breaker.record_success()

                # Reset error count
                self.error_counts[operation] = 0

                return result

            except Exception as e:
                last_exception = e
                context.metadata = {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                }

                # Record failure
                if circuit_breaker:
                    circuit_breaker.record_failure()

                # Increment error count
                self.error_counts[operation] = self.error_counts.get(operation, 0) + 1

                logger.warning(
                    f"Attempt {attempt + 1}/{retry_config.max_attempts} failed for {operation}: {e}"
                )

                # Don't retry on the last attempt
                if attempt == retry_config.max_attempts - 1:
                    break

                # Calculate delay
                delay = self._calculate_delay(retry_config, attempt)

                logger.info(f"Retrying {operation} in {delay:.2f} seconds")
                await asyncio.sleep(delay)

        # All retries failed
        logger.error(
            f"All {retry_config.max_attempts} attempts failed for {operation}: {last_exception}"
        )
        raise last_exception

    def _calculate_delay(self, config: RetryConfig, attempt: int) -> float:
        """Calculate delay for retry attempt."""
        delay = config.base_delay * (config.backoff_factor**attempt)

        # Apply jitter
        if config.jitter:
            jitter_factor = 0.1  # 10% jitter
            jitter = delay * jitter_factor * (random.random() * 2 - 1)
            delay += jitter

        # Cap at max delay
        delay = min(delay, config.max_delay)

        return delay

    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics."""
        stats = {
            "total_errors": sum(self.error_counts.values()),
            "errors_by_operation": dict(self.error_counts),
            "circuit_breakers": {},
        }

        for name, breaker in self.circuit_breakers.items():
            stats["circuit_breakers"][name] = breaker.get_status()

        return stats

    def reset_circuit_breaker(self, name: str):
        """Reset a circuit breaker to closed state."""
        if name in self.circuit_breakers:
            breaker = self.circuit_breakers[name]
            breaker.state = CircuitBreakerState.CLOSED
            breaker.failure_count = 0
            logger.info(f"Reset circuit breaker {name}")

    def reset_error_counts(self, operation: Optional[str] = None):
        """Reset error counts."""
        if operation:
            self.error_counts[operation] = 0
        else:
            self.error_counts.clear()

    async def handle_azure_entra_error(
        self,
        exception: Exception,
        operation: Optional[str] = None,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> AzureEntraError:
        """
        Handle Azure Entra specific errors with specialized logic.

        Args:
            exception: Original exception
            operation: Operation being performed
            user_context: User context information

        Returns:
            Mapped Azure Entra exception
        """
        # Map to our custom exception hierarchy
        azure_error = map_azure_entra_exception(exception, operation, user_context)

        # Log the error with appropriate severity
        severity = get_azure_entra_error_severity(azure_error)
        log_method = getattr(logger, severity.lower(), logger.error)

        log_method(
            f"Azure Entra error in {operation}: {azure_error.message}",
            extra={
                "error_code": azure_error.error_code,
                "operation": operation,
                "user_context": user_context,
                "severity": severity,
                "retryable": is_retryable_azure_entra_error(azure_error),
                "details": azure_error.details,
            },
        )

        # Track error patterns
        self._track_error_pattern("azure_entra", azure_error.error_code)

        # Update user error tracking if user context available
        if user_context and user_context.get("user_id"):
            self._track_user_error(user_context["user_id"], "azure_entra")

        return azure_error

    async def handle_github_error(
        self,
        exception: Exception,
        operation: Optional[str] = None,
        repository: Optional[str] = None,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> GitHubError:
        """
        Handle GitHub integration errors with retry logic.

        Args:
            exception: Original exception
            operation: Operation being performed
            repository: Repository context
            user_context: User context information

        Returns:
            Mapped GitHub exception
        """
        # Map to our custom exception hierarchy
        github_error = map_github_exception(
            exception, operation, repository, user_context
        )

        # Log the error with appropriate severity
        severity = get_github_error_severity(github_error)
        log_method = getattr(logger, severity.lower(), logger.error)

        log_method(
            f"GitHub error in {operation}: {github_error.message}",
            extra={
                "error_code": github_error.error_code,
                "operation": operation,
                "repository": repository,
                "user_context": user_context,
                "severity": severity,
                "retryable": is_retryable_github_error(github_error),
                "details": github_error.details,
            },
        )

        # Track error patterns
        self._track_error_pattern("github", github_error.error_code)

        # Update user error tracking if user context available
        if user_context and user_context.get("user_id"):
            self._track_user_error(user_context["user_id"], "github")

        return github_error

    async def handle_websocket_error(
        self,
        exception: Exception,
        connection_id: Optional[str] = None,
        user_id: Optional[int] = None,
        operation: Optional[str] = None,
    ) -> WebSocketError:
        """
        Handle WebSocket errors with connection recovery logic.

        Args:
            exception: Original exception
            connection_id: WebSocket connection ID
            user_id: User ID
            operation: Operation being performed

        Returns:
            Mapped WebSocket exception
        """
        # Map to our custom exception hierarchy
        ws_error = map_websocket_exception(exception, connection_id, user_id, operation)

        # Log the error with appropriate severity
        severity = get_websocket_error_severity(ws_error)
        log_method = getattr(logger, severity.lower(), logger.error)

        log_method(
            f"WebSocket error in {operation}: {ws_error.message}",
            extra={
                "error_code": ws_error.error_code,
                "connection_id": connection_id,
                "user_id": user_id,
                "operation": operation,
                "severity": severity,
                "retryable": is_retryable_websocket_error(ws_error),
                "details": ws_error.details,
            },
        )

        # Track error patterns
        self._track_error_pattern("websocket", ws_error.error_code)

        # Update user error tracking if user ID available
        if user_id:
            self._track_user_error(user_id, "websocket")

        return ws_error

    async def handle_security_incident(
        self,
        exception: SecurityError,
        request_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Handle security incidents with comprehensive logging and response.

        Args:
            exception: Security exception
            request_context: Request context information

        Returns:
            Security response actions
        """
        # Create audit log entry
        audit_log = create_security_audit_log(exception, request_context)

        # Log security incident
        logger.critical(
            f"Security incident: {exception.message}",
            extra={
                "security_incident": True,
                "error_code": exception.error_code,
                "security_level": exception.security_level,
                "user_id": exception.user_id,
                "ip_address": exception.ip_address,
                "audit_log": audit_log,
            },
        )

        # Store incident for tracking
        incident_id = f"SEC_{int(time.time())}_{exception.user_id or 'unknown'}"
        incident = SecurityIncident(
            incident_id=incident_id,
            timestamp=datetime.utcnow(),
            severity=exception.security_level,
            error_type=exception.error_code,
            user_id=exception.user_id,
            ip_address=exception.ip_address,
            details=exception.details,
        )
        self.security_incidents[incident_id] = incident

        # Determine security response
        response = determine_security_response(exception)

        # Track security patterns
        self._track_error_pattern("security", exception.error_code)

        # Update user security tracking
        if exception.user_id:
            self._track_user_error(exception.user_id, "security")

        return {
            "incident_id": incident_id,
            "audit_log": audit_log,
            "response": response,
        }

    async def handle_supabase_error(
        self,
        exception: Exception,
        operation: Optional[str] = None,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> SupabaseError:
        """
        Handle Supabase specific errors with specialized logic.

        Args:
            exception: Original exception
            operation: Operation being performed
            user_context: User context information

        Returns:
            Mapped Supabase exception
        """
        # Map to our custom exception hierarchy
        supabase_error = map_supabase_exception(
            exception, operation, user_context.get("user_id") if user_context else None, user_context
        )

        # Log the error with appropriate severity
        severity = get_supabase_error_severity(supabase_error)
        log_method = getattr(logger, severity.lower(), logger.error)

        log_method(
            f"Supabase error in {operation}: {supabase_error.message}",
            extra={
                "error_code": supabase_error.error_code,
                "operation": operation,
                "user_context": user_context,
                "severity": severity,
                "retryable": is_retryable_supabase_error(supabase_error),
                "details": supabase_error.details,
            },
        )

        # Track error patterns
        self._track_error_pattern("supabase", supabase_error.error_code)

        # Update user error tracking if user context available
        if user_context and user_context.get("user_id"):
            self._track_user_error(user_context["user_id"], "supabase")

        return supabase_error

    async def handle_project_error(
        self,
        exception: Exception,
        operation: Optional[str] = None,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> ProjectError:
        """
        Handle project management specific errors with specialized logic.

        Args:
            exception: Original exception
            operation: Operation being performed
            user_context: User context information

        Returns:
            Mapped Project exception
        """
        # Map to our custom exception hierarchy
        project_error = map_project_exception(
            exception, 
            operation, 
            user_context.get("project_id") if user_context else None,
            user_context.get("user_id") if user_context else None,
            user_context
        )

        # Log the error with appropriate severity
        severity = get_project_error_severity(project_error)
        log_method = getattr(logger, severity.lower(), logger.error)

        log_method(
            f"Project error in {operation}: {project_error.message}",
            extra={
                "error_code": project_error.error_code,
                "operation": operation,
                "project_id": project_error.project_id,
                "user_id": project_error.user_id,
                "user_context": user_context,
                "severity": severity,
                "retryable": is_retryable_project_error(project_error),
                "details": project_error.details,
            },
        )

        # Track error patterns
        self._track_error_pattern("project", project_error.error_code)

        # Update user error tracking if user context available
        if user_context and user_context.get("user_id"):
            self._track_user_error(user_context["user_id"], "project")

        return project_error

    def _track_error_pattern(self, category: str, error_code: str):
        """Track error patterns for analysis."""
        pattern_key = f"{category}:{error_code}"
        if pattern_key not in self.error_patterns:
            self.error_patterns[pattern_key] = []

        self.error_patterns[pattern_key].append(datetime.utcnow())

        # Keep only recent errors (last 24 hours)
        cutoff = datetime.utcnow() - timedelta(hours=24)
        self.error_patterns[pattern_key] = [
            timestamp
            for timestamp in self.error_patterns[pattern_key]
            if timestamp > cutoff
        ]

    def _track_user_error(self, user_id: int, category: str):
        """Track user-specific error counts."""
        if user_id not in self.user_error_tracking:
            self.user_error_tracking[user_id] = {}

        self.user_error_tracking[user_id][category] = (
            self.user_error_tracking[user_id].get(category, 0) + 1
        )

    def get_error_patterns(self) -> Dict[str, Any]:
        """Get error pattern analysis."""
        patterns = {}
        for pattern_key, timestamps in self.error_patterns.items():
            if timestamps:
                patterns[pattern_key] = {
                    "count": len(timestamps),
                    "first_occurrence": min(timestamps).isoformat(),
                    "last_occurrence": max(timestamps).isoformat(),
                    "frequency": len(timestamps) / 24,  # errors per hour
                }

        return patterns

    def get_user_error_summary(self, user_id: int) -> Dict[str, Any]:
        """Get error summary for a specific user."""
        user_errors = self.user_error_tracking.get(user_id, {})
        return {
            "user_id": user_id,
            "total_errors": sum(user_errors.values()),
            "errors_by_category": user_errors,
            "risk_level": self._calculate_user_risk_level(user_errors),
        }

    def _calculate_user_risk_level(self, user_errors: Dict[str, int]) -> str:
        """Calculate user risk level based on error patterns."""
        total_errors = sum(user_errors.values())
        security_errors = user_errors.get("security", 0)

        if security_errors > 5 or total_errors > 50:
            return "high"
        elif security_errors > 2 or total_errors > 20:
            return "medium"
        elif total_errors > 5:
            return "low"
        else:
            return "minimal"

    def get_security_incidents(
        self, resolved: Optional[bool] = None
    ) -> List[SecurityIncident]:
        """Get security incidents, optionally filtered by resolution status."""
        incidents = list(self.security_incidents.values())

        if resolved is not None:
            incidents = [
                incident for incident in incidents if incident.resolved == resolved
            ]

        return sorted(incidents, key=lambda x: x.timestamp, reverse=True)

    def resolve_security_incident(self, incident_id: str, resolution_notes: str):
        """Mark a security incident as resolved."""
        if incident_id in self.security_incidents:
            self.security_incidents[incident_id].resolved = True
            self.security_incidents[incident_id].resolution_notes = resolution_notes
            logger.info(f"Security incident {incident_id} resolved: {resolution_notes}")


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open."""

    def __init__(self, message: str, breaker_status: Dict[str, Any]):
        super().__init__(message)
        self.breaker_status = breaker_status


# Default configurations
DEFAULT_RETRY_CONFIGS = {
    # Existing configurations
    "embedding_generation": RetryConfig(
        max_attempts=3, base_delay=1.0, max_delay=30.0, backoff_factor=2.0
    ),
    "llm_summarization": RetryConfig(
        max_attempts=2, base_delay=2.0, max_delay=60.0, backoff_factor=2.0
    ),
    "vector_storage": RetryConfig(
        max_attempts=5, base_delay=0.5, max_delay=10.0, backoff_factor=1.5
    ),
    "file_processing": RetryConfig(
        max_attempts=3, base_delay=1.0, max_delay=20.0, backoff_factor=2.0
    ),
    # Azure Entra configurations
    "azure_entra_auth": RetryConfig(
        max_attempts=3, base_delay=2.0, max_delay=30.0, backoff_factor=2.0
    ),
    "azure_entra_token_refresh": RetryConfig(
        max_attempts=2, base_delay=1.0, max_delay=10.0, backoff_factor=2.0
    ),
    "azure_entra_profile_sync": RetryConfig(
        max_attempts=3, base_delay=1.0, max_delay=15.0, backoff_factor=1.5
    ),
    # GitHub configurations
    "github_auth": RetryConfig(
        max_attempts=3, base_delay=2.0, max_delay=30.0, backoff_factor=2.0
    ),
    "github_api_call": RetryConfig(
        max_attempts=5, base_delay=1.0, max_delay=60.0, backoff_factor=2.0
    ),
    "github_sync": RetryConfig(
        max_attempts=3, base_delay=3.0, max_delay=45.0, backoff_factor=2.0
    ),
    "github_commit": RetryConfig(
        max_attempts=3, base_delay=2.0, max_delay=30.0, backoff_factor=2.0
    ),
    # WebSocket configurations
    "websocket_connect": RetryConfig(
        max_attempts=5, base_delay=1.0, max_delay=20.0, backoff_factor=1.5
    ),
    "websocket_message": RetryConfig(
        max_attempts=2, base_delay=0.5, max_delay=5.0, backoff_factor=2.0
    ),
    "websocket_broadcast": RetryConfig(
        max_attempts=3, base_delay=1.0, max_delay=10.0, backoff_factor=1.5
    ),
    # Supabase configurations
    "supabase_auth": RetryConfig(
        max_attempts=3, base_delay=2.0, max_delay=30.0, backoff_factor=2.0
    ),
    "supabase_user_validation": RetryConfig(
        max_attempts=2, base_delay=1.0, max_delay=10.0, backoff_factor=2.0
    ),
    "supabase_service_call": RetryConfig(
        max_attempts=3, base_delay=1.0, max_delay=15.0, backoff_factor=1.5
    ),
    # Project management configurations
    "project_creation": RetryConfig(
        max_attempts=3, base_delay=1.0, max_delay=20.0, backoff_factor=2.0
    ),
    "project_update": RetryConfig(
        max_attempts=2, base_delay=1.0, max_delay=15.0, backoff_factor=2.0
    ),
    "project_deletion": RetryConfig(
        max_attempts=3, base_delay=2.0, max_delay=30.0, backoff_factor=2.0
    ),
    "project_storage": RetryConfig(
        max_attempts=5, base_delay=1.0, max_delay=30.0, backoff_factor=1.5
    ),
    "project_sync": RetryConfig(
        max_attempts=3, base_delay=3.0, max_delay=45.0, backoff_factor=2.0
    ),
}

DEFAULT_CIRCUIT_BREAKER_CONFIGS = {
    # Existing configurations
    "anthropic_api": CircuitBreakerConfig(
        failure_threshold=5, recovery_timeout=60.0, expected_exception=(Exception,)
    ),
    "database": CircuitBreakerConfig(
        failure_threshold=3, recovery_timeout=30.0, expected_exception=(Exception,)
    ),
    "vector_store": CircuitBreakerConfig(
        failure_threshold=5, recovery_timeout=45.0, expected_exception=(Exception,)
    ),
    # Azure Entra configurations
    "azure_entra_service": CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=120.0,
        expected_exception=(AzureEntraError,),
    ),
    # GitHub configurations
    "github_api": CircuitBreakerConfig(
        failure_threshold=10, recovery_timeout=300.0, expected_exception=(GitHubError,)
    ),
    # WebSocket configurations
    "websocket_service": CircuitBreakerConfig(
        failure_threshold=3, recovery_timeout=30.0, expected_exception=(WebSocketError,)
    ),
    # Supabase configurations
    "supabase_service": CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=60.0,
        expected_exception=(SupabaseError,),
    ),
    # Project management configurations
    "project_service": CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=45.0,
        expected_exception=(ProjectError,),
    ),
}


def create_default_error_handler() -> ComprehensiveErrorHandlingService:
    """Create error handler with default configurations."""
    handler = ComprehensiveErrorHandlingService()

    # Add default retry configs
    for operation, config in DEFAULT_RETRY_CONFIGS.items():
        handler.add_retry_config(operation, config)

    # Add default circuit breakers
    for name, config in DEFAULT_CIRCUIT_BREAKER_CONFIGS.items():
        handler.add_circuit_breaker(name, config)

    return handler
