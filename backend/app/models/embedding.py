from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey, Index, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
import uuid

from app.models.base import Base


class Repository(Base):
    """Repository model to store repository information."""

    __tablename__ = "repositories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    url = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    branch = Column(String(100), default="main", nullable=False)

    # Relationships
    files = relationship(
        "FileEmbedding", back_populates="repository", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Repository {self.name}>"


class FileEmbedding(Base):
    """File embedding model to store file embeddings with metadata."""

    __tablename__ = "file_embeddings"

    id = Column(Integer, primary_key=True, index=True)

    # File identification
    file_path = Column(String(1000), nullable=False, index=True)
    file_name = Column(String(255), nullable=False, index=True)
    file_extension = Column(String(10), nullable=True, index=True)
    file_size = Column(Integer, nullable=True)
    file_hash = Column(
        String(64), nullable=True, index=True
    )  # SHA-256 hash for change detection

    # Repository reference
    repository_id = Column(
        Integer, ForeignKey("repositories.id"), nullable=False, index=True
    )

    # Content information
    content_chunk = Column(
        Text, nullable=True
    )  # The actual text chunk that was embedded
    chunk_index = Column(
        Integer, default=0, nullable=False
    )  # For files split into multiple chunks
    total_chunks = Column(Integer, default=1, nullable=False)

    # Embedding data
    embedding_vector = Column(Vector(1536), nullable=False)  # pgvector column
    embedding_model = Column(
        String(100), nullable=False
    )  # Model used to generate embedding
    embedding_dimension = Column(Integer, nullable=False)

    # Dual embedding support
    embedding_type = Column(String(20), default="code", nullable=False)  # 'code' or 'summary'
    summary_text = Column(Text, nullable=True)  # LLM-generated summary
    summary_embedding_vector = Column(Vector(1536), nullable=True)  # Summary embedding
    summary_confidence = Column(Float, nullable=True)  # Confidence score of summary
    summary_type = Column(String(50), nullable=True)  # Type of summary (infrastructure, security, etc.)

    # Processing metadata
    processing_metadata = Column(JSON, nullable=True)  # Additional processing information
    summarization_model = Column(String(100), nullable=True)  # Model used for summarization
    chunk_strategy = Column(String(50), nullable=True)  # Chunking strategy used

    # Metadata
    language = Column(String(50), nullable=True)  # Programming language detected
    tokens_count = Column(Integer, nullable=True)  # Number of tokens in the chunk

    # Relationships
    repository = relationship("Repository", back_populates="files")

    def __repr__(self):
        return f"<FileEmbedding {self.file_path} chunk {self.chunk_index}>"


# Create indexes for better query performance
Index(
    "idx_file_embeddings_repo_path",
    FileEmbedding.repository_id,
    FileEmbedding.file_path,
)
Index("idx_file_embeddings_hash", FileEmbedding.file_hash)
Index("idx_file_embeddings_type", FileEmbedding.embedding_type)
Index("idx_file_embeddings_summary_type", FileEmbedding.summary_type)
Index("idx_file_embeddings_confidence", FileEmbedding.summary_confidence)
Index("idx_repositories_name", Repository.name)

# Composite indexes for common queries
Index(
    "idx_file_embeddings_repo_type",
    FileEmbedding.repository_id,
    FileEmbedding.embedding_type,
)
Index(
    "idx_file_embeddings_repo_path_type",
    FileEmbedding.repository_id,
    FileEmbedding.file_path,
    FileEmbedding.embedding_type,
)
