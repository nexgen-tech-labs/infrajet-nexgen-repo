"""empty message

Revision ID: b51003a8d1fe
Revises: add_autonomous_chat_tables, f80e301913ef
Create Date: 2025-09-28 16:09:14.247233

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b51003a8d1fe'
down_revision: Union[str, Sequence[str], None] = ('add_autonomous_chat_tables', 'f80e301913ef')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Create conversation_threads table
    op.create_table('conversation_threads',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, default='active'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('last_message_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_conversation_threads_id'), 'conversation_threads', ['id'], unique=False)
    op.create_index(op.f('ix_conversation_threads_project_id'), 'conversation_threads', ['project_id'], unique=False)
    op.create_index(op.f('ix_conversation_threads_user_id'), 'conversation_threads', ['user_id'], unique=False)
    op.create_index(op.f('ix_conversation_threads_created_at'), 'conversation_threads', ['created_at'], unique=False)

    # Create conversation_contexts table
    op.create_table('conversation_contexts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('thread_id', sa.String(length=36), nullable=False),
        sa.Column('intent', sa.Text(), nullable=True),
        sa.Column('code_references', sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column('generation_lineage', sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=False),
        sa.Column('context_metadata', sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['thread_id'], ['conversation_threads.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_conversation_contexts_id'), 'conversation_contexts', ['id'], unique=False)
    op.create_index(op.f('ix_conversation_contexts_thread_id'), 'conversation_contexts', ['thread_id'], unique=False)
    op.create_index(op.f('ix_conversation_contexts_last_updated'), 'conversation_contexts', ['last_updated'], unique=False)

    # Create clarification_requests table
    op.create_table('clarification_requests',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('thread_id', sa.String(length=36), nullable=False),
        sa.Column('request_data', sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, default='pending'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('answered_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['thread_id'], ['conversation_threads.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_clarification_requests_id'), 'clarification_requests', ['id'], unique=False)
    op.create_index(op.f('ix_clarification_requests_thread_id'), 'clarification_requests', ['thread_id'], unique=False)
    op.create_index(op.f('ix_clarification_requests_status'), 'clarification_requests', ['status'], unique=False)
    op.create_index(op.f('ix_clarification_requests_created_at'), 'clarification_requests', ['created_at'], unique=False)

    # Create generation_lineage table
    op.create_table('generation_lineage',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('thread_id', sa.String(length=36), nullable=False),
        sa.Column('generation_id', sa.String(length=36), nullable=False),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('response', sa.Text(), nullable=True),
        sa.Column('model_used', sa.String(length=100), nullable=False),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('processing_time_ms', sa.Integer(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False, default=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('generation_metadata', sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['thread_id'], ['conversation_threads.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_generation_lineage_id'), 'generation_lineage', ['id'], unique=False)
    op.create_index(op.f('ix_generation_lineage_thread_id'), 'generation_lineage', ['thread_id'], unique=False)
    op.create_index(op.f('ix_generation_lineage_generation_id'), 'generation_lineage', ['generation_id'], unique=False)
    op.create_index(op.f('ix_generation_lineage_created_at'), 'generation_lineage', ['created_at'], unique=False)

    # Update project_chats table to add thread_id column
    op.add_column('project_chats', sa.Column('thread_id', sa.String(length=36), nullable=True))
    op.create_index(op.f('ix_project_chats_thread_id'), 'project_chats', ['thread_id'], unique=False)
    op.create_foreign_key('fk_project_chats_thread_id', 'project_chats', 'conversation_threads', ['thread_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    """Downgrade schema."""
    pass
