"""
Azure File Share Project Folder Manager.

This module provides project folder management for Azure File Share including
UUID-based folder structure, listing, and cleanup operations.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List, Set
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from azure.storage.fileshare.aio import ShareDirectoryClient
from azure.core.exceptions import (
    AzureError,
    ResourceNotFoundError,
    ResourceExistsError,
    HttpResponseError
)

from app.services.azure.connection import AzureConnectionManager, get_connection_manager
from app.core.azure_config import AzureFileShareConfig, get_azure_config


class FolderOperationType(Enum):
    """Folder operation types for logging and monitoring."""
    CREATE = "create"
    LIST = "list"
    DELETE = "delete"
    EXISTS = "exists"
    CLEANUP = "cleanup"


@dataclass
class FolderInfo:
    """Information about a folder in Azure File Share."""
    path: str
    name: str
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    is_directory: bool = True
    size_bytes: int = 0
    file_count: int = 0
    subdirectory_count: int = 0
    properties: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_azure_properties(cls, path: str, properties: Dict[str, Any]) -> "FolderInfo":
        """Create FolderInfo from Azure directory properties."""
        name = Path(path).name
        return cls(
            path=path,
            name=name,
            created_at=properties.get("creation_time"),
            modified_at=properties.get("last_modified"),
            is_directory=properties.get("is_directory", True),
            properties=properties
        )


@dataclass
class FolderOperationResult:
    """Result of a folder operation."""
    success: bool
    operation: FolderOperationType
    folder_path: str
    message: str
    folder_info: Optional[FolderInfo] = None
    items: Optional[List[FolderInfo]] = None
    error: Optional[str] = None
    duration_seconds: Optional[float] = None


class FolderStructureManager:
    """Manages UUID-based folder structure utilities."""
    
    def __init__(self, config: Optional[AzureFileShareConfig] = None):
        """Initialize folder structure manager."""
        self.config = config or get_azure_config()
        self.logger = logging.getLogger(__name__)
    
    def generate_project_id(self) -> str:
        """
        Generate a new UUID-based project ID.
        
        Returns:
            String UUID for the project.
        """
        return str(uuid.uuid4())
    
    def validate_project_id(self, project_id: str) -> tuple[bool, Optional[str]]:
        """
        Validate a project ID format.
        
        Args:
            project_id: Project ID to validate.
            
        Returns:
            Tuple of (is_valid, error_message).
        """
        if not project_id:
            return False, "Project ID cannot be empty"
        
        try:
            # Try to parse as UUID
            uuid.UUID(project_id)
            return True, None
        except ValueError:
            return False, "Project ID must be a valid UUID"
    
    def get_project_folder_path(self, project_id: str) -> str:
        """
        Get the folder path for a project.
        
        Args:
            project_id: Project UUID.
            
        Returns:
            Full folder path for the project.
        """
        return self.config.get_project_path(project_id)
    
    def get_generation_folder_path(self, project_id: str, generation_hash: str) -> str:
        """
        Get the folder path for a specific generation.
        
        Args:
            project_id: Project UUID.
            generation_hash: Generation hash identifier.
            
        Returns:
            Full folder path for the generation.
        """
        return self.config.get_generation_path(project_id, generation_hash)
    
    def parse_project_path(self, folder_path: str) -> Optional[Dict[str, str]]:
        """
        Parse a folder path to extract project information.
        
        Args:
            folder_path: Folder path to parse.
            
        Returns:
            Dictionary with project_id and generation_hash if parseable, None otherwise.
        """
        try:
            # Remove base directory prefix
            base_dir = self.config.AZURE_BASE_DIRECTORY
            if folder_path.startswith(base_dir + "/"):
                relative_path = folder_path[len(base_dir) + 1:]
            elif folder_path.startswith(base_dir):
                relative_path = folder_path[len(base_dir):]
            else:
                relative_path = folder_path
            
            # Split path components
            parts = relative_path.strip("/").split("/")
            
            if len(parts) >= 1:
                project_id = parts[0]
                
                # Validate project ID
                is_valid, _ = self.validate_project_id(project_id)
                if not is_valid:
                    return None
                
                result = {"project_id": project_id}
                
                if len(parts) >= 2:
                    result["generation_hash"] = parts[1]
                
                return result
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Failed to parse project path {folder_path}: {e}")
            return None
    
    def generate_generation_hash(self, query: str, timestamp: Optional[datetime] = None) -> str:
        """
        Generate a hash for a code generation.
        
        Args:
            query: The generation query.
            timestamp: Optional timestamp (defaults to now).
            
        Returns:
            Generation hash string.
        """
        import hashlib
        
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        # Create hash from query and timestamp
        content = f"{query}_{timestamp.isoformat()}"
        hash_obj = hashlib.sha256(content.encode('utf-8'))
        return hash_obj.hexdigest()[:16]  # Use first 16 characters


class FolderListingService:
    """Service for listing folder contents."""
    
    def __init__(self, connection_manager: Optional[AzureConnectionManager] = None):
        """Initialize listing service."""
        self.connection_manager = connection_manager
        self.structure_manager = FolderStructureManager()
        self.logger = logging.getLogger(__name__)
    
    async def list_folder_contents(
        self,
        folder_path: str,
        recursive: bool = False,
        include_files: bool = True
    ) -> FolderOperationResult:
        """
        List contents of a folder.
        
        Args:
            folder_path: Path of the folder to list.
            recursive: Whether to list recursively.
            include_files: Whether to include files in the listing.
            
        Returns:
            FolderOperationResult with folder contents.
        """
        start_time = datetime.utcnow()
        
        try:
            # Get connection manager
            if not self.connection_manager:
                self.connection_manager = await get_connection_manager()
            
            # Get directory client
            async with self.connection_manager.get_share_client() as share_client:
                directory_client = share_client.get_directory_client(folder_path)
                
                # List directory contents
                items = []
                async for item in directory_client.list_directories_and_files():
                    item_path = f"{folder_path}/{item['name']}"
                    
                    if item['is_directory']:
                        # It's a directory
                        folder_info = FolderInfo(
                            path=item_path,
                            name=item['name'],
                            is_directory=True,
                            properties=item
                        )
                        items.append(folder_info)
                        
                        # Recurse if requested
                        if recursive:
                            sub_result = await self.list_folder_contents(
                                item_path, recursive=True, include_files=include_files
                            )
                            if sub_result.success and sub_result.items:
                                items.extend(sub_result.items)
                    
                    elif include_files:
                        # It's a file
                        file_info = FolderInfo(
                            path=item_path,
                            name=item['name'],
                            is_directory=False,
                            size_bytes=item.get('size', 0),
                            properties=item
                        )
                        items.append(file_info)
                
                duration = (datetime.utcnow() - start_time).total_seconds()
                
                self.logger.info(f"Listed folder contents: {folder_path} ({len(items)} items)")
                
                return FolderOperationResult(
                    success=True,
                    operation=FolderOperationType.LIST,
                    folder_path=folder_path,
                    message=f"Listed {len(items)} items",
                    items=items,
                    duration_seconds=duration
                )
                
        except ResourceNotFoundError:
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = f"Folder not found: {folder_path}"
            
            return FolderOperationResult(
                success=False,
                operation=FolderOperationType.LIST,
                folder_path=folder_path,
                message=error_msg,
                error="Folder not found",
                duration_seconds=duration
            )
            
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = str(e)
            
            self.logger.error(f"Failed to list folder contents {folder_path}: {error_msg}")
            
            return FolderOperationResult(
                success=False,
                operation=FolderOperationType.LIST,
                folder_path=folder_path,
                message=f"Listing failed: {error_msg}",
                error=error_msg,
                duration_seconds=duration
            )
    
    async def list_projects(self) -> FolderOperationResult:
        """
        List all projects in the base directory.
        
        Returns:
            FolderOperationResult with project folders.
        """
        base_path = self.structure_manager.config.AZURE_BASE_DIRECTORY
        
        result = await self.list_folder_contents(base_path, recursive=False, include_files=False)
        
        if result.success and result.items:
            # Filter to only valid project folders
            project_folders = []
            for item in result.items:
                if item.is_directory:
                    project_info = self.structure_manager.parse_project_path(item.path)
                    if project_info:
                        # Add project info to folder info
                        item.properties.update(project_info)
                        project_folders.append(item)
            
            result.items = project_folders
            result.message = f"Found {len(project_folders)} projects"
        
        return result
    
    async def list_project_generations(self, project_id: str) -> FolderOperationResult:
        """
        List all generations for a project.
        
        Args:
            project_id: Project UUID.
            
        Returns:
            FolderOperationResult with generation folders.
        """
        # Validate project ID
        is_valid, error_msg = self.structure_manager.validate_project_id(project_id)
        if not is_valid:
            return FolderOperationResult(
                success=False,
                operation=FolderOperationType.LIST,
                folder_path="",
                message=f"Invalid project ID: {error_msg}",
                error=error_msg
            )
        
        project_path = self.structure_manager.get_project_folder_path(project_id)
        
        result = await self.list_folder_contents(project_path, recursive=False, include_files=False)
        
        if result.success and result.items:
            # Add generation info to folder info
            for item in result.items:
                if item.is_directory:
                    item.properties["project_id"] = project_id
                    item.properties["generation_hash"] = item.name
        
        return result


class FolderCleanupService:
    """Service for folder cleanup operations."""
    
    def __init__(self, connection_manager: Optional[AzureConnectionManager] = None):
        """Initialize cleanup service."""
        self.connection_manager = connection_manager
        self.structure_manager = FolderStructureManager()
        self.listing_service = FolderListingService(connection_manager)
        self.logger = logging.getLogger(__name__)
    
    async def delete_folder(
        self,
        folder_path: str,
        recursive: bool = False
    ) -> FolderOperationResult:
        """
        Delete a folder and optionally its contents.
        
        Args:
            folder_path: Path of the folder to delete.
            recursive: Whether to delete contents recursively.
            
        Returns:
            FolderOperationResult with deletion result.
        """
        start_time = datetime.utcnow()
        
        try:
            # Get connection manager
            if not self.connection_manager:
                self.connection_manager = await get_connection_manager()
            
            # Get directory client
            async with self.connection_manager.get_share_client() as share_client:
                directory_client = share_client.get_directory_client(folder_path)
                
                if recursive:
                    # Delete contents first
                    await self._delete_folder_contents(directory_client)
                
                # Delete the directory itself
                await directory_client.delete_directory()
                
                duration = (datetime.utcnow() - start_time).total_seconds()
                
                self.logger.info(f"Deleted folder: {folder_path}")
                
                return FolderOperationResult(
                    success=True,
                    operation=FolderOperationType.DELETE,
                    folder_path=folder_path,
                    message="Folder deleted successfully",
                    duration_seconds=duration
                )
                
        except ResourceNotFoundError:
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = f"Folder not found: {folder_path}"
            
            return FolderOperationResult(
                success=False,
                operation=FolderOperationType.DELETE,
                folder_path=folder_path,
                message=error_msg,
                error="Folder not found",
                duration_seconds=duration
            )
            
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = str(e)
            
            self.logger.error(f"Failed to delete folder {folder_path}: {error_msg}")
            
            return FolderOperationResult(
                success=False,
                operation=FolderOperationType.DELETE,
                folder_path=folder_path,
                message=f"Deletion failed: {error_msg}",
                error=error_msg,
                duration_seconds=duration
            )
    
    async def _delete_folder_contents(self, directory_client: ShareDirectoryClient) -> None:
        """Recursively delete folder contents."""
        async for item in directory_client.list_directories_and_files():
            if item['is_directory']:
                # Recursively delete subdirectory
                sub_directory_client = directory_client.get_subdirectory_client(item['name'])
                await self._delete_folder_contents(sub_directory_client)
                await sub_directory_client.delete_directory()
            else:
                # Delete file
                file_client = directory_client.get_file_client(item['name'])
                await file_client.delete_file()
    
    async def cleanup_empty_folders(self, base_path: str) -> FolderOperationResult:
        """
        Clean up empty folders in a directory tree.
        
        Args:
            base_path: Base path to start cleanup from.
            
        Returns:
            FolderOperationResult with cleanup results.
        """
        start_time = datetime.utcnow()
        deleted_folders = []
        
        try:
            # Get all folders recursively
            listing_result = await self.listing_service.list_folder_contents(
                base_path, recursive=True, include_files=True
            )
            
            if not listing_result.success:
                return listing_result
            
            # Group items by directory
            directories = {}
            for item in listing_result.items or []:
                dir_path = str(Path(item.path).parent)
                if dir_path not in directories:
                    directories[dir_path] = {"files": [], "dirs": []}
                
                if item.is_directory:
                    directories[dir_path]["dirs"].append(item)
                else:
                    directories[dir_path]["files"].append(item)
            
            # Find empty directories (no files and no non-empty subdirectories)
            empty_dirs = set()
            for dir_path, contents in directories.items():
                if not contents["files"]:  # No files
                    # Check if all subdirectories are empty
                    all_subdirs_empty = all(
                        subdir.path in empty_dirs 
                        for subdir in contents["dirs"]
                    )
                    if all_subdirs_empty:
                        empty_dirs.add(dir_path)
            
            # Delete empty directories (deepest first)
            sorted_empty_dirs = sorted(empty_dirs, key=lambda x: x.count("/"), reverse=True)
            
            for dir_path in sorted_empty_dirs:
                if dir_path != base_path:  # Don't delete the base path
                    delete_result = await self.delete_folder(dir_path, recursive=False)
                    if delete_result.success:
                        deleted_folders.append(dir_path)
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            self.logger.info(f"Cleaned up {len(deleted_folders)} empty folders")
            
            return FolderOperationResult(
                success=True,
                operation=FolderOperationType.CLEANUP,
                folder_path=base_path,
                message=f"Cleaned up {len(deleted_folders)} empty folders",
                duration_seconds=duration
            )
            
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = str(e)
            
            self.logger.error(f"Failed to cleanup empty folders in {base_path}: {error_msg}")
            
            return FolderOperationResult(
                success=False,
                operation=FolderOperationType.CLEANUP,
                folder_path=base_path,
                message=f"Cleanup failed: {error_msg}",
                error=error_msg,
                duration_seconds=duration
            )


class ProjectFolderManager:
    """
    Main project folder manager that combines all folder operations.
    
    This service provides a unified interface for project folder management
    including creation, listing, and cleanup operations.
    """
    
    def __init__(self, connection_manager: Optional[AzureConnectionManager] = None):
        """Initialize project folder manager."""
        self.connection_manager = connection_manager
        self.structure_manager = FolderStructureManager()
        self.listing_service = FolderListingService(connection_manager)
        self.cleanup_service = FolderCleanupService(connection_manager)
        self.logger = logging.getLogger(__name__)
    
    # Project management
    async def create_project_folder(self, project_id: Optional[str] = None) -> FolderOperationResult:
        """
        Create a new project folder.
        
        Args:
            project_id: Optional project ID (generates new one if not provided).
            
        Returns:
            FolderOperationResult with creation result.
        """
        start_time = datetime.utcnow()
        
        try:
            # Generate project ID if not provided
            if not project_id:
                project_id = self.structure_manager.generate_project_id()
            
            # Validate project ID
            is_valid, error_msg = self.structure_manager.validate_project_id(project_id)
            if not is_valid:
                return FolderOperationResult(
                    success=False,
                    operation=FolderOperationType.CREATE,
                    folder_path="",
                    message=f"Invalid project ID: {error_msg}",
                    error=error_msg
                )
            
            # Get project folder path
            project_path = self.structure_manager.get_project_folder_path(project_id)
            
            # Get connection manager
            if not self.connection_manager:
                self.connection_manager = await get_connection_manager()
            
            # Create project directory
            async with self.connection_manager.get_share_client() as share_client:
                directory_client = share_client.get_directory_client(project_path)
                
                try:
                    await directory_client.create_directory()
                except ResourceExistsError:
                    # Directory already exists, that's okay
                    pass
                
                # Get directory properties
                properties = await directory_client.get_directory_properties()
                folder_info = FolderInfo.from_azure_properties(project_path, properties)
                folder_info.properties["project_id"] = project_id
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            self.logger.info(f"Created project folder: {project_id}")
            
            return FolderOperationResult(
                success=True,
                operation=FolderOperationType.CREATE,
                folder_path=project_path,
                message=f"Project folder created: {project_id}",
                folder_info=folder_info,
                duration_seconds=duration
            )
            
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = str(e)
            
            self.logger.error(f"Failed to create project folder {project_id}: {error_msg}")
            
            return FolderOperationResult(
                success=False,
                operation=FolderOperationType.CREATE,
                folder_path=project_id or "",
                message=f"Creation failed: {error_msg}",
                error=error_msg,
                duration_seconds=duration
            )
    
    async def create_generation_folder(
        self,
        project_id: str,
        generation_hash: Optional[str] = None,
        query: Optional[str] = None
    ) -> FolderOperationResult:
        """
        Create a generation folder within a project.
        
        Args:
            project_id: Project UUID.
            generation_hash: Optional generation hash (generates if not provided).
            query: Query string for hash generation (if generation_hash not provided).
            
        Returns:
            FolderOperationResult with creation result.
        """
        start_time = datetime.utcnow()
        
        try:
            # Validate project ID
            is_valid, error_msg = self.structure_manager.validate_project_id(project_id)
            if not is_valid:
                return FolderOperationResult(
                    success=False,
                    operation=FolderOperationType.CREATE,
                    folder_path="",
                    message=f"Invalid project ID: {error_msg}",
                    error=error_msg
                )
            
            # Generate generation hash if not provided
            if not generation_hash:
                if not query:
                    query = f"generation_{datetime.utcnow().isoformat()}"
                generation_hash = self.structure_manager.generate_generation_hash(query)
            
            # Get generation folder path
            generation_path = self.structure_manager.get_generation_folder_path(
                project_id, generation_hash
            )
            
            # Get connection manager
            if not self.connection_manager:
                self.connection_manager = await get_connection_manager()
            
            # Ensure project folder exists first
            project_result = await self.create_project_folder(project_id)
            if not project_result.success:
                return project_result
            
            # Create generation directory
            async with self.connection_manager.get_share_client() as share_client:
                directory_client = share_client.get_directory_client(generation_path)
                
                try:
                    await directory_client.create_directory()
                except ResourceExistsError:
                    # Directory already exists, that's okay
                    pass
                
                # Get directory properties
                properties = await directory_client.get_directory_properties()
                folder_info = FolderInfo.from_azure_properties(generation_path, properties)
                folder_info.properties.update({
                    "project_id": project_id,
                    "generation_hash": generation_hash
                })
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            self.logger.info(f"Created generation folder: {project_id}/{generation_hash}")
            
            return FolderOperationResult(
                success=True,
                operation=FolderOperationType.CREATE,
                folder_path=generation_path,
                message=f"Generation folder created: {generation_hash}",
                folder_info=folder_info,
                duration_seconds=duration
            )
            
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = str(e)
            
            self.logger.error(f"Failed to create generation folder {project_id}/{generation_hash}: {error_msg}")
            
            return FolderOperationResult(
                success=False,
                operation=FolderOperationType.CREATE,
                folder_path=f"{project_id}/{generation_hash or 'unknown'}",
                message=f"Creation failed: {error_msg}",
                error=error_msg,
                duration_seconds=duration
            )
    
    # Folder existence checks
    async def project_folder_exists(self, project_id: str) -> FolderOperationResult:
        """
        Check if a project folder exists.
        
        Args:
            project_id: Project UUID.
            
        Returns:
            FolderOperationResult indicating if folder exists.
        """
        start_time = datetime.utcnow()
        
        try:
            # Validate project ID
            is_valid, error_msg = self.structure_manager.validate_project_id(project_id)
            if not is_valid:
                return FolderOperationResult(
                    success=False,
                    operation=FolderOperationType.EXISTS,
                    folder_path="",
                    message=f"Invalid project ID: {error_msg}",
                    error=error_msg
                )
            
            # Get project folder path
            project_path = self.structure_manager.get_project_folder_path(project_id)
            
            # Get connection manager
            if not self.connection_manager:
                self.connection_manager = await get_connection_manager()
            
            # Check if directory exists
            async with self.connection_manager.get_share_client() as share_client:
                directory_client = share_client.get_directory_client(project_path)
                
                try:
                    properties = await directory_client.get_directory_properties()
                    folder_info = FolderInfo.from_azure_properties(project_path, properties)
                    folder_info.properties["project_id"] = project_id
                    
                    duration = (datetime.utcnow() - start_time).total_seconds()
                    
                    return FolderOperationResult(
                        success=True,
                        operation=FolderOperationType.EXISTS,
                        folder_path=project_path,
                        message="Project folder exists",
                        folder_info=folder_info,
                        duration_seconds=duration
                    )
                    
                except ResourceNotFoundError:
                    duration = (datetime.utcnow() - start_time).total_seconds()
                    
                    return FolderOperationResult(
                        success=True,  # Success means we got a definitive answer
                        operation=FolderOperationType.EXISTS,
                        folder_path=project_path,
                        message="Project folder does not exist",
                        duration_seconds=duration
                    )
            
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = str(e)
            
            self.logger.error(f"Failed to check if project folder exists {project_id}: {error_msg}")
            
            return FolderOperationResult(
                success=False,
                operation=FolderOperationType.EXISTS,
                folder_path=project_id,
                message=f"Existence check failed: {error_msg}",
                error=error_msg,
                duration_seconds=duration
            )
    
    # Listing operations
    async def list_projects(self) -> FolderOperationResult:
        """List all projects."""
        return await self.listing_service.list_projects()
    
    async def list_project_generations(self, project_id: str) -> FolderOperationResult:
        """List generations for a project."""
        return await self.listing_service.list_project_generations(project_id)
    
    async def list_generation_contents(
        self,
        project_id: str,
        generation_hash: str,
        recursive: bool = True
    ) -> FolderOperationResult:
        """
        List contents of a generation folder.
        
        Args:
            project_id: Project UUID.
            generation_hash: Generation hash.
            recursive: Whether to list recursively.
            
        Returns:
            FolderOperationResult with generation contents.
        """
        generation_path = self.structure_manager.get_generation_folder_path(
            project_id, generation_hash
        )
        
        return await self.listing_service.list_folder_contents(
            generation_path, recursive=recursive, include_files=True
        )
    
    # Cleanup operations
    async def delete_project_folder(self, project_id: str) -> FolderOperationResult:
        """Delete a project folder and all its contents."""
        project_path = self.structure_manager.get_project_folder_path(project_id)
        return await self.cleanup_service.delete_folder(project_path, recursive=True)
    
    async def delete_generation_folder(
        self,
        project_id: str,
        generation_hash: str
    ) -> FolderOperationResult:
        """Delete a generation folder and its contents."""
        generation_path = self.structure_manager.get_generation_folder_path(
            project_id, generation_hash
        )
        return await self.cleanup_service.delete_folder(generation_path, recursive=True)
    
    async def cleanup_empty_project_folders(self) -> FolderOperationResult:
        """Clean up empty project folders."""
        base_path = self.structure_manager.config.AZURE_BASE_DIRECTORY
        return await self.cleanup_service.cleanup_empty_folders(base_path)
    
    # Utility methods
    def generate_project_id(self) -> str:
        """Generate a new project ID."""
        return self.structure_manager.generate_project_id()
    
    def generate_generation_hash(self, query: str) -> str:
        """Generate a generation hash."""
        return self.structure_manager.generate_generation_hash(query)
    
    def validate_project_id(self, project_id: str) -> tuple[bool, Optional[str]]:
        """Validate a project ID."""
        return self.structure_manager.validate_project_id(project_id)


# Global project folder manager instance
_project_folder_manager: Optional[ProjectFolderManager] = None


async def get_project_folder_manager() -> ProjectFolderManager:
    """
    Get the global project folder manager instance.
    
    Returns:
        ProjectFolderManager: Global project folder manager.
    """
    global _project_folder_manager
    
    if _project_folder_manager is None:
        connection_manager = await get_connection_manager()
        _project_folder_manager = ProjectFolderManager(connection_manager)
    
    return _project_folder_manager