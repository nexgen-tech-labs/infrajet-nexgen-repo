"""
Azure File Share Connection Manager.

This module provides connection management, pooling, and health checks
for Azure File Share operations.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum

from azure.storage.fileshare.aio import ShareServiceClient, ShareClient, ShareFileClient
from azure.core.exceptions import (
    AzureError, 
    ServiceRequestError, 
    ResourceNotFoundError,
    ClientAuthenticationError
)

from app.core.azure_config import AzureFileShareConfig, get_azure_config


class ConnectionStatus(Enum):
    """Connection status enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ConnectionMetrics:
    """Connection metrics for monitoring."""
    total_connections: int = 0
    active_connections: int = 0
    failed_connections: int = 0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    average_response_time: float = 0.0
    response_times: List[float] = field(default_factory=list)
    
    def add_response_time(self, response_time: float) -> None:
        """Add a response time measurement."""
        self.response_times.append(response_time)
        # Keep only last 100 measurements
        if len(self.response_times) > 100:
            self.response_times = self.response_times[-100:]
        self.average_response_time = sum(self.response_times) / len(self.response_times)
    
    def record_success(self) -> None:
        """Record a successful connection."""
        self.last_success = datetime.utcnow()
    
    def record_failure(self) -> None:
        """Record a failed connection."""
        self.failed_connections += 1
        self.last_failure = datetime.utcnow()


@dataclass
class HealthCheckResult:
    """Health check result."""
    status: ConnectionStatus
    message: str
    timestamp: datetime
    response_time: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)


class AzureConnectionManager:
    """
    Manages Azure File Share connections with pooling and health monitoring.
    
    Features:
    - Connection pooling and reuse
    - Health checks and monitoring
    - Automatic retry and recovery
    - Performance metrics tracking
    """
    
    def __init__(self, config: Optional[AzureFileShareConfig] = None):
        """Initialize the connection manager."""
        self.config = config or get_azure_config()
        self.logger = logging.getLogger(__name__)
        
        # Connection pool
        self._service_client: Optional[ShareServiceClient] = None
        self._share_client: Optional[ShareClient] = None
        self._connection_lock = asyncio.Lock()
        
        # Health monitoring
        self.metrics = ConnectionMetrics()
        self._last_health_check: Optional[HealthCheckResult] = None
        self._health_check_interval = timedelta(minutes=5)
        
        # Configuration
        self._max_retries = self.config.AZURE_RETRY_ATTEMPTS
        self._retry_delay = self.config.AZURE_RETRY_DELAY
        self._timeout = self.config.AZURE_TIMEOUT_SECONDS
    
    async def initialize(self) -> bool:
        """
        Initialize the connection manager.
        
        Returns:
            True if initialization successful, False otherwise.
        """
        try:
            if not self.config.is_enabled():
                self.logger.info("Azure File Share integration is disabled")
                return True
            
            async with self._connection_lock:
                await self._create_service_client()
                await self._ensure_share_exists()
                
            # Perform initial health check
            health_result = await self.health_check()
            if health_result.status == ConnectionStatus.HEALTHY:
                self.logger.info("Azure File Share connection initialized successfully")
                return True
            else:
                self.logger.error(f"Azure File Share initialization failed: {health_result.message}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to initialize Azure connection manager: {e}")
            return False
    
    async def _create_service_client(self) -> None:
        """Create Azure service client."""
        try:
            connection_string = self.config.get_connection_string()
            self._service_client = ShareServiceClient.from_connection_string(
                connection_string,
                timeout=self._timeout
            )
            
            # Create share client
            self._share_client = self._service_client.get_share_client(
                share=self.config.AZURE_FILE_SHARE_NAME
            )
            
            self.metrics.total_connections += 1
            self.logger.debug("Azure service client created successfully")
            
        except Exception as e:
            self.metrics.record_failure()
            self.logger.error(f"Failed to create Azure service client: {e}")
            raise
    
    async def _ensure_share_exists(self) -> None:
        """Ensure the file share exists, create if necessary."""
        if not self._share_client:
            raise RuntimeError("Share client not initialized")
        
        try:
            # Check if share exists
            await self._share_client.get_share_properties()
            self.logger.debug(f"File share '{self.config.AZURE_FILE_SHARE_NAME}' exists")
            
        except ResourceNotFoundError:
            if self.config.AZURE_AUTO_CREATE_SHARE:
                try:
                    await self._share_client.create_share()
                    self.logger.info(f"Created file share '{self.config.AZURE_FILE_SHARE_NAME}'")
                except Exception as e:
                    self.logger.error(f"Failed to create file share: {e}")
                    raise
            else:
                raise RuntimeError(
                    f"File share '{self.config.AZURE_FILE_SHARE_NAME}' does not exist "
                    "and auto-creation is disabled"
                )
    
    @asynccontextmanager
    async def get_service_client(self):
        """
        Get a service client with connection management.
        
        Yields:
            ShareServiceClient: Azure service client.
        """
        if not self.config.is_enabled():
            raise RuntimeError("Azure File Share integration is disabled")
        
        start_time = datetime.utcnow()
        
        try:
            async with self._connection_lock:
                if not self._service_client:
                    await self._create_service_client()
                
                self.metrics.active_connections += 1
                
            yield self._service_client
            
            # Record success metrics
            response_time = (datetime.utcnow() - start_time).total_seconds()
            self.metrics.add_response_time(response_time)
            self.metrics.record_success()
            
        except Exception as e:
            self.metrics.record_failure()
            self.logger.error(f"Error with service client: {e}")
            raise
        finally:
            self.metrics.active_connections = max(0, self.metrics.active_connections - 1)
    
    @asynccontextmanager
    async def get_share_client(self):
        """
        Get a share client with connection management.
        
        Yields:
            ShareClient: Azure share client.
        """
        if not self.config.is_enabled():
            raise RuntimeError("Azure File Share integration is disabled")
        
        start_time = datetime.utcnow()
        
        try:
            async with self._connection_lock:
                if not self._share_client:
                    await self._create_service_client()
                    await self._ensure_share_exists()
                
                self.metrics.active_connections += 1
                
            yield self._share_client
            
            # Record success metrics
            response_time = (datetime.utcnow() - start_time).total_seconds()
            self.metrics.add_response_time(response_time)
            self.metrics.record_success()
            
        except Exception as e:
            self.metrics.record_failure()
            self.logger.error(f"Error with share client: {e}")
            raise
        finally:
            self.metrics.active_connections = max(0, self.metrics.active_connections - 1)
    
    async def get_file_client(self, file_path: str) -> ShareFileClient:
        """
        Get a file client for a specific file.
        
        Args:
            file_path: Path to the file in the share.
            
        Returns:
            ShareFileClient: Azure file client.
        """
        if not self.config.is_enabled():
            raise RuntimeError("Azure File Share integration is disabled")
        
        async with self.get_share_client() as share_client:
            return share_client.get_file_client(file_path)
    
    async def health_check(self, force: bool = False) -> HealthCheckResult:
        """
        Perform a health check on the Azure connection.
        
        Args:
            force: Force a new health check even if recent one exists.
            
        Returns:
            HealthCheckResult: Health check result.
        """
        # Return cached result if recent and not forced
        if (not force and 
            self._last_health_check and 
            datetime.utcnow() - self._last_health_check.timestamp < self._health_check_interval):
            return self._last_health_check
        
        start_time = datetime.utcnow()
        
        try:
            if not self.config.is_enabled():
                result = HealthCheckResult(
                    status=ConnectionStatus.HEALTHY,
                    message="Azure File Share integration is disabled",
                    timestamp=datetime.utcnow(),
                    details={"enabled": False}
                )
            else:
                # Test connection by getting share properties
                async with self.get_share_client() as share_client:
                    properties = await share_client.get_share_properties()
                    
                response_time = (datetime.utcnow() - start_time).total_seconds()
                
                result = HealthCheckResult(
                    status=ConnectionStatus.HEALTHY,
                    message="Connection healthy",
                    timestamp=datetime.utcnow(),
                    response_time=response_time,
                    details={
                        "enabled": True,
                        "share_name": self.config.AZURE_FILE_SHARE_NAME,
                        "quota": properties.get("quota", "unknown"),
                        "metrics": {
                            "total_connections": self.metrics.total_connections,
                            "active_connections": self.metrics.active_connections,
                            "failed_connections": self.metrics.failed_connections,
                            "average_response_time": self.metrics.average_response_time
                        }
                    }
                )
                
        except ClientAuthenticationError as e:
            result = HealthCheckResult(
                status=ConnectionStatus.UNHEALTHY,
                message=f"Authentication failed: {e}",
                timestamp=datetime.utcnow(),
                details={"error_type": "authentication", "enabled": True}
            )
        except ResourceNotFoundError as e:
            result = HealthCheckResult(
                status=ConnectionStatus.UNHEALTHY,
                message=f"Share not found: {e}",
                timestamp=datetime.utcnow(),
                details={"error_type": "not_found", "enabled": True}
            )
        except ServiceRequestError as e:
            result = HealthCheckResult(
                status=ConnectionStatus.DEGRADED,
                message=f"Service request failed: {e}",
                timestamp=datetime.utcnow(),
                details={"error_type": "service_request", "enabled": True}
            )
        except Exception as e:
            result = HealthCheckResult(
                status=ConnectionStatus.UNHEALTHY,
                message=f"Unexpected error: {e}",
                timestamp=datetime.utcnow(),
                details={"error_type": "unexpected", "enabled": True}
            )
        
        self._last_health_check = result
        return result
    
    async def test_connection(self) -> Dict[str, Any]:
        """
        Test the Azure connection and return detailed results.
        
        Returns:
            Dict containing test results and metrics.
        """
        test_results = {
            "timestamp": datetime.utcnow().isoformat(),
            "config_valid": False,
            "connection_successful": False,
            "share_accessible": False,
            "response_time": None,
            "error": None,
            "metrics": {
                "total_connections": self.metrics.total_connections,
                "active_connections": self.metrics.active_connections,
                "failed_connections": self.metrics.failed_connections,
                "average_response_time": self.metrics.average_response_time
            }
        }
        
        try:
            # Test configuration
            self.config.get_connection_string()
            test_results["config_valid"] = True
            
            if not self.config.is_enabled():
                test_results["connection_successful"] = True
                test_results["share_accessible"] = True
                test_results["error"] = "Azure integration disabled"
                return test_results
            
            # Test connection
            start_time = datetime.utcnow()
            
            async with self.get_share_client() as share_client:
                properties = await share_client.get_share_properties()
                test_results["connection_successful"] = True
                test_results["share_accessible"] = True
                
                response_time = (datetime.utcnow() - start_time).total_seconds()
                test_results["response_time"] = response_time
                
                test_results["share_info"] = {
                    "name": self.config.AZURE_FILE_SHARE_NAME,
                    "quota": properties.get("quota"),
                    "last_modified": properties.get("last_modified")
                }
                
        except Exception as e:
            test_results["error"] = str(e)
            self.logger.error(f"Connection test failed: {e}")
        
        return test_results
    
    async def close(self) -> None:
        """Close all connections and cleanup resources."""
        try:
            async with self._connection_lock:
                if self._service_client:
                    await self._service_client.close()
                    self._service_client = None
                
                if self._share_client:
                    # Share client is closed when service client is closed
                    self._share_client = None
                
            self.logger.info("Azure connection manager closed successfully")
            
        except Exception as e:
            self.logger.error(f"Error closing Azure connection manager: {e}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current connection metrics."""
        return {
            "total_connections": self.metrics.total_connections,
            "active_connections": self.metrics.active_connections,
            "failed_connections": self.metrics.failed_connections,
            "last_success": self.metrics.last_success.isoformat() if self.metrics.last_success else None,
            "last_failure": self.metrics.last_failure.isoformat() if self.metrics.last_failure else None,
            "average_response_time": self.metrics.average_response_time,
            "recent_response_times": self.metrics.response_times[-10:] if self.metrics.response_times else []
        }


# Global connection manager instance
_connection_manager: Optional[AzureConnectionManager] = None


async def get_connection_manager() -> AzureConnectionManager:
    """
    Get the global connection manager instance.
    
    Returns:
        AzureConnectionManager: Global connection manager.
    """
    global _connection_manager
    
    if _connection_manager is None:
        _connection_manager = AzureConnectionManager()
        await _connection_manager.initialize()
    
    return _connection_manager


async def close_connection_manager() -> None:
    """Close the global connection manager."""
    global _connection_manager
    
    if _connection_manager:
        await _connection_manager.close()
        _connection_manager = None


# Connection testing utilities
class ConnectionTester:
    """Utilities for testing Azure connections."""
    
    @staticmethod
    async def test_connection_with_config(config: AzureFileShareConfig) -> Dict[str, Any]:
        """
        Test connection with a specific configuration.
        
        Args:
            config: Azure configuration to test.
            
        Returns:
            Dict containing test results.
        """
        manager = AzureConnectionManager(config)
        
        try:
            await manager.initialize()
            return await manager.test_connection()
        finally:
            await manager.close()
    
    @staticmethod
    async def benchmark_connection(
        config: AzureFileShareConfig, 
        iterations: int = 10
    ) -> Dict[str, Any]:
        """
        Benchmark connection performance.
        
        Args:
            config: Azure configuration to test.
            iterations: Number of test iterations.
            
        Returns:
            Dict containing benchmark results.
        """
        manager = AzureConnectionManager(config)
        response_times = []
        errors = []
        
        try:
            await manager.initialize()
            
            for i in range(iterations):
                try:
                    start_time = datetime.utcnow()
                    health_result = await manager.health_check(force=True)
                    response_time = (datetime.utcnow() - start_time).total_seconds()
                    
                    if health_result.status == ConnectionStatus.HEALTHY:
                        response_times.append(response_time)
                    else:
                        errors.append(f"Iteration {i}: {health_result.message}")
                        
                except Exception as e:
                    errors.append(f"Iteration {i}: {e}")
            
            return {
                "iterations": iterations,
                "successful": len(response_times),
                "failed": len(errors),
                "success_rate": len(response_times) / iterations * 100,
                "response_times": {
                    "min": min(response_times) if response_times else None,
                    "max": max(response_times) if response_times else None,
                    "avg": sum(response_times) / len(response_times) if response_times else None,
                    "all": response_times
                },
                "errors": errors
            }
            
        finally:
            await manager.close()