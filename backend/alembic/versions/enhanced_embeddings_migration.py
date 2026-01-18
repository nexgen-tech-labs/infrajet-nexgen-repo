"""
Add dual embeddings support with LLM summarization

Revision ID: enhanced_embeddings
Revises: e1a620b22fea
Create Date: 2025-01-07 12:05:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = 'enhanced_embeddings'
down_revision = 'e1a620b22fea'
branch_labels = None
depends_on = None


def upgrade():
    """Add new columns for dual embeddings support."""

    # Enable pgvector extension (required for Vector type)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Add new columns to file_embeddings table
    op.add_column('file_embeddings', sa.Column('embedding_type', sa.String(20), nullable=False, server_default='code'))
    op.add_column('file_embeddings', sa.Column('summary_text', sa.Text(), nullable=True))

    # Use raw SQL for vector column to ensure extension is available
    op.execute("ALTER TABLE file_embeddings ADD COLUMN summary_embedding_vector vector(1536)")
    op.add_column('file_embeddings', sa.Column('summary_confidence', sa.Float(), nullable=True))
    op.add_column('file_embeddings', sa.Column('summary_type', sa.String(50), nullable=True))
    op.add_column('file_embeddings', sa.Column('processing_metadata', postgresql.JSON(), nullable=True))
    op.add_column('file_embeddings', sa.Column('summarization_model', sa.String(100), nullable=True))
    op.add_column('file_embeddings', sa.Column('chunk_strategy', sa.String(50), nullable=True))

    # Create indexes for better query performance
    op.create_index('idx_file_embeddings_type', 'file_embeddings', ['embedding_type'])
    op.create_index('idx_file_embeddings_summary_type', 'file_embeddings', ['summary_type'])
    op.create_index('idx_file_embeddings_confidence', 'file_embeddings', ['summary_confidence'])
    op.create_index('idx_file_embeddings_repo_type', 'file_embeddings', ['repository_id', 'embedding_type'])
    op.create_index('idx_file_embeddings_repo_path_type', 'file_embeddings', ['repository_id', 'file_path', 'embedding_type'])

    # Update existing records to have embedding_type = 'code'
    op.execute("UPDATE file_embeddings SET embedding_type = 'code' WHERE embedding_type IS NULL")


def downgrade():
    """Remove dual embeddings support columns."""

    # Drop indexes
    op.drop_index('idx_file_embeddings_repo_path_type')
    op.drop_index('idx_file_embeddings_repo_type')
    op.drop_index('idx_file_embeddings_confidence')
    op.drop_index('idx_file_embeddings_summary_type')
    op.drop_index('idx_file_embeddings_type')

    # Drop columns
    op.drop_column('file_embeddings', 'chunk_strategy')
    op.drop_column('file_embeddings', 'summarization_model')
    op.drop_column('file_embeddings', 'processing_metadata')
    op.drop_column('file_embeddings', 'summary_type')
    op.drop_column('file_embeddings', 'summary_confidence')
    op.drop_column('file_embeddings', 'summary_embedding_vector')
    op.drop_column('file_embeddings', 'summary_text')
    op.drop_column('file_embeddings', 'embedding_type')