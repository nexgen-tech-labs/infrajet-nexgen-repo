from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Enum,
    ForeignKey,
    Text,
    JSON,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import enum


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"
    SUPERUSER = "superuser"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String(255), nullable=True, index=True)  # Added for compatibility
    full_name = Column(String, index=True, nullable=True)
    is_active = Column(Boolean(), default=True)
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False)

    # Profile fields (keeping these as they may be useful for other auth providers)
    profile_picture_url = Column(String(500), nullable=True)
    organization = Column(String(255), nullable=True)
    department = Column(String(255), nullable=True)

    # GitHub integration fields
    github_user_id = Column(Integer, nullable=True, unique=True, index=True)  # GitHub user/org ID
    github_username = Column(String(255), nullable=True)
    github_email = Column(String(255), nullable=True)
    github_access_token = Column(Text, nullable=True)  # Encrypted OAuth token
    github_token_expires_at = Column(DateTime, nullable=True)

    # GitHub App integration fields
    github_installation_id = Column(Integer, nullable=True, index=True)
    github_app_id = Column(Integer, nullable=True)
    github_connected_at = Column(DateTime, nullable=True)

    # Timestamps
    email_verified = Column(DateTime, nullable=True)
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    # Relationships
    refresh_tokens = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )
    github_sync_records = relationship(
        "GitHubSyncRecord", back_populates="user", cascade="all, delete-orphan"
    )
    preferences = relationship(
        "UserPreferences",
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    websocket_sessions = relationship(
        "WebSocketSession", back_populates="user", cascade="all, delete-orphan"
    )

    def connect_github_oauth(self, github_user_id: int, github_username: str,
                           github_email: Optional[str], access_token: str,
                           token_expires_at: Optional[datetime]) -> None:
        """Connect GitHub OAuth account."""
        self.github_user_id = github_user_id
        self.github_username = github_username
        self.github_email = github_email
        self.github_access_token = access_token  # Should be encrypted in production
        self.github_token_expires_at = token_expires_at
        self.updated_at = func.now()

    def connect_github_app(self, installation_id: int, app_id: int) -> None:
        """Connect GitHub App installation."""
        self.github_installation_id = installation_id
        self.github_app_id = app_id
        self.github_connected_at = func.now()
        self.updated_at = func.now()

    def disconnect_github_oauth(self) -> None:
        """Disconnect GitHub OAuth."""
        self.github_user_id = None
        self.github_username = None
        self.github_email = None
        self.github_access_token = None
        self.github_token_expires_at = None
        self.updated_at = func.now()

    def disconnect_github_app(self) -> None:
        """Disconnect GitHub App installation."""
        self.github_installation_id = None
        self.github_app_id = None
        self.github_connected_at = None
        self.updated_at = func.now()

    @property
    def is_github_app_connected(self) -> bool:
        """Check if GitHub App is connected."""
        return (
            self.github_installation_id is not None
            and self.github_app_id is not None
        )

    def __repr__(self):
        return f"<User {self.email}>"


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Relationships
    user = relationship("User", back_populates="refresh_tokens")

    def __repr__(self):
        return f"<RefreshToken {self.token[:10]}...>"


class GitHubSyncStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GitHubSyncRecord(Base):
    __tablename__ = "github_sync_records"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    github_repository = Column(String(255), nullable=False)
    github_repo_id = Column(Integer, nullable=True, index=True)  # GitHub repository ID
    github_installation_id = Column(Integer, nullable=True, index=True)  # GitHub App installation ID
    last_sync_at = Column(DateTime, nullable=True)
    sync_status = Column(
        String(50), default=GitHubSyncStatus.PENDING.value, nullable=False
    )
    last_commit_sha = Column(String(40), nullable=True)
    sync_errors = Column(Text, nullable=True)

    # Enhanced tracking fields
    files_synced_count = Column(Integer, default=0, nullable=False)
    conflicts_resolved_count = Column(Integer, default=0, nullable=False)
    sync_duration_seconds = Column(Integer, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    branch_name = Column(String(255), default="main", nullable=False)

    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    # Relationships
    user = relationship("User", back_populates="github_sync_records")
    project = relationship("Project", back_populates="github_sync_records")

    def mark_as_started(self) -> None:
        """Mark sync as started."""
        self.sync_status = GitHubSyncStatus.IN_PROGRESS.value
        self.updated_at = func.now()

    def mark_as_completed(
        self,
        files_synced: int = 0,
        conflicts_resolved: int = 0,
        duration_seconds: Optional[int] = None,
        commit_sha: Optional[str] = None,
    ) -> None:
        """Mark sync as completed with metrics."""
        self.sync_status = GitHubSyncStatus.COMPLETED.value
        self.last_sync_at = func.now()
        self.files_synced_count = files_synced
        self.conflicts_resolved_count = conflicts_resolved
        if duration_seconds:
            self.sync_duration_seconds = duration_seconds
        if commit_sha:
            self.last_commit_sha = commit_sha
        self.sync_errors = None
        self.updated_at = func.now()

    def mark_as_failed(
        self, error_message: str, duration_seconds: Optional[int] = None
    ) -> None:
        """Mark sync as failed with error details."""
        self.sync_status = GitHubSyncStatus.FAILED.value
        self.sync_errors = error_message
        if duration_seconds:
            self.sync_duration_seconds = duration_seconds
        self.updated_at = func.now()

    def increment_retry_count(self) -> None:
        """Increment retry count."""
        self.retry_count += 1
        self.updated_at = func.now()

    @property
    def is_completed(self) -> bool:
        """Check if sync is completed."""
        return self.sync_status == GitHubSyncStatus.COMPLETED.value

    @property
    def is_failed(self) -> bool:
        """Check if sync failed."""
        return self.sync_status == GitHubSyncStatus.FAILED.value

    @property
    def is_in_progress(self) -> bool:
        """Check if sync is in progress."""
        return self.sync_status == GitHubSyncStatus.IN_PROGRESS.value

    def __repr__(self):
        return f"<GitHubSyncRecord {self.project_id} -> {self.github_repository}>"


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # UI preferences
    theme = Column(String(20), default="light", nullable=False)
    language = Column(String(5), default="en", nullable=False)
    timezone = Column(String(50), default="UTC", nullable=False)

    # Notification preferences
    email_notifications = Column(Boolean, default=True, nullable=False)
    realtime_updates = Column(Boolean, default=True, nullable=False)

    # Integration preferences
    auto_sync_github = Column(Boolean, default=False, nullable=False)

    # Additional settings as JSON
    additional_settings = Column(JSON, nullable=True)

    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    # Relationships
    user = relationship("User", back_populates="preferences")

    def update_preferences(self, **kwargs) -> None:
        """Update user preferences."""
        for key, value in kwargs.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)
        self.updated_at = func.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert preferences to dictionary."""
        return {
            "theme": self.theme,
            "language": self.language,
            "timezone": self.timezone,
            "email_notifications": self.email_notifications,
            "realtime_updates": self.realtime_updates,
            "auto_sync_github": self.auto_sync_github,
            "additional_settings": self.additional_settings or {},
        }

    def __repr__(self):
        return f"<UserPreferences user_id={self.user_id}>"


# Create a simple base class without deleted_at for GitHub connections
SimpleBase = declarative_base()

class GitHubConnection(SimpleBase):
    """Simple GitHub connection details stored in Azure PostgreSQL."""
    __tablename__ = "github_connections"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # GitHub fields
    github_user_id = Column(Integer, nullable=True, unique=True, index=True)
    github_username = Column(String(255), nullable=True)
    github_access_token = Column(Text, nullable=True)  # Encrypted
    github_installation_id = Column(Integer, nullable=True, index=True)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)

    # Timestamps
    # github_connected_at = Column(DateTime, nullable=True)  # TODO: Add after migration
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

    def connect_github(
        self,
        github_user_id: int,
        github_username: str,
        access_token: str,
        installation_id: Optional[int] = None
    ) -> None:
        """Connect GitHub account."""
        self.github_user_id = github_user_id
        self.github_username = github_username
        self.github_access_token = access_token  # Should be encrypted
        self.github_installation_id = installation_id
        # self.github_connected_at = func.now()  # TODO: Add after migration
        self.is_active = True
        self.updated_at = func.now()

    def disconnect_github(self) -> None:
        """Disconnect GitHub account."""
        self.is_active = False
        self.updated_at = func.now()

    @property
    def is_connected(self) -> bool:
        """Check if GitHub is connected."""
        return (
            self.github_user_id is not None
            and self.github_access_token is not None
            and self.is_active
        )

    def __repr__(self):
        return f"<GitHubConnection user_id={self.user_id} github_user={self.github_username}>"


class WebSocketSession(Base):
    __tablename__ = "websocket_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Session metadata
    connected_at = Column(DateTime, nullable=False, default=func.now())
    last_heartbeat = Column(DateTime, nullable=False, default=func.now())
    session_metadata = Column(JSON, nullable=True)

    # Session status
    is_active = Column(Boolean, default=True, nullable=False)
    disconnected_at = Column(DateTime, nullable=True)

    # Connection info
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(
        DateTime, nullable=False, default=func.now(), onupdate=func.now()
    )

    # Relationships
    user = relationship("User", back_populates="websocket_sessions")

    def update_heartbeat(self) -> None:
        """Update last heartbeat timestamp."""
        self.last_heartbeat = func.now()
        self.updated_at = func.now()

    def disconnect(self) -> None:
        """Mark session as disconnected."""
        self.is_active = False
        self.disconnected_at = func.now()
        self.updated_at = func.now()

    @property
    def duration(self) -> Optional[int]:
        """Get session duration in seconds."""
        if self.disconnected_at:
            return int((self.disconnected_at - self.connected_at).total_seconds())
        return int((datetime.utcnow() - self.connected_at).total_seconds())

    def __repr__(self):
        return f"<WebSocketSession {self.session_id} user_id={self.user_id}>"
