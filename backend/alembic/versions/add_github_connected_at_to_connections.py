"""Add github_connected_at to github_connections table

Revision ID: add_github_connected_at
Revises: add_github_connections
Create Date: 2025-09-28 14:46:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_github_connected_at'
down_revision = 'add_github_connections'
branch_labels = None
depends_on = None


def upgrade():
    """Add github_connected_at column to github_connections table."""
    op.add_column('github_connections', sa.Column('github_connected_at', sa.DateTime(), nullable=True))


def downgrade():
    """Remove github_connected_at column from github_connections table."""
    op.drop_column('github_connections', 'github_connected_at')