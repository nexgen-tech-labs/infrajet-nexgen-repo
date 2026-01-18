"""
Enhanced Azure File Share Service with User-Scoped Operations.

This module provides user-scoped file operations for Azure File Share including
user isolation, project management, and file operations with user_id/project_id structure.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass, field

from azure.storage.fileshare.aio import ShareFileClient, ShareDirectoryClient
from azure.core.exceptions import (
    AzureError,
    ResourceNotFoundError,
    ResourceExistsError,
    HttpResponseError
)

from app.services.azure.connection import AzureConnectionManager, get_connection_manager
from app.services.azure.file_operations import (
    FileOperationsService, 
    FileOperationResult, 
    FileMetadata,
    FileOperationType
)
from app.services.azure.folder_manager import (
    ProjectFolderManager,
    FolderOperationResult,
    FolderInfo
)
from app.core.azure_config import AzureFileShareConfig, get_azure_config


@dataclass
class FileInfo:
    """File information with user and project context."""
    name: str
    path: str
    size: int
    modified_date: datetime
    project_id: str
    user_id: str
    generation_id: Optional[str] = None
    content_type: str = "text/plain"
    relative_path: str = ""  # Path relative to generation folder
    
    @classmethod
    def from_azure_metadata(
        cls, 
        metadata: FileMetadata, 
        user_id: str, 
        project_id: str, 
        generation_id: Optional[str] = None
    ) -> "FileInfo":
        """Create FileInfo from Azure FileMetadata."""
        # Extract relative path from full path
        path_parts = metadata.file_path.split("/")
        if len(path_parts) >= 4:  # projects/user_id/project_id/generation_id/file
            relative_path = "/".join(path_parts[4:])
        else:
            relative_path = Path(metadata.file_path).name
        
        return cls(
            name=Path(metadata.file_path).name,
            path=metadata.file_path,
            size=metadata.size_bytes,
            modified_date=metadata.modified_at,
            project_id=project_id,
            user_id=user_id,
            generation_id=generation_id,
            content_type=metadata.content_type,
            relative_path=relative_path
        )


@dataclass
class SaveResult:
    """Result of file save operation."""
    success: bool
    message: str
    saved_files: List[str] = field(default_factory=list)
    failed_files: List[str] = field(default_factory=list)
    azure_paths: List[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class ProjectInfo:
    """Project information with user context."""
    id: str
    name: str
    user_id: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    file_count: int = 0
    total_size: int = 0
    generation_count: int = 0
    last_generation_id: Optional[str] = None


class UserDirectoryManager:
    """Manages user-specific directory structure."""
    
    def __init__(self, config: Optional[AzureFileShareConfig] = None):
        """Initialize user directory manager."""
        self.config = config or get_azure_config()
        self.logger = logging.getLogger(__name__)
    
    def get_user_base_path(self, user_id: str) -> str:
        """Get the base path for a user."""
        return f"{self.config.AZURE_BASE_DIRECTORY}/{user_id}"
    
    def get_user_project_path(self, user_id: str, project_id: str) -> str:
        """Get the path for a user's project."""
        return f"{self.config.AZURE_BASE_DIRECTORY}/{user_id}/{project_id}"
    
    def get_user_generation_path(self, user_id: str, project_id: str, generation_id: str) -> str:
        """Get the path for a user's project generation."""
        return f"{self.config.AZURE_BASE_DIRECTORY}/{user_id}/{project_id}/{generation_id}"
    
    def get_user_file_path(self, user_id: str, project_id: str, generation_id: str, file_path: str) -> str:
        """Get the full path for a user's file."""
        file_path = file_path.lstrip("/")
        return f"{self.config.AZURE_BASE_DIRECTORY}/{user_id}/{project_id}/{generation_id}/{file_path}"
    
    def parse_user_file_path(self, full_path: str) -> Optional[Dict[str, str]]:
        """Parse a full file path to extract user, project, and generation info."""
        try:
            # Remove base directory prefix
            base_dir = self.config.AZURE_BASE_DIRECTORY
            if full_path.startswith(base_dir + "/"):
                relative_path = full_path[len(base_dir) + 1:]
            else:
                return None
            
            # Split path: user_id/project_id/generation_id/file_path
            parts = relative_path.split("/")
            if len(parts) >= 3:
                return {
                    "user_id": parts[0],
                    "project_id": parts[1],
                    "generation_id": parts[2],
                    "file_path": "/".join(parts[3:]) if len(parts) > 3 else ""
                }
            
            return None
        except Exception as e:
            self.logger.warning(f"Failed to parse user file path {full_path}: {e}")
            return None
    
    def validate_user_id(self, user_id: str) -> tuple[bool, Optional[str]]:
        """Validate user ID format."""
        if not user_id:
            return False, "User ID cannot be empty"
        
        if not user_id.replace("-", "").replace("_", "").isalnum():
            return False, "User ID can only contain letters, numbers, hyphens, and underscores"
        
        if len(user_id) > 100:
            return False, "User ID too long (max 100 characters)"
        
        return True, None
    
    def validate_project_id(self, project_id: str) -> tuple[bool, Optional[str]]:
        """Validate project ID format."""
        if not project_id:
            return False, "Project ID cannot be empty"
        
        try:
            # Try to parse as UUID
            uuid.UUID(project_id)
            return True, None
        except ValueError:
            return False, "Project ID must be a valid UUID"


class AzureFileService:
    """
    Enhanced Azure File Share service with user-scoped operations.
    
    This service provides user-isolated file operations with the directory structure:
    projects/{user_id}/{project_id}/{generation_id}/files
    """
    
    def __init__(self, connection_manager: Optional[AzureConnectionManager] = None):
        """Initialize Azure File Service."""
        self.connection_manager = connection_manager
        self.config = get_azure_config()
        self.directory_manager = UserDirectoryManager(self.config)
        self.file_operations = FileOperationsService(connection_manager)
        self.folder_manager = ProjectFolderManager(connection_manager)
        self.logger = logging.getLogger(__name__)
    
    async def save_generated_files(
        self,
        user_id: str,
        project_id: str,
        generation_id: str,
        files: Dict[str, str]
    ) -> SaveResult:
        """
        Save generated files to Azure File Share with user isolation.
        
        Args:
            user_id: User identifier from Supabase token
            project_id: Project identifier (UUID)
            generation_id: Generation identifier
            files: Dictionary of filename -> content
            
        Returns:
            SaveResult with operation results
        """
        try:
            # Validate inputs
            is_valid, error_msg = self.directory_manager.validate_user_id(user_id)
            if not is_valid:
                return SaveResult(
                    success=False,
                    message=f"Invalid user ID: {error_msg}",
                    error=error_msg
                )
            
            is_valid, error_msg = self.directory_manager.validate_project_id(project_id)
            if not is_valid:
                return SaveResult(
                    success=False,
                    message=f"Invalid project ID: {error_msg}",
                    error=error_msg
                )
            
            if not generation_id:
                return SaveResult(
                    success=False,
                    message="Generation ID cannot be empty",
                    error="Missing generation ID"
                )
            
            if not files:
                return SaveResult(
                    success=False,
                    message="No files to save",
                    error="Empty files dictionary"
                )
            
            # Ensure user project directory exists
            await self._ensure_user_project_directory(user_id, project_id)
            
            # Ensure generation directory exists
            generation_path = self.directory_manager.get_user_generation_path(
                user_id, project_id, generation_id
            )
            await self._ensure_directory_exists(generation_path)
            
            # Save files concurrently
            save_tasks = []
            for filename, content in files.items():
                file_path = self.directory_manager.get_user_file_path(
                    user_id, project_id, generation_id, filename
                )
                
                task = self.file_operations.upload_file(
                    file_path=file_path,
                    content=content,
                    overwrite=True,
                    metadata={
                        "user_id": user_id,
                        "project_id": project_id,
                        "generation_id": generation_id,
                        "filename": filename
                    }
                )
                save_tasks.append((filename, file_path, task))
            
            # Execute all save operations
            results = await asyncio.gather(
                *[task for _, _, task in save_tasks],
                return_exceptions=True
            )
            
            # Process results
            saved_files = []
            failed_files = []
            azure_paths = []
            
            for i, result in enumerate(results):
                filename, file_path, _ = save_tasks[i]
                
                if isinstance(result, Exception):
                    self.logger.error(f"Failed to save file {filename}: {result}")
                    failed_files.append(filename)
                elif isinstance(result, FileOperationResult) and result.success:
                    saved_files.append(filename)
                    azure_paths.append(file_path)
                else:
                    self.logger.error(f"Failed to save file {filename}: {result.error if hasattr(result, 'error') else 'Unknown error'}")
                    failed_files.append(filename)
            
            success = len(saved_files) > 0
            message = f"Saved {len(saved_files)} files"
            if failed_files:
                message += f", failed to save {len(failed_files)} files"
            
            self.logger.info(f"File save operation for user {user_id}, project {project_id}: {message}")
            
            return SaveResult(
                success=success,
                message=message,
                saved_files=saved_files,
                failed_files=failed_files,
                azure_paths=azure_paths,
                error=None if success else f"Failed to save {len(failed_files)} files"
            )
            
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Error saving files for user {user_id}, project {project_id}: {error_msg}")
            
            return SaveResult(
                success=False,
                message=f"Save operation failed: {error_msg}",
                error=error_msg
            )
    
    async def list_user_files(
        self,
        user_id: str,
        project_id: Optional[str] = None,
        generation_id: Optional[str] = None
    ) -> List[FileInfo]:
        """
        List files for a user with optional project and generation filtering.
        
        Args:
            user_id: User identifier
            project_id: Optional project filter
            generation_id: Optional generation filter (requires project_id)
            
        Returns:
            List of FileInfo objects
        """
        try:
            # Validate user ID
            is_valid, error_msg = self.directory_manager.validate_user_id(user_id)
            if not is_valid:
                self.logger.error(f"Invalid user ID: {error_msg}")
                return []
            
            files = []
            
            if project_id and generation_id:
                # List files in specific generation
                files = await self._list_generation_files(user_id, project_id, generation_id)
            elif project_id:
                # List all files in project
                files = await self._list_project_files(user_id, project_id)
            else:
                # List all files for user
                files = await self._list_all_user_files(user_id)
            
            self.logger.info(f"Listed {len(files)} files for user {user_id}")
            return files
            
        except Exception as e:
            self.logger.error(f"Error listing files for user {user_id}: {e}")
            return []
    
    async def get_file_content(
        self,
        user_id: str,
        project_id: str,
        generation_id: str,
        file_path: str
    ) -> Optional[str]:
        """
        Get content of a specific file.
        
        Args:
            user_id: User identifier
            project_id: Project identifier
            generation_id: Generation identifier
            file_path: Relative file path within generation
            
        Returns:
            File content as string or None if not found
        """
        try:
            # Validate inputs
            is_valid, error_msg = self.directory_manager.validate_user_id(user_id)
            if not is_valid:
                self.logger.error(f"Invalid user ID: {error_msg}")
                return None
            
            # Get full file path
            full_path = self.directory_manager.get_user_file_path(
                user_id, project_id, generation_id, file_path
            )
            
            # Download file
            result = await self.file_operations.download_file(full_path, as_text=True)
            
            if result.success and hasattr(result, 'content'):
                return result.content
            else:
                self.logger.warning(f"File not found or failed to download: {full_path}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting file content: {e}")
            return None
    
    async def create_project(
        self,
        user_id: str,
        project_id: str,
        project_name: str,
        description: Optional[str] = None
    ) -> bool:
        """
        Create a project directory for a user.
        
        Args:
            user_id: User identifier
            project_id: Project identifier (UUID)
            project_name: Human-readable project name
            description: Optional project description
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate inputs
            is_valid, error_msg = self.directory_manager.validate_user_id(user_id)
            if not is_valid:
                self.logger.error(f"Invalid user ID: {error_msg}")
                return False
            
            is_valid, error_msg = self.directory_manager.validate_project_id(project_id)
            if not is_valid:
                self.logger.error(f"Invalid project ID: {error_msg}")
                return False
            
            # Create project directory
            success = await self._ensure_user_project_directory(user_id, project_id)
            
            if success:
                self.logger.info(f"Created project {project_id} for user {user_id}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error creating project for user {user_id}: {e}")
            return False
    
    async def delete_project(
        self,
        user_id: str,
        project_id: str
    ) -> bool:
        """
        Delete a project and all its files for a user.
        
        Args:
            user_id: User identifier
            project_id: Project identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate inputs
            is_valid, error_msg = self.directory_manager.validate_user_id(user_id)
            if not is_valid:
                self.logger.error(f"Invalid user ID: {error_msg}")
                return False
            
            # Get project path
            project_path = self.directory_manager.get_user_project_path(user_id, project_id)
            
            # Delete project directory recursively
            if not self.connection_manager:
                self.connection_manager = await get_connection_manager()
            
            async with self.connection_manager.get_share_client() as share_client:
                directory_client = share_client.get_directory_client(project_path)
                
                try:
                    # Delete directory contents recursively
                    await self._delete_directory_recursive(directory_client)
                    await directory_client.delete_directory()
                    
                    self.logger.info(f"Deleted project {project_id} for user {user_id}")
                    return True
                    
                except ResourceNotFoundError:
                    self.logger.warning(f"Project {project_id} not found for user {user_id}")
                    return True  # Consider it successful if already deleted
                    
        except Exception as e:
            self.logger.error(f"Error deleting project {project_id} for user {user_id}: {e}")
            return False
    
    async def list_user_projects(self, user_id: str) -> List[ProjectInfo]:
        """
        List all projects for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of ProjectInfo objects
        """
        try:
            # Validate user ID
            is_valid, error_msg = self.directory_manager.validate_user_id(user_id)
            if not is_valid:
                self.logger.error(f"Invalid user ID: {error_msg}")
                return []
            
            # Get user base path
            user_path = self.directory_manager.get_user_base_path(user_id)
            
            # List user directories (projects)
            if not self.connection_manager:
                self.connection_manager = await get_connection_manager()
            
            projects = []
            
            try:
                async with self.connection_manager.get_share_client() as share_client:
                    directory_client = share_client.get_directory_client(user_path)
                    
                    async for item in directory_client.list_directories_and_files():
                        if item['is_directory']:
                            project_id = item['name']
                            
                            # Validate project ID format
                            is_valid, _ = self.directory_manager.validate_project_id(project_id)
                            if is_valid:
                                # Get project statistics
                                project_info = await self._get_project_info(user_id, project_id)
                                if project_info:
                                    projects.append(project_info)
                
            except ResourceNotFoundError:
                # User directory doesn't exist yet, return empty list
                pass
            
            self.logger.info(f"Listed {len(projects)} projects for user {user_id}")
            return projects
            
        except Exception as e:
            self.logger.error(f"Error listing projects for user {user_id}: {e}")
            return []
    
    # Private helper methods
    
    async def _ensure_user_project_directory(self, user_id: str, project_id: str) -> bool:
        """Ensure user project directory exists."""
        try:
            if not self.connection_manager:
                self.connection_manager = await get_connection_manager()
            
            # Ensure user base directory exists
            user_path = self.directory_manager.get_user_base_path(user_id)
            await self._ensure_directory_exists(user_path)
            
            # Ensure project directory exists
            project_path = self.directory_manager.get_user_project_path(user_id, project_id)
            await self._ensure_directory_exists(project_path)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to ensure user project directory: {e}")
            return False
    
    async def _ensure_directory_exists(self, directory_path: str) -> None:
        """Ensure a directory exists, creating it if necessary."""
        if not self.connection_manager:
            self.connection_manager = await get_connection_manager()
        
        async with self.connection_manager.get_share_client() as share_client:
            directory_client = share_client.get_directory_client(directory_path)
            
            try:
                await directory_client.create_directory()
            except ResourceExistsError:
                # Directory already exists, that's fine
                pass
    
    async def _delete_directory_recursive(self, directory_client: ShareDirectoryClient) -> None:
        """Recursively delete directory contents."""
        async for item in directory_client.list_directories_and_files():
            if item['is_directory']:
                # Recursively delete subdirectory
                sub_directory_client = directory_client.get_subdirectory_client(item['name'])
                await self._delete_directory_recursive(sub_directory_client)
                await sub_directory_client.delete_directory()
            else:
                # Delete file
                file_client = directory_client.get_file_client(item['name'])
                await file_client.delete_file()
    
    async def _list_generation_files(
        self,
        user_id: str,
        project_id: str,
        generation_id: str
    ) -> List[FileInfo]:
        """List files in a specific generation."""
        files = []
        generation_path = self.directory_manager.get_user_generation_path(
            user_id, project_id, generation_id
        )
        
        try:
            if not self.connection_manager:
                self.connection_manager = await get_connection_manager()
            
            async with self.connection_manager.get_share_client() as share_client:
                directory_client = share_client.get_directory_client(generation_path)
                
                async for item in directory_client.list_directories_and_files():
                    if not item['is_directory']:
                        file_path = f"{generation_path}/{item['name']}"
                        
                        # Get file metadata
                        file_client = share_client.get_file_client(file_path)
                        properties = await file_client.get_file_properties()
                        
                        # Create FileInfo
                        file_info = FileInfo(
                            name=item['name'],
                            path=file_path,
                            size=item.get('size', 0),
                            modified_date=properties.get('last_modified', datetime.utcnow()),
                            project_id=project_id,
                            user_id=user_id,
                            generation_id=generation_id,
                            relative_path=item['name']
                        )
                        files.append(file_info)
                        
        except ResourceNotFoundError:
            # Generation directory doesn't exist
            pass
        except Exception as e:
            self.logger.error(f"Error listing generation files: {e}")
        
        return files
    
    async def _list_project_files(self, user_id: str, project_id: str) -> List[FileInfo]:
        """List all files in a project across all generations."""
        files = []
        project_path = self.directory_manager.get_user_project_path(user_id, project_id)
        
        try:
            if not self.connection_manager:
                self.connection_manager = await get_connection_manager()
            
            async with self.connection_manager.get_share_client() as share_client:
                directory_client = share_client.get_directory_client(project_path)
                
                # List generations
                async for item in directory_client.list_directories_and_files():
                    if item['is_directory']:
                        generation_id = item['name']
                        generation_files = await self._list_generation_files(
                            user_id, project_id, generation_id
                        )
                        files.extend(generation_files)
                        
        except ResourceNotFoundError:
            # Project directory doesn't exist
            pass
        except Exception as e:
            self.logger.error(f"Error listing project files: {e}")
        
        return files
    
    async def _list_all_user_files(self, user_id: str) -> List[FileInfo]:
        """List all files for a user across all projects."""
        files = []
        user_path = self.directory_manager.get_user_base_path(user_id)
        
        try:
            if not self.connection_manager:
                self.connection_manager = await get_connection_manager()
            
            async with self.connection_manager.get_share_client() as share_client:
                directory_client = share_client.get_directory_client(user_path)
                
                # List projects
                async for item in directory_client.list_directories_and_files():
                    if item['is_directory']:
                        project_id = item['name']
                        
                        # Validate project ID format
                        is_valid, _ = self.directory_manager.validate_project_id(project_id)
                        if is_valid:
                            project_files = await self._list_project_files(user_id, project_id)
                            files.extend(project_files)
                        
        except ResourceNotFoundError:
            # User directory doesn't exist
            pass
        except Exception as e:
            self.logger.error(f"Error listing all user files: {e}")
        
        return files
    
    async def _get_project_info(self, user_id: str, project_id: str) -> Optional[ProjectInfo]:
        """Get project information including statistics."""
        try:
            project_path = self.directory_manager.get_user_project_path(user_id, project_id)
            
            if not self.connection_manager:
                self.connection_manager = await get_connection_manager()
            
            async with self.connection_manager.get_share_client() as share_client:
                directory_client = share_client.get_directory_client(project_path)
                
                # Get directory properties
                properties = await directory_client.get_directory_properties()
                
                # Count files and calculate statistics
                file_count = 0
                total_size = 0
                generation_count = 0
                last_generation_id = None
                latest_modified = None
                
                async for item in directory_client.list_directories_and_files():
                    if item['is_directory']:
                        generation_count += 1
                        generation_id = item['name']
                        
                        # Get generation files
                        generation_files = await self._list_generation_files(
                            user_id, project_id, generation_id
                        )
                        
                        file_count += len(generation_files)
                        total_size += sum(f.size for f in generation_files)
                        
                        # Track latest generation
                        if generation_files:
                            latest_file_modified = max(f.modified_date for f in generation_files)
                            if latest_modified is None or latest_file_modified > latest_modified:
                                latest_modified = latest_file_modified
                                last_generation_id = generation_id
                
                return ProjectInfo(
                    id=project_id,
                    name=project_id,  # Use project_id as name for now
                    user_id=user_id,
                    created_at=properties.get('creation_time'),
                    updated_at=latest_modified or properties.get('last_modified'),
                    file_count=file_count,
                    total_size=total_size,
                    generation_count=generation_count,
                    last_generation_id=last_generation_id
                )
                
        except Exception as e:
            self.logger.error(f"Error getting project info for {project_id}: {e}")
            return None


# Global service instance
_azure_file_service: Optional[AzureFileService] = None


async def get_azure_file_service() -> AzureFileService:
    """
    Get the global Azure File Service instance.
    
    Returns:
        AzureFileService: Global Azure File Service instance.
    """
    global _azure_file_service
    
    if _azure_file_service is None:
        connection_manager = await get_connection_manager()
        _azure_file_service = AzureFileService(connection_manager)
    
    return _azure_file_service