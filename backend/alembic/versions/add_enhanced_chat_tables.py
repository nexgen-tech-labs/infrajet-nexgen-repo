"""Add enhanced chat tables

Revision ID: enhanced_chat_001
Revises: previous_revision
Create Date: 2024-01-15 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'enhanced_chat_001'
down_revision = None  # Replace with actual previous revision
branch_labels = None
depends_on = None


def upgrade():
    """Add enhanced chat tables."""
    
    # Add cloud_provider column to conversation_threads if it doesn't exist
    try:
        op.add_column('conversation_threads', 
                     sa.Column('cloud_provider', sa.String(50), nullable=False, server_default='AWS'))
    except Exception:
        # Column might already exist
        pass
    
    # Add thread_id column to project_chats if it doesn't exist
    try:
        op.add_column('project_chats', 
                     sa.Column('thread_id', sa.String(36), nullable=True))
        op.create_index('ix_project_chats_thread_id', 'project_chats', ['thread_id'])
        op.create_foreign_key('fk_project_chats_thread_id', 'project_chats', 'conversation_threads', 
                             ['thread_id'], ['id'])
    except Exception:
        # Column might already exist
        pass
    
    # Create conversation_contexts table if it doesn't exist
    try:
        op.create_table('conversation_contexts',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('thread_id', sa.String(36), nullable=False),
            sa.Column('intent', sa.Text(), nullable=True),
            sa.Column('code_references', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('generation_lineage', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('summary', sa.Text(), nullable=True),
            sa.Column('context_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('last_updated', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['thread_id'], ['conversation_threads.id']),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_conversation_contexts_thread_id', 'conversation_contexts', ['thread_id'])
        op.create_index('ix_conversation_contexts_last_updated', 'conversation_contexts', ['last_updated'])
    except Exception:
        # Table might already exist
        pass
    
    # Create clarification_requests table if it doesn't exist
    try:
        op.create_table('clarification_requests',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('thread_id', sa.String(36), nullable=False),
            sa.Column('request_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('answered_at', sa.DateTime(), nullable=True),
            sa.Column('expires_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['thread_id'], ['conversation_threads.id']),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_clarification_requests_thread_id', 'clarification_requests', ['thread_id'])
        op.create_index('ix_clarification_requests_created_at', 'clarification_requests', ['created_at'])
    except Exception:
        # Table might already exist
        pass
    
    # Create generation_lineage table if it doesn't exist
    try:
        op.create_table('generation_lineage',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('thread_id', sa.String(36), nullable=False),
            sa.Column('generation_id', sa.String(36), nullable=False),
            sa.Column('prompt', sa.Text(), nullable=False),
            sa.Column('response', sa.Text(), nullable=True),
            sa.Column('model_used', sa.String(100), nullable=False),
            sa.Column('tokens_used', sa.Integer(), nullable=True),
            sa.Column('processing_time_ms', sa.Integer(), nullable=True),
            sa.Column('success', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('generation_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['thread_id'], ['conversation_threads.id']),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_generation_lineage_thread_id', 'generation_lineage', ['thread_id'])
        op.create_index('ix_generation_lineage_generation_id', 'generation_lineage', ['generation_id'])
        op.create_index('ix_generation_lineage_created_at', 'generation_lineage', ['created_at'])
    except Exception:
        # Table might already exist
        pass


def downgrade():
    """Remove enhanced chat tables."""
    
    # Drop tables in reverse order
    try:
        op.drop_table('generation_lineage')
    except Exception:
        pass
    
    try:
        op.drop_table('clarification_requests')
    except Exception:
        pass
    
    try:
        op.drop_table('conversation_contexts')
    except Exception:
        pass
    
    # Remove added columns
    try:
        op.drop_constraint('fk_project_chats_thread_id', 'project_chats', type_='foreignkey')
        op.drop_index('ix_project_chats_thread_id', 'project_chats')
        op.drop_column('project_chats', 'thread_id')
    except Exception:
        pass
    
    try:
        op.drop_column('conversation_threads', 'cloud_provider')
    except Exception:
        pass