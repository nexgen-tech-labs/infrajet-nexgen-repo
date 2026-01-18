"""add_generation_id_to_project_chats

Revision ID: e841ac6f60f9
Revises: dc93aca59348
Create Date: 2025-09-29 12:35:59.933335

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e841ac6f60f9'
down_revision: Union[str, Sequence[str], None] = 'dc93aca59348'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add generation_id column to project_chats table
    op.add_column('project_chats', sa.Column('generation_id', sa.String(36), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove generation_id column from project_chats table
    op.drop_column('project_chats', 'generation_id')
