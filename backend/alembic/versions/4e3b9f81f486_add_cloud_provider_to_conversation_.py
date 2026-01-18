"""add_cloud_provider_to_conversation_threads

Revision ID: 4e3b9f81f486
Revises: 7abbcd5ee9e7
Create Date: 2025-09-28 17:14:03.105025

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e3b9f81f486'
down_revision: Union[str, Sequence[str], None] = '7abbcd5ee9e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add cloud_provider column to conversation_threads table
    op.add_column('conversation_threads', sa.Column('cloud_provider', sa.String(length=50), nullable=False, default='AWS'))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove cloud_provider column from conversation_threads table
    op.drop_column('conversation_threads', 'cloud_provider')
