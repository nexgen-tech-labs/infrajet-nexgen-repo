import enum
import uuid
from datetime import datetime
from typing import Dict, Any, List
from sqlalchemy import Column, String, Text, Enum, DateTime, ForeignKey, func, Integer, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base


class MessageType(str, enum.Enum):
    """Enum for different message types in chat."""
    USER = "user"
    SYSTEM = "system"
    AI = "ai"
    CLARIFICATION_REQUEST = "clarification_request"


class ProjectChat(Base):
    """
    ProjectChat model for storing chat messages associated with projects.
    Each message belongs to a project and is sent by a user.
    """
    __tablename__ = "project_chats"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)  # Supabase user ID
    message_content = Column(Text, nullable=False)
    message_type = Column(Enum(MessageType), default=MessageType.USER, nullable=False)
    timestamp = Column(DateTime, default=func.now(), nullable=False, index=True)
    thread_id = Column(String(36), ForeignKey("conversation_threads.id"), nullable=True, index=True)
    generation_id = Column(String(36), nullable=True, index=True)  # Links to CodeGeneration table for system messages

    # Relationships
    project = relationship("Project", back_populates="chats")
    thread = relationship("ConversationThread", back_populates="messages")

    def __init__(self, **kwargs):
        """Initialize ProjectChat with auto-generated UUID."""
        if 'id' not in kwargs:
            kwargs['id'] = str(uuid.uuid4())
        super().__init__(**kwargs)

    def __repr__(self):
        return f"<ProjectChat {self.id} ({self.message_type})>"

    @property
    def is_user_message(self) -> bool:
        """Check if message is from user."""
        return self.message_type == MessageType.USER

    @property
    def is_system_message(self) -> bool:
        """Check if message is from system."""
        return self.message_type == MessageType.SYSTEM

    @property
    def is_ai_message(self) -> bool:
        """Check if message is from AI."""
        return self.message_type == MessageType.AI

    @property
    def is_clarification_request(self) -> bool:
        """Check if message is a clarification request."""
        return self.message_type == MessageType.CLARIFICATION_REQUEST


class ConversationThread(Base):
    """
    ConversationThread model for managing autonomous chat conversation threads.

    Each thread represents a conversation session with context tracking.
    """
    __tablename__ = "conversation_threads"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)  # Supabase user ID
    title = Column(String(255), nullable=True)
    status = Column(String(50), nullable=False, default="active")
    cloud_provider = Column(String(50), nullable=False, default="AWS")  # Cloud provider (AWS, Azure, GCP)
    created_at = Column(DateTime, default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    last_message_at = Column(DateTime, nullable=True)

    # Relationships
    project = relationship("Project", back_populates="conversation_threads")
    contexts = relationship("ConversationContext", back_populates="thread", cascade="all, delete-orphan")
    clarification_requests = relationship("ClarificationRequest", back_populates="thread", cascade="all, delete-orphan")
    generation_lineage = relationship("GenerationLineage", back_populates="thread", cascade="all, delete-orphan")
    messages = relationship("ProjectChat", back_populates="thread")

    def __init__(self, **kwargs):
        """Initialize ConversationThread with auto-generated UUID."""
        if 'id' not in kwargs:
            kwargs['id'] = str(uuid.uuid4())
        super().__init__(**kwargs)

    def __repr__(self):
        return f"<ConversationThread {self.id} ({self.status})>"


class ConversationContext(Base):
    """
    ConversationContext model for storing conversation context and state.

    Tracks intent, code references, generation lineage, and summaries.
    """
    __tablename__ = "conversation_contexts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    thread_id = Column(String(36), ForeignKey("conversation_threads.id"), nullable=False, index=True)
    intent = Column(Text, nullable=True)
    code_references = Column(JSONB, nullable=True)
    generation_lineage = Column(JSONB, nullable=True)
    summary = Column(Text, nullable=True)
    last_updated = Column(DateTime, default=func.now(), nullable=False, index=True)
    context_metadata = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    thread = relationship("ConversationThread", back_populates="contexts")

    def __init__(self, **kwargs):
        """Initialize ConversationContext with auto-generated UUID."""
        if 'id' not in kwargs:
            kwargs['id'] = str(uuid.uuid4())
        super().__init__(**kwargs)

    def __repr__(self):
        return f"<ConversationContext {self.id} for thread {self.thread_id}>"


class ClarificationRequest(Base):
    """
    ClarificationRequest model for storing clarification requests to users.

    Tracks questions asked to users and their responses.
    """
    __tablename__ = "clarification_requests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    thread_id = Column(String(36), ForeignKey("conversation_threads.id"), nullable=False, index=True)
    request_data = Column(JSONB, nullable=False)  # Stores questions, context, etc.
    status = Column(String(50), nullable=False, default="pending")  # pending, answered, expired
    created_at = Column(DateTime, default=func.now(), nullable=False, index=True)
    answered_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    thread = relationship("ConversationThread", back_populates="clarification_requests")

    def __init__(self, **kwargs):
        """Initialize ClarificationRequest with auto-generated UUID."""
        if 'id' not in kwargs:
            kwargs['id'] = str(uuid.uuid4())
        super().__init__(**kwargs)

    def __repr__(self):
        return f"<ClarificationRequest {self.id} ({self.status})>"

    @property
    def is_pending(self) -> bool:
        """Check if request is pending."""
        return self.status == "pending"

    @property
    def is_answered(self) -> bool:
        """Check if request has been answered."""
        return self.status == "answered"

    @property
    def is_expired(self) -> bool:
        """Check if request has expired."""
        return self.status == "expired"


class GenerationLineage(Base):
    """
    GenerationLineage model for tracking AI code generation lineage.

    Records prompts, responses, models used, and generation metadata.
    """
    __tablename__ = "generation_lineage"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    thread_id = Column(String(36), ForeignKey("conversation_threads.id"), nullable=False, index=True)
    generation_id = Column(String(36), nullable=False, index=True)
    prompt = Column(Text, nullable=False)
    response = Column(Text, nullable=True)
    model_used = Column(String(100), nullable=False)
    tokens_used = Column(Integer, nullable=True)
    processing_time_ms = Column(Integer, nullable=True)
    success = Column(Boolean, nullable=False, default=False)
    error_message = Column(Text, nullable=True)
    generation_metadata = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    thread = relationship("ConversationThread", back_populates="generation_lineage")

    def __init__(self, **kwargs):
        """Initialize GenerationLineage with auto-generated UUID."""
        if 'id' not in kwargs:
            kwargs['id'] = str(uuid.uuid4())
        super().__init__(**kwargs)

    def __repr__(self):
        return f"<GenerationLineage {self.id} ({'success' if self.success else 'failed'})>"