"""
Conversation Context Manager for Autonomous Chat System.

This service manages conversation state, context snapshots, summarization,
and tracks intent, code references, and generation lineage for autonomous
chat conversations.
"""

import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from logconfig.logger import get_logger

logger = get_logger()


@dataclass
class ConversationContext:
    """Data class representing conversation context."""
    thread_id: str
    intent: Optional[str] = None
    code_references: List[Dict[str, Any]] = None
    generation_lineage: List[Dict[str, Any]] = None
    summary: Optional[str] = None
    last_updated: datetime = None
    context_metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.code_references is None:
            self.code_references = []
        if self.generation_lineage is None:
            self.generation_lineage = []
        if self.context_metadata is None:
            self.context_metadata = {}
        if self.last_updated is None:
            self.last_updated = datetime.utcnow()


class ConversationContextManagerError(Exception):
    """Base exception for conversation context manager operations."""
    pass


class ConversationContextManager:
    """
    Manages conversation context for autonomous chat system.

    Handles context snapshots, summarization, intent tracking,
    code references, and generation lineage.
    """

    def __init__(self, db_session: AsyncSession):
        """
        Initialize the conversation context manager.

        Args:
            db_session: Database session for operations
        """
        self.db = db_session

    async def save_context(self, context: ConversationContext) -> str:
        """
        Save conversation context to database.

        Args:
            context: ConversationContext to save

        Returns:
            str: Context ID

        Raises:
            ConversationContextManagerError: If save operation fails
        """
        try:
            # For now, we'll store in memory/disk since DB schema isn't ready yet
            # This will be updated in Phase 2 when we add the database tables
            context_id = str(uuid.uuid4())

            # Serialize context for storage
            context_data = {
                'id': context_id,
                'thread_id': context.thread_id,
                'intent': context.intent,
                'code_references': context.code_references,
                'generation_lineage': context.generation_lineage,
                'summary': context.summary,
                'last_updated': context.last_updated.isoformat(),
                'metadata': context.context_metadata
            }

            # TODO: Replace with actual database insertion when schema is ready
            # For now, we'll log the context data
            logger.info(f"Saving context for thread {context.thread_id}: {json.dumps(context_data, indent=2)}")

            return context_id

        except Exception as e:
            logger.error(f"Failed to save context for thread {context.thread_id}: {e}")
            raise ConversationContextManagerError(f"Failed to save context: {e}")

    async def load_context(self, thread_id: str) -> Optional[ConversationContext]:
        """
        Load conversation context from database.

        Args:
            thread_id: Conversation thread ID

        Returns:
            Optional[ConversationContext]: Loaded context or None if not found

        Raises:
            ConversationContextManagerError: If load operation fails
        """
        try:
            # TODO: Replace with actual database query when schema is ready
            # For now, return None as we don't have persistence yet
            logger.info(f"Loading context for thread {thread_id} (not implemented yet)")
            return None

        except Exception as e:
            logger.error(f"Failed to load context for thread {thread_id}: {e}")
            raise ConversationContextManagerError(f"Failed to load context: {e}")

    async def update_context(
        self,
        thread_id: str,
        updates: Dict[str, Any]
    ) -> ConversationContext:
        """
        Update conversation context with new information.

        Args:
            thread_id: Conversation thread ID
            updates: Dictionary of fields to update

        Returns:
            ConversationContext: Updated context

        Raises:
            ConversationContextManagerError: If update operation fails
        """
        try:
            # Load existing context
            context = await self.load_context(thread_id)

            if context is None:
                # Create new context if none exists
                context = ConversationContext(thread_id=thread_id)

            # Apply updates
            for key, value in updates.items():
                if hasattr(context, key):
                    setattr(context, key, value)

            # Update timestamp
            context.last_updated = datetime.utcnow()

            # Save updated context
            await self.save_context(context)

            logger.info(f"Updated context for thread {thread_id}")
            return context

        except Exception as e:
            logger.error(f"Failed to update context for thread {thread_id}: {e}")
            raise ConversationContextManagerError(f"Failed to update context: {e}")

    async def summarize_context(self, thread_id: str, max_length: int = 500) -> str:
        """
        Generate or retrieve a summary of the conversation context.

        Args:
            thread_id: Conversation thread ID
            max_length: Maximum length of summary in characters

        Returns:
            str: Context summary

        Raises:
            ConversationContextManagerError: If summarization fails
        """
        try:
            context = await self.load_context(thread_id)

            if context and context.summary:
                # Return existing summary if available
                return context.summary

            # TODO: Implement LLM-based summarization when context is available
            # For now, return a placeholder summary
            summary = f"Conversation context for thread {thread_id}: Intent - {context.intent if context else 'Unknown'}"

            # Truncate if too long
            if len(summary) > max_length:
                summary = summary[:max_length - 3] + "..."

            # Update context with summary
            if context:
                context.summary = summary
                await self.save_context(context)

            logger.info(f"Generated summary for thread {thread_id}")
            return summary

        except Exception as e:
            logger.error(f"Failed to summarize context for thread {thread_id}: {e}")
            raise ConversationContextManagerError(f"Failed to summarize context: {e}")

    async def add_code_reference(
        self,
        thread_id: str,
        file_path: str,
        line_number: Optional[int] = None,
        code_snippet: Optional[str] = None,
        reference_type: str = "general"
    ) -> None:
        """
        Add a code reference to the conversation context.

        Args:
            thread_id: Conversation thread ID
            file_path: Path to the referenced file
            line_number: Line number in the file (optional)
            code_snippet: Code snippet (optional)
            reference_type: Type of reference (e.g., 'function', 'class', 'general')

        Raises:
            ConversationContextManagerError: If operation fails
        """
        try:
            reference = {
                'id': str(uuid.uuid4()),
                'file_path': file_path,
                'line_number': line_number,
                'code_snippet': code_snippet,
                'reference_type': reference_type,
                'timestamp': datetime.utcnow().isoformat()
            }

            updates = {
                'code_references': lambda ctx: (ctx.code_references or []) + [reference]
            }

            await self.update_context(thread_id, updates)
            logger.info(f"Added code reference to thread {thread_id}: {file_path}")

        except Exception as e:
            logger.error(f"Failed to add code reference to thread {thread_id}: {e}")
            raise ConversationContextManagerError(f"Failed to add code reference: {e}")

    async def add_generation_lineage(
        self,
        thread_id: str,
        generation_id: str,
        prompt: str,
        response: str,
        model_used: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add generation lineage entry to track AI generations.

        Args:
            thread_id: Conversation thread ID
            generation_id: Unique ID for this generation
            prompt: The prompt used for generation
            response: The AI response
            model_used: LLM model used
            metadata: Additional metadata

        Raises:
            ConversationContextManagerError: If operation fails
        """
        try:
            lineage_entry = {
                'id': str(uuid.uuid4()),
                'generation_id': generation_id,
                'prompt': prompt,
                'response': response,
                'model_used': model_used,
                'timestamp': datetime.utcnow().isoformat(),
                'metadata': metadata or {}
            }

            updates = {
                'generation_lineage': lambda ctx: (ctx.generation_lineage or []) + [lineage_entry]
            }

            await self.update_context(thread_id, updates)
            logger.info(f"Added generation lineage to thread {thread_id}: {generation_id}")

        except Exception as e:
            logger.error(f"Failed to add generation lineage to thread {thread_id}: {e}")
            raise ConversationContextManagerError(f"Failed to add generation lineage: {e}")

    async def get_context_stats(self, thread_id: str) -> Dict[str, Any]:
        """
        Get statistics about the conversation context.

        Args:
            thread_id: Conversation thread ID

        Returns:
            Dict[str, Any]: Context statistics

        Raises:
            ConversationContextManagerError: If operation fails
        """
        try:
            context = await self.load_context(thread_id)

            if not context:
                return {
                    'thread_id': thread_id,
                    'has_context': False,
                    'code_references_count': 0,
                    'generation_lineage_count': 0,
                    'last_updated': None
                }

            return {
                'thread_id': thread_id,
                'has_context': True,
                'intent': context.intent,
                'code_references_count': len(context.code_references),
                'generation_lineage_count': len(context.generation_lineage),
                'has_summary': bool(context.summary),
                'last_updated': context.last_updated.isoformat() if context.last_updated else None
            }

        except Exception as e:
            logger.error(f"Failed to get context stats for thread {thread_id}: {e}")
            raise ConversationContextManagerError(f"Failed to get context stats: {e}")