"""add_azure_entra_fields_to_users

Revision ID: 1fe8ca7c007a
Revises: eb7a60e7f763
Create Date: 2025-09-23 13:58:34.382822

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1fe8ca7c007a'
down_revision: Union[str, Sequence[str], None] = 'eb7a60e7f763'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add Azure Entra ID fields
    op.add_column('users', sa.Column('azure_entra_id', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('azure_tenant_id', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('azure_access_token_hash', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('azure_refresh_token_hash', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('azure_token_expires_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('profile_picture_url', sa.String(500), nullable=True))
    op.add_column('users', sa.Column('organization', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('department', sa.String(255), nullable=True))
    
    # Add GitHub integration fields
    op.add_column('users', sa.Column('github_username', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('github_access_token_hash', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('github_connected_at', sa.DateTime(), nullable=True))
    
    # Create unique index for azure_entra_id
    op.create_index('ix_users_azure_entra_id', 'users', ['azure_entra_id'], unique=True)
    
    # Remove password-based authentication field
    op.drop_column('users', 'hashed_password')


def downgrade() -> None:
    """Downgrade schema."""
    # Add back password field
    op.add_column('users', sa.Column('hashed_password', sa.String(), nullable=False))
    
    # Drop unique index
    op.drop_index('ix_users_azure_entra_id', table_name='users')
    
    # Remove Azure Entra fields
    op.drop_column('users', 'azure_entra_id')
    op.drop_column('users', 'azure_tenant_id')
    op.drop_column('users', 'azure_access_token_hash')
    op.drop_column('users', 'azure_refresh_token_hash')
    op.drop_column('users', 'azure_token_expires_at')
    op.drop_column('users', 'profile_picture_url')
    op.drop_column('users', 'organization')
    op.drop_column('users', 'department')
    
    # Remove GitHub fields
    op.drop_column('users', 'github_username')
    op.drop_column('users', 'github_access_token_hash')
    op.drop_column('users', 'github_connected_at')
