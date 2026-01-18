"""Add project management tables

Revision ID: f8c9d2e1a4b7
Revises: e1a620b22fea
Create Date: 2025-01-17 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f8c9d2e1a4b7"
down_revision: Union[str, Sequence[str], None] = "e1a620b22fea"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    
    # Create ProjectStatus enum
    op.execute("CREATE TYPE projectstatus AS ENUM ('active', 'archived', 'deleted')")
    
    # Create GenerationStatus enum
    op.execute("CREATE TYPE generationstatus AS ENUM ('pending', 'in_progress', 'completed', 'failed', 'cancelled')")
    
    # Create projects table
    op.create_table(
        "projects",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.Enum("active", "archived", "deleted", name="projectstatus"), nullable=False),
        sa.Column("azure_folder_path", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index(op.f("ix_projects_id"), "projects", ["id"], unique=False)
    op.create_index(op.f("ix_projects_name"), "projects", ["name"], unique=False)
    op.create_index(op.f("ix_projects_user_id"), "projects", ["user_id"], unique=False)
    op.create_index(op.f("ix_projects_status"), "projects", ["status"], unique=False)

    # Create project_files table
    op.create_table(
        "project_files",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("azure_path", sa.String(1000), nullable=False),
        sa.Column("file_type", sa.String(10), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "file_path", name="uq_project_files_project_path"),
    )
    op.create_index(op.f("ix_project_files_id"), "project_files", ["id"], unique=False)
    op.create_index(op.f("ix_project_files_project_id"), "project_files", ["project_id"], unique=False)

    # Create code_generations table
    op.create_table(
        "code_generations",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("scenario", sa.String(50), nullable=False),
        sa.Column("status", sa.Enum("pending", "in_progress", "completed", "failed", "cancelled", name="generationstatus"), nullable=False),
        sa.Column("generation_hash", sa.String(64), nullable=False),
        sa.Column("provider_type", sa.String(50), nullable=True),
        sa.Column("temperature", sa.String(10), nullable=True),
        sa.Column("max_tokens", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index(op.f("ix_code_generations_id"), "code_generations", ["id"], unique=False)
    op.create_index(op.f("ix_code_generations_project_id"), "code_generations", ["project_id"], unique=False)
    op.create_index(op.f("ix_code_generations_user_id"), "code_generations", ["user_id"], unique=False)
    op.create_index(op.f("ix_code_generations_status"), "code_generations", ["status"], unique=False)
    op.create_index(op.f("ix_code_generations_generation_hash"), "code_generations", ["generation_hash"], unique=False)

    # Create generated_files table (junction table)
    op.create_table(
        "generated_files",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("generation_id", sa.String(36), nullable=False),
        sa.Column("project_file_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["generation_id"], ["code_generations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_file_id"], ["project_files.id"]),
    )
    op.create_index(op.f("ix_generated_files_id"), "generated_files", ["id"], unique=False)
    op.create_index(op.f("ix_generated_files_generation_id"), "generated_files", ["generation_id"], unique=False)
    op.create_index(op.f("ix_generated_files_project_file_id"), "generated_files", ["project_file_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    
    # Drop generated_files table
    op.drop_index(op.f("ix_generated_files_project_file_id"), table_name="generated_files")
    op.drop_index(op.f("ix_generated_files_generation_id"), table_name="generated_files")
    op.drop_index(op.f("ix_generated_files_id"), table_name="generated_files")
    op.drop_table("generated_files")

    # Drop code_generations table
    op.drop_index(op.f("ix_code_generations_generation_hash"), table_name="code_generations")
    op.drop_index(op.f("ix_code_generations_status"), table_name="code_generations")
    op.drop_index(op.f("ix_code_generations_user_id"), table_name="code_generations")
    op.drop_index(op.f("ix_code_generations_project_id"), table_name="code_generations")
    op.drop_index(op.f("ix_code_generations_id"), table_name="code_generations")
    op.drop_table("code_generations")

    # Drop project_files table
    op.drop_index(op.f("ix_project_files_project_id"), table_name="project_files")
    op.drop_index(op.f("ix_project_files_id"), table_name="project_files")
    op.drop_table("project_files")

    # Drop projects table
    op.drop_index(op.f("ix_projects_status"), table_name="projects")
    op.drop_index(op.f("ix_projects_user_id"), table_name="projects")
    op.drop_index(op.f("ix_projects_name"), table_name="projects")
    op.drop_index(op.f("ix_projects_id"), table_name="projects")
    op.drop_table("projects")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS generationstatus")
    op.execute("DROP TYPE IF EXISTS projectstatus")