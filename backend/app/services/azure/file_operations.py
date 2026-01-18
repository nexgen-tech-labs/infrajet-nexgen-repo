"""
Azure File Share File Operations Service.

This module provides file operations for Azure File Share including
upload, download, metadata management, and file validation.
"""

import asyncio
import hashlib
import logging
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, BinaryIO, Union
from dataclasses import dataclass, field
from enum import Enum

from azure.storage.fileshare.aio import ShareFileClient
from azure.core.exceptions import (
    AzureError,
    ResourceNotFoundError,
    ResourceExistsError,
    HttpResponseError
)

from app.services.azure.connection import AzureConnectionManager, get_connection_manager
from app.core.azure_config import AzureFileShareConfig, get_azure_config


class FileOperationType(Enum):
    """File operation types for logging and monitoring."""
    UPLOAD = "upload"
    DOWNLOAD = "download"
    DELETE = "delete"
    LIST = "list"
    METADATA = "metadata"
    EXISTS = "exists"


@dataclass
class FileMetadata:
    """File metadata information."""
    file_path: str
    size_bytes: int
    content_hash: str
    content_type: str
    created_at: datetime
    modified_at: datetime
    etag: Optional[str] = None
    properties: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_azure_properties(cls, file_path: str, properties: Dict[str, Any]) -> "FileMetadata":
        """Create FileMetadata from Azure file properties."""
        return cls(
            file_path=file_path,
            size_bytes=properties.get("size", 0),
            content_hash=properties.get("content_settings", {}).get("content_md5", ""),
            content_type=properties.get("content_settings", {}).get("content_type", ""),
            created_at=properties.get("creation_time", datetime.utcnow()),
            modified_at=properties.get("last_modified", datetime.utcnow()),
            etag=properties.get("etag"),
            properties=properties
        )


@dataclass
class FileOperationResult:
    """Result of a file operation."""
    success: bool
    operation: FileOperationType
    file_path: str
    message: str
    metadata: Optional[FileMetadata] = None
    error: Optional[str] = None
    duration_seconds: Optional[float] = None


class FileValidator:
    """File validation utilities."""
    
    def __init__(self, config: Optional[AzureFileShareConfig] = None):
        """Initialize file validator."""
        self.config = config or get_azure_config()
        self.logger = logging.getLogger(__name__)
    
    def validate_file_path(self, file_path: str) -> tuple[bool, Optional[str]]:
        """
        Validate file path for Azure File Share.
        
        Args:
            file_path: File path to validate.
            
        Returns:
            Tuple of (is_valid, error_message).
        """
        if not file_path:
            return False, "File path cannot be empty"
        
        # Remove leading/trailing slashes
        normalized_path = file_path.strip("/")
        
        if not normalized_path:
            return False, "File path cannot be just slashes"
        
        # Check for invalid characters
        invalid_chars = ['<', '>', ':', '"', '|', '?', '*']
        for char in invalid_chars:
            if char in normalized_path:
                return False, f"File path contains invalid character: {char}"
        
        # Check path length (Azure limit is 1024 characters)
        if len(normalized_path) > 1024:
            return False, "File path too long (max 1024 characters)"
        
        # Check individual path components
        path_parts = normalized_path.split("/")
        for part in path_parts:
            if not part:
                return False, "File path cannot contain empty components"
            
            if len(part) > 255:
                return False, f"Path component too long: {part}"
            
            # Check for reserved names
            reserved_names = [
                "CON", "PRN", "AUX", "NUL",
                "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
                "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
            ]
            if part.upper() in reserved_names:
                return False, f"Reserved name not allowed: {part}"
        
        return True, None
    
    def validate_file_size(self, size_bytes: int) -> tuple[bool, Optional[str]]:
        """
        Validate file size.
        
        Args:
            size_bytes: File size in bytes.
            
        Returns:
            Tuple of (is_valid, error_message).
        """
        if size_bytes < 0:
            return False, "File size cannot be negative"
        
        max_size_bytes = self.config.AZURE_MAX_FILE_SIZE_MB * 1024 * 1024
        if size_bytes > max_size_bytes:
            return False, f"File size {size_bytes} exceeds maximum {max_size_bytes} bytes"
        
        return True, None
    
    def validate_content_type(self, file_path: str, content_type: Optional[str] = None) -> str:
        """
        Validate and determine content type.
        
        Args:
            file_path: File path to determine type from.
            content_type: Explicit content type (optional).
            
        Returns:
            Validated content type.
        """
        if content_type:
            return content_type
        
        # Guess content type from file extension
        guessed_type, _ = mimetypes.guess_type(file_path)
        if guessed_type:
            return guessed_type
        
        # Default to text/plain for common code files
        file_ext = Path(file_path).suffix.lower()
        code_extensions = {
            '.tf': 'text/plain',
            '.tfvars': 'text/plain',
            '.hcl': 'text/plain',
            '.json': 'application/json',
            '.yaml': 'text/yaml',
            '.yml': 'text/yaml',
            '.md': 'text/markdown',
            '.txt': 'text/plain',
            '.py': 'text/plain',
            '.js': 'text/plain',
            '.ts': 'text/plain'
        }
        
        return code_extensions.get(file_ext, 'application/octet-stream')


class FileProcessor:
    """File processing utilities."""
    
    @staticmethod
    def calculate_content_hash(content: Union[str, bytes]) -> str:
        """
        Calculate MD5 hash of file content.
        
        Args:
            content: File content as string or bytes.
            
        Returns:
            MD5 hash as hex string.
        """
        if isinstance(content, str):
            content = content.encode('utf-8')
        
        return hashlib.md5(content).hexdigest()
    
    @staticmethod
    def prepare_content_for_upload(content: Union[str, bytes]) -> bytes:
        """
        Prepare content for upload to Azure.
        
        Args:
            content: Content to prepare.
            
        Returns:
            Content as bytes ready for upload.
        """
        if isinstance(content, str):
            return content.encode('utf-8')
        return content
    
    @staticmethod
    def process_downloaded_content(content: bytes, as_text: bool = True) -> Union[str, bytes]:
        """
        Process content downloaded from Azure.
        
        Args:
            content: Downloaded content as bytes.
            as_text: Whether to return as text (default) or bytes.
            
        Returns:
            Processed content.
        """
        if as_text:
            try:
                return content.decode('utf-8')
            except UnicodeDecodeError:
                # If UTF-8 decoding fails, try other encodings
                for encoding in ['latin-1', 'cp1252']:
                    try:
                        return content.decode(encoding)
                    except UnicodeDecodeError:
                        continue
                # If all fail, return as bytes
                return content
        return content


class FileUploadService:
    """Service for uploading files to Azure File Share."""
    
    def __init__(self, connection_manager: Optional[AzureConnectionManager] = None):
        """Initialize upload service."""
        self.connection_manager = connection_manager
        self.validator = FileValidator()
        self.logger = logging.getLogger(__name__)
    
    async def upload_file(
        self,
        file_path: str,
        content: Union[str, bytes],
        content_type: Optional[str] = None,
        overwrite: bool = True,
        metadata: Optional[Dict[str, str]] = None
    ) -> FileOperationResult:
        """
        Upload a file to Azure File Share.
        
        Args:
            file_path: Path where to store the file.
            content: File content to upload.
            content_type: MIME type of the content.
            overwrite: Whether to overwrite existing files.
            metadata: Additional metadata to store with the file.
            
        Returns:
            FileOperationResult with upload result.
        """
        start_time = datetime.utcnow()
        
        try:
            # Validate file path
            is_valid, error_msg = self.validator.validate_file_path(file_path)
            if not is_valid:
                return FileOperationResult(
                    success=False,
                    operation=FileOperationType.UPLOAD,
                    file_path=file_path,
                    message=f"Invalid file path: {error_msg}",
                    error=error_msg
                )
            
            # Prepare content
            content_bytes = FileProcessor.prepare_content_for_upload(content)
            content_hash = FileProcessor.calculate_content_hash(content_bytes)
            
            # Validate file size
            is_valid, error_msg = self.validator.validate_file_size(len(content_bytes))
            if not is_valid:
                return FileOperationResult(
                    success=False,
                    operation=FileOperationType.UPLOAD,
                    file_path=file_path,
                    message=f"Invalid file size: {error_msg}",
                    error=error_msg
                )
            
            # Determine content type
            final_content_type = self.validator.validate_content_type(file_path, content_type)
            
            # Get connection manager
            if not self.connection_manager:
                self.connection_manager = await get_connection_manager()
            
            # Get file client
            file_client = await self.connection_manager.get_file_client(file_path)
            
            # Check if file exists and handle overwrite
            if not overwrite:
                try:
                    await file_client.get_file_properties()
                    return FileOperationResult(
                        success=False,
                        operation=FileOperationType.UPLOAD,
                        file_path=file_path,
                        message="File already exists and overwrite is disabled",
                        error="File exists"
                    )
                except ResourceNotFoundError:
                    # File doesn't exist, proceed with upload
                    pass
            
            # Create parent directories if needed
            await self._ensure_parent_directories(file_path)
            
            # Upload file
            from azure.storage.fileshare import ContentSettings
            
            # Create content settings without MD5 hash for now (to avoid encoding issues)
            content_settings = ContentSettings(
                content_type=final_content_type
            )
            
            await file_client.upload_file(
                data=content_bytes,
                length=len(content_bytes),
                content_settings=content_settings,
                metadata=metadata or {}
            )
            
            # Get file properties for metadata
            properties = await file_client.get_file_properties()
            file_metadata = FileMetadata.from_azure_properties(file_path, properties)
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            self.logger.info(f"Successfully uploaded file: {file_path} ({len(content_bytes)} bytes)")
            
            return FileOperationResult(
                success=True,
                operation=FileOperationType.UPLOAD,
                file_path=file_path,
                message=f"File uploaded successfully ({len(content_bytes)} bytes)",
                metadata=file_metadata,
                duration_seconds=duration
            )
            
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = str(e)
            
            self.logger.error(f"Failed to upload file {file_path}: {error_msg}")
            
            return FileOperationResult(
                success=False,
                operation=FileOperationType.UPLOAD,
                file_path=file_path,
                message=f"Upload failed: {error_msg}",
                error=error_msg,
                duration_seconds=duration
            )
    
    async def _ensure_parent_directories(self, file_path: str) -> None:
        """Ensure parent directories exist for the file path."""
        path_parts = file_path.split("/")[:-1]  # Exclude filename
        
        if not path_parts:
            return  # No parent directories needed
        
        # Build directory path incrementally
        current_path = ""
        for part in path_parts:
            current_path = f"{current_path}/{part}" if current_path else part
            
            try:
                if not self.connection_manager:
                    self.connection_manager = await get_connection_manager()
                
                async with self.connection_manager.get_share_client() as share_client:
                    directory_client = share_client.get_directory_client(current_path)
                    await directory_client.create_directory()
                    
            except ResourceExistsError:
                # Directory already exists, continue
                pass
            except Exception as e:
                self.logger.warning(f"Failed to create directory {current_path}: {e}")


class FileDownloadService:
    """Service for downloading files from Azure File Share."""
    
    def __init__(self, connection_manager: Optional[AzureConnectionManager] = None):
        """Initialize download service."""
        self.connection_manager = connection_manager
        self.logger = logging.getLogger(__name__)
    
    async def download_file(
        self,
        file_path: str,
        as_text: bool = True
    ) -> FileOperationResult:
        """
        Download a file from Azure File Share.
        
        Args:
            file_path: Path of the file to download.
            as_text: Whether to return content as text or bytes.
            
        Returns:
            FileOperationResult with download result and content.
        """
        start_time = datetime.utcnow()
        
        try:
            # Get connection manager
            if not self.connection_manager:
                self.connection_manager = await get_connection_manager()
            
            # Get file client
            file_client = await self.connection_manager.get_file_client(file_path)
            
            # Download file
            download_stream = await file_client.download_file()
            content_bytes = await download_stream.readall()
            
            # Process content
            content = FileProcessor.process_downloaded_content(content_bytes, as_text)
            
            # Get file properties for metadata
            properties = await file_client.get_file_properties()
            file_metadata = FileMetadata.from_azure_properties(file_path, properties)
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            self.logger.info(f"Successfully downloaded file: {file_path} ({len(content_bytes)} bytes)")
            
            result = FileOperationResult(
                success=True,
                operation=FileOperationType.DOWNLOAD,
                file_path=file_path,
                message=f"File downloaded successfully ({len(content_bytes)} bytes)",
                metadata=file_metadata,
                duration_seconds=duration
            )
            
            # Add content to result (extend the dataclass)
            result.content = content
            
            return result
            
        except ResourceNotFoundError:
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = f"File not found: {file_path}"
            
            self.logger.warning(error_msg)
            
            return FileOperationResult(
                success=False,
                operation=FileOperationType.DOWNLOAD,
                file_path=file_path,
                message=error_msg,
                error="File not found",
                duration_seconds=duration
            )
            
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = str(e)
            
            self.logger.error(f"Failed to download file {file_path}: {error_msg}")
            
            return FileOperationResult(
                success=False,
                operation=FileOperationType.DOWNLOAD,
                file_path=file_path,
                message=f"Download failed: {error_msg}",
                error=error_msg,
                duration_seconds=duration
            )


class FileMetadataService:
    """Service for file metadata operations."""
    
    def __init__(self, connection_manager: Optional[AzureConnectionManager] = None):
        """Initialize metadata service."""
        self.connection_manager = connection_manager
        self.logger = logging.getLogger(__name__)
    
    async def get_file_metadata(self, file_path: str) -> FileOperationResult:
        """
        Get metadata for a file.
        
        Args:
            file_path: Path of the file.
            
        Returns:
            FileOperationResult with metadata.
        """
        start_time = datetime.utcnow()
        
        try:
            # Get connection manager
            if not self.connection_manager:
                self.connection_manager = await get_connection_manager()
            
            # Get file client
            file_client = await self.connection_manager.get_file_client(file_path)
            
            # Get file properties
            properties = await file_client.get_file_properties()
            file_metadata = FileMetadata.from_azure_properties(file_path, properties)
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            return FileOperationResult(
                success=True,
                operation=FileOperationType.METADATA,
                file_path=file_path,
                message="Metadata retrieved successfully",
                metadata=file_metadata,
                duration_seconds=duration
            )
            
        except ResourceNotFoundError:
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = f"File not found: {file_path}"
            
            return FileOperationResult(
                success=False,
                operation=FileOperationType.METADATA,
                file_path=file_path,
                message=error_msg,
                error="File not found",
                duration_seconds=duration
            )
            
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = str(e)
            
            self.logger.error(f"Failed to get metadata for {file_path}: {error_msg}")
            
            return FileOperationResult(
                success=False,
                operation=FileOperationType.METADATA,
                file_path=file_path,
                message=f"Metadata retrieval failed: {error_msg}",
                error=error_msg,
                duration_seconds=duration
            )
    
    async def file_exists(self, file_path: str) -> FileOperationResult:
        """
        Check if a file exists.
        
        Args:
            file_path: Path of the file to check.
            
        Returns:
            FileOperationResult indicating if file exists.
        """
        start_time = datetime.utcnow()
        
        try:
            # Get connection manager
            if not self.connection_manager:
                self.connection_manager = await get_connection_manager()
            
            # Get file client
            file_client = await self.connection_manager.get_file_client(file_path)
            
            # Try to get file properties
            await file_client.get_file_properties()
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            return FileOperationResult(
                success=True,
                operation=FileOperationType.EXISTS,
                file_path=file_path,
                message="File exists",
                duration_seconds=duration
            )
            
        except ResourceNotFoundError:
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            return FileOperationResult(
                success=True,  # Success means we got a definitive answer
                operation=FileOperationType.EXISTS,
                file_path=file_path,
                message="File does not exist",
                duration_seconds=duration
            )
            
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = str(e)
            
            self.logger.error(f"Failed to check if file exists {file_path}: {error_msg}")
            
            return FileOperationResult(
                success=False,
                operation=FileOperationType.EXISTS,
                file_path=file_path,
                message=f"Existence check failed: {error_msg}",
                error=error_msg,
                duration_seconds=duration
            )


class FileOperationsService:
    """
    Main file operations service that combines all file operations.
    
    This service provides a unified interface for all file operations
    including upload, download, metadata, and validation.
    """
    
    def __init__(self, connection_manager: Optional[AzureConnectionManager] = None):
        """Initialize file operations service."""
        self.connection_manager = connection_manager
        self.upload_service = FileUploadService(connection_manager)
        self.download_service = FileDownloadService(connection_manager)
        self.metadata_service = FileMetadataService(connection_manager)
        self.validator = FileValidator()
        self.logger = logging.getLogger(__name__)
    
    # Upload operations
    async def upload_file(
        self,
        file_path: str,
        content: Union[str, bytes],
        content_type: Optional[str] = None,
        overwrite: bool = True,
        metadata: Optional[Dict[str, str]] = None
    ) -> FileOperationResult:
        """Upload a file to Azure File Share."""
        return await self.upload_service.upload_file(
            file_path, content, content_type, overwrite, metadata
        )
    
    async def upload_multiple_files(
        self,
        files: List[Dict[str, Any]],
        overwrite: bool = True
    ) -> List[FileOperationResult]:
        """
        Upload multiple files concurrently.
        
        Args:
            files: List of file dictionaries with 'path', 'content', and optional metadata.
            overwrite: Whether to overwrite existing files.
            
        Returns:
            List of FileOperationResult for each file.
        """
        tasks = []
        for file_info in files:
            task = self.upload_file(
                file_path=file_info['path'],
                content=file_info['content'],
                content_type=file_info.get('content_type'),
                overwrite=overwrite,
                metadata=file_info.get('metadata')
            )
            tasks.append(task)
        
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    # Download operations
    async def download_file(self, file_path: str, as_text: bool = True) -> FileOperationResult:
        """Download a file from Azure File Share."""
        return await self.download_service.download_file(file_path, as_text)
    
    async def download_multiple_files(
        self,
        file_paths: List[str],
        as_text: bool = True
    ) -> List[FileOperationResult]:
        """
        Download multiple files concurrently.
        
        Args:
            file_paths: List of file paths to download.
            as_text: Whether to return content as text.
            
        Returns:
            List of FileOperationResult for each file.
        """
        tasks = [
            self.download_file(file_path, as_text)
            for file_path in file_paths
        ]
        
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    # Metadata operations
    async def get_file_metadata(self, file_path: str) -> FileOperationResult:
        """Get metadata for a file."""
        return await self.metadata_service.get_file_metadata(file_path)
    
    async def file_exists(self, file_path: str) -> FileOperationResult:
        """Check if a file exists."""
        return await self.metadata_service.file_exists(file_path)
    
    # Delete operations
    async def delete_file(self, file_path: str) -> FileOperationResult:
        """
        Delete a file from Azure File Share.
        
        Args:
            file_path: Path of the file to delete.
            
        Returns:
            FileOperationResult with deletion result.
        """
        start_time = datetime.utcnow()
        
        try:
            # Get connection manager
            if not self.connection_manager:
                self.connection_manager = await get_connection_manager()
            
            # Get file client
            file_client = await self.connection_manager.get_file_client(file_path)
            
            # Delete file
            await file_client.delete_file()
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            
            self.logger.info(f"Successfully deleted file: {file_path}")
            
            return FileOperationResult(
                success=True,
                operation=FileOperationType.DELETE,
                file_path=file_path,
                message="File deleted successfully",
                duration_seconds=duration
            )
            
        except ResourceNotFoundError:
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = f"File not found: {file_path}"
            
            return FileOperationResult(
                success=False,
                operation=FileOperationType.DELETE,
                file_path=file_path,
                message=error_msg,
                error="File not found",
                duration_seconds=duration
            )
            
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = str(e)
            
            self.logger.error(f"Failed to delete file {file_path}: {error_msg}")
            
            return FileOperationResult(
                success=False,
                operation=FileOperationType.DELETE,
                file_path=file_path,
                message=f"Deletion failed: {error_msg}",
                error=error_msg,
                duration_seconds=duration
            )
    
    # Validation operations
    def validate_file_path(self, file_path: str) -> tuple[bool, Optional[str]]:
        """Validate a file path."""
        return self.validator.validate_file_path(file_path)
    
    def validate_file_size(self, size_bytes: int) -> tuple[bool, Optional[str]]:
        """Validate file size."""
        return self.validator.validate_file_size(size_bytes)
    
    def validate_content_type(self, file_path: str, content_type: Optional[str] = None) -> str:
        """Validate and determine content type."""
        return self.validator.validate_content_type(file_path, content_type)


# Global file operations service instance
_file_operations_service: Optional[FileOperationsService] = None


async def get_file_operations_service() -> FileOperationsService:
    """
    Get the global file operations service instance.
    
    Returns:
        FileOperationsService: Global file operations service.
    """
    global _file_operations_service
    
    if _file_operations_service is None:
        connection_manager = await get_connection_manager()
        _file_operations_service = FileOperationsService(connection_manager)
    
    return _file_operations_service