"""
Security specific exception hierarchy.

This module defines comprehensive exception classes for security-related
operations, providing specific error types for suspicious activities,
security violations, and audit logging.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from .base_exceptions import BaseApplicationError


class SecurityError(BaseApplicationError):
    """
    Base exception for security-related operations.

    All security related exceptions inherit from this base class.
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
        user_message: Optional[str] = None,
        troubleshooting_guide: Optional[str] = None,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        requires_audit: bool = True,
        security_level: str = "medium",
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            original_exception=original_exception,
            user_message=user_message,
            troubleshooting_guide=troubleshooting_guide,
            severity=security_level,
        )
        self.user_id = user_id
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.requires_audit = requires_audit
        self.security_level = security_level

        # Add security context to details
        self.details.update(
            {
                "user_id": user_id,
                "ip_address": ip_address,
                "user_agent": (
                    user_agent[:200] if user_agent else None
                ),  # Truncate long user agents
                "requires_audit": requires_audit,
                "security_level": security_level,
            }
        )


class SuspiciousActivityError(SecurityError):
    """
    Exception raised when suspicious activity is detected.
    """

    def __init__(
        self,
        message: str = "Suspicious activity detected",
        activity_type: Optional[str] = None,
        risk_score: Optional[int] = None,
        indicators: Optional[List[str]] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="SUSPICIOUS_ACTIVITY_DETECTED",
            user_message="Unusual activity detected. Your account may be temporarily restricted.",
            troubleshooting_guide="If this was legitimate activity, contact support to review your account.",
            security_level="high",
            **kwargs,
        )
        self.activity_type = activity_type
        self.risk_score = risk_score
        self.indicators = indicators or []
        self.details.update(
            {
                "activity_type": activity_type,
                "risk_score": risk_score,
                "indicators": indicators,
            }
        )


class BruteForceAttemptError(SecurityError):
    """
    Exception raised when brute force attack is detected.
    """

    def __init__(
        self,
        message: str = "Brute force attack detected",
        attempt_count: Optional[int] = None,
        time_window: Optional[int] = None,
        target_endpoint: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="BRUTE_FORCE_DETECTED",
            user_message="Too many failed attempts. Your access has been temporarily restricted.",
            troubleshooting_guide="Wait before trying again. If you're having trouble, contact support.",
            security_level="critical",
            **kwargs,
        )
        self.attempt_count = attempt_count
        self.time_window = time_window
        self.target_endpoint = target_endpoint
        self.details.update(
            {
                "attempt_count": attempt_count,
                "time_window": time_window,
                "target_endpoint": target_endpoint,
            }
        )


class UnauthorizedAccessError(SecurityError):
    """
    Exception raised when unauthorized access is attempted.
    """

    def __init__(
        self,
        message: str = "Unauthorized access attempt",
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        attempted_action: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="UNAUTHORIZED_ACCESS_ATTEMPT",
            user_message="You don't have permission to access this resource.",
            troubleshooting_guide="Contact your administrator if you believe you should have access.",
            security_level="high",
            **kwargs,
        )
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.attempted_action = attempted_action
        self.details.update(
            {
                "resource_type": resource_type,
                "resource_id": resource_id,
                "attempted_action": attempted_action,
            }
        )


class TokenManipulationError(SecurityError):
    """
    Exception raised when token manipulation is detected.
    """

    def __init__(
        self,
        message: str = "Token manipulation detected",
        token_type: Optional[str] = None,
        manipulation_type: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="TOKEN_MANIPULATION_DETECTED",
            user_message="Invalid authentication token. Please sign in again.",
            troubleshooting_guide="Sign out and sign back in. If problems persist, contact support.",
            security_level="critical",
            **kwargs,
        )
        self.token_type = token_type
        self.manipulation_type = manipulation_type
        self.details.update(
            {
                "token_type": token_type,
                "manipulation_type": manipulation_type,
            }
        )


class DataExfiltrationAttemptError(SecurityError):
    """
    Exception raised when data exfiltration attempt is detected.
    """

    def __init__(
        self,
        message: str = "Data exfiltration attempt detected",
        data_type: Optional[str] = None,
        volume_attempted: Optional[int] = None,
        extraction_method: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="DATA_EXFILTRATION_ATTEMPT",
            user_message="Unusual data access pattern detected. Access has been restricted.",
            troubleshooting_guide="Contact support if this was legitimate activity.",
            security_level="critical",
            **kwargs,
        )
        self.data_type = data_type
        self.volume_attempted = volume_attempted
        self.extraction_method = extraction_method
        self.details.update(
            {
                "data_type": data_type,
                "volume_attempted": volume_attempted,
                "extraction_method": extraction_method,
            }
        )


class InjectionAttemptError(SecurityError):
    """
    Exception raised when injection attack is detected.
    """

    def __init__(
        self,
        message: str = "Injection attack detected",
        injection_type: Optional[str] = None,
        payload: Optional[str] = None,
        target_field: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="INJECTION_ATTACK_DETECTED",
            user_message="Invalid input detected. Request has been blocked.",
            troubleshooting_guide="Ensure your input doesn't contain special characters or scripts.",
            security_level="high",
            **kwargs,
        )
        self.injection_type = injection_type
        # Sanitize payload for logging (remove actual malicious content)
        self.payload = payload[:100] if payload else None
        self.target_field = target_field
        self.details.update(
            {
                "injection_type": injection_type,
                "payload_length": len(payload) if payload else 0,
                "target_field": target_field,
            }
        )


class SessionHijackingError(SecurityError):
    """
    Exception raised when session hijacking is detected.
    """

    def __init__(
        self,
        message: str = "Session hijacking detected",
        session_id: Optional[str] = None,
        original_ip: Optional[str] = None,
        new_ip: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="SESSION_HIJACKING_DETECTED",
            user_message="Session security violation detected. Please sign in again.",
            troubleshooting_guide="Sign out and sign back in from a secure location.",
            security_level="critical",
            **kwargs,
        )
        # Don't store full session ID for security
        self.session_id_hash = hash(session_id) if session_id else None
        self.original_ip = original_ip
        self.new_ip = new_ip
        self.details.update(
            {
                "session_id_hash": self.session_id_hash,
                "original_ip": original_ip,
                "new_ip": new_ip,
            }
        )


class PrivilegeEscalationError(SecurityError):
    """
    Exception raised when privilege escalation is attempted.
    """

    def __init__(
        self,
        message: str = "Privilege escalation attempt detected",
        current_role: Optional[str] = None,
        attempted_role: Optional[str] = None,
        escalation_method: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="PRIVILEGE_ESCALATION_ATTEMPT",
            user_message="Unauthorized privilege escalation attempt. Access denied.",
            troubleshooting_guide="Contact your administrator if you need additional permissions.",
            security_level="critical",
            **kwargs,
        )
        self.current_role = current_role
        self.attempted_role = attempted_role
        self.escalation_method = escalation_method
        self.details.update(
            {
                "current_role": current_role,
                "attempted_role": attempted_role,
                "escalation_method": escalation_method,
            }
        )


class AnomalousPatternError(SecurityError):
    """
    Exception raised when anomalous usage patterns are detected.
    """

    def __init__(
        self,
        message: str = "Anomalous usage pattern detected",
        pattern_type: Optional[str] = None,
        deviation_score: Optional[float] = None,
        baseline_behavior: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="ANOMALOUS_PATTERN_DETECTED",
            user_message="Unusual usage pattern detected. Some features may be temporarily restricted.",
            troubleshooting_guide="If this is normal behavior for you, contact support to adjust your profile.",
            security_level="medium",
            **kwargs,
        )
        self.pattern_type = pattern_type
        self.deviation_score = deviation_score
        self.baseline_behavior = baseline_behavior or {}
        self.details.update(
            {
                "pattern_type": pattern_type,
                "deviation_score": deviation_score,
                "baseline_behavior": baseline_behavior,
            }
        )


class ComplianceViolationError(SecurityError):
    """
    Exception raised when compliance violation is detected.
    """

    def __init__(
        self,
        message: str = "Compliance violation detected",
        violation_type: Optional[str] = None,
        regulation: Optional[str] = None,
        severity_level: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code="COMPLIANCE_VIOLATION",
            user_message="Action violates compliance requirements and has been blocked.",
            troubleshooting_guide="Contact your compliance officer for guidance on permitted actions.",
            security_level="high",
            **kwargs,
        )
        self.violation_type = violation_type
        self.regulation = regulation
        self.severity_level = severity_level
        self.details.update(
            {
                "violation_type": violation_type,
                "regulation": regulation,
                "severity_level": severity_level,
            }
        )


def create_security_audit_log(
    exception: SecurityError,
    request_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a comprehensive audit log entry for security exceptions.

    Args:
        exception: Security exception to log
        request_context: Optional request context information

    Returns:
        Audit log entry dictionary
    """
    audit_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": "security_violation",
        "error_code": exception.error_code,
        "security_level": exception.security_level,
        "message": exception.message,
        "user_id": exception.user_id,
        "ip_address": exception.ip_address,
        "user_agent": exception.user_agent,
        "details": exception.details,
        "requires_investigation": exception.security_level in ["high", "critical"],
        "auto_response_triggered": True,
    }

    # Add request context if available
    if request_context:
        audit_entry["request_context"] = {
            "method": request_context.get("method"),
            "path": request_context.get("path"),
            "headers": {
                k: v
                for k, v in request_context.get("headers", {}).items()
                if k.lower() not in ["authorization", "cookie", "x-api-key"]
            },
            "query_params": request_context.get("query_params"),
        }

    return audit_entry


def determine_security_response(exception: SecurityError) -> Dict[str, Any]:
    """
    Determine appropriate security response based on exception type and severity.

    Args:
        exception: Security exception to evaluate

    Returns:
        Dictionary containing recommended security responses
    """
    response = {
        "block_request": True,
        "log_incident": True,
        "notify_admin": False,
        "temporary_ban": False,
        "require_reauth": False,
        "escalate_to_soc": False,
        "ban_duration_minutes": 0,
    }

    # Critical security violations
    if isinstance(
        exception,
        (
            BruteForceAttemptError,
            TokenManipulationError,
            SessionHijackingError,
            PrivilegeEscalationError,
            DataExfiltrationAttemptError,
        ),
    ):
        response.update(
            {
                "notify_admin": True,
                "temporary_ban": True,
                "require_reauth": True,
                "escalate_to_soc": True,
                "ban_duration_minutes": 60,  # 1 hour
            }
        )

    # High security violations
    elif isinstance(
        exception,
        (
            SuspiciousActivityError,
            UnauthorizedAccessError,
            InjectionAttemptError,
            ComplianceViolationError,
        ),
    ):
        response.update(
            {
                "notify_admin": True,
                "require_reauth": True,
                "ban_duration_minutes": 15,  # 15 minutes
            }
        )

    # Medium security violations
    elif isinstance(exception, AnomalousPatternError):
        response.update(
            {
                "temporary_ban": False,
                "ban_duration_minutes": 0,
            }
        )

    return response


def is_security_exception_retryable(exception: SecurityError) -> bool:
    """
    Determine if a security exception allows for retry.

    Args:
        exception: Security exception to check

    Returns:
        True if retry is allowed, False otherwise
    """
    # Most security exceptions should not be retryable to prevent abuse
    non_retryable_types = (
        BruteForceAttemptError,
        TokenManipulationError,
        SessionHijackingError,
        PrivilegeEscalationError,
        DataExfiltrationAttemptError,
        InjectionAttemptError,
    )

    return not isinstance(exception, non_retryable_types)


def get_security_error_context(
    request: Optional[Any] = None,
    user: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Extract security-relevant context from request and user objects.

    Args:
        request: Optional request object
        user: Optional user object

    Returns:
        Dictionary containing security context
    """
    context = {}

    if request:
        context.update(
            {
                "ip_address": getattr(request, "client", {}).get("host"),
                "user_agent": getattr(request, "headers", {}).get("user-agent"),
                "method": getattr(request, "method", None),
                "path": (
                    str(getattr(request, "url", {}).path)
                    if hasattr(request, "url")
                    else None
                ),
            }
        )

    if user:
        context.update(
            {
                "user_id": getattr(user, "id", None),
                "user_email": getattr(user, "email", None),
                "user_role": getattr(user, "role", None),
            }
        )

    return context
