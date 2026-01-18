"""Add GitHub sync enhancements

Revision ID: add_github_sync_enhancements
Revises: 
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_github_sync_enhancements'
down_revision = None  # Update this with the actual previous revision
branch_labels = None
depends_on = None


def upgrade():
    """Add enhanced tracking fields to github_sync_records table."""
    
    # Add new columns to github_sync_records table
    op.add_column('github_sync_records', sa.Column('files_synced_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('github_sync_records', sa.Column('conflicts_resolved_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('github_sync_records', sa.Column('sync_duration_seconds', sa.Integer(), nullable=True))
    op.add_column('github_sync_records', sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('github_sync_records', sa.Column('branch_name', sa.String(length=255), nullable=False, server_default='main'))
    
    # Create indexes for better query performance
    op.create_index('ix_github_sync_records_sync_status', 'github_sync_records', ['sync_status'])
    op.create_index('ix_github_sync_records_last_sync_at', 'github_sync_records', ['last_sync_at'])
    op.create_index('ix_github_sync_records_branch_name', 'github_sync_records', ['branch_name'])
    op.create_index('ix_github_sync_records_user_project', 'github_sync_records', ['user_id', 'project_id'])


def downgrade():
    """Remove enhanced tracking fields from github_sync_records table."""
    
    # Drop indexes
    op.drop_index('ix_github_sync_records_user_project', table_name='github_sync_records')
    op.drop_index('ix_github_sync_records_branch_name', table_name='github_sync_records')
    op.drop_index('ix_github_sync_records_last_sync_at', table_name='github_sync_records')
    op.drop_index('ix_github_sync_records_sync_status', table_name='github_sync_records')
    
    # Drop columns
    op.drop_column('github_sync_records', 'branch_name')
    op.drop_column('github_sync_records', 'retry_count')
    op.drop_column('github_sync_records', 'sync_duration_seconds')
    op.drop_column('github_sync_records', 'conflicts_resolved_count')
    op.drop_column('github_sync_records', 'files_synced_count')