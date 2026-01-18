from functools import lru_cache
from typing import Optional, Union, Tuple, List, Dict, Any
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import EmailStr, field_validator, validator
import logging
# Disabled configuration imports
# from .azure_entra import AzureEntraConfig
# from .github import GitHubConfig


class Settings(BaseSettings):
    # App Settings
    APP_ENV: str = "development"
    LOG_LEVEL: str = "DEBUG"

    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Infrajet Backend"

    # Database
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "infrajet_db"
    DATABASE_URL: Optional[str] = None

    # JWT
    SECRET_KEY: str = "default-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    FRONTEND_URL: str = "http://localhost:8080"

    # First Superuser
    FIRST_SUPERUSER_EMAIL: EmailStr = "admin@example.com"
    FIRST_SUPERUSER_PASSWORD: str = "changeme"

    # Email
    SMTP_TLS: bool = True
    SMTP_PORT: Optional[int] = None
    SMTP_HOST: Optional[str] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_FROM_EMAIL: Optional[EmailStr] = None
    EMAILS_FROM_NAME: Optional[str] = None

    # Embedding Settings
    ANTHROPIC_API_KEY: Optional[str] = None
    EMBEDDING_MODEL: str = "claude-3-haiku-20240307"
    FAISS_INDEX_PATH: str = "data/embeddings"
    ALLOWED_EXTENSIONS: str = ".tf,.tfvars,.hcl"
    MAX_CHUNK_TOKENS: int = 400
    OVERLAP_TOKENS: int = 60
    EMBEDDING_DIMENSION: int = 1536

    # Supabase Configuration (Backend Integration)
    SUPABASE_URL: Optional[str] = None
    SUPABASE_ANON_KEY: Optional[str] = None
    SUPABASE_JWT_SECRET: Optional[str] = None
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None
    
    # Frontend Supabase Configuration (for reference/validation)
    VITE_SUPABASE_PROJECT_ID: Optional[str] = None
    VITE_SUPABASE_PUBLISHABLE_KEY: Optional[str] = None
    VITE_SUPABASE_URL: Optional[str] = None

    # Feature Flags - Disabled authentication and integration features
    ENTRA_AUTH_ENABLED: bool = False
    GITHUB_INTEGRATION_ENABLED: bool = True
    SUPABASE_AUTH_ENABLED: bool = True

    # GitHub App Configuration (for repository operations)
    GITHUB_APP_ID: Optional[str] = None
    GITHUB_APP_SLUG: Optional[str] = None  # App slug/name for installation URLs
    GITHUB_CLIENT_ID: Optional[str] = None
    GITHUB_CLIENT_SECRET: Optional[str] = None
    GITHUB_PRIVATE_KEY: Optional[str] = None
    GITHUB_WEBHOOK_SECRET: Optional[str] = None

    @field_validator("GITHUB_APP_ID", mode="before")
    @classmethod
    def validate_github_app_id(cls, v: Optional[Union[str, int]]) -> Optional[str]:
        """Convert GITHUB_APP_ID to string if it's an integer."""
        if v is None:
            return v
        return str(v)

    # Azure Entra ID Settings (DISABLED)
    # AZURE_ENTRA_CLIENT_ID: Optional[str] = None
    # AZURE_ENTRA_CLIENT_SECRET: Optional[str] = None
    # AZURE_ENTRA_TENANT_ID: Optional[str] = None
    # AZURE_ENTRA_AUTHORITY: Optional[str] = None
    # AZURE_ENTRA_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/callback"
    # AZURE_ENTRA_SCOPES: List[str] = ["openid", "profile", "email", "User.Read"]
    # AZURE_ENTRA_SESSION_TIMEOUT_MINUTES: int = 60
    # AZURE_ENTRA_VALIDATE_ISSUER: bool = True
    # AZURE_ENTRA_VALIDATE_AUDIENCE: bool = True

    # GitHub OAuth Settings (ENABLED)
    GITHUB_CLIENT_ID: Optional[str] = None
    GITHUB_CLIENT_SECRET: Optional[str] = None
    GITHUB_REDIRECT_URI: Optional[str] = None
    GITHUB_SCOPES: List[str] = ["repo", "user:email", "read:user"]

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str]) -> str:
        if isinstance(v, str) and v:
            return v
        # For now, return a default connection string
        # In production, you should set DATABASE_URL directly in .env
        return "postgresql+asyncpg://postgres:postgres@localhost:5432/infrajet_db"

    def get_allowed_extensions(self) -> Tuple[str, ...]:
        """Parse ALLOWED_EXTENSIONS string into a tuple."""
        if isinstance(self.ALLOWED_EXTENSIONS, str):
            # Parse string like ".tf,.tfvars,.hcl"
            extensions = []
            for ext in self.ALLOWED_EXTENSIONS.split(","):
                ext = ext.strip().strip('"').strip("'")
                if ext:
                    extensions.append(ext)
            return tuple(extensions)
        return (".tf", ".tfvars", ".hcl")  # Default fallback

    @field_validator("SUPABASE_URL", mode="before")
    @classmethod
    def validate_supabase_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate Supabase URL format."""
        if not v:
            return v
        
        if not v.startswith("https://"):
            raise ValueError("Supabase URL must start with https://")
        
        if not v.endswith(".supabase.co"):
            raise ValueError("Supabase URL must end with .supabase.co")
        
        return v

    @field_validator("SUPABASE_ANON_KEY", mode="before")
    @classmethod
    def validate_supabase_anon_key(cls, v: Optional[str]) -> Optional[str]:
        """Validate Supabase anonymous key format."""
        if not v:
            return v
        
        # Basic JWT format validation
        if not v.startswith("eyJ"):
            raise ValueError("Supabase anonymous key must be a valid JWT token")
        
        parts = v.split(".")
        if len(parts) != 3:
            raise ValueError("Supabase anonymous key must be a valid JWT token with 3 parts")
        
        return v

    def validate_supabase_config(self) -> Tuple[bool, List[str]]:
        """
        Validate Supabase configuration completeness.
        
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        if self.SUPABASE_AUTH_ENABLED:
            if not self.SUPABASE_URL:
                errors.append("SUPABASE_URL is required when Supabase authentication is enabled")
            
            if not self.SUPABASE_ANON_KEY:
                errors.append("SUPABASE_ANON_KEY is required when Supabase authentication is enabled")
            
            if not self.SUPABASE_JWT_SECRET:
                errors.append("SUPABASE_JWT_SECRET is required for JWT validation")
            
            if not self.SUPABASE_SERVICE_ROLE_KEY:
                errors.append("SUPABASE_SERVICE_ROLE_KEY is required for full table access")
            
            # Validate frontend/backend URL consistency
            if self.VITE_SUPABASE_URL and self.SUPABASE_URL:
                if self.VITE_SUPABASE_URL != self.SUPABASE_URL:
                    errors.append("Frontend and backend Supabase URLs must match")
            
            # Validate frontend/backend key consistency
            if self.VITE_SUPABASE_PUBLISHABLE_KEY and self.SUPABASE_ANON_KEY:
                if self.VITE_SUPABASE_PUBLISHABLE_KEY != self.SUPABASE_ANON_KEY:
                    errors.append("Frontend and backend Supabase keys must match")
        
        return len(errors) == 0, errors

    def validate_github_config(self) -> Tuple[bool, List[str]]:
        """
        Validate GitHub App configuration completeness.

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        if self.GITHUB_INTEGRATION_ENABLED:
            if not self.GITHUB_APP_ID:
                errors.append("GITHUB_APP_ID is required when GitHub integration is enabled")

            if not self.GITHUB_APP_SLUG:
                errors.append("GITHUB_APP_SLUG is required when GitHub integration is enabled")

            if not self.GITHUB_CLIENT_ID:
                errors.append("GITHUB_CLIENT_ID is required when GitHub integration is enabled")

            if not self.GITHUB_CLIENT_SECRET:
                errors.append("GITHUB_CLIENT_SECRET is required when GitHub integration is enabled")

            if not self.GITHUB_PRIVATE_KEY:
                errors.append("GITHUB_PRIVATE_KEY is required for GitHub App authentication")

        return len(errors) == 0, errors

    def get_feature_flags(self) -> dict:
        """Get current feature flag status."""
        return {
            "supabase_auth_enabled": self.SUPABASE_AUTH_ENABLED,
            "entra_auth_enabled": self.ENTRA_AUTH_ENABLED,
            "github_integration_enabled": self.GITHUB_INTEGRATION_ENABLED,
        }

    def is_github_configured(self) -> bool:
        """Check if GitHub App is properly configured."""
        is_valid, _ = self.validate_github_config()
        return is_valid and self.GITHUB_INTEGRATION_ENABLED

    def is_supabase_configured(self) -> bool:
        """Check if Supabase is properly configured."""
        is_valid, _ = self.validate_supabase_config()
        return is_valid and self.SUPABASE_AUTH_ENABLED

    def validate_all_configurations(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate all application configurations.
        
        Returns:
            Tuple of (is_valid, validation_report)
        """
        validation_report = {
            "overall_valid": True,
            "supabase": {"valid": True, "errors": []},
            "feature_flags": self.get_feature_flags(),
            "warnings": [],
            "errors": []
        }

        # Validate Supabase configuration
        if self.SUPABASE_AUTH_ENABLED:
            supabase_valid, supabase_errors = self.validate_supabase_config()
            validation_report["supabase"]["valid"] = supabase_valid
            validation_report["supabase"]["errors"] = supabase_errors
            
            if not supabase_valid:
                validation_report["overall_valid"] = False
                validation_report["errors"].extend(supabase_errors)

        # Validate feature flag consistency
        if self.ENTRA_AUTH_ENABLED and self.SUPABASE_AUTH_ENABLED:
            warning = "Both Entra ID and Supabase authentication are enabled"
            validation_report["warnings"].append(warning)

        # Validate GitHub configuration
        if self.GITHUB_INTEGRATION_ENABLED:
            github_valid, github_errors = self.validate_github_config()
            validation_report["github"] = {"valid": github_valid, "errors": github_errors}
            
            if not github_valid:
                validation_report["overall_valid"] = False
                validation_report["errors"].extend(github_errors)

        # Check for required environment variables based on enabled features
        if self.SUPABASE_AUTH_ENABLED:
            required_vars = ["SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_JWT_SECRET", "SUPABASE_SERVICE_ROLE_KEY"]
            missing_vars = [var for var in required_vars if not getattr(self, var)]
            if missing_vars:
                error = f"Missing required Supabase environment variables: {', '.join(missing_vars)}"
                validation_report["errors"].append(error)
                validation_report["overall_valid"] = False

        if self.GITHUB_INTEGRATION_ENABLED:
            required_vars = ["GITHUB_APP_ID", "GITHUB_APP_SLUG", "GITHUB_CLIENT_ID", "GITHUB_CLIENT_SECRET", "GITHUB_PRIVATE_KEY"]
            missing_vars = [var for var in required_vars if not getattr(self, var)]
            if missing_vars:
                error = f"Missing required GitHub App environment variables: {', '.join(missing_vars)}"
                validation_report["errors"].append(error)
                validation_report["overall_valid"] = False

        return validation_report["overall_valid"], validation_report

    # Disabled configuration methods
    # def get_azure_entra_config(self) -> AzureEntraConfig:
    #     """Get Azure Entra configuration."""
    #     return AzureEntraConfig(
    #         client_id=self.AZURE_ENTRA_CLIENT_ID or "",
    #         client_secret=self.AZURE_ENTRA_CLIENT_SECRET or "",
    #         tenant_id=self.AZURE_ENTRA_TENANT_ID or "",
    #         authority=self.AZURE_ENTRA_AUTHORITY,
    #         redirect_uri=self.AZURE_ENTRA_REDIRECT_URI,
    #         scopes=self.AZURE_ENTRA_SCOPES,
    #         session_timeout_minutes=self.AZURE_ENTRA_SESSION_TIMEOUT_MINUTES,
    #         validate_issuer=self.AZURE_ENTRA_VALIDATE_ISSUER,
    #         validate_audience=self.AZURE_ENTRA_VALIDATE_AUDIENCE,
    #     )

    # def get_github_config(self) -> GitHubConfig:
    #     """Get GitHub OAuth configuration."""
    #     return GitHubConfig(
    #         client_id=self.GITHUB_CLIENT_ID or "",
    #         client_secret=self.GITHUB_CLIENT_SECRET or "",
    #         redirect_uri=self.GITHUB_REDIRECT_URI,
    #         scopes=self.GITHUB_SCOPES,
    #     )

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra fields in .env
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
