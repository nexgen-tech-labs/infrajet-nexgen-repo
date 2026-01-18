"""
Monitoring service for embeddings processing.
"""

import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict, Counter
import psutil
import asyncio
from logconfig.logger import get_logger

logger = get_logger()


@dataclass
class ProcessingMetrics:
    """Metrics for processing operations."""
    operation: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: float = 0.0
    success: bool = False
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemMetrics:
    """System resource metrics."""
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    disk_usage_percent: float
    timestamp: float


class EmbeddingMonitoringService:
    """Service for monitoring embedding processing operations."""

    def __init__(self):
        self.metrics_history: List[ProcessingMetrics] = []
        self.system_metrics_history: List[SystemMetrics] = []
        self.counters = defaultdict(Counter)
        self.gauges = {}
        self.histograms = defaultdict(list)

        # Start background monitoring
        self.monitoring_task = None
        self.is_monitoring = False

    async def start_monitoring(self):
        """Start background system monitoring."""
        if self.is_monitoring:
            return

        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(self._monitor_system_resources())
        logger.info("Started embedding monitoring service")

    async def stop_monitoring(self):
        """Stop background monitoring."""
        self.is_monitoring = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped embedding monitoring service")

    def record_processing_start(self, operation: str, metadata: Dict[str, Any] = None) -> str:
        """Record the start of a processing operation."""
        metric_id = f"{operation}_{int(time.time() * 1000)}"
        metric = ProcessingMetrics(
            operation=operation,
            start_time=time.time(),
            metadata=metadata or {}
        )
        self.metrics_history.append(metric)
        self.counters[operation]['started'] += 1

        # Keep only recent metrics
        if len(self.metrics_history) > 1000:
            self.metrics_history = self.metrics_history[-500:]

        return metric_id

    def record_processing_end(self, metric_id: str, success: bool = True, error_message: str = None):
        """Record the end of a processing operation."""
        for metric in reversed(self.metrics_history):
            if f"{metric.operation}_{int(metric.start_time * 1000)}" == metric_id:
                metric.end_time = time.time()
                metric.duration_ms = (metric.end_time - metric.start_time) * 1000
                metric.success = success
                metric.error_message = error_message

                # Update counters
                operation = metric.operation
                if success:
                    self.counters[operation]['completed'] += 1
                else:
                    self.counters[operation]['failed'] += 1

                # Update histograms
                self.histograms[operation].append(metric.duration_ms)
                if len(self.histograms[operation]) > 100:
                    self.histograms[operation] = self.histograms[operation][-50:]

                break

    def increment_counter(self, name: str, labels: Dict[str, str] = None):
        """Increment a counter metric."""
        key = name
        if labels:
            key = f"{name}_{'_'.join(f'{k}:{v}' for k, v in sorted(labels.items()))}"
        self.counters[name][key] += 1

    def set_gauge(self, name: str, value: float):
        """Set a gauge metric."""
        self.gauges[name] = value

    def observe_histogram(self, name: str, value: float):
        """Observe a histogram value."""
        self.histograms[name].append(value)
        if len(self.histograms[name]) > 100:
            self.histograms[name] = self.histograms[name][-50:]

    async def _monitor_system_resources(self):
        """Background task to monitor system resources."""
        while self.is_monitoring:
            try:
                # CPU usage
                cpu_percent = psutil.cpu_percent(interval=1)

                # Memory usage
                memory = psutil.virtual_memory()
                memory_percent = memory.percent
                memory_used_mb = memory.used / (1024 * 1024)

                # Disk usage
                disk = psutil.disk_usage('/')
                disk_usage_percent = disk.percent

                # Record metrics
                system_metric = SystemMetrics(
                    cpu_percent=cpu_percent,
                    memory_percent=memory_percent,
                    memory_used_mb=memory_used_mb,
                    disk_usage_percent=disk_usage_percent,
                    timestamp=time.time()
                )

                self.system_metrics_history.append(system_metric)

                # Keep only recent system metrics
                if len(self.system_metrics_history) > 100:
                    self.system_metrics_history = self.system_metrics_history[-50:]

                # Update gauges
                self.set_gauge('cpu_percent', cpu_percent)
                self.set_gauge('memory_percent', memory_percent)
                self.set_gauge('disk_usage_percent', disk_usage_percent)

                await asyncio.sleep(30)  # Monitor every 30 seconds

            except Exception as e:
                logger.error(f"Error monitoring system resources: {e}")
                await asyncio.sleep(30)

    def get_processing_stats(self, operation: str = None) -> Dict[str, Any]:
        """Get processing statistics."""
        if operation:
            operations = [operation]
        else:
            operations = list(self.counters.keys())

        stats = {}

        for op in operations:
            op_counters = self.counters[op]
            op_histogram = self.histograms[op]

            stats[op] = {
                'total_started': op_counters.get('started', 0),
                'total_completed': op_counters.get('completed', 0),
                'total_failed': op_counters.get('failed', 0),
                'success_rate': 0.0,
                'avg_duration_ms': 0.0,
                'min_duration_ms': 0.0,
                'max_duration_ms': 0.0,
                'p95_duration_ms': 0.0
            }

            total_completed = op_counters.get('completed', 0)
            total_started = op_counters.get('started', 0)

            if total_started > 0:
                stats[op]['success_rate'] = total_completed / total_started

            if op_histogram:
                sorted_durations = sorted(op_histogram)
                stats[op]['avg_duration_ms'] = sum(op_histogram) / len(op_histogram)
                stats[op]['min_duration_ms'] = min(op_histogram)
                stats[op]['max_duration_ms'] = max(op_histogram)

                # Calculate P95
                p95_index = int(len(sorted_durations) * 0.95)
                if p95_index < len(sorted_durations):
                    stats[op]['p95_duration_ms'] = sorted_durations[p95_index]

        return stats

    def get_system_stats(self) -> Dict[str, Any]:
        """Get current system statistics."""
        if not self.system_metrics_history:
            return {}

        latest = self.system_metrics_history[-1]

        # Calculate averages
        recent_metrics = self.system_metrics_history[-10:]  # Last 10 measurements

        return {
            'current': {
                'cpu_percent': latest.cpu_percent,
                'memory_percent': latest.memory_percent,
                'memory_used_mb': latest.memory_used_mb,
                'disk_usage_percent': latest.disk_usage_percent,
                'timestamp': latest.timestamp
            },
            'averages': {
                'cpu_percent': sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics),
                'memory_percent': sum(m.memory_percent for m in recent_metrics) / len(recent_metrics),
                'disk_usage_percent': sum(m.disk_usage_percent for m in recent_metrics) / len(recent_metrics)
            }
        }

    def get_health_status(self) -> Dict[str, Any]:
        """Get overall system health status."""
        system_stats = self.get_system_stats()
        processing_stats = self.get_processing_stats()

        # Determine health based on various factors
        health_score = 100

        if system_stats:
            current = system_stats.get('current', {})

            # Penalize high resource usage
            if current.get('cpu_percent', 0) > 90:
                health_score -= 20
            elif current.get('cpu_percent', 0) > 80:
                health_score -= 10

            if current.get('memory_percent', 0) > 90:
                health_score -= 20
            elif current.get('memory_percent', 0) > 80:
                health_score -= 10

        # Check for recent failures
        total_failed = sum(stats.get('total_failed', 0) for stats in processing_stats.values())
        total_completed = sum(stats.get('total_completed', 0) for stats in processing_stats.values())

        if total_completed > 0:
            failure_rate = total_failed / (total_failed + total_completed)
            if failure_rate > 0.1:  # More than 10% failure rate
                health_score -= 15
            elif failure_rate > 0.05:  # More than 5% failure rate
                health_score -= 5

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
            'system_stats': system_stats,
            'processing_stats': processing_stats,
            'timestamp': time.time()
        }

    def get_recent_errors(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent processing errors."""
        errors = []
        for metric in reversed(self.metrics_history):
            if not metric.success and metric.error_message:
                errors.append({
                    'operation': metric.operation,
                    'error_message': metric.error_message,
                    'duration_ms': metric.duration_ms,
                    'timestamp': metric.end_time,
                    'metadata': metric.metadata
                })
                if len(errors) >= limit:
                    break
        return errors