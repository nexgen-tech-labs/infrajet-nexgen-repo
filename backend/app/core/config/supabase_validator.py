"""
Supabase Configuration Validator Module.

This module provides comprehensive validation, testing, and environment loading
utilities for Supabase authentication configuration. It ensures configuration integrity
and provides detailed validation feedback.
"""

import os
import re
import json
import base64
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from pydantic import BaseModel, Field
import logging
from urllib.parse import urlparse

from .azure_validator import ValidationLevel, ValidationResult, ConfigValidationReport


class SupabaseConfigValidator:
    """Comprehensive Supabase configuration validator."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the validator with optional logger."""
        self.logger = logger or logging.getLogger(__name__)

    def validate_supabase_config(self, settings) -> ConfigValidationReport:
        """
        Perform comprehensive validation of Supabase configuration.

        Args:
            settings: Settings object containing Supabase configuration

        Returns:
            Detailed validation report
        """
        report = ConfigValidationReport(is_valid=True)

        # Validate feature flags
        self._validate_feature_flags(settings, report)

        # Only validate Supabase config if enabled
        if settings.SUPABASE_AUTH_ENABLED:
            # Validate connection settings
            self._validate_connection_settings(settings, report)

            # Validate JWT configuration
            self._validate_jwt_configuration(settings, report)

            # Validate frontend/backend consistency
            self._validate_frontend_backend_consistency(settings, report)

        # Generate configuration summary
        self._generate_config_summary(settings, report)

        # Log validation results
        self._log_validation_results(report)

        return report

    def _validate_feature_flags(self, settings, report: ConfigValidationReport) -> None:
        """Validate feature flag settings."""

        if not settings.SUPABASE_AUTH_ENABLED:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.INFO,
                    field="supabase_enabled",
                    message="Supabase authentication is disabled",
                    suggestion="Enable SUPABASE_AUTH_ENABLED to use Supabase authentication",
                )
            )
            return

        # Check for conflicting authentication methods
        if settings.ENTRA_AUTH_ENABLED:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.WARNING,
                    field="conflicting_auth",
                    message="Both Supabase and Entra ID authentication are enabled",
                    suggestion="Disable one authentication method to avoid conflicts",
                )
            )

        if settings.GITHUB_INTEGRATION_ENABLED:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.INFO,
                    field="github_integration",
                    message="GitHub integration is enabled alongside Supabase",
                    suggestion="Consider if both integrations are needed",
                )
            )

    def _validate_connection_settings(
        self, settings, report: ConfigValidationReport
    ) -> None:
        """Validate Supabase connection settings."""

        # Validate Supabase URL
        if not settings.SUPABASE_URL:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.ERROR,
                    field="supabase_url",
                    message="SUPABASE_URL is required when Supabase authentication is enabled",
                    suggestion="Set SUPABASE_URL to your Supabase project URL",
                )
            )
        else:
            self._validate_supabase_url_format(settings.SUPABASE_URL, report)

        # Validate anonymous key
        if not settings.SUPABASE_ANON_KEY:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.ERROR,
                    field="supabase_anon_key",
                    message="SUPABASE_ANON_KEY is required when Supabase authentication is enabled",
                    suggestion="Set SUPABASE_ANON_KEY to your Supabase anonymous/public key",
                )
            )
        else:
            self._validate_jwt_token_format(
                settings.SUPABASE_ANON_KEY, "supabase_anon_key", report, settings
            )

        # Validate service role key
        if not settings.SUPABASE_SERVICE_ROLE_KEY:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.ERROR,
                    field="supabase_service_role_key",
                    message="SUPABASE_SERVICE_ROLE_KEY is required for full table access",
                    suggestion="Set SUPABASE_SERVICE_ROLE_KEY to your Supabase service role key",
                )
            )
        else:
            self._validate_jwt_token_format(
                settings.SUPABASE_SERVICE_ROLE_KEY,
                "supabase_service_role_key",
                report,
                settings,
            )

    def _validate_supabase_url_format(
        self, url: str, report: ConfigValidationReport
    ) -> None:
        """Validate Supabase URL format."""

        if not url.startswith("https://"):
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.ERROR,
                    field="supabase_url_protocol",
                    message="Supabase URL must use HTTPS protocol",
                    value=url,
                    suggestion="Ensure URL starts with https://",
                )
            )

        if not url.endswith(".supabase.co"):
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.ERROR,
                    field="supabase_url_domain",
                    message="Supabase URL must end with .supabase.co",
                    value=url,
                    suggestion="Use the official Supabase project URL",
                )
            )

        # Extract project ID from URL
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname
            if hostname:
                project_id = hostname.split(".")[0]
                if len(project_id) < 10:
                    report.add_result(
                        ValidationResult(
                            level=ValidationLevel.WARNING,
                            field="supabase_project_id",
                            message="Supabase project ID appears to be too short",
                            value=project_id,
                            suggestion="Verify the project URL is correct",
                        )
                    )
        except Exception as e:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.WARNING,
                    field="supabase_url_parsing",
                    message=f"Could not parse Supabase URL: {str(e)}",
                    value=url,
                )
            )

    def _validate_jwt_token_format(
        self, token: str, field_name: str, report: ConfigValidationReport, settings=None
    ) -> None:
        """Validate JWT token format."""

        if not token.startswith("eyJ"):
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.ERROR,
                    field=field_name,
                    message="Token must be a valid JWT (should start with 'eyJ')",
                    suggestion="Verify the token is copied correctly from Supabase dashboard",
                )
            )
            return

        # Check JWT structure (3 parts separated by dots)
        parts = token.split(".")
        if len(parts) != 3:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.ERROR,
                    field=f"{field_name}_structure",
                    message="JWT token must have exactly 3 parts separated by dots",
                    suggestion="Verify the complete token is copied",
                )
            )
            return

        # Try to decode the header to validate it's a proper JWT
        try:
            header_data = base64.urlsafe_b64decode(parts[0] + "==")
            header = json.loads(header_data)

            if "alg" not in header:
                report.add_result(
                    ValidationResult(
                        level=ValidationLevel.WARNING,
                        field=f"{field_name}_header",
                        message="JWT header missing algorithm specification",
                    )
                )

            if "typ" not in header or header["typ"] != "JWT":
                report.add_result(
                    ValidationResult(
                        level=ValidationLevel.WARNING,
                        field=f"{field_name}_type",
                        message="JWT header missing or incorrect type specification",
                    )
                )

        except Exception as e:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.WARNING,
                    field=f"{field_name}_decode",
                    message=f"Could not decode JWT header: {str(e)}",
                    suggestion="Verify the token format is correct",
                )
            )

        # Try to decode the payload for additional validation
        try:
            payload_data = base64.urlsafe_b64decode(parts[1] + "==")
            payload = json.loads(payload_data)

            # Check for required Supabase claims
            if "iss" not in payload:
                report.add_result(
                    ValidationResult(
                        level=ValidationLevel.WARNING,
                        field=f"{field_name}_issuer",
                        message="JWT missing issuer claim",
                    )
                )
            else:
                issuer = payload["iss"]
                # Accept both "supabase" (for anon keys) and the full auth URL (for user tokens)
                valid_issuers = ["supabase"]
                if (
                    settings
                    and hasattr(settings, "SUPABASE_URL")
                    and settings.SUPABASE_URL
                ):
                    valid_issuers.append(f"{settings.SUPABASE_URL}/auth/v1")

                if issuer not in valid_issuers:
                    report.add_result(
                        ValidationResult(
                            level=ValidationLevel.WARNING,
                            field=f"{field_name}_issuer_value",
                            message=f"JWT issuer '{issuer}' is not a valid Supabase issuer",
                            value=issuer,
                            suggestion=f"Expected one of: {valid_issuers}",
                        )
                    )

            if "role" not in payload:
                report.add_result(
                    ValidationResult(
                        level=ValidationLevel.WARNING,
                        field=f"{field_name}_role",
                        message="JWT missing role claim",
                    )
                )

        except Exception as e:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.WARNING,
                    field=f"{field_name}_payload",
                    message=f"Could not decode JWT payload: {str(e)}",
                    suggestion="Token may be malformed or encrypted",
                )
            )

    def _validate_jwt_configuration(
        self, settings, report: ConfigValidationReport
    ) -> None:
        """Validate JWT configuration settings."""

        if not settings.SUPABASE_JWT_SECRET:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.ERROR,
                    field="supabase_jwt_secret",
                    message="SUPABASE_JWT_SECRET is required for JWT validation",
                    suggestion="Set SUPABASE_JWT_SECRET from your Supabase project settings",
                )
            )
        else:
            # Basic validation of JWT secret
            if len(settings.SUPABASE_JWT_SECRET) < 32:
                report.add_result(
                    ValidationResult(
                        level=ValidationLevel.WARNING,
                        field="supabase_jwt_secret_length",
                        message="JWT secret appears to be too short for security",
                        suggestion="Ensure you're using the correct JWT secret from Supabase",
                    )
                )

        # Validate service role key format if present
        if (
            hasattr(settings, "SUPABASE_SERVICE_ROLE_KEY")
            and settings.SUPABASE_SERVICE_ROLE_KEY
        ):
            # Service role key should be longer and more secure
            if len(settings.SUPABASE_SERVICE_ROLE_KEY) < 64:
                report.add_result(
                    ValidationResult(
                        level=ValidationLevel.WARNING,
                        field="supabase_service_role_key_length",
                        message="Service role key appears to be too short",
                        suggestion="Ensure you're using the correct service role key from Supabase",
                    )
                )

    def _validate_frontend_backend_consistency(
        self, settings, report: ConfigValidationReport
    ) -> None:
        """Validate consistency between frontend and backend Supabase configuration."""

        # Check URL consistency
        if settings.VITE_SUPABASE_URL and settings.SUPABASE_URL:
            if settings.VITE_SUPABASE_URL != settings.SUPABASE_URL:
                report.add_result(
                    ValidationResult(
                        level=ValidationLevel.ERROR,
                        field="url_consistency",
                        message="Frontend and backend Supabase URLs must match",
                        value=f"Frontend: {settings.VITE_SUPABASE_URL}, Backend: {settings.SUPABASE_URL}",
                        suggestion="Ensure both VITE_SUPABASE_URL and SUPABASE_URL point to the same project",
                    )
                )

        # Check key consistency
        if settings.VITE_SUPABASE_PUBLISHABLE_KEY and settings.SUPABASE_ANON_KEY:
            if settings.VITE_SUPABASE_PUBLISHABLE_KEY != settings.SUPABASE_ANON_KEY:
                report.add_result(
                    ValidationResult(
                        level=ValidationLevel.ERROR,
                        field="key_consistency",
                        message="Frontend and backend Supabase keys must match",
                        suggestion="Ensure both VITE_SUPABASE_PUBLISHABLE_KEY and SUPABASE_ANON_KEY use the same anonymous key",
                    )
                )

        # Check if frontend config is missing
        if not settings.VITE_SUPABASE_URL:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.WARNING,
                    field="frontend_url_missing",
                    message="Frontend Supabase URL (VITE_SUPABASE_URL) is not set",
                    suggestion="Set VITE_SUPABASE_URL for frontend integration",
                )
            )

        if not settings.VITE_SUPABASE_PUBLISHABLE_KEY:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.WARNING,
                    field="frontend_key_missing",
                    message="Frontend Supabase key (VITE_SUPABASE_PUBLISHABLE_KEY) is not set",
                    suggestion="Set VITE_SUPABASE_PUBLISHABLE_KEY for frontend integration",
                )
            )

    def _generate_config_summary(
        self, settings, report: ConfigValidationReport
    ) -> None:
        """Generate configuration summary."""

        try:
            summary = {
                "supabase_auth_enabled": settings.SUPABASE_AUTH_ENABLED,
                "entra_auth_enabled": settings.ENTRA_AUTH_ENABLED,
                "github_integration_enabled": settings.GITHUB_INTEGRATION_ENABLED,
                "has_supabase_url": bool(settings.SUPABASE_URL),
                "has_supabase_anon_key": bool(settings.SUPABASE_ANON_KEY),
                "has_supabase_jwt_secret": bool(settings.SUPABASE_JWT_SECRET),
                "has_supabase_service_role_key": bool(
                    getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", None)
                ),
                "has_frontend_url": bool(settings.VITE_SUPABASE_URL),
                "has_frontend_key": bool(settings.VITE_SUPABASE_PUBLISHABLE_KEY),
                "has_frontend_project_id": bool(settings.VITE_SUPABASE_PROJECT_ID),
            }

            # Add URL information if available
            if settings.SUPABASE_URL:
                try:
                    parsed = urlparse(settings.SUPABASE_URL)
                    hostname = parsed.hostname
                    if hostname:
                        project_id = hostname.split(".")[0]
                        summary["extracted_project_id"] = project_id
                except Exception:
                    pass

            # Check configuration completeness
            if settings.SUPABASE_AUTH_ENABLED:
                required_fields = [
                    "SUPABASE_URL",
                    "SUPABASE_ANON_KEY",
                    "SUPABASE_JWT_SECRET",
                    "SUPABASE_SERVICE_ROLE_KEY",
                ]
                missing_fields = [
                    field for field in required_fields if not getattr(settings, field)
                ]
                summary["missing_required_fields"] = missing_fields
                summary["configuration_complete"] = len(missing_fields) == 0
            else:
                summary["configuration_complete"] = True

            report.config_summary = summary

        except Exception as e:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.WARNING,
                    field="config_summary",
                    message=f"Could not generate complete configuration summary: {str(e)}",
                )
            )

    def _log_validation_results(self, report: ConfigValidationReport) -> None:
        """Log validation results."""

        if not self.logger:
            return

        summary = report.get_summary()

        if report.is_valid:
            self.logger.info(
                f"Supabase configuration validation passed with {summary['warnings']} warnings"
            )
        else:
            self.logger.error(
                f"Supabase configuration validation failed with {summary['errors']} errors"
            )

        # Log errors
        for error in report.errors:
            self.logger.error(
                f"Supabase config error in {error.field}: {error.message}"
            )

        # Log warnings
        for warning in report.warnings:
            self.logger.warning(
                f"Supabase config warning in {warning.field}: {warning.message}"
            )


class SupabaseEnvironmentLoader:
    """Utilities for loading and managing Supabase environment variables."""

    @staticmethod
    def get_supabase_env_vars() -> Dict[str, Optional[str]]:
        """Get all Supabase-related environment variables."""
        supabase_vars = {}

        # Backend Supabase variables
        backend_vars = [
            "SUPABASE_URL",
            "SUPABASE_ANON_KEY",
            "SUPABASE_JWT_SECRET",
            "SUPABASE_SERVICE_ROLE_KEY",
        ]

        # Frontend Supabase variables
        frontend_vars = [
            "VITE_SUPABASE_PROJECT_ID",
            "VITE_SUPABASE_PUBLISHABLE_KEY",
            "VITE_SUPABASE_URL",
        ]

        # Feature flags
        feature_vars = [
            "SUPABASE_AUTH_ENABLED",
            "ENTRA_AUTH_ENABLED",
            "GITHUB_INTEGRATION_ENABLED",
        ]

        all_vars = backend_vars + frontend_vars + feature_vars

        for var in all_vars:
            supabase_vars[var] = os.getenv(var)

        return supabase_vars

    @staticmethod
    def validate_required_env_vars() -> Tuple[bool, List[str]]:
        """
        Validate that required Supabase environment variables are set.

        Returns:
            Tuple of (all_present, missing_vars)
        """
        # Only check if Supabase auth is enabled
        if os.getenv("SUPABASE_AUTH_ENABLED", "true").lower() != "true":
            return True, []

        required_vars = [
            "SUPABASE_URL",
            "SUPABASE_ANON_KEY",
            "SUPABASE_JWT_SECRET",
            "SUPABASE_SERVICE_ROLE_KEY",
        ]
        missing_vars = []

        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)

        return len(missing_vars) == 0, missing_vars

    @staticmethod
    def create_supabase_env_template() -> str:
        """Create a template for Supabase environment variables."""
        template = """# Supabase Configuration (Frontend)
VITE_SUPABASE_PROJECT_ID=your-supabase-project-id
VITE_SUPABASE_PUBLISHABLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
VITE_SUPABASE_URL=https://your-project-id.supabase.co

# Supabase Configuration (Backend)
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_JWT_SECRET=your-jwt-secret-here
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key-here

# Feature Flags - Authentication and Integration
SUPABASE_AUTH_ENABLED=true
ENTRA_AUTH_ENABLED=false
GITHUB_INTEGRATION_ENABLED=true

# GitHub App Configuration
GITHUB_APP_ID=your-github-app-id
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret
GITHUB_PRIVATE_KEY=your-github-app-private-key
GITHUB_WEBHOOK_SECRET=your-webhook-secret
"""
        return template


# Convenience functions
def validate_supabase_configuration(settings) -> ConfigValidationReport:
    """Validate Supabase configuration and return detailed report."""
    validator = SupabaseConfigValidator()
    return validator.validate_supabase_config(settings)


def quick_validate_supabase_config(settings) -> Tuple[bool, str]:
    """
    Quick validation of Supabase configuration.

    Returns:
        Tuple of (is_valid, summary_message)
    """
    try:
        report = validate_supabase_configuration(settings)

        if report.is_valid:
            warnings = len(report.warnings)
            if warnings > 0:
                return True, f"Supabase configuration valid with {warnings} warnings"
            else:
                return True, "Supabase configuration is valid"
        else:
            errors = len(report.errors)
            return False, f"Supabase configuration invalid with {errors} errors"

    except Exception as e:
        return False, f"Supabase validation failed: {str(e)}"


def check_supabase_env_requirements() -> Tuple[bool, List[str]]:
    """Check if required Supabase environment variables are set."""
    loader = SupabaseEnvironmentLoader()
    return loader.validate_required_env_vars()
