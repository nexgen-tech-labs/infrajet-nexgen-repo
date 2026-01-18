"""migrate_data_for_github_app_integration

Revision ID: d5e66ae95ca5
Revises: 8554c68dae0b
Create Date: 2025-09-27 18:13:16.727419

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5e66ae95ca5'
down_revision: Union[str, Sequence[str], None] = '8554c68dae0b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Migrate data for GitHub App integration."""
    
    # Create a connection to execute raw SQL
    connection = op.get_bind()
    
    # 1. Migrate existing projects to use supabase_user_id
    # For now, we'll set supabase_user_id to the string representation of user_id
    # In a real migration, you would map existing user IDs to Supabase user IDs
    connection.execute(
        sa.text("UPDATE projects SET supabase_user_id = CAST(user_id AS VARCHAR) WHERE supabase_user_id IS NULL")
    )
    
    # 2. Update existing GitHub sync records to have default values for new fields
    # Set github_repo_id and github_installation_id to NULL for existing records
    # These will need to be populated when users reconnect their GitHub App
    connection.execute(
        sa.text("UPDATE github_sync_records SET github_repo_id = NULL, github_installation_id = NULL WHERE github_repo_id IS NULL")
    )
    
    # 3. Reset GitHub connection status for all users since we're switching to GitHub App
    # Users will need to reconnect using the GitHub App
    connection.execute(
        sa.text("UPDATE users SET github_installation_id = NULL, github_app_id = NULL, github_connected_at = NULL")
    )


def downgrade() -> None:
    """Downgrade data migration."""
    
    # Create a connection to execute raw SQL
    connection = op.get_bind()
    
    # 1. Clear supabase_user_id data
    connection.execute(
        sa.text("UPDATE projects SET supabase_user_id = NULL")
    )
    
    # 2. Clear GitHub App specific data
    connection.execute(
        sa.text("UPDATE github_sync_records SET github_repo_id = NULL, github_installation_id = NULL")
    )
    
    # 3. Clear GitHub App connection data
    connection.execute(
        sa.text("UPDATE users SET github_installation_id = NULL, github_app_id = NULL")
    )
