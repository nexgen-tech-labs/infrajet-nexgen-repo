"""Add GitHub user ID and OAuth fields to users table

Revision ID: 562f4458b9e3
Revises: 4ad086e9e217
Create Date: 2025-09-28 11:54:27.177478

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '562f4458b9e3'
down_revision: Union[str, Sequence[str], None] = '4ad086e9e217'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add new GitHub OAuth fields (these are new)
    op.add_column('users', sa.Column('github_user_id', sa.BigInteger(), nullable=True))
    op.add_column('users', sa.Column('github_email', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('github_access_token', sa.String(500), nullable=True))
    op.add_column('users', sa.Column('github_token_expires_at', sa.DateTime(), nullable=True))

    # Note: github_installation_id and github_app_id already exist from previous migration
    # Update github_app_id type from Integer to String for consistency
    op.alter_column('users', 'github_app_id', type_=sa.String(50), existing_type=sa.Integer())

    # Create indexes for better performance
    op.create_index('ix_users_github_user_id', 'users', ['github_user_id'], unique=True)
    # Note: ix_users_github_installation_id index already exists


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index('ix_users_github_user_id', table_name='users')
    # Note: ix_users_github_installation_id index should remain as it existed before

    # Revert github_app_id type back to Integer
    op.alter_column('users', 'github_app_id', type_=sa.Integer(), existing_type=sa.String(50))

    # Drop new GitHub OAuth fields
    op.drop_column('users', 'github_token_expires_at')
    op.drop_column('users', 'github_access_token')
    op.drop_column('users', 'github_email')
    op.drop_column('users', 'github_user_id')

    # Note: github_installation_id and github_app_id columns should remain as they existed before
