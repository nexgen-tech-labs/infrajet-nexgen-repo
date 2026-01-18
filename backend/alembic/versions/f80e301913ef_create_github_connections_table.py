"""create_github_connections_table

Revision ID: f80e301913ef
Revises: 562f4458b9e3
Create Date: 2025-09-28 12:27:47.649064

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f80e301913ef'
down_revision: Union[str, Sequence[str], None] = '562f4458b9e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create github_connections table
    op.create_table('github_connections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('supabase_user_id', sa.String(length=255), nullable=False),
        sa.Column('github_user_id', sa.Integer(), nullable=True),
        sa.Column('github_username', sa.String(length=255), nullable=True),
        sa.Column('github_email', sa.String(length=255), nullable=True),
        sa.Column('github_access_token', sa.Text(), nullable=True),
        sa.Column('github_token_expires_at', sa.DateTime(), nullable=True),
        sa.Column('github_installation_id', sa.Integer(), nullable=True),
        sa.Column('github_app_id', sa.Integer(), nullable=True),
        sa.Column('github_connected_at', sa.DateTime(), nullable=True),
        sa.Column('connection_type', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'), server_onupdate=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index(op.f('ix_github_connections_id'), 'github_connections', ['id'], unique=False)
    op.create_index(op.f('ix_github_connections_supabase_user_id'), 'github_connections', ['supabase_user_id'], unique=False)
    op.create_index(op.f('ix_github_connections_github_user_id'), 'github_connections', ['github_user_id'], unique=True)
    op.create_index(op.f('ix_github_connections_github_installation_id'), 'github_connections', ['github_installation_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index(op.f('ix_github_connections_github_installation_id'), table_name='github_connections')
    op.drop_index(op.f('ix_github_connections_github_user_id'), table_name='github_connections')
    op.drop_index(op.f('ix_github_connections_supabase_user_id'), table_name='github_connections')
    op.drop_index(op.f('ix_github_connections_id'), table_name='github_connections')

    # Drop table
    op.drop_table('github_connections')
