"""merge_heads

Revision ID: eb7a60e7f763
Revises: f8c9d2e1a4b7, e6ef5e72eb0e
Create Date: 2025-09-23 13:58:23.801641

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eb7a60e7f763'
down_revision: Union[str, Sequence[str], None] = ('f8c9d2e1a4b7', 'e6ef5e72eb0e')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
