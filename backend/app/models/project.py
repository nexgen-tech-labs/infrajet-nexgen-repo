import enum
import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, String, Integer, ForeignKey, Enum, Text, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base


class ProjectStatus(str, enum.Enum):
    """Enum for project status values."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class Project(Base):
    """
    Project model for organizing generated code into projects.
    Each project has a unique UUID and belongs to a user.
    """
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    user_id = Column(String(36), nullable=False, index=True)  # Supabase UUID - removed FK constraint for Supabase integration
    supabase_user_id = Column(String(255), nullable=True, index=True)  # For Supabase user association (deprecated, use user_id)
    status = Column(Enum(ProjectStatus), default=ProjectStatus.ACTIVE, nullable=False, index=True)
    azure_folder_path = Column(String(500), nullable=False)
    
    # GitHub App integration fields
    github_repo_id = Column(Integer, nullable=True, index=True)
    github_repo_name = Column(String(255), nullable=True)
    github_installation_id = Column(Integer, nullable=True, index=True)
    github_linked = Column(Boolean, default=False, nullable=False)
    last_github_sync = Column(DateTime, nullable=True)

    # Relationships
    # Note: user relationship removed since users are managed in Supabase
    files = relationship("ProjectFile", back_populates="project", cascade="all, delete-orphan")
    generations = relationship("CodeGeneration", back_populates="project", cascade="all, delete-orphan")
    github_sync_records = relationship("GitHubSyncRecord", back_populates="project", cascade="all, delete-orphan")
    chats = relationship("ProjectChat", back_populates="project", cascade="all, delete-orphan")
    conversation_threads = relationship("ConversationThread", back_populates="project", cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        """Initialize project with auto-generated UUID and Azure folder path."""
        if 'id' not in kwargs:
            kwargs['id'] = str(uuid.uuid4())
        if 'azure_folder_path' not in kwargs and 'id' in kwargs:
            kwargs['azure_folder_path'] = f"projects/{kwargs['id']}"
        super().__init__(**kwargs)

    def __repr__(self):
        return f"<Project {self.name} ({self.id})>"

    @property
    def is_active(self) -> bool:
        """Check if project is active."""
        return self.status == ProjectStatus.ACTIVE

    @property
    def is_archived(self) -> bool:
        """Check if project is archived."""
        return self.status == ProjectStatus.ARCHIVED

    @property
    def is_deleted(self) -> bool:
        """Check if project is deleted."""
        return self.status == ProjectStatus.DELETED

    @property
    def is_github_linked(self) -> bool:
        """Check if project is linked to GitHub."""
        return self.github_linked and self.github_repo_id is not None

    def link_to_github(self, repo_id: int, repo_name: str, installation_id: int) -> None:
        """Link project to GitHub repository."""
        self.github_repo_id = repo_id
        self.github_repo_name = repo_name
        self.github_installation_id = installation_id
        self.github_linked = True

    def unlink_from_github(self) -> None:
        """Unlink project from GitHub repository."""
        self.github_repo_id = None
        self.github_repo_name = None
        self.github_installation_id = None
        self.github_linked = False
        self.last_github_sync = None

    def update_github_sync(self) -> None:
        """Update last GitHub sync timestamp."""
        from sqlalchemy.sql import func
        self.last_github_sync = func.now()


class ProjectFile(Base):
    """
    ProjectFile model for tracking file metadata in projects.
    Stores information about files stored in Azure File Share.
    """
    __tablename__ = "project_files"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    file_path = Column(String(500), nullable=False)  # Relative path within project
    azure_path = Column(String(1000), nullable=False)  # Full Azure File Share path
    file_type = Column(String(10), nullable=False)  # .tf, .tfvars, etc.
    size_bytes = Column(Integer, nullable=False, default=0)
    content_hash = Column(String(64), nullable=False)  # SHA-256 hash

    # Relationships
    project = relationship("Project", back_populates="files")

    def __init__(self, **kwargs):
        """Initialize ProjectFile with computed azure_path if not provided."""
        if 'azure_path' not in kwargs and 'project_id' in kwargs and 'file_path' in kwargs:
            kwargs['azure_path'] = f"projects/{kwargs['project_id']}/{kwargs['file_path']}"
        super().__init__(**kwargs)

    def __repr__(self):
        return f"<ProjectFile {self.file_path} ({self.project_id})>"

    @property
    def file_extension(self) -> str:
        """Get file extension from file_path."""
        if '.' not in self.file_path:
            return ''
        return self.file_path.split('.')[-1]

    @property
    def is_terraform_file(self) -> bool:
        """Check if file is a Terraform file."""
        return self.file_type in ['.tf', '.tfvars', '.tfstate']

    def validate_file_path(self) -> bool:
        """Validate that file_path is safe and doesn't contain path traversal."""
        import os
        # Normalize the path and check for path traversal attempts
        normalized = os.path.normpath(self.file_path)
        return not (
            normalized.startswith('/') or 
            normalized.startswith('..') or 
            '/../' in normalized or
            normalized == '..'
        )

    def update_content_hash(self, content: str) -> None:
        """Update content hash based on file content."""
        import hashlib
        self.content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        self.size_bytes = len(content.encode('utf-8'))


class GenerationStatus(str, enum.Enum):
    """Enum for code generation status values."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CodeGeneration(Base):
    """
    CodeGeneration model for tracking code generation requests and their results.
    Links projects with specific generation jobs and organizes files by generation.
    """
    __tablename__ = "code_generations"

    id = Column(String(36), primary_key=True, index=True)  # job_id from generation system
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)  # Supabase UUID - removed FK constraint for Supabase integration
    query = Column(Text, nullable=False)  # Original user query
    scenario = Column(String(50), nullable=False)  # Generation scenario
    status = Column(Enum(GenerationStatus), default=GenerationStatus.PENDING, nullable=False, index=True)
    generation_hash = Column(String(64), nullable=False, index=True)  # For folder organization
    
    # Optional fields for additional context
    provider_type = Column(String(50), nullable=True)  # LLM provider used
    temperature = Column(String(10), nullable=True)  # Generation temperature
    max_tokens = Column(Integer, nullable=True)  # Max tokens used
    error_message = Column(Text, nullable=True)  # Error details if failed

    # Relationships
    project = relationship("Project", back_populates="generations")
    # Note: user relationship removed since users are managed in Supabase
    files = relationship("GeneratedFile", back_populates="generation", cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        """Initialize CodeGeneration with computed generation_hash if not provided."""
        if 'generation_hash' not in kwargs:
            kwargs['generation_hash'] = self._compute_generation_hash(
                kwargs.get('query', ''),
                kwargs.get('scenario', ''),
                kwargs.get('id', '')
            )
        super().__init__(**kwargs)

    def __repr__(self):
        return f"<CodeGeneration {self.id} ({self.status})>"

    @staticmethod
    def _compute_generation_hash(query: str, scenario: str, job_id: str) -> str:
        """Compute a hash for organizing generation folders."""
        import hashlib
        from datetime import datetime
        
        # Combine query, scenario, job_id and timestamp for uniqueness
        content = f"{query}:{scenario}:{job_id}:{datetime.utcnow().isoformat()}"
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]  # Use first 16 chars

    @property
    def is_pending(self) -> bool:
        """Check if generation is pending."""
        return self.status == GenerationStatus.PENDING

    @property
    def is_in_progress(self) -> bool:
        """Check if generation is in progress."""
        return self.status == GenerationStatus.IN_PROGRESS

    @property
    def is_completed(self) -> bool:
        """Check if generation is completed."""
        return self.status == GenerationStatus.COMPLETED

    @property
    def is_failed(self) -> bool:
        """Check if generation failed."""
        return self.status == GenerationStatus.FAILED

    @property
    def is_cancelled(self) -> bool:
        """Check if generation was cancelled."""
        return self.status == GenerationStatus.CANCELLED

    @property
    def folder_path(self) -> str:
        """Get the folder path for this generation in Azure File Share."""
        return f"projects/{self.project_id}/{self.generation_hash}"

    def mark_as_started(self) -> None:
        """Mark generation as started."""
        self.status = GenerationStatus.IN_PROGRESS

    def mark_as_completed(self) -> None:
        """Mark generation as completed."""
        self.status = GenerationStatus.COMPLETED

    def mark_as_failed(self, error_message: str = None) -> None:
        """Mark generation as failed with optional error message."""
        self.status = GenerationStatus.FAILED
        if error_message:
            self.error_message = error_message

    def mark_as_cancelled(self) -> None:
        """Mark generation as cancelled."""
        self.status = GenerationStatus.CANCELLED


class GeneratedFile(Base):
    """
    GeneratedFile model for linking generated files to specific code generations.
    This creates a many-to-many relationship between generations and project files.
    """
    __tablename__ = "generated_files"

    id = Column(Integer, primary_key=True, index=True)
    generation_id = Column(String(36), ForeignKey("code_generations.id"), nullable=False, index=True)
    project_file_id = Column(Integer, ForeignKey("project_files.id"), nullable=False, index=True)

    # Relationships
    generation = relationship("CodeGeneration", back_populates="files")
    project_file = relationship("ProjectFile")

    def __repr__(self):
        return f"<GeneratedFile gen:{self.generation_id} file:{self.project_file_id}>"