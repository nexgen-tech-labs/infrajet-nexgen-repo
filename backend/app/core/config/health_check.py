"""
Configuration Health Check Module.

This module provides utilities for checking the health and validity of all
application configurations, including Azure, and feature flags.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from ..settings import get_settings
from .azure_validator import validate_azure_configuration, quick_validate_azure_config


class HealthStatus(str, Enum):
    """Health check status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    UNHEALTHY = "unhealthy"
    DISABLED = "disabled"


@dataclass
class ComponentHealth:
    """Health status of a configuration component."""
    name: str
    status: HealthStatus
    message: str
    details: Optional[Dict[str, Any]] = None
    errors: Optional[List[str]] = None
    warnings: Optional[List[str]] = None


class ConfigurationHealthChecker:
    """Comprehensive configuration health checker."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the health checker with optional logger."""
        self.logger = logger or logging.getLogger(__name__)

    def check_all_configurations(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check of all configurations.

        Returns:
            Dictionary containing health status of all components
        """
        settings = get_settings()
        
        health_report = {
            "overall_status": HealthStatus.HEALTHY,
            "timestamp": None,
            "components": {},
            "summary": {
                "healthy": 0,
                "warnings": 0,
                "unhealthy": 0,
                "disabled": 0
            },
            "recommendations": []
        }

        # Check Azure configuration
        azure_health = self._check_azure_health()
        health_report["components"]["azure"] = azure_health

        # Check feature flags
        feature_flags_health = self._check_feature_flags_health(settings)
        health_report["components"]["feature_flags"] = feature_flags_health

        # Check database configuration
        database_health = self._check_database_health(settings)
        health_report["components"]["database"] = database_health

        # Calculate overall status and summary
        self._calculate_overall_status(health_report)
        self._generate_recommendations(health_report, settings)

        # Add timestamp
        from datetime import datetime
        health_report["timestamp"] = datetime.utcnow().isoformat()

        # Log health check results
        self._log_health_results(health_report)

        return health_report

    def _check_azure_health(self) -> ComponentHealth:
        """Check Azure File Share configuration health."""
        
        try:
            from ..azure_config import get_azure_config
            azure_config = get_azure_config()
            
            if not azure_config.is_enabled():
                return ComponentHealth(
                    name="azure",
                    status=HealthStatus.DISABLED,
                    message="Azure File Share integration is disabled"
                )

            # Use the validator for detailed checking
            report = validate_azure_configuration(azure_config)
            
            if report.is_valid:
                if len(report.warnings) > 0:
                    return ComponentHealth(
                        name="azure",
                        status=HealthStatus.WARNING,
                        message=f"Azure configuration valid with {len(report.warnings)} warnings",
                        warnings=[w.message for w in report.warnings],
                        details=report.config_summary
                    )
                else:
                    return ComponentHealth(
                        name="azure",
                        status=HealthStatus.HEALTHY,
                        message="Azure File Share configuration is healthy",
                        details=report.config_summary
                    )
            else:
                return ComponentHealth(
                    name="azure",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Azure configuration invalid with {len(report.errors)} errors",
                    errors=[e.message for e in report.errors],
                    warnings=[w.message for w in report.warnings] if report.warnings else None,
                    details=report.config_summary
                )

        except Exception as e:
            return ComponentHealth(
                name="azure",
                status=HealthStatus.UNHEALTHY,
                message=f"Failed to validate Azure configuration: {str(e)}",
                errors=[str(e)]
            )

    def _check_feature_flags_health(self, settings) -> ComponentHealth:
        """Check feature flags configuration health."""
        
        try:
            feature_flags = settings.get_feature_flags()
            warnings = []
            
            # Check for conflicting authentication methods
            if settings.ENTRA_AUTH_ENABLED:
                warnings.append("Entra ID authentication is enabled")
            
            # Check if no authentication is enabled
            if not settings.ENTRA_AUTH_ENABLED:
                warnings.append("No authentication method is enabled")
            
            # Check GitHub integration status
            if settings.GITHUB_INTEGRATION_ENABLED:
                warnings.append("GitHub integration is enabled (may be disabled in current version)")

            status = HealthStatus.HEALTHY
            message = "Feature flags configuration is healthy"
            
            if warnings:
                status = HealthStatus.WARNING
                message = f"Feature flags have {len(warnings)} warnings"

            return ComponentHealth(
                name="feature_flags",
                status=status,
                message=message,
                warnings=warnings if warnings else None,
                details=feature_flags
            )

        except Exception as e:
            return ComponentHealth(
                name="feature_flags",
                status=HealthStatus.UNHEALTHY,
                message=f"Failed to validate feature flags: {str(e)}",
                errors=[str(e)]
            )

    def _check_database_health(self, settings) -> ComponentHealth:
        """Check database configuration health."""
        
        try:
            if not settings.DATABASE_URL:
                return ComponentHealth(
                    name="database",
                    status=HealthStatus.UNHEALTHY,
                    message="Database URL is not configured",
                    errors=["DATABASE_URL is required"]
                )

            # Basic URL validation
            if not settings.DATABASE_URL.startswith("postgresql"):
                return ComponentHealth(
                    name="database",
                    status=HealthStatus.WARNING,
                    message="Database URL does not appear to be PostgreSQL",
                    warnings=["Expected PostgreSQL database URL"]
                )

            return ComponentHealth(
                name="database",
                status=HealthStatus.HEALTHY,
                message="Database configuration appears healthy",
                details={"url_configured": True}
            )

        except Exception as e:
            return ComponentHealth(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message=f"Failed to validate database configuration: {str(e)}",
                errors=[str(e)]
            )

    def _calculate_overall_status(self, health_report: Dict[str, Any]) -> None:
        """Calculate overall health status and summary."""
        
        components = health_report["components"]
        summary = health_report["summary"]
        
        # Count component statuses
        for component in components.values():
            status = component.status
            if status == HealthStatus.HEALTHY:
                summary["healthy"] += 1
            elif status == HealthStatus.WARNING:
                summary["warnings"] += 1
            elif status == HealthStatus.UNHEALTHY:
                summary["unhealthy"] += 1
            elif status == HealthStatus.DISABLED:
                summary["disabled"] += 1

        # Determine overall status
        if summary["unhealthy"] > 0:
            health_report["overall_status"] = HealthStatus.UNHEALTHY
        elif summary["warnings"] > 0:
            health_report["overall_status"] = HealthStatus.WARNING
        else:
            health_report["overall_status"] = HealthStatus.HEALTHY

    def _generate_recommendations(self, health_report: Dict[str, Any], settings) -> None:
        """Generate recommendations based on health check results."""
        
        recommendations = []
        components = health_report["components"]

        # Azure recommendations
        azure = components.get("azure")
        if azure and azure.status == HealthStatus.UNHEALTHY:
            recommendations.append("Fix Azure File Share configuration to enable file storage")
        elif azure and azure.status == HealthStatus.DISABLED:
            recommendations.append("Enable Azure File Share by setting AZURE_ENABLED=true")

        # Feature flags recommendations
        if not settings.ENTRA_AUTH_ENABLED:
            recommendations.append("Enable at least one authentication method")

        # Database recommendations
        database = components.get("database")
        if database and database.status == HealthStatus.UNHEALTHY:
            recommendations.append("Configure DATABASE_URL to enable database connectivity")

        health_report["recommendations"] = recommendations

    def _log_health_results(self, health_report: Dict[str, Any]) -> None:
        """Log health check results."""
        
        if not self.logger:
            return

        overall_status = health_report["overall_status"]
        summary = health_report["summary"]

        if overall_status == HealthStatus.HEALTHY:
            self.logger.info(
                f"Configuration health check passed: {summary['healthy']} healthy, "
                f"{summary['warnings']} warnings, {summary['disabled']} disabled"
            )
        elif overall_status == HealthStatus.WARNING:
            self.logger.warning(
                f"Configuration health check has warnings: {summary['warnings']} warnings, "
                f"{summary['unhealthy']} unhealthy components"
            )
        else:
            self.logger.error(
                f"Configuration health check failed: {summary['unhealthy']} unhealthy components"
            )

        # Log component-specific issues
        for name, component in health_report["components"].items():
            if component.status == HealthStatus.UNHEALTHY:
                self.logger.error(f"{name.title()} configuration is unhealthy: {component.message}")
            elif component.status == HealthStatus.WARNING:
                self.logger.warning(f"{name.title()} configuration has warnings: {component.message}")

        # Log recommendations
        if health_report["recommendations"]:
            self.logger.info("Configuration recommendations:")
            for rec in health_report["recommendations"]:
                self.logger.info(f"  - {rec}")


# Convenience functions
def check_configuration_health() -> Dict[str, Any]:
    """Perform a comprehensive configuration health check."""
    checker = ConfigurationHealthChecker()
    return checker.check_all_configurations()


def quick_health_check() -> Tuple[bool, str]:
    """
    Perform a quick health check of critical configurations.

    Returns:
        Tuple of (is_healthy, summary_message)
    """
    try:
        health_report = check_configuration_health()
        
        overall_status = health_report["overall_status"]
        summary = health_report["summary"]
        
        if overall_status == HealthStatus.HEALTHY:
            return True, f"All configurations healthy ({summary['healthy']} components)"
        elif overall_status == HealthStatus.WARNING:
            return True, f"Configurations have warnings ({summary['warnings']} warnings)"
        else:
            return False, f"Configuration issues detected ({summary['unhealthy']} unhealthy)"

    except Exception as e:
        return False, f"Health check failed: {str(e)}"


def validate_startup_configuration() -> Tuple[bool, List[str]]:
    """
    Validate configuration required for application startup.

    Returns:
        Tuple of (can_start, critical_errors)
    """
    critical_errors = []
    
    try:
        settings = get_settings()
        
        # Check database configuration
        if not settings.DATABASE_URL:
            critical_errors.append("DATABASE_URL is required for application startup")
        
        # Check if no authentication is enabled
        if not settings.ENTRA_AUTH_ENABLED:
            critical_errors.append("At least one authentication method must be enabled")

        return len(critical_errors) == 0, critical_errors

    except Exception as e:
        critical_errors.append(f"Failed to validate startup configuration: {str(e)}")
        return False, critical_errors