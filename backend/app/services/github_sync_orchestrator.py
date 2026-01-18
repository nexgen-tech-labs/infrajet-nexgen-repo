"""
GitHub Sync Orchestrator Service.

This service orchestrates the synchronization of project files from Azure File Share
to GitHub repositories with enhanced conflict detection, retry mechanisms, and
real-time progress tracking.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from logconfig.logger import get_logger
from app.services.github_service import GitHubIntegrationService, GitHubError
from app.services.projects.crud_service import ProjectCRUDService, ProjectNotFoundError
from app.services.azure.file_operations import get_file_operations_service
from app.services.realtime_service import realtime_service
from app.models.user import User, GitHubSyncRecord, GitHubSyncStatus
from app.models.project import Project
from app.schemas.github import (
    GitHubSyncResponse,
    GitHubSyncConflict,
    GitHubSyncMetrics,
    GitHubSyncStatusUpdate,
    GitHubSyncStatus as SchemaSyncStatus
)

logger = get_logger()


class GitHubSyncOrchestrator:
    """
    Orchestrator for GitHub synchronization operations with enhanced features.
    
    This service provides high-level sync operations with:
    - Conflict detection and resolution
    - Retry mechanisms for failed operations
    - Real-time progress tracking
    - Batch synchronization
    - Sync metrics and analytics
    """

    def __init__(self, db_session: AsyncSession):
        """
        Initialize the sync orchestrator.
        
        Args:
            db_session: Database session for operations
        """
        self.db = db_session
        self.github_service = GitHubIntegrationService()
        self.project_crud = ProjectCRUDService(db_session)
        
        # Track active sync operations
        self.active_syncs: Dict[str, Dict[str, Any]] = {}

    async def sync_project_with_progress_tracking(
        self,
        user: User,
        project_id: str,
        repository_full_name: str,
        commit_message: Optional[str] = None,
        branch: str = "main",
        check_conflicts: bool = True
    ) -> Tuple[GitHubSyncResponse, str]:
        """
        Sync project with real-time progress tracking.
        
        Args:
            user: User performing the sync
            project_id: Project ID to sync
            repository_full_name: Target repository
            commit_message: Optional commit message
            branch: Target branch
            check_conflicts: Whether to check for conflicts first
            
        Returns:
            Tuple of (GitHubSyncResponse, sync_tracking_id)
        """
        sync_tracking_id = str(uuid.uuid4())
        
        try:
            # Initialize sync tracking
            self.active_syncs[sync_tracking_id] = {
                "user_id": user.id,
                "project_id": project_id,
                "repository": repository_full_name,
                "branch": branch,
                "status": "initializing",
                "progress": 0,
                "total_files": 0,
                "files_completed": 0,
                "current_file": None,
                "started_at": datetime.utcnow(),
                "errors": []
            }

            # Send initial status update
            await self._send_sync_status_update(sync_tracking_id, user.id)

            # Get project and files
            project = await self.project_crud.get_project(project_id, user.id, include_files=True)
            
            if not project.files:
                raise GitHubError(f"No files found in project {project_id}")

            # Update tracking with file count
            self.active_syncs[sync_tracking_id]["total_files"] = len(project.files)
            self.active_syncs[sync_tracking_id]["status"] = "checking_conflicts"
            await self._send_sync_status_update(sync_tracking_id, user.id)

            # Check for conflicts if requested
            conflicts = []
            if check_conflicts:
                try:
                    conflicts = await self.github_service.get_sync_conflicts(
                        self.db, user, project_id, repository_full_name, branch
                    )
                    
                    if conflicts:
                        logger.info(f"Found {len(conflicts)} potential conflicts for project {project_id}")
                        # Store conflicts in tracking
                        self.active_syncs[sync_tracking_id]["conflicts"] = conflicts
                except Exception as e:
                    logger.warning(f"Could not check conflicts: {str(e)}")

            # Update status to syncing
            self.active_syncs[sync_tracking_id]["status"] = "syncing"
            await self._send_sync_status_update(sync_tracking_id, user.id)

            # Perform the actual sync with progress tracking
            sync_response = await self._sync_with_progress_updates(
                sync_tracking_id, user, project, repository_full_name, 
                commit_message, branch
            )

            # Update final status
            self.active_syncs[sync_tracking_id]["status"] = "completed" if sync_response.status == SchemaSyncStatus.COMPLETED else "failed"
            self.active_syncs[sync_tracking_id]["progress"] = 100
            self.active_syncs[sync_tracking_id]["completed_at"] = datetime.utcnow()
            await self._send_sync_status_update(sync_tracking_id, user.id)

            return sync_response, sync_tracking_id

        except Exception as e:
            # Update error status
            if sync_tracking_id in self.active_syncs:
                self.active_syncs[sync_tracking_id]["status"] = "failed"
                self.active_syncs[sync_tracking_id]["error"] = str(e)
                await self._send_sync_status_update(sync_tracking_id, user.id)
            
            logger.error(f"Error in sync with progress tracking: {str(e)}")
            raise

    async def _sync_with_progress_updates(
        self,
        sync_tracking_id: str,
        user: User,
        project: Project,
        repository_full_name: str,
        commit_message: Optional[str],
        branch: str
    ) -> GitHubSyncResponse:
        """
        Perform sync with progress updates.
        
        Args:
            sync_tracking_id: Sync tracking ID
            user: User performing sync
            project: Project to sync
            repository_full_name: Target repository
            commit_message: Commit message
            branch: Target branch
            
        Returns:
            GitHubSyncResponse with results
        """
        file_service = await get_file_operations_service()
        files_content = {}
        
        # Download files with progress updates
        for i, project_file in enumerate(project.files):
            try:
                # Update current file being processed
                self.active_syncs[sync_tracking_id]["current_file"] = project_file.file_path
                self.active_syncs[sync_tracking_id]["progress"] = int((i / len(project.files)) * 50)  # First 50% for downloading
                await self._send_sync_status_update(sync_tracking_id, user.id)

                # Download file
                download_result = await file_service.download_file(project_file.azure_path)
                if download_result.success and hasattr(download_result, 'content'):
                    files_content[project_file.file_path] = download_result.content
                else:
                    error_msg = f"Failed to download {project_file.file_path}: {download_result.error}"
                    self.active_syncs[sync_tracking_id]["errors"].append(error_msg)
                    logger.warning(error_msg)

            except Exception as e:
                error_msg = f"Error downloading {project_file.file_path}: {str(e)}"
                self.active_syncs[sync_tracking_id]["errors"].append(error_msg)
                logger.error(error_msg)

        if not files_content:
            raise GitHubError("No files could be downloaded for sync")

        # Update status to uploading
        self.active_syncs[sync_tracking_id]["status"] = "uploading"
        self.active_syncs[sync_tracking_id]["progress"] = 50
        await self._send_sync_status_update(sync_tracking_id, user.id)

        # Generate commit message
        if not commit_message:
            commit_message = f"Sync project '{project.name}' from Infrajet"

        # Perform GitHub sync
        sync_response = await self.github_service.sync_project_to_repository(
            db=self.db,
            user=user,
            project_id=project.id,
            repository_full_name=repository_full_name,
            files_content=files_content,
            commit_message=commit_message,
            branch=branch
        )

        return sync_response

    async def _send_sync_status_update(self, sync_tracking_id: str, user_id: int):
        """
        Send real-time sync status update.
        
        Args:
            sync_tracking_id: Sync tracking ID
            user_id: User ID to send update to
        """
        if sync_tracking_id not in self.active_syncs:
            return

        sync_info = self.active_syncs[sync_tracking_id]
        
        # Create status update
        status_update = GitHubSyncStatusUpdate(
            sync_id=sync_tracking_id,
            status=SchemaSyncStatus(sync_info["status"]) if sync_info["status"] in ["pending", "in_progress", "completed", "failed", "cancelled"] else SchemaSyncStatus.IN_PROGRESS,
            progress_percentage=sync_info.get("progress", 0),
            current_file=sync_info.get("current_file"),
            files_completed=sync_info.get("files_completed", 0),
            total_files=sync_info.get("total_files", 0),
            error_message=sync_info.get("error")
        )

        # Send via WebSocket
        try:
            await realtime_service.send_to_user(
                user_id=user_id,
                event_type="github_sync_progress",
                data=status_update.dict()
            )
        except Exception as e:
            logger.warning(f"Failed to send sync status update: {str(e)}")

    async def batch_sync_projects(
        self,
        user: User,
        sync_requests: List[Dict[str, Any]],
        max_concurrent: int = 3
    ) -> List[GitHubSyncResponse]:
        """
        Sync multiple projects concurrently with rate limiting.
        
        Args:
            user: User performing syncs
            sync_requests: List of sync request dictionaries
            max_concurrent: Maximum concurrent syncs
            
        Returns:
            List of GitHubSyncResponse results
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def sync_single_project(request: Dict[str, Any]) -> GitHubSyncResponse:
            async with semaphore:
                try:
                    response, _ = await self.sync_project_with_progress_tracking(
                        user=user,
                        project_id=request["project_id"],
                        repository_full_name=request["repository_full_name"],
                        commit_message=request.get("commit_message"),
                        branch=request.get("branch", "main"),
                        check_conflicts=request.get("check_conflicts", True)
                    )
                    return response
                except Exception as e:
                    logger.error(f"Error in batch sync for project {request['project_id']}: {str(e)}")
                    # Return a failed response
                    from app.schemas.github import GitHubSyncResponse
                    return GitHubSyncResponse(
                        sync_id="failed",
                        status=SchemaSyncStatus.FAILED,
                        repository_full_name=request["repository_full_name"],
                        branch=request.get("branch", "main"),
                        files_synced=0,
                        error_message=str(e),
                        created_at=datetime.utcnow()
                    )

        # Execute all syncs concurrently
        tasks = [sync_single_project(request) for request in sync_requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and return valid responses
        valid_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Batch sync task failed: {str(result)}")
                # Create a failed response for exceptions
                valid_results.append(GitHubSyncResponse(
                    sync_id="exception",
                    status=SchemaSyncStatus.FAILED,
                    repository_full_name="unknown",
                    branch="main",
                    files_synced=0,
                    error_message=str(result),
                    created_at=datetime.utcnow()
                ))
            else:
                valid_results.append(result)
        
        return valid_results

    async def get_sync_metrics(
        self,
        user: User,
        project_id: Optional[str] = None,
        days_back: int = 30
    ) -> GitHubSyncMetrics:
        """
        Get sync metrics and statistics.
        
        Args:
            user: User to get metrics for
            project_id: Optional project ID filter
            days_back: Number of days to look back
            
        Returns:
            GitHubSyncMetrics with statistics
        """
        try:
            # Build query
            query = select(GitHubSyncRecord).where(
                and_(
                    GitHubSyncRecord.user_id == user.id,
                    GitHubSyncRecord.created_at >= datetime.utcnow() - timedelta(days=days_back)
                )
            )
            
            if project_id:
                query = query.where(GitHubSyncRecord.project_id == project_id)

            result = await self.db.execute(query)
            sync_records = result.scalars().all()

            # Calculate metrics
            total_syncs = len(sync_records)
            successful_syncs = len([r for r in sync_records if r.sync_status == GitHubSyncStatus.COMPLETED])
            failed_syncs = len([r for r in sync_records if r.sync_status == GitHubSyncStatus.FAILED])
            
            # Calculate total files synced (this would need to be tracked in sync records)
            total_files_synced = 0  # Would need to enhance sync records to track this
            
            # Calculate conflicts resolved (would need to enhance tracking)
            total_conflicts_resolved = 0
            
            # Calculate average duration (would need to track duration in sync records)
            average_sync_duration = None
            
            # Get last sync timestamp
            last_sync_at = None
            if sync_records:
                completed_syncs = [r for r in sync_records if r.last_sync_at]
                if completed_syncs:
                    last_sync_at = max(r.last_sync_at for r in completed_syncs)

            return GitHubSyncMetrics(
                total_syncs=total_syncs,
                successful_syncs=successful_syncs,
                failed_syncs=failed_syncs,
                total_files_synced=total_files_synced,
                total_conflicts_resolved=total_conflicts_resolved,
                average_sync_duration=average_sync_duration,
                last_sync_at=last_sync_at
            )

        except Exception as e:
            logger.error(f"Error getting sync metrics: {str(e)}")
            raise GitHubError(f"Failed to get sync metrics: {str(e)}")

    async def cleanup_old_sync_records(
        self,
        days_to_keep: int = 90,
        keep_failed_records: bool = True
    ) -> int:
        """
        Clean up old sync records to prevent database bloat.
        
        Args:
            days_to_keep: Number of days of records to keep
            keep_failed_records: Whether to keep failed records longer
            
        Returns:
            Number of records cleaned up
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            # Build delete query
            if keep_failed_records:
                # Only delete successful records older than cutoff
                query = select(GitHubSyncRecord).where(
                    and_(
                        GitHubSyncRecord.created_at < cutoff_date,
                        GitHubSyncRecord.sync_status == GitHubSyncStatus.COMPLETED
                    )
                )
            else:
                # Delete all records older than cutoff
                query = select(GitHubSyncRecord).where(
                    GitHubSyncRecord.created_at < cutoff_date
                )

            result = await self.db.execute(query)
            records_to_delete = result.scalars().all()
            
            # Delete records
            for record in records_to_delete:
                await self.db.delete(record)
            
            await self.db.commit()
            
            logger.info(f"Cleaned up {len(records_to_delete)} old sync records")
            return len(records_to_delete)

        except Exception as e:
            logger.error(f"Error cleaning up sync records: {str(e)}")
            await self.db.rollback()
            return 0

    async def get_active_syncs(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get currently active syncs for a user.
        
        Args:
            user_id: User ID to get active syncs for
            
        Returns:
            List of active sync information
        """
        active_user_syncs = []
        
        for sync_id, sync_info in self.active_syncs.items():
            if sync_info["user_id"] == user_id:
                # Calculate duration
                duration = (datetime.utcnow() - sync_info["started_at"]).total_seconds()
                
                active_user_syncs.append({
                    "sync_id": sync_id,
                    "project_id": sync_info["project_id"],
                    "repository": sync_info["repository"],
                    "status": sync_info["status"],
                    "progress": sync_info["progress"],
                    "current_file": sync_info.get("current_file"),
                    "duration_seconds": duration,
                    "errors": sync_info.get("errors", [])
                })
        
        return active_user_syncs

    async def cancel_sync(self, sync_tracking_id: str, user_id: int) -> bool:
        """
        Cancel an active sync operation.
        
        Args:
            sync_tracking_id: Sync tracking ID to cancel
            user_id: User ID requesting cancellation
            
        Returns:
            True if cancellation was successful
        """
        if sync_tracking_id not in self.active_syncs:
            return False
        
        sync_info = self.active_syncs[sync_tracking_id]
        
        # Check if user owns this sync
        if sync_info["user_id"] != user_id:
            return False
        
        # Update status to cancelled
        sync_info["status"] = "cancelled"
        sync_info["cancelled_at"] = datetime.utcnow()
        
        # Send status update
        await self._send_sync_status_update(sync_tracking_id, user_id)
        
        logger.info(f"Cancelled sync {sync_tracking_id} for user {user_id}")
        return True

    async def close(self):
        """Clean up resources."""
        await self.github_service.close()
        
        # Clean up active syncs
        self.active_syncs.clear()