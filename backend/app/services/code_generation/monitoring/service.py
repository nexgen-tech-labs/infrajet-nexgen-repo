"""
Code Generation Monitoring Service.

This module provides comprehensive monitoring for the code generation system,
including Prometheus metrics, health checks, and performance tracking.
"""

import time
import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict, Counter
import psutil
import threading
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

from logconfig.logger import get_logger

logger = get_logger()


@dataclass
class GenerationMetrics:
    """Metrics for code generation operations."""
    operation: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: float = 0.0
    success: bool = False
    error_message: Optional[str] = None
    job_id: Optional[str] = None
    scenario: Optional[str] = None
    provider: Optional[str] = None
    tokens_used: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class CodeGenerationMonitoringService:
    """
    Monitoring service for code generation operations.

    Provides Prometheus metrics, health checks, and performance monitoring
    specifically tailored for the code generation system.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the monitoring service."""
        # Use class-level initialization flag to ensure thread-safety
        if not hasattr(self.__class__, '_initialized'):
            with self.__class__._lock:
                if not hasattr(self.__class__, '_initialized'):
                    self.__class__._initialized = True

                    self.metrics_history: List[GenerationMetrics] = []
                    self.system_metrics_history: List[Dict[str, Any]] = []
                    self.counters = defaultdict(Counter)
                    self.histograms = defaultdict(list)

                    # Prometheus metrics
                    self._setup_prometheus_metrics()

                    # Background monitoring
                    self.monitoring_task = None
                    self.is_monitoring = False

                    logger.info("CodeGenerationMonitoringService initialized")

    def _setup_prometheus_metrics(self):
        """Set up Prometheus metrics."""
        # Counters
        self.generation_requests_total = Counter(
            name='code_generation_requests_total',
            documentation='Total number of code generation requests',
            labelnames=['scenario', 'provider', 'status']
        )

        self.validation_requests_total = Counter(
            name='code_generation_validation_requests_total',
            documentation='Total number of validation requests',
            labelnames=['status']
        )

        self.diff_requests_total = Counter(
            name='code_generation_diff_requests_total',
            documentation='Total number of diff generation requests',
            labelnames=['status']
        )

        # Histograms
        self.generation_duration = Histogram(
            name='code_generation_duration_seconds',
            documentation='Time spent generating code',
            labelnames=['scenario', 'provider'],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0]
        )

        self.validation_duration = Histogram(
            name='code_generation_validation_duration_seconds',
            documentation='Time spent validating code',
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0]
        )

        self.diff_duration = Histogram(
            name='code_generation_diff_duration_seconds',
            documentation='Time spent generating diffs',
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0]
        )

        # Gauges
        self.active_jobs = Gauge(
            name='code_generation_active_jobs',
            documentation='Number of currently active generation jobs'
        )

        self.queued_jobs = Gauge(
            name='code_generation_queued_jobs',
            documentation='Number of queued generation jobs'
        )

        self.system_cpu_percent = Gauge(
            name='code_generation_system_cpu_percent',
            documentation='System CPU usage percentage'
        )

        self.system_memory_percent = Gauge(
            name='code_generation_system_memory_percent',
            documentation='System memory usage percentage'
        )

    async def start_monitoring(self):
        """Start background system monitoring."""
        if self.is_monitoring:
            return

        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(self._monitor_system_resources())
        logger.info("Started code generation monitoring service")

    async def stop_monitoring(self):
        """Stop background monitoring."""
        self.is_monitoring = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped code generation monitoring service")

    def record_generation_start(self, job_id: str, scenario: str, provider: str, metadata: Dict[str, Any] = None) -> str:
        """Record the start of a code generation operation."""
        metric_id = f"generation_{job_id}_{int(time.time() * 1000)}"
        metric = GenerationMetrics(
            operation="generation",
            start_time=time.time(),
            job_id=job_id,
            scenario=scenario,
            provider=provider,
            metadata=metadata or {}
        )
        self.metrics_history.append(metric)
        self.counters["generation"]["started"] += 1

        # Update Prometheus metrics
        self.active_jobs.inc()

        # Keep only recent metrics
        if len(self.metrics_history) > 1000:
            self.metrics_history = self.metrics_history[-500:]

        return metric_id

    def record_generation_end(self, metric_id: str, success: bool, error_message: str = None, tokens_used: int = None):
        """Record the end of a code generation operation."""
        for metric in reversed(self.metrics_history):
            if f"generation_{metric.job_id}_{int(metric.start_time * 1000)}" == metric_id:
                metric.end_time = time.time()
                metric.duration_ms = (metric.end_time - metric.start_time) * 1000
                metric.success = success
                metric.error_message = error_message
                metric.tokens_used = tokens_used

                # Update counters
                if success:
                    self.counters["generation"]["completed"] += 1
                else:
                    self.counters["generation"]["failed"] += 1

                # Update histograms
                self.histograms["generation"].append(metric.duration_ms)
                if len(self.histograms["generation"]) > 100:
                    self.histograms["generation"] = self.histograms["generation"][-50:]

                # Update Prometheus metrics
                self.active_jobs.dec()
                status = "success" if success else "failed"
                self.generation_requests_total.labels(
                    scenario=metric.scenario,
                    provider=metric.provider,
                    status=status
                ).inc()

                self.generation_duration.labels(
                    scenario=metric.scenario,
                    provider=metric.provider
                ).observe(metric.duration_ms / 1000)

                break

    def record_job_start(self, job_id: str, request_data: Dict[str, Any]):
        """Record job start for monitoring."""
        scenario = request_data.get("scenario", "unknown")
        provider = request_data.get("provider_type", "unknown")
        return self.record_generation_start(job_id, scenario, provider, request_data)

    def record_job_end(self, job_id: str, success: bool, metrics: Dict[str, Any] = None):
        """Record job completion for monitoring."""
        error_message = None
        tokens_used = None

        if metrics:
            error_message = metrics.get("error_message")
            tokens_used = metrics.get("tokens_used")

        # Find the metric by job_id
        for metric in reversed(self.metrics_history):
            if metric.job_id == job_id and metric.operation == "generation":
                metric_id = f"generation_{job_id}_{int(metric.start_time * 1000)}"
                self.record_generation_end(metric_id, success, error_message, tokens_used)
                break

    def record_validation_request(self, success: bool, duration_ms: float):
        """Record a validation request."""
        status = "success" if success else "failed"
        self.validation_requests_total.labels(status=status).inc()
        self.validation_duration.observe(duration_ms / 1000)

    def record_diff_request(self, success: bool, duration_ms: float):
        """Record a diff generation request."""
        status = "success" if success else "failed"
        self.diff_requests_total.labels(status=status).inc()
        self.diff_duration.observe(duration_ms / 1000)

    async def _monitor_system_resources(self):
        """Background task to monitor system resources."""
        while self.is_monitoring:
            try:
                # CPU usage
                cpu_percent = psutil.cpu_percent(interval=1)

                # Memory usage
                memory = psutil.virtual_memory()
                memory_percent = memory.percent

                # Update Prometheus gauges
                self.system_cpu_percent.set(cpu_percent)
                self.system_memory_percent.set(memory_percent)

                # Record system metrics
                system_metric = {
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory_percent,
                    "timestamp": time.time()
                }
                self.system_metrics_history.append(system_metric)

                # Keep only recent system metrics
                if len(self.system_metrics_history) > 100:
                    self.system_metrics_history = self.system_metrics_history[-50:]

                await asyncio.sleep(30)  # Monitor every 30 seconds

            except Exception as e:
                logger.error(f"Error monitoring system resources: {e}")
                await asyncio.sleep(30)

    def get_generation_stats(self) -> Dict[str, Any]:
        """Get generation statistics."""
        generation_metrics = [m for m in self.metrics_history if m.operation == "generation"]

        if not generation_metrics:
            return {"total_requests": 0, "success_rate": 0.0, "avg_duration_ms": 0.0}

        total_requests = len(generation_metrics)
        successful_requests = sum(1 for m in generation_metrics if m.success)
        success_rate = successful_requests / total_requests if total_requests > 0 else 0.0

        completed_metrics = [m for m in generation_metrics if m.end_time]
        avg_duration_ms = (
            sum(m.duration_ms for m in completed_metrics) / len(completed_metrics)
            if completed_metrics else 0.0
        )

        return {
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": total_requests - successful_requests,
            "success_rate": success_rate,
            "avg_duration_ms": avg_duration_ms,
            "active_jobs": self.active_jobs._value if hasattr(self.active_jobs, '_value') else 0
        }

    def get_health_status(self) -> Dict[str, Any]:
        """Get overall system health status."""
        generation_stats = self.get_generation_stats()

        # Determine health based on various factors
        health_score = 100

        # Check success rate
        success_rate = generation_stats.get("success_rate", 0)
        if success_rate < 0.8:  # Less than 80% success rate
            health_score -= 20
        elif success_rate < 0.9:  # Less than 90% success rate
            health_score -= 10

        # Check system resources
        if self.system_metrics_history:
            latest = self.system_metrics_history[-1]
            if latest.get('cpu_percent', 0) > 90:
                health_score -= 20
            elif latest.get('cpu_percent', 0) > 80:
                health_score -= 10

            if latest.get('memory_percent', 0) > 90:
                health_score -= 20
            elif latest.get('memory_percent', 0) > 80:
                health_score -= 10

        # Determine status
        if health_score >= 90:
            status = "healthy"
        elif health_score >= 70:
            status = "warning"
        else:
            status = "critical"

        return {
            'status': status,
            'health_score': health_score,
            'generation_stats': generation_stats,
            'system_stats': self.system_metrics_history[-1] if self.system_metrics_history else {},
            'timestamp': time.time()
        }

    def get_prometheus_metrics(self) -> str:
        """Get Prometheus-formatted metrics."""
        return generate_latest()

    def get_recent_errors(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent generation errors."""
        errors = []
        for metric in reversed(self.metrics_history):
            if not metric.success and metric.error_message:
                errors.append({
                    'job_id': metric.job_id,
                    'operation': metric.operation,
                    'error_message': metric.error_message,
                    'duration_ms': metric.duration_ms,
                    'scenario': metric.scenario,
                    'provider': metric.provider,
                    'timestamp': metric.end_time,
                    'metadata': metric.metadata
                })
                if len(errors) >= limit:
                    break
        return errors