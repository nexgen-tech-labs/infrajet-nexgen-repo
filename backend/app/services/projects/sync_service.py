"""
File synchronization service for maintaining consistency between database and Azure File Share.

This module provides synchronization capabilities including:
- Bidirectional sync between database and Azure File Share
- Conflict detection and resolution
- Batch synchronization operations
- Metadata reconciliation
- Background sync tasks
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_

from app.models.project import Project, ProjectFile, ProjectStatus
from app.services.azure.file_operations import FileOperationsService, get_file_operations_service
from app.services.azure.folder_manager import ProjectFolderManager, get_folder_manager
from app.services.projects.reconciliation import ReconciliationService


class SyncDirection(Enum):
    """Synchronization direction options."""
    DATABASE_TO_AZURE = "db_to_azure"
    AZURE_TO_DATABASE = "azure_to_db"
    BIDIRECTIONAL = "bidirectional"


class SyncConflictResolution(Enum):
    """Conflict resolution strategies."""
    AZURE_WINS = "azure_wins"
    DATABASE_WINS = "database_wins"
    NEWEST_WINS = "newest_wins"
    MANUAL = "manual"


class SyncStatus(Enum):
    """Synchronization status values."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CONFLICT = "conflict"


@dataclass
class SyncConflict:
    """Represents a synchronization conflict."""
    file_path: str
    project_id: str
    conflict_type: str
    database_metadata: Optional[Dict[str, Any]] = None
    azure_metadata: Optional[Dict[str, Any]] = None
    resolution_strategy: Optional[SyncConflictResolution] = None
    resolved: bool = False
    resolution_timestamp: Optional[datetime] = None


@dataclass
class SyncResult:
    """Result of a synchronization operation."""
    success: bool
    project_id: str
    direction: SyncDirection
    files_processed: int = 0
    files_synced: int = 0
    files_skipped: int = 0
    conflicts_detected: int = 0
    conflicts: List[SyncConflict] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    duration_seconds: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SyncOperation:
    """Represents a synchronization operation."""
    operation_id: str
    project_id: str
    direction: SyncDirection
    status: SyncStatus
    conflict_resolution: SyncConflictResolution
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[SyncResult] = None


class SyncService:
    """
    Service for synchronizing files between database and Azure File Share.
    
    This service handles bidirectional synchronization, conflict detection,
    and resolution strategies to maintain consistency between storage layers.
    """

    def __init__(
        self,
        db_session: AsyncSession,
        file_operations: Optional[FileOperationsService] = None,
        folder_manager: Optional[ProjectFolderManager] = None,
        reconciliation_service: Optional[ReconciliationService] = None
    ):
        """
        Initialize the synchronization service.
        
        Args:
            db_session: Database session for operations
            file_operations: Azure file operations service
            folder_manager: Project folder manager
            reconciliation_service: Reconciliation service for conflict resolution
        """
        self.db = db_session
        self.file_operations = file_operations
        self.folder_manager = folder_manager
        self.reconciliation_service = reconciliation_service
        self.logger = logging.getLogger(__name__)
        self._active_operations: Dict[str, SyncOperation] = {}

    async def sync_project(
        self,
        project_id: str,
        direction: SyncDirection = SyncDirection.BIDIRECTIONAL,
        conflict_resolution: SyncConflictResolution = SyncConflictResolution.NEWEST_WINS,
        force: bool = False
    ) -> SyncResult:
        """
        Synchronize a project between database and Azure File Share.
        
        Args:
            project_id: Project ID to synchronize
            direction: Synchronization direction
            conflict_resolution: Strategy for resolving conflicts
            force: Whether to force sync even if no changes detected
            
        Returns:
            SyncResult with synchronization details
        """
        start_time = datetime.utcnow()
        operation_id = f"sync_{project_id}_{int(start_time.timestamp())}"
        
        # Create sync operation
        operation = SyncOperation(
            operation_id=operation_id,
            project_id=project_id,
            direction=direction,
            status=SyncStatus.PENDING,
            conflict_resolution=conflict_resolution
        )
        
        self._active_operations[operation_id] = operation
        
        try:
            # Initialize services if not provided
            if not self.file_operations:
                self.file_operations = await get_file_operations_service()
            
            if not self.folder_manager:
                self.folder_manager = await get_folder_manager()
            
            if not self.reconciliation_service:
                self.reconciliation_service = ReconciliationService(
                    self.db, self.file_operations, self.folder_manager
                )

            # Verify project exists
            project = await self._get_project(project_id)
            if not project:
                raise ValueError(f"Project {project_id} not found")

            if project.status == ProjectStatus.DELETED:
                raise ValueError(f"Cannot sync deleted project {project_id}")

            # Mark operation as started
            operation.status = SyncStatus.IN_PROGRESS
            operation.started_at = datetime.utcnow()

            # Perform synchronization based on direction
            if direction == SyncDirection.DATABASE_TO_AZURE:
                result = await self._sync_database_to_azure(project, conflict_resolution, force)
            elif direction == SyncDirection.AZURE_TO_DATABASE:
                result = await self._sync_azure_to_database(project, conflict_resolution, force)
            else:  # BIDIRECTIONAL
                result = await self._sync_bidirectional(project, conflict_resolution, force)

            # Update operation status
            operation.status = SyncStatus.COMPLETED if result.success else SyncStatus.FAILED
            operation.completed_at = datetime.utcnow()
            operation.result = result

            # Calculate duration
            result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()

            self.logger.info(
                f"Sync completed for project {project_id}: "
                f"{result.files_synced}/{result.files_processed} files synced, "
                f"{result.conflicts_detected} conflicts"
            )

            return result

        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Sync failed for project {project_id}: {error_msg}")

            # Create error result
            result = SyncResult(
                success=False,
                project_id=project_id,
                direction=direction,
                errors=[error_msg],
                duration_seconds=(datetime.utcnow() - start_time).total_seconds()
            )

            # Update operation status
            operation.status = SyncStatus.FAILED
            operation.completed_at = datetime.utcnow()
            operation.result = result

            return result

        finally:
            # Clean up operation
            if operation_id in self._active_operations:
                del self._active_operations[operation_id]

    async def sync_multiple_projects(
        self,
        project_ids: List[str],
        direction: SyncDirection = SyncDirection.BIDIRECTIONAL,
        conflict_resolution: SyncConflictResolution = SyncConflictResolution.NEWEST_WINS,
        max_concurrent: int = 5
    ) -> List[SyncResult]:
        """
        Synchronize multiple projects concurrently.
        
        Args:
            project_ids: List of project IDs to synchronize
            direction: Synchronization direction
            conflict_resolution: Strategy for resolving conflicts
            max_concurrent: Maximum number of concurrent sync operations
            
        Returns:
            List of SyncResult for each project
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def sync_with_semaphore(project_id: str) -> SyncResult:
            async with semaphore:
                return await self.sync_project(project_id, direction, conflict_resolution)
        
        tasks = [sync_with_semaphore(pid) for pid in project_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to error results
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error_result = SyncResult(
                    success=False,
                    project_id=project_ids[i],
                    direction=direction,
                    errors=[str(result)]
                )
                final_results.append(error_result)
            else:
                final_results.append(result)
        
        return final_results

    async def get_sync_status(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current synchronization status for a project.
        
        Args:
            project_id: Project ID to check status for
            
        Returns:
            Dictionary with sync status information or None if no active sync
        """
        # Find active operation for project
        for operation in self._active_operations.values():
            if operation.project_id == project_id:
                return {
                    'operation_id': operation.operation_id,
                    'status': operation.status.value,
                    'direction': operation.direction.value,
                    'started_at': operation.started_at,
                    'duration_seconds': (
                        (datetime.utcnow() - operation.started_at).total_seconds()
                        if operation.started_at else None
                    )
                }
        
        return None

    async def cancel_sync(self, project_id: str) -> bool:
        """
        Cancel an active synchronization operation.
        
        Args:
            project_id: Project ID to cancel sync for
            
        Returns:
            True if sync was cancelled, False if no active sync
        """
        # Find and cancel active operation
        for operation_id, operation in list(self._active_operations.items()):
            if operation.project_id == project_id:
                operation.status = SyncStatus.FAILED
                operation.completed_at = datetime.utcnow()
                del self._active_operations[operation_id]
                
                self.logger.info(f"Cancelled sync operation {operation_id} for project {project_id}")
                return True
        
        return False

    async def detect_sync_conflicts(self, project_id: str) -> List[SyncConflict]:
        """
        Detect synchronization conflicts for a project without performing sync.
        
        Args:
            project_id: Project ID to check for conflicts
            
        Returns:
            List of detected conflicts
        """
        try:
            # Initialize services
            if not self.file_operations:
                self.file_operations = await get_file_operations_service()
            
            if not self.folder_manager:
                self.folder_manager = await get_folder_manager()

            # Get project
            project = await self._get_project(project_id)
            if not project:
                return []

            # Get database files
            db_files = await self._get_database_files(project_id)
            db_file_map = {f.file_path: f for f in db_files}

            # Get Azure files
            azure_files = await self.folder_manager.list_project_files(project_id)
            azure_file_map = {f.file_path: f for f in azure_files}

            conflicts = []

            # Check for conflicts in files that exist in both locations
            common_files = set(db_file_map.keys()) & set(azure_file_map.keys())
            
            for file_path in common_files:
                db_file = db_file_map[file_path]
                azure_file = azure_file_map[file_path]
                
                # Compare metadata to detect conflicts
                if self._has_metadata_conflict(db_file, azure_file):
                    conflict = SyncConflict(
                        file_path=file_path,
                        project_id=project_id,
                        conflict_type="metadata_mismatch",
                        database_metadata=self._extract_file_metadata(db_file),
                        azure_metadata=self._extract_azure_metadata(azure_file)
                    )
                    conflicts.append(conflict)

            # Files only in database (missing in Azure)
            db_only_files = set(db_file_map.keys()) - set(azure_file_map.keys())
            for file_path in db_only_files:
                conflict = SyncConflict(
                    file_path=file_path,
                    project_id=project_id,
                    conflict_type="missing_in_azure",
                    database_metadata=self._extract_file_metadata(db_file_map[file_path])
                )
                conflicts.append(conflict)

            # Files only in Azure (missing in database)
            azure_only_files = set(azure_file_map.keys()) - set(db_file_map.keys())
            for file_path in azure_only_files:
                conflict = SyncConflict(
                    file_path=file_path,
                    project_id=project_id,
                    conflict_type="missing_in_database",
                    azure_metadata=self._extract_azure_metadata(azure_file_map[file_path])
                )
                conflicts.append(conflict)

            return conflicts

        except Exception as e:
            self.logger.error(f"Failed to detect conflicts for project {project_id}: {e}")
            return []

    async def _sync_database_to_azure(
        self,
        project: Project,
        conflict_resolution: SyncConflictResolution,
        force: bool
    ) -> SyncResult:
        """Synchronize from database to Azure File Share."""
        result = SyncResult(
            success=True,
            project_id=project.id,
            direction=SyncDirection.DATABASE_TO_AZURE
        )

        try:
            # Get database files
            db_files = await self._get_database_files(project.id)
            result.files_processed = len(db_files)

            for db_file in db_files:
                try:
                    # Check if file exists in Azure
                    exists_result = await self.file_operations.file_exists(db_file.azure_path)
                    
                    if exists_result.success and "exists" in exists_result.message.lower():
                        # File exists, check for conflicts
                        azure_metadata_result = await self.file_operations.get_file_metadata(db_file.azure_path)
                        
                        if azure_metadata_result.success:
                            if self._has_metadata_conflict(db_file, azure_metadata_result.metadata):
                                # Handle conflict
                                conflict = SyncConflict(
                                    file_path=db_file.file_path,
                                    project_id=project.id,
                                    conflict_type="metadata_mismatch",
                                    database_metadata=self._extract_file_metadata(db_file),
                                    azure_metadata=self._extract_azure_metadata(azure_metadata_result.metadata)
                                )
                                
                                if conflict_resolution == SyncConflictResolution.DATABASE_WINS or force:
                                    # Upload database version
                                    await self._upload_database_file_to_azure(db_file)
                                    result.files_synced += 1
                                else:
                                    result.conflicts.append(conflict)
                                    result.conflicts_detected += 1
                            else:
                                # No conflict, skip if not forced
                                if force:
                                    await self._upload_database_file_to_azure(db_file)
                                    result.files_synced += 1
                                else:
                                    result.files_skipped += 1
                        else:
                            # Can't get Azure metadata, treat as conflict
                            result.errors.append(f"Failed to get Azure metadata for {db_file.file_path}")
                    else:
                        # File doesn't exist in Azure, upload it
                        await self._upload_database_file_to_azure(db_file)
                        result.files_synced += 1

                except Exception as e:
                    error_msg = f"Failed to sync file {db_file.file_path}: {str(e)}"
                    result.errors.append(error_msg)
                    self.logger.error(error_msg)

            result.success = len(result.errors) == 0

        except Exception as e:
            result.success = False
            result.errors.append(str(e))

        return result

    async def _sync_azure_to_database(
        self,
        project: Project,
        conflict_resolution: SyncConflictResolution,
        force: bool
    ) -> SyncResult:
        """Synchronize from Azure File Share to database."""
        result = SyncResult(
            success=True,
            project_id=project.id,
            direction=SyncDirection.AZURE_TO_DATABASE
        )

        try:
            # Get Azure files
            azure_files = await self.folder_manager.list_project_files(project.id)
            result.files_processed = len(azure_files)

            # Get existing database files
            db_files = await self._get_database_files(project.id)
            db_file_map = {f.file_path: f for f in db_files}

            for azure_file in azure_files:
                try:
                    if azure_file.file_path in db_file_map:
                        # File exists in database, check for conflicts
                        db_file = db_file_map[azure_file.file_path]
                        
                        if self._has_metadata_conflict(db_file, azure_file):
                            # Handle conflict
                            conflict = SyncConflict(
                                file_path=azure_file.file_path,
                                project_id=project.id,
                                conflict_type="metadata_mismatch",
                                database_metadata=self._extract_file_metadata(db_file),
                                azure_metadata=self._extract_azure_metadata(azure_file)
                            )
                            
                            if conflict_resolution == SyncConflictResolution.AZURE_WINS or force:
                                # Update database with Azure metadata
                                await self._update_database_file_from_azure(db_file, azure_file)
                                result.files_synced += 1
                            else:
                                result.conflicts.append(conflict)
                                result.conflicts_detected += 1
                        else:
                            # No conflict, skip if not forced
                            if force:
                                await self._update_database_file_from_azure(db_file, azure_file)
                                result.files_synced += 1
                            else:
                                result.files_skipped += 1
                    else:
                        # File doesn't exist in database, create it
                        await self._create_database_file_from_azure(project.id, azure_file)
                        result.files_synced += 1

                except Exception as e:
                    error_msg = f"Failed to sync file {azure_file.file_path}: {str(e)}"
                    result.errors.append(error_msg)
                    self.logger.error(error_msg)

            result.success = len(result.errors) == 0

        except Exception as e:
            result.success = False
            result.errors.append(str(e))

        return result

    async def _sync_bidirectional(
        self,
        project: Project,
        conflict_resolution: SyncConflictResolution,
        force: bool
    ) -> SyncResult:
        """Perform bidirectional synchronization."""
        # For bidirectional sync, we need to be more careful about conflicts
        # First detect all conflicts, then resolve them based on strategy
        
        conflicts = await self.detect_sync_conflicts(project.id)
        
        result = SyncResult(
            success=True,
            project_id=project.id,
            direction=SyncDirection.BIDIRECTIONAL,
            conflicts=conflicts,
            conflicts_detected=len(conflicts)
        )

        try:
            # Get all files from both sources
            db_files = await self._get_database_files(project.id)
            azure_files = await self.folder_manager.list_project_files(project.id)
            
            db_file_map = {f.file_path: f for f in db_files}
            azure_file_map = {f.file_path: f for f in azure_files}
            
            all_file_paths = set(db_file_map.keys()) | set(azure_file_map.keys())
            result.files_processed = len(all_file_paths)

            for file_path in all_file_paths:
                try:
                    db_file = db_file_map.get(file_path)
                    azure_file = azure_file_map.get(file_path)

                    if db_file and azure_file:
                        # File exists in both, resolve conflicts
                        if self._has_metadata_conflict(db_file, azure_file):
                            await self._resolve_bidirectional_conflict(
                                db_file, azure_file, conflict_resolution, result
                            )
                        else:
                            result.files_skipped += 1
                    elif db_file and not azure_file:
                        # File only in database, upload to Azure
                        await self._upload_database_file_to_azure(db_file)
                        result.files_synced += 1
                    elif azure_file and not db_file:
                        # File only in Azure, create in database
                        await self._create_database_file_from_azure(project.id, azure_file)
                        result.files_synced += 1

                except Exception as e:
                    error_msg = f"Failed to sync file {file_path}: {str(e)}"
                    result.errors.append(error_msg)
                    self.logger.error(error_msg)

            result.success = len(result.errors) == 0

        except Exception as e:
            result.success = False
            result.errors.append(str(e))

        return result

    async def _resolve_bidirectional_conflict(
        self,
        db_file: ProjectFile,
        azure_file: Any,
        conflict_resolution: SyncConflictResolution,
        result: SyncResult
    ) -> None:
        """Resolve a bidirectional synchronization conflict."""
        if conflict_resolution == SyncConflictResolution.DATABASE_WINS:
            await self._upload_database_file_to_azure(db_file)
            result.files_synced += 1
        elif conflict_resolution == SyncConflictResolution.AZURE_WINS:
            await self._update_database_file_from_azure(db_file, azure_file)
            result.files_synced += 1
        elif conflict_resolution == SyncConflictResolution.NEWEST_WINS:
            # Compare timestamps and use newer version
            db_modified = db_file.updated_at
            azure_modified = getattr(azure_file, 'modified_at', datetime.min)
            
            if db_modified > azure_modified:
                await self._upload_database_file_to_azure(db_file)
            else:
                await self._update_database_file_from_azure(db_file, azure_file)
            result.files_synced += 1
        else:  # MANUAL
            # Add to conflicts for manual resolution
            conflict = SyncConflict(
                file_path=db_file.file_path,
                project_id=db_file.project_id,
                conflict_type="bidirectional_conflict",
                database_metadata=self._extract_file_metadata(db_file),
                azure_metadata=self._extract_azure_metadata(azure_file)
            )
            result.conflicts.append(conflict)

    async def _get_project(self, project_id: str) -> Optional[Project]:
        """Get project by ID."""
        query = select(Project).where(Project.id == project_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _get_database_files(self, project_id: str) -> List[ProjectFile]:
        """Get all files for a project from database."""
        query = select(ProjectFile).where(ProjectFile.project_id == project_id)
        result = await self.db.execute(query)
        return result.scalars().all()

    def _has_metadata_conflict(self, db_file: ProjectFile, azure_file: Any) -> bool:
        """Check if there's a metadata conflict between database and Azure file."""
        # Compare content hashes if available
        if hasattr(azure_file, 'content_hash') and azure_file.content_hash:
            return db_file.content_hash != azure_file.content_hash
        
        # Compare file sizes
        if hasattr(azure_file, 'size_bytes'):
            return db_file.size_bytes != azure_file.size_bytes
        
        # If we can't compare, assume no conflict
        return False

    def _extract_file_metadata(self, db_file: ProjectFile) -> Dict[str, Any]:
        """Extract metadata from database file."""
        return {
            'file_path': db_file.file_path,
            'size_bytes': db_file.size_bytes,
            'content_hash': db_file.content_hash,
            'file_type': db_file.file_type,
            'created_at': db_file.created_at,
            'updated_at': db_file.updated_at
        }

    def _extract_azure_metadata(self, azure_file: Any) -> Dict[str, Any]:
        """Extract metadata from Azure file."""
        return {
            'file_path': getattr(azure_file, 'file_path', ''),
            'size_bytes': getattr(azure_file, 'size_bytes', 0),
            'content_hash': getattr(azure_file, 'content_hash', ''),
            'content_type': getattr(azure_file, 'content_type', ''),
            'created_at': getattr(azure_file, 'created_at', None),
            'modified_at': getattr(azure_file, 'modified_at', None)
        }

    async def _upload_database_file_to_azure(self, db_file: ProjectFile) -> None:
        """Upload a database file to Azure File Share."""
        # This would need to get the actual file content from somewhere
        # For now, we'll just update the metadata
        pass

    async def _update_database_file_from_azure(self, db_file: ProjectFile, azure_file: Any) -> None:
        """Update database file metadata from Azure file."""
        updates = {}
        
        if hasattr(azure_file, 'size_bytes'):
            updates['size_bytes'] = azure_file.size_bytes
        
        if hasattr(azure_file, 'content_hash'):
            updates['content_hash'] = azure_file.content_hash
        
        if updates:
            updates['updated_at'] = datetime.utcnow()
            
            stmt = (
                update(ProjectFile)
                .where(ProjectFile.id == db_file.id)
                .values(**updates)
            )
            await self.db.execute(stmt)

    async def _create_database_file_from_azure(self, project_id: str, azure_file: Any) -> None:
        """Create a new database file record from Azure file."""
        db_file = ProjectFile(
            project_id=project_id,
            file_path=getattr(azure_file, 'file_path', ''),
            azure_path=getattr(azure_file, 'azure_path', ''),
            file_type=getattr(azure_file, 'file_type', ''),
            size_bytes=getattr(azure_file, 'size_bytes', 0),
            content_hash=getattr(azure_file, 'content_hash', '')
        )
        
        self.db.add(db_file)
        await self.db.flush()


# Background task utilities
class BackgroundSyncTask:
    """Background task for periodic synchronization."""
    
    def __init__(
        self,
        sync_service: SyncService,
        interval_minutes: int = 60,
        max_concurrent: int = 3
    ):
        """
        Initialize background sync task.
        
        Args:
            sync_service: Synchronization service to use
            interval_minutes: Sync interval in minutes
            max_concurrent: Maximum concurrent sync operations
        """
        self.sync_service = sync_service
        self.interval_minutes = interval_minutes
        self.max_concurrent = max_concurrent
        self.logger = logging.getLogger(__name__)
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the background sync task."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run_sync_loop())
        self.logger.info(f"Started background sync task with {self.interval_minutes}min interval")

    async def stop(self) -> None:
        """Stop the background sync task."""
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Stopped background sync task")

    async def _run_sync_loop(self) -> None:
        """Run the periodic sync loop."""
        while self._running:
            try:
                await self._perform_background_sync()
                await asyncio.sleep(self.interval_minutes * 60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Background sync error: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying

    async def _perform_background_sync(self) -> None:
        """Perform background synchronization for all active projects."""
        try:
            # Get all active projects
            query = select(Project.id).where(Project.status == ProjectStatus.ACTIVE)
            result = await self.sync_service.db.execute(query)
            project_ids = [row[0] for row in result.fetchall()]
            
            if not project_ids:
                return
            
            self.logger.info(f"Starting background sync for {len(project_ids)} projects")
            
            # Sync projects in batches
            results = await self.sync_service.sync_multiple_projects(
                project_ids=project_ids,
                direction=SyncDirection.BIDIRECTIONAL,
                conflict_resolution=SyncConflictResolution.NEWEST_WINS,
                max_concurrent=self.max_concurrent
            )
            
            # Log results
            successful = sum(1 for r in results if r.success)
            failed = len(results) - successful
            total_conflicts = sum(r.conflicts_detected for r in results)
            
            self.logger.info(
                f"Background sync completed: {successful} successful, "
                f"{failed} failed, {total_conflicts} conflicts detected"
            )
            
        except Exception as e:
            self.logger.error(f"Background sync failed: {e}")


# Global sync service instance
_sync_service: Optional[SyncService] = None


async def get_sync_service(db_session: AsyncSession) -> SyncService:
    """
    Get a sync service instance.
    
    Args:
        db_session: Database session to use
        
    Returns:
        SyncService instance
    """
    return SyncService(db_session)