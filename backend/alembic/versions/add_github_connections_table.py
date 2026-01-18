"""Add GitHub connections table

Revision ID: add_github_connections
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_github_connections'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Create or update GitHub connections table."""
    # Drop existing table if it exists (for clean migration)
    op.execute("DROP TABLE IF EXISTS github_connections CASCADE")
    
    # Create github_connections table with correct structure
    op.create_table(
        'github_connections',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('supabase_user_id', sa.String(255), nullable=False, index=True),
        sa.Column('github_user_id', sa.Integer(), nullable=True, unique=True, index=True),
        sa.Column('github_username', sa.String(255), nullable=True),
        sa.Column('github_access_token', sa.Text(), nullable=True),
        sa.Column('github_installation_id', sa.Integer(), nullable=True, index=True),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)
    )


def downgrade():
    """Drop GitHub connections table."""
    op.drop_table('github_connections')