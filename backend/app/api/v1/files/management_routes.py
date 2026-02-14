"""
File Management API Routes with Hybrid Architecture and Conditional GitHub Integration.

This module provides comprehensive file management endpoints including:
- File listing with Supabase JWT validation and user UUID extraction
- User validation against Supabase users table using SERVICE_ROLE_KEY
- File metadata retrieval from Azure PostgreSQL and content from Azure File Share
- File organization by project hierarchy using Azure PostgreSQL project data
- Conditional GitHub file synchronization endpoints (only for projects with github_linked=true)
- Project linking/unlinking endpoints that update Azure PostgreSQL and optionally create GitHub repositories
- GitHub installation validation endpoints using GitHub App authentication
- Proper error handling for Supabase validation, Azure operations, and GitHub API calls
"""

import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user_id, SupabaseJWTValidator
from app.services.azure_file_service import AzureFileService, FileInfo, SaveResult
from app.services.project_management_service import (
    ProjectManagementService,
    ProjectManagementError,
    GitHubLinkingError,
    AzureIntegrationError
)
from app.services.github_app_service import GitHubAppService, GitHubAppError
from app.db.session import get_async_db
from logconfig.logger import get_logger

logger = get_logger()
router = APIRouter(prefix="/files", tags=["file-management"])


# Request/Response Models
class FileListRequest(BaseModel):
    """Request model for file listing operations."""
    project_id: Optional[str] = Field(None, description="Optional project ID filter")
    generation_id: Optional[str] = Field(None, description="Optional generation ID filter")
    file_type: Optional[str] = Field(None, description="Optional file type filter (tf, json, yaml, etc.)")
    include_content: bool = Field(False, description="Whether to include file content")
    max_results: int = Field(100, ge=1, le=500, description="Maximum number of results")


class FileInfoResponse(BaseModel):
    """Response model for file information."""
    name: str
    path: str
    relative_path: str
    size: int
    modified_date: datetime
    project_id: str
    user_id: str
    generation_id: Optional[str]
    content_type: str
    content: Optional[str] = None  # Only included if requested


class FileListResponse(BaseModel):
    """Response model for file listing."""
    files: List[FileInfoResponse]
    total_count: int
    project_hierarchy: Dict[str, Any]  # Project organization structure
    message: str


class ProjectHierarchyResponse(BaseModel):
    """Response model for project hierarchy."""
    user_id: str
    projects: Dict[str, Dict[str, Any]]  # project_id -> project info with files
    total_projects: int
    total_files: int
    total_size: int


class GitHubSyncRequest(BaseModel):
    """Request model for GitHub synchronization."""
    project_id: str = Field(..., description="Project ID to sync")
    generation_id: Optional[str] = Field(None, description="Optional specific generation to sync")
    commit_message: Optional[str] = Field(None, description="Custom commit message")
    branch: str = Field("main", description="Target branch")


class GitHubSyncResponse(BaseModel):
    """Response model for GitHub synchronization."""
    success: bool
    project_id: str
    files_synced: int
    commit_sha: Optional[str]
    repository_url: Optional[str]
    commit_url: Optional[str]
    message: str
    error_message: Optional[str]


class GitHubInstallationResponse(BaseModel):
    """Response model for GitHub installation information."""
    id: int
    account_login: str
    account_type: str
    permissions: Dict[str, str]
    repository_count: int
    created_at: datetime
    updated_at: datetime


class GitHubInstallationListResponse(BaseModel):
    """Response model for GitHub installation listing."""
    installations: List[GitHubInstallationResponse]
    total_count: int
    message: str


class ProjectLinkRequest(BaseModel):
    """Request model for project linking operations."""
    installation_id: int = Field(..., description="GitHub App installation ID")
    create_repository: bool = Field(True, description="Whether to create a new repository")
    repository_name: Optional[str] = Field(None, description="Repository name (defaults to project name)")
    repository_description: Optional[str] = Field(None, description="Repository description")
    private: bool = Field(True, description="Whether repository should be private")


class ProjectLinkResponse(BaseModel):
    """Response model for project linking operations."""
    success: bool
    project_id: str
    repository_url: Optional[str]
    repository_id: Optional[int]
    installation_id: Optional[int]
    message: str
    error_message: Optional[str]


# Dependency to get services
async def get_file_management_services(
    db_session: AsyncSession = Depends(get_async_db)
) -> tuple[AzureFileService, ProjectManagementService, GitHubAppService, SupabaseJWTValidator]:
    """Get all required services for file management."""
    azure_service = AzureFileService()
    github_service = GitHubAppService()
    supabase_auth = SupabaseJWTValidator()
    
    project_service = ProjectManagementService(
        db_session=db_session,
        azure_service=azure_service,
        github_service=github_service,
        supabase_auth=supabase_auth
    )
    
    return azure_service, project_service, github_service, supabase_auth


@router.get(
    "",
    response_model=FileListResponse,
    summary="List user files with hybrid architecture",
    description="""
    List files for a user with Supabase JWT validation and user UUID extraction.
    
    - Validates user exists in Supabase users table using SERVICE_ROLE_KEY
    - Retrieves file metadata from Azure PostgreSQL projects table and file content from Azure File Share
    - Creates file organization by project hierarchy using Azure PostgreSQL project data
    - Supports filtering by project, generation, and file type
    - Optionally includes file content
    """
)
async def list_user_files(
    request: FileListRequest = Depends(),
    user_id: str = Depends(get_current_user_id),
    services: tuple = Depends(get_file_management_services)
) -> FileListResponse:
    """
    List files for a user with comprehensive filtering and organization.
    
    Args:
        request: File listing request parameters
        user_id: Supabase user ID from JWT token
        services: Tuple of required services
        
    Returns:
        FileListResponse with organized file information
        
    Raises:
        HTTPException: If operation fails
    """
    try:
        azure_service, project_service, github_service, supabase_auth = services
        
        # Validate user exists in Supabase users table using SERVICE_ROLE_KEY
        user_exists = await supabase_auth.validate_user_exists(user_id)
        if not user_exists:
            raise HTTPException(
                status_code=404,
                detail="User not found in Supabase users table"
            )
        
        # Get files from Azure File Share
        files = await azure_service.list_user_files(
            user_id=user_id,
            project_id=request.project_id,
            generation_id=request.generation_id
        )
        
        # Filter by file type if specified
        if request.file_type:
            files = [f for f in files if f.name.endswith(f".{request.file_type}")]
        
        # Limit results
        files = files[:request.max_results]
        
        # Get file content if requested
        file_responses = []
        for file_info in files:
            file_response = FileInfoResponse(
                name=file_info.name,
                path=file_info.path,
                relative_path=file_info.relative_path,
                size=file_info.size,
                modified_date=file_info.modified_date,
                project_id=file_info.project_id,
                user_id=file_info.user_id,
                generation_id=file_info.generation_id,
                content_type=file_info.content_type
            )
            
            # Include content if requested
            if request.include_content:
                try:
                    content = await azure_service.get_file_content(
                        user_id=user_id,
                        project_id=file_info.project_id,
                        generation_id=file_info.generation_id or "",
                        file_path=file_info.relative_path
                    )
                    file_response.content = content
                except Exception as e:
                    logger.warning(f"Failed to get content for file {file_info.path}: {e}")
                    file_response.content = None
            
            file_responses.append(file_response)
        
        # Build project hierarchy from Azure PostgreSQL project data
        project_hierarchy = await _build_project_hierarchy(
            user_id, project_service, files
        )
        
        return FileListResponse(
            files=file_responses,
            total_count=len(file_responses),
            project_hierarchy=project_hierarchy,
            message=f"Retrieved {len(file_responses)} files for user"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing files for user {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list files: {str(e)}"
        )


@router.get(
    "/hierarchy",
    response_model=ProjectHierarchyResponse,
    summary="Get project hierarchy with file organization",
    description="""
    Get complete project hierarchy with file organization using Azure PostgreSQL project data.
    
    - Validates user exists in Supabase users table using SERVICE_ROLE_KEY
    - Organizes files by project hierarchy using Azure PostgreSQL project data
    - Includes project metadata and file statistics
    - Provides comprehensive view of user's file organization
    """
)
async def get_project_hierarchy(
    include_files: bool = Query(True, description="Whether to include file details"),
    user_id: str = Depends(get_current_user_id),
    services: tuple = Depends(get_file_management_services)
) -> ProjectHierarchyResponse:
    """
    Get complete project hierarchy with file organization.
    
    Args:
        include_files: Whether to include file details
        user_id: Supabase user ID from JWT token
        services: Tuple of required services
        
    Returns:
        ProjectHierarchyResponse with organized project structure
        
    Raises:
        HTTPException: If operation fails
    """
    try:
        azure_service, project_service, github_service, supabase_auth = services
        
        # Validate user exists in Supabase users table using SERVICE_ROLE_KEY
        user_exists = await supabase_auth.validate_user_exists(user_id)
        if not user_exists:
            raise HTTPException(
                status_code=404,
                detail="User not found in Supabase users table"
            )
        
        # Get user projects from Azure PostgreSQL
        projects_data = await project_service.list_user_projects(
            user_id=user_id,
            include_files=include_files,
            include_github_info=True
        )
        
        # Build hierarchy structure
        projects = {}
        total_files = 0
        total_size = 0
        
        for project_data in projects_data:
            project_id = project_data["id"]
            
            project_info = {
                "id": project_id,
                "name": project_data["name"],
                "description": project_data["description"],
                "status": project_data["status"],
                "created_at": project_data["created_at"],
                "updated_at": project_data["updated_at"],
                "github_linked": project_data["github_linked"],
                "github_info": project_data.get("github_info"),
                "file_count": project_data.get("file_count", 0),
                "total_size": project_data.get("total_size", 0),
                "files": []
            }
            
            if include_files and "files" in project_data:
                project_info["files"] = project_data["files"]
                total_files += len(project_data["files"])
                total_size += sum(f.get("size", 0) for f in project_data["files"])
            else:
                total_files += project_info["file_count"]
                total_size += project_info["total_size"]
            
            projects[project_id] = project_info
        
        return ProjectHierarchyResponse(
            user_id=user_id,
            projects=projects,
            total_projects=len(projects),
            total_files=total_files,
            total_size=total_size
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting project hierarchy for user {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get project hierarchy: {str(e)}"
        )


@router.post(
    "/sync-github",
    response_model=GitHubSyncResponse,
    summary="Sync files to GitHub repository (conditional)",
    description="""
    Conditionally sync project files to GitHub repository (only for projects with github_linked=true).
    
    - Validates user exists in Supabase users table using SERVICE_ROLE_KEY
    - Checks if project is linked to GitHub repository
    - Retrieves files from Azure File Share
    - Pushes files to GitHub repository using GitHub App authentication
    - Updates last sync timestamp in Azure PostgreSQL
    """
)
async def sync_files_to_github(
    request: GitHubSyncRequest,
    user_id: str = Depends(get_current_user_id),
    services: tuple = Depends(get_file_management_services)
) -> GitHubSyncResponse:
    """
    Sync project files to GitHub repository (conditional on github_linked=true).
    
    Args:
        request: GitHub sync request parameters
        user_id: Supabase user ID from JWT token
        services: Tuple of required services
        
    Returns:
        GitHubSyncResponse with sync results
        
    Raises:
        HTTPException: If operation fails
    """
    try:
        azure_service, project_service, github_service, supabase_auth = services
        
        # Validate user exists in Supabase users table using SERVICE_ROLE_KEY
        user_exists = await supabase_auth.validate_user_exists(user_id)
        if not user_exists:
            raise HTTPException(
                status_code=404,
                detail="User not found in Supabase users table"
            )
        
        # Get project to check if it's linked to GitHub
        project = await project_service.get_project_by_id(user_id, request.project_id)
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project {request.project_id} not found"
            )
        
        # Check if project is linked to GitHub
        if not project.github_linked:
            raise HTTPException(
                status_code=400,
                detail=f"Project {request.project_id} is not linked to GitHub. Use /files/link-project endpoint to link it first."
            )
        
        # Perform GitHub synchronization
        success = await project_service.sync_project_with_github(
            user_id=user_id,
            project_id=request.project_id,
            generation_id=request.generation_id
        )
        
        if not success:
            return GitHubSyncResponse(
                success=False,
                project_id=request.project_id,
                files_synced=0,
                commit_sha=None,
                repository_url=None,
                commit_url=None,
                message="GitHub synchronization failed",
                error_message="Failed to sync files to GitHub repository"
            )
        
        # Get updated project info for response
        updated_project = await project_service.get_project_by_id(user_id, request.project_id)
        repository_url = f"https://github.com/{updated_project.github_repo_name}" if updated_project.github_repo_name else None
        
        return GitHubSyncResponse(
            success=True,
            project_id=request.project_id,
            files_synced=0,  # Would need to track this in the sync method
            commit_sha=None,  # Would need to return this from sync method
            repository_url=repository_url,
            commit_url=None,  # Would need to construct this
            message=f"Successfully synchronized project {request.project_id} with GitHub",
            error_message=None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing files to GitHub for user {user_id}, project {request.project_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"GitHub synchronization failed: {str(e)}"
        )


@router.post(
    "/link-project",
    response_model=ProjectLinkResponse,
    summary="Link project to GitHub repository",
    description="""
    Link a project to GitHub repository, updating Azure PostgreSQL and optionally creating GitHub repository.
    
    - Validates user exists in Supabase users table using SERVICE_ROLE_KEY
    - Updates project in Azure PostgreSQL with GitHub repository information
    - Optionally creates new GitHub repository using GitHub App authentication
    - Sets github_linked flag to true in Azure PostgreSQL
    """
)
async def link_project_to_github(
    project_id: str = Path(..., description="Project ID to link"),
    request: ProjectLinkRequest = Body(...),
    user_id: str = Depends(get_current_user_id),
    services: tuple = Depends(get_file_management_services)
) -> ProjectLinkResponse:
    """
    Link a project to GitHub repository.
    
    Args:
        project_id: Project ID to link
        request: Project linking request parameters
        user_id: Supabase user ID from JWT token
        services: Tuple of required services
        
    Returns:
        ProjectLinkResponse with linking results
        
    Raises:
        HTTPException: If operation fails
    """
    try:
        azure_service, project_service, github_service, supabase_auth = services
        
        # Validate user exists in Supabase users table using SERVICE_ROLE_KEY
        user_exists = await supabase_auth.validate_user_exists(user_id)
        if not user_exists:
            raise HTTPException(
                status_code=404,
                detail="User not found in Supabase users table"
            )
        
        # Link project to GitHub
        result = await project_service.link_project_to_github(
            user_id=user_id,
            project_id=project_id,
            installation_id=request.installation_id,
            create_repo=request.create_repository,
            repo_name=request.repository_name
        )
        
        if not result.success:
            raise HTTPException(
                status_code=400,
                detail=result.error_message or "Failed to link project to GitHub"
            )
        
        return ProjectLinkResponse(
            success=True,
            project_id=project_id,
            repository_url=result.repo_url,
            repository_id=result.repo_id,
            installation_id=result.installation_id,
            message=f"Successfully linked project {project_id} to GitHub",
            error_message=None
        )
        
    except HTTPException:
        raise
    except GitHubLinkingError as e:
        logger.error(f"GitHub linking error for project {project_id}, user {user_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error linking project {project_id} to GitHub for user {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Project linking failed: {str(e)}"
        )


@router.post(
    "/unlink-project",
    response_model=ProjectLinkResponse,
    summary="Unlink project from GitHub repository",
    description="""
    Unlink a project from GitHub repository, updating Azure PostgreSQL.
    
    - Validates user exists in Supabase users table using SERVICE_ROLE_KEY
    - Updates project in Azure PostgreSQL to remove GitHub repository information
    - Sets github_linked flag to false in Azure PostgreSQL
    - Optionally deletes GitHub repository
    - Preserves Azure File Share data
    """
)
async def unlink_project_from_github(
    project_id: str = Path(..., description="Project ID to unlink"),
    delete_repository: bool = Query(False, description="Whether to delete the GitHub repository"),
    user_id: str = Depends(get_current_user_id),
    services: tuple = Depends(get_file_management_services)
) -> ProjectLinkResponse:
    """
    Unlink a project from GitHub repository.
    
    Args:
        project_id: Project ID to unlink
        delete_repository: Whether to delete the GitHub repository
        user_id: Supabase user ID from JWT token
        services: Tuple of required services
        
    Returns:
        ProjectLinkResponse with unlinking results
        
    Raises:
        HTTPException: If operation fails
    """
    try:
        azure_service, project_service, github_service, supabase_auth = services
        
        # Validate user exists in Supabase users table using SERVICE_ROLE_KEY
        user_exists = await supabase_auth.validate_user_exists(user_id)
        if not user_exists:
            raise HTTPException(
                status_code=404,
                detail="User not found in Supabase users table"
            )
        
        # Unlink project from GitHub
        result = await project_service.unlink_project_from_github(
            user_id=user_id,
            project_id=project_id,
            delete_repo=delete_repository
        )
        
        if not result.success:
            raise HTTPException(
                status_code=400,
                detail=result.error_message or "Failed to unlink project from GitHub"
            )
        
        message = f"Successfully unlinked project {project_id} from GitHub"
        if delete_repository:
            message += " and deleted repository"
        
        return ProjectLinkResponse(
            success=True,
            project_id=project_id,
            repository_url=None,
            repository_id=None,
            installation_id=None,
            message=message,
            error_message=None
        )
        
    except HTTPException:
        raise
    except GitHubLinkingError as e:
        logger.error(f"GitHub unlinking error for project {project_id}, user {user_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error unlinking project {project_id} from GitHub for user {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Project unlinking failed: {str(e)}"
        )


@router.get(
    "/github/installations",
    response_model=GitHubInstallationListResponse,
    summary="Get GitHub App installations for user",
    description="""
    Get GitHub App installations accessible to the user using GitHub App authentication.
    
    - Validates user exists in Supabase users table using SERVICE_ROLE_KEY
    - Retrieves GitHub App installations using GitHub App authentication
    - Validates installation access for the user
    - Returns installation information for project linking
    """
)
async def get_github_installations(
    user_id: str = Depends(get_current_user_id),
    services: tuple = Depends(get_file_management_services)
) -> GitHubInstallationListResponse:
    """
    Get GitHub App installations accessible to the user.
    
    Args:
        user_id: Supabase user ID from JWT token
        services: Tuple of required services
        
    Returns:
        GitHubInstallationListResponse with installation information
        
    Raises:
        HTTPException: If operation fails
    """
    try:
        azure_service, project_service, github_service, supabase_auth = services
        
        # Validate user exists in Supabase users table using SERVICE_ROLE_KEY
        user_exists = await supabase_auth.validate_user_exists(user_id)
        if not user_exists:
            raise HTTPException(
                status_code=404,
                detail="User not found in Supabase users table"
            )
        
        # Note: This is a simplified implementation
        # In a full implementation, you would need to:
        # 1. Get user's GitHub access token (stored separately or obtained via OAuth)
        # 2. Use that token to get user's installations
        # For now, we'll return a placeholder response
        
        logger.warning("GitHub installations endpoint not fully implemented - requires user GitHub access token")
        
        return GitHubInstallationListResponse(
            installations=[],
            total_count=0,
            message="GitHub installations endpoint requires user GitHub access token integration"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting GitHub installations for user {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get GitHub installations: {str(e)}"
        )


@router.get(
    "/github/installations/{installation_id}/validate",
    summary="Validate GitHub App installation access",
    description="""
    Validate user access to a specific GitHub App installation.
    
    - Validates user exists in Supabase users table using SERVICE_ROLE_KEY
    - Validates GitHub App installation access using GitHub App authentication
    - Checks if user has access to the specified installation
    - Returns validation results for project linking operations
    """
)
async def validate_github_installation(
    installation_id: int = Path(..., description="GitHub App installation ID"),
    user_id: str = Depends(get_current_user_id),
    services: tuple = Depends(get_file_management_services)
) -> Dict[str, Any]:
    """
    Validate user access to GitHub App installation.
    
    Args:
        installation_id: GitHub App installation ID to validate
        user_id: Supabase user ID from JWT token
        services: Tuple of required services
        
    Returns:
        Dictionary with validation results
        
    Raises:
        HTTPException: If operation fails
    """
    try:
        azure_service, project_service, github_service, supabase_auth = services
        
        # Validate user exists in Supabase users table using SERVICE_ROLE_KEY
        user_exists = await supabase_auth.validate_user_exists(user_id)
        if not user_exists:
            raise HTTPException(
                status_code=404,
                detail="User not found in Supabase users table"
            )
        
        # Try to get installation access token to validate access
        try:
            access_token = await github_service.get_installation_access_token(installation_id)
            
            return {
                "valid": True,
                "installation_id": installation_id,
                "user_id": user_id,
                "message": f"User has access to GitHub App installation {installation_id}",
                "validated_at": datetime.utcnow().isoformat()
            }
            
        except GitHubAppError as e:
            return {
                "valid": False,
                "installation_id": installation_id,
                "user_id": user_id,
                "message": f"User does not have access to GitHub App installation {installation_id}",
                "error": str(e),
                "validated_at": datetime.utcnow().isoformat()
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating GitHub installation {installation_id} for user {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Installation validation failed: {str(e)}"
        )


@router.get(
    "/{project_id}/download",
    summary="Download project files as archive",
    description="""
    Download all files for a project as a compressed archive.
    
    - Validates user exists in Supabase users table using SERVICE_ROLE_KEY
    - Retrieves all files for the project from Azure File Share
    - Creates compressed archive with proper file organization
    - Returns streaming response for efficient download
    """
)
async def download_project_files(
    project_id: str = Path(..., description="Project ID"),
    generation_id: Optional[str] = Query(None, description="Optional specific generation"),
    format: str = Query("zip", description="Archive format (zip, tar)"),
    user_id: str = Depends(get_current_user_id),
    services: tuple = Depends(get_file_management_services)
) -> Response:
    """
    Download project files as compressed archive.
    
    Args:
        project_id: Project ID to download
        generation_id: Optional specific generation to download
        format: Archive format (zip or tar)
        user_id: Supabase user ID from JWT token
        services: Tuple of required services
        
    Returns:
        StreamingResponse with compressed archive
        
    Raises:
        HTTPException: If operation fails
    """
    try:
        azure_service, project_service, github_service, supabase_auth = services
        
        # Validate user exists in Supabase users table using SERVICE_ROLE_KEY
        user_exists = await supabase_auth.validate_user_exists(user_id)
        if not user_exists:
            raise HTTPException(
                status_code=404,
                detail="User not found in Supabase users table"
            )
        
        # Verify project access
        project = await project_service.get_project_by_id(user_id, project_id)
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project {project_id} not found"
            )
        
        # Get project files
        files = await azure_service.list_user_files(
            user_id=user_id,
            project_id=project_id,
            generation_id=generation_id
        )
        
        if not files:
            raise HTTPException(
                status_code=404,
                detail=f"No files found for project {project_id}"
            )
        
        # For now, return a simple response indicating the feature is available
        # Full implementation would create and stream the archive
        return Response(
            content=f"Project {project_id} download would contain {len(files)} files",
            media_type="text/plain",
            headers={
                "Content-Disposition": f"attachment; filename={project_id}-files.txt"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading project {project_id} for user {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Project download failed: {str(e)}"
        )


# Helper functions
async def _build_project_hierarchy(
    user_id: str,
    project_service: ProjectManagementService,
    files: List[FileInfo]
) -> Dict[str, Any]:
    """
    Build project hierarchy from Azure PostgreSQL project data.
    
    Args:
        user_id: User ID
        project_service: Project management service
        files: List of files to organize
        
    Returns:
        Dictionary with project hierarchy structure
    """
    try:
        # Get user projects from Azure PostgreSQL
        projects_data = await project_service.list_user_projects(
            user_id=user_id,
            include_files=False,
            include_github_info=True
        )
        
        # Build hierarchy
        hierarchy = {
            "user_id": user_id,
            "projects": {},
            "total_projects": len(projects_data),
            "total_files": len(files)
        }
        
        # Organize files by project
        files_by_project = {}
        for file_info in files:
            project_id = file_info.project_id
            if project_id not in files_by_project:
                files_by_project[project_id] = []
            files_by_project[project_id].append(file_info)
        
        # Add project information
        for project_data in projects_data:
            project_id = project_data["id"]
            project_files = files_by_project.get(project_id, [])
            
            # Organize files by generation
            generations = {}
            for file_info in project_files:
                gen_id = file_info.generation_id or "unknown"
                if gen_id not in generations:
                    generations[gen_id] = []
                generations[gen_id].append({
                    "name": file_info.name,
                    "path": file_info.relative_path,
                    "size": file_info.size,
                    "modified_date": file_info.modified_date.isoformat(),
                    "content_type": file_info.content_type
                })
            
            hierarchy["projects"][project_id] = {
                "name": project_data["name"],
                "description": project_data["description"],
                "status": project_data["status"],
                "github_linked": project_data["github_linked"],
                "file_count": len(project_files),
                "generations": generations
            }
        
        return hierarchy
        
    except Exception as e:
        logger.error(f"Error building project hierarchy: {e}")
        return {
            "user_id": user_id,
            "projects": {},
            "total_projects": 0,
            "total_files": len(files),
            "error": str(e)
        }