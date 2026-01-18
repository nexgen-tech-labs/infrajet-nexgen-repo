"""Enable pgvector extension and convert embedding vectors

Revision ID: 963e787ba7e8
Revises: e1a620b22fea
Create Date: 2025-09-06 12:23:08.241452

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = "963e787ba7e8"
down_revision: Union[str, Sequence[str], None] = "e1a620b22fea"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Convert embedding_vector column from ARRAY to Vector type
    # First, create a temporary column with Vector type
    op.add_column(
        "file_embeddings",
        sa.Column("embedding_vector_new", Vector(1536), nullable=True),
    )

    # Copy data from old column to new column
    op.execute(
        """
        UPDATE file_embeddings 
        SET embedding_vector_new = embedding_vector::vector(1536)
        WHERE embedding_vector IS NOT NULL
    """
    )

    # Drop the old column
    op.drop_column("file_embeddings", "embedding_vector")

    # Rename the new column
    op.alter_column(
        "file_embeddings", "embedding_vector_new", new_column_name="embedding_vector"
    )

    # Make the column NOT NULL
    op.alter_column("file_embeddings", "embedding_vector", nullable=False)

    # Create an index for vector similarity search (using cosine distance)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_file_embeddings_vector_cosine ON file_embeddings USING ivfflat (embedding_vector vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the vector index
    op.execute("DROP INDEX IF EXISTS idx_file_embeddings_vector_cosine")

    # Convert Vector column back to ARRAY
    op.add_column(
        "file_embeddings",
        sa.Column("embedding_vector_new", sa.ARRAY(sa.Float()), nullable=True),
    )

    # Copy data back
    op.execute(
        """
        UPDATE file_embeddings 
        SET embedding_vector_new = embedding_vector::float[]
        WHERE embedding_vector IS NOT NULL
    """
    )

    # Drop the vector column
    op.drop_column("file_embeddings", "embedding_vector")

    # Rename back
    op.alter_column(
        "file_embeddings", "embedding_vector_new", new_column_name="embedding_vector"
    )

    # Make NOT NULL
    op.alter_column("file_embeddings", "embedding_vector", nullable=False)

    # Drop the extension (be careful with this in production)
    op.execute("DROP EXTENSION IF EXISTS vector")
