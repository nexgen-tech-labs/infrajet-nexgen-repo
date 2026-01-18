"""
GitHub integration routes for OAuth authentication and repository synchronization.

This module provides endpoints for:
- GitHub OAuth authentication flow
- Repository selection and sync configuration
- Sync status monitoring and history
- Manual synchronization triggers
- GitHub disconnection and token cleanup
"""

import secrets
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from fastapi.responses import RedirectResponse
from logconfig.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.db.session import get_db
from app.middleware.auth import get_current_active_user
from app.models.user import User, GitHubConnection
from app.services.github_service import GitHubIntegrationService
from app.schemas.github import (
    GitHubAuthResponse,
    GitHubCallbackRequest,
    GitHubUserProfile,
    GitHubRepository,
    GitHubRepositoryList,
    GitHubSyncRequest,
    GitHubSyncResponse,
    GitHubSyncHistory,
    GitHubConnectionStatus,
    GitHubDisconnectRequest,
    GitHubDisconnectResponse,
    GitHubProjectSyncRequest,
    GitHubSyncConflictCheckRequest,
    GitHubSyncConflictCheckResponse,
    GitHubSyncRetryRequest,
)
from app.core.github import (
    GitHubError,
    GitHubAuthError,
    GitHubAPIError,
    RepositoryNotFoundError,
    InsufficientPermissionsError,
)

logger = get_logger()
settings = get_settings()
router = APIRouter()

# Initialize GitHub service
github_service = GitHubIntegrationService()


async def _is_user_github_connected(db: AsyncSession, user: User) -> bool:
    """Check if user has an active GitHub connection."""
    result = await db.execute(
        select(GitHubConnection).filter(
            GitHubConnection.supabase_user_id == user.supabase_user_id,
            GitHubConnection.is_github_oauth_connected == True
        )
    )
    connection = result.scalars().first()
    return connection is not None


@router.get("/auth/login", response_model=GitHubAuthResponse)
async def github_auth_login(
    request: Request,
    state: Optional[str] = Query(None, description="CSRF protection state parameter")
):
    """
    Initiate GitHub OAuth authentication flow.
    
    This endpoint generates a GitHub authorization URL and redirects the user
    to GitHub for authentication. The state parameter is used for CSRF protection.
    """
    try:
        logger.info("Initiating GitHub OAuth authentication flow")
        
        # Generate authorization URL with state parameter
        auth_url, generated_state = await github_service.get_authorization_url(state)
        
        # Store state in session for validation
        request.session["github_oauth_state"] = generated_state
        
        logger.info(f"Generated GitHub authorization URL with state: {generated_state}")
        
        return GitHubAuthResponse(
            authorization_url=auth_url,
            state=generated_state
        )
        
    except GitHubError as e:
        logger.error(f"GitHub authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GitHub authentication error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during GitHub auth initiation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate GitHub authentication"
        )


@router.post("/auth/callback", response_model=GitHubUserProfile)
async def github_auth_callback(
    request: Request,
    callback_data: GitHubCallbackRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Handle GitHub OAuth callback and connect account.
    
    This endpoint processes the authorization code from GitHub,
    exchanges it for an access token, and connects the GitHub account
    to the current user.
    """
    try:
        logger.info(f"Processing GitHub OAuth callback for user: {current_user.id}")
        
        # Validate state parameter for CSRF protection
        stored_state = request.session.get("github_oauth_state")
        if not stored_state or stored_state != callback_data.state:
            logger.warning(f"Invalid OAuth state parameter for user: {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid state parameter. Possible CSRF attack."
            )
        
        # Clear state from session
        request.session.pop("github_oauth_state", None)
        
        # Exchange code for token and connect account
        github_profile = await github_service.exchange_code_for_token(
            db, current_user, callback_data.code
        )
        
        logger.info(f"Successfully connected GitHub account for user: {current_user.id}")
        
        return github_profile
        
    except GitHubAuthError as e:
        logger.error(f"GitHub authentication error for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"GitHub authentication failed: {str(e)}"
        )
    except GitHubError as e:
        logger.error(f"GitHub service error for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GitHub service error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during GitHub callback for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process GitHub authentication"
        )


@router.get("/connection/status", response_model=GitHubConnectionStatus)
async def get_github_connection_status(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get GitHub connection status for the current user.
    
    Returns information about whether GitHub is connected,
    username, connection timestamp, and basic statistics.
    """
    try:
        logger.info(f"Getting GitHub connection status for user: {current_user.id}")
        
        connection_status = await github_service.get_connection_status(db, current_user)
        
        logger.info(f"Retrieved GitHub connection status for user: {current_user.id}")
        return connection_status
        
    except Exception as e:
        logger.error(f"Error getting GitHub connection status for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get GitHub connection status"
        )


@router.get("/repositories", response_model=GitHubRepositoryList)
async def get_user_repositories(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(30, ge=1, le=100, description="Items per page")
):
    """
    Get user's GitHub repositories.
    
    Returns a paginated list of repositories that the user has access to.
    Requires GitHub account to be connected.
    """
    try:
        logger.info(f"Getting repositories for user: {current_user.id}")
        
        if not current_user.is_github_connected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitHub account not connected. Please connect your GitHub account first."
            )
        
        repositories = await github_service.get_user_repositories(
            db, current_user, page=page, per_page=per_page
        )
        
        logger.info(f"Retrieved {len(repositories)} repositories for user: {current_user.id}")
        
        return GitHubRepositoryList(
            repositories=repositories,
            total_count=len(repositories),  # This is an approximation
            page=page,
            per_page=per_page
        )
        
    except GitHubAuthError as e:
        logger.error(f"GitHub authentication error for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="GitHub authentication failed. Please reconnect your GitHub account."
        )
    except GitHubError as e:
        logger.error(f"GitHub service error for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GitHub service error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error getting repositories for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get repositories"
        )


@router.get("/repositories/{owner}/{repo}", response_model=GitHubRepository)
async def get_repository(
    owner: str,
    repo: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific repository by owner and name.
    
    Returns detailed information about a specific repository.
    Requires GitHub account to be connected and access to the repository.
    """
    try:
        logger.info(f"Getting repository {owner}/{repo} for user: {current_user.id}")
        
        if not await _is_user_github_connected(db, current_user):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitHub account not connected. Please connect your GitHub account first."
            )
        
        repository = await github_service.get_repository(db, current_user, owner, repo)
        
        logger.info(f"Retrieved repository {owner}/{repo} for user: {current_user.id}")
        return repository
        
    except RepositoryNotFoundError as e:
        logger.warning(f"Repository {owner}/{repo} not found for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository {owner}/{repo} not found or not accessible"
        )
    except InsufficientPermissionsError as e:
        logger.warning(f"Insufficient permissions for repository {owner}/{repo} for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions to access repository {owner}/{repo}"
        )
    except GitHubError as e:
        logger.error(f"GitHub service error for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GitHub service error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error getting repository {owner}/{repo} for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get repository"
        )


@router.post("/sync/project", response_model=GitHubSyncResponse)
async def sync_project_to_github(
    sync_request: GitHubProjectSyncRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Sync an entire project to a GitHub repository.
    
    This endpoint retrieves all files from a project stored in Azure File Share
    and synchronizes them to the specified GitHub repository.
    """
    try:
        logger.info(f"Starting project sync for user {current_user.id}: project {sync_request.project_id} to {sync_request.repository_full_name}")
        
        if not await _is_user_github_connected(db, current_user):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitHub account not connected. Please connect your GitHub account first."
            )
        
        # TODO: Implement project file retrieval from Azure File Share
        # This would typically involve:
        # 1. Get project files from Azure File Share
        # 2. Prepare files_content dictionary
        # For now, we'll use a placeholder
        
        # Get project files (placeholder implementation)
        files_content = await _get_project_files(sync_request.project_id, current_user.id)
        
        if not files_content:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No files found for project {sync_request.project_id}"
            )
        
        # Generate commit message
        commit_message = sync_request.commit_message or f"Sync project {sync_request.project_id} from Infrajet"
        
        # Perform sync
        sync_response = await github_service.sync_project_to_repository(
            db=db,
            user=current_user,
            project_id=sync_request.project_id,
            repository_full_name=sync_request.repository_full_name,
            files_content=files_content,
            commit_message=commit_message,
            branch=sync_request.branch
        )
        
        logger.info(f"Completed project sync for user {current_user.id}: {sync_response.files_synced} files synced")
        return sync_response
        
    except RepositoryNotFoundError as e:
        logger.warning(f"Repository {sync_request.repository_full_name} not found for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository {sync_request.repository_full_name} not found or not accessible"
        )
    except InsufficientPermissionsError as e:
        logger.warning(f"Insufficient permissions for repository {sync_request.repository_full_name} for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Insufficient permissions to write to repository {sync_request.repository_full_name}"
        )
    except GitHubError as e:
        logger.error(f"GitHub service error during sync for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GitHub sync error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error syncing project for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync project to GitHub"
        )


@router.get("/sync/history/{project_id}", response_model=GitHubSyncHistory)
async def get_sync_history(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get synchronization history for a project.
    
    Returns a list of all sync operations performed for the specified project,
    including status, timestamps, and error information.
    """
    try:
        logger.info(f"Getting sync history for project {project_id} for user: {current_user.id}")
        
        sync_history = await github_service.get_sync_history(db, current_user, project_id)
        
        logger.info(f"Retrieved sync history for project {project_id}: {sync_history.total_syncs} records")
        return sync_history
        
    except Exception as e:
        logger.error(f"Error getting sync history for project {project_id} for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get sync history"
        )


@router.post("/sync/retry", response_model=GitHubSyncResponse)
async def retry_failed_sync(
    retry_request: GitHubSyncRetryRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retry a failed synchronization operation.
    
    This endpoint allows retrying a previously failed sync operation
    using the same parameters but with enhanced retry logic.
    """
    try:
        logger.info(f"Retrying sync operation {retry_request.sync_record_id} for user: {current_user.id}")
        
        # TODO: Implement sync retry logic
        # This would involve:
        # 1. Get the failed sync record
        # 2. Extract original sync parameters
        # 3. Retry the sync operation
        
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Sync retry functionality is not yet implemented"
        )
        
    except Exception as e:
        logger.error(f"Error retrying sync for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retry sync operation"
        )


@router.post("/disconnect", response_model=GitHubDisconnectResponse)
async def disconnect_github(
    disconnect_request: GitHubDisconnectRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Disconnect GitHub account from the current user.
    
    This endpoint removes the GitHub connection, optionally revokes
    the access token, and cleans up stored credentials.
    """
    try:
        logger.info(f"Disconnecting GitHub account for user: {current_user.id}")
        
        if not current_user.is_github_connected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitHub account is not connected"
            )
        
        # Disconnect GitHub account
        success = await github_service.disconnect_github(
            db, current_user, revoke_token=disconnect_request.revoke_token
        )
        
        if success:
            logger.info(f"Successfully disconnected GitHub account for user: {current_user.id}")
            return GitHubDisconnectResponse(
                success=True,
                message="GitHub account disconnected successfully",
                token_revoked=disconnect_request.revoke_token
            )
        else:
            logger.error(f"Failed to disconnect GitHub account for user: {current_user.id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to disconnect GitHub account"
            )
        
    except Exception as e:
        logger.error(f"Error disconnecting GitHub account for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to disconnect GitHub account"
        )


# Helper function to get project files (placeholder implementation)
async def _get_project_files(project_id: str, user_id: int) -> dict:
    """
    Get project files from Azure File Share.
    
    This is a placeholder implementation that should be replaced
    with actual Azure File Share integration.
    """
    # TODO: Implement actual project file retrieval from Azure File Share
    # This would involve:
    # 1. Connect to Azure File Share
    # 2. Navigate to user's project directory
    # 3. Read all files and their content
    # 4. Return as dictionary of file_path -> content
    
    # Placeholder return
    return {
        "main.tf": "# Terraform configuration placeholder",
        "variables.tf": "# Variables placeholder",
        "outputs.tf": "# Outputs placeholder"
    }

@router.post("/sync/check-conflicts", response_model=GitHubSyncConflictCheckResponse)
async def check_sync_conflicts(
    conflict_request: GitHubSyncConflictCheckRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Check for potential conflicts before syncing a project.
    
    This endpoint analyzes the project files against the target repository
    to identify potential conflicts and suggest resolution strategies.
    """
    try:
        logger.info(f"Checking sync conflicts for project {conflict_request.project_id} for user: {current_user.id}")
        
        if not current_user.is_github_connected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitHub account not connected. Please connect your GitHub account first."
            )
        
        # TODO: Implement conflict checking logic
        # This would involve:
        # 1. Get project files from Azure File Share
        # 2. Compare with existing files in GitHub repository
        # 3. Identify conflicts and suggest resolution strategies
        
        # Placeholder implementation
        return GitHubSyncConflictCheckResponse(
            project_id=conflict_request.project_id,
            repository_full_name=conflict_request.repository_full_name,
            branch=conflict_request.branch,
            conflicts=[],
            total_conflicts=0,
            can_auto_resolve=0
        )
        
    except Exception as e:
        logger.error(f"Error checking sync conflicts for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check sync conflicts"
        )


@router.get("/sync/status/{project_id}")
async def get_sync_status(
    project_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current synchronization status for a project.
    
    Returns the current sync status, progress information,
    and any ongoing sync operations.
    """
    try:
        logger.info(f"Getting sync status for project {project_id} for user: {current_user.id}")
        
        # Get the most recent sync history to determine current status
        sync_history = await github_service.get_sync_history(db, current_user, project_id)
        
        if not sync_history.sync_records:
            return {
                "project_id": project_id,
                "status": "never_synced",
                "message": "Project has never been synced to GitHub"
            }
        
        latest_sync = sync_history.sync_records[0]  # Most recent sync
        
        return {
            "project_id": project_id,
            "status": latest_sync.sync_status.value,
            "repository": sync_history.repository_full_name,
            "last_sync_at": latest_sync.last_sync_at,
            "last_commit_sha": latest_sync.last_commit_sha,
            "error_message": latest_sync.sync_errors,
            "total_syncs": sync_history.total_syncs,
            "last_successful_sync": sync_history.last_successful_sync
        }
        
    except Exception as e:
        logger.error(f"Error getting sync status for project {project_id} for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get sync status"
        )


@router.post("/sync/manual-trigger", response_model=GitHubSyncResponse)
async def manual_sync_trigger(
    sync_request: GitHubSyncRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually trigger a synchronization operation.
    
    This endpoint allows users to manually trigger a sync operation
    with custom parameters and file selection.
    """
    try:
        logger.info(f"Manual sync trigger for project {sync_request.project_id} for user: {current_user.id}")
        
        if not current_user.is_github_connected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GitHub account not connected. Please connect your GitHub account first."
            )
        
        # Get project files based on sync request parameters
        if sync_request.sync_all_files:
            files_content = await _get_project_files(sync_request.project_id, current_user.id)
        else:
            # Get only specified files
            files_content = await _get_specific_project_files(
                sync_request.project_id, 
                current_user.id, 
                sync_request.file_paths or []
            )
        
        if not files_content:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No files found to sync"
            )
        
        # Generate commit message
        commit_message = sync_request.commit_message or f"Manual sync of project {sync_request.project_id}"
        
        # Perform sync
        sync_response = await github_service.sync_project_to_repository(
            db=db,
            user=current_user,
            project_id=sync_request.project_id,
            repository_full_name=sync_request.repository_full_name,
            files_content=files_content,
            commit_message=commit_message,
            branch=sync_request.branch
        )
        
        logger.info(f"Manual sync completed for user {current_user.id}: {sync_response.files_synced} files synced")
        return sync_response
        
    except Exception as e:
        logger.error(f"Error in manual sync trigger for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trigger manual sync"
        )


@router.get("/sync/metrics")
async def get_sync_metrics(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get synchronization metrics and statistics for the user.
    
    Returns aggregated statistics about the user's GitHub sync operations,
    including success rates, total files synced, and performance metrics.
    """
    try:
        logger.info(f"Getting sync metrics for user: {current_user.id}")
        
        # TODO: Implement metrics aggregation
        # This would involve:
        # 1. Query all sync records for the user
        # 2. Calculate aggregated statistics
        # 3. Return comprehensive metrics
        
        # Placeholder implementation
        return {
            "user_id": current_user.id,
            "total_syncs": 0,
            "successful_syncs": 0,
            "failed_syncs": 0,
            "total_files_synced": 0,
            "total_conflicts_resolved": 0,
            "average_sync_duration": None,
            "last_sync_at": None,
            "connected_repositories": 0
        }
        
    except Exception as e:
        logger.error(f"Error getting sync metrics for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get sync metrics"
        )


# Additional helper function for specific file retrieval
async def _get_specific_project_files(project_id: str, user_id: int, file_paths: List[str]) -> dict:
    """
    Get specific project files from Azure File Share.
    
    This is a placeholder implementation for retrieving only specified files.
    """
    # TODO: Implement actual specific file retrieval from Azure File Share
    # This would filter the files based on the provided file_paths
    
    all_files = await _get_project_files(project_id, user_id)
    
    # Filter files based on requested paths
    specific_files = {
        path: content for path, content in all_files.items() 
        if path in file_paths
    }
    
    return specific_files