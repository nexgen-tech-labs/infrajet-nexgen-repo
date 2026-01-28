from functools import lru_cache
from typing import Optional, Union, Tuple, List, Dict, Any
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import EmailStr, field_validator

class Settings(BaseSettings):
    # App Settings
    APP_ENV: str = "development"
    LOG_LEVEL: str = "DEBUG"

    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Infrajet Backend"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:infrajetdevdb202@/infrajetdb?host=/cloudsql/pgsql-infrajet-dev"

    # Redis (Valkey)
    REDIS_HOST: str = "infrajet-valkey-memstore"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None

    # Firebase
    FIREBASE_PROJECT_ID: str = "infrajet-nexgen-fb-55585-e9543"

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

    # Feature Flags
    ENTRA_AUTH_ENABLED: bool = False
    GITHUB_INTEGRATION_ENABLED: bool = True
    SUPABASE_AUTH_ENABLED: bool = False # Supabase is now disabled
    FIREBASE_AUTH_ENABLED: bool = True

    # GitHub App Configuration (for repository operations)
    GITHUB_APP_ID: Optional[str] = None
    GITHUB_APP_SLUG: Optional[str] = None
    GITHUB_CLIENT_ID: Optional[str] = None
    GITHUB_CLIENT_SECRET: Optional[str] = None
    GITHUB_PRIVATE_KEY: Optional[str] = None
    GITHUB_WEBHOOK_SECRET: Optional[str] = None

    @field_validator("GITHUB_APP_ID", mode="before")
    @classmethod
    def validate_github_app_id(cls, v: Optional[Union[str, int]]) -> Optional[str]:
        if v is None:
            return v
        return str(v)

    # GitHub OAuth Settings (ENABLED)
    GITHUB_OAUTH_CLIENT_ID: Optional[str] = None
    GITHUB_OAUTH_CLIENT_SECRET: Optional[str] = None
    GITHUB_REDIRECT_URI: Optional[str] = None
    GITHUB_SCOPES: List[str] = ["repo", "user:email", "read:user"]

    def get_allowed_extensions(self) -> Tuple[str, ...]:
        if isinstance(self.ALLOWED_EXTENSIONS, str):
            extensions = []
            for ext in self.ALLOWED_EXTENSIONS.split(","):
                ext = ext.strip().strip('\'').strip('"')
                if ext:
                    extensions.append(ext)
            return tuple(extensions)
        return (".tf", ".tfvars", ".hcl")

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

@lru_cache()
def get_settings() -> Settings:
    return Settings()
