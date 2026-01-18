"""
Security event logging service for comprehensive security monitoring.

This service provides specialized logging for security events, suspicious activities,
and audit trails with structured logging and alerting capabilities.
"""

import json
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
from enum import Enum
from dataclasses import dataclass, field

from logconfig.logger import get_logger
from ..exceptions.security_exceptions import SecurityError

logger = get_logger()


class SecurityEventType(Enum):
    """Types of security events."""

    AUTHENTICATION_FAILURE = "authentication_failure"
    AUTHORIZATION_VIOLATION = "authorization_violation"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    BRUTE_FORCE_ATTEMPT = "brute_force_attempt"
    TOKEN_MANIPULATION = "token_manipulation"
    SESSION_HIJACKING = "session_hijacking"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    DATA_EXFILTRATION = "data_exfiltration"
    INJECTION_ATTEMPT = "injection_attempt"
    ANOMALOUS_PATTERN = "anomalous_pattern"
    COMPLIANCE_VIOLATION = "compliance_violation"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    CONFIGURATION_TAMPERING = "configuration_tampering"
    UNAUTHORIZED_ACCESS = "unauthorized_access"


class SecuritySeverity(Enum):
    """Security event severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityEvent:
    """Security event data structure."""

    event_id: str
    event_type: SecurityEventType
    severity: SecuritySeverity
    timestamp: datetime
    user_id: Optional[int]
    ip_address: Optional[str]
    user_agent: Optional[str]
    description: str
    details: Dict[str, Any] = field(default_factory=dict)
    request_context: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolution_notes: Optional[str] = None
    tags: Set[str] = field(default_factory=set)


@dataclass
class SecurityAlert:
    """Security alert for high-priority events."""

    alert_id: str
    event_ids: List[str]
    alert_type: str
    severity: SecuritySeverity
    timestamp: datetime
    description: str
    affected_users: Set[int] = field(default_factory=set)
    affected_ips: Set[str] = field(default_factory=set)
    auto_response_triggered: bool = False
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None


class SecurityLoggingService:
    """
    Comprehensive security logging service with event tracking,
    pattern detection, and alerting capabilities.
    """

    def __init__(self):
        self.events: Dict[str, SecurityEvent] = {}
        self.alerts: Dict[str, SecurityAlert] = {}
        self.user_activity_tracking: Dict[int, List[SecurityEvent]] = {}
        self.ip_activity_tracking: Dict[str, List[SecurityEvent]] = {}
        self.event_patterns: Dict[str, List[datetime]] = {}
        self.blocked_ips: Dict[str, datetime] = {}
        self.blocked_users: Dict[int, datetime] = {}

        # Configuration
        self.max_events_per_user = 1000
        self.max_events_per_ip = 500
        self.event_retention_days = 90
        self.pattern_detection_window_hours = 24

        # Thresholds for automatic alerting
        self.alert_thresholds = {
            SecurityEventType.BRUTE_FORCE_ATTEMPT: 5,
            SecurityEventType.AUTHENTICATION_FAILURE: 10,
            SecurityEventType.SUSPICIOUS_ACTIVITY: 3,
            SecurityEventType.TOKEN_MANIPULATION: 1,
            SecurityEventType.SESSION_HIJACKING: 1,
            SecurityEventType.PRIVILEGE_ESCALATION: 1,
            SecurityEventType.DATA_EXFILTRATION: 1,
            SecurityEventType.INJECTION_ATTEMPT: 5,
        }

    def log_security_event(
        self,
        event_type: SecurityEventType,
        severity: SecuritySeverity,
        description: str,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        request_context: Optional[Dict[str, Any]] = None,
        tags: Optional[Set[str]] = None,
    ) -> str:
        """
        Log a security event with comprehensive tracking.

        Args:
            event_type: Type of security event
            severity: Severity level
            description: Human-readable description
            user_id: Optional user ID involved
            ip_address: Optional IP address
            user_agent: Optional user agent string
            details: Optional additional details
            request_context: Optional request context
            tags: Optional tags for categorization

        Returns:
            Event ID for tracking
        """
        event_id = self._generate_event_id()

        event = SecurityEvent(
            event_id=event_id,
            event_type=event_type,
            severity=severity,
            timestamp=datetime.utcnow(),
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            description=description,
            details=details or {},
            request_context=request_context or {},
            tags=tags or set(),
        )

        # Store the event
        self.events[event_id] = event

        # Track by user and IP
        if user_id:
            if user_id not in self.user_activity_tracking:
                self.user_activity_tracking[user_id] = []
            self.user_activity_tracking[user_id].append(event)
            self._cleanup_user_events(user_id)

        if ip_address:
            if ip_address not in self.ip_activity_tracking:
                self.ip_activity_tracking[ip_address] = []
            self.ip_activity_tracking[ip_address].append(event)
            self._cleanup_ip_events(ip_address)

        # Log to structured logger
        self._log_to_structured_logger(event)

        # Check for patterns and potential alerts
        self._check_for_patterns(event)

        # Check if automatic response is needed
        self._check_automatic_response(event)

        return event_id

    def log_security_exception(
        self,
        exception: SecurityError,
        request_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Log a security exception as a security event.

        Args:
            exception: Security exception to log
            request_context: Optional request context

        Returns:
            Event ID for tracking
        """
        # Map exception to event type
        event_type = self._map_exception_to_event_type(exception)
        severity = self._map_severity_string_to_enum(exception.security_level)

        return self.log_security_event(
            event_type=event_type,
            severity=severity,
            description=exception.message,
            user_id=exception.user_id,
            ip_address=exception.ip_address,
            user_agent=exception.user_agent,
            details=exception.details,
            request_context=request_context,
            tags={exception.error_code} if exception.error_code else set(),
        )

    def create_security_alert(
        self,
        alert_type: str,
        severity: SecuritySeverity,
        description: str,
        event_ids: List[str],
        affected_users: Optional[Set[int]] = None,
        affected_ips: Optional[Set[str]] = None,
    ) -> str:
        """
        Create a security alert for high-priority events.

        Args:
            alert_type: Type of alert
            severity: Alert severity
            description: Alert description
            event_ids: Related event IDs
            affected_users: Set of affected user IDs
            affected_ips: Set of affected IP addresses

        Returns:
            Alert ID for tracking
        """
        alert_id = self._generate_alert_id()

        alert = SecurityAlert(
            alert_id=alert_id,
            event_ids=event_ids,
            alert_type=alert_type,
            severity=severity,
            timestamp=datetime.utcnow(),
            description=description,
            affected_users=affected_users or set(),
            affected_ips=affected_ips or set(),
        )

        self.alerts[alert_id] = alert

        # Log alert
        logger.critical(
            f"Security alert created: {description}",
            extra={
                "alert_id": alert_id,
                "alert_type": alert_type,
                "severity": severity.value,
                "event_count": len(event_ids),
                "affected_users": list(affected_users) if affected_users else [],
                "affected_ips": list(affected_ips) if affected_ips else [],
            },
        )

        return alert_id

    def get_security_events(
        self,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        event_type: Optional[SecurityEventType] = None,
        severity: Optional[SecuritySeverity] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[SecurityEvent]:
        """
        Retrieve security events with filtering options.

        Args:
            user_id: Filter by user ID
            ip_address: Filter by IP address
            event_type: Filter by event type
            severity: Filter by severity
            start_time: Filter by start time
            end_time: Filter by end time
            limit: Maximum number of events to return

        Returns:
            List of matching security events
        """
        events = list(self.events.values())

        # Apply filters
        if user_id is not None:
            events = [e for e in events if e.user_id == user_id]

        if ip_address:
            events = [e for e in events if e.ip_address == ip_address]

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        if severity:
            events = [e for e in events if e.severity == severity]

        if start_time:
            events = [e for e in events if e.timestamp >= start_time]

        if end_time:
            events = [e for e in events if e.timestamp <= end_time]

        # Sort by timestamp (newest first) and limit
        events.sort(key=lambda x: x.timestamp, reverse=True)
        return events[:limit]

    def get_security_alerts(
        self,
        severity: Optional[SecuritySeverity] = None,
        acknowledged: Optional[bool] = None,
        limit: int = 50,
    ) -> List[SecurityAlert]:
        """
        Retrieve security alerts with filtering options.

        Args:
            severity: Filter by severity
            acknowledged: Filter by acknowledgment status
            limit: Maximum number of alerts to return

        Returns:
            List of matching security alerts
        """
        alerts = list(self.alerts.values())

        # Apply filters
        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        if acknowledged is not None:
            alerts = [a for a in alerts if a.acknowledged == acknowledged]

        # Sort by timestamp (newest first) and limit
        alerts.sort(key=lambda x: x.timestamp, reverse=True)
        return alerts[:limit]

    def get_user_security_summary(self, user_id: int) -> Dict[str, Any]:
        """
        Get security summary for a specific user.

        Args:
            user_id: User ID to analyze

        Returns:
            Security summary dictionary
        """
        user_events = self.user_activity_tracking.get(user_id, [])

        # Calculate statistics
        total_events = len(user_events)
        events_by_type = {}
        events_by_severity = {}
        recent_events = []

        cutoff_time = datetime.utcnow() - timedelta(hours=24)

        for event in user_events:
            # Count by type
            event_type_str = event.event_type.value
            events_by_type[event_type_str] = events_by_type.get(event_type_str, 0) + 1

            # Count by severity
            severity_str = event.severity.value
            events_by_severity[severity_str] = (
                events_by_severity.get(severity_str, 0) + 1
            )

            # Recent events
            if event.timestamp >= cutoff_time:
                recent_events.append(event)

        # Calculate risk score
        risk_score = self._calculate_user_risk_score(user_events)

        return {
            "user_id": user_id,
            "total_events": total_events,
            "events_by_type": events_by_type,
            "events_by_severity": events_by_severity,
            "recent_events_24h": len(recent_events),
            "risk_score": risk_score,
            "risk_level": self._get_risk_level(risk_score),
            "is_blocked": user_id in self.blocked_users,
            "blocked_until": self.blocked_users.get(user_id),
        }

    def get_ip_security_summary(self, ip_address: str) -> Dict[str, Any]:
        """
        Get security summary for a specific IP address.

        Args:
            ip_address: IP address to analyze

        Returns:
            Security summary dictionary
        """
        ip_events = self.ip_activity_tracking.get(ip_address, [])

        # Calculate statistics
        total_events = len(ip_events)
        events_by_type = {}
        unique_users = set()
        recent_events = []

        cutoff_time = datetime.utcnow() - timedelta(hours=24)

        for event in ip_events:
            # Count by type
            event_type_str = event.event_type.value
            events_by_type[event_type_str] = events_by_type.get(event_type_str, 0) + 1

            # Track unique users
            if event.user_id:
                unique_users.add(event.user_id)

            # Recent events
            if event.timestamp >= cutoff_time:
                recent_events.append(event)

        # Calculate risk score
        risk_score = self._calculate_ip_risk_score(ip_events)

        return {
            "ip_address": ip_address,
            "total_events": total_events,
            "events_by_type": events_by_type,
            "unique_users": len(unique_users),
            "recent_events_24h": len(recent_events),
            "risk_score": risk_score,
            "risk_level": self._get_risk_level(risk_score),
            "is_blocked": ip_address in self.blocked_ips,
            "blocked_until": self.blocked_ips.get(ip_address),
        }

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """
        Acknowledge a security alert.

        Args:
            alert_id: Alert ID to acknowledge
            acknowledged_by: Who acknowledged the alert

        Returns:
            True if successful, False if alert not found
        """
        if alert_id not in self.alerts:
            return False

        alert = self.alerts[alert_id]
        alert.acknowledged = True
        alert.acknowledged_by = acknowledged_by
        alert.acknowledged_at = datetime.utcnow()

        logger.info(
            f"Security alert acknowledged",
            extra={
                "alert_id": alert_id,
                "acknowledged_by": acknowledged_by,
                "alert_type": alert.alert_type,
            },
        )

        return True

    def block_user(self, user_id: int, duration_minutes: int, reason: str):
        """
        Temporarily block a user for security reasons.

        Args:
            user_id: User ID to block
            duration_minutes: Block duration in minutes
            reason: Reason for blocking
        """
        block_until = datetime.utcnow() + timedelta(minutes=duration_minutes)
        self.blocked_users[user_id] = block_until

        logger.warning(
            f"User blocked for security reasons",
            extra={
                "user_id": user_id,
                "duration_minutes": duration_minutes,
                "blocked_until": block_until.isoformat(),
                "reason": reason,
            },
        )

    def block_ip(self, ip_address: str, duration_minutes: int, reason: str):
        """
        Temporarily block an IP address for security reasons.

        Args:
            ip_address: IP address to block
            duration_minutes: Block duration in minutes
            reason: Reason for blocking
        """
        block_until = datetime.utcnow() + timedelta(minutes=duration_minutes)
        self.blocked_ips[ip_address] = block_until

        logger.warning(
            f"IP address blocked for security reasons",
            extra={
                "ip_address": ip_address,
                "duration_minutes": duration_minutes,
                "blocked_until": block_until.isoformat(),
                "reason": reason,
            },
        )

    def is_user_blocked(self, user_id: int) -> bool:
        """Check if a user is currently blocked."""
        if user_id not in self.blocked_users:
            return False

        block_until = self.blocked_users[user_id]
        if datetime.utcnow() >= block_until:
            # Block expired, remove it
            del self.blocked_users[user_id]
            return False

        return True

    def is_ip_blocked(self, ip_address: str) -> bool:
        """Check if an IP address is currently blocked."""
        if ip_address not in self.blocked_ips:
            return False

        block_until = self.blocked_ips[ip_address]
        if datetime.utcnow() >= block_until:
            # Block expired, remove it
            del self.blocked_ips[ip_address]
            return False

        return True

    def cleanup_old_events(self):
        """Clean up old events based on retention policy."""
        cutoff_time = datetime.utcnow() - timedelta(days=self.event_retention_days)

        # Remove old events
        old_event_ids = [
            event_id
            for event_id, event in self.events.items()
            if event.timestamp < cutoff_time
        ]

        for event_id in old_event_ids:
            del self.events[event_id]

        # Clean up tracking dictionaries
        for user_id in list(self.user_activity_tracking.keys()):
            self.user_activity_tracking[user_id] = [
                event
                for event in self.user_activity_tracking[user_id]
                if event.timestamp >= cutoff_time
            ]
            if not self.user_activity_tracking[user_id]:
                del self.user_activity_tracking[user_id]

        for ip_address in list(self.ip_activity_tracking.keys()):
            self.ip_activity_tracking[ip_address] = [
                event
                for event in self.ip_activity_tracking[ip_address]
                if event.timestamp >= cutoff_time
            ]
            if not self.ip_activity_tracking[ip_address]:
                del self.ip_activity_tracking[ip_address]

        logger.info(f"Cleaned up {len(old_event_ids)} old security events")

    def _generate_event_id(self) -> str:
        """Generate a unique event ID."""
        import uuid

        return f"SEC_{int(time.time())}_{str(uuid.uuid4())[:8]}"

    def _generate_alert_id(self) -> str:
        """Generate a unique alert ID."""
        import uuid

        return f"ALERT_{int(time.time())}_{str(uuid.uuid4())[:8]}"

    def _log_to_structured_logger(self, event: SecurityEvent):
        """Log event to structured logger."""
        log_data = {
            "event_id": event.event_id,
            "event_type": event.event_type.value,
            "severity": event.severity.value,
            "user_id": event.user_id,
            "ip_address": event.ip_address,
            "user_agent": event.user_agent,
            "description": event.description,
            "details": event.details,
            "request_context": event.request_context,
            "tags": list(event.tags),
        }

        # Choose log level based on severity
        if event.severity == SecuritySeverity.CRITICAL:
            logger.critical(f"Security event: {event.description}", extra=log_data)
        elif event.severity == SecuritySeverity.HIGH:
            logger.error(f"Security event: {event.description}", extra=log_data)
        elif event.severity == SecuritySeverity.MEDIUM:
            logger.warning(f"Security event: {event.description}", extra=log_data)
        else:
            logger.info(f"Security event: {event.description}", extra=log_data)

    def _check_for_patterns(self, event: SecurityEvent):
        """Check for suspicious patterns and create alerts if needed."""
        pattern_key = f"{event.event_type.value}:{event.user_id}:{event.ip_address}"

        if pattern_key not in self.event_patterns:
            self.event_patterns[pattern_key] = []

        self.event_patterns[pattern_key].append(event.timestamp)

        # Keep only recent events
        cutoff_time = datetime.utcnow() - timedelta(
            hours=self.pattern_detection_window_hours
        )
        self.event_patterns[pattern_key] = [
            timestamp
            for timestamp in self.event_patterns[pattern_key]
            if timestamp > cutoff_time
        ]

        # Check if threshold exceeded
        threshold = self.alert_thresholds.get(event.event_type, 10)
        if len(self.event_patterns[pattern_key]) >= threshold:
            self._create_pattern_alert(event, len(self.event_patterns[pattern_key]))

    def _create_pattern_alert(self, event: SecurityEvent, count: int):
        """Create an alert for detected patterns."""
        alert_type = f"pattern_{event.event_type.value}"
        description = (
            f"Suspicious pattern detected: {count} {event.event_type.value} events"
        )

        if event.user_id:
            description += f" from user {event.user_id}"
        if event.ip_address:
            description += f" from IP {event.ip_address}"

        self.create_security_alert(
            alert_type=alert_type,
            severity=SecuritySeverity.HIGH,
            description=description,
            event_ids=[event.event_id],
            affected_users={event.user_id} if event.user_id else set(),
            affected_ips={event.ip_address} if event.ip_address else set(),
        )

    def _check_automatic_response(self, event: SecurityEvent):
        """Check if automatic response is needed for the event."""
        from ..exceptions.security_exceptions import (
            BruteForceAttemptError,
            TokenManipulationError,
            SessionHijackingError,
            PrivilegeEscalationError,
        )

        # Define automatic responses based on event type
        if event.event_type in [
            SecurityEventType.BRUTE_FORCE_ATTEMPT,
            SecurityEventType.TOKEN_MANIPULATION,
            SecurityEventType.SESSION_HIJACKING,
            SecurityEventType.PRIVILEGE_ESCALATION,
        ]:
            # Block user and/or IP
            if event.user_id:
                self.block_user(
                    event.user_id,
                    60,
                    f"Automatic block due to {event.event_type.value}",
                )
            if event.ip_address:
                self.block_ip(
                    event.ip_address,
                    30,
                    f"Automatic block due to {event.event_type.value}",
                )

    def _cleanup_user_events(self, user_id: int):
        """Clean up old events for a user to prevent memory issues."""
        events = self.user_activity_tracking[user_id]
        if len(events) > self.max_events_per_user:
            # Keep only the most recent events
            events.sort(key=lambda x: x.timestamp, reverse=True)
            self.user_activity_tracking[user_id] = events[: self.max_events_per_user]

    def _cleanup_ip_events(self, ip_address: str):
        """Clean up old events for an IP to prevent memory issues."""
        events = self.ip_activity_tracking[ip_address]
        if len(events) > self.max_events_per_ip:
            # Keep only the most recent events
            events.sort(key=lambda x: x.timestamp, reverse=True)
            self.ip_activity_tracking[ip_address] = events[: self.max_events_per_ip]

    def _map_exception_to_event_type(
        self, exception: SecurityError
    ) -> SecurityEventType:
        """Map security exception to event type."""
        from ..exceptions.security_exceptions import (
            SuspiciousActivityError,
            BruteForceAttemptError,
            UnauthorizedAccessError,
            TokenManipulationError,
            DataExfiltrationAttemptError,
            InjectionAttemptError,
            SessionHijackingError,
            PrivilegeEscalationError,
            AnomalousPatternError,
            ComplianceViolationError,
        )

        mapping = {
            SuspiciousActivityError: SecurityEventType.SUSPICIOUS_ACTIVITY,
            BruteForceAttemptError: SecurityEventType.BRUTE_FORCE_ATTEMPT,
            UnauthorizedAccessError: SecurityEventType.UNAUTHORIZED_ACCESS,
            TokenManipulationError: SecurityEventType.TOKEN_MANIPULATION,
            DataExfiltrationAttemptError: SecurityEventType.DATA_EXFILTRATION,
            InjectionAttemptError: SecurityEventType.INJECTION_ATTEMPT,
            SessionHijackingError: SecurityEventType.SESSION_HIJACKING,
            PrivilegeEscalationError: SecurityEventType.PRIVILEGE_ESCALATION,
            AnomalousPatternError: SecurityEventType.ANOMALOUS_PATTERN,
            ComplianceViolationError: SecurityEventType.COMPLIANCE_VIOLATION,
        }

        return mapping.get(type(exception), SecurityEventType.SUSPICIOUS_ACTIVITY)

    def _map_severity_string_to_enum(self, severity_str: str) -> SecuritySeverity:
        """Map severity string to enum."""
        mapping = {
            "low": SecuritySeverity.LOW,
            "medium": SecuritySeverity.MEDIUM,
            "high": SecuritySeverity.HIGH,
            "critical": SecuritySeverity.CRITICAL,
        }
        return mapping.get(severity_str.lower(), SecuritySeverity.MEDIUM)

    def _calculate_user_risk_score(self, events: List[SecurityEvent]) -> int:
        """Calculate risk score for a user based on their security events."""
        if not events:
            return 0

        score = 0
        recent_cutoff = datetime.utcnow() - timedelta(hours=24)

        for event in events:
            # Base score by severity
            if event.severity == SecuritySeverity.CRITICAL:
                event_score = 10
            elif event.severity == SecuritySeverity.HIGH:
                event_score = 5
            elif event.severity == SecuritySeverity.MEDIUM:
                event_score = 2
            else:
                event_score = 1

            # Double score for recent events
            if event.timestamp >= recent_cutoff:
                event_score *= 2

            score += event_score

        return min(score, 100)  # Cap at 100

    def _calculate_ip_risk_score(self, events: List[SecurityEvent]) -> int:
        """Calculate risk score for an IP based on security events."""
        if not events:
            return 0

        score = 0
        recent_cutoff = datetime.utcnow() - timedelta(hours=24)
        unique_users = set()

        for event in events:
            # Base score by severity
            if event.severity == SecuritySeverity.CRITICAL:
                event_score = 8
            elif event.severity == SecuritySeverity.HIGH:
                event_score = 4
            elif event.severity == SecuritySeverity.MEDIUM:
                event_score = 2
            else:
                event_score = 1

            # Double score for recent events
            if event.timestamp >= recent_cutoff:
                event_score *= 2

            # Track unique users
            if event.user_id:
                unique_users.add(event.user_id)

            score += event_score

        # Bonus score for multiple users from same IP (potential compromise)
        if len(unique_users) > 3:
            score += len(unique_users) * 2

        return min(score, 100)  # Cap at 100

    def _get_risk_level(self, risk_score: int) -> str:
        """Convert risk score to risk level."""
        if risk_score >= 80:
            return "critical"
        elif risk_score >= 60:
            return "high"
        elif risk_score >= 30:
            return "medium"
        elif risk_score >= 10:
            return "low"
        else:
            return "minimal"


# Global instance
security_logging_service = SecurityLoggingService()
