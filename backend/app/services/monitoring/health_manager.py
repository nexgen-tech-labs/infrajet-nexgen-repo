"""
Health monitoring manager for Azure File Share integration.

Provides comprehensive health checking for Azure File Share connectivity,
database connections, and system resources with modular checkers
and metrics collection.
"""

import asyncio
import time
import psutil
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json

from app.utils.logging.correlation_logger import get_correlation_logger, OperationType


class HealthStatus(str, Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class CheckType(str, Enum):
    """Types of health checks."""
    AZURE_CONNECTIVITY = "azure_connectivity"
    DATABASE_CONNECTIVITY = "database_connectivity"
    SYSTEM_RESOURCES = "system_resources"
    SERVICE_AVAILABILITY = "service_availability"
    CUSTOM = "custom"


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    check_name: str
    check_type: CheckType
    status: HealthStatus
    message: str
    duration_ms: float
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class SystemMetrics:
    """System resource metrics."""
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_usage_percent: float
    disk_free_gb: float
    load_average: Optional[List[float]] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ConnectivityMetrics:
    """Connectivity metrics for external services."""
    service_name: str
    response_time_ms: float
    success_rate: float
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    consecutive_failures: int = 0
    total_checks: int = 0
    successful_checks: int = 0


class BaseHealthChecker:
    """Base class for health checkers."""
    
    def __init__(self, name: str, check_type: CheckType):
        self.name = name
        self.check_type = check_type
        self.logger = get_correlation_logger(f"health_checker_{name}")
    
    async def check(self) -> HealthCheckResult:
        """Perform health check. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement check method")
    
    def _create_result(
        self,
        status: HealthStatus,
        message: str,
        duration_ms: float,
        details: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> HealthCheckResult:
        """Create a health check result."""
        return HealthCheckResult(
            check_name=self.name,
            check_type=self.check_type,
            status=status,
            message=message,
            duration_ms=duration_ms,
            timestamp=datetime.utcnow(),
            details=details or {},
            error=error
        )


class AzureConnectivityChecker(BaseHealthChecker):
    """Health checker for Azure File Share connectivity."""
    
    def __init__(self, azure_service=None):
        super().__init__("azure_file_share", CheckType.AZURE_CONNECTIVITY)
        self.azure_service = azure_service
    
    async def check(self) -> HealthCheckResult:
        """Check Azure File Share connectivity."""
        start_time = time.time()
        
        try:
            if not self.azure_service:
                return self._create_result(
                    HealthStatus.WARNING,
                    "Azure service not configured",
                    0.0,
                    error="Azure File Share service not available for health check"
                )
            
            # Test basic connectivity
            is_connected = await self.azure_service.ensure_connection()
            duration_ms = (time.time() - start_time) * 1000
            
            if is_connected:
                # Try to list a directory to test actual functionality
                try:
                    # This is a basic test - adjust based on your Azure service interface
                    await self.azure_service.list_project_files("health-check-test")
                    return self._create_result(
                        HealthStatus.HEALTHY,
                        "Azure File Share is accessible",
                        duration_ms,
                        {"connection_test": "passed", "functionality_test": "passed"}
                    )
                except Exception as e:
                    # Connection works but functionality might be limited
                    return self._create_result(
                        HealthStatus.WARNING,
                        "Azure File Share connected but functionality limited",
                        duration_ms,
                        {"connection_test": "passed", "functionality_test": "failed"},
                        error=str(e)
                    )
            else:
                return self._create_result(
                    HealthStatus.CRITICAL,
                    "Azure File Share connection failed",
                    duration_ms,
                    {"connection_test": "failed"}
                )
                
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.logger.error(
                "Azure connectivity check failed",
                operation_type=OperationType.AZURE_LIST,
                exception=e,
                duration_ms=duration_ms
            )
            
            return self._create_result(
                HealthStatus.CRITICAL,
                "Azure File Share health check failed",
                duration_ms,
                error=str(e)
            )


class DatabaseConnectivityChecker(BaseHealthChecker):
    """Health checker for database connectivity."""
    
    def __init__(self, db_session_factory=None):
        super().__init__("database", CheckType.DATABASE_CONNECTIVITY)
        self.db_session_factory = db_session_factory
    
    async def check(self) -> HealthCheckResult:
        """Check database connectivity."""
        start_time = time.time()
        
        try:
            if not self.db_session_factory:
                return self._create_result(
                    HealthStatus.WARNING,
                    "Database session factory not configured",
                    0.0,
                    error="Database session factory not available for health check"
                )
            
            # Test database connection with a simple query
            from sqlalchemy import text
            
            async with self.db_session_factory() as session:
                result = await session.execute(text("SELECT 1"))
                await result.fetchone()
                
            duration_ms = (time.time() - start_time) * 1000
            
            return self._create_result(
                HealthStatus.HEALTHY,
                "Database is accessible",
                duration_ms,
                {"query_test": "passed"}
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.logger.error(
                "Database connectivity check failed",
                operation_type=OperationType.DATABASE_OPERATION,
                exception=e,
                duration_ms=duration_ms
            )
            
            return self._create_result(
                HealthStatus.CRITICAL,
                "Database connection failed",
                duration_ms,
                {"query_test": "failed"},
                error=str(e)
            )


class SystemResourceChecker(BaseHealthChecker):
    """Health checker for system resources."""
    
    def __init__(
        self,
        cpu_warning_threshold: float = 80.0,
        cpu_critical_threshold: float = 95.0,
        memory_warning_threshold: float = 80.0,
        memory_critical_threshold: float = 95.0,
        disk_warning_threshold: float = 85.0,
        disk_critical_threshold: float = 95.0
    ):
        super().__init__("system_resources", CheckType.SYSTEM_RESOURCES)
        self.cpu_warning_threshold = cpu_warning_threshold
        self.cpu_critical_threshold = cpu_critical_threshold
        self.memory_warning_threshold = memory_warning_threshold
        self.memory_critical_threshold = memory_critical_threshold
        self.disk_warning_threshold = disk_warning_threshold
        self.disk_critical_threshold = disk_critical_threshold
    
    async def check(self) -> HealthCheckResult:
        """Check system resource usage."""
        start_time = time.time()
        
        try:
            # Get system metrics
            metrics = await self._get_system_metrics()
            duration_ms = (time.time() - start_time) * 1000
            
            # Determine overall status
            status = HealthStatus.HEALTHY
            issues = []
            
            # Check CPU usage
            if metrics.cpu_percent >= self.cpu_critical_threshold:
                status = HealthStatus.CRITICAL
                issues.append(f"CPU usage critical: {metrics.cpu_percent:.1f}%")
            elif metrics.cpu_percent >= self.cpu_warning_threshold:
                if status == HealthStatus.HEALTHY:
                    status = HealthStatus.WARNING
                issues.append(f"CPU usage high: {metrics.cpu_percent:.1f}%")
            
            # Check memory usage
            if metrics.memory_percent >= self.memory_critical_threshold:
                status = HealthStatus.CRITICAL
                issues.append(f"Memory usage critical: {metrics.memory_percent:.1f}%")
            elif metrics.memory_percent >= self.memory_warning_threshold:
                if status == HealthStatus.HEALTHY:
                    status = HealthStatus.WARNING
                issues.append(f"Memory usage high: {metrics.memory_percent:.1f}%")
            
            # Check disk usage
            if metrics.disk_usage_percent >= self.disk_critical_threshold:
                status = HealthStatus.CRITICAL
                issues.append(f"Disk usage critical: {metrics.disk_usage_percent:.1f}%")
            elif metrics.disk_usage_percent >= self.disk_warning_threshold:
                if status == HealthStatus.HEALTHY:
                    status = HealthStatus.WARNING
                issues.append(f"Disk usage high: {metrics.disk_usage_percent:.1f}%")
            
            # Create message
            if issues:
                message = f"System resources: {', '.join(issues)}"
            else:
                message = "System resources are healthy"
            
            # Create details
            details = {
                "cpu_percent": metrics.cpu_percent,
                "memory_percent": metrics.memory_percent,
                "memory_used_mb": metrics.memory_used_mb,
                "memory_available_mb": metrics.memory_available_mb,
                "disk_usage_percent": metrics.disk_usage_percent,
                "disk_free_gb": metrics.disk_free_gb,
                "thresholds": {
                    "cpu_warning": self.cpu_warning_threshold,
                    "cpu_critical": self.cpu_critical_threshold,
                    "memory_warning": self.memory_warning_threshold,
                    "memory_critical": self.memory_critical_threshold,
                    "disk_warning": self.disk_warning_threshold,
                    "disk_critical": self.disk_critical_threshold
                }
            }
            
            if metrics.load_average:
                details["load_average"] = metrics.load_average
            
            return self._create_result(
                status,
                message,
                duration_ms,
                details
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.logger.error(
                "System resource check failed",
                exception=e,
                duration_ms=duration_ms
            )
            
            return self._create_result(
                HealthStatus.CRITICAL,
                "System resource check failed",
                duration_ms,
                error=str(e)
            )
    
    async def _get_system_metrics(self) -> SystemMetrics:
        """Get current system metrics."""
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Memory usage
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_used_mb = memory.used / (1024 * 1024)
        memory_available_mb = memory.available / (1024 * 1024)
        
        # Disk usage
        disk = psutil.disk_usage('/')
        disk_usage_percent = (disk.used / disk.total) * 100
        disk_free_gb = disk.free / (1024 * 1024 * 1024)
        
        # Load average (Unix-like systems only)
        load_average = None
        try:
            load_average = list(psutil.getloadavg())
        except (AttributeError, OSError):
            # Not available on Windows
            pass
        
        return SystemMetrics(
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_used_mb=memory_used_mb,
            memory_available_mb=memory_available_mb,
            disk_usage_percent=disk_usage_percent,
            disk_free_gb=disk_free_gb,
            load_average=load_average
        )


class CustomHealthChecker(BaseHealthChecker):
    """Custom health checker that accepts a callable."""
    
    def __init__(self, name: str, check_function: Callable[[], Union[HealthCheckResult, Dict[str, Any]]]):
        super().__init__(name, CheckType.CUSTOM)
        self.check_function = check_function
    
    async def check(self) -> HealthCheckResult:
        """Execute custom health check function."""
        start_time = time.time()
        
        try:
            if asyncio.iscoroutinefunction(self.check_function):
                result = await self.check_function()
            else:
                result = self.check_function()
            
            duration_ms = (time.time() - start_time) * 1000
            
            if isinstance(result, HealthCheckResult):
                return result
            elif isinstance(result, dict):
                # Convert dict to HealthCheckResult
                return self._create_result(
                    HealthStatus(result.get("status", HealthStatus.UNKNOWN)),
                    result.get("message", "Custom check completed"),
                    duration_ms,
                    result.get("details", {}),
                    result.get("error")
                )
            else:
                return self._create_result(
                    HealthStatus.UNKNOWN,
                    "Custom check returned unexpected result",
                    duration_ms,
                    {"result": str(result)}
                )
                
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.logger.error(
                f"Custom health check '{self.name}' failed",
                exception=e,
                duration_ms=duration_ms
            )
            
            return self._create_result(
                HealthStatus.CRITICAL,
                f"Custom check '{self.name}' failed",
                duration_ms,
                error=str(e)
            )


class HealthCheckManager:
    """
    Manager for health checks and system monitoring.
    
    Provides centralized health checking with modular checkers,
    metrics collection, and monitoring capabilities.
    """
    
    def __init__(self):
        self.checkers: Dict[str, BaseHealthChecker] = {}
        self.check_history: List[HealthCheckResult] = []
        self.connectivity_metrics: Dict[str, ConnectivityMetrics] = {}
        self.logger = get_correlation_logger("health_manager")
        
        # Monitoring configuration
        self.monitoring_enabled = False
        self.monitoring_interval = 60  # seconds
        self.monitoring_task: Optional[asyncio.Task] = None
        
        # History limits
        self.max_history_size = 1000
        self.history_retention_hours = 24
    
    def register_checker(self, checker: BaseHealthChecker) -> None:
        """Register a health checker."""
        self.checkers[checker.name] = checker
        self.logger.info(
            f"Registered health checker: {checker.name}",
            checker_type=checker.check_type.value
        )
    
    def unregister_checker(self, name: str) -> None:
        """Unregister a health checker."""
        if name in self.checkers:
            del self.checkers[name]
            self.logger.info(f"Unregistered health checker: {name}")
    
    def register_azure_checker(self, azure_service=None) -> None:
        """Register Azure File Share connectivity checker."""
        checker = AzureConnectivityChecker(azure_service)
        self.register_checker(checker)
    
    def register_database_checker(self, db_session_factory=None) -> None:
        """Register database connectivity checker."""
        checker = DatabaseConnectivityChecker(db_session_factory)
        self.register_checker(checker)
    
    def register_system_checker(self, **thresholds) -> None:
        """Register system resource checker with optional custom thresholds."""
        checker = SystemResourceChecker(**thresholds)
        self.register_checker(checker)
    
    def register_custom_checker(self, name: str, check_function: Callable) -> None:
        """Register a custom health checker."""
        checker = CustomHealthChecker(name, check_function)
        self.register_checker(checker)
    
    async def check_health(self, checker_names: Optional[List[str]] = None) -> Dict[str, HealthCheckResult]:
        """
        Run health checks for specified checkers or all registered checkers.
        
        Args:
            checker_names: List of checker names to run, or None for all
            
        Returns:
            Dictionary mapping checker names to their results
        """
        if checker_names is None:
            checkers_to_run = self.checkers
        else:
            checkers_to_run = {
                name: checker for name, checker in self.checkers.items()
                if name in checker_names
            }
        
        results = {}
        
        # Run checks concurrently
        tasks = []
        for name, checker in checkers_to_run.items():
            task = asyncio.create_task(self._run_single_check(name, checker))
            tasks.append(task)
        
        if tasks:
            completed_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(completed_results):
                checker_name = list(checkers_to_run.keys())[i]
                
                if isinstance(result, Exception):
                    # Handle exceptions from individual checks
                    error_result = HealthCheckResult(
                        check_name=checker_name,
                        check_type=CheckType.CUSTOM,
                        status=HealthStatus.CRITICAL,
                        message=f"Health check failed with exception",
                        duration_ms=0.0,
                        timestamp=datetime.utcnow(),
                        error=str(result)
                    )
                    results[checker_name] = error_result
                else:
                    results[checker_name] = result
        
        # Store results in history
        for result in results.values():
            self._add_to_history(result)
        
        return results
    
    async def _run_single_check(self, name: str, checker: BaseHealthChecker) -> HealthCheckResult:
        """Run a single health check with logging."""
        self.logger.debug(
            f"Running health check: {name}",
            checker_type=checker.check_type.value
        )
        
        try:
            result = await checker.check()
            
            # Update connectivity metrics if applicable
            if checker.check_type in [CheckType.AZURE_CONNECTIVITY, CheckType.DATABASE_CONNECTIVITY]:
                self._update_connectivity_metrics(name, result)
            
            self.logger.info(
                f"Health check completed: {name}",
                status=result.status.value,
                duration_ms=result.duration_ms,
                checker_type=checker.check_type.value
            )
            
            return result
            
        except Exception as e:
            self.logger.error(
                f"Health check failed: {name}",
                exception=e,
                checker_type=checker.check_type.value
            )
            raise
    
    def _add_to_history(self, result: HealthCheckResult) -> None:
        """Add result to history with size and time limits."""
        self.check_history.append(result)
        
        # Remove old entries
        cutoff_time = datetime.utcnow() - timedelta(hours=self.history_retention_hours)
        self.check_history = [
            r for r in self.check_history
            if r.timestamp > cutoff_time
        ]
        
        # Limit size
        if len(self.check_history) > self.max_history_size:
            self.check_history = self.check_history[-self.max_history_size:]
    
    def _update_connectivity_metrics(self, service_name: str, result: HealthCheckResult) -> None:
        """Update connectivity metrics for a service."""
        if service_name not in self.connectivity_metrics:
            self.connectivity_metrics[service_name] = ConnectivityMetrics(
                service_name=service_name,
                response_time_ms=0.0,
                success_rate=0.0
            )
        
        metrics = self.connectivity_metrics[service_name]
        metrics.response_time_ms = result.duration_ms
        metrics.total_checks += 1
        
        if result.status == HealthStatus.HEALTHY:
            metrics.successful_checks += 1
            metrics.last_success = result.timestamp
            metrics.consecutive_failures = 0
        else:
            metrics.last_failure = result.timestamp
            metrics.consecutive_failures += 1
        
        metrics.success_rate = metrics.successful_checks / metrics.total_checks
    
    async def get_overall_health(self) -> Dict[str, Any]:
        """Get overall system health status."""
        results = await self.check_health()
        
        if not results:
            return {
                "status": HealthStatus.UNKNOWN,
                "message": "No health checkers registered",
                "timestamp": datetime.utcnow().isoformat(),
                "checks": {}
            }
        
        # Determine overall status
        statuses = [result.status for result in results.values()]
        
        if HealthStatus.CRITICAL in statuses:
            overall_status = HealthStatus.CRITICAL
        elif HealthStatus.WARNING in statuses:
            overall_status = HealthStatus.WARNING
        elif all(status == HealthStatus.HEALTHY for status in statuses):
            overall_status = HealthStatus.HEALTHY
        else:
            overall_status = HealthStatus.UNKNOWN
        
        # Count statuses
        status_counts = {
            HealthStatus.HEALTHY: statuses.count(HealthStatus.HEALTHY),
            HealthStatus.WARNING: statuses.count(HealthStatus.WARNING),
            HealthStatus.CRITICAL: statuses.count(HealthStatus.CRITICAL),
            HealthStatus.UNKNOWN: statuses.count(HealthStatus.UNKNOWN)
        }
        
        # Create summary message
        total_checks = len(results)
        healthy_checks = status_counts[HealthStatus.HEALTHY]
        
        if overall_status == HealthStatus.HEALTHY:
            message = f"All {total_checks} health checks passed"
        else:
            failed_checks = total_checks - healthy_checks
            message = f"{failed_checks} of {total_checks} health checks failed"
        
        return {
            "status": overall_status,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            "summary": {
                "total_checks": total_checks,
                "status_counts": {k.value: v for k, v in status_counts.items()},
                "success_rate": healthy_checks / total_checks if total_checks > 0 else 0
            },
            "checks": {
                name: {
                    "status": result.status.value,
                    "message": result.message,
                    "duration_ms": result.duration_ms,
                    "timestamp": result.timestamp.isoformat(),
                    "details": result.details,
                    "error": result.error
                }
                for name, result in results.items()
            },
            "connectivity_metrics": {
                name: {
                    "response_time_ms": metrics.response_time_ms,
                    "success_rate": metrics.success_rate,
                    "consecutive_failures": metrics.consecutive_failures,
                    "total_checks": metrics.total_checks,
                    "last_success": metrics.last_success.isoformat() if metrics.last_success else None,
                    "last_failure": metrics.last_failure.isoformat() if metrics.last_failure else None
                }
                for name, metrics in self.connectivity_metrics.items()
            }
        }
    
    async def start_monitoring(self, interval: int = 60) -> None:
        """Start background health monitoring."""
        if self.monitoring_enabled:
            return
        
        self.monitoring_interval = interval
        self.monitoring_enabled = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        self.logger.info(
            "Started health monitoring",
            interval_seconds=interval,
            registered_checkers=list(self.checkers.keys())
        )
    
    async def stop_monitoring(self) -> None:
        """Stop background health monitoring."""
        self.monitoring_enabled = False
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
            self.monitoring_task = None
        
        self.logger.info("Stopped health monitoring")
    
    async def _monitoring_loop(self) -> None:
        """Background monitoring loop."""
        while self.monitoring_enabled:
            try:
                await self.check_health()
                await asyncio.sleep(self.monitoring_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(
                    "Error in health monitoring loop",
                    exception=e
                )
                await asyncio.sleep(self.monitoring_interval)
    
    def get_check_history(
        self,
        checker_name: Optional[str] = None,
        hours: int = 1,
        limit: Optional[int] = None
    ) -> List[HealthCheckResult]:
        """
        Get health check history.
        
        Args:
            checker_name: Filter by checker name, or None for all
            hours: Number of hours of history to return
            limit: Maximum number of results to return
            
        Returns:
            List of health check results
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        filtered_history = [
            result for result in self.check_history
            if result.timestamp > cutoff_time
            and (checker_name is None or result.check_name == checker_name)
        ]
        
        # Sort by timestamp (newest first)
        filtered_history.sort(key=lambda x: x.timestamp, reverse=True)
        
        if limit:
            filtered_history = filtered_history[:limit]
        
        return filtered_history
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of health check metrics."""
        if not self.check_history:
            return {"message": "No health check history available"}
        
        # Calculate metrics by checker
        checker_metrics = {}
        
        for result in self.check_history:
            checker_name = result.check_name
            
            if checker_name not in checker_metrics:
                checker_metrics[checker_name] = {
                    "total_checks": 0,
                    "successful_checks": 0,
                    "durations": [],
                    "last_check": None,
                    "last_success": None,
                    "last_failure": None
                }
            
            metrics = checker_metrics[checker_name]
            metrics["total_checks"] += 1
            metrics["durations"].append(result.duration_ms)
            metrics["last_check"] = result.timestamp
            
            if result.status == HealthStatus.HEALTHY:
                metrics["successful_checks"] += 1
                metrics["last_success"] = result.timestamp
            else:
                metrics["last_failure"] = result.timestamp
        
        # Calculate summary statistics
        for checker_name, metrics in checker_metrics.items():
            durations = metrics["durations"]
            
            metrics.update({
                "success_rate": metrics["successful_checks"] / metrics["total_checks"],
                "avg_duration_ms": sum(durations) / len(durations),
                "min_duration_ms": min(durations),
                "max_duration_ms": max(durations),
                "last_check": metrics["last_check"].isoformat() if metrics["last_check"] else None,
                "last_success": metrics["last_success"].isoformat() if metrics["last_success"] else None,
                "last_failure": metrics["last_failure"].isoformat() if metrics["last_failure"] else None
            })
            
            # Remove raw durations from output
            del metrics["durations"]
        
        return {
            "total_history_entries": len(self.check_history),
            "registered_checkers": list(self.checkers.keys()),
            "monitoring_enabled": self.monitoring_enabled,
            "monitoring_interval": self.monitoring_interval,
            "checker_metrics": checker_metrics
        }


# Global health manager instance
_health_manager: Optional[HealthCheckManager] = None


def get_health_manager() -> HealthCheckManager:
    """Get the global health manager instance."""
    global _health_manager
    if _health_manager is None:
        _health_manager = HealthCheckManager()
    return _health_manager


def initialize_default_health_checks(
    azure_service=None,
    db_session_factory=None,
    **system_thresholds
) -> HealthCheckManager:
    """
    Initialize health manager with default health checks.
    
    Args:
        azure_service: Azure File Share service instance
        db_session_factory: Database session factory
        **system_thresholds: Custom thresholds for system resource checker
        
    Returns:
        Configured HealthCheckManager instance
    """
    manager = get_health_manager()
    
    # Register default checkers
    if azure_service:
        manager.register_azure_checker(azure_service)
    
    if db_session_factory:
        manager.register_database_checker(db_session_factory)
    
    manager.register_system_checker(**system_thresholds)
    
    return manager