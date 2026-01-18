"""
Azure Configuration Validator Module.

This module provides comprehensive validation, testing, and environment loading
utilities for Azure File Share configuration. It ensures configuration integrity
and provides detailed validation feedback.
"""

import os
import re
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass
from enum import Enum
from pydantic import BaseModel, Field, ValidationError
import logging
from urllib.parse import urlparse

from ..azure_config import AzureFileShareConfig, get_azure_config


class ValidationLevel(str, Enum):
    """Validation severity levels."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationResult:
    """Result of a configuration validation check."""

    level: ValidationLevel
    field: str
    message: str
    value: Optional[Any] = None
    suggestion: Optional[str] = None


class ConfigValidationReport(BaseModel):
    """Comprehensive validation report for Azure configuration."""

    is_valid: bool = Field(description="Overall validation status")
    errors: List[ValidationResult] = Field(
        default_factory=list, description="Critical errors"
    )
    warnings: List[ValidationResult] = Field(
        default_factory=list, description="Non-critical warnings"
    )
    info: List[ValidationResult] = Field(
        default_factory=list, description="Informational messages"
    )
    config_summary: Dict[str, Any] = Field(
        default_factory=dict, description="Configuration summary"
    )

    def add_result(self, result: ValidationResult) -> None:
        """Add a validation result to the appropriate category."""
        if result.level == ValidationLevel.ERROR:
            self.errors.append(result)
            self.is_valid = False
        elif result.level == ValidationLevel.WARNING:
            self.warnings.append(result)
        else:
            self.info.append(result)

    def get_total_issues(self) -> int:
        """Get total number of issues (errors + warnings)."""
        return len(self.errors) + len(self.warnings)

    def get_summary(self) -> Dict[str, int]:
        """Get summary of validation results."""
        return {
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "info": len(self.info),
            "total_issues": self.get_total_issues(),
        }


class AzureConfigValidator:
    """Comprehensive Azure configuration validator."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the validator with optional logger."""
        self.logger = logger or logging.getLogger(__name__)

    def validate_config(
        self, config: Optional[AzureFileShareConfig] = None
    ) -> ConfigValidationReport:
        """
        Perform comprehensive validation of Azure configuration.

        Args:
            config: Optional configuration to validate. If None, uses current config.

        Returns:
            Detailed validation report
        """
        if config is None:
            try:
                config = get_azure_config()
            except Exception as e:
                report = ConfigValidationReport(is_valid=False)
                report.add_result(
                    ValidationResult(
                        level=ValidationLevel.ERROR,
                        field="config_loading",
                        message=f"Failed to load configuration: {str(e)}",
                        suggestion="Check environment variables and configuration files",
                    )
                )
                return report

        report = ConfigValidationReport(is_valid=True)

        # Validate connection settings
        self._validate_connection_settings(config, report)

        # Validate operational settings
        self._validate_operational_settings(config, report)

        # Validate directory structure
        self._validate_directory_structure(config, report)

        # Validate feature flags
        self._validate_feature_flags(config, report)

        # Generate configuration summary
        self._generate_config_summary(config, report)

        # Log validation results
        self._log_validation_results(report)

        return report

    def _validate_connection_settings(
        self, config: AzureFileShareConfig, report: ConfigValidationReport
    ) -> None:
        """Validate Azure connection settings."""

        # Validate connection string
        try:
            connection_string = config.get_connection_string()

            if not connection_string:
                report.add_result(
                    ValidationResult(
                        level=ValidationLevel.ERROR,
                        field="connection_string",
                        message="Connection string is empty or None",
                        suggestion="Set AZURE_STORAGE_CONNECTION_STRING or provide account name/key",
                    )
                )
                return

            # Validate connection string format
            self._validate_connection_string_format(connection_string, report)

        except Exception as e:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.ERROR,
                    field="connection_string",
                    message=f"Failed to get connection string: {str(e)}",
                    suggestion="Check AZURE_STORAGE_CONNECTION_STRING or account credentials",
                )
            )

        # Validate individual components if available
        if config.AZURE_STORAGE_ACCOUNT_NAME:
            self._validate_account_name(config.AZURE_STORAGE_ACCOUNT_NAME, report)

        if config.AZURE_STORAGE_ACCOUNT_KEY:
            self._validate_account_key(config.AZURE_STORAGE_ACCOUNT_KEY, report)

    def _validate_connection_string_format(
        self, connection_string: str, report: ConfigValidationReport
    ) -> None:
        """Validate Azure Storage connection string format."""

        required_components = ["AccountName=", "AccountKey="]
        missing_components = []

        for component in required_components:
            if component not in connection_string:
                missing_components.append(component.rstrip("="))

        if missing_components:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.ERROR,
                    field="connection_string_format",
                    message=f"Missing required components: {', '.join(missing_components)}",
                    suggestion="Ensure connection string includes AccountName and AccountKey",
                )
            )

        # Check for common issues
        if "DefaultEndpointsProtocol=" not in connection_string:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.WARNING,
                    field="connection_string_protocol",
                    message="DefaultEndpointsProtocol not specified",
                    suggestion="Consider adding DefaultEndpointsProtocol=https for security",
                )
            )

        # Validate account name extraction
        try:
            account_name_match = re.search(r"AccountName=([^;]+)", connection_string)
            if account_name_match:
                account_name = account_name_match.group(1)
                self._validate_account_name(account_name, report)
        except Exception as e:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.WARNING,
                    field="connection_string_parsing",
                    message=f"Could not parse account name from connection string: {str(e)}",
                )
            )

    def _validate_account_name(
        self, account_name: str, report: ConfigValidationReport
    ) -> None:
        """Validate Azure Storage account name."""

        if not account_name:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.ERROR,
                    field="account_name",
                    message="Account name is empty",
                )
            )
            return

        # Azure Storage account name rules
        if len(account_name) < 3 or len(account_name) > 24:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.ERROR,
                    field="account_name_length",
                    message=f"Account name length ({len(account_name)}) must be between 3 and 24 characters",
                    value=account_name,
                )
            )

        if not account_name.islower():
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.ERROR,
                    field="account_name_case",
                    message="Account name must be lowercase",
                    value=account_name,
                    suggestion="Convert account name to lowercase",
                )
            )

        if not account_name.isalnum():
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.ERROR,
                    field="account_name_chars",
                    message="Account name can only contain letters and numbers",
                    value=account_name,
                )
            )

    def _validate_account_key(
        self, account_key: str, report: ConfigValidationReport
    ) -> None:
        """Validate Azure Storage account key."""

        if not account_key:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.ERROR,
                    field="account_key",
                    message="Account key is empty",
                )
            )
            return

        # Basic validation for account key format (Base64)
        if len(account_key) != 88:  # Standard Azure account key length
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.WARNING,
                    field="account_key_length",
                    message=f"Account key length ({len(account_key)}) is not standard (88 characters)",
                    suggestion="Verify account key is correct",
                )
            )

        # Check if it looks like Base64
        import base64

        try:
            base64.b64decode(account_key, validate=True)
        except Exception:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.WARNING,
                    field="account_key_format",
                    message="Account key does not appear to be valid Base64",
                    suggestion="Verify account key format",
                )
            )

    def _validate_operational_settings(
        self, config: AzureFileShareConfig, report: ConfigValidationReport
    ) -> None:
        """Validate operational settings."""

        # Validate retry settings
        if config.AZURE_RETRY_ATTEMPTS < 1:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.ERROR,
                    field="retry_attempts",
                    message="Retry attempts must be at least 1",
                    value=config.AZURE_RETRY_ATTEMPTS,
                )
            )
        elif config.AZURE_RETRY_ATTEMPTS > 10:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.WARNING,
                    field="retry_attempts",
                    message="High retry attempts may cause delays",
                    value=config.AZURE_RETRY_ATTEMPTS,
                    suggestion="Consider reducing retry attempts for better performance",
                )
            )

        # Validate retry delay
        if config.AZURE_RETRY_DELAY < 0.1:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.WARNING,
                    field="retry_delay",
                    message="Very short retry delay may overwhelm the service",
                    value=config.AZURE_RETRY_DELAY,
                )
            )
        elif config.AZURE_RETRY_DELAY > 60:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.WARNING,
                    field="retry_delay",
                    message="Long retry delay may cause timeouts",
                    value=config.AZURE_RETRY_DELAY,
                )
            )

        # Validate timeout
        if config.AZURE_TIMEOUT_SECONDS < 5:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.WARNING,
                    field="timeout",
                    message="Short timeout may cause premature failures",
                    value=config.AZURE_TIMEOUT_SECONDS,
                )
            )
        elif config.AZURE_TIMEOUT_SECONDS > 300:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.WARNING,
                    field="timeout",
                    message="Long timeout may cause poor user experience",
                    value=config.AZURE_TIMEOUT_SECONDS,
                )
            )

        # Validate file size limit
        if config.AZURE_MAX_FILE_SIZE_MB < 1:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.ERROR,
                    field="max_file_size",
                    message="Maximum file size must be at least 1 MB",
                    value=config.AZURE_MAX_FILE_SIZE_MB,
                )
            )
        elif config.AZURE_MAX_FILE_SIZE_MB > 1000:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.WARNING,
                    field="max_file_size",
                    message="Large file size limit may impact performance",
                    value=config.AZURE_MAX_FILE_SIZE_MB,
                )
            )

    def _validate_directory_structure(
        self, config: AzureFileShareConfig, report: ConfigValidationReport
    ) -> None:
        """Validate directory structure settings."""

        # Validate file share name
        share_name = config.AZURE_FILE_SHARE_NAME
        if not share_name:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.ERROR,
                    field="share_name",
                    message="File share name cannot be empty",
                )
            )
            return

        # Azure File Share naming rules
        if len(share_name) < 3 or len(share_name) > 63:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.ERROR,
                    field="share_name_length",
                    message=f"Share name length ({len(share_name)}) must be between 3 and 63 characters",
                    value=share_name,
                )
            )

        if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$", share_name):
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.ERROR,
                    field="share_name_format",
                    message="Share name must start and end with alphanumeric characters, contain only lowercase letters, numbers, and hyphens",
                    value=share_name,
                )
            )

        if "--" in share_name:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.ERROR,
                    field="share_name_consecutive_hyphens",
                    message="Share name cannot contain consecutive hyphens",
                    value=share_name,
                )
            )

        # Validate base directory
        base_dir = config.AZURE_BASE_DIRECTORY
        if not base_dir:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.WARNING,
                    field="base_directory",
                    message="Base directory is empty, files will be stored in root",
                    suggestion="Consider setting a base directory for organization",
                )
            )
        elif base_dir.startswith("/") or base_dir.endswith("/"):
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.WARNING,
                    field="base_directory_slashes",
                    message="Base directory should not start or end with slashes",
                    value=base_dir,
                    suggestion="Remove leading/trailing slashes",
                )
            )

    def _validate_feature_flags(
        self, config: AzureFileShareConfig, report: ConfigValidationReport
    ) -> None:
        """Validate feature flag settings."""

        if not config.AZURE_ENABLED:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.INFO,
                    field="azure_enabled",
                    message="Azure File Share integration is disabled",
                    suggestion="Enable AZURE_ENABLED to use Azure File Share features",
                )
            )

        if config.AZURE_ENABLED and not config.AZURE_AUTO_CREATE_SHARE:
            report.add_result(
                ValidationResult(
                    level=ValidationLevel.WARNING,
                    field="auto_create_share",
                    message="Auto-create share is disabled, manual share creation required",
                    suggestion="Enable AZURE_AUTO_CREATE_SHARE for automatic setup",
                )
            )

    def _generate_config_summary(
        self, config: AzureFileShareConfig, report: ConfigValidationReport
    ) -> None:
        """Generate configuration summary."""

        try:
            summary = {
                "enabled": config.AZURE_ENABLED,
                "share_name": config.AZURE_FILE_SHARE_NAME,
                "base_directory": config.AZURE_BASE_DIRECTORY,
                "retry_attempts": config.AZURE_RETRY_ATTEMPTS,
                "retry_delay": config.AZURE_RETRY_DELAY,
                "timeout_seconds": config.AZURE_TIMEOUT_SECONDS,
                "max_file_size_mb": config.AZURE_MAX_FILE_SIZE_MB,
                "auto_create_share": config.AZURE_AUTO_CREATE_SHARE,
                "logging_enabled": config.AZURE_ENABLE_LOGGING,
                "has_connection_string": bool(config.AZURE_STORAGE_CONNECTION_STRING),
                "has_account_name": bool(config.AZURE_STORAGE_ACCOUNT_NAME),
                "has_account_key": bool(config.AZURE_STORAGE_ACCOUNT_KEY),
            }

            # Add path examples
            test_project_id = "example-project-123"
            test_generation_hash = "gen-abc123"

            summary["path_examples"] = {
                "project_path": config.get_project_path(test_project_id),
                "generation_path": config.get_generation_path(
                    test_project_id, test_generation_hash
                ),
                "file_path": config.get_file_path(
                    test_project_id, test_generation_hash, "main.tf"
                ),
            }

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
                f"Azure configuration validation passed with {summary['warnings']} warnings"
            )
        else:
            self.logger.error(
                f"Azure configuration validation failed with {summary['errors']} errors"
            )

        # Log errors
        for error in report.errors:
            self.logger.error(f"Config error in {error.field}: {error.message}")

        # Log warnings
        for warning in report.warnings:
            self.logger.warning(f"Config warning in {warning.field}: {warning.message}")


class EnvironmentLoader:
    """Utilities for loading and managing environment variables for Azure configuration."""

    @staticmethod
    def load_from_file(file_path: str) -> Dict[str, str]:
        """
        Load environment variables from a file.

        Args:
            file_path: Path to the environment file

        Returns:
            Dictionary of environment variables
        """
        env_vars = {}

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Environment file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue

                # Parse key=value pairs
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")

                    # Only include Azure-related variables
                    if key.startswith("AZURE_"):
                        env_vars[key] = value
                else:
                    logging.warning(
                        f"Invalid line format in {file_path}:{line_num}: {line}"
                    )

        return env_vars

    @staticmethod
    def get_azure_env_vars() -> Dict[str, Optional[str]]:
        """Get all Azure-related environment variables."""
        azure_vars = {}

        for key, value in os.environ.items():
            if key.startswith("AZURE_"):
                azure_vars[key] = value

        return azure_vars

    @staticmethod
    def validate_required_env_vars() -> Tuple[bool, List[str]]:
        """
        Validate that required environment variables are set.

        Returns:
            Tuple of (all_present, missing_vars)
        """
        required_vars = ["AZURE_STORAGE_CONNECTION_STRING", "AZURE_FILE_SHARE_NAME"]

        # Alternative authentication method
        alternative_vars = ["AZURE_STORAGE_ACCOUNT_NAME", "AZURE_STORAGE_ACCOUNT_KEY"]

        missing_vars = []

        # Check if connection string is provided
        if not os.getenv("AZURE_STORAGE_CONNECTION_STRING"):
            # Check if alternative authentication is provided
            if not all(os.getenv(var) for var in alternative_vars):
                missing_vars.extend(
                    [
                        "AZURE_STORAGE_CONNECTION_STRING (or AZURE_STORAGE_ACCOUNT_NAME + AZURE_STORAGE_ACCOUNT_KEY)"
                    ]
                )

        # Check other required variables
        if not os.getenv("AZURE_FILE_SHARE_NAME"):
            missing_vars.append("AZURE_FILE_SHARE_NAME")

        return len(missing_vars) == 0, missing_vars

    @staticmethod
    def set_env_vars(env_vars: Dict[str, str], override: bool = False) -> None:
        """
        Set environment variables.

        Args:
            env_vars: Dictionary of environment variables to set
            override: Whether to override existing variables
        """
        for key, value in env_vars.items():
            if override or key not in os.environ:
                os.environ[key] = value

    @staticmethod
    def create_env_template() -> str:
        """Create a template for Azure environment variables."""
        template = """# Azure File Share Configuration
# Connection Settings (choose one method)

# Method 1: Connection String (recommended)
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=your_account;AccountKey=your_key;EndpointSuffix=core.windows.net

# Method 2: Account Name and Key (alternative)
# AZURE_STORAGE_ACCOUNT_NAME=your_storage_account_name
# AZURE_STORAGE_ACCOUNT_KEY=your_storage_account_key

# File Share Settings
AZURE_FILE_SHARE_NAME=infrajet-projects
AZURE_BASE_DIRECTORY=projects

# Operational Settings
AZURE_RETRY_ATTEMPTS=3
AZURE_RETRY_DELAY=1.0
AZURE_TIMEOUT_SECONDS=30
AZURE_MAX_FILE_SIZE_MB=100

# Feature Flags
AZURE_ENABLED=true
AZURE_AUTO_CREATE_SHARE=true
AZURE_ENABLE_LOGGING=true
"""
        return template


# Convenience functions
def validate_azure_configuration(
    config: Optional[AzureFileShareConfig] = None,
) -> ConfigValidationReport:
    """Validate Azure configuration and return detailed report."""
    validator = AzureConfigValidator()
    return validator.validate_config(config)


def quick_validate_azure_config() -> Tuple[bool, str]:
    """
    Quick validation of Azure configuration.

    Returns:
        Tuple of (is_valid, summary_message)
    """
    try:
        report = validate_azure_configuration()

        if report.is_valid:
            warnings = len(report.warnings)
            if warnings > 0:
                return True, f"Configuration valid with {warnings} warnings"
            else:
                return True, "Configuration is valid"
        else:
            errors = len(report.errors)
            return False, f"Configuration invalid with {errors} errors"

    except Exception as e:
        return False, f"Validation failed: {str(e)}"


def load_azure_env_from_file(file_path: str = ".env") -> Dict[str, str]:
    """Load Azure environment variables from file."""
    loader = EnvironmentLoader()
    return loader.load_from_file(file_path)


def check_azure_env_requirements() -> Tuple[bool, List[str]]:
    """Check if required Azure environment variables are set."""
    loader = EnvironmentLoader()
    return loader.validate_required_env_vars()
