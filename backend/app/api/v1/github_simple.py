"""
Simplified GitHub API endpoints - App-only integration.

This module provides simplified GitHub integration using only GitHub App
with OAuth flow for automatic installation mapping.
"""

from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_async_db
from app.dependencies.auth import get_current_user, CurrentUser
from app.models.user import GitHubConnection
from app.services.github_app_oauth_service import GitHubAppOAuthService
from app.services.project_github_service import ProjectGitHubService

from logconfig.logger import get_logger

logger = get_logger()
router = APIRouter(prefix="/github", tags=["GitHub Integration"])


@router.get("/status")
async def get_github_status(
    db: AsyncSession = Depends(get_async_db),
    current_user: CurrentUser = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get GitHub connection status for the current user.
    
    Returns connection status, username, installation info, and repository count.
    """
    try:
        github_service = GitHubAppOAuthService()
        status = await github_service.get_connection_status(db, current_user)
        
        return {
            "success": True,
            "data": status
        }
        
    except Exception as e:
        logger.error(f"Error getting GitHub status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get GitHub status: {str(e)}"
        )


@router.get("/connect-url")
async def get_connect_url(
    state: Optional[str] = Query(None, description="CSRF state parameter"),
    current_user: CurrentUser = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get GitHub App OAuth authorization URL.

    This URL handles both app installation (if needed) and user authorization automatically.
    Users just need to visit this URL and authorize the app.
    """
    try:
        github_service = GitHubAppOAuthService()

        if not github_service.is_configured():
            raise HTTPException(
                status_code=503,
                detail="GitHub App is not configured. Please check environment variables."
            )

        auth_url, state = await github_service.get_authorization_url(str(current_user.id), state)

        return {
            "success": True,
            "data": {
                "authorization_url": auth_url,
                "state": state,
                "instructions": "Visit the authorization URL to connect your GitHub account and repositories"
            }
        }

    except Exception as e:
        logger.error(f"Error getting connect URL: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get connect URL: {str(e)}"
        )


@router.get("/callback")
async def github_callback(
    code: str = Query(..., description="Authorization code from GitHub"),
    state: str = Query(..., description="State parameter for CSRF protection"),
    db: AsyncSession = Depends(get_async_db)
) -> Any:
    """
    Handle GitHub OAuth callback.

    This endpoint is called by GitHub after user authorization.
    It connects the GitHub account using the user_id from state.
    """
    from fastapi.responses import RedirectResponse
    import os
    from app.models.user import User

    try:
        # Parse state to extract user_id
        if ":" not in state:
            raise ValueError("Invalid state format")

        user_id_str, _ = state.split(":", 1)
        user_id = int(user_id_str)

        # Get user from database
        result = await db.execute(select(User).filter(User.id == user_id))
        user = result.scalars().first()

        if not user:
            raise ValueError("User not found")

        # Get installations first
        github_service = GitHubAppOAuthService()
        token_data = await github_service.exchange_code_for_tokens(code)
        installations = token_data["installations"]

        if not installations:
            # No installations found, redirect to install URL
            try:
                install_url = github_service.get_install_url()
                return RedirectResponse(url=install_url)
            except ValueError as e:
                logger.error(f"Install URL not configured: {e}")
                return {
                    "success": False,
                    "error": "GitHub App installation required. Please install the app to your account.",
                    "install_url": "https://github.com/apps/YOUR_APP_SLUG/installations/new"
                }

        # Installations found, connect the user
        result = await github_service.connect_user_github(db, user, code)

        frontend_callback_url = os.getenv("GITHUB_FRONTEND_CALLBACK_URL")

        if frontend_callback_url:
            # Redirect to frontend with success
            redirect_url = f"{frontend_callback_url}?success=true&message={result['message']}"
            return RedirectResponse(url=redirect_url)

        # Return JSON for API consumption
        return {
            "success": True,
            "data": result,
            "message": "GitHub connected successfully!"
        }

    except Exception as e:
        logger.error(f"Error in GitHub callback: {str(e)}")

        frontend_callback_url = os.getenv("GITHUB_FRONTEND_CALLBACK_URL")

        if frontend_callback_url:
            # Redirect to frontend with error
            redirect_url = f"{frontend_callback_url}?success=false&error={str(e)}"
            return RedirectResponse(url=redirect_url)

        # Return JSON error
        return {
            "success": False,
            "error": str(e),
            "message": "GitHub connection failed."
        }


@router.post("/connect")
async def connect_github(
    code: str = Body(..., embed=True, description="Authorization code from GitHub callback"),
    db: AsyncSession = Depends(get_async_db),
    current_user: CurrentUser = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Connect GitHub App for the current user.
    
    This endpoint handles the OAuth callback and automatically:
    1. Exchanges the code for access tokens
    2. Gets user information from GitHub
    3. Finds and connects the user's app installations
    4. Maps everything to the current Supabase user
    
    No manual installation ID required!
    """
    try:
        github_service = GitHubAppOAuthService()
        result = await github_service.connect_user_github(db, current_user, code)
        
        return {
            "success": True,
            "data": result,
            "message": "GitHub connected successfully! You can now access your repositories."
        }
        
    except Exception as e:
        logger.error(f"Error connecting GitHub: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to connect GitHub: {str(e)}"
        )


@router.get("/repositories")
async def get_repositories(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(30, ge=1, le=100, description="Items per page"),
    use_oauth_token: bool = Query(False, description="Use OAuth token for user's repos only (default: False uses installation token)"),
    db: AsyncSession = Depends(get_async_db),
    current_user: CurrentUser = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get repositories accessible through GitHub.

    Args:
        use_oauth_token: If True, returns only user's personal repositories using OAuth token.
                        If False (default), returns repositories accessible through GitHub App installation
                        (includes org repos where app is installed).

    Returns:
        List of accessible repositories
    """
    try:
        github_service = GitHubAppOAuthService()
        repositories = await github_service.get_user_repositories(db, current_user, use_oauth_token=use_oauth_token)

        # Apply simple pagination
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_repos = repositories[start_idx:end_idx]

        token_type = "OAuth token (user repos only)" if use_oauth_token else "installation token (app-accessible repos)"

        return {
            "success": True,
            "data": {
                "repositories": [
                    {
                        "id": repo.id,
                        "name": repo.name,
                        "full_name": repo.full_name,
                        "description": repo.description,
                        "private": repo.private,
                        "html_url": repo.html_url,
                        "clone_url": repo.clone_url,
                        "created_at": repo.created_at,
                        "updated_at": repo.updated_at
                    }
                    for repo in paginated_repos
                ],
                "total_count": len(repositories),
                "page": page,
                "per_page": per_page,
                "has_more": end_idx < len(repositories),
                "token_type": token_type
            },
            "message": f"Found {len(repositories)} accessible repositories using {token_type}"
        }

    except Exception as e:
        logger.error(f"Error getting repositories: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get repositories: {str(e)}"
        )


@router.post("/repositories")
async def create_repository(
    name: str = Body(..., description="Repository name"),
    description: str = Body("", description="Repository description"),
    private: bool = Body(False, description="Whether repository should be private"),
    use_oauth_token: bool = Body(True, description="Use OAuth token for personal repos (default: True)"),
    db: AsyncSession = Depends(get_async_db),
    current_user: CurrentUser = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Create a new GitHub repository.

    Args:
        name: Repository name
        description: Repository description
        private: Whether repository should be private
        use_oauth_token: If True, create personal repo. If False, create org repo (if app installed).

    Returns:
        Repository creation result
    """
    try:
        logger.info(f"Creating repository '{name}' for user {current_user.id}, private={private}, use_oauth={use_oauth_token}")

        # Validate repository name
        if not name or not name.strip():
            raise HTTPException(
                status_code=400,
                detail="Repository name is required and cannot be empty"
            )

        # Validate name format (GitHub rules)
        if not name.replace('-', '').replace('_', '').isalnum():
            raise HTTPException(
                status_code=400,
                detail="Repository name can only contain alphanumeric characters, hyphens, and underscores"
            )

        if len(name) > 100:
            raise HTTPException(
                status_code=400,
                detail="Repository name cannot be longer than 100 characters"
            )

        github_service = GitHubAppOAuthService()
        result = await github_service.create_repository(
            db=db,
            user=current_user,
            repo_name=name.strip(),
            description=description.strip() if description else "",
            private=bool(private),
            use_oauth_token=bool(use_oauth_token)
        )

        logger.info(f"Successfully created repository {result['repository']['full_name']} for user {current_user.id}")

        return {
            "success": True,
            "data": result,
            "message": f"Successfully created repository {result['repository']['full_name']}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating repository '{name}' for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to create repository: {str(e)}"
        )


@router.post("/repositories/{owner}/{repo}/sync")
async def sync_to_repository(
    owner: str,
    repo: str,
    files_content: Dict[str, str] = Body(..., description="Dictionary of file paths to content"),
    commit_message: str = Body(..., description="Commit message"),
    branch: str = Body("main", description="Target branch"),
    use_oauth_token: bool = Body(False, description="Use OAuth token instead of installation token"),
    db: AsyncSession = Depends(get_async_db),
    current_user: CurrentUser = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Sync generated files to a GitHub repository.

    Args:
        owner: Repository owner
        repo: Repository name
        files_content: Dictionary of file paths to content
        commit_message: Commit message
        branch: Target branch
        use_oauth_token: If True, use OAuth token. If False (default), use installation token.

    Returns:
        Sync result
    """
    try:
        if not files_content:
            raise HTTPException(
                status_code=400,
                detail="No files provided for sync"
            )

        repository_full_name = f"{owner}/{repo}"

        github_service = GitHubAppOAuthService()
        sync_result = await github_service.sync_files_to_repository(
            db=db,
            user=current_user,
            repository_full_name=repository_full_name,
            files_content=files_content,
            commit_message=commit_message,
            branch=branch,
            use_oauth_token=use_oauth_token
        )

        return {
            "success": True,
            "data": sync_result,
            "message": f"Successfully synced {len(files_content)} files to {repository_full_name}"
        }

    except Exception as e:
        logger.error(f"Error syncing to repository {owner}/{repo}: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to sync to repository: {str(e)}"
        )


@router.delete("/disconnect")
async def disconnect_github(
    db: AsyncSession = Depends(get_async_db),
    current_user: CurrentUser = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Disconnect GitHub App for the current user.
    
    This will remove the GitHub connection and the user will need to reconnect
    to access repositories again.
    """
    try:
        github_service = GitHubAppOAuthService()
        success = await github_service.disconnect_github(db, current_user)
        
        if success:
            return {
                "success": True,
                "message": "GitHub disconnected successfully"
            }
        else:
            return {
                "success": False,
                "message": "No GitHub connection found to disconnect"
            }
        
    except Exception as e:
        logger.error(f"Error disconnecting GitHub: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to disconnect GitHub: {str(e)}"
        )


# Project-GitHub Integration Endpoints

@router.get("/projects/{project_id}/github-status")
async def get_project_github_status(
    project_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: CurrentUser = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get GitHub integration status for a project.

    Args:
        project_id: Project ID

    Returns:
        Project GitHub status
    """
    try:
        service = ProjectGitHubService()
        result = await service.get_project_github_status(db, current_user, project_id)

        if not result["success"]:
            raise HTTPException(status_code=404, detail=result["error"])

        return {
            "success": True,
            "data": result["data"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting project GitHub status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get project GitHub status: {str(e)}"
        )


@router.post("/projects/{project_id}/link-repo")
async def link_project_to_repo(
    project_id: str,
    repo_name: str = Body(..., description="GitHub repository name"),
    repo_owner: Optional[str] = Body(None, description="GitHub repository owner (optional - defaults to user's GitHub username)"),
    use_oauth_token: bool = Body(False, description="Use OAuth token for personal repos"),
    db: AsyncSession = Depends(get_async_db),
    current_user: CurrentUser = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Link a project to a GitHub repository.

    Args:
        project_id: Project ID
        repo_name: Repository name
        repo_owner: Repository owner (optional - defaults to user's GitHub username if not provided)
        use_oauth_token: Use OAuth token for personal repos

    Returns:
        Link operation result
    """
    try:
        # If repo_owner not provided, get it from user's GitHub connection
        if not repo_owner:
            result = await db.execute(
                select(GitHubConnection).filter(
                    GitHubConnection.supabase_user_id == current_user.supabase_user_id,
                    GitHubConnection.is_active == True
                )
            )
            github_conn = result.scalars().first()

            if not github_conn or not github_conn.github_username:
                raise HTTPException(
                    status_code=400,
                    detail="Repository owner not provided and user is not connected to GitHub"
                )

            repo_owner = github_conn.github_username
            logger.info(f"Using GitHub username '{repo_owner}' as repository owner for user {current_user.id}")

        service = ProjectGitHubService()
        result = await service.link_project_to_repo(
            db, current_user, project_id, repo_owner, repo_name, use_oauth_token
        )

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error linking project to repo: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to link project to repository: {str(e)}"
        )


@router.delete("/projects/{project_id}/unlink-repo")
async def unlink_project_from_repo(
    project_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: CurrentUser = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Unlink a project from its GitHub repository.

    Args:
        project_id: Project ID

    Returns:
        Unlink operation result
    """
    try:
        service = ProjectGitHubService()
        result = await service.unlink_project_from_repo(db, current_user, project_id)

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unlinking project from repo: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to unlink project from repository: {str(e)}"
        )


@router.post("/projects/{project_id}/push")
async def push_project_to_repo(
    project_id: str,
    generation_id: Optional[str] = Body(None, description="Specific generation ID, or all"),
    commit_message: str = Body("Manual sync from InfraJet", description="Commit message"),
    branch: str = Body("main", description="Target branch"),
    db: AsyncSession = Depends(get_async_db),
    current_user: CurrentUser = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Push project files to linked GitHub repository.

    Args:
        project_id: Project ID
        generation_id: Optional specific generation, or all generations
        commit_message: Commit message
        branch: Target branch

    Returns:
        Push operation result
    """
    try:
        service = ProjectGitHubService()
        result = await service.push_project_files_to_repo(
            db, current_user, project_id, generation_id, commit_message, branch
        )

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pushing project to repo: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to push project to repository: {str(e)}"
        )


@router.post("/projects/{project_id}/pull")
async def pull_repo_to_project(
    project_id: str,
    repo_path: str = Body("", description="Repository sub-path"),
    branch: str = Body("main", description="Branch to pull from"),
    db: AsyncSession = Depends(get_async_db),
    current_user: CurrentUser = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Pull files from linked GitHub repository to project.

    Args:
        project_id: Project ID
        repo_path: Optional repository sub-path
        branch: Branch to pull from

    Returns:
        Pull operation result
    """
    try:
        service = ProjectGitHubService()
        result = await service.pull_repo_to_project(
            db, current_user, project_id, repo_path, branch
        )

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pulling repo to project: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to pull repository to project: {str(e)}"
        )


@router.post("/projects/{project_id}/branches")
async def create_project_branch(
    project_id: str,
    new_branch_name: str = Body(..., description="Name of the new branch to create"),
    source_branch: str = Body("main", description="Source branch to create from"),
    db: AsyncSession = Depends(get_async_db),
    current_user: CurrentUser = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Create a new branch in a project's linked GitHub repository.

    Args:
        project_id: Project ID
        new_branch_name: Name of the new branch to create
        source_branch: Source branch to create from (default: "main")

    Returns:
        Branch creation result
    """
    try:
        service = ProjectGitHubService()
        result = await service.create_project_branch(
            db, current_user, project_id, new_branch_name, source_branch
        )

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating project branch: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create project branch: {str(e)}"
        )


@router.get("/projects/{project_id}/branches")
async def get_project_branches(
    project_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: CurrentUser = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get branches for a project's linked GitHub repository.

    Args:
        project_id: Project ID

    Returns:
        Repository branches information
    """
    try:
        service = ProjectGitHubService()
        result = await service.get_project_repository_branches(db, current_user, project_id)

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting project branches: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get project branches: {str(e)}"
        )


@router.post("/generations/{generation_id}/auto-sync")
async def auto_sync_generation(
    generation_id: str,
    db: AsyncSession = Depends(get_async_db)
) -> Dict[str, Any]:
    """
    Auto-sync a completed generation to its linked GitHub repository.

    This endpoint is typically called by the generation completion handler.

    Args:
        generation_id: Generation ID

    Returns:
        Sync operation result
    """
    try:
        service = ProjectGitHubService()
        result = await service.sync_generation_to_repo(db, generation_id)

        if not result["success"]:
            logger.warning(f"Auto-sync failed for generation {generation_id}: {result['error']}")

        return result

    except Exception as e:
        logger.error(f"Error auto-syncing generation: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


