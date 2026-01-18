from datetime import datetime
from typing import Any
from sqlalchemy.ext.declarative import as_declarative, declared_attr
from sqlalchemy import Column, DateTime

@as_declarative()
class Base:
    id: Any
    __name__: str

    # Generate __tablename__ automatically
    @declared_attr
    def __tablename__(cls) -> str:
        return cls.__name__.lower()

    # Common columns
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

from .user import (
    User,
    RefreshToken,
    UserRole,
    GitHubSyncRecord,
    GitHubSyncStatus,
    UserPreferences,
    WebSocketSession,
)
from .embedding import Repository, FileEmbedding
from .project import (
    Project,
    ProjectFile,
    CodeGeneration,
    GeneratedFile,
    ProjectStatus,
    GenerationStatus,
)
from .chat import (
    ProjectChat,
    MessageType,
    ConversationThread,
    ConversationContext,
    ClarificationRequest,
    GenerationLineage,
)

__all__ = [
    "Base",
    "User",
    "RefreshToken",
    "UserRole",
    "GitHubSyncRecord",
    "GitHubSyncStatus",
    "UserPreferences",
    "WebSocketSession",
    "Repository",
    "FileEmbedding",
    "Project",
    "ProjectFile",
    "CodeGeneration",
    "GeneratedFile",
    "ProjectStatus",
    "GenerationStatus",
    "ProjectChat",
    "MessageType",
    "ConversationThread",
    "ConversationContext",
    "ClarificationRequest",
    "GenerationLineage",
]
