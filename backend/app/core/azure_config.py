"""
Azure File Share Configuration Module.

This module provides configuration management for Azure File Share integration,
including connection strings, authentication, and operational settings.
"""

from functools import lru_cache
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import os
from urllib.parse import urlparse


class AzureFileShareConfig(BaseSettings):
    """Azure File Share configuration settings."""
    
    # Connection Settings
    AZURE_STORAGE_CONNECTION_STRING: Optional[str] = Field(
        None, 
        description="Azure Storage connection string"
    )
    AZURE_STORAGE_ACCOUNT_NAME: Optional[str] = Field(
        None,
        description="Azure Storage account name"
    )
    AZURE_STORAGE_ACCOUNT_KEY: Optional[str] = Field(
        None,
        description="Azure Storage account key"
    )
    AZURE_FILE_SHARE_NAME: str = Field(
        "ngtl-fileshare",
        description="Name of the Azure File Share"
    )
    
    # Directory Structure
    AZURE_BASE_DIRECTORY: str = Field(
        "projects",
        description="Base directory for all projects in Azure File Share"
    )
    
    # Operation Settings
    AZURE_RETRY_ATTEMPTS: int = Field(
        3,
        ge=1,
        le=10,
        description="Number of retry attempts for Azure operations"
    )
    AZURE_RETRY_DELAY: float = Field(
        1.0,
        ge=0.1,
        le=60.0,
        description="Initial delay between retries in seconds"
    )
    AZURE_TIMEOUT_SECONDS: int = Field(
        30,
        ge=5,
        le=300,
        description="Timeout for Azure operations in seconds"
    )
    AZURE_MAX_FILE_SIZE_MB: int = Field(
        100,
        ge=1,
        le=1000,
        description="Maximum file size in MB"
    )
    
    # Feature Flags
    AZURE_ENABLED: bool = Field(
        True,
        description="Enable/disable Azure File Share integration"
    )
    AZURE_AUTO_CREATE_SHARE: bool = Field(
        True,
        description="Automatically create file share if it doesn't exist"
    )
    AZURE_ENABLE_LOGGING: bool = Field(
        True,
        description="Enable detailed logging for Azure operations"
    )
    
    @field_validator("AZURE_STORAGE_CONNECTION_STRING", mode="before")
    @classmethod
    def validate_connection_string(cls, v: Optional[str]) -> Optional[str]:
        """Validate Azure Storage connection string format."""
        if not v or v == "None":
            return None
            
        # Basic validation for connection string format
        required_parts = ["AccountName=", "AccountKey="]
        if not all(part in v for part in required_parts):
            raise ValueError(
                "Invalid Azure Storage connection string format. "
                "Must contain AccountName and AccountKey."
            )
        return v
    
    @field_validator("AZURE_FILE_SHARE_NAME", mode="before")
    @classmethod
    def validate_share_name(cls, v: str) -> str:
        """Validate Azure File Share name according to Azure naming rules."""
        if not v:
            raise ValueError("Azure File Share name cannot be empty")
        
        # Azure File Share naming rules
        if len(v) < 3 or len(v) > 63:
            raise ValueError("Azure File Share name must be between 3 and 63 characters")
        
        if not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Azure File Share name can only contain letters, numbers, hyphens, and underscores")
        
        if v.startswith("-") or v.endswith("-"):
            raise ValueError("Azure File Share name cannot start or end with a hyphen")
        
        return v.lower()  # Azure File Share names are case-insensitive
    
    def get_connection_string(self) -> str:
        """Get the Azure Storage connection string."""
        if self.AZURE_STORAGE_CONNECTION_STRING:
            return self.AZURE_STORAGE_CONNECTION_STRING
        
        if self.AZURE_STORAGE_ACCOUNT_NAME and self.AZURE_STORAGE_ACCOUNT_KEY:
            return (
                f"DefaultEndpointsProtocol=https;"
                f"AccountName={self.AZURE_STORAGE_ACCOUNT_NAME};"
                f"AccountKey={self.AZURE_STORAGE_ACCOUNT_KEY};"
                f"EndpointSuffix=core.windows.net"
            )
        
        raise ValueError(
            "Azure Storage connection string or account name/key must be provided. "
            "Set AZURE_STORAGE_CONNECTION_STRING or both AZURE_STORAGE_ACCOUNT_NAME "
            "and AZURE_STORAGE_ACCOUNT_KEY environment variables."
        )
    
    def get_project_path(self, project_id: str) -> str:
        """Get the full path for a project in Azure File Share."""
        return f"{self.AZURE_BASE_DIRECTORY}/{project_id}"
    
    def get_generation_path(self, project_id: str, generation_hash: str) -> str:
        """Get the full path for a specific generation within a project."""
        return f"{self.AZURE_BASE_DIRECTORY}/{project_id}/{generation_hash}"
    
    def get_file_path(self, project_id: str, generation_hash: str, file_path: str) -> str:
        """Get the full path for a specific file within a generation."""
        # Ensure file_path doesn't start with /
        file_path = file_path.lstrip("/")
        return f"{self.AZURE_BASE_DIRECTORY}/{project_id}/{generation_hash}/{file_path}"
    
    def is_enabled(self) -> bool:
        """Check if Azure File Share integration is enabled."""
        return self.AZURE_ENABLED
    
    def get_retry_config(self) -> Dict[str, Any]:
        """Get retry configuration for Azure operations."""
        return {
            "attempts": self.AZURE_RETRY_ATTEMPTS,
            "delay": self.AZURE_RETRY_DELAY,
            "timeout": self.AZURE_TIMEOUT_SECONDS
        }
    
    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_assignment=True
    )


class AzureConnectionInfo(BaseModel):
    """Azure connection information for health checks and monitoring."""
    
    account_name: Optional[str] = None
    share_name: str
    base_directory: str
    is_enabled: bool
    connection_valid: bool = False
    last_check: Optional[str] = None
    error_message: Optional[str] = None
    
    @classmethod
    def from_config(cls, config: AzureFileShareConfig) -> "AzureConnectionInfo":
        """Create connection info from configuration."""
        try:
            connection_string = config.get_connection_string()
            # Extract account name from connection string
            account_name = None
            if "AccountName=" in connection_string:
                start = connection_string.find("AccountName=") + len("AccountName=")
                end = connection_string.find(";", start)
                if end == -1:
                    end = len(connection_string)
                account_name = connection_string[start:end]
            
            return cls(
                account_name=account_name,
                share_name=config.AZURE_FILE_SHARE_NAME,
                base_directory=config.AZURE_BASE_DIRECTORY,
                is_enabled=config.is_enabled(),
                connection_valid=True
            )
        except Exception as e:
            return cls(
                share_name=config.AZURE_FILE_SHARE_NAME,
                base_directory=config.AZURE_BASE_DIRECTORY,
                is_enabled=config.is_enabled(),
                connection_valid=False,
                error_message=str(e)
            )


@lru_cache()
def get_azure_config() -> AzureFileShareConfig:
    """Get cached Azure File Share configuration."""
    return AzureFileShareConfig()


def validate_azure_config() -> tuple[bool, Optional[str]]:
    """
    Validate Azure configuration.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        config = get_azure_config()
        
        if not config.is_enabled():
            return True, "Azure File Share integration is disabled"
        
        # Test connection string
        config.get_connection_string()
        
        return True, None
    except Exception as e:
        return False, str(e)


# Configuration testing utilities
class AzureConfigTester:
    """Utilities for testing Azure configuration."""
    
    @staticmethod
    def create_test_config(**overrides) -> AzureFileShareConfig:
        """Create a test configuration with optional overrides."""
        test_values = {
            "AZURE_STORAGE_CONNECTION_STRING": "DefaultEndpointsProtocol=https;AccountName=testaccount;AccountKey=testkey;EndpointSuffix=core.windows.net",
            "AZURE_FILE_SHARE_NAME": "test-share",
            "AZURE_BASE_DIRECTORY": "test-projects",
            "AZURE_ENABLED": "true",
            **overrides
        }
        
        # Temporarily set environment variables
        original_env = {}
        for key, value in test_values.items():
            original_env[key] = os.environ.get(key)
            if value is not None:
                os.environ[key] = str(value)
            elif key in os.environ:
                del os.environ[key]
        
        try:
            config = AzureFileShareConfig()
            return config
        finally:
            # Restore original environment
            for key, original_value in original_env.items():
                if original_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = original_value
    
    @staticmethod
    def validate_test_config(config: AzureFileShareConfig) -> Dict[str, Any]:
        """Validate a test configuration and return validation results."""
        results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "info": {}
        }
        
        try:
            # Test connection string
            connection_string = config.get_connection_string()
            results["info"]["connection_string_length"] = len(connection_string)
            
            # Test path generation
            test_project_id = "test-project-123"
            test_generation_hash = "abc123"
            test_file_path = "main.tf"
            
            project_path = config.get_project_path(test_project_id)
            generation_path = config.get_generation_path(test_project_id, test_generation_hash)
            file_path = config.get_file_path(test_project_id, test_generation_hash, test_file_path)
            
            results["info"]["paths"] = {
                "project": project_path,
                "generation": generation_path,
                "file": file_path
            }
            
            # Test retry configuration
            retry_config = config.get_retry_config()
            results["info"]["retry_config"] = retry_config
            
        except Exception as e:
            results["valid"] = False
            results["errors"].append(str(e))
        
        return results