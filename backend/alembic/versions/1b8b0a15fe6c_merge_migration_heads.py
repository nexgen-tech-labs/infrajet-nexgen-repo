"""Merge migration heads

Revision ID: 1b8b0a15fe6c
Revises: 8915fd1fe2df, add_github_sync_enhancements
Create Date: 2025-09-23 21:39:04.756922

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1b8b0a15fe6c'
down_revision: Union[str, Sequence[str], None] = ('8915fd1fe2df', 'add_github_sync_enhancements')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
