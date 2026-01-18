"""update_schema_for_github_app_and_remove_entra_id

Revision ID: 8554c68dae0b
Revises: adc694485be9
Create Date: 2025-09-27 18:11:34.575395

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8554c68dae0b'
down_revision: Union[str, Sequence[str], None] = 'adc694485be9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    
    # 1. Remove Entra ID related columns from users table
    op.drop_index('ix_users_azure_entra_id', table_name='users')
    op.drop_column('users', 'azure_entra_id')
    op.drop_column('users', 'azure_tenant_id')
    op.drop_column('users', 'azure_access_token_hash')
    op.drop_column('users', 'azure_refresh_token_hash')
    op.drop_column('users', 'azure_token_expires_at')
    
    # 2. Update GitHub-related columns in users table for GitHub App integration
    # Remove old GitHub OAuth columns
    op.drop_column('users', 'github_access_token_hash')
    op.drop_column('users', 'github_connected_at')
    
    # Add new GitHub App columns to users table
    op.add_column('users', sa.Column('github_installation_id', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('github_app_id', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('github_connected_at', sa.DateTime(), nullable=True))
    
    # 3. Add GitHub App integration columns to projects table
    op.add_column('projects', sa.Column('github_repo_id', sa.Integer(), nullable=True))
    op.add_column('projects', sa.Column('github_repo_name', sa.String(255), nullable=True))
    op.add_column('projects', sa.Column('github_installation_id', sa.Integer(), nullable=True))
    op.add_column('projects', sa.Column('github_linked', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('projects', sa.Column('last_github_sync', sa.DateTime(), nullable=True))
    
    # 4. Update user_id column in projects table to support Supabase user IDs (String instead of Integer)
    # First, add the new column
    op.add_column('projects', sa.Column('supabase_user_id', sa.String(255), nullable=True))
    
    # Create indexes for new columns
    op.create_index('ix_projects_github_repo_id', 'projects', ['github_repo_id'])
    op.create_index('ix_projects_github_installation_id', 'projects', ['github_installation_id'])
    op.create_index('ix_projects_supabase_user_id', 'projects', ['supabase_user_id'])
    op.create_index('ix_users_github_installation_id', 'users', ['github_installation_id'])
    
    # 5. Update GitHubSyncRecord table to support GitHub App
    op.add_column('github_sync_records', sa.Column('github_installation_id', sa.Integer(), nullable=True))
    op.add_column('github_sync_records', sa.Column('github_repo_id', sa.Integer(), nullable=True))
    op.create_index('ix_github_sync_records_installation_id', 'github_sync_records', ['github_installation_id'])
    op.create_index('ix_github_sync_records_repo_id', 'github_sync_records', ['github_repo_id'])


def downgrade() -> None:
    """Downgrade schema."""
    
    # Drop new indexes
    op.drop_index('ix_github_sync_records_repo_id', table_name='github_sync_records')
    op.drop_index('ix_github_sync_records_installation_id', table_name='github_sync_records')
    op.drop_index('ix_users_github_installation_id', table_name='users')
    op.drop_index('ix_projects_supabase_user_id', table_name='projects')
    op.drop_index('ix_projects_github_installation_id', table_name='projects')
    op.drop_index('ix_projects_github_repo_id', table_name='projects')
    
    # Remove GitHub App columns from github_sync_records
    op.drop_column('github_sync_records', 'github_repo_id')
    op.drop_column('github_sync_records', 'github_installation_id')
    
    # Remove GitHub App columns from projects table
    op.drop_column('projects', 'last_github_sync')
    op.drop_column('projects', 'github_linked')
    op.drop_column('projects', 'github_installation_id')
    op.drop_column('projects', 'github_repo_name')
    op.drop_column('projects', 'github_repo_id')
    op.drop_column('projects', 'supabase_user_id')
    
    # Remove GitHub App columns from users table
    op.drop_column('users', 'github_connected_at')
    op.drop_column('users', 'github_app_id')
    op.drop_column('users', 'github_installation_id')
    
    # Restore old GitHub OAuth columns
    op.add_column('users', sa.Column('github_access_token_hash', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('github_connected_at', sa.DateTime(), nullable=True))
    
    # Restore Entra ID columns
    op.add_column('users', sa.Column('azure_token_expires_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('azure_refresh_token_hash', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('azure_access_token_hash', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('azure_tenant_id', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('azure_entra_id', sa.String(255), nullable=True))
    op.create_index('ix_users_azure_entra_id', 'users', ['azure_entra_id'], unique=True)
