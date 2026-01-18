"""Add CLARIFICATION_REQUEST to messagetype enum

Revision ID: 7abbcd5ee9e7
Revises: b51003a8d1fe
Create Date: 2025-09-28 17:00:35.188941

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7abbcd5ee9e7'
down_revision: Union[str, Sequence[str], None] = 'b51003a8d1fe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add CLARIFICATION_REQUEST to the messagetype enum
    op.execute("ALTER TYPE messagetype ADD VALUE 'CLARIFICATION_REQUEST'")


def downgrade() -> None:
    """Downgrade schema."""
    pass
