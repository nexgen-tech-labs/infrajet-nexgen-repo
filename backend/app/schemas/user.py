from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field, validator
from app.models.user import UserRole


# Shared properties
class UserBase(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = True
    role: Optional[UserRole] = UserRole.USER


# Properties to receive on user creation
class UserCreate(UserBase):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)

    @validator("password")
    def password_complexity(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number")
        return v


# Properties to receive on user update (admin only)
class UserUpdate(UserBase):
    password: Optional[str] = Field(None, min_length=8, max_length=100)

    @validator("password")
    def password_complexity(cls, v):
        if v is not None:
            if len(v) < 8:
                raise ValueError("Password must be at least 8 characters long")
            if not any(c.isupper() for c in v):
                raise ValueError("Password must contain at least one uppercase letter")
            if not any(c.islower() for c in v):
                raise ValueError("Password must contain at least one lowercase letter")
            if not any(c.isdigit() for c in v):
                raise ValueError("Password must contain at least one number")
        return v


# Properties shared by models stored in DB
class UserInDBBase(UserBase):
    id: int
    email: EmailStr
    is_active: bool
    role: UserRole
    created_at: datetime
    updated_at: datetime
    email_verified: Optional[datetime] = None
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


# Properties to return to client
class User(UserInDBBase):
    pass


# Properties stored in DB
class UserInDB(UserInDBBase):
    hashed_password: str


# Response model for listing users (without sensitive data)
class UserList(BaseModel):
    items: List[User]
    total: int

    class Config:
        from_attributes = True


# Authentication models
class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserRegister(UserCreate):
    password_confirm: str

    @validator("password_confirm")
    def passwords_match(cls, v, values, **kwargs):
        if "password" in values and v != values["password"]:
            raise ValueError("Passwords do not match")
        return v


class UserInResponse(BaseModel):
    user: User
    token: str
    refresh_token: str


# Enhanced user profile schemas for comprehensive profile management
class AzureEntraProfile(BaseModel):
    """Azure Entra profile information."""

    azure_entra_id: Optional[str] = None
    azure_tenant_id: Optional[str] = None
    organization: Optional[str] = None
    department: Optional[str] = None
    profile_picture_url: Optional[str] = None
    token_expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class GitHubIntegration(BaseModel):
    """GitHub integration status."""

    is_connected: bool
    username: Optional[str] = None
    connected_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ConnectedServices(BaseModel):
    """Connected services information."""

    github: GitHubIntegration
    azure_entra: AzureEntraProfile

    class Config:
        from_attributes = True


class UserSession(BaseModel):
    """User session information."""

    session_id: str
    user_id: int
    connected_at: datetime
    last_heartbeat: datetime
    metadata: Dict[str, Any] = {}
    is_active: bool = True

    class Config:
        from_attributes = True


class UserPreferences(BaseModel):
    """User preferences and settings."""

    theme: Optional[str] = "light"
    language: Optional[str] = "en"
    timezone: Optional[str] = "UTC"
    email_notifications: bool = True
    realtime_updates: bool = True
    auto_sync_github: bool = False

    class Config:
        from_attributes = True


class UserProfileComplete(BaseModel):
    """Complete user profile with all related information."""

    # Basic user info
    id: int
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool
    role: UserRole
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None

    # Connected services
    connected_services: ConnectedServices

    # Active sessions
    active_sessions: List[UserSession] = []

    # User preferences
    preferences: UserPreferences

    # Statistics
    total_projects: int = 0
    total_generations: int = 0
    github_sync_count: int = 0

    class Config:
        from_attributes = True


class UserPreferencesUpdate(BaseModel):
    """Schema for updating user preferences."""

    theme: Optional[str] = None
    language: Optional[str] = None
    timezone: Optional[str] = None
    email_notifications: Optional[bool] = None
    realtime_updates: Optional[bool] = None
    auto_sync_github: Optional[bool] = None

    @validator("theme")
    def validate_theme(cls, v):
        if v is not None and v not in ["light", "dark", "auto"]:
            raise ValueError("Theme must be one of: light, dark, auto")
        return v

    @validator("language")
    def validate_language(cls, v):
        if v is not None and len(v) != 2:
            raise ValueError("Language must be a 2-character ISO code")
        return v


class SessionRevocationRequest(BaseModel):
    """Request to revoke specific sessions."""

    session_ids: List[str]
    revoke_all: bool = False


class SessionRevocationResponse(BaseModel):
    """Response for session revocation."""

    revoked_sessions: List[str]
    failed_sessions: List[str]
    total_revoked: int
    message: str
