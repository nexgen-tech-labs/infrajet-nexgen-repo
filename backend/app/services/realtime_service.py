"""
Real-time service for emitting events to WebSocket clients.

This service provides a high-level interface for other services
to emit real-time events without directly managing WebSocket connections.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from enum import Enum

from app.services.websocket_manager import (
    websocket_manager,
    RealtimeEvent,
    GenerationProgressEvent,
    ProjectUpdateEvent,
)

logger = logging.getLogger(__name__)


class GenerationStatus(str, Enum):
    """Code generation status enumeration."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProjectUpdateType(str, Enum):
    """Project update type enumeration."""

    FILE_ADDED = "file_added"
    FILE_UPDATED = "file_updated"
    FILE_DELETED = "file_deleted"
    GENERATION_STARTED = "generation_started"
    GENERATION_COMPLETED = "generation_completed"
    GENERATION_FAILED = "generation_failed"
    PROJECT_UPDATED = "project_updated"
    SYNC_STARTED = "sync_started"
    SYNC_COMPLETED = "sync_completed"
    SYNC_FAILED = "sync_failed"


class RealtimeService:
    """
    Service for emitting real-time events to WebSocket clients.

    This service acts as a bridge between business logic and WebSocket
    communication, providing typed methods for common event types.
    """

    def __init__(self):
        self.websocket_manager = websocket_manager

    async def emit_generation_progress(
        self,
        generation_id: str,
        project_id: str,
        user_id: int,
        status: GenerationStatus,
        progress_percentage: int = 0,
        current_step: str = "",
        estimated_completion: Optional[datetime] = None,
        files_generated: Optional[List[str]] = None,
    ):
        """
        Emit code generation progress update.

        Args:
            generation_id: Unique generation identifier
            project_id: Project identifier
            user_id: User who initiated the generation
            status: Current generation status
            progress_percentage: Progress percentage (0-100)
            current_step: Description of current step
            estimated_completion: Estimated completion time
            files_generated: List of files generated so far
        """
        event_data = {
            "event_type": "generation_progress",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "generation_id": generation_id,
                "project_id": project_id,
                "user_id": user_id,
                "status": status.value,
                "progress_percentage": progress_percentage,
                "current_step": current_step,
                "estimated_completion": (
                    estimated_completion.isoformat() if estimated_completion else None
                ),
                "files_generated": files_generated or [],
            },
        }

        # Broadcast to generation subscribers
        generation_count = await self.websocket_manager.broadcast_to_generation(
            generation_id, event_data
        )

        # Also send to user's other sessions
        user_count = await self.websocket_manager.send_to_user(user_id, event_data)

        # And to project subscribers
        project_count = await self.websocket_manager.broadcast_to_project(
            project_id, event_data
        )

        logger.info(
            f"Generation progress event emitted: generation_id={generation_id}, "
            f"status={status.value}, progress={progress_percentage}%, "
            f"notified_sessions={generation_count + user_count + project_count}"
        )

    async def emit_generation_started(
        self,
        generation_id: str,
        project_id: str,
        user_id: int,
        prompt: str,
        estimated_duration: Optional[int] = None,
    ):
        """
        Emit generation started event.

        Args:
            generation_id: Unique generation identifier
            project_id: Project identifier
            user_id: User who initiated the generation
            prompt: Generation prompt/description
            estimated_duration: Estimated duration in seconds
        """
        await self.emit_generation_progress(
            generation_id=generation_id,
            project_id=project_id,
            user_id=user_id,
            status=GenerationStatus.IN_PROGRESS,
            progress_percentage=0,
            current_step="Initializing code generation...",
            estimated_completion=(
                datetime.utcnow() + timedelta(seconds=estimated_duration)
                if estimated_duration
                else None
            ),
        )

        # Also emit project update
        await self.emit_project_update(
            project_id=project_id,
            user_id=user_id,
            update_type=ProjectUpdateType.GENERATION_STARTED,
            data={
                "generation_id": generation_id,
                "prompt": prompt,
                "estimated_duration": estimated_duration,
            },
        )

    async def emit_generation_completed(
        self,
        generation_id: str,
        project_id: str,
        user_id: int,
        files_generated: List[str],
        generation_summary: Optional[str] = None,
    ):
        """
        Emit generation completed event.

        Args:
            generation_id: Unique generation identifier
            project_id: Project identifier
            user_id: User who initiated the generation
            files_generated: List of generated files
            generation_summary: Summary of what was generated
        """
        await self.emit_generation_progress(
            generation_id=generation_id,
            project_id=project_id,
            user_id=user_id,
            status=GenerationStatus.COMPLETED,
            progress_percentage=100,
            current_step="Generation completed successfully",
            files_generated=files_generated,
        )

        # Also emit project update
        await self.emit_project_update(
            project_id=project_id,
            user_id=user_id,
            update_type=ProjectUpdateType.GENERATION_COMPLETED,
            data={
                "generation_id": generation_id,
                "files_generated": files_generated,
                "file_count": len(files_generated),
                "summary": generation_summary,
            },
        )

    async def emit_generation_failed(
        self,
        generation_id: str,
        project_id: str,
        user_id: int,
        error_message: str,
        error_details: Optional[Dict[str, Any]] = None,
    ):
        """
        Emit generation failed event.

        Args:
            generation_id: Unique generation identifier
            project_id: Project identifier
            user_id: User who initiated the generation
            error_message: Error message
            error_details: Additional error details
        """
        await self.emit_generation_progress(
            generation_id=generation_id,
            project_id=project_id,
            user_id=user_id,
            status=GenerationStatus.FAILED,
            progress_percentage=0,
            current_step=f"Generation failed: {error_message}",
        )

        # Also emit project update
        await self.emit_project_update(
            project_id=project_id,
            user_id=user_id,
            update_type=ProjectUpdateType.GENERATION_FAILED,
            data={
                "generation_id": generation_id,
                "error_message": error_message,
                "error_details": error_details or {},
            },
        )

    async def emit_project_update(
        self,
        project_id: str,
        user_id: int,
        update_type: ProjectUpdateType,
        data: Optional[Dict[str, Any]] = None,
    ):
        """
        Emit project update event.

        Args:
            project_id: Project identifier
            user_id: User associated with the update
            update_type: Type of update
            data: Additional update data
        """
        event_data = {
            "event_type": "project_updated",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "project_id": project_id,
                "user_id": user_id,
                "update_type": update_type.value,
                "update_data": data or {},
            },
        }

        # Broadcast to project subscribers
        project_count = await self.websocket_manager.broadcast_to_project(
            project_id, event_data
        )

        # Also send to user's sessions
        user_count = await self.websocket_manager.send_to_user(user_id, event_data)

        logger.info(
            f"Project update event emitted: project_id={project_id}, "
            f"update_type={update_type.value}, "
            f"notified_sessions={project_count + user_count}"
        )

    async def emit_file_created(
        self,
        project_id: str,
        user_id: int,
        file_path: str,
        file_size: Optional[int] = None,
        generation_id: Optional[str] = None,
    ):
        """
        Emit file created event.

        Args:
            project_id: Project identifier
            user_id: User who created the file
            file_path: Path of the created file
            file_size: Size of the file in bytes
            generation_id: Associated generation ID if applicable
        """
        await self.emit_project_update(
            project_id=project_id,
            user_id=user_id,
            update_type=ProjectUpdateType.FILE_ADDED,
            data={
                "file_path": file_path,
                "file_size": file_size,
                "generation_id": generation_id,
            },
        )

    async def emit_sync_status(
        self,
        project_id: str,
        user_id: int,
        sync_type: str,  # "github", "azure_devops", etc.
        status: str,  # "started", "completed", "failed"
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Emit synchronization status event.

        Args:
            project_id: Project identifier
            user_id: User who initiated the sync
            sync_type: Type of synchronization
            status: Sync status
            details: Additional sync details
        """
        update_type_map = {
            "started": ProjectUpdateType.SYNC_STARTED,
            "completed": ProjectUpdateType.SYNC_COMPLETED,
            "failed": ProjectUpdateType.SYNC_FAILED,
        }

        update_type = update_type_map.get(status, ProjectUpdateType.PROJECT_UPDATED)

        await self.emit_project_update(
            project_id=project_id,
            user_id=user_id,
            update_type=update_type,
            data={
                "sync_type": sync_type,
                "sync_status": status,
                "sync_details": details or {},
            },
        )

    async def emit_user_notification(
        self,
        user_id: int,
        notification_type: str,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ):
        """
        Emit user-specific notification.

        Args:
            user_id: Target user ID
            notification_type: Type of notification (info, warning, error, success)
            title: Notification title
            message: Notification message
            data: Additional notification data
        """
        event_data = {
            "event_type": "user_notification",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "notification_type": notification_type,
                "title": title,
                "message": message,
                "notification_data": data or {},
            },
        }

        sent_count = await self.websocket_manager.send_to_user(user_id, event_data)

        logger.info(
            f"User notification emitted: user_id={user_id}, "
            f"type={notification_type}, title='{title}', "
            f"notified_sessions={sent_count}"
        )

    async def emit_system_announcement(
        self,
        announcement_type: str,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ):
        """
        Emit system-wide announcement to all connected users.

        Args:
            announcement_type: Type of announcement (maintenance, update, etc.)
            title: Announcement title
            message: Announcement message
            data: Additional announcement data
        """
        event_data = {
            "event_type": "system_announcement",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "announcement_type": announcement_type,
                "title": title,
                "message": message,
                "announcement_data": data or {},
            },
        }

        # Send to all active connections
        total_sent = 0
        for user_id in self.websocket_manager.user_sessions.keys():
            sent_count = await self.websocket_manager.send_to_user(user_id, event_data)
            total_sent += sent_count

        logger.info(
            f"System announcement emitted: type={announcement_type}, "
            f"title='{title}', notified_sessions={total_sent}"
        )

    async def emit_dashboard_update(
        self,
        user_id: int,
        update_type: str,
        data: Optional[Dict[str, Any]] = None,
    ):
        """
        Emit dashboard-specific update event.
        
        Args:
            user_id: User ID to send update to
            update_type: Type of dashboard update
            data: Additional update data
        """
        event_data = {
            "event_type": "dashboard_update",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "update_type": update_type,
                "user_id": user_id,
                "update_data": data or {},
            },
        }
        
        # Send to user's sessions
        user_count = await self.websocket_manager.send_to_user(user_id, event_data)
        
        logger.info(
            f"Dashboard update event emitted: user_id={user_id}, "
            f"update_type={update_type}, "
            f"notified_sessions={user_count}"
        )

    async def emit_project_list_update(
        self,
        user_id: int,
        projects_summary: List[Dict[str, Any]],
        active_generations_summary: List[Dict[str, Any]],
    ):
        """
        Emit project list update for dashboard.

        Args:
            user_id: User ID to send update to
            projects_summary: Summary of user's projects
            active_generations_summary: Summary of active generations
        """
        await self.emit_dashboard_update(
            user_id=user_id,
            update_type="project_list_updated",
            data={
                "projects": projects_summary,
                "active_generations": active_generations_summary,
                "total_projects": len(projects_summary),
                "total_active_generations": len(active_generations_summary),
            }
        )

    async def emit_user_clarification_request(
        self,
        generation_id: str,
        project_id: str,
        user_id: int,
        question: str,
        context: Optional[Dict[str, Any]] = None,
        timeout_seconds: int = 300,
    ):
        """
        Emit user clarification request during autonomous generation.

        Args:
            generation_id: Generation ID requesting clarification
            project_id: Project ID
            user_id: User ID to request clarification from
            question: Question to ask the user
            context: Additional context for the clarification
            timeout_seconds: Timeout for user response
        """
        success = await self.websocket_manager.request_user_clarification(
            generation_id=generation_id,
            project_id=project_id,
            user_id=user_id,
            question=question,
            context=context,
            timeout_seconds=timeout_seconds,
        )

        if success:
            logger.info(
                f"User clarification request emitted: generation_id={generation_id}, "
                f"user_id={user_id}, question='{question[:50]}...'"
            )
        else:
            logger.warning(
                f"Failed to emit user clarification request: generation_id={generation_id}, "
                f"user_id={user_id}"
            )

    async def submit_clarification_response(
        self, generation_id: str, user_id: int, response: str
    ) -> bool:
        """
        Submit user response to a clarification request.

        Args:
            generation_id: Generation ID
            user_id: User ID providing the response
            response: User's response

        Returns:
            True if response was accepted
        """
        return await self.websocket_manager.submit_clarification_response(
            generation_id, user_id, response
        )

    async def get_clarification_response(
        self, generation_id: str, timeout_seconds: Optional[int] = None
    ) -> Optional[str]:
        """
        Get the response to a clarification request.

        Args:
            generation_id: Generation ID
            timeout_seconds: Override timeout

        Returns:
            User response or None if timeout/no response
        """
        return await self.websocket_manager.get_clarification_response(
            generation_id, timeout_seconds
        )

    def get_connection_stats(self) -> Dict[str, Any]:
        """Get WebSocket connection statistics."""
        return self.websocket_manager.get_connection_stats()


# Global realtime service instance
realtime_service = RealtimeService()
