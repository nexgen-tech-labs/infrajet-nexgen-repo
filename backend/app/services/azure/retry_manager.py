"""
Azure File Share Retry Manager.

This module provides retry logic and error handling for Azure File Share operations,
including exponential backoff, circuit breaker patterns, and comprehensive logging.
"""

import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Callable, TypeVar, Awaitable, Union
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps

from app.exceptions.azure_exceptions import (
    AzureFileShareError,
    AzureRetryExhaustedError,
    is_retryable_error,
    get_error_severity,
    map_azure_exception
)
from app.core.azure_config import AzureFileShareConfig, get_azure_config


T = TypeVar('T')


class RetryStrategy(Enum):
    """Retry strategy types."""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"
    IMMEDIATE = "immediate"


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class RetryAttempt:
    """Information about a retry attempt."""
    attempt_number: int
    delay_seconds: float
    exception: Optional[Exception] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    duration_seconds: Optional[float] = None


@dataclass
class RetryResult:
    """Result of a retry operation."""
    success: bool
    result: Any = None
    exception: Optional[Exception] = None
    attempts: List[RetryAttempt] = field(default_factory=list)
    total_duration_seconds: float = 0.0
    
    @property
    def attempt_count(self) -> int:
        """Get the number of attempts made."""
        return len(self.attempts)
    
    @property
    def final_attempt(self) -> Optional[RetryAttempt]:
        """Get the final attempt."""
        return self.attempts[-1] if self.attempts else None


@dataclass
class CircuitBreakerMetrics:
    """Circuit breaker metrics."""
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    state_change_time: datetime = field(default_factory=datetime.utcnow)
    
    def record_success(self) -> None:
        """Record a successful operation."""
        self.success_count += 1
        self.last_success_time = datetime.utcnow()
    
    def record_failure(self) -> None:
        """Record a failed operation."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
    
    def reset(self) -> None:
        """Reset metrics."""
        self.failure_count = 0
        self.success_count = 0
        self.state_change_time = datetime.utcnow()


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_multiplier: float = 2.0,
        jitter: bool = True,
        strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
        retryable_exceptions: Optional[List[type]] = None
    ):
        """
        Initialize retry configuration.
        
        Args:
            max_attempts: Maximum number of retry attempts.
            base_delay: Base delay between retries in seconds.
            max_delay: Maximum delay between retries in seconds.
            backoff_multiplier: Multiplier for exponential backoff.
            jitter: Whether to add random jitter to delays.
            strategy: Retry strategy to use.
            retryable_exceptions: List of exception types that should be retried.
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_multiplier = backoff_multiplier
        self.jitter = jitter
        self.strategy = strategy
        self.retryable_exceptions = retryable_exceptions or []
    
    def calculate_delay(self, attempt_number: int) -> float:
        """
        Calculate delay for a specific attempt.
        
        Args:
            attempt_number: The attempt number (1-based).
            
        Returns:
            Delay in seconds.
        """
        if self.strategy == RetryStrategy.IMMEDIATE:
            delay = 0.0
        elif self.strategy == RetryStrategy.FIXED_DELAY:
            delay = self.base_delay
        elif self.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.base_delay * attempt_number
        elif self.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.base_delay * (self.backoff_multiplier ** (attempt_number - 1))
        else:
            delay = self.base_delay
        
        # Apply maximum delay limit
        delay = min(delay, self.max_delay)
        
        # Add jitter if enabled
        if self.jitter and delay > 0:
            jitter_amount = delay * 0.1  # 10% jitter
            delay += random.uniform(-jitter_amount, jitter_amount)
            delay = max(0, delay)  # Ensure non-negative
        
        return delay
    
    def is_retryable(self, exception: Exception) -> bool:
        """
        Check if an exception is retryable.
        
        Args:
            exception: Exception to check.
            
        Returns:
            True if retryable, False otherwise.
        """
        # Check custom retryable exceptions
        if self.retryable_exceptions:
            if any(isinstance(exception, exc_type) for exc_type in self.retryable_exceptions):
                return True
        
        # Use global retryable error check
        return is_retryable_error(exception)


class CircuitBreaker:
    """Circuit breaker for Azure operations."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 3
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit.
            recovery_timeout: Time to wait before trying to recover (seconds).
            success_threshold: Number of successes needed to close circuit from half-open.
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        
        self.state = CircuitBreakerState.CLOSED
        self.metrics = CircuitBreakerMetrics()
        self.logger = logging.getLogger(__name__)
    
    def can_execute(self) -> bool:
        """
        Check if operation can be executed.
        
        Returns:
            True if operation can proceed, False if circuit is open.
        """
        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.OPEN:
            # Check if recovery timeout has passed
            if (self.metrics.last_failure_time and 
                datetime.utcnow() - self.metrics.last_failure_time >= timedelta(seconds=self.recovery_timeout)):
                self._transition_to_half_open()
                return True
            return False
        elif self.state == CircuitBreakerState.HALF_OPEN:
            return True
        
        return False
    
    def record_success(self) -> None:
        """Record a successful operation."""
        self.metrics.record_success()
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            if self.metrics.success_count >= self.success_threshold:
                self._transition_to_closed()
        elif self.state == CircuitBreakerState.CLOSED:
            # Reset failure count on success
            self.metrics.failure_count = 0
    
    def record_failure(self) -> None:
        """Record a failed operation."""
        self.metrics.record_failure()
        
        if self.state == CircuitBreakerState.CLOSED:
            if self.metrics.failure_count >= self.failure_threshold:
                self._transition_to_open()
        elif self.state == CircuitBreakerState.HALF_OPEN:
            self._transition_to_open()
    
    def _transition_to_open(self) -> None:
        """Transition to open state."""
        self.state = CircuitBreakerState.OPEN
        self.metrics.state_change_time = datetime.utcnow()
        self.logger.warning("Circuit breaker opened due to failures")
    
    def _transition_to_half_open(self) -> None:
        """Transition to half-open state."""
        self.state = CircuitBreakerState.HALF_OPEN
        self.metrics.state_change_time = datetime.utcnow()
        self.metrics.reset()
        self.logger.info("Circuit breaker transitioned to half-open for testing")
    
    def _transition_to_closed(self) -> None:
        """Transition to closed state."""
        self.state = CircuitBreakerState.CLOSED
        self.metrics.state_change_time = datetime.utcnow()
        self.metrics.reset()
        self.logger.info("Circuit breaker closed - service recovered")
    
    def get_state_info(self) -> Dict[str, Any]:
        """Get current state information."""
        return {
            "state": self.state.value,
            "failure_count": self.metrics.failure_count,
            "success_count": self.metrics.success_count,
            "last_failure_time": self.metrics.last_failure_time.isoformat() if self.metrics.last_failure_time else None,
            "last_success_time": self.metrics.last_success_time.isoformat() if self.metrics.last_success_time else None,
            "state_change_time": self.metrics.state_change_time.isoformat(),
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "success_threshold": self.success_threshold
        }


class AzureOperationLogger:
    """Standalone logging utilities for Azure operations."""
    
    def __init__(self, logger_name: str = __name__):
        """Initialize operation logger."""
        self.logger = logging.getLogger(logger_name)
    
    def log_operation_start(
        self,
        operation: str,
        resource_path: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Log the start of an Azure operation.
        
        Args:
            operation: Name of the operation.
            resource_path: Optional resource path.
            details: Optional operation details.
            
        Returns:
            Correlation ID for tracking.
        """
        import uuid
        correlation_id = str(uuid.uuid4())
        
        log_data = {
            "correlation_id": correlation_id,
            "operation": operation,
            "resource_path": resource_path,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat(),
            "event": "operation_start"
        }
        
        self.logger.info(f"Azure operation started: {operation}", extra=log_data)
        return correlation_id
    
    def log_operation_success(
        self,
        correlation_id: str,
        operation: str,
        duration_seconds: float,
        result_summary: Optional[str] = None
    ) -> None:
        """
        Log successful completion of an Azure operation.
        
        Args:
            correlation_id: Correlation ID from operation start.
            operation: Name of the operation.
            duration_seconds: Operation duration.
            result_summary: Optional summary of the result.
        """
        log_data = {
            "correlation_id": correlation_id,
            "operation": operation,
            "duration_seconds": duration_seconds,
            "result_summary": result_summary,
            "timestamp": datetime.utcnow().isoformat(),
            "event": "operation_success"
        }
        
        self.logger.info(f"Azure operation completed: {operation} ({duration_seconds:.2f}s)", extra=log_data)
    
    def log_operation_failure(
        self,
        correlation_id: str,
        operation: str,
        exception: Exception,
        duration_seconds: float,
        attempt_number: Optional[int] = None
    ) -> None:
        """
        Log failure of an Azure operation.
        
        Args:
            correlation_id: Correlation ID from operation start.
            operation: Name of the operation.
            exception: Exception that occurred.
            duration_seconds: Operation duration.
            attempt_number: Optional attempt number for retries.
        """
        log_data = {
            "correlation_id": correlation_id,
            "operation": operation,
            "exception_type": exception.__class__.__name__,
            "exception_message": str(exception),
            "duration_seconds": duration_seconds,
            "attempt_number": attempt_number,
            "error_severity": get_error_severity(exception),
            "timestamp": datetime.utcnow().isoformat(),
            "event": "operation_failure"
        }
        
        self.logger.error(f"Azure operation failed: {operation} - {exception}", extra=log_data)
    
    def log_retry_attempt(
        self,
        correlation_id: str,
        operation: str,
        attempt_number: int,
        delay_seconds: float,
        exception: Exception
    ) -> None:
        """
        Log a retry attempt.
        
        Args:
            correlation_id: Correlation ID from operation start.
            operation: Name of the operation.
            attempt_number: Attempt number.
            delay_seconds: Delay before this attempt.
            exception: Exception from previous attempt.
        """
        log_data = {
            "correlation_id": correlation_id,
            "operation": operation,
            "attempt_number": attempt_number,
            "delay_seconds": delay_seconds,
            "previous_exception": str(exception),
            "timestamp": datetime.utcnow().isoformat(),
            "event": "retry_attempt"
        }
        
        self.logger.warning(
            f"Retrying Azure operation: {operation} (attempt {attempt_number}, delay {delay_seconds:.2f}s)",
            extra=log_data
        )


class RetryManager:
    """
    Main retry manager for Azure File Share operations.
    
    Provides retry logic with exponential backoff, circuit breaker pattern,
    and comprehensive logging for Azure operations.
    """
    
    def __init__(
        self,
        config: Optional[AzureFileShareConfig] = None,
        retry_config: Optional[RetryConfig] = None,
        circuit_breaker: Optional[CircuitBreaker] = None
    ):
        """
        Initialize retry manager.
        
        Args:
            config: Azure configuration.
            retry_config: Retry configuration.
            circuit_breaker: Circuit breaker instance.
        """
        self.config = config or get_azure_config()
        self.retry_config = retry_config or RetryConfig(
            max_attempts=self.config.AZURE_RETRY_ATTEMPTS,
            base_delay=self.config.AZURE_RETRY_DELAY
        )
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.logger = AzureOperationLogger()
    
    async def execute_with_retry(
        self,
        operation: Callable[[], Awaitable[T]],
        operation_name: str,
        resource_path: Optional[str] = None,
        custom_retry_config: Optional[RetryConfig] = None
    ) -> RetryResult:
        """
        Execute an operation with retry logic.
        
        Args:
            operation: Async function to execute.
            operation_name: Name of the operation for logging.
            resource_path: Optional resource path for logging.
            custom_retry_config: Optional custom retry configuration.
            
        Returns:
            RetryResult with operation result or final exception.
        """
        retry_config = custom_retry_config or self.retry_config
        correlation_id = self.logger.log_operation_start(operation_name, resource_path)
        
        start_time = datetime.utcnow()
        attempts = []
        last_exception = None
        
        for attempt_num in range(1, retry_config.max_attempts + 1):
            # Check circuit breaker
            if not self.circuit_breaker.can_execute():
                circuit_exception = AzureFileShareError(
                    "Circuit breaker is open - operation rejected",
                    error_code="CIRCUIT_BREAKER_OPEN",
                    details=self.circuit_breaker.get_state_info()
                )
                
                self.logger.log_operation_failure(
                    correlation_id, operation_name, circuit_exception,
                    (datetime.utcnow() - start_time).total_seconds()
                )
                
                return RetryResult(
                    success=False,
                    exception=circuit_exception,
                    attempts=attempts,
                    total_duration_seconds=(datetime.utcnow() - start_time).total_seconds()
                )
            
            attempt_start = datetime.utcnow()
            
            try:
                # Execute the operation
                result = await operation()
                
                # Record success
                attempt_duration = (datetime.utcnow() - attempt_start).total_seconds()
                attempt = RetryAttempt(
                    attempt_number=attempt_num,
                    delay_seconds=0.0,
                    timestamp=attempt_start,
                    duration_seconds=attempt_duration
                )
                attempts.append(attempt)
                
                self.circuit_breaker.record_success()
                
                total_duration = (datetime.utcnow() - start_time).total_seconds()
                self.logger.log_operation_success(
                    correlation_id, operation_name, total_duration,
                    f"Succeeded on attempt {attempt_num}"
                )
                
                return RetryResult(
                    success=True,
                    result=result,
                    attempts=attempts,
                    total_duration_seconds=total_duration
                )
                
            except Exception as e:
                # Map Azure exceptions to our custom hierarchy
                if not isinstance(e, AzureFileShareError):
                    e = map_azure_exception(e, operation_name, resource_path)
                
                last_exception = e
                attempt_duration = (datetime.utcnow() - attempt_start).total_seconds()
                
                # Calculate delay for next attempt
                delay = retry_config.calculate_delay(attempt_num) if attempt_num < retry_config.max_attempts else 0.0
                
                attempt = RetryAttempt(
                    attempt_number=attempt_num,
                    delay_seconds=delay,
                    exception=e,
                    timestamp=attempt_start,
                    duration_seconds=attempt_duration
                )
                attempts.append(attempt)
                
                self.circuit_breaker.record_failure()
                
                # Check if we should retry
                if attempt_num >= retry_config.max_attempts or not retry_config.is_retryable(e):
                    break
                
                # Log retry attempt
                self.logger.log_retry_attempt(
                    correlation_id, operation_name, attempt_num + 1, delay, e
                )
                
                # Wait before next attempt
                if delay > 0:
                    await asyncio.sleep(delay)
        
        # All attempts failed
        total_duration = (datetime.utcnow() - start_time).total_seconds()
        
        retry_exhausted_exception = AzureRetryExhaustedError(
            f"Operation '{operation_name}' failed after {len(attempts)} attempts",
            max_attempts=retry_config.max_attempts,
            last_error=last_exception
        )
        
        self.logger.log_operation_failure(
            correlation_id, operation_name, retry_exhausted_exception, total_duration
        )
        
        return RetryResult(
            success=False,
            exception=retry_exhausted_exception,
            attempts=attempts,
            total_duration_seconds=total_duration
        )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get retry manager metrics."""
        return {
            "retry_config": {
                "max_attempts": self.retry_config.max_attempts,
                "base_delay": self.retry_config.base_delay,
                "max_delay": self.retry_config.max_delay,
                "strategy": self.retry_config.strategy.value
            },
            "circuit_breaker": self.circuit_breaker.get_state_info()
        }


def retry_azure_operation(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
    operation_name: Optional[str] = None
):
    """
    Decorator for adding retry logic to Azure operations.
    
    Args:
        max_attempts: Maximum number of retry attempts.
        base_delay: Base delay between retries.
        strategy: Retry strategy to use.
        operation_name: Optional operation name for logging.
        
    Returns:
        Decorated function with retry logic.
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            retry_config = RetryConfig(
                max_attempts=max_attempts,
                base_delay=base_delay,
                strategy=strategy
            )
            
            retry_manager = RetryManager(retry_config=retry_config)
            
            async def operation():
                return await func(*args, **kwargs)
            
            op_name = operation_name or func.__name__
            result = await retry_manager.execute_with_retry(operation, op_name)
            
            if result.success:
                return result.result
            else:
                raise result.exception
        
        return wrapper
    return decorator


# Global retry manager instance
_retry_manager: Optional[RetryManager] = None


def get_retry_manager() -> RetryManager:
    """
    Get the global retry manager instance.
    
    Returns:
        RetryManager: Global retry manager.
    """
    global _retry_manager
    
    if _retry_manager is None:
        _retry_manager = RetryManager()
    
    return _retry_manager