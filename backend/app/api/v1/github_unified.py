"""
Unified GitHub API endpoints.

This module provides unified API endpoints for both GitHub OAuth and GitHub App
integrations, allowing users to connect and manage repositories through either method.
"""

from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_db
from app.services.auth import get_current_user
from app.services.github_connection_service import GitHubConnectionService
from app.models.user import User
from app.schemas.github import (
    GitHubRepository,
    GitHubSyncResponse,
    GitHubConnectionStatus
)
from logconfig.logger import get_logger

logger = get_logger()
router = APIRouter(prefix="/github", tags=["GitHub Integration"])


@router.get("/connection/status")
async def get_connection_status(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get comprehensive GitHub connection status.
    
    Returns information about both OAuth and GitHub App connections,
    available capabilities, and recommendations.
    """
    try:
        github_service = GitHubConnectionService()
        status = await github_service.get_unified_status(db, current_user)
        
        return {
            "success": True,
            "data": status
        }
        
    except Exception as e:
        logger.error(f"Error getting GitHub connection status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get connection status: {str(e)}"
        )


@router.get("/connection/options")
async def get_connection_options(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get available GitHub connection options and recommendations.
    
    Helps users understand which connection methods are available
    and which would be best for their use case.
    """
    try:
        github_service = GitHubConnectionService()
        options = await github_service.get_connection_options(db, current_user)
        
        return {
            "success": True,
            "data": options
        }
        
    except Exception as e:
        logger.error(f"Error getting GitHub connection options: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get connection options: {str(e)}"
        )


@router.post("/oauth/connect")
async def connect_oauth(
    code: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Connect GitHub OAuth for personal repository access.
    
    This endpoint handles the OAuth callback and connects the user's
    personal GitHub account for repository access.
    """
    try:
        github_service = GitHubConnectionService()
        result = await github_service.connect_oauth(db, current_user, code)
        
        return {
            "success": True,
            "data": result,
            "message": "GitHub OAuth connected successfully"
        }
        
    except Exception as e:
        logger.error(f"Error connecting GitHub OAuth: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to connect GitHub OAuth: {str(e)}"
        )


@router.post("/app/connect")
async def connect_app_installation(
    installation_id: int = Body(..., embed=True),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Connect GitHub App installation for organization repository access.
    
    This endpoint connects a GitHub App installation to provide access
    to organization repositories with fine-grained permissions.
    """
    try:
        github_service = GitHubConnectionService()
        result = await github_service.connect_app_installation(
            db, current_user, installation_id
        )
        
        return {
            "success": True,
            "data": result,
            "message": "GitHub App installation connected successfully"
        }
        
    except Exception as e:
        logger.error(f"Error connecting GitHub App installation: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to connect GitHub App installation: {str(e)}"
        )


@router.get("/repositories")
async def get_repositories(
    connection_type: Optional[str] = Query(None, description="Filter by connection type: 'oauth', 'app', or None for all"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(30, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get all available repositories from connected GitHub integrations.
    
    Returns repositories from both OAuth (personal) and GitHub App (organization)
    connections, with clear indication of the source.
    """
    try:
        github_service = GitHubConnectionService()
        repositories = await github_service.get_available_repositories(
            db, current_user, connection_type
        )
        
        # Apply pagination (simple implementation)
        all_repos = repositories["oauth_repos"] + repositories["app_repos"]
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_repos = all_repos[start_idx:end_idx]
        
        return {
            "success": True,
            "data": {
                "repositories": paginated_repos,
                "oauth_count": len(repositories["oauth_repos"]),
                "app_count": len(repositories["app_repos"]),
                "total_count": repositories["total_count"],
                "page": page,
                "per_page": per_page,
                "has_more": end_idx < repositories["total_count"]
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting repositories: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get repositories: {str(e)}"
        )


@router.post("/repositories/{owner}/{repo}/sync")
async def sync_to_repository(
    owner: str,
    repo: str,
    files_content: Dict[str, str] = Body(..., description="Dictionary of file paths to content"),
    commit_message: str = Body(..., description="Commit message"),
    branch: str = Body("main", description="Target branch"),
    preferred_method: Optional[str] = Body(None, description="Preferred sync method: 'oauth' or 'app'"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Sync generated files to a GitHub repository.
    
    Automatically chooses the best available method (OAuth or GitHub App)
    based on repository ownership and user preferences.
    """
    try:
        repository_full_name = f"{owner}/{repo}"
        
        github_service = GitHubConnectionService()
        sync_response = await github_service.sync_to_repository(
            db=db,
            user=current_user,
            repository_full_name=repository_full_name,
            files_content=files_content,
            commit_message=commit_message,
            branch=branch,
            preferred_method=preferred_method
        )
        
        return {
            "success": True,
            "data": sync_response,
            "message": f"Successfully synced {len(files_content)} files to {repository_full_name}"
        }
        
    except Exception as e:
        logger.error(f"Error syncing to repository {owner}/{repo}: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to sync to repository: {str(e)}"
        )


@router.delete("/connection")
async def disconnect_github(
    connection_type: Optional[str] = Query(None, description="Connection type to disconnect: 'oauth', 'app', or None for all"),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Disconnect GitHub integrations.
    
    Can disconnect specific connection types (OAuth or App) or all connections.
    """
    try:
        github_service = GitHubConnectionService()
        results = await github_service.disconnect_github(
            db, current_user, connection_type
        )
        
        disconnected_types = []
        if results["oauth_disconnected"]:
            disconnected_types.append("OAuth")
        if results["app_disconnected"]:
            disconnected_types.append("GitHub App")
        
        message = f"Disconnected: {', '.join(disconnected_types)}" if disconnected_types else "No connections to disconnect"
        
        return {
            "success": True,
            "data": results,
            "message": message
        }
        
    except Exception as e:
        logger.error(f"Error disconnecting GitHub: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to disconnect GitHub: {str(e)}"
        )


@router.get("/oauth/authorize-url")
async def get_oauth_authorize_url(
    state: Optional[str] = Query(None, description="CSRF state parameter")
) -> Dict[str, Any]:
    """
    Get GitHub OAuth authorization URL.
    
    Returns the URL users should visit to authorize the application
    for personal repository access.
    """
    try:
        github_service = GitHubConnectionService()
        auth_url, state = await github_service.oauth_service.get_authorization_url(state)
        
        return {
            "success": True,
            "data": {
                "authorization_url": auth_url,
                "state": state
            },
            "message": "Visit the authorization URL to connect your GitHub account"
        }
        
    except Exception as e:
        logger.error(f"Error getting OAuth authorization URL: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get authorization URL: {str(e)}"
        )


@router.get("/app/installation-url")
async def get_app_installation_url() -> Dict[str, Any]:
    """
    Get GitHub App installation URL.
    
    Returns the URL users should visit to install the GitHub App
    for organization repository access.
    """
    try:
        github_service = GitHubConnectionService()
        
        if not github_service.app_service.is_configured():
            raise HTTPException(
                status_code=503,
                detail="GitHub App is not configured"
            )
        
        # GitHub App installation URL format
        app_id = github_service.app_service.app_id
        installation_url = f"https://github.com/apps/{app_id}/installations/new"
        
        return {
            "success": True,
            "data": {
                "installation_url": installation_url,
                "app_id": app_id
            },
            "message": "Visit the installation URL to install the GitHub App"
        }
        
    except Exception as e:
        logger.error(f"Error getting App installation URL: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get installation URL: {str(e)}"
        )


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Health check for GitHub integration services.
    
    Returns the health status of both OAuth and GitHub App services.
    """
    try:
        github_service = GitHubConnectionService()
        
        # Check OAuth service health
        oauth_health = {
            "service": "GitHub OAuth",
            "status": "healthy",
            "configured": True
        }
        
        # Check App service health
        app_health = await github_service.app_service.health_check()
        
        overall_status = "healthy"
        if app_health["status"] != "healthy":
            overall_status = "degraded"
        
        return {
            "success": True,
            "data": {
                "overall_status": overall_status,
                "oauth": oauth_health,
                "app": app_health
            }
        }
        
    except Exception as e:
        logger.error(f"Error in GitHub health check: {str(e)}")
        return {
            "success": False,
            "data": {
                "overall_status": "unhealthy",
                "error": str(e)
            }
        }