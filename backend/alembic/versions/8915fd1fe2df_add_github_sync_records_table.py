"""add_github_sync_records_table

Revision ID: 8915fd1fe2df
Revises: 1fe8ca7c007a
Create Date: 2025-09-23 13:59:05.376095

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8915fd1fe2df'
down_revision: Union[str, Sequence[str], None] = '1fe8ca7c007a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create github_sync_records table
    op.create_table(
        'github_sync_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.String(36), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('github_repository', sa.String(255), nullable=False),
        sa.Column('last_sync_at', sa.DateTime(), nullable=True),
        sa.Column('sync_status', sa.String(50), nullable=False, default='pending'),
        sa.Column('last_commit_sha', sa.String(40), nullable=True),
        sa.Column('sync_errors', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        # sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),  # Will add this later
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.UniqueConstraint('project_id', 'github_repository', name='uq_github_sync_project_repo')
    )
    op.create_index('ix_github_sync_records_id', 'github_sync_records', ['id'], unique=False)
    op.create_index('ix_github_sync_records_project_id', 'github_sync_records', ['project_id'], unique=False)
    op.create_index('ix_github_sync_records_user_id', 'github_sync_records', ['user_id'], unique=False)
    op.create_index('ix_github_sync_records_sync_status', 'github_sync_records', ['sync_status'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop github_sync_records table
    op.drop_index('ix_github_sync_records_sync_status', table_name='github_sync_records')
    op.drop_index('ix_github_sync_records_user_id', table_name='github_sync_records')
    op.drop_index('ix_github_sync_records_project_id', table_name='github_sync_records')
    op.drop_index('ix_github_sync_records_id', table_name='github_sync_records')
    op.drop_table('github_sync_records')
