"""add_missing_github_sync_indexes

Revision ID: 6ee568782e2c
Revises: 5f409f4af68b
Create Date: 2025-09-27 18:22:25.379496

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6ee568782e2c'
down_revision: Union[str, Sequence[str], None] = '5f409f4af68b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add missing GitHub sync indexes."""
    
    # Add the missing indexes for GitHub App integration
    try:
        op.create_index('ix_github_sync_records_github_installation_id', 'github_sync_records', ['github_installation_id'])
    except:
        pass  # Index might already exist
    
    try:
        op.create_index('ix_github_sync_records_github_repo_id', 'github_sync_records', ['github_repo_id'])
    except:
        pass  # Index might already exist


def downgrade() -> None:
    """Downgrade schema."""
    
    # Drop the GitHub sync indexes
    try:
        op.drop_index('ix_github_sync_records_github_repo_id', table_name='github_sync_records')
    except:
        pass
    
    try:
        op.drop_index('ix_github_sync_records_github_installation_id', table_name='github_sync_records')
    except:
        pass
