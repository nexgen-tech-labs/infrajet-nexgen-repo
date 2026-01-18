"""cleanup_index_inconsistencies

Revision ID: 5f409f4af68b
Revises: d5e66ae95ca5
Create Date: 2025-09-27 18:20:54.243326

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5f409f4af68b'
down_revision: Union[str, Sequence[str], None] = 'd5e66ae95ca5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Clean up index inconsistencies."""
    
    # Remove old indexes that are no longer needed or have been replaced
    
    # Code generations indexes
    try:
        op.drop_index('ix_code_generations_created_at', table_name='code_generations')
    except:
        pass
    try:
        op.drop_index('ix_code_generations_project_status', table_name='code_generations')
    except:
        pass
    try:
        op.drop_index('ix_code_generations_updated_at', table_name='code_generations')
    except:
        pass
    try:
        op.drop_index('ix_code_generations_user_status', table_name='code_generations')
    except:
        pass
    
    # Generated files indexes
    try:
        op.drop_index('ix_generated_files_created_at', table_name='generated_files')
    except:
        pass
    
    # GitHub sync records indexes - remove old ones
    try:
        op.drop_index('ix_github_sync_records_branch', table_name='github_sync_records')
    except:
        pass
    try:
        op.drop_index('ix_github_sync_records_installation_id', table_name='github_sync_records')
    except:
        pass
    try:
        op.drop_index('ix_github_sync_records_last_sync_at', table_name='github_sync_records')
    except:
        pass
    try:
        op.drop_index('ix_github_sync_records_repo_id', table_name='github_sync_records')
    except:
        pass
    try:
        op.drop_index('ix_github_sync_records_repository', table_name='github_sync_records')
    except:
        pass
    try:
        op.drop_index('ix_github_sync_records_sync_status', table_name='github_sync_records')
    except:
        pass
    try:
        op.drop_index('ix_github_sync_records_user_project', table_name='github_sync_records')
    except:
        pass
    
    # Project files indexes
    try:
        op.drop_index('ix_project_files_content_hash', table_name='project_files')
    except:
        pass
    try:
        op.drop_index('ix_project_files_created_at', table_name='project_files')
    except:
        pass
    try:
        op.drop_index('ix_project_files_file_type', table_name='project_files')
    except:
        pass
    
    # Projects indexes
    try:
        op.drop_index('ix_projects_created_at', table_name='projects')
    except:
        pass
    try:
        op.drop_index('ix_projects_updated_at', table_name='projects')
    except:
        pass
    try:
        op.drop_index('ix_projects_user_status', table_name='projects')
    except:
        pass
    
    # Refresh tokens indexes
    try:
        op.drop_index('ix_refresh_tokens_expires_at', table_name='refresh_tokens')
    except:
        pass
    try:
        op.drop_index('ix_refresh_tokens_user_id', table_name='refresh_tokens')
    except:
        pass
    
    # User preferences indexes
    try:
        op.drop_index('ix_user_preferences_user_id', table_name='user_preferences')
    except:
        pass
    
    # Users indexes
    try:
        op.drop_index('ix_users_github_username', table_name='users')
    except:
        pass
    try:
        op.drop_index('ix_users_last_login', table_name='users')
    except:
        pass
    try:
        op.drop_index('ix_users_organization', table_name='users')
    except:
        pass
    
    # WebSocket sessions indexes
    try:
        op.drop_index('ix_websocket_sessions_connected_at', table_name='websocket_sessions')
    except:
        pass
    try:
        op.drop_index('ix_websocket_sessions_last_heartbeat', table_name='websocket_sessions')
    except:
        pass
    try:
        op.drop_index('ix_websocket_sessions_user_active', table_name='websocket_sessions')
    except:
        pass


def downgrade() -> None:
    """Downgrade schema."""
    # This migration is for cleanup only, no need to recreate the old indexes
    pass
