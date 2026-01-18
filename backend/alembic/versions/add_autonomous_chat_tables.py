"""Add autonomous chat tables for conversation management

Revision ID: add_autonomous_chat_tables
Revises: add_github_connected_at
Create Date: 2025-09-28 15:07:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_autonomous_chat_tables'
down_revision = 'add_github_connected_at'
branch_labels = None
depends_on = None


def upgrade():
    """Add tables for autonomous chat functionality."""

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
        sa.Column('code_references', postgresql.JSONB(), nullable=True),
        sa.Column('generation_lineage', postgresql.JSONB(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
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
        sa.Column('request_data', postgresql.JSONB(), nullable=False),
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
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
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


def downgrade():
    """Remove autonomous chat tables."""

    # Remove thread_id from project_chats
    op.drop_constraint('fk_project_chats_thread_id', 'project_chats', type_='foreignkey')
    op.drop_index(op.f('ix_project_chats_thread_id'), table_name='project_chats')
    op.drop_column('project_chats', 'thread_id')

    # Drop generation_lineage table
    op.drop_index(op.f('ix_generation_lineage_created_at'), table_name='generation_lineage')
    op.drop_index(op.f('ix_generation_lineage_generation_id'), table_name='generation_lineage')
    op.drop_index(op.f('ix_generation_lineage_thread_id'), table_name='generation_lineage')
    op.drop_index(op.f('ix_generation_lineage_id'), table_name='generation_lineage')
    op.drop_table('generation_lineage')

    # Drop clarification_requests table
    op.drop_index(op.f('ix_clarification_requests_created_at'), table_name='clarification_requests')
    op.drop_index(op.f('ix_clarification_requests_status'), table_name='clarification_requests')
    op.drop_index(op.f('ix_clarification_requests_thread_id'), table_name='clarification_requests')
    op.drop_index(op.f('ix_clarification_requests_id'), table_name='clarification_requests')
    op.drop_table('clarification_requests')

    # Drop conversation_contexts table
    op.drop_index(op.f('ix_conversation_contexts_last_updated'), table_name='conversation_contexts')
    op.drop_index(op.f('ix_conversation_contexts_thread_id'), table_name='conversation_contexts')
    op.drop_index(op.f('ix_conversation_contexts_id'), table_name='conversation_contexts')
    op.drop_table('conversation_contexts')

    # Drop conversation_threads table
    op.drop_index(op.f('ix_conversation_threads_created_at'), table_name='conversation_threads')
    op.drop_index(op.f('ix_conversation_threads_user_id'), table_name='conversation_threads')
    op.drop_index(op.f('ix_conversation_threads_project_id'), table_name='conversation_threads')
    op.drop_index(op.f('ix_conversation_threads_id'), table_name='conversation_threads')
    op.drop_table('conversation_threads')