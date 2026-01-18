"""empty message

Revision ID: e6ef5e72eb0e
Revises: 963e787ba7e8, enhanced_embeddings
Create Date: 2025-09-09 15:54:32.010446

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e6ef5e72eb0e'
down_revision: Union[str, Sequence[str], None] = ('963e787ba7e8', 'enhanced_embeddings')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
