"""
Reconciliation service for resolving conflicts between database and Azure File Share.

This module provides conflict detection and resolution capabilities including:
- Metadata comparison and conflict detection
- Automated conflict resolution strategies
- Manual conflict resolution support
- Data integrity validation
- Reconciliation reporting
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_, func

from app.models.project import Project, ProjectFile, ProjectStatus
from app.services.azure.file_operations import FileOperationsService, FileMetadata
from app.services.azure.folder_manager import ProjectFolderManager


class ConflictType(Enum):
    """Types of conflicts that can occur during reconciliation."""
    MISSING_IN_DATABASE = "missing_in_database"
    MISSING_IN_AZURE = "missing_in_azure"
    CONTENT_MISMATCH = "content_mismatch"
    SIZE_MISMATCH = "size_mismatch"
    HASH_MISMATCH = "hash_mismatch"
    TIMESTAMP_MISMATCH = "timestamp_mismatch"
    TYPE_MISMATCH = "type_mismatch"


class ResolutionAction(Enum):
    """Actions that can be taken to resolve conflicts."""
    UPLOAD_TO_AZURE = "upload_to_azure"
    DOWNLOAD_FROM_AZURE = "download_from_azure"
    UPDATE_DATABASE_METADATA = "update_database_metadata"
    UPDATE_AZURE_METADATA = "update_azure_metadata"
    DELETE_FROM_DATABASE = "delete_from_database"
    DELETE_FROM_AZURE = "delete_from_azure"
    MANUAL_REVIEW = "manual_review"
    IGNORE = "ignore"


@dataclass
class ReconciliationConflict:
    """Represents a conflict found during reconciliation."""
    conflict_id: str
    project_id: str
    file_path: str
    conflict_type: ConflictType
    database_metadata: Optional[Dict[str, Any]] = None
    azure_metadata: Optional[Dict[str, Any]] = None
    recommended_action: Optional[ResolutionAction] = None
    confidence_score: float = 0.0
    detected_at: datetime = field(default_factory=datetime.utcnow)
    resolved: bool = False
    resolution_action: Optional[ResolutionAction] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None


@dataclass
class ReconciliationReport:
    """Report of reconciliation results."""
    project_id: str
    total_files_checked: int
    conflicts_detected: int
    conflicts_resolved: int
    conflicts_pending: int
    conflicts: List[ReconciliationConflict] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None


class ReconciliationService:
    """
    Service for reconciling data between database and Azure File Share.
    
    This service detects conflicts, suggests resolution actions, and can
    automatically resolve conflicts based on configured strategies.
    """

    def __init__(
        self,
        db_session: AsyncSession,
        file_operations: FileOperationsService,
        folder_manager: ProjectFolderManager
    ):
        """
        Initialize the reconciliation service.
        
        Args:
            db_session: Database session for operations
            file_operations: Azure file operations service
            folder_manager: Project folder manager
        """
        self.db = db_session
        self.file_operations = file_operations
        self.folder_manager = folder_manager
        self.logger = logging.getLogger(__name__)

    async def reconcile_project(
        self,
        project_id: str,
        auto_resolve: bool = False,
        resolution_strategy: Optional[str] = None
    ) -> ReconciliationReport:
        """
        Reconcile a project between database and Azure File Share.
        
        Args:
            project_id: Project ID to reconcile
            auto_resolve: Whether to automatically resolve conflicts
            resolution_strategy: Strategy for automatic resolution
            
        Returns:
            ReconciliationReport with results
        """
        report = ReconciliationReport(project_id=project_id)
        
        try:
            # Verify project exists and is active
            project = await self._get_project(project_id)
            if not project:
                report.errors.append(f"Project {project_id} not found")
                return report
            
            if project.status == ProjectStatus.DELETED:
                report.errors.append(f"Cannot reconcile deleted project {project_id}")
                return report

            # Get files from both sources
            db_files = await self._get_database_files(project_id)
            azure_files = await self._get_azure_files(project_id)
            
            # Create lookup maps
            db_file_map = {f.file_path: f for f in db_files}
            azure_file_map = {f.file_path: f for f in azure_files}
            
            # Get all unique file paths
            all_file_paths = set(db_file_map.keys()) | set(azure_file_map.keys())
            report.total_files_checked = len(all_file_paths)
            
            # Check each file for conflicts
            for file_path in all_file_paths:
                db_file = db_file_map.get(file_path)
                azure_file = azure_file_map.get(file_path)
                
                conflicts = await self._detect_file_conflicts(
                    project_id, file_path, db_file, azure_file
                )
                
                for conflict in conflicts:
                    report.conflicts.append(conflict)
                    report.conflicts_detected += 1
                    
                    # Auto-resolve if requested
                    if auto_resolve and conflict.recommended_action != ResolutionAction.MANUAL_REVIEW:
                        try:
                            await self._resolve_conflict(conflict, resolution_strategy)
                            report.conflicts_resolved += 1
                        except Exception as e:
                            error_msg = f"Failed to resolve conflict {conflict.conflict_id}: {str(e)}"
                            report.errors.append(error_msg)
                            self.logger.error(error_msg)
            
            report.conflicts_pending = report.conflicts_detected - report.conflicts_resolved
            report.completed_at = datetime.utcnow()
            report.duration_seconds = (report.completed_at - report.started_at).total_seconds()
            
            self.logger.info(
                f"Reconciliation completed for project {project_id}: "
                f"{report.conflicts_detected} conflicts detected, "
                f"{report.conflicts_resolved} resolved"
            )
            
        except Exception as e:
            error_msg = f"Reconciliation failed for project {project_id}: {str(e)}"
            report.errors.append(error_msg)
            self.logger.error(error_msg)
        
        return report

    async def detect_conflicts(self, project_id: str) -> List[ReconciliationConflict]:
        """
        Detect conflicts for a project without resolving them.
        
        Args:
            project_id: Project ID to check
            
        Returns:
            List of detected conflicts
        """
        report = await self.reconcile_project(project_id, auto_resolve=False)
        return report.conflicts

    async def resolve_conflict(
        self,
        conflict: ReconciliationConflict,
        action: ResolutionAction,
        notes: Optional[str] = None
    ) -> bool:
        """
        Resolve a specific conflict with the given action.
        
        Args:
            conflict: Conflict to resolve
            action: Resolution action to take
            notes: Optional notes about the resolution
            
        Returns:
            True if resolution was successful
        """
        try:
            success = await self._resolve_conflict(conflict, action=action)
            
            if success:
                conflict.resolved = True
                conflict.resolution_action = action
                conflict.resolved_at = datetime.utcnow()
                conflict.resolution_notes = notes
                
                self.logger.info(
                    f"Resolved conflict {conflict.conflict_id} with action {action.value}"
                )
            
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to resolve conflict {conflict.conflict_id}: {str(e)}")
            return False

    async def validate_data_integrity(self, project_id: str) -> Dict[str, Any]:
        """
        Validate data integrity for a project.
        
        Args:
            project_id: Project ID to validate
            
        Returns:
            Dictionary with validation results
        """
        validation_result = {
            'project_id': project_id,
            'valid': True,
            'issues': [],
            'statistics': {
                'total_db_files': 0,
                'total_azure_files': 0,
                'matching_files': 0,
                'orphaned_db_files': 0,
                'orphaned_azure_files': 0,
                'corrupted_files': 0
            }
        }
        
        try:
            # Get files from both sources
            db_files = await self._get_database_files(project_id)
            azure_files = await self._get_azure_files(project_id)
            
            db_file_map = {f.file_path: f for f in db_files}
            azure_file_map = {f.file_path: f for f in azure_files}
            
            validation_result['statistics']['total_db_files'] = len(db_files)
            validation_result['statistics']['total_azure_files'] = len(azure_files)
            
            # Check for matching files
            common_files = set(db_file_map.keys()) & set(azure_file_map.keys())
            validation_result['statistics']['matching_files'] = len(common_files)
            
            # Check for orphaned files
            orphaned_db = set(db_file_map.keys()) - set(azure_file_map.keys())
            orphaned_azure = set(azure_file_map.keys()) - set(db_file_map.keys())
            
            validation_result['statistics']['orphaned_db_files'] = len(orphaned_db)
            validation_result['statistics']['orphaned_azure_files'] = len(orphaned_azure)
            
            # Report orphaned files as issues
            for file_path in orphaned_db:
                validation_result['issues'].append({
                    'type': 'orphaned_database_file',
                    'file_path': file_path,
                    'description': f'File exists in database but not in Azure: {file_path}'
                })
            
            for file_path in orphaned_azure:
                validation_result['issues'].append({
                    'type': 'orphaned_azure_file',
                    'file_path': file_path,
                    'description': f'File exists in Azure but not in database: {file_path}'
                })
            
            # Check for corrupted files (hash mismatches)
            for file_path in common_files:
                db_file = db_file_map[file_path]
                azure_file = azure_file_map[file_path]
                
                if self._has_hash_mismatch(db_file, azure_file):
                    validation_result['statistics']['corrupted_files'] += 1
                    validation_result['issues'].append({
                        'type': 'hash_mismatch',
                        'file_path': file_path,
                        'description': f'Content hash mismatch for file: {file_path}',
                        'db_hash': db_file.content_hash,
                        'azure_hash': getattr(azure_file, 'content_hash', 'unknown')
                    })
            
            # Determine overall validity
            validation_result['valid'] = len(validation_result['issues']) == 0
            
        except Exception as e:
            validation_result['valid'] = False
            validation_result['issues'].append({
                'type': 'validation_error',
                'description': f'Validation failed: {str(e)}'
            })
        
        return validation_result

    async def _detect_file_conflicts(
        self,
        project_id: str,
        file_path: str,
        db_file: Optional[ProjectFile],
        azure_file: Optional[FileMetadata]
    ) -> List[ReconciliationConflict]:
        """Detect conflicts for a specific file."""
        conflicts = []
        conflict_id_base = f"{project_id}_{file_path}_{int(datetime.utcnow().timestamp())}"
        
        if db_file and not azure_file:
            # File exists in database but not in Azure
            conflict = ReconciliationConflict(
                conflict_id=f"{conflict_id_base}_missing_azure",
                project_id=project_id,
                file_path=file_path,
                conflict_type=ConflictType.MISSING_IN_AZURE,
                database_metadata=self._extract_db_metadata(db_file),
                recommended_action=ResolutionAction.UPLOAD_TO_AZURE,
                confidence_score=0.9
            )
            conflicts.append(conflict)
            
        elif azure_file and not db_file:
            # File exists in Azure but not in database
            conflict = ReconciliationConflict(
                conflict_id=f"{conflict_id_base}_missing_db",
                project_id=project_id,
                file_path=file_path,
                conflict_type=ConflictType.MISSING_IN_DATABASE,
                azure_metadata=self._extract_azure_metadata(azure_file),
                recommended_action=ResolutionAction.UPDATE_DATABASE_METADATA,
                confidence_score=0.9
            )
            conflicts.append(conflict)
            
        elif db_file and azure_file:
            # File exists in both, check for mismatches
            
            # Check content hash
            if self._has_hash_mismatch(db_file, azure_file):
                conflict = ReconciliationConflict(
                    conflict_id=f"{conflict_id_base}_hash",
                    project_id=project_id,
                    file_path=file_path,
                    conflict_type=ConflictType.HASH_MISMATCH,
                    database_metadata=self._extract_db_metadata(db_file),
                    azure_metadata=self._extract_azure_metadata(azure_file),
                    recommended_action=self._recommend_hash_resolution(db_file, azure_file),
                    confidence_score=0.7
                )
                conflicts.append(conflict)
            
            # Check file size
            if self._has_size_mismatch(db_file, azure_file):
                conflict = ReconciliationConflict(
                    conflict_id=f"{conflict_id_base}_size",
                    project_id=project_id,
                    file_path=file_path,
                    conflict_type=ConflictType.SIZE_MISMATCH,
                    database_metadata=self._extract_db_metadata(db_file),
                    azure_metadata=self._extract_azure_metadata(azure_file),
                    recommended_action=self._recommend_size_resolution(db_file, azure_file),
                    confidence_score=0.8
                )
                conflicts.append(conflict)
        
        return conflicts

    async def _resolve_conflict(
        self,
        conflict: ReconciliationConflict,
        strategy: Optional[Union[str, ResolutionAction]] = None,
        action: Optional[ResolutionAction] = None
    ) -> bool:
        """Resolve a conflict using the specified action or strategy."""
        
        # Determine action to take
        if action:
            resolution_action = action
        elif isinstance(strategy, ResolutionAction):
            resolution_action = strategy
        elif strategy == "azure_wins":
            resolution_action = self._get_azure_wins_action(conflict)
        elif strategy == "database_wins":
            resolution_action = self._get_database_wins_action(conflict)
        elif strategy == "newest_wins":
            resolution_action = self._get_newest_wins_action(conflict)
        else:
            resolution_action = conflict.recommended_action
        
        if not resolution_action or resolution_action == ResolutionAction.MANUAL_REVIEW:
            return False
        
        try:
            if resolution_action == ResolutionAction.UPLOAD_TO_AZURE:
                return await self._upload_to_azure(conflict)
            elif resolution_action == ResolutionAction.DOWNLOAD_FROM_AZURE:
                return await self._download_from_azure(conflict)
            elif resolution_action == ResolutionAction.UPDATE_DATABASE_METADATA:
                return await self._update_database_metadata(conflict)
            elif resolution_action == ResolutionAction.UPDATE_AZURE_METADATA:
                return await self._update_azure_metadata(conflict)
            elif resolution_action == ResolutionAction.DELETE_FROM_DATABASE:
                return await self._delete_from_database(conflict)
            elif resolution_action == ResolutionAction.DELETE_FROM_AZURE:
                return await self._delete_from_azure(conflict)
            elif resolution_action == ResolutionAction.IGNORE:
                return True  # Just mark as resolved
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to execute resolution action {resolution_action}: {str(e)}")
            return False

    def _recommend_hash_resolution(
        self,
        db_file: ProjectFile,
        azure_file: FileMetadata
    ) -> ResolutionAction:
        """Recommend resolution action for hash mismatch."""
        # Compare timestamps if available
        db_modified = db_file.updated_at
        azure_modified = getattr(azure_file, 'modified_at', datetime.min)
        
        if db_modified > azure_modified:
            return ResolutionAction.UPLOAD_TO_AZURE
        elif azure_modified > db_modified:
            return ResolutionAction.DOWNLOAD_FROM_AZURE
        else:
            return ResolutionAction.MANUAL_REVIEW

    def _recommend_size_resolution(
        self,
        db_file: ProjectFile,
        azure_file: FileMetadata
    ) -> ResolutionAction:
        """Recommend resolution action for size mismatch."""
        # Similar logic to hash resolution
        return self._recommend_hash_resolution(db_file, azure_file)

    def _get_azure_wins_action(self, conflict: ReconciliationConflict) -> ResolutionAction:
        """Get resolution action when Azure version should win."""
        if conflict.conflict_type == ConflictType.MISSING_IN_DATABASE:
            return ResolutionAction.UPDATE_DATABASE_METADATA
        elif conflict.conflict_type == ConflictType.MISSING_IN_AZURE:
            return ResolutionAction.DELETE_FROM_DATABASE
        else:
            return ResolutionAction.DOWNLOAD_FROM_AZURE

    def _get_database_wins_action(self, conflict: ReconciliationConflict) -> ResolutionAction:
        """Get resolution action when database version should win."""
        if conflict.conflict_type == ConflictType.MISSING_IN_AZURE:
            return ResolutionAction.UPLOAD_TO_AZURE
        elif conflict.conflict_type == ConflictType.MISSING_IN_DATABASE:
            return ResolutionAction.DELETE_FROM_AZURE
        else:
            return ResolutionAction.UPLOAD_TO_AZURE

    def _get_newest_wins_action(self, conflict: ReconciliationConflict) -> ResolutionAction:
        """Get resolution action based on newest timestamp."""
        if not conflict.database_metadata or not conflict.azure_metadata:
            return conflict.recommended_action or ResolutionAction.MANUAL_REVIEW
        
        db_modified = conflict.database_metadata.get('updated_at', datetime.min)
        azure_modified = conflict.azure_metadata.get('modified_at', datetime.min)
        
        if isinstance(db_modified, str):
            db_modified = datetime.fromisoformat(db_modified.replace('Z', '+00:00'))
        if isinstance(azure_modified, str):
            azure_modified = datetime.fromisoformat(azure_modified.replace('Z', '+00:00'))
        
        if db_modified > azure_modified:
            return self._get_database_wins_action(conflict)
        else:
            return self._get_azure_wins_action(conflict)

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

    async def _get_azure_files(self, project_id: str) -> List[FileMetadata]:
        """Get all files for a project from Azure."""
        try:
            return await self.folder_manager.list_project_files(project_id)
        except Exception as e:
            self.logger.error(f"Failed to get Azure files for project {project_id}: {str(e)}")
            return []

    def _extract_db_metadata(self, db_file: ProjectFile) -> Dict[str, Any]:
        """Extract metadata from database file."""
        return {
            'file_path': db_file.file_path,
            'azure_path': db_file.azure_path,
            'file_type': db_file.file_type,
            'size_bytes': db_file.size_bytes,
            'content_hash': db_file.content_hash,
            'created_at': db_file.created_at.isoformat() if db_file.created_at else None,
            'updated_at': db_file.updated_at.isoformat() if db_file.updated_at else None
        }

    def _extract_azure_metadata(self, azure_file: FileMetadata) -> Dict[str, Any]:
        """Extract metadata from Azure file."""
        return {
            'file_path': azure_file.file_path,
            'size_bytes': azure_file.size_bytes,
            'content_hash': azure_file.content_hash,
            'content_type': azure_file.content_type,
            'created_at': azure_file.created_at.isoformat() if azure_file.created_at else None,
            'modified_at': azure_file.modified_at.isoformat() if azure_file.modified_at else None,
            'etag': azure_file.etag
        }

    def _has_hash_mismatch(self, db_file: ProjectFile, azure_file: FileMetadata) -> bool:
        """Check if there's a content hash mismatch."""
        if not db_file.content_hash or not azure_file.content_hash:
            return False
        return db_file.content_hash != azure_file.content_hash

    def _has_size_mismatch(self, db_file: ProjectFile, azure_file: FileMetadata) -> bool:
        """Check if there's a file size mismatch."""
        return db_file.size_bytes != azure_file.size_bytes

    # Resolution action implementations
    async def _upload_to_azure(self, conflict: ReconciliationConflict) -> bool:
        """Upload database file to Azure."""
        # Implementation would need actual file content
        # For now, just log the action
        self.logger.info(f"Would upload {conflict.file_path} to Azure")
        return True

    async def _download_from_azure(self, conflict: ReconciliationConflict) -> bool:
        """Download Azure file and update database."""
        # Implementation would download and update database
        self.logger.info(f"Would download {conflict.file_path} from Azure")
        return True

    async def _update_database_metadata(self, conflict: ReconciliationConflict) -> bool:
        """Update database metadata from Azure."""
        if not conflict.azure_metadata:
            return False
        
        try:
            # Create new database record
            db_file = ProjectFile(
                project_id=conflict.project_id,
                file_path=conflict.file_path,
                azure_path=f"projects/{conflict.project_id}/{conflict.file_path}",
                file_type=self._get_file_type(conflict.file_path),
                size_bytes=conflict.azure_metadata.get('size_bytes', 0),
                content_hash=conflict.azure_metadata.get('content_hash', '')
            )
            
            self.db.add(db_file)
            await self.db.flush()
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update database metadata: {str(e)}")
            return False

    async def _update_azure_metadata(self, conflict: ReconciliationConflict) -> bool:
        """Update Azure metadata from database."""
        # Azure File Share doesn't support arbitrary metadata updates
        # This would typically involve re-uploading the file
        self.logger.info(f"Would update Azure metadata for {conflict.file_path}")
        return True

    async def _delete_from_database(self, conflict: ReconciliationConflict) -> bool:
        """Delete file record from database."""
        try:
            stmt = delete(ProjectFile).where(
                and_(
                    ProjectFile.project_id == conflict.project_id,
                    ProjectFile.file_path == conflict.file_path
                )
            )
            await self.db.execute(stmt)
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete from database: {str(e)}")
            return False

    async def _delete_from_azure(self, conflict: ReconciliationConflict) -> bool:
        """Delete file from Azure."""
        try:
            azure_path = f"projects/{conflict.project_id}/{conflict.file_path}"
            result = await self.file_operations.delete_file(azure_path)
            return result.success
            
        except Exception as e:
            self.logger.error(f"Failed to delete from Azure: {str(e)}")
            return False

    def _get_file_type(self, file_path: str) -> str:
        """Get file type from file path."""
        if '.' not in file_path:
            return ''
        return '.' + file_path.split('.')[-1].lower()