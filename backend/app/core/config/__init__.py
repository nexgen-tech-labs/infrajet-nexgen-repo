"""
Configuration package for Azure File Share and Supabase integration.

This package provides comprehensive configuration management, validation,
and environment loading utilities for Azure File Share and Supabase integration.
"""

from .azure_validator import (
    AzureConfigValidator,
    ConfigValidationReport,
    ValidationResult,
    ValidationLevel,
    EnvironmentLoader,
    validate_azure_configuration,
    quick_validate_azure_config,
    load_azure_env_from_file,
    check_azure_env_requirements,
)

from .supabase_validator import (
    SupabaseConfigValidator,
    SupabaseEnvironmentLoader,
    validate_supabase_configuration,
    quick_validate_supabase_config,
    check_supabase_env_requirements,
)

from .health_check import (
    ConfigurationHealthChecker,
    ComponentHealth,
    HealthStatus,
    check_configuration_health,
    quick_health_check,
    validate_startup_configuration,
)

# Import validation script functions for programmatic use
try:
    from .validate_config import validate_configuration, print_health_report
except ImportError:
    # Handle case where validation script dependencies are not available
    validate_configuration = None
    print_health_report = None

# Import the main settings function for backward compatibility
from ..settings import get_settings

__all__ = [
    # Azure validators
    "AzureConfigValidator",
    "ConfigValidationReport",
    "ValidationResult",
    "ValidationLevel",
    "EnvironmentLoader",
    "validate_azure_configuration",
    "quick_validate_azure_config",
    "load_azure_env_from_file",
    "check_azure_env_requirements",
    # Supabase validators
    "SupabaseConfigValidator",
    "SupabaseEnvironmentLoader",
    "validate_supabase_configuration",
    "quick_validate_supabase_config",
    "check_supabase_env_requirements",
    # Health check utilities
    "ConfigurationHealthChecker",
    "ComponentHealth",
    "HealthStatus",
    "check_configuration_health",
    "quick_health_check",
    "validate_startup_configuration",
    # Validation utilities
    "validate_configuration",
    "print_health_report",
    # Settings
    "get_settings",
]
