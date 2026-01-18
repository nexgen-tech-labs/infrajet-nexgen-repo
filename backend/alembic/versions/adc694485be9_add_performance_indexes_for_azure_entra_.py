"""add_performance_indexes_for_azure_entra_features

Revision ID: adc694485be9
Revises: 0b70656934f4
Create Date: 2025-09-23 23:41:04.603688

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "adc694485be9"
down_revision: Union[str, Sequence[str], None] = "0b70656934f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add performance indexes for Azure Entra features

    # Users table indexes for Azure Entra authentication
    op.create_index(
        "ix_users_azure_tenant_id", "users", ["azure_tenant_id"], unique=False
    )
    op.create_index(
        "ix_users_azure_token_expires_at",
        "users",
        ["azure_token_expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_users_github_username", "users", ["github_username"], unique=False
    )
    op.create_index("ix_users_last_login", "users", ["last_login"], unique=False)
    op.create_index("ix_users_organization", "users", ["organization"], unique=False)

    # Composite indexes for common query patterns
    op.create_index(
        "ix_users_active_azure", "users", ["is_active", "azure_entra_id"], unique=False
    )
    op.create_index(
        "ix_users_github_connected",
        "users",
        ["github_username", "github_connected_at"],
        unique=False,
    )

    # GitHub sync records indexes for performance
    op.create_index(
        "ix_github_sync_records_sync_status",
        "github_sync_records",
        ["sync_status"],
        unique=False,
    )
    op.create_index(
        "ix_github_sync_records_last_sync_at",
        "github_sync_records",
        ["last_sync_at"],
        unique=False,
    )
    op.create_index(
        "ix_github_sync_records_user_project",
        "github_sync_records",
        ["user_id", "project_id"],
        unique=False,
    )
    op.create_index(
        "ix_github_sync_records_repository",
        "github_sync_records",
        ["github_repository"],
        unique=False,
    )
    op.create_index(
        "ix_github_sync_records_branch",
        "github_sync_records",
        ["branch_name"],
        unique=False,
    )

    # WebSocket sessions indexes for real-time features
    op.create_index(
        "ix_websocket_sessions_user_active",
        "websocket_sessions",
        ["user_id", "is_active"],
        unique=False,
    )
    op.create_index(
        "ix_websocket_sessions_last_heartbeat",
        "websocket_sessions",
        ["last_heartbeat"],
        unique=False,
    )
    op.create_index(
        "ix_websocket_sessions_connected_at",
        "websocket_sessions",
        ["connected_at"],
        unique=False,
    )

    # User preferences indexes
    op.create_index(
        "ix_user_preferences_user_id", "user_preferences", ["user_id"], unique=False
    )

    # Project-related indexes for better performance
    op.create_index("ix_projects_created_at", "projects", ["created_at"], unique=False)
    op.create_index("ix_projects_updated_at", "projects", ["updated_at"], unique=False)
    op.create_index(
        "ix_projects_user_status", "projects", ["user_id", "status"], unique=False
    )

    # Code generation indexes
    op.create_index(
        "ix_code_generations_created_at",
        "code_generations",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_code_generations_updated_at",
        "code_generations",
        ["updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_code_generations_user_status",
        "code_generations",
        ["user_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_code_generations_project_status",
        "code_generations",
        ["project_id", "status"],
        unique=False,
    )

    # Project files indexes
    op.create_index(
        "ix_project_files_file_type", "project_files", ["file_type"], unique=False
    )
    op.create_index(
        "ix_project_files_created_at", "project_files", ["created_at"], unique=False
    )
    op.create_index(
        "ix_project_files_content_hash", "project_files", ["content_hash"], unique=False
    )

    # Generated files indexes
    op.create_index(
        "ix_generated_files_created_at", "generated_files", ["created_at"], unique=False
    )

    # Refresh tokens indexes
    op.create_index(
        "ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"], unique=False
    )
    op.create_index(
        "ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop performance indexes for Azure Entra features

    # Users table indexes
    op.drop_index("ix_users_azure_tenant_id", table_name="users")
    op.drop_index("ix_users_azure_token_expires_at", table_name="users")
    op.drop_index("ix_users_github_username", table_name="users")
    op.drop_index("ix_users_last_login", table_name="users")
    op.drop_index("ix_users_organization", table_name="users")
    op.drop_index("ix_users_active_azure", table_name="users")
    op.drop_index("ix_users_github_connected", table_name="users")

    # GitHub sync records indexes
    op.drop_index(
        "ix_github_sync_records_sync_status", table_name="github_sync_records"
    )
    op.drop_index(
        "ix_github_sync_records_last_sync_at", table_name="github_sync_records"
    )
    op.drop_index(
        "ix_github_sync_records_user_project", table_name="github_sync_records"
    )
    op.drop_index("ix_github_sync_records_repository", table_name="github_sync_records")
    op.drop_index("ix_github_sync_records_branch", table_name="github_sync_records")

    # WebSocket sessions indexes
    op.drop_index("ix_websocket_sessions_user_active", table_name="websocket_sessions")
    op.drop_index(
        "ix_websocket_sessions_last_heartbeat", table_name="websocket_sessions"
    )
    op.drop_index("ix_websocket_sessions_connected_at", table_name="websocket_sessions")

    # User preferences indexes
    op.drop_index("ix_user_preferences_user_id", table_name="user_preferences")

    # Project-related indexes
    op.drop_index("ix_projects_created_at", table_name="projects")
    op.drop_index("ix_projects_updated_at", table_name="projects")
    op.drop_index("ix_projects_user_status", table_name="projects")

    # Code generation indexes
    op.drop_index("ix_code_generations_created_at", table_name="code_generations")
    op.drop_index("ix_code_generations_updated_at", table_name="code_generations")
    op.drop_index("ix_code_generations_user_status", table_name="code_generations")
    op.drop_index("ix_code_generations_project_status", table_name="code_generations")

    # Project files indexes
    op.drop_index("ix_project_files_file_type", table_name="project_files")
    op.drop_index("ix_project_files_created_at", table_name="project_files")
    op.drop_index("ix_project_files_content_hash", table_name="project_files")

    # Generated files indexes
    op.drop_index("ix_generated_files_created_at", table_name="generated_files")

    # Refresh tokens indexes
    op.drop_index("ix_refresh_tokens_expires_at", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
