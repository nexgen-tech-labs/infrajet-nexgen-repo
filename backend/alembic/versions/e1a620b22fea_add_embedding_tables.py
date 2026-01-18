"""Add embedding tables

Revision ID: e1a620b22fea
Revises: 
Create Date: 2025-09-05 15:09:38.655966

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e1a620b22fea"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column(
            "role",
            sa.Enum("USER", "ADMIN", "SUPERUSER", name="userrole"),
            nullable=False,
        ),
        sa.Column("email_verified", sa.DateTime(), nullable=True),
        sa.Column("last_login", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_full_name"), "users", ["full_name"], unique=False)
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)

    # Create refresh_tokens table
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_refresh_tokens_id"), "refresh_tokens", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_refresh_tokens_token"), "refresh_tokens", ["token"], unique=True
    )

    # Create repositories table
    op.create_table(
        "repositories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("branch", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_repositories_name", "repositories", ["name"], unique=False)
    op.create_index(op.f("ix_repositories_id"), "repositories", ["id"], unique=False)
    op.create_index(
        op.f("ix_repositories_name"), "repositories", ["name"], unique=False
    )

    # Create file_embeddings table
    op.create_table(
        "file_embeddings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(length=1000), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_extension", sa.String(length=10), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("file_hash", sa.String(length=64), nullable=True),
        sa.Column("repository_id", sa.Integer(), nullable=False),
        sa.Column("content_chunk", sa.Text(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("total_chunks", sa.Integer(), nullable=False),
        sa.Column("embedding_vector", sa.ARRAY(sa.Float()), nullable=False),
        sa.Column("embedding_model", sa.String(length=100), nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(length=50), nullable=True),
        sa.Column("tokens_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["repository_id"],
            ["repositories.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_file_embeddings_hash", "file_embeddings", ["file_hash"], unique=False
    )
    op.create_index(
        "idx_file_embeddings_repo_path",
        "file_embeddings",
        ["repository_id", "file_path"],
        unique=False,
    )
    op.create_index(
        op.f("ix_file_embeddings_file_extension"),
        "file_embeddings",
        ["file_extension"],
        unique=False,
    )
    op.create_index(
        op.f("ix_file_embeddings_file_hash"),
        "file_embeddings",
        ["file_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_file_embeddings_file_name"),
        "file_embeddings",
        ["file_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_file_embeddings_file_path"),
        "file_embeddings",
        ["file_path"],
        unique=False,
    )
    op.create_index(
        op.f("ix_file_embeddings_id"), "file_embeddings", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_file_embeddings_repository_id"),
        "file_embeddings",
        ["repository_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_file_embeddings_repository_id"), table_name="file_embeddings"
    )
    op.drop_index(op.f("ix_file_embeddings_id"), table_name="file_embeddings")
    op.drop_index(op.f("ix_file_embeddings_file_path"), table_name="file_embeddings")
    op.drop_index(op.f("ix_file_embeddings_file_name"), table_name="file_embeddings")
    op.drop_index(op.f("ix_file_embeddings_file_hash"), table_name="file_embeddings")
    op.drop_index(
        op.f("ix_file_embeddings_file_extension"), table_name="file_embeddings"
    )
    op.drop_index("idx_file_embeddings_repo_path", table_name="file_embeddings")
    op.drop_index("idx_file_embeddings_hash", table_name="file_embeddings")
    op.drop_table("file_embeddings")

    op.drop_index(op.f("ix_repositories_name"), table_name="repositories")
    op.drop_index(op.f("ix_repositories_id"), table_name="repositories")
    op.drop_index("idx_repositories_name", table_name="repositories")
    op.drop_table("repositories")

    op.drop_index(op.f("ix_refresh_tokens_token"), table_name="refresh_tokens")
    op.drop_index(op.f("ix_refresh_tokens_id"), table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_index(op.f("ix_users_full_name"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

    # Drop the enum type
    op.execute("DROP TYPE IF EXISTS userrole")
