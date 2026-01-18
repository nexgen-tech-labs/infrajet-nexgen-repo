"""
Metadata synchronization module for Azure File Share and PostgreSQL database.

This module provides utilities for keeping database metadata in sync with Azure File Share
operations, handling conflicts, and ensuring data consistency through atomic transactions.
"""

import asyncio
import hashlib
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple, Any
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select, update, delete, and_, or_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.db.session import get_db
from app.models.project import Project, ProjectFile
from app.services.azure.file_operations import FileOperationsService
from app.exceptions.azure_exceptions import AzureFileShareError


logger = logging.getLogger(__name__)


class SyncConflictType(Enum):
    """Types of synchronization conflicts that can occur."""
    FILE_MODIFIED_BOTH = "file_modified_both"
    FILE_DELETED_AZURE_MODIFIED_DB = "file_deleted_azure_modified_db"
    FILE_DELETED_DB_MODIFIED_AZURE = "file_deleted_db_modified_azure"
    FILE_ADDED_BOTH_DIFFERENT = "file_added_both_different"
    METADATA_MISMATCH = "metadata_mismatch"


class SyncResolutionStrategy(Enum):
    """Strategies for resolving synchronization conflicts."""
    AZURE_WINS = "azure_wins"
    DATABASE_WINS = "database_wins"
    MERGE = "merge"
    MANUAL = "manual"
    SKIP = "skip"


@dataclass
class FileMetadata:
    """File metadata for synchronization operations."""
    file_path: str
    azure_path: str
    size_bytes: int
    content_hash: str
    last_modified: datetime
    file_type: str


@dataclass
class SyncConflict:
    """Represents a synchronization conflict between Azure and database."""
    conflict_type: SyncConflictType
    file_path: str
    azure_metadata: Optional[FileMetadata]
    db_metadata: Optional[Dict[str, Any]]
    resolution_strategy: Optional[SyncResolutionStrategy] = None
    resolved: bool = False


@dataclass
class SyncResult:
    """Result of a synchronization operation."""
    success: bool
    files_added: int = 0
    files_updated: int = 0
    files_deleted: int = 0
    conflicts: List[SyncConflict] = None
    errors: List[str] = None

    def __post_init__(self):
        if self.conflicts is None:
            self.conflicts = []
        if self.errors is None:
            self.errors = []


class AtomicTransactionManager:
    """Utility for managing atomic database transactions during sync operations."""
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self._savepoints: List[str] = []
    
    @asynccontextmanager
    async def atomic_operation(self, operation_name: str = None):
        """Create an atomic operation with automatic rollback on failure."""
        savepoint_name = operation_name or f"sync_op_{len(self._savepoints)}"
        
        try:
            # Create savepoint for nested transactions
            await self.db_session.begin_nested()
            self._savepoints.append(savepoint_name)
            
            logger.debug(f"Started atomic operation: {savepoint_name}")
            yield
            
            # Commit the nested transaction
            await self.db_session.commit()
            logger.debug(f"Committed atomic operation: {savepoint_name}")
            
        except Exception as e:
            # Rollback to savepoint on any error
            await self.db_session.rollback()
            logger.error(f"Rolled back atomic operation {savepoint_name}: {str(e)}")
            raise
        finally:
            if savepoint_name in self._savepoints:
                self._savepoints.remove(savepoint_name)


class ConflictResolver:
    """Utility for resolving synchronization conflicts."""
    
    def __init__(self, default_strategy: SyncResolutionStrategy = SyncResolutionStrategy.AZURE_WINS):
        self.default_strategy = default_strategy
        self._resolution_rules: Dict[SyncConflictType, SyncResolutionStrategy] = {
            SyncConflictType.FILE_MODIFIED_BOTH: SyncResolutionStrategy.AZURE_WINS,
            SyncConflictType.FILE_DELETED_AZURE_MODIFIED_DB: SyncResolutionStrategy.AZURE_WINS,
            SyncConflictType.FILE_DELETED_DB_MODIFIED_AZURE: SyncResolutionStrategy.DATABASE_WINS,
            SyncConflictType.FILE_ADDED_BOTH_DIFFERENT: SyncResolutionStrategy.AZURE_WINS,
            SyncConflictType.METADATA_MISMATCH: SyncResolutionStrategy.AZURE_WINS,
        }
    
    def get_resolution_strategy(self, conflict: SyncConflict) -> SyncResolutionStrategy:
        """Get the resolution strategy for a specific conflict."""
        if conflict.resolution_strategy:
            return conflict.resolution_strategy
        
        return self._resolution_rules.get(conflict.conflict_type, self.default_strategy)
    
    def set_resolution_rule(self, conflict_type: SyncConflictType, strategy: SyncResolutionStrategy):
        """Set a resolution rule for a specific conflict type."""
        self._resolution_rules[conflict_type] = strategy


class MetadataSyncManager:
    """
    Manages synchronization between Azure File Share and PostgreSQL database metadata.
    
    Provides atomic operations for keeping file metadata consistent between storage
    and database, with conflict resolution and error handling.
    """
    
    def __init__(
        self,
        azure_service: FileOperationsService,
        conflict_resolver: Optional[ConflictResolver] = None
    ):
        self.azure_service = azure_service
        self.conflict_resolver = conflict_resolver or ConflictResolver()
        self._sync_locks: Dict[str, asyncio.Lock] = {}
    
    async def _get_project_lock(self, project_id: str) -> asyncio.Lock:
        """Get or create a lock for a specific project."""
        if project_id not in self._sync_locks:
            self._sync_locks[project_id] = asyncio.Lock()
        return self._sync_locks[project_id]
    
    async def sync_project_metadata(
        self,
        project_id: str,
        db_session: AsyncSession,
        force_full_sync: bool = False
    ) -> SyncResult:
        """
        Synchronize metadata for a specific project between Azure and database.
        
        Args:
            project_id: The project to synchronize
            db_session: Database session for operations
            force_full_sync: If True, perform full reconciliation regardless of timestamps
            
        Returns:
            SyncResult with details of the synchronization operation
        """
        project_lock = await self._get_project_lock(project_id)
        
        async with project_lock:
            logger.info(f"Starting metadata sync for project {project_id}")
            
            try:
                # Get current state from both sources
                azure_files = await self._get_azure_file_metadata(project_id)
                db_files = await self._get_database_file_metadata(project_id, db_session)
                
                # Detect conflicts and changes
                conflicts, changes = await self._analyze_sync_differences(
                    azure_files, db_files, force_full_sync
                )
                
                # Apply changes atomically
                transaction_manager = AtomicTransactionManager(db_session)
                
                async with transaction_manager.atomic_operation("project_metadata_sync"):
                    result = await self._apply_sync_changes(
                        project_id, changes, conflicts, db_session
                    )
                
                logger.info(
                    f"Completed metadata sync for project {project_id}: "
                    f"{result.files_added} added, {result.files_updated} updated, "
                    f"{result.files_deleted} deleted, {len(result.conflicts)} conflicts"
                )
                
                return result
                
            except Exception as e:
                logger.error(f"Failed to sync metadata for project {project_id}: {str(e)}")
                return SyncResult(
                    success=False,
                    errors=[f"Sync failed: {str(e)}"]
                )
    
    async def _get_azure_file_metadata(self, project_id: str) -> Dict[str, FileMetadata]:
        """Get file metadata from Azure File Share."""
        try:
            azure_files = await self.azure_service.list_project_files(project_id)
            metadata_dict = {}
            
            for file_info in azure_files:
                # Calculate content hash if not provided
                content_hash = file_info.get('content_hash')
                if not content_hash:
                    try:
                        content = await self.azure_service.download_file(
                            project_id, file_info['file_path']
                        )
                        content_hash = hashlib.sha256(content.encode()).hexdigest()
                    except Exception as e:
                        logger.warning(
                            f"Could not calculate hash for {file_info['file_path']}: {str(e)}"
                        )
                        content_hash = "unknown"
                
                metadata = FileMetadata(
                    file_path=file_info['file_path'],
                    azure_path=file_info['azure_path'],
                    size_bytes=file_info['size_bytes'],
                    content_hash=content_hash,
                    last_modified=file_info['last_modified'],
                    file_type=file_info.get('file_type', self._get_file_type(file_info['file_path']))
                )
                metadata_dict[file_info['file_path']] = metadata
            
            return metadata_dict
            
        except AzureFileShareError as e:
            logger.error(f"Failed to get Azure file metadata for project {project_id}: {str(e)}")
            raise
    
    async def _get_database_file_metadata(
        self, project_id: str, db_session: AsyncSession
    ) -> Dict[str, Dict[str, Any]]:
        """Get file metadata from database."""
        try:
            query = select(ProjectFile).where(
                and_(
                    ProjectFile.project_id == project_id,
                    ProjectFile.deleted_at.is_(None)
                )
            )
            result = await db_session.execute(query)
            db_files = result.scalars().all()
            
            metadata_dict = {}
            for file_record in db_files:
                metadata_dict[file_record.file_path] = {
                    'id': file_record.id,
                    'file_path': file_record.file_path,
                    'azure_path': file_record.azure_path,
                    'size_bytes': file_record.size_bytes,
                    'content_hash': file_record.content_hash,
                    'file_type': file_record.file_type,
                    'created_at': file_record.created_at,
                    'updated_at': file_record.updated_at
                }
            
            return metadata_dict
            
        except SQLAlchemyError as e:
            logger.error(f"Failed to get database file metadata for project {project_id}: {str(e)}")
            raise
    
    async def _analyze_sync_differences(
        self,
        azure_files: Dict[str, FileMetadata],
        db_files: Dict[str, Dict[str, Any]],
        force_full_sync: bool
    ) -> Tuple[List[SyncConflict], Dict[str, Any]]:
        """Analyze differences between Azure and database metadata."""
        conflicts = []
        changes = {
            'add': [],
            'update': [],
            'delete': []
        }
        
        azure_paths = set(azure_files.keys())
        db_paths = set(db_files.keys())
        
        # Files only in Azure (need to add to database)
        for file_path in azure_paths - db_paths:
            changes['add'].append(azure_files[file_path])
        
        # Files only in database (need to delete from database)
        for file_path in db_paths - azure_paths:
            changes['delete'].append(db_files[file_path])
        
        # Files in both (check for conflicts or updates)
        for file_path in azure_paths & db_paths:
            azure_meta = azure_files[file_path]
            db_meta = db_files[file_path]
            
            # Check for content differences
            if azure_meta.content_hash != db_meta['content_hash']:
                if force_full_sync:
                    changes['update'].append(azure_meta)
                else:
                    # Potential conflict - both sides modified
                    conflict = SyncConflict(
                        conflict_type=SyncConflictType.FILE_MODIFIED_BOTH,
                        file_path=file_path,
                        azure_metadata=azure_meta,
                        db_metadata=db_meta
                    )
                    conflicts.append(conflict)
            
            # Check for metadata differences
            elif (azure_meta.size_bytes != db_meta['size_bytes'] or
                  azure_meta.file_type != db_meta['file_type']):
                conflict = SyncConflict(
                    conflict_type=SyncConflictType.METADATA_MISMATCH,
                    file_path=file_path,
                    azure_metadata=azure_meta,
                    db_metadata=db_meta
                )
                conflicts.append(conflict)
        
        return conflicts, changes
    
    async def _apply_sync_changes(
        self,
        project_id: str,
        changes: Dict[str, Any],
        conflicts: List[SyncConflict],
        db_session: AsyncSession
    ) -> SyncResult:
        """Apply synchronization changes to the database."""
        result = SyncResult(success=True)
        
        try:
            # Resolve conflicts first
            for conflict in conflicts:
                await self._resolve_conflict(conflict, project_id, db_session)
                result.conflicts.append(conflict)
            
            # Add new files
            for file_metadata in changes['add']:
                await self._add_file_to_database(project_id, file_metadata, db_session)
                result.files_added += 1
            
            # Update existing files
            for file_metadata in changes['update']:
                await self._update_file_in_database(project_id, file_metadata, db_session)
                result.files_updated += 1
            
            # Delete removed files
            for db_metadata in changes['delete']:
                await self._delete_file_from_database(db_metadata['id'], db_session)
                result.files_deleted += 1
            
            return result
            
        except Exception as e:
            result.success = False
            result.errors.append(f"Failed to apply sync changes: {str(e)}")
            raise
    
    async def _resolve_conflict(
        self,
        conflict: SyncConflict,
        project_id: str,
        db_session: AsyncSession
    ):
        """Resolve a synchronization conflict based on resolution strategy."""
        strategy = self.conflict_resolver.get_resolution_strategy(conflict)
        
        try:
            if strategy == SyncResolutionStrategy.AZURE_WINS:
                if conflict.azure_metadata:
                    await self._update_file_in_database(
                        project_id, conflict.azure_metadata, db_session
                    )
                else:
                    await self._delete_file_from_database(
                        conflict.db_metadata['id'], db_session
                    )
                conflict.resolved = True
                
            elif strategy == SyncResolutionStrategy.DATABASE_WINS:
                # Keep database version, no changes needed
                conflict.resolved = True
                
            elif strategy == SyncResolutionStrategy.SKIP:
                # Skip this conflict, leave as unresolved
                pass
                
            else:
                # Manual resolution required
                logger.warning(f"Manual resolution required for conflict: {conflict.file_path}")
        
        except Exception as e:
            logger.error(f"Failed to resolve conflict for {conflict.file_path}: {str(e)}")
            raise
    
    async def _add_file_to_database(
        self,
        project_id: str,
        file_metadata: FileMetadata,
        db_session: AsyncSession
    ):
        """Add a new file record to the database."""
        project_file = ProjectFile(
            project_id=project_id,
            file_path=file_metadata.file_path,
            azure_path=file_metadata.azure_path,
            file_type=file_metadata.file_type,
            size_bytes=file_metadata.size_bytes,
            content_hash=file_metadata.content_hash
        )
        
        db_session.add(project_file)
        await db_session.flush()
    
    async def _update_file_in_database(
        self,
        project_id: str,
        file_metadata: FileMetadata,
        db_session: AsyncSession
    ):
        """Update an existing file record in the database."""
        query = update(ProjectFile).where(
            and_(
                ProjectFile.project_id == project_id,
                ProjectFile.file_path == file_metadata.file_path
            )
        ).values(
            azure_path=file_metadata.azure_path,
            file_type=file_metadata.file_type,
            size_bytes=file_metadata.size_bytes,
            content_hash=file_metadata.content_hash,
            updated_at=datetime.utcnow()
        )
        
        await db_session.execute(query)
    
    async def _delete_file_from_database(self, file_id: int, db_session: AsyncSession):
        """Soft delete a file record from the database."""
        query = update(ProjectFile).where(
            ProjectFile.id == file_id
        ).values(
            deleted_at=datetime.utcnow()
        )
        
        await db_session.execute(query)
    
    def _get_file_type(self, file_path: str) -> str:
        """Extract file type from file path."""
        if '.' in file_path:
            return file_path.split('.')[-1].lower()
        return 'unknown'
    
    async def force_reconciliation(
        self,
        project_id: str,
        db_session: AsyncSession,
        resolution_strategy: SyncResolutionStrategy = SyncResolutionStrategy.AZURE_WINS
    ) -> SyncResult:
        """
        Force a full reconciliation between Azure and database for a project.
        
        This method performs a complete sync, resolving all conflicts according
        to the specified strategy.
        """
        logger.info(f"Starting force reconciliation for project {project_id}")
        
        # Temporarily override conflict resolution strategy
        original_strategy = self.conflict_resolver.default_strategy
        self.conflict_resolver.default_strategy = resolution_strategy
        
        try:
            result = await self.sync_project_metadata(
                project_id, db_session, force_full_sync=True
            )
            
            logger.info(f"Completed force reconciliation for project {project_id}")
            return result
            
        finally:
            # Restore original strategy
            self.conflict_resolver.default_strategy = original_strategy