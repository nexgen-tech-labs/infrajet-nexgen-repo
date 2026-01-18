"""
GitHub App integration routes for repository operations and webhook handling.

This module provides endpoints for:
- GitHub App authentication and installation management
- Repository creation, push, and sync operations using GitHub App
- User repository access validation through GitHub App installations
- GitHub App webhook handling for installation events
"""

import json
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, status, Header
from fastapi.responses import JSONResponse
from logconfig.logger import get_logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.db.session import get_db
from app.middleware.supabase_auth import get_current_user_id
from app.services.github_app_service import (
    GitHubAppService,
    GitHubAppError,
    GitHubAppAuthError,
    GitHubAppAPIError,
    GitHubAppRateLimitError,
    get_github_app_service
)
from app.schemas.github import (
    GitHubInstallation,
    GitHubAppRepository,
    GitHubAppCreateRepoRequest,
    GitHubAppPushRequest,
    GitHubAppSyncRequest,
    GitHubAppSyncResponse,
    GitHubAppValidateAccessRequest,
    GitHubAppValidateAccessResponse,
    GitHubAppWebhookRequest,
    GitHubAppWebhookResponse,
    GitHubAppTokenResponse,
    GitHubAppAuthRequest,
    GitHubAppInstallUrlRequest,
    GitHubAppInstallUrlResponse
)

logger = get_logger()
settings = get_settings()
router = APIRouter()


@router.get("/installations", response_model=List[GitHubInstallation])
async def get_user_installations(
    user_access_token: str = Header(..., alias="X-GitHub-Token"),
    github_app_service: GitHubAppService = Depends(get_github_app_service)
):
    """
    Get GitHub App installations accessible to a user.
    
    This endpoint retrieves all GitHub App installations that the user
    has access to, which can be used for repository operations.
    
    Args:
        user_access_token: User's GitHub access token (from header)
        
    Returns:
        List of GitHubInstallation objects
    """
    try:
        logger.info("Getting user GitHub App installations")
        
        installations = await github_app_service.get_user_installations(user_access_token)
        
        logger.info(f"Retrieved {len(installations)} installations")
        return installations
        
    except GitHubAppAuthError as e:
        logger.error(f"GitHub App authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"GitHub App authentication failed: {str(e)}"
        )
    except GitHubAppAPIError as e:
        logger.error(f"GitHub App API error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GitHub App API error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error getting user installations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user installations"
        )


@router.post("/installation/token", response_model=GitHubAppTokenResponse)
async def get_installation_token(
    auth_request: GitHubAppAuthRequest,
    user_id: str = Depends(get_current_user_id),
    github_app_service: GitHubAppService = Depends(get_github_app_service)
):
    """
    Get installation access token for repository operations.
    
    This endpoint generates an installation access token that can be used
    for repository operations within the specified installation.
    
    Args:
        auth_request: GitHub App authentication request with installation ID
        user_id: Current user ID from Supabase authentication
        
    Returns:
        GitHubAppTokenResponse with access token and metadata
    """
    try:
        logger.info(f"Getting installation token for installation {auth_request.installation_id}")
        
        # Get installation access token
        access_token = await github_app_service.get_installation_access_token(
            auth_request.installation_id
        )
        
        # Return token response (simplified - in production you might want to cache this)
        return GitHubAppTokenResponse(
            token=access_token,
            expires_at="2024-01-01T00:00:00Z",  # GitHub tokens typically expire in 1 hour
            permissions={},
            repository_selection="selected"
        )
        
    except GitHubAppAuthError as e:
        logger.error(f"GitHub App authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"GitHub App authentication failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error getting installation token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get installation token"
        )


@router.post("/repositories", response_model=GitHubAppRepository)
async def create_repository(
    create_request: GitHubAppCreateRepoRequest,
    user_id: str = Depends(get_current_user_id),
    github_app_service: GitHubAppService = Depends(get_github_app_service)
):
    """
    Create a new repository using GitHub App.
    
    This endpoint creates a new repository in the specified installation
    using GitHub App authentication.
    
    Args:
        create_request: Repository creation request with installation ID and details
        user_id: Current user ID from Supabase authentication
        
    Returns:
        GitHubAppRepository object with repository details
    """
    try:
        logger.info(f"Creating repository {create_request.name} for user {user_id}")
        
        # Create repository using GitHub App
        repository = await github_app_service.create_repository(
            installation_id=create_request.installation_id,
            repo_name=create_request.name,
            description=create_request.description,
            private=create_request.private,
            owner=create_request.owner
        )
        
        # Convert to API response model
        return GitHubAppRepository(
            id=repository.id,
            name=repository.name,
            full_name=repository.full_name,
            description=repository.description,
            private=repository.private,
            html_url=repository.html_url,
            clone_url=repository.clone_url,
            created_at=repository.created_at,
            updated_at=repository.updated_at
        )
        
    except GitHubAppAuthError as e:
        logger.error(f"GitHub App authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"GitHub App authentication failed: {str(e)}"
        )
    except GitHubAppAPIError as e:
        logger.error(f"GitHub App API error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GitHub App API error: {str(e)}"
        )
    except GitHubAppRateLimitError as e:
        logger.error(f"GitHub App rate limit error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"GitHub API rate limit exceeded: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error creating repository: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create repository"
        )


@router.post("/repositories/push")
async def push_files(
    push_request: GitHubAppPushRequest,
    user_id: str = Depends(get_current_user_id),
    github_app_service: GitHubAppService = Depends(get_github_app_service)
):
    """
    Push files to a repository using GitHub App.
    
    This endpoint pushes files to an existing repository using GitHub App
    authentication and returns the commit SHA.
    
    Args:
        push_request: Push request with installation ID, repository details, and files
        user_id: Current user ID from Supabase authentication
        
    Returns:
        Dictionary with commit SHA and push details
    """
    try:
        logger.info(f"Pushing {len(push_request.files)} files to {push_request.repo_owner}/{push_request.repo_name}")
        
        # Push files using GitHub App
        commit_sha = await github_app_service.push_files(
            installation_id=push_request.installation_id,
            repo_owner=push_request.repo_owner,
            repo_name=push_request.repo_name,
            files=push_request.files,
            commit_message=push_request.commit_message,
            branch=push_request.branch
        )
        
        return {
            "success": True,
            "commit_sha": commit_sha,
            "files_pushed": len(push_request.files),
            "repository_url": f"https://github.com/{push_request.repo_owner}/{push_request.repo_name}",
            "commit_url": f"https://github.com/{push_request.repo_owner}/{push_request.repo_name}/commit/{commit_sha}",
            "branch": push_request.branch
        }
        
    except GitHubAppAuthError as e:
        logger.error(f"GitHub App authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"GitHub App authentication failed: {str(e)}"
        )
    except GitHubAppAPIError as e:
        logger.error(f"GitHub App API error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GitHub App API error: {str(e)}"
        )
    except GitHubAppRateLimitError as e:
        logger.error(f"GitHub App rate limit error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"GitHub API rate limit exceeded: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error pushing files: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to push files"
        )


@router.post("/repositories/sync", response_model=GitHubAppSyncResponse)
async def sync_repository(
    sync_request: GitHubAppSyncRequest,
    user_id: str = Depends(get_current_user_id),
    github_app_service: GitHubAppService = Depends(get_github_app_service)
):
    """
    Sync files to a repository with conflict detection.
    
    This endpoint syncs files to an existing repository using GitHub App
    authentication with conflict detection and resolution.
    
    Args:
        sync_request: Sync request with installation ID, repository details, and files
        user_id: Current user ID from Supabase authentication
        
    Returns:
        GitHubAppSyncResponse with sync results
    """
    try:
        logger.info(f"Syncing {len(sync_request.files)} files to {sync_request.repo_owner}/{sync_request.repo_name}")
        
        # Sync repository using GitHub App
        sync_result = await github_app_service.sync_repository(
            installation_id=sync_request.installation_id,
            repo_owner=sync_request.repo_owner,
            repo_name=sync_request.repo_name,
            files=sync_request.files,
            commit_message=sync_request.commit_message,
            branch=sync_request.branch
        )
        
        return GitHubAppSyncResponse(
            success=sync_result["success"],
            commit_sha=sync_result.get("commit_sha"),
            files_synced=sync_result["files_synced"],
            repository_url=sync_result["repository_url"],
            commit_url=sync_result.get("commit_url")
        )
        
    except GitHubAppAuthError as e:
        logger.error(f"GitHub App authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"GitHub App authentication failed: {str(e)}"
        )
    except GitHubAppAPIError as e:
        logger.error(f"GitHub App API error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GitHub App API error: {str(e)}"
        )
    except GitHubAppRateLimitError as e:
        logger.error(f"GitHub App rate limit error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"GitHub API rate limit exceeded: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error syncing repository: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync repository"
        )


@router.post("/repositories/validate-access", response_model=GitHubAppValidateAccessResponse)
async def validate_repository_access(
    validate_request: GitHubAppValidateAccessRequest,
    user_id: str = Depends(get_current_user_id),
    github_app_service: GitHubAppService = Depends(get_github_app_service)
):
    """
    Validate user access to repository through GitHub App installation.
    
    This endpoint validates that a user has access to a specific repository
    through a GitHub App installation.
    
    Args:
        validate_request: Validation request with user token, installation ID, and repository details
        user_id: Current user ID from Supabase authentication
        
    Returns:
        GitHubAppValidateAccessResponse with access validation results
    """
    try:
        logger.info(f"Validating access to {validate_request.repo_owner}/{validate_request.repo_name} for user {user_id}")
        
        # Validate repository access
        has_access = await github_app_service.validate_user_repository_access(
            user_access_token=validate_request.user_access_token,
            installation_id=validate_request.installation_id,
            repo_owner=validate_request.repo_owner,
            repo_name=validate_request.repo_name
        )
        
        return GitHubAppValidateAccessResponse(
            has_access=has_access,
            installation_found=True,  # If we got here, installation exists
            repository_accessible=has_access
        )
        
    except GitHubAppAuthError as e:
        logger.error(f"GitHub App authentication error: {str(e)}")
        return GitHubAppValidateAccessResponse(
            has_access=False,
            installation_found=False,
            repository_accessible=False
        )
    except GitHubAppAPIError as e:
        logger.error(f"GitHub App API error: {str(e)}")
        return GitHubAppValidateAccessResponse(
            has_access=False,
            installation_found=True,
            repository_accessible=False
        )
    except Exception as e:
        logger.error(f"Error validating repository access: {str(e)}")
        return GitHubAppValidateAccessResponse(
            has_access=False,
            installation_found=False,
            repository_accessible=False
        )


@router.post("/webhook", response_model=GitHubAppWebhookResponse)
async def handle_webhook(
    request: Request,
    x_github_event: str = Header(..., alias="X-GitHub-Event"),
    x_hub_signature_256: str = Header(..., alias="X-Hub-Signature-256"),
    github_app_service: GitHubAppService = Depends(get_github_app_service)
):
    """
    Handle GitHub App webhook events.
    
    This endpoint receives and processes GitHub App webhook events such as
    installation events, repository events, and push events.
    
    Args:
        request: FastAPI request object containing webhook payload
        x_github_event: GitHub event type header
        x_hub_signature_256: GitHub signature header for validation
        
    Returns:
        GitHubAppWebhookResponse with handling results
    """
    try:
        # Get raw payload
        payload = await request.body()
        
        logger.info(f"Received GitHub webhook event: {x_github_event}")
        
        # Validate webhook signature
        if not github_app_service.validate_webhook_signature(payload, x_hub_signature_256):
            logger.warning("Invalid webhook signature")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature"
            )
        
        # Parse payload
        try:
            payload_data = json.loads(payload.decode('utf-8'))
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON payload: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON payload"
            )
        
        # Handle webhook event
        result = await github_app_service.handle_webhook_event(x_github_event, payload_data)
        
        return GitHubAppWebhookResponse(
            handled=result.get("handled", False),
            message=result.get("message", "Event processed"),
            error=result.get("error")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling webhook: {str(e)}")
        return GitHubAppWebhookResponse(
            handled=False,
            message="Webhook processing failed",
            error=str(e)
        )


@router.get("/install", response_model=GitHubAppInstallUrlResponse)
async def get_installation_url(
    request: GitHubAppInstallUrlRequest = None,
    user_id: str = Depends(get_current_user_id)
):
    """
    Generate GitHub App installation URL.

    This endpoint generates the URL where users can install the GitHub App.
    The URL can include optional parameters for state tracking and suggested organizations.

    Args:
        request: Optional installation URL request with state and target parameters
        user_id: Current user ID from Supabase authentication

    Returns:
        GitHubAppInstallUrlResponse with installation URL and metadata
    """
    try:
        logger.info(f"Generating GitHub App installation URL for user: {user_id}")

        # For now, we'll use a placeholder app name
        # In production, this should be configured in settings or derived from GitHub API
        app_name = settings.GITHUB_APP_NAME or "infrajet"  # Default fallback

        # Base GitHub Apps installation URL
        base_url = "https://github.com/apps"
        installation_url = f"{base_url}/{app_name}/installations/new"

        # Add query parameters if provided
        query_params = []
        if request and request.state:
            query_params.append(f"state={request.state}")
        if request and request.suggested_target_id:
            query_params.append(f"suggested_target_id={request.suggested_target_id}")

        if query_params:
            installation_url += "?" + "&".join(query_params)

        # Direct app page URL
        github_app_url = f"{base_url}/{app_name}"

        logger.info(f"Generated installation URL for app: {app_name}")

        return GitHubAppInstallUrlResponse(
            installation_url=installation_url,
            app_name=app_name,
            state=request.state if request else None,
            github_app_url=github_app_url
        )

    except Exception as e:
        logger.error(f"Error generating installation URL for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate installation URL"
        )


@router.get("/health")
async def health_check(
    github_app_service: GitHubAppService = Depends(get_github_app_service)
):
    """
    GitHub App service health check.
    
    This endpoint performs a comprehensive health check of the GitHub App
    service including configuration validation, JWT generation, and API connectivity.
    
    Returns:
        Dictionary with health check results
    """
    try:
        health_status = await github_app_service.health_check()
        
        # Set appropriate HTTP status code based on health
        if health_status["status"] == "healthy":
            status_code = status.HTTP_200_OK
        elif health_status["status"] == "degraded":
            status_code = status.HTTP_200_OK  # Still operational
        else:
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        
        return JSONResponse(
            status_code=status_code,
            content=health_status
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "service": "GitHub App",
                "status": "unhealthy",
                "checks": {},
                "errors": [f"Health check failed: {str(e)}"]
            }
        )