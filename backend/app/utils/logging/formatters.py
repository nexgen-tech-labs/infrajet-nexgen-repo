"""
Log formatters for Azure File Share operations.

Provides specialized formatters for different types of log entries,
including Azure operations, structured data, and aggregation utilities.
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass, asdict


class LogFormat(str, Enum):
    """Available log formats."""
    JSON = "json"
    STRUCTURED = "structured"
    AZURE_OPERATION = "azure_operation"
    COMPACT = "compact"


@dataclass
class LogEntry:
    """Structured log entry data class."""
    timestamp: str
    level: str
    message: str
    correlation_id: Optional[str] = None
    user_id: Optional[int] = None
    project_id: Optional[str] = None
    operation_type: Optional[str] = None
    operation_id: Optional[str] = None
    duration_ms: Optional[float] = None
    success: Optional[bool] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None


class StructuredFormatter:
    """
    Formatter for structured log entries with consistent format.
    
    Provides standardized formatting for all log entries with
    proper field ordering and data serialization.
    """
    
    def __init__(self, format_type: LogFormat = LogFormat.JSON):
        self.format_type = format_type
    
    def format_log_entry(
        self,
        level: str,
        message: str,
        correlation_id: Optional[str] = None,
        user_id: Optional[int] = None,
        project_id: Optional[str] = None,
        operation_type: Optional[str] = None,
        operation_id: Optional[str] = None,
        duration_ms: Optional[float] = None,
        success: Optional[bool] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """Format a log entry according to the specified format."""
        
        entry = LogEntry(
            timestamp=datetime.utcnow().isoformat(),
            level=level,
            message=message,
            correlation_id=correlation_id,
            user_id=user_id,
            project_id=project_id,
            operation_type=operation_type,
            operation_id=operation_id,
            duration_ms=duration_ms,
            success=success,
            error_type=error_type,
            error_message=error_message,
            extra_data=extra_data
        )
        
        if self.format_type == LogFormat.JSON:
            return self._format_json(entry)
        elif self.format_type == LogFormat.STRUCTURED:
            return self._format_structured(entry)
        elif self.format_type == LogFormat.COMPACT:
            return self._format_compact(entry)
        else:
            return self._format_json(entry)
    
    def _format_json(self, entry: LogEntry) -> str:
        """Format as JSON."""
        # Convert to dict and remove None values
        data = {k: v for k, v in asdict(entry).items() if v is not None}
        return json.dumps(data, default=str, separators=(',', ':'))
    
    def _format_structured(self, entry: LogEntry) -> str:
        """Format as structured text."""
        parts = [
            f"[{entry.timestamp}]",
            f"[{entry.level}]",
            f"[{entry.correlation_id or 'NO-CORRELATION'}]"
        ]
        
        if entry.user_id:
            parts.append(f"[user:{entry.user_id}]")
        
        if entry.project_id:
            parts.append(f"[project:{entry.project_id}]")
        
        if entry.operation_type:
            parts.append(f"[op:{entry.operation_type}]")
        
        if entry.duration_ms is not None:
            parts.append(f"[{entry.duration_ms:.2f}ms]")
        
        if entry.success is not None:
            status = "SUCCESS" if entry.success else "FAILURE"
            parts.append(f"[{status}]")
        
        parts.append(entry.message)
        
        if entry.error_type:
            parts.append(f"ERROR: {entry.error_type}: {entry.error_message}")
        
        return " ".join(parts)
    
    def _format_compact(self, entry: LogEntry) -> str:
        """Format as compact single line."""
        parts = [
            entry.timestamp[:19],  # Remove microseconds
            entry.level[:1],  # First letter only
            entry.correlation_id[:8] if entry.correlation_id else "--------",
            entry.message
        ]
        
        if entry.duration_ms is not None:
            parts.append(f"({entry.duration_ms:.0f}ms)")
        
        return " | ".join(parts)


class AzureOperationFormatter:
    """
    Specialized formatter for Azure File Share operations.
    
    Provides detailed formatting for Azure operations with
    operation-specific fields and metrics.
    """
    
    def __init__(self):
        self.base_formatter = StructuredFormatter(LogFormat.JSON)
    
    def format_operation_start(
        self,
        operation_type: str,
        operation_id: str,
        correlation_id: Optional[str] = None,
        user_id: Optional[int] = None,
        project_id: Optional[str] = None,
        operation_details: Optional[Dict[str, Any]] = None
    ) -> str:
        """Format Azure operation start log."""
        
        extra_data = {
            "phase": "start",
            "operation_id": operation_id
        }
        
        if operation_details:
            extra_data["operation_details"] = operation_details
        
        return self.base_formatter.format_log_entry(
            level="INFO",
            message=f"Azure operation started: {operation_type}",
            correlation_id=correlation_id,
            user_id=user_id,
            project_id=project_id,
            operation_type=operation_type,
            operation_id=operation_id,
            extra_data=extra_data
        )
    
    def format_operation_success(
        self,
        operation_type: str,
        operation_id: str,
        duration_ms: float,
        correlation_id: Optional[str] = None,
        user_id: Optional[int] = None,
        project_id: Optional[str] = None,
        result_details: Optional[Dict[str, Any]] = None
    ) -> str:
        """Format Azure operation success log."""
        
        extra_data = {
            "phase": "success",
            "operation_id": operation_id
        }
        
        if result_details:
            extra_data["result_details"] = result_details
        
        return self.base_formatter.format_log_entry(
            level="INFO",
            message=f"Azure operation completed: {operation_type}",
            correlation_id=correlation_id,
            user_id=user_id,
            project_id=project_id,
            operation_type=operation_type,
            operation_id=operation_id,
            duration_ms=duration_ms,
            success=True,
            extra_data=extra_data
        )
    
    def format_operation_failure(
        self,
        operation_type: str,
        operation_id: str,
        duration_ms: float,
        error_type: str,
        error_message: str,
        correlation_id: Optional[str] = None,
        user_id: Optional[int] = None,
        project_id: Optional[str] = None,
        retry_count: Optional[int] = None
    ) -> str:
        """Format Azure operation failure log."""
        
        extra_data = {
            "phase": "failure",
            "operation_id": operation_id
        }
        
        if retry_count is not None:
            extra_data["retry_count"] = retry_count
        
        return self.base_formatter.format_log_entry(
            level="ERROR",
            message=f"Azure operation failed: {operation_type}",
            correlation_id=correlation_id,
            user_id=user_id,
            project_id=project_id,
            operation_type=operation_type,
            operation_id=operation_id,
            duration_ms=duration_ms,
            success=False,
            error_type=error_type,
            error_message=error_message,
            extra_data=extra_data
        )


class LogAggregator:
    """
    Utility for aggregating and analyzing log entries.
    
    Provides methods for collecting, filtering, and analyzing
    log data for monitoring and debugging purposes.
    """
    
    def __init__(self):
        self.entries: List[Dict[str, Any]] = []
    
    def add_entry(self, log_entry: str) -> None:
        """Add a log entry for aggregation."""
        try:
            if log_entry.startswith('{'):
                # JSON format
                entry = json.loads(log_entry)
                self.entries.append(entry)
        except json.JSONDecodeError:
            # Skip non-JSON entries
            pass
    
    def get_entries_by_operation(self, operation_type: str) -> List[Dict[str, Any]]:
        """Get all entries for a specific operation type."""
        return [
            entry for entry in self.entries
            if entry.get("operation_type") == operation_type
        ]
    
    def get_entries_by_correlation_id(self, correlation_id: str) -> List[Dict[str, Any]]:
        """Get all entries for a specific correlation ID."""
        return [
            entry for entry in self.entries
            if entry.get("correlation_id") == correlation_id
        ]
    
    def get_failed_operations(self) -> List[Dict[str, Any]]:
        """Get all failed operations."""
        return [
            entry for entry in self.entries
            if entry.get("success") is False or entry.get("level") == "ERROR"
        ]
    
    def get_operation_metrics(self, operation_type: str) -> Dict[str, Any]:
        """Get metrics for a specific operation type."""
        entries = self.get_entries_by_operation(operation_type)
        
        if not entries:
            return {"count": 0}
        
        durations = [
            entry.get("duration_ms", 0) for entry in entries
            if entry.get("duration_ms") is not None
        ]
        
        success_count = len([
            entry for entry in entries
            if entry.get("success") is True
        ])
        
        failure_count = len([
            entry for entry in entries
            if entry.get("success") is False
        ])
        
        return {
            "count": len(entries),
            "success_count": success_count,
            "failure_count": failure_count,
            "success_rate": success_count / len(entries) if entries else 0,
            "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
            "min_duration_ms": min(durations) if durations else 0,
            "max_duration_ms": max(durations) if durations else 0
        }
    
    def clear(self) -> None:
        """Clear all aggregated entries."""
        self.entries.clear()


# Global instances
structured_formatter = StructuredFormatter()
azure_formatter = AzureOperationFormatter()
log_aggregator = LogAggregator()


def get_structured_formatter(format_type: LogFormat = LogFormat.JSON) -> StructuredFormatter:
    """Get a structured formatter instance."""
    return StructuredFormatter(format_type)


def get_azure_formatter() -> AzureOperationFormatter:
    """Get an Azure operation formatter instance."""
    return azure_formatter


def get_log_aggregator() -> LogAggregator:
    """Get the global log aggregator instance."""
    return log_aggregator