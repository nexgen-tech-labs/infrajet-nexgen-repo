"""
Project Management API Routes with Hybrid Architecture.

This module provides comprehensive project management endpoints including:
- Project upsert (create or update)
- Project listing with user isolation using Supabase SERVICE_ROLE_KEY
- Project deletion with Azure cleanup and optional GitHub repository deletion
- GitHub repository linking/unlinking
- GitHub repository synchronization for linked projects
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body
from pydantic import BaseModel, Field

from app.dependencies.auth import get_current_user_id
from app.services.project_management_service import (
    ProjectManagementService,
    ProjectManagementError,
    GitHubLinkingError,
    AzureIntegrationError
)
from app.services.azure_file_service import AzureFileService
from app.services.github_app_service import GitHubAppService
from app.dependencies.auth import SupabaseJWTValidator
from app.db.session import get_async_db
from logconfig.logger import get_logger

logger = get_logger()
router = APIRouter(prefix="/projects", tags=["project-management"])


# Request/Response Models
class ProjectUpsertRequest(BaseModel):
    """Request model for project upsert operations."""
    name: str = Field(..., min_length=1, max_length=100, description="Project name")
    description: Optional[str] = Field(None, max_length=500, description="Project description")
    project_id: Optional[str] = Field(None, description="Optional project ID (UUID)")
    link_to_github: bool = Field(False, description="Whether to link project to GitHub")
    github_installation_id: Optional[int] = Field(None, description="GitHub App installation ID")


class ProjectResponse(BaseModel):
    """Response model for project data."""
    id: str
    name: str
    description: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    azure_folder_path: str
    github_linked: bool
    github_repo_id: Optional[int]
    github_repo_name: Optional[str]
    github_installation_id: Optional[int]
    last_github_sync: Optional[datetime]
    file_count: Optional[int] = 0
    total_size: Optional[int] = 0


class ProjectUpsertResponse(BaseModel):
    """Response model for project upsert operations."""
    project: ProjectResponse
    is_new: bool
    azure_folders_created: List[str]
    github_repo_created: bool
    github_repo_url: Optional[str]
    message: str


class ProjectListResponse(BaseModel):
    """Response model for project listing."""
    projects: List[ProjectResponse]
    total_count: int
    message: str


class ProjectDeletionResponse(BaseModel):
    """Response model for project deletion."""
    success: bool
    azure_cleanup_success: bool
    github_repo_deleted: bool
    message: str
    error_message: Optional[str]


class GitHubLinkRequest(BaseModel):
    """Request model for GitHub linking operations."""
    installation_id: int = Field(..., description="GitHub App installation ID")
    create_repo: bool = Field(True, description="Whether to create a new repository")
    repo_name: Optional[str] = Field(None, description="Repository name (defaults to project name)")


class GitHubLinkResponse(BaseModel):
    """Response model for GitHub linking operations."""
    success: bool
    repo_url: Optional[str]
    repo_id: Optional[int]
    installation_id: Optional[int]
    message: str
    error_message: Optional[str]


class ProjectFileInfoResponse(BaseModel):
    """Response model for project file information."""
    project_id: str
    file_count: int
    total_size: int
    files: List[Dict[str, Any]]


# Dependency to get project management service
async def get_project_management_service(
    db_session = Depends(get_async_db)
) -> ProjectManagementService:
    """Get project management service with all dependencies."""
    from app.core.config import get_settings
    
    settings = get_settings()
    azure_service = AzureFileService()
    
    # Only initialize GitHub service if integration is enabled
    github_service = None
    if settings.GITHUB_INTEGRATION_ENABLED:
        try:
            github_service = GitHubAppService()
        except Exception as e:
            # Log the error but don't fail the entire service
            print(f"Warning: GitHub service initialization failed: {e}")
            github_service = None
    
    supabase_auth = SupabaseJWTValidator()
    
    return ProjectManagementService(
        db_session=db_session,
        azure_service=azure_service,
        github_service=github_service,
        supabase_auth=supabase_auth
    )


@router.post(
    "/upsert",
    response_model=ProjectUpsertResponse,
    summary="Create or update a project",
    description="""
    Create a new project or update an existing one (upsert functionality).
    
    - Creates Azure File Share directory structure for new projects
    - Optionally links project to GitHub repository using GitHub App
    - Validates user exists in Supabase using SERVICE_ROLE_KEY
    - Ensures all projects are stored in user-isolated folders
    """
)
async def upsert_project(
    request: ProjectUpsertRequest,
    user_id: str = Depends(get_current_user_id),
    service: ProjectManagementService = Depends(get_project_management_service)
) -> ProjectUpsertResponse:
    """
    Create or update a project with optional GitHub integration.
    
    Args:
        request: Project upsert request data
        user_id: Supabase user ID from JWT token
        service: Project management service
        
    Returns:
        ProjectUpsertResponse with operation results
        
    Raises:
        HTTPException: If operation fails
    """
    try:
        # Validate GitHub linking requirements
        if request.link_to_github and not request.github_installation_id:
            raise HTTPException(
                status_code=400,
                detail="GitHub installation ID is required when linking to GitHub"
            )
        
        # Perform upsert operation
        result = await service.upsert_project(
            user_id=user_id,
            project_name=request.name,
            project_description=request.description,
            project_id=request.project_id,
            link_to_github=request.link_to_github,
            github_installation_id=request.github_installation_id
        )
        
        # Convert project to response model
        project_response = ProjectResponse(
            id=result.project.id,
            name=result.project.name,
            description=result.project.description,
            status=result.project.status.value,
            created_at=result.project.created_at,
            updated_at=result.project.updated_at,
            azure_folder_path=result.project.azure_folder_path,
            github_linked=result.project.github_linked,
            github_repo_id=result.project.github_repo_id,
            github_repo_name=result.project.github_repo_name,
            github_installation_id=result.project.github_installation_id,
            last_github_sync=result.project.last_github_sync
        )
        
        message = f"{'Created' if result.is_new else 'Updated'} project '{request.name}'"
        if result.github_repo_created:
            message += f" and linked to GitHub repository"
        
        return ProjectUpsertResponse(
            project=project_response,
            is_new=result.is_new,
            azure_folders_created=result.azure_folders_created,
            github_repo_created=result.github_repo_created,
            github_repo_url=result.github_repo_url,
            message=message
        )
        
    except ProjectManagementError as e:
        logger.error(f"Project management error for user {user_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in project upsert for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Project upsert failed: {str(e)}")


@router.get(
    "",
    response_model=ProjectListResponse,
    summary="List user projects",
    description="""
    List all projects for a user with user isolation using Supabase SERVICE_ROLE_KEY.
    
    - Validates user exists in Supabase users table
    - Returns projects with optional file and GitHub information
    - Supports filtering by project status
    - Includes Azure File Share file counts and sizes
    """
)
async def list_user_projects(
    include_files: bool = Query(False, description="Include file information from Azure File Share"),
    include_github_info: bool = Query(False, description="Include GitHub repository information"),
    status_filter: Optional[str] = Query(None, description="Filter by project status"),
    user_id: str = Depends(get_current_user_id),
    service: ProjectManagementService = Depends(get_project_management_service)
) -> ProjectListResponse:
    """
    List all projects for a user with enhanced information.
    
    Args:
        include_files: Whether to include file information
        include_github_info: Whether to include GitHub information
        status_filter: Optional status filter
        user_id: Supabase user ID from JWT token
        service: Project management service
        
    Returns:
        ProjectListResponse with project list
        
    Raises:
        HTTPException: If operation fails
    """
    try:
        # Convert status filter to enum if provided
        from app.models.project import ProjectStatus
        status_enum = None
        if status_filter:
            try:
                status_enum = ProjectStatus(status_filter.lower())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status filter: {status_filter}"
                )
        
        # Get projects from service
        projects_data = await service.list_user_projects(
            user_id=user_id,
            include_files=include_files,
            include_github_info=include_github_info,
            status_filter=status_enum
        )
        
        # Convert to response models
        projects = []
        for project_data in projects_data:
            project_response = ProjectResponse(
                id=project_data["id"],
                name=project_data["name"],
                description=project_data["description"],
                status=project_data["status"],
                created_at=project_data["created_at"],
                updated_at=project_data["updated_at"],
                azure_folder_path=project_data["azure_folder_path"],
                github_linked=project_data["github_linked"],
                github_repo_id=project_data.get("github_info", {}).get("repo_id"),
                github_repo_name=project_data.get("github_info", {}).get("repo_name"),
                github_installation_id=project_data.get("github_info", {}).get("installation_id"),
                last_github_sync=project_data["last_github_sync"],
                file_count=project_data.get("file_count", 0),
                total_size=project_data.get("total_size", 0)
            )
            projects.append(project_response)
        
        return ProjectListResponse(
            projects=projects,
            total_count=len(projects),
            message=f"Retrieved {len(projects)} projects for user"
        )
        
    except ProjectManagementError as e:
        logger.error(f"Project management error for user {user_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error listing projects for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list projects: {str(e)}")


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get project by ID",
    description="""
    Get a specific project by ID with user access validation.
    
    - Validates user exists in Supabase using SERVICE_ROLE_KEY
    - Ensures user has access to the requested project
    - Returns complete project information including GitHub status
    """
)
async def get_project_by_id(
    project_id: str = Path(..., description="Project ID (UUID)"),
    user_id: str = Depends(get_current_user_id),
    service: ProjectManagementService = Depends(get_project_management_service)
) -> ProjectResponse:
    """
    Get a specific project by ID.
    
    Args:
        project_id: Project ID to retrieve
        user_id: Supabase user ID from JWT token
        service: Project management service
        
    Returns:
        ProjectResponse with project data
        
    Raises:
        HTTPException: If project not found or access denied
    """
    try:
        project = await service.get_project_by_id(user_id=user_id, project_id=project_id)
        
        if not project:
            raise HTTPException(
                status_code=404,
                detail=f"Project {project_id} not found"
            )
        
        return ProjectResponse(
            id=project.id,
            name=project.name,
            description=project.description,
            status=project.status.value,
            created_at=project.created_at,
            updated_at=project.updated_at,
            azure_folder_path=project.azure_folder_path,
            github_linked=project.github_linked,
            github_repo_id=project.github_repo_id,
            github_repo_name=project.github_repo_name,
            github_installation_id=project.github_installation_id,
            last_github_sync=project.last_github_sync
        )
        
    except ProjectManagementError as e:
        logger.error(f"Project management error for user {user_id}, project {project_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting project {project_id} for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get project: {str(e)}")


@router.delete(
    "/{project_id}",
    response_model=ProjectDeletionResponse,
    summary="Delete project",
    description="""
    Delete a project with Azure cleanup and optional GitHub repository deletion.
    
    - Validates user access to the project
    - Cleans up Azure File Share files
    - Optionally deletes GitHub repository if linked
    - Supports both soft delete (mark as deleted) and hard delete
    """
)
async def delete_project(
    project_id: str = Path(..., description="Project ID (UUID)"),
    delete_github_repo: bool = Query(False, description="Whether to delete GitHub repository"),
    soft_delete: bool = Query(True, description="Whether to soft delete (mark as deleted)"),
    user_id: str = Depends(get_current_user_id),
    service: ProjectManagementService = Depends(get_project_management_service)
) -> ProjectDeletionResponse:
    """
    Delete a project with cleanup operations.
    
    Args:
        project_id: Project ID to delete
        delete_github_repo: Whether to delete GitHub repository
        soft_delete: Whether to soft delete or hard delete
        user_id: Supabase user ID from JWT token
        service: Project management service
        
    Returns:
        ProjectDeletionResponse with operation results
        
    Raises:
        HTTPException: If operation fails
    """
    try:
        result = await service.delete_project(
            user_id=user_id,
            project_id=project_id,
            delete_github_repo=delete_github_repo,
            soft_delete=soft_delete
        )
        
        if not result.success:
            raise HTTPException(
                status_code=400,
                detail=result.error_message or "Project deletion failed"
            )
        
        message = f"{'Soft deleted' if soft_delete else 'Deleted'} project {project_id}"
        if result.azure_cleanup_success:
            message += " with Azure cleanup"
        if result.github_repo_deleted:
            message += " and GitHub repository deletion"
        
        return ProjectDeletionResponse(
            success=result.success,
            azure_cleanup_success=result.azure_cleanup_success,
            github_repo_deleted=result.github_repo_deleted,
            message=message,
            error_message=result.error_message
        )
        
    except ProjectManagementError as e:
        logger.error(f"Project management error deleting {project_id} for user {user_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error deleting project {project_id} for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Project deletion failed: {str(e)}")


@router.post(
    "/{project_id}/link-github",
    response_model=GitHubLinkResponse,
    summary="Link project to GitHub repository",
    description="""
    Link a project to a GitHub repository using GitHub App authentication.
    
    - Creates a new GitHub repository if requested
    - Updates project with GitHub repository information
    - Sets github_linked flag to true
    - Validates GitHub App installation access
    """
)
async def link_project_to_github(
    project_id: str = Path(..., description="Project ID (UUID)"),
    request: GitHubLinkRequest = Body(...),
    user_id: str = Depends(get_current_user_id),
    service: ProjectManagementService = Depends(get_project_management_service)
) -> GitHubLinkResponse:
    """
    Link a project to a GitHub repository.
    
    Args:
        project_id: Project ID to link
        request: GitHub linking request data
        user_id: Supabase user ID from JWT token
        service: Project management service
        
    Returns:
        GitHubLinkResponse with operation results
        
    Raises:
        HTTPException: If operation fails
    """
    try:
        result = await service.link_project_to_github(
            user_id=user_id,
            project_id=project_id,
            installation_id=request.installation_id,
            create_repo=request.create_repo,
            repo_name=request.repo_name
        )
        
        if not result.success:
            raise HTTPException(
                status_code=400,
                detail=result.error_message or "GitHub linking failed"
            )
        
        message = f"Successfully linked project {project_id} to GitHub"
        if request.create_repo:
            message += " with new repository creation"
        
        return GitHubLinkResponse(
            success=result.success,
            repo_url=result.repo_url,
            repo_id=result.repo_id,
            installation_id=result.installation_id,
            message=message,
            error_message=result.error_message
        )
        
    except GitHubLinkingError as e:
        logger.error(f"GitHub linking error for project {project_id}, user {user_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error linking project {project_id} to GitHub for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"GitHub linking failed: {str(e)}")


@router.post(
    "/{project_id}/unlink-github",
    response_model=GitHubLinkResponse,
    summary="Unlink project from GitHub repository",
    description="""
    Unlink a project from its GitHub repository.
    
    - Removes GitHub repository information from project
    - Sets github_linked flag to false
    - Optionally deletes the GitHub repository
    - Preserves Azure File Share data
    """
)
async def unlink_project_from_github(
    project_id: str = Path(..., description="Project ID (UUID)"),
    delete_repo: bool = Query(False, description="Whether to delete the GitHub repository"),
    user_id: str = Depends(get_current_user_id),
    service: ProjectManagementService = Depends(get_project_management_service)
) -> GitHubLinkResponse:
    """
    Unlink a project from its GitHub repository.
    
    Args:
        project_id: Project ID to unlink
        delete_repo: Whether to delete the GitHub repository
        user_id: Supabase user ID from JWT token
        service: Project management service
        
    Returns:
        GitHubLinkResponse with operation results
        
    Raises:
        HTTPException: If operation fails
    """
    try:
        result = await service.unlink_project_from_github(
            user_id=user_id,
            project_id=project_id,
            delete_repo=delete_repo
        )
        
        if not result.success:
            raise HTTPException(
                status_code=400,
                detail=result.error_message or "GitHub unlinking failed"
            )
        
        message = f"Successfully unlinked project {project_id} from GitHub"
        if delete_repo:
            message += " and deleted repository"
        
        return GitHubLinkResponse(
            success=result.success,
            repo_url=None,
            repo_id=None,
            installation_id=None,
            message=message,
            error_message=result.error_message
        )
        
    except GitHubLinkingError as e:
        logger.error(f"GitHub unlinking error for project {project_id}, user {user_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error unlinking project {project_id} from GitHub for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"GitHub unlinking failed: {str(e)}")


@router.post(
    "/{project_id}/sync-github",
    summary="Sync project with GitHub repository",
    description="""
    Synchronize project files with GitHub repository (only for linked projects).
    
    - Validates project is linked to GitHub
    - Retrieves files from Azure File Share
    - Pushes files to GitHub repository using GitHub App
    - Updates last sync timestamp
    """
)
async def sync_project_with_github(
    project_id: str = Path(..., description="Project ID (UUID)"),
    generation_id: Optional[str] = Query(None, description="Specific generation to sync"),
    user_id: str = Depends(get_current_user_id),
    service: ProjectManagementService = Depends(get_project_management_service)
) -> Dict[str, Any]:
    """
    Synchronize project files with GitHub repository.
    
    Args:
        project_id: Project ID to sync
        generation_id: Optional specific generation to sync
        user_id: Supabase user ID from JWT token
        service: Project management service
        
    Returns:
        Dictionary with sync results
        
    Raises:
        HTTPException: If operation fails
    """
    try:
        success = await service.sync_project_with_github(
            user_id=user_id,
            project_id=project_id,
            generation_id=generation_id
        )
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="GitHub synchronization failed"
            )
        
        return {
            "success": True,
            "message": f"Successfully synchronized project {project_id} with GitHub",
            "synced_at": datetime.utcnow().isoformat()
        }
        
    except ProjectManagementError as e:
        logger.error(f"Project management error syncing {project_id} for user {user_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error syncing project {project_id} with GitHub for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"GitHub synchronization failed: {str(e)}")


@router.get(
    "/{project_id}/files",
    response_model=ProjectFileInfoResponse,
    summary="Get project file information",
    description="""
    Get file information for a project from Azure File Share.
    
    - Lists all files in the project's Azure File Share directory
    - Includes file metadata (size, modification date, generation ID)
    - Optionally includes file content
    - Ensures user isolation and project access validation
    """
)
async def get_project_file_info(
    project_id: str = Path(..., description="Project ID (UUID)"),
    include_content: bool = Query(False, description="Whether to include file content"),
    user_id: str = Depends(get_current_user_id),
    service: ProjectManagementService = Depends(get_project_management_service)
) -> ProjectFileInfoResponse:
    """
    Get file information for a project.
    
    Args:
        project_id: Project ID to get files for
        include_content: Whether to include file content
        user_id: Supabase user ID from JWT token
        service: Project management service
        
    Returns:
        ProjectFileInfoResponse with file information
        
    Raises:
        HTTPException: If operation fails
    """
    try:
        file_info = await service.get_project_file_info(
            user_id=user_id,
            project_id=project_id,
            include_content=include_content
        )
        
        return ProjectFileInfoResponse(**file_info)
        
    except ProjectManagementError as e:
        logger.error(f"Project management error getting files for {project_id}, user {user_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting files for project {project_id}, user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get file information: {str(e)}")