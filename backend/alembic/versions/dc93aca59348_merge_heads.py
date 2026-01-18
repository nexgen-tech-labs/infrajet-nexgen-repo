"""merge_heads

Revision ID: dc93aca59348
Revises: 4e3b9f81f486, enhanced_chat_001
Create Date: 2025-09-29 12:35:54.723753

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dc93aca59348'
down_revision: Union[str, Sequence[str], None] = ('4e3b9f81f486', 'enhanced_chat_001')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
